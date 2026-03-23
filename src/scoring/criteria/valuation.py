"""
Scoring criterion: Valuation Asymmetry (max 15 points).
  ev_ebitda:     5 pts — EV/EBITDA ≤ 8–18x tiered
  price_to_fcf:  5 pts — Price/FCF ≤ 12–30x tiered
  peg_ratio:     5 pts — PEG ≤ 0.8–2.0 tiered
"""
from __future__ import annotations

from src.shared.types import CriterionScore


def score_valuation(
    ev_ebit: float | None,
    ev_fcf: float | None,
    sector_median_ev_ebit: float | None = None,
    sector_median_ev_fcf: float | None = None,
    cfg: dict | None = None,
    ev_ebitda: float | None = None,
    price_to_fcf: float | None = None,
    peg_ratio: float | None = None,
) -> list[CriterionScore]:
    c = cfg or {}
    scores = []

    # ── EV/EBITDA (5 pts) ───────────────────────────────────────────────────
    ee_max  = float(c.get("ev_ebitda", {}).get("max_points", 5.0))
    ee_exc  = float(c.get("ev_ebitda", {}).get("thresholds", {}).get("excellent",  8))
    ee_good = float(c.get("ev_ebitda", {}).get("thresholds", {}).get("good",      13))
    ee_fair = float(c.get("ev_ebitda", {}).get("thresholds", {}).get("fair",      18))

    # Use ev_ebitda if available, fall back to ev_ebit as proxy
    ee_val = ev_ebitda if ev_ebitda is not None else ev_ebit
    ee_score, ee_evidence = 0.0, "Unknown"
    if ee_val is not None:
        v = float(ee_val)
        if v <= ee_exc:
            ee_score = ee_max
            ee_evidence = f"Attractive EV/EBITDA: {v:.1f}x (≤{ee_exc:.0f}x)"
        elif v <= ee_good:
            ee_score = ee_max * 0.75
            ee_evidence = f"Good EV/EBITDA: {v:.1f}x"
        elif v <= ee_fair:
            ee_score = ee_max * 0.4
            ee_evidence = f"Fair EV/EBITDA: {v:.1f}x"
        else:
            ee_score = 0.0
            ee_evidence = f"Expensive EV/EBITDA: {v:.1f}x (>{ee_fair:.0f}x)"
    scores.append(CriterionScore(name="ev_ebitda", score=ee_score, max_score=ee_max, weight=1.0, evidence=ee_evidence))

    # ── Price/FCF (5 pts) ────────────────────────────────────────────────────
    pf_max  = float(c.get("price_to_fcf", {}).get("max_points", 5.0))
    pf_exc  = float(c.get("price_to_fcf", {}).get("thresholds", {}).get("excellent", 12))
    pf_good = float(c.get("price_to_fcf", {}).get("thresholds", {}).get("good",      20))
    pf_fair = float(c.get("price_to_fcf", {}).get("thresholds", {}).get("fair",      30))

    # Use price_to_fcf if available, fall back to ev_fcf
    pf_val = price_to_fcf if price_to_fcf is not None else ev_fcf
    pf_score, pf_evidence = 0.0, "Unknown"
    if pf_val is not None:
        v = float(pf_val)
        if v <= pf_exc:
            pf_score = pf_max
            pf_evidence = f"Attractive P/FCF: {v:.1f}x"
        elif v <= pf_good:
            pf_score = pf_max * 0.75
            pf_evidence = f"Good P/FCF: {v:.1f}x"
        elif v <= pf_fair:
            pf_score = pf_max * 0.35
            pf_evidence = f"Fair P/FCF: {v:.1f}x"
        else:
            pf_score = 0.0
            pf_evidence = f"Expensive P/FCF: {v:.1f}x"
    scores.append(CriterionScore(name="price_to_fcf", score=pf_score, max_score=pf_max, weight=1.0, evidence=pf_evidence))

    # ── PEG ratio (5 pts) ────────────────────────────────────────────────────
    pg_max  = float(c.get("peg_ratio", {}).get("max_points", 5.0))
    pg_exc  = float(c.get("peg_ratio", {}).get("thresholds", {}).get("excellent", 0.8))
    pg_good = float(c.get("peg_ratio", {}).get("thresholds", {}).get("good",      1.3))
    pg_fair = float(c.get("peg_ratio", {}).get("thresholds", {}).get("fair",      2.0))

    pg_score, pg_evidence = 0.0, "PEG data unavailable"
    if peg_ratio is not None:
        v = float(peg_ratio)
        if v <= pg_exc:
            pg_score = pg_max
            pg_evidence = f"Excellent PEG: {v:.2f} (growth at a discount)"
        elif v <= pg_good:
            pg_score = pg_max * 0.7
            pg_evidence = f"Good PEG: {v:.2f}"
        elif v <= pg_fair:
            pg_score = pg_max * 0.3
            pg_evidence = f"Fair PEG: {v:.2f}"
        else:
            pg_score = 0.0
            pg_evidence = f"Expensive PEG: {v:.2f} (>{pg_fair})"
    scores.append(CriterionScore(name="peg_ratio", score=pg_score, max_score=pg_max, weight=1.0, evidence=pg_evidence))

    return scores
