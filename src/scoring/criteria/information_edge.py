"""
Scoring criterion: Information Edge / Underfollowed (max 10 points).
  analyst_coverage:      6 pts — fewer analysts = better edge
  market_cap_sweet_spot: 4 pts — $300M–$3B sweet spot
"""
from __future__ import annotations

from src.shared.types import CriterionScore


def score_information_edge(
    analyst_count: int | None,
    market_cap: float | None,
    cfg: dict | None = None,
) -> list[CriterionScore]:
    c = cfg or {}
    scores = []

    # ── Analyst coverage (6 pts) — fewer is better ──────────────────────────
    ac_max  = float(c.get("analyst_coverage", {}).get("max_points", 6.0))
    ac_exc  = int(c.get("analyst_coverage", {}).get("thresholds", {}).get("excellent", 2))
    ac_good = int(c.get("analyst_coverage", {}).get("thresholds", {}).get("good",      5))
    ac_weak = int(c.get("analyst_coverage", {}).get("thresholds", {}).get("weak",      10))

    cov_score, cov_evidence = 0.0, "Coverage unknown"
    if analyst_count is not None:
        if analyst_count <= ac_exc:
            cov_score = ac_max
            cov_evidence = f"Very underfollowed: {analyst_count} analyst(s)"
        elif analyst_count <= ac_good:
            cov_score = ac_max * 0.67
            cov_evidence = f"Underfollowed: {analyst_count} analysts"
        elif analyst_count <= ac_weak:
            cov_score = ac_max * 0.25
            cov_evidence = f"Moderate coverage: {analyst_count} analysts"
        else:
            cov_score = 0.0
            cov_evidence = f"Well-covered: {analyst_count} analysts"
    scores.append(CriterionScore(name="analyst_coverage", score=cov_score, max_score=ac_max, weight=1.0, evidence=cov_evidence))

    # ── Market cap sweet spot (4 pts) ────────────────────────────────────────
    mc_max = float(c.get("market_cap_sweet_spot", {}).get("max_points", 4.0))
    mc_min = float(c.get("market_cap_sweet_spot", {}).get("min_usd", 300_000_000))
    mc_max_usd = float(c.get("market_cap_sweet_spot", {}).get("max_usd", 3_000_000_000))

    cap_score, cap_evidence = 0.0, "Market cap data unavailable"
    if market_cap is not None:
        mc = float(market_cap)
        if mc_min <= mc <= mc_max_usd:
            cap_score = mc_max
            cap_evidence = f"In sweet spot: ${mc/1e6:.0f}M (${mc_min/1e6:.0f}M–${mc_max_usd/1e9:.0f}B)"
        elif mc < mc_min:
            cap_score = mc_max * 0.25
            cap_evidence = f"Below sweet spot: ${mc/1e6:.0f}M"
        else:
            cap_score = mc_max * 0.25
            cap_evidence = f"Above sweet spot: ${mc/1e9:.1f}B"
    scores.append(CriterionScore(name="market_cap_sweet_spot", score=cap_score, max_score=mc_max, weight=1.0, evidence=cap_evidence))

    return scores
