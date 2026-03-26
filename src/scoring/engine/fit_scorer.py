"""
Phoenician Fit Score calculator (0–100).

Key design principle: ADDITIVE BONUS MODEL
- Every criterion is a bonus, never a penalty
- Missing data = 0 points added, NOT a deduction
- Score = points_earned / max_of_available_criteria * 100
- This ensures companies are scored on what we know, not penalised for what we don't
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

# Criteria that are considered "unmeasurable" when data is missing
# These are excluded from the denominator when None, rather than scoring 0
_OPTIONAL_CRITERIA = {
    "founder_led",
    "insider_ownership",
    "recent_insider_buying",
    "insider_conviction",
    "analyst_coverage",
    "recurring_revenue",
    "international_expansion",
    "management_quality_signal",
    "margin_expansion",
    "peg_ratio",
}


def _is_criteria_missing_data(criterion: CriterionScore) -> bool:
    """Return True if criterion scored 0 due to missing data (not due to failing)."""
    missing_indicators = {
        "Unknown", "unavailable", "data unavailable", "Coverage unknown",
        "No insider buying", "No recent cluster", "No transcript", "PEG data unavailable",
        "Margin expansion data unavailable", "Earnings quality data unavailable",
    }
    return (
        criterion.score == 0.0
        and criterion.name in _OPTIONAL_CRITERIA
        and any(ind.lower() in (criterion.evidence or "").lower() for ind in missing_indicators)
    )


class FitScorer:
    """Compute Phoenician Fit Score for a company using additive bonus model."""

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

        # ── A. Founder / Ownership ────────────────────────────────────────────
        founder_scores = score_founder_ownership(
            is_founder_led=company.is_founder_led,
            insider_ownership_pct=_f(metrics.insider_ownership_pct),
            cfg=founder_cfg,
            cluster_purchases=cluster_purchases or [],
            current_price=current_price,
            week52_low=week52_low,
        )
        all_criteria.extend(founder_scores)

        # ── B. Business Quality ───────────────────────────────────────────────
        has_pricing_power = None
        if claims:
            has_pricing_power = any(
                c.get("type") == "pricing_power" and c.get("confidence", 0) > 0.5
                for c in claims
            )
        elif metrics.gross_margin is not None:
            has_pricing_power = float(metrics.gross_margin) > 0.50

        # Use ebit_margin directly — more accurate than roic*2 proxy
        ebit_margin = _f(metrics.ebit_margin)
        if ebit_margin is None and metrics.ebit is not None and metrics.revenue is not None:
            rev = float(metrics.revenue)
            if rev > 0:
                ebit_margin = float(metrics.ebit) / rev

        quality_scores = score_business_quality(
            gross_margin=_f(metrics.gross_margin),
            roic=_f(metrics.roic),
            revenue_growth_3yr=_f(metrics.revenue_growth_3yr_cagr),
            has_pricing_power=has_pricing_power,
            cfg=quality_cfg,
            operating_margin=ebit_margin,
            roa=_f(metrics.roic),     # use ROIC as ROA proxy when ROA unavailable
            roe=_f(metrics.roe),
            revenue_growth_yoy=_f(metrics.revenue_growth_yoy),
            net_income_growth_yoy=None,
        )
        all_criteria.extend(quality_scores)

        # Management quality signal
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

        # ── C. Unit Economics ─────────────────────────────────────────────────
        # Cap FCF yield at 50% — above that is a data error (placeholder market cap)
        fcf_yield = _f(metrics.fcf_yield)
        if fcf_yield is not None and fcf_yield > 0.50:
            fcf_yield = None  # treat as missing, not 50%+ yield

        unit_scores = score_unit_economics(
            fcf=_f(metrics.fcf),
            fcf_prior=None,
            fcf_yield=fcf_yield,
            capex_to_revenue=_f(metrics.capex_to_revenue),
            cfg=unit_cfg,
            net_income=_f(metrics.net_income),
        )
        all_criteria.extend(unit_scores)

        # ── D. Valuation ──────────────────────────────────────────────────────
        medians = sector_medians or {}
        val_scores = score_valuation(
            ev_ebit=_f(metrics.ev_ebit),
            ev_fcf=_f(metrics.ev_fcf),
            sector_median_ev_ebit=_f(medians.get("median_ev_ebit")),
            sector_median_ev_fcf=_f(medians.get("median_ev_fcf")),
            cfg=val_cfg,
        )
        all_criteria.extend(val_scores)

        # ── E. Information Edge ───────────────────────────────────────────────
        edge_scores = score_information_edge(
            analyst_count=metrics.analyst_count,
            market_cap=_f(metrics.market_cap_usd),
            cfg=edge_cfg,
        )
        all_criteria.extend(edge_scores)

        # ── F. Scalability ────────────────────────────────────────────────────
        has_intl = None
        has_recurring = None
        if claims:
            has_intl      = any(c.get("type") == "international_expansion" for c in claims)
            has_recurring = any(c.get("type") == "recurring_revenue" for c in claims)
        else:
            # International: non-US companies inherently have international exposure
            if company.country and company.country not in ("US", ""):
                has_intl = True

            # Recurring revenue: broader sector heuristics
            sector = (company.gics_sector or "").lower()
            gm = float(metrics.gross_margin) if metrics.gross_margin is not None else 0
            recurring_sectors = ("technology", "software", "healthcare", "financial services")
            if any(s in sector for s in recurring_sectors) and gm > 0.50:
                has_recurring = True

        scale_scores = score_scalability(
            has_tam_narrative=None,
            has_international_expansion=has_intl,
            has_recurring_revenue=has_recurring,
            cfg=scale_cfg,
        )
        all_criteria.extend(scale_scores)

        # ── ADDITIVE BONUS SCORING ────────────────────────────────────────────
        # Score = earned_points / available_max * 100
        # "Available max" excludes criteria where data is missing
        # This means a company is never penalised for data we don't have

        earned = 0.0
        available_max = 0.0

        for criterion in all_criteria:
            if _is_criteria_missing_data(criterion):
                # Data unavailable — exclude from denominator entirely
                # The company neither gains nor loses points
                continue
            earned += criterion.score
            available_max += criterion.max_score

        if available_max <= 0:
            total = 0.0
        else:
            # Normalise to 100
            total = min(100.0, max(0.0, (earned / available_max) * 100.0))

        logger.info("Fit score for %s: %.1f/100 (earned %.1f / available %.1f)",
                    company.ticker, total, earned, available_max)
        return total, all_criteria
