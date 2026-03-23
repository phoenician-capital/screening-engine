"""
Phoenician Fit Score calculator (0–100).
Aggregates all criteria into a single composite score.
"""
from __future__ import annotations

import logging

from src.db.models.company import Company
from src.db.models.metric import Metric
from src.scoring.criteria import (
    score_business_quality,
    score_founder_ownership,
    score_information_edge,
    score_management_quality,
    score_scalability,
    score_unit_economics,
    score_valuation,
)
from src.shared.types import CriterionScore, ScoringResult

logger = logging.getLogger(__name__)


class FitScorer:
    """Compute Phoenician Fit Score for a company."""

    def score(
        self,
        company: Company,
        metrics: Metric,
        sector_medians: dict | None = None,
        claims: list[dict] | None = None,
        cluster_purchases: list | None = None,
        current_price: float | None = None,
        week52_low: float | None = None,
        transcript_signals: dict | None = None,
    ) -> tuple[float, list[CriterionScore]]:
        all_criteria: list[CriterionScore] = []

        from src.config.scoring_weights import load_scoring_weights
        weights = load_scoring_weights()
        sub = weights.get("categories", {})
        founder_cfg = sub.get("founder_ownership",   {}).get("sub_criteria", {})
        quality_cfg = sub.get("business_quality",    {}).get("sub_criteria", {})
        unit_cfg    = sub.get("unit_economics",      {}).get("sub_criteria", {})
        edge_cfg    = sub.get("information_edge",    {}).get("sub_criteria", {})
        scale_cfg   = sub.get("scalability",         {}).get("sub_criteria", {})
        val_cfg     = sub.get("valuation_asymmetry", {}).get("sub_criteria", {})

        def _f(v) -> float | None:
            return float(v) if v is not None else None

        # ── A. Founder / Ownership (max 20) ──────────────────────────────────
        founder_scores = score_founder_ownership(
            is_founder_led=company.is_founder_led,
            insider_ownership_pct=_f(metrics.insider_ownership_pct),
            cfg=founder_cfg,
            cluster_purchases=cluster_purchases or [],
            current_price=current_price,
            week52_low=week52_low,
        )
        all_criteria.extend(founder_scores)

        # ── B. Business Quality (max 25) ─────────────────────────────────────
        has_pricing_power = None
        if claims:
            has_pricing_power = any(
                c.get("type") == "pricing_power" and c.get("confidence", 0) > 0.5
                for c in claims
            )
        elif metrics.gross_margin is not None:
            has_pricing_power = float(metrics.gross_margin) > 0.50

        quality_scores = score_business_quality(
            gross_margin=_f(metrics.gross_margin),
            roic=_f(metrics.roic),
            revenue_growth_3yr=_f(metrics.revenue_growth_3yr_cagr),
            has_pricing_power=has_pricing_power,
            cfg=quality_cfg,
            revenue_growth_yoy=_f(metrics.revenue_growth_yoy),
            net_income_growth_yoy=None,  # not yet in Metric model — placeholder
        )
        all_criteria.extend(quality_scores)

        # Management quality signal (separate criterion in business_quality)
        mgmt_cfg = quality_cfg.get("management_quality_signal", {})
        ts = transcript_signals or {}
        mgmt_scores = score_management_quality(
            guidance_direction=ts.get("guidance_direction"),
            management_tone=ts.get("management_tone"),
            margin_commentary=ts.get("margin_commentary"),
            competitive_positioning=ts.get("competitive_positioning"),
            cfg=mgmt_cfg,
        )
        all_criteria.extend(mgmt_scores)

        # ── C. Unit Economics (max 20) ────────────────────────────────────────
        unit_scores = score_unit_economics(
            fcf=_f(metrics.fcf),
            fcf_prior=None,
            fcf_yield=_f(metrics.fcf_yield),
            capex_to_revenue=_f(metrics.capex_to_revenue),
            cfg=unit_cfg,
            net_income=_f(metrics.net_income),
        )
        all_criteria.extend(unit_scores)

        # ── D. Valuation (max 15) ─────────────────────────────────────────────
        medians = sector_medians or {}
        val_scores = score_valuation(
            ev_ebit=_f(metrics.ev_ebit),
            ev_fcf=_f(metrics.ev_fcf),
            sector_median_ev_ebit=_f(medians.get("median_ev_ebit")),
            sector_median_ev_fcf=_f(medians.get("median_ev_fcf")),
            cfg=val_cfg,
        )
        all_criteria.extend(val_scores)

        # ── E. Information Edge (max 10) ─────────────────────────────────────
        edge_scores = score_information_edge(
            analyst_count=metrics.analyst_count,
            market_cap=_f(metrics.market_cap_usd),
            cfg=edge_cfg,
        )
        all_criteria.extend(edge_scores)

        # ── F. Scalability (max 10) ───────────────────────────────────────────
        has_intl = None
        has_recurring = None
        if claims:
            has_intl     = any(c.get("type") == "international_expansion" for c in claims)
            has_recurring = any(c.get("type") == "recurring_revenue" for c in claims)
        else:
            if company.country and company.country not in ("US", ""):
                has_intl = True
            sector = (company.gics_sector or "").lower()
            gm = float(metrics.gross_margin) if metrics.gross_margin is not None else 0
            if ("technology" in sector or "software" in sector) and gm > 0.60:
                has_recurring = True

        scale_scores = score_scalability(
            has_tam_narrative=None,
            has_international_expansion=has_intl,
            has_recurring_revenue=has_recurring,
            cfg=scale_cfg,
        )
        all_criteria.extend(scale_scores)

        # ── Total ─────────────────────────────────────────────────────────────
        total = min(100.0, max(0.0, sum(c.score for c in all_criteria)))
        logger.info("Fit score for %s: %.1f/100", company.ticker, total)
        return total, all_criteria
