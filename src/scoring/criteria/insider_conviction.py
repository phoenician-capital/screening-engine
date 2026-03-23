"""
Scoring criterion: Insider Conviction Score (max 8 points).
Detects cluster insider buying near 52-week lows.
Points freed from: market_cap_band (3) + tam_narrative (5) = 8 pts.
"""
from __future__ import annotations

from src.shared.types import CriterionScore

ROLE_WEIGHTS: dict[str, float] = {
    "ceo": 3.0, "chief executive": 3.0, "president": 2.5,
    "cfo": 2.0, "chief financial": 2.0,
    "coo": 1.8, "chief operating": 1.8,
    "director": 1.0, "chairman": 1.5,
    "svp": 0.9, "evp": 0.9, "vp": 0.8,
    "officer": 0.7,
}


def _role_weight(title: str | None) -> float:
    if not title:
        return 0.5
    t = title.lower()
    for key, w in ROLE_WEIGHTS.items():
        if key in t:
            return w
    return 0.5


def score_insider_conviction(
    cluster_purchases: list,
    current_price: float | None = None,
    week52_low: float | None = None,
    cfg: dict | None = None,
) -> list[CriterionScore]:
    """
    Cluster score (0–4 pts):
      Sum role weights for all open-market purchases in the window.
      Capped at 4. Requires at least 2 distinct insiders.

    Proximity score (0–4 pts):
      Within 10% of 52-wk low → 4 pts
      Within 20%               → 2 pts
      Otherwise                → 0 pts
    """
    c = cfg or {}
    max_pts = float(c.get("max_points", 8.0))
    cluster_max = max_pts / 2
    prox_max = max_pts / 2

    # ── Cluster score ──────────────────────────────────────────────────
    cluster_score = 0.0
    cluster_evidence = "No insider cluster detected"

    open_market = [p for p in (cluster_purchases or []) if getattr(p, "is_open_market", True)]
    distinct_insiders = {getattr(p, "insider_name", "") for p in open_market}

    if len(distinct_insiders) >= 2:
        raw_weight = sum(_role_weight(getattr(p, "insider_title", None)) for p in open_market)
        cluster_score = min(cluster_max, raw_weight / 2)
        total_val = sum(float(getattr(p, "total_value", 0) or 0) for p in open_market)
        cluster_evidence = (
            f"{len(distinct_insiders)} insiders buying within window "
            f"(total ${total_val/1e3:.0f}K)"
        )
    elif len(distinct_insiders) == 1:
        cluster_evidence = "Single insider buying — not a cluster"

    # ── Proximity to 52-week low ────────────────────────────────────────
    prox_score = 0.0
    prox_evidence = "52-week low data unavailable"

    if current_price and week52_low and week52_low > 0:
        pct_above_low = (current_price - week52_low) / week52_low
        if pct_above_low <= 0.10:
            prox_score = prox_max
            prox_evidence = f"Within 10% of 52-wk low (now ${current_price:.2f}, low ${week52_low:.2f})"
        elif pct_above_low <= 0.20:
            prox_score = prox_max / 2
            prox_evidence = f"Within 20% of 52-wk low (now ${current_price:.2f}, low ${week52_low:.2f})"
        else:
            prox_evidence = f"{pct_above_low:.0%} above 52-wk low"

    return [
        CriterionScore(
            name="insider_cluster",
            score=cluster_score,
            max_score=cluster_max,
            weight=1.0,
            evidence=cluster_evidence,
        ),
        CriterionScore(
            name="insider_near_52wk_low",
            score=prox_score,
            max_score=prox_max,
            weight=1.0,
            evidence=prox_evidence,
        ),
    ]
