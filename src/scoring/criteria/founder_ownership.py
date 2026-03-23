"""
Scoring criterion: Founder / Ownership alignment (max 20 points).
  founder_led:          8 pts — founder or family CEO with meaningful stake
  insider_ownership:    6 pts — insider ownership % tiered
  recent_insider_buying:4 pts — buying activity in last 3 years
  insider_conviction:   2 pts — cluster buy near 52-wk low (bonus signal)
"""
from __future__ import annotations

import datetime as dt
from src.shared.types import CriterionScore


def score_founder_ownership(
    is_founder_led: bool | None,
    insider_ownership_pct: float | None,
    cfg: dict | None = None,
    cluster_purchases: list | None = None,
    current_price: float | None = None,
    week52_low: float | None = None,
) -> list[CriterionScore]:
    c = cfg or {}
    scores = []

    # ── Founder-led (8 pts) ──────────────────────────────────────────────────
    fl_max = float(c.get("founder_led", {}).get("max_points", 8.0))
    fl_score, fl_evidence = 0.0, "Unknown"
    if is_founder_led is True:
        fl_score = fl_max
        fl_evidence = "Founder-led / family-controlled"
    elif is_founder_led is False:
        fl_score = fl_max * 0.25
        fl_evidence = "Professional management (not founder-led)"
    scores.append(CriterionScore(name="founder_led", score=fl_score, max_score=fl_max, weight=1.0, evidence=fl_evidence))

    # ── Insider ownership % (6 pts) ─────────────────────────────────────────
    io_cfg  = c.get("insider_ownership", {})
    io_max  = float(io_cfg.get("max_points", 6.0))
    io_exc  = io_cfg.get("thresholds", {}).get("excellent", 0.20)
    io_good = io_cfg.get("thresholds", {}).get("good", 0.10)
    io_weak = io_cfg.get("thresholds", {}).get("weak", 0.01)

    io_score, io_evidence = 0.0, "Unknown"
    if insider_ownership_pct is not None:
        p = float(insider_ownership_pct)
        if p >= io_exc:
            io_score = io_max
            io_evidence = f"Strong insider ownership: {p:.1%}"
        elif p >= io_good:
            io_score = io_max * 0.67
            io_evidence = f"Meaningful insider ownership: {p:.1%}"
        elif p >= io_weak:
            io_score = io_max * 0.33
            io_evidence = f"Some insider ownership: {p:.1%}"
        else:
            io_score = 0.0
            io_evidence = f"Minimal insider ownership: {p:.1%}"
    scores.append(CriterionScore(name="insider_ownership", score=io_score, max_score=io_max, weight=1.0, evidence=io_evidence))

    # ── Recent insider buying (4 pts) ────────────────────────────────────────
    ib_cfg  = c.get("recent_insider_buying", {})
    ib_max  = float(ib_cfg.get("max_points", 4.0))
    lookback_years = int(ib_cfg.get("lookback_years", 3))
    cutoff = dt.date.today() - dt.timedelta(days=lookback_years * 365)

    ib_score, ib_evidence = 0.0, "No insider buying in lookback period"
    purchases = cluster_purchases or []
    recent = [p for p in purchases if getattr(p, "transaction_date", None) and p.transaction_date >= cutoff]
    min_tx = float(ib_cfg.get("min_transaction_usd", 50000))
    strong_tx = float(ib_cfg.get("strong_transaction_usd", 1000000))

    meaningful = [p for p in recent if float(getattr(p, "total_value", 0) or 0) >= min_tx]
    if meaningful:
        total_val = sum(float(getattr(p, "total_value", 0) or 0) for p in meaningful)
        strong = any(float(getattr(p, "total_value", 0) or 0) >= strong_tx for p in meaningful)
        if strong:
            ib_score = ib_max
            ib_evidence = f"Strong insider buying: ${total_val/1e3:.0f}K total ({len(meaningful)} transactions)"
        else:
            ib_score = ib_max * 0.6
            ib_evidence = f"Meaningful insider buying: ${total_val/1e3:.0f}K total"
    scores.append(CriterionScore(name="recent_insider_buying", score=ib_score, max_score=ib_max, weight=1.0, evidence=ib_evidence))

    # ── Insider conviction cluster (2 pts bonus) ─────────────────────────────
    ic_cfg = c.get("insider_conviction", {})
    ic_max = float(ic_cfg.get("max_points", 2.0))
    window_days = int(ic_cfg.get("cluster_window_days", 14))
    cutoff_cluster = dt.date.today() - dt.timedelta(days=window_days)

    ic_score, ic_evidence = 0.0, "No recent cluster detected"
    recent_cluster = [p for p in purchases if getattr(p, "transaction_date", None) and p.transaction_date >= cutoff_cluster and getattr(p, "is_open_market", True)]
    distinct = {getattr(p, "insider_name", "") for p in recent_cluster}

    if len(distinct) >= 2:
        # Check 52-wk low proximity
        if current_price and week52_low and week52_low > 0:
            pct_above = (current_price - week52_low) / week52_low
            if pct_above <= 0.20:
                ic_score = ic_max
                ic_evidence = f"Cluster buy near 52-wk low: {len(distinct)} insiders within {window_days}d"
            else:
                ic_score = ic_max * 0.5
                ic_evidence = f"Cluster buy: {len(distinct)} insiders within {window_days}d"
        else:
            ic_score = ic_max * 0.5
            ic_evidence = f"Cluster buy detected: {len(distinct)} insiders within {window_days}d"
    scores.append(CriterionScore(name="insider_conviction", score=ic_score, max_score=ic_max, weight=1.0, evidence=ic_evidence))

    return scores
