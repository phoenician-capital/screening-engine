"""
Risk / Deduction score (0–100, higher = riskier).
Per Phoenician Capital Round 3 criteria.
"""
from __future__ import annotations

import logging

from src.db.models.metric import Metric
from src.shared.types import CriterionScore

logger = logging.getLogger(__name__)


class RiskScorer:
    """Compute aggregate risk score for a company."""

    def score(
        self,
        metrics: Metric,
        claims: list[dict] | None = None,
        country: str | None = None,
    ) -> tuple[float, list[CriterionScore]]:
        from src.config.scoring_weights import load_scoring_weights
        w = load_scoring_weights()
        rc = w.get("risk_criteria", {})
        criteria: list[CriterionScore] = []

        # ── Leverage risk (0–25) ──────────────────────────────────────────────
        lev_max = float(rc.get("leverage", {}).get("max_points", 25.0))
        lev_thr = rc.get("leverage", {}).get("thresholds", {})
        low_thr  = float(lev_thr.get("low",  2.0))
        med_thr  = float(lev_thr.get("medium", 3.0))
        high_thr = float(lev_thr.get("high",  4.0))

        lev_score = 0.0
        lev_ev = "Leverage data unavailable"
        if metrics.net_debt_ebitda is not None:
            nd = float(metrics.net_debt_ebitda)
            if nd > high_thr:
                lev_score = lev_max
                lev_ev = f"High leverage: {nd:.1f}x Net Debt/EBITDA"
            elif nd > med_thr:
                lev_score = lev_max * 0.72
                lev_ev = f"Elevated leverage: {nd:.1f}x"
            elif nd > low_thr:
                lev_score = lev_max * 0.40
                lev_ev = f"Moderate leverage: {nd:.1f}x"
            else:
                lev_score = 0.0
                lev_ev = f"Low leverage: {nd:.1f}x"
        criteria.append(CriterionScore(name="leverage", score=lev_score, max_score=lev_max, weight=1.0, evidence=lev_ev))

        # ── Unprofitable (0–20) ──────────────────────────────────────────────
        unp_max = float(rc.get("unprofitable", {}).get("max_points", 20.0))
        unp_score = 0.0
        unp_ev = "Company profitable"
        if metrics.net_income is not None:
            ni = float(metrics.net_income)
            if ni < 0:
                unp_score = unp_max
                unp_ev = f"Net income negative: ${ni/1e6:.1f}M"
            else:
                unp_ev = f"Profitable: NI ${ni/1e6:.1f}M"
        criteria.append(CriterionScore(name="unprofitable", score=unp_score, max_score=unp_max, weight=1.0, evidence=unp_ev))

        # ── Earnings quality (0–15) ───────────────────────────────────────────
        eq_max = float(rc.get("earnings_quality", {}).get("max_points", 15.0))
        eq_thr = float(rc.get("earnings_quality", {}).get("threshold", 0.50))
        eq_score = 0.0
        eq_ev = "Earnings quality data unavailable"
        if metrics.fcf is not None and metrics.net_income is not None:
            ni = float(metrics.net_income)
            fcf = float(metrics.fcf)
            if ni > 0:
                ratio = fcf / ni
                if ratio < eq_thr:
                    eq_score = eq_max
                    eq_ev = f"Low earnings quality: FCF/NI = {ratio:.2f} (accruals may be elevated)"
                else:
                    eq_ev = f"Good earnings quality: FCF/NI = {ratio:.2f}"
        criteria.append(CriterionScore(name="earnings_quality", score=eq_score, max_score=eq_max, weight=1.0, evidence=eq_ev))

        # ── Customer concentration (0–15) — from claims ──────────────────────
        conc_max = float(rc.get("customer_concentration", {}).get("max_points", 15.0))
        conc_score = 0.0
        conc_ev = "No concentration signal"
        if claims:
            conc_claims = [c for c in claims if c.get("type") == "customer_concentration_risk"]
            if conc_claims:
                conc_score = conc_max * max(c.get("confidence", 0.5) for c in conc_claims)
                conc_ev = "Customer concentration risk detected"
        criteria.append(CriterionScore(name="customer_concentration", score=conc_score, max_score=conc_max, weight=1.0, evidence=conc_ev))

        # ── Geographic / EM risk (0–15) ───────────────────────────────────────
        geo_max = float(rc.get("geographic_risk", {}).get("max_points", 15.0))
        high_risk_countries = set(
            c.upper() for c in rc.get("geographic_risk", {}).get("high_risk_countries", [
                "BR", "IN", "MX", "ID", "TR", "CN", "RU", "IR", "KP", "SY", "BY"
            ])
        )
        geo_score = 0.0
        geo_ev = f"Jurisdiction: {country or 'Unknown'}"
        if country and country.upper() in high_risk_countries:
            geo_score = geo_max
            geo_ev = f"Higher-risk jurisdiction: {country}"
        criteria.append(CriterionScore(name="geographic_risk", score=geo_score, max_score=geo_max, weight=1.0, evidence=geo_ev))

        # ── Red flags (0–10) — regulatory, litigation, restatements ─────────
        rf_max = float(rc.get("red_flags", {}).get("max_points", 10.0))
        rf_score = 0.0
        rf_ev = "No red flags"
        if claims:
            flag_types = {"regulatory_risk", "accounting_concern", "management_change"}
            flagged = [c for c in claims if c.get("type") in flag_types]
            if flagged:
                rf_score = rf_max * min(1.0, len(flagged) / 2)
                types = list({c["type"] for c in flagged})
                rf_ev = f"Red flags: {', '.join(t.replace('_',' ') for t in types)}"
        criteria.append(CriterionScore(name="red_flags", score=rf_score, max_score=rf_max, weight=1.0, evidence=rf_ev))

        total = min(100.0, max(0.0, sum(c.score for c in criteria)))
        logger.info("Risk score: %.1f/100", total)
        return total, criteria
