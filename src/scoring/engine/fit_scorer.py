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
    score_capital_allocation,
    score_balance_sheet,
    score_quality_trifecta,
    score_earnings_integrity,
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
    """Compute Phoenician Fit Score using AI Financial Analyst Agent + Python supplementary signals."""

    async def score(
        self,
        company: Company,
        metrics: Metric,
        sector_medians: dict | None = None,
        claims: list[dict] | None = None,
        cluster_purchases: list | None = None,
        current_price: float | None = None,
        week52_low: float | None = None,
        transcript_signals: dict | None = None,
        historical: list[dict] | None = None,
        portfolio_avg: dict | None = None,
        feedback_context: str | None = None,
    ) -> tuple[float, list[CriterionScore]]:
        from src.scoring.engine.analyst_agent import score_with_analyst_agent

        all_criteria: list[CriterionScore] = []

        # ── STEP 1: AI Financial Analyst Agent (primary scoring) ──────────────
        # Called directly as async — parallelism handled by asyncio.gather in pipeline
        try:
            agent_criteria = await score_with_analyst_agent(
                company, metrics, historical, portfolio_avg, sector_medians, feedback_context,
                current_price=current_price,
                market_tier=getattr(company, "market_tier", 1) or 1,
            )
        except Exception as e:
            logger.warning("Agent scoring failed for %s: %s", company.ticker, e)
            agent_criteria = []

        if agent_criteria:
            all_criteria.extend(agent_criteria)
            logger.info("Using agent scoring for %s (%d dimensions)", company.ticker, len(agent_criteria))
        else:
            logger.info("Using Python threshold scoring for %s (agent unavailable)", company.ticker)

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

        # Agent already covers: business_quality, unit_economics, capital_returns,
        # growth_quality, balance_sheet, phoenician_fit
        # Python adds: founder/ownership signals, insider buying, bonus criteria
        # These are supplementary — agent handles the core quality dimensions

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

        # ── B–D. Python scoring (only when agent unavailable) ────────────────
        if not agent_criteria:
            has_pricing_power = None
            if claims:
                has_pricing_power = any(
                    c.get("type") == "pricing_power" and c.get("confidence", 0) > 0.5
                    for c in claims
                )
            elif metrics.gross_margin is not None:
                has_pricing_power = float(metrics.gross_margin) > 0.50

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
                roa=_f(metrics.roic),
                roe=_f(metrics.roe),
                revenue_growth_yoy=_f(metrics.revenue_growth_yoy),
                net_income_growth_yoy=None,
            )
            all_criteria.extend(quality_scores)

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

            fcf_yield = _f(metrics.fcf_yield)
            if fcf_yield is not None and fcf_yield > 0.50:
                fcf_yield = None

            unit_scores = score_unit_economics(
                fcf=_f(metrics.fcf),
                fcf_prior=None,
                fcf_yield=fcf_yield,
                capex_to_revenue=_f(metrics.capex_to_revenue),
                cfg=unit_cfg,
                net_income=_f(metrics.net_income),
            )
            all_criteria.extend(unit_scores)

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

            # International revenue %: extract from description
            desc = (company.description or "").lower() if hasattr(company, "description") else ""
            import re as _re
            intl_match = _re.search(r'(\d+)%.*?international|international.*?(\d+)%', desc)
            if intl_match:
                pct = int(intl_match.group(1) or intl_match.group(2) or 0)
                if pct >= 20:
                    has_intl = True

            # Recurring revenue: keyword scan in company description
            _RECURRING_KEYWORDS = (
                "subscription", "saas", "software-as-a-service", "recurring revenue",
                "annual recurring", "maintenance contract", "service contract",
                "managed services", "licensing", "royalt", "platform fee",
                "monthly active", "annual contract value", "arr ", "mrr ",
            )
            if any(kw in desc for kw in _RECURRING_KEYWORDS):
                has_recurring = True
            else:
                # Sector heuristic fallback
                sector = (company.gics_sector or "").lower()
                gm = float(metrics.gross_margin) if metrics.gross_margin is not None else 0
                recurring_sectors = ("technology", "software", "healthcare services")
                if any(s in sector for s in recurring_sectors) and gm > 0.60:
                    has_recurring = True

        scale_scores = score_scalability(
            has_tam_narrative=None,
            has_international_expansion=has_intl,
            has_recurring_revenue=has_recurring,
            cfg=scale_cfg,
        )
        all_criteria.extend(scale_scores)

        # ── G. Quality Trifecta (bonus, max 5) ───────────────────────────────
        # Awards extra points when GM + ROIC + FCF yield all above threshold
        fcf_yield_for_trifecta = _f(metrics.fcf_yield)
        if fcf_yield_for_trifecta and fcf_yield_for_trifecta > 0.50:
            fcf_yield_for_trifecta = None  # cap anomalies
        trifecta_scores = score_quality_trifecta(
            gross_margin=_f(metrics.gross_margin),
            roic=_f(metrics.roic),
            fcf_yield=fcf_yield_for_trifecta,
        )
        all_criteria.extend(trifecta_scores)

        # ── H. Capital Allocation (bonus, max 6) ─────────────────────────────
        cap_alloc_scores = score_capital_allocation(
            stock_repurchased=_f(metrics.stock_repurchased) if hasattr(metrics, "stock_repurchased") else None,
            stock_based_comp=_f(metrics.stock_based_compensation) if hasattr(metrics, "stock_based_compensation") else None,
            acquisitions_net=_f(metrics.acquisitions_net) if hasattr(metrics, "acquisitions_net") else None,
            revenue=_f(metrics.revenue),
            market_cap=_f(metrics.market_cap_usd),
        )
        all_criteria.extend(cap_alloc_scores)

        # ── I. Balance Sheet Quality (bonus, max 5) ───────────────────────────
        bs_scores = score_balance_sheet(
            net_debt=_f(metrics.net_debt) if hasattr(metrics, "net_debt") else None,
            current_ratio=_f(metrics.current_ratio) if hasattr(metrics, "current_ratio") else None,
            goodwill=_f(metrics.goodwill) if hasattr(metrics, "goodwill") else None,
            total_assets=_f(metrics.total_assets),
            cash=_f(metrics.cash) if hasattr(metrics, "cash") else None,
            market_cap=_f(metrics.market_cap_usd),
        )
        all_criteria.extend(bs_scores)

        # ── J. Earnings Integrity (bonus, max 3) ─────────────────────────────
        ei_scores = score_earnings_integrity(
            revenue=_f(metrics.revenue),
            revenue_prior=_f(metrics.revenue_prior_year) if hasattr(metrics, "revenue_prior_year") else None,
            accounts_receivable=_f(metrics.accounts_receivable) if hasattr(metrics, "accounts_receivable") else None,
            accounts_receivable_prior=_f(metrics.accounts_receivable_prior) if hasattr(metrics, "accounts_receivable_prior") else None,
            net_income=_f(metrics.net_income),
            fcf=_f(metrics.fcf),
        )
        all_criteria.extend(ei_scores)

        # ── FINAL SCORE COMPUTATION ───────────────────────────────────────────
        # If agent ran: use overall_fit_score directly (LLM's holistic judgment)
        # If agent failed: use additive Python threshold scoring

        overall_fit_criterion = next(
            (c for c in all_criteria if c.name == "overall_fit"), None
        )

        if overall_fit_criterion is not None and overall_fit_criterion.score > 0:
            # LLM gave us a holistic overall score — use it directly
            total = min(100.0, max(0.0, overall_fit_criterion.score))
            logger.info("Fit score for %s: %.1f/100 (LLM overall_fit)",
                        company.ticker, total)
        else:
            # Python fallback: additive bonus scoring
            earned = 0.0
            available_max = 0.0
            for criterion in all_criteria:
                if _is_criteria_missing_data(criterion):
                    continue
                if criterion.name in ("overall_fit", "llm_risk_score", "analyst_thesis"):
                    continue
                earned += criterion.score
                available_max += criterion.max_score

            if available_max <= 0:
                total = 0.0
            else:
                total = min(100.0, max(0.0, (earned / available_max) * 100.0))
            logger.info("Fit score for %s: %.1f/100 (Python fallback, earned %.1f / available %.1f)",
                        company.ticker, total, earned, available_max)

        return total, all_criteria
