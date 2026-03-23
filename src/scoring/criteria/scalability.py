"""
Scoring criterion: Scalability (max 10 points).
  recurring_revenue:      6 pts — ≥ 40–80% recurring/subscription tiered
  international_expansion: 4 pts — geographic revenue diversification
"""
from __future__ import annotations

from src.shared.types import CriterionScore


def score_scalability(
    has_tam_narrative: bool | None = None,
    has_international_expansion: bool | None = None,
    has_recurring_revenue: bool | None = None,
    cfg: dict | None = None,
    recurring_revenue_pct: float | None = None,
) -> list[CriterionScore]:
    c = cfg or {}
    scores = []

    # ── Recurring revenue (6 pts) ────────────────────────────────────────────
    rr_max  = float(c.get("recurring_revenue", {}).get("max_points", 6.0))
    rr_exc  = c.get("recurring_revenue", {}).get("thresholds", {}).get("excellent", 0.80)
    rr_good = c.get("recurring_revenue", {}).get("thresholds", {}).get("good",      0.60)
    rr_weak = c.get("recurring_revenue", {}).get("thresholds", {}).get("weak",      0.40)

    rr_score, rr_evidence = 0.0, "Recurring revenue data unavailable"

    if recurring_revenue_pct is not None:
        p = float(recurring_revenue_pct)
        if p >= rr_exc:
            rr_score = rr_max
            rr_evidence = f"High recurring revenue: {p:.0%}"
        elif p >= rr_good:
            rr_score = rr_max * 0.75
            rr_evidence = f"Good recurring revenue: {p:.0%}"
        elif p >= rr_weak:
            rr_score = rr_max * 0.4
            rr_evidence = f"Some recurring revenue: {p:.0%}"
        else:
            rr_score = 0.0
            rr_evidence = f"Low recurring revenue: {p:.0%}"
    elif has_recurring_revenue is True:
        rr_score = rr_max * 0.6
        rr_evidence = "Recurring/subscription revenue model detected"
    elif has_recurring_revenue is False:
        rr_evidence = "No recurring revenue model detected"

    scores.append(CriterionScore(name="recurring_revenue", score=rr_score, max_score=rr_max, weight=1.0, evidence=rr_evidence))

    # ── International expansion (4 pts) ─────────────────────────────────────
    ie_max = float(c.get("international_expansion", {}).get("max_points", 4.0))
    ie_score, ie_evidence = 0.0, "International revenue data unavailable"
    if has_international_expansion is True:
        ie_score = ie_max
        ie_evidence = "Geographic revenue diversification confirmed"
    elif has_international_expansion is False:
        ie_score = 0.0
        ie_evidence = "Domestic revenue only"
    scores.append(CriterionScore(name="international_expansion", score=ie_score, max_score=ie_max, weight=1.0, evidence=ie_evidence))

    return scores
