"""
Scoring criterion: Valuation Asymmetry (max 15 points).

Smart scoring: sector-relative when available, absolute thresholds as fallback.
- ev_ebitda:     6 pts — relative to sector median when available
- price_to_fcf:  6 pts — absolute tiered
- peg_ratio:     3 pts — growth-adjusted valuation
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

    # ── EV/EBITDA — sector-relative scoring ─────────────────────────────────
    ee_max  = float(c.get("ev_ebitda", {}).get("max_points", 6.0))
    ee_exc  = float(c.get("ev_ebitda", {}).get("thresholds", {}).get("excellent", 10))
    ee_good = float(c.get("ev_ebitda", {}).get("thresholds", {}).get("good",      15))
    ee_fair = float(c.get("ev_ebitda", {}).get("thresholds", {}).get("fair",      22))

    ee_val = ev_ebitda if ev_ebitda is not None else ev_ebit
    ee_score, ee_evidence = 0.0, "Unknown"

    if ee_val is not None:
        v = float(ee_val)
        # Sanity check — negative or extreme EV/EBITDA is a data error
        if v <= 0 or v > 200:
            ee_evidence = f"EV/EBITDA data unreliable: {v:.1f}x"
        elif sector_median_ev_ebit is not None and sector_median_ev_ebit > 0:
            # Sector-relative scoring: compare to sector median
            sector_med = float(sector_median_ev_ebit)
            discount = (sector_med - v) / sector_med  # positive = trading at discount
            if discount >= 0.30:
                ee_score = ee_max
                ee_evidence = f"Deep discount to sector: {v:.1f}x vs sector median {sector_med:.1f}x ({discount:.0%} cheaper)"
            elif discount >= 0.15:
                ee_score = ee_max * 0.75
                ee_evidence = f"Discount to sector: {v:.1f}x vs median {sector_med:.1f}x"
            elif discount >= 0.0:
                ee_score = ee_max * 0.45
                ee_evidence = f"In line with sector: {v:.1f}x vs median {sector_med:.1f}x"
            elif discount >= -0.20:
                ee_score = ee_max * 0.2
                ee_evidence = f"Slight premium to sector: {v:.1f}x vs median {sector_med:.1f}x"
            else:
                ee_score = 0.0
                ee_evidence = f"Significant premium to sector: {v:.1f}x vs median {sector_med:.1f}x"
        else:
            # Absolute thresholds fallback
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

    # ── Price/FCF ────────────────────────────────────────────────────────────
    pf_max  = float(c.get("price_to_fcf", {}).get("max_points", 6.0))
    pf_exc  = float(c.get("price_to_fcf", {}).get("thresholds", {}).get("excellent", 15))
    pf_good = float(c.get("price_to_fcf", {}).get("thresholds", {}).get("good",      25))
    pf_fair = float(c.get("price_to_fcf", {}).get("thresholds", {}).get("fair",      35))

    pf_val = price_to_fcf if price_to_fcf is not None else ev_fcf
    pf_score, pf_evidence = 0.0, "Unknown"
    if pf_val is not None:
        v = float(pf_val)
        if v <= 0 or v > 300:
            pf_evidence = f"P/FCF data unreliable: {v:.1f}x"
        elif sector_median_ev_fcf is not None and sector_median_ev_fcf > 0:
            med = float(sector_median_ev_fcf)
            discount = (med - v) / med
            if discount >= 0.25:
                pf_score = pf_max
                pf_evidence = f"Deep discount P/FCF: {v:.1f}x vs sector {med:.1f}x"
            elif discount >= 0.10:
                pf_score = pf_max * 0.75
                pf_evidence = f"Good P/FCF vs sector: {v:.1f}x vs {med:.1f}x"
            elif discount >= -0.10:
                pf_score = pf_max * 0.4
                pf_evidence = f"Fair P/FCF: {v:.1f}x vs sector {med:.1f}x"
            else:
                pf_score = 0.0
                pf_evidence = f"Premium P/FCF: {v:.1f}x vs sector {med:.1f}x"
        else:
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

    # ── PEG ratio ────────────────────────────────────────────────────────────
    pg_max  = float(c.get("peg_ratio", {}).get("max_points", 3.0))
    pg_exc  = float(c.get("peg_ratio", {}).get("thresholds", {}).get("excellent", 0.8))
    pg_good = float(c.get("peg_ratio", {}).get("thresholds", {}).get("good",      1.5))
    pg_fair = float(c.get("peg_ratio", {}).get("thresholds", {}).get("fair",      2.5))

    pg_score, pg_evidence = 0.0, "PEG data unavailable"
    if peg_ratio is not None:
        v = float(peg_ratio)
        if v <= 0:
            pg_evidence = "PEG data unreliable (negative)"
        elif v <= pg_exc:
            pg_score = pg_max
            pg_evidence = f"Excellent PEG: {v:.2f} — growth at a discount"
        elif v <= pg_good:
            pg_score = pg_max * 0.7
            pg_evidence = f"Good PEG: {v:.2f}"
        elif v <= pg_fair:
            pg_score = pg_max * 0.3
            pg_evidence = f"Fair PEG: {v:.2f}"
        else:
            pg_score = 0.0
            pg_evidence = f"Expensive PEG: {v:.2f}"
    scores.append(CriterionScore(name="peg_ratio", score=pg_score, max_score=pg_max, weight=1.0, evidence=pg_evidence))

    return scores
