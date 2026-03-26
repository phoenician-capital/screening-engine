"""
Risk / Deduction score (0–100, higher = riskier).
Per Phoenician Capital Round 3 criteria.

Design: Every company gets a realistic risk score based on available data.
Risk is never 0 — every investment has some risk. Minimum risk score is 5.
Missing data = assume moderate risk (not zero risk).
"""
from __future__ import annotations

import logging

from src.db.models.metric import Metric
from src.shared.types import CriterionScore

logger = logging.getLogger(__name__)

# Countries with elevated but not disqualifying risk
_ELEVATED_RISK_COUNTRIES = {"BR", "IN", "MX", "ID", "TR"}
# Countries that are high-risk but not excluded (excluded ones filtered in hard filter)
_HIGH_RISK_COUNTRIES = {"CN", "RU", "IR", "KP", "SY", "BY"}
# Countries with lower institutional quality / weaker shareholder protections
_MODERATE_RISK_COUNTRIES = {"IL", "PL", "GR", "AR", "CL", "CO", "PE", "TH", "VN", "PH", "MY"}


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

        # ── 1. Leverage risk (0–25) ───────────────────────────────────────────
        lev_max = float(rc.get("leverage", {}).get("max_points", 25.0))
        lev_thr = rc.get("leverage", {}).get("thresholds", {})
        low_thr  = float(lev_thr.get("low",    2.0))
        med_thr  = float(lev_thr.get("medium", 3.0))
        high_thr = float(lev_thr.get("high",   4.0))

        lev_score = 0.0
        lev_ev    = "Leverage data unavailable — moderate risk assumed"

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
            elif nd < -1.0:
                # Net cash — very low leverage risk
                lev_score = 0.0
                lev_ev = f"Net cash position: {abs(nd):.1f}x — no leverage risk"
            else:
                lev_score = lev_max * 0.10
                lev_ev = f"Low leverage: {nd:.1f}x"
        else:
            # No leverage data — try to infer from net_debt and ebitda
            if metrics.net_debt is not None and metrics.net_income is not None:
                ni = float(metrics.net_income)
                nd_val = float(metrics.net_debt)
                if ni > 0:
                    # Use NI as EBITDA proxy (conservative)
                    proxy_ratio = nd_val / (ni * 1.5)  # assume EBITDA ~ 1.5x NI
                    if proxy_ratio > 4.0:
                        lev_score = lev_max * 0.8
                        lev_ev = f"Estimated high leverage: ND/EBITDA proxy ~{proxy_ratio:.1f}x"
                    elif proxy_ratio > 2.0:
                        lev_score = lev_max * 0.4
                        lev_ev = f"Estimated moderate leverage: proxy ~{proxy_ratio:.1f}x"
                    else:
                        lev_score = lev_max * 0.15
                        lev_ev = f"Estimated low leverage: proxy ~{proxy_ratio:.1f}x"
                elif nd_val > 0:
                    # Has net debt but no income — risky
                    lev_score = lev_max * 0.60
                    lev_ev = "Net debt present, profitability weak — leverage risk elevated"
            else:
                # Truly unknown — assign small baseline risk
                lev_score = lev_max * 0.12
        criteria.append(CriterionScore(name="leverage", score=lev_score, max_score=lev_max, weight=1.0, evidence=lev_ev))

        # ── 2. Profitability risk (0–20) ──────────────────────────────────────
        unp_max   = float(rc.get("unprofitable", {}).get("max_points", 20.0))
        unp_score = 0.0
        unp_ev    = "Profitability data unavailable"

        if metrics.net_income is not None:
            ni = float(metrics.net_income)
            if ni < 0:
                unp_score = unp_max
                unp_ev = f"Net income negative: ${ni/1e6:.1f}M"
            elif metrics.revenue and float(metrics.revenue) > 0:
                net_margin = ni / float(metrics.revenue)
                if net_margin < 0.03:
                    # Barely profitable — fragile
                    unp_score = unp_max * 0.30
                    unp_ev = f"Thin profitability: net margin {net_margin:.1%}"
                elif net_margin < 0.08:
                    unp_score = unp_max * 0.10
                    unp_ev = f"Adequate profitability: net margin {net_margin:.1%}"
                else:
                    unp_score = 0.0
                    unp_ev = f"Profitable: NI ${ni/1e6:.0f}M (margin {net_margin:.1%})"
            else:
                unp_score = 0.0
                unp_ev = f"Profitable: NI ${ni/1e6:.0f}M"
        else:
            # Unknown profitability — small baseline risk
            unp_score = unp_max * 0.15
            unp_ev = "Profitability unknown — moderate risk assumed"
        criteria.append(CriterionScore(name="unprofitable", score=unp_score, max_score=unp_max, weight=1.0, evidence=unp_ev))

        # ── 3. Earnings quality risk (0–15) ───────────────────────────────────
        eq_max = float(rc.get("earnings_quality", {}).get("max_points", 15.0))
        eq_thr = float(rc.get("earnings_quality", {}).get("threshold", 0.50))
        eq_score = 0.0
        eq_ev    = "Earnings quality data unavailable"

        if metrics.fcf is not None and metrics.net_income is not None:
            ni  = float(metrics.net_income)
            fcf = float(metrics.fcf)
            if ni > 0:
                ratio = fcf / ni
                if ratio < 0.0:
                    eq_score = eq_max
                    eq_ev = f"Poor earnings quality: negative FCF despite positive NI (ratio {ratio:.2f})"
                elif ratio < eq_thr:
                    eq_score = eq_max * 0.70
                    eq_ev = f"Low earnings quality: FCF/NI = {ratio:.2f} — accruals elevated"
                elif ratio < 0.70:
                    eq_score = eq_max * 0.30
                    eq_ev = f"Moderate earnings quality: FCF/NI = {ratio:.2f}"
                else:
                    eq_score = 0.0
                    eq_ev = f"Good earnings quality: FCF/NI = {ratio:.2f}"
            elif ni < 0 and fcf > 0:
                # Negative NI but positive FCF — accounting losses, not cash losses
                eq_score = eq_max * 0.20
                eq_ev = f"Accounting loss but positive FCF ${fcf/1e6:.0f}M — review non-cash items"
            elif ni < 0 and fcf < 0:
                eq_score = eq_max * 0.60
                eq_ev = f"Both NI and FCF negative — cash burning"
        elif metrics.fcf is not None and float(metrics.fcf) < 0:
            eq_score = eq_max * 0.40
            eq_ev = f"Negative FCF: ${float(metrics.fcf)/1e6:.0f}M — cash consumption"
        criteria.append(CriterionScore(name="earnings_quality", score=eq_score, max_score=eq_max, weight=1.0, evidence=eq_ev))

        # ── 4. Revenue concentration / customer risk (0–10) ──────────────────
        conc_max   = float(rc.get("customer_concentration", {}).get("max_points", 10.0))
        conc_score = 0.0
        conc_ev    = "No concentration signal detected"

        if claims:
            conc_claims = [c for c in claims if c.get("type") == "customer_concentration_risk"]
            if conc_claims:
                conc_score = conc_max * max(c.get("confidence", 0.5) for c in conc_claims)
                conc_ev = "Customer concentration risk detected in filings"

        # Also check if company is small with few revenue streams (proxy)
        if metrics.revenue and float(metrics.revenue) < 200_000_000:
            if conc_score == 0.0:
                conc_score = conc_max * 0.20  # small companies inherently more concentrated
                conc_ev = "Small company: elevated customer concentration risk by size"
        criteria.append(CriterionScore(name="customer_concentration", score=conc_score, max_score=conc_max, weight=1.0, evidence=conc_ev))

        # ── 5. Geographic / jurisdiction risk (0–15) ─────────────────────────
        geo_max   = float(rc.get("geographic_risk", {}).get("max_points", 15.0))
        geo_score = 0.0
        geo_ev    = f"Jurisdiction: {country or 'Unknown'}"

        ctry = (country or "").upper()
        if ctry in _HIGH_RISK_COUNTRIES:
            geo_score = geo_max
            geo_ev = f"High-risk jurisdiction: {country}"
        elif ctry in _ELEVATED_RISK_COUNTRIES:
            geo_score = geo_max * 0.65
            geo_ev = f"Elevated-risk jurisdiction: {country} — EM currency/political risk"
        elif ctry in _MODERATE_RISK_COUNTRIES:
            geo_score = geo_max * 0.35
            geo_ev = f"Moderate jurisdiction risk: {country} — weaker institutional framework"
        elif ctry not in ("US", "GB", "CA", "AU", "NZ", "DE", "FR", "NL",
                          "SE", "NO", "DK", "FI", "CH", "AT", "BE", "IE",
                          "SG", "JP", "HK", "KR"):
            # Unknown or less common jurisdiction — small baseline risk
            geo_score = geo_max * 0.15
            geo_ev = f"Jurisdiction: {country or 'Unknown'} — limited data on regulatory framework"
        else:
            geo_score = 0.0
            geo_ev = f"Low jurisdiction risk: {country}"
        criteria.append(CriterionScore(name="geographic_risk", score=geo_score, max_score=geo_max, weight=1.0, evidence=geo_ev))

        # ── 6. Valuation risk — is this priced for perfection? (0–10) ────────
        val_max   = float(rc.get("red_flags", {}).get("max_points", 10.0))
        val_score = 0.0
        val_ev    = "No valuation red flags"

        if metrics.ev_ebit is not None:
            ee = float(metrics.ev_ebit)
            if 0 < ee > 50:
                val_score = val_max * 0.50
                val_ev = f"Priced for perfection: EV/EBIT {ee:.1f}x — limited margin of safety"
            elif 0 < ee > 35:
                val_score = val_max * 0.25
                val_ev = f"High valuation: EV/EBIT {ee:.1f}x — execution dependent"

        # Also check claims for red flags
        if claims:
            flag_types = {"regulatory_risk", "accounting_concern", "management_change",
                         "litigation_risk", "restatement"}
            flagged = [c for c in claims if c.get("type") in flag_types]
            if flagged:
                flag_score = val_max * min(1.0, len(flagged) / 2)
                if flag_score > val_score:
                    val_score = flag_score
                    types = list({c["type"] for c in flagged})
                    val_ev = f"Red flags: {', '.join(t.replace('_', ' ') for t in types)}"
        criteria.append(CriterionScore(name="red_flags", score=val_score, max_score=val_max, weight=1.0, evidence=val_ev))

        total = min(100.0, max(0.0, sum(c.score for c in criteria)))

        # Minimum risk floor — no investment is zero risk
        if total < 5.0:
            total = 5.0
            for c in criteria:
                if c.name == "leverage":
                    c.score = max(c.score, 5.0 - sum(x.score for x in criteria if x.name != "leverage"))
                    break

        logger.info("Risk score: %.1f/100", total)
        return total, criteria
