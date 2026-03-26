"""
Scoring criterion: Unit Economics & Cash Flow (max 20 points).
  fcf_positive:         4 pts — positive FCF
  fcf_yield:            6 pts — FCF yield ≥ 3–8% tiered
  fcf_to_net_income:    5 pts — earnings quality ratio ≥ 0.5–0.9
  low_capex_intensity:  5 pts — capex/revenue < 5–15%
"""
from __future__ import annotations

from src.shared.types import CriterionScore


def score_unit_economics(
    fcf: float | None,
    fcf_prior: float | None,
    fcf_yield: float | None,
    capex_to_revenue: float | None,
    cfg: dict | None = None,
    net_income: float | None = None,
) -> list[CriterionScore]:
    c = cfg or {}
    scores = []

    # ── FCF positive (4 pts) ─────────────────────────────────────────────────
    fp_max = float(c.get("fcf_positive", {}).get("max_points", 4.0))
    fp_score, fp_evidence = 0.0, "FCF data unavailable"
    if fcf is not None:
        if fcf > 0:
            fp_score = fp_max
            fp_evidence = f"Positive FCF: ${fcf/1e6:.1f}M"
        else:
            fp_score = 0.0
            fp_evidence = f"Negative FCF: ${fcf/1e6:.1f}M"
    scores.append(CriterionScore(name="fcf_positive", score=fp_score, max_score=fp_max, weight=1.0, evidence=fp_evidence))

    # ── FCF yield (6 pts) ────────────────────────────────────────────────────
    fy_max  = float(c.get("fcf_yield", {}).get("max_points", 6.0))
    fy_exc  = c.get("fcf_yield", {}).get("thresholds", {}).get("excellent", 0.08)
    fy_good = c.get("fcf_yield", {}).get("thresholds", {}).get("good",      0.05)
    fy_weak = c.get("fcf_yield", {}).get("thresholds", {}).get("weak",      0.03)

    fy_score, fy_evidence = 0.0, "Unknown"
    if fcf_yield is not None:
        y = float(fcf_yield)
        if y >= fy_exc:
            fy_score = fy_max
            fy_evidence = f"Excellent FCF yield: {y:.1%}"
        elif y >= fy_good:
            fy_score = fy_max * 0.75
            fy_evidence = f"Good FCF yield: {y:.1%}"
        elif y >= fy_weak:
            fy_score = fy_max * 0.4
            fy_evidence = f"Moderate FCF yield: {y:.1%}"
        else:
            fy_score = 0.0
            fy_evidence = f"Low FCF yield: {y:.1%}"
    scores.append(CriterionScore(name="fcf_yield", score=fy_score, max_score=fy_max, weight=1.0, evidence=fy_evidence))

    # ── FCF/Net Income quality ratio (5 pts) ────────────────────────────────
    fni_max = float(c.get("fcf_to_net_income", {}).get("max_points", 5.0))
    fni_exc  = c.get("fcf_to_net_income", {}).get("thresholds", {}).get("excellent", 0.90)
    fni_good = c.get("fcf_to_net_income", {}).get("thresholds", {}).get("good",      0.70)
    fni_weak = c.get("fcf_to_net_income", {}).get("thresholds", {}).get("weak",      0.50)

    fni_score, fni_evidence = 0.0, "Earnings quality data unavailable"
    if fcf is not None and net_income is not None and net_income > 0:
        ratio = float(fcf) / float(net_income)
        # Cap ratio at 5x — above that is usually a one-time item not real quality
        ratio = min(ratio, 5.0)
        if ratio >= fni_exc:
            fni_score = fni_max
            fni_evidence = f"Excellent earnings quality: FCF/NI = {ratio:.1f}x"
        elif ratio >= fni_good:
            fni_score = fni_max * 0.8
            fni_evidence = f"Good earnings quality: FCF/NI = {ratio:.1f}x"
        elif ratio >= fni_weak:
            fni_score = fni_max * 0.5
            fni_evidence = f"Adequate earnings quality: FCF/NI = {ratio:.1f}x"
        else:
            fni_score = 0.0
            fni_evidence = f"Low earnings quality: FCF/NI = {ratio:.1f}x (accruals may be elevated)"
    elif fcf is not None and fcf > 0 and (net_income is None or net_income == 0):
        # FCF positive but NI unavailable — partial credit
        fni_score = fni_max * 0.4
        fni_evidence = f"Positive FCF ${fcf/1e6:.0f}M — NI data unavailable for ratio"
    elif net_income is not None and net_income < 0:
        fni_evidence = "Company unprofitable — earnings quality N/A"
    scores.append(CriterionScore(name="fcf_to_net_income", score=fni_score, max_score=fni_max, weight=1.0, evidence=fni_evidence))

    # ── Capex intensity (5 pts) — lower is better ───────────────────────────
    cx_max  = float(c.get("low_capex_intensity", {}).get("max_points", 5.0))
    cx_exc  = c.get("low_capex_intensity", {}).get("thresholds", {}).get("excellent", 0.05)
    cx_good = c.get("low_capex_intensity", {}).get("thresholds", {}).get("good",      0.10)
    cx_weak = c.get("low_capex_intensity", {}).get("thresholds", {}).get("weak",      0.15)

    cx_score, cx_evidence = 0.0, "Unknown"
    if capex_to_revenue is not None:
        cr = float(capex_to_revenue)
        if cr <= cx_exc:
            cx_score = cx_max
            cx_evidence = f"Asset-light: capex/rev {cr:.1%}"
        elif cr <= cx_good:
            cx_score = cx_max * 0.6
            cx_evidence = f"Low capex: capex/rev {cr:.1%}"
        elif cr <= cx_weak:
            cx_score = cx_max * 0.2
            cx_evidence = f"Moderate capex: capex/rev {cr:.1%}"
        else:
            cx_score = 0.0
            cx_evidence = f"Capital intensive: capex/rev {cr:.1%}"
    scores.append(CriterionScore(name="low_capex_intensity", score=cx_score, max_score=cx_max, weight=1.0, evidence=cx_evidence))

    return scores
