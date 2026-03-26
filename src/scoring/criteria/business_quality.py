"""
Scoring criterion: Business Quality (max 25 points).
  gross_margin:           5 pts — tiered 15–70%
  operating_margin:       4 pts — tiered 10–25%
  roa_roe:                4 pts — ROA 5–15% or ROE 10–45%, best of both
  revenue_growth:         5 pts — YoY ≥ 8% tiered
  margin_expansion:       3 pts — net income growing faster than revenue
  management_quality:     4 pts — transcript signals
"""
from __future__ import annotations

from src.shared.types import CriterionScore


def _t(cfg: dict, key: str, level: str, default: float) -> float:
    return float(cfg.get(key, {}).get("thresholds", {}).get(level, default))


def score_business_quality(
    gross_margin: float | None,
    roic: float | None,
    revenue_growth_3yr: float | None,
    has_pricing_power: bool | None = None,
    cfg: dict | None = None,
    operating_margin: float | None = None,
    roa: float | None = None,
    roe: float | None = None,
    revenue_growth_yoy: float | None = None,
    net_income_growth_yoy: float | None = None,
) -> list[CriterionScore]:
    c = cfg or {}
    scores = []

    # ── Gross margin (5 pts) ────────────────────────────────────────────────
    gm_max  = float(c.get("gross_margin", {}).get("max_points", 5.0))
    gm_exc  = _t(c, "gross_margin", "excellent", 0.70)
    gm_good = _t(c, "gross_margin", "good",      0.50)
    gm_mod  = _t(c, "gross_margin", "moderate",  0.30)
    gm_weak = _t(c, "gross_margin", "weak",       0.15)

    gm_score, gm_evidence = 0.0, "Unknown"
    if gross_margin is not None:
        g = float(gross_margin)
        if g >= gm_exc:
            gm_score = gm_max
            gm_evidence = f"Exceptional gross margin: {g:.1%}"
        elif g >= gm_good:
            gm_score = gm_max * 0.8
            gm_evidence = f"Strong gross margin: {g:.1%}"
        elif g >= gm_mod:
            gm_score = gm_max * 0.5
            gm_evidence = f"Good gross margin: {g:.1%}"
        elif g >= gm_weak:
            gm_score = gm_max * 0.2
            gm_evidence = f"Moderate gross margin: {g:.1%}"
        else:
            gm_score = 0.0
            gm_evidence = f"Low gross margin: {g:.1%}"
    scores.append(CriterionScore(name="gross_margin", score=gm_score, max_score=gm_max, weight=1.0, evidence=gm_evidence))

    # ── Operating margin (4 pts) ────────────────────────────────────────────
    om_max  = float(c.get("operating_margin", {}).get("max_points", 4.0))
    om_exc  = _t(c, "operating_margin", "excellent", 0.25)
    om_good = _t(c, "operating_margin", "good",      0.15)
    om_weak = _t(c, "operating_margin", "weak",      0.10)

    om_score, om_evidence = 0.0, "Unknown"
    # Use operating_margin (ebit_margin) directly — no proxy
    om_val = operating_margin
    if om_val is not None:
        if om_val >= om_exc:
            om_score = om_max
            om_evidence = f"Excellent operating margin: {om_val:.1%}"
        elif om_val >= om_good:
            om_score = om_max * 0.75
            om_evidence = f"Good operating margin: {om_val:.1%}"
        elif om_val >= om_weak:
            om_score = om_max * 0.4
            om_evidence = f"Moderate operating margin: {om_val:.1%}"
        else:
            om_score = 0.0
            om_evidence = f"Low operating margin: {om_val:.1%}"
    scores.append(CriterionScore(name="operating_margin", score=om_score, max_score=om_max, weight=1.0, evidence=om_evidence))

    # ── ROA/ROE (4 pts) — best of both ─────────────────────────────────────
    rr_max = float(c.get("roa_roe", {}).get("max_points", 4.0))
    rr_cfg = c.get("roa_roe", {}).get("thresholds", {})

    roa_exc  = float(rr_cfg.get("roa_excellent", 0.15))
    roa_good = float(rr_cfg.get("roa_good",      0.08))
    roa_weak = float(rr_cfg.get("roa_weak",      0.05))
    roe_exc  = float(rr_cfg.get("roe_excellent", 0.35))
    roe_good = float(rr_cfg.get("roe_good",      0.20))
    roe_weak = float(rr_cfg.get("roe_weak",      0.10))

    rr_score, rr_evidence = 0.0, "Unknown"
    # Use ROIC as ROA proxy if ROA not available
    roa_val = roa if roa is not None else (float(roic) if roic is not None else None)

    roa_pts, roe_pts = 0.0, 0.0
    roa_ev, roe_ev = "", ""
    if roa_val is not None:
        if roa_val >= roa_exc:
            roa_pts = rr_max
            roa_ev = f"Excellent ROA: {roa_val:.1%}"
        elif roa_val >= roa_good:
            roa_pts = rr_max * 0.67
            roa_ev = f"Good ROA: {roa_val:.1%}"
        elif roa_val >= roa_weak:
            roa_pts = rr_max * 0.33
            roa_ev = f"Moderate ROA: {roa_val:.1%}"
    if roe is not None:
        r = float(roe)
        if r >= roe_exc:
            roe_pts = rr_max
            roe_ev = f"Excellent ROE: {r:.1%}"
        elif r >= roe_good:
            roe_pts = rr_max * 0.67
            roe_ev = f"Good ROE: {r:.1%}"
        elif r >= roe_weak:
            roe_pts = rr_max * 0.33
            roe_ev = f"Moderate ROE: {r:.1%}"
    if roa_pts >= roe_pts:
        rr_score, rr_evidence = roa_pts, roa_ev or "ROA data available"
    else:
        rr_score, rr_evidence = roe_pts, roe_ev
    scores.append(CriterionScore(name="roa_roe", score=rr_score, max_score=rr_max, weight=1.0, evidence=rr_evidence))

    # ── Revenue growth YoY (5 pts) ──────────────────────────────────────────
    rg_max  = float(c.get("revenue_growth", {}).get("max_points", 5.0))
    rg_exc  = _t(c, "revenue_growth", "excellent", 0.20)
    rg_good = _t(c, "revenue_growth", "good",      0.12)
    rg_weak = _t(c, "revenue_growth", "weak",      0.08)

    # Use YoY if available, fall back to 3yr CAGR
    rg_val = revenue_growth_yoy if revenue_growth_yoy is not None else revenue_growth_3yr
    rg_score, rg_evidence = 0.0, "Unknown"
    if rg_val is not None:
        if rg_val >= rg_exc:
            rg_score = rg_max
            rg_evidence = f"Strong revenue growth: {rg_val:.1%}"
        elif rg_val >= rg_good:
            rg_score = rg_max * 0.7
            rg_evidence = f"Good revenue growth: {rg_val:.1%}"
        elif rg_val >= rg_weak:
            rg_score = rg_max * 0.4
            rg_evidence = f"Adequate revenue growth: {rg_val:.1%}"
        elif rg_val >= 0.05:
            rg_score = rg_max * 0.25
            rg_evidence = f"Modest growth: {rg_val:.1%}"
        elif rg_val >= 0.0:
            rg_score = rg_max * 0.10
            rg_evidence = f"Flat revenue: {rg_val:.1%}"
        else:
            rg_score = 0.0
            rg_evidence = f"Revenue declining: {rg_val:.1%}"
    scores.append(CriterionScore(name="revenue_growth", score=rg_score, max_score=rg_max, weight=1.0, evidence=rg_evidence))

    # ── Margin expansion (3 pts) — net income growing faster than revenue ───
    me_max = float(c.get("margin_expansion", {}).get("max_points", 3.0))
    me_score, me_evidence = 0.0, "Margin expansion data unavailable"
    if revenue_growth_yoy is not None and net_income_growth_yoy is not None:
        if net_income_growth_yoy > revenue_growth_yoy and net_income_growth_yoy > 0:
            spread = net_income_growth_yoy - revenue_growth_yoy
            if spread >= 0.10:
                me_score = me_max
                me_evidence = f"Strong margin expansion: NI growing {spread:.1%} faster than revenue"
            else:
                me_score = me_max * 0.6
                me_evidence = f"Margin expansion: NI growing faster than revenue"
        elif net_income_growth_yoy <= 0 and revenue_growth_yoy > 0:
            me_evidence = "Margin contraction: NI declining despite revenue growth"
    scores.append(CriterionScore(name="margin_expansion", score=me_score, max_score=me_max, weight=1.0, evidence=me_evidence))

    # ── Management quality signal (4 pts) — from transcript analysis ────────
    # NOTE: this is populated in fit_scorer.py via score_management_quality()
    # It is NOT computed here to avoid circular dependency.
    # Placeholder kept for correct max_points accounting.

    return scores
