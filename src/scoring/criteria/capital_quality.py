"""
Advanced quality signals — capital allocation, balance sheet strength,
quality trifecta bonus, momentum, and earnings quality checks.

These are purely additive bonus signals — missing data = 0 pts, never a penalty.
"""
from __future__ import annotations

from src.shared.types import CriterionScore


def score_capital_allocation(
    stock_repurchased: float | None = None,
    stock_based_comp: float | None = None,
    acquisitions_net: float | None = None,
    revenue: float | None = None,
    market_cap: float | None = None,
) -> list[CriterionScore]:
    """
    Capital allocation quality (max 6 pts — bonus).
    Checks: buybacks, low dilution, disciplined M&A.
    """
    scores = []
    ca_score = 0.0
    ca_evidence_parts = []

    # Buybacks — management believes stock is undervalued
    if stock_repurchased is not None and market_cap and market_cap > 0:
        buyback_yield = abs(float(stock_repurchased)) / float(market_cap)
        if buyback_yield >= 0.03:  # ≥ 3% buyback yield
            ca_score += 2.0
            ca_evidence_parts.append(f"Active buybacks: {buyback_yield:.1%} yield")
        elif buyback_yield >= 0.01:
            ca_score += 1.0
            ca_evidence_parts.append(f"Some buybacks: {buyback_yield:.1%} yield")

    # Stock-based compensation — low SBC = less dilution
    if stock_based_comp is not None and revenue and revenue > 0:
        sbc_ratio = abs(float(stock_based_comp)) / float(revenue)
        if sbc_ratio <= 0.02:
            ca_score += 2.0
            ca_evidence_parts.append(f"Low SBC: {sbc_ratio:.1%} of revenue")
        elif sbc_ratio <= 0.05:
            ca_score += 1.0
            ca_evidence_parts.append(f"Moderate SBC: {sbc_ratio:.1%} of revenue")

    # M&A discipline — low acquisition spending
    if acquisitions_net is not None and revenue and revenue > 0:
        acq_ratio = abs(float(acquisitions_net)) / float(revenue)
        if acq_ratio <= 0.03:
            ca_score += 2.0
            ca_evidence_parts.append("Disciplined M&A: minimal acquisition spend")
        elif acq_ratio <= 0.10:
            ca_score += 1.0
            ca_evidence_parts.append(f"Moderate M&A: {acq_ratio:.1%} of revenue")

    evidence = "; ".join(ca_evidence_parts) if ca_evidence_parts else "Capital allocation data unavailable"
    scores.append(CriterionScore(
        name="capital_allocation", score=ca_score, max_score=6.0,
        weight=1.0, evidence=evidence
    ))
    return scores


def score_balance_sheet(
    net_debt: float | None = None,
    current_ratio: float | None = None,
    goodwill: float | None = None,
    total_assets: float | None = None,
    cash: float | None = None,
    market_cap: float | None = None,
) -> list[CriterionScore]:
    """
    Balance sheet quality (max 5 pts — bonus).
    Rewards fortress balance sheets, penalises goodwill-heavy.
    """
    scores = []
    bs_score = 0.0
    bs_evidence_parts = []

    # Net cash position — fortress balance sheet
    if net_debt is not None:
        nd = float(net_debt)
        if nd < -0.05 * (market_cap or 1):  # net cash > 5% of market cap
            bs_score += 2.0
            bs_evidence_parts.append(f"Net cash position: fortress balance sheet")
        elif nd < 0:
            bs_score += 1.0
            bs_evidence_parts.append("Net cash: no net debt")

    # Current ratio — liquidity
    if current_ratio is not None:
        cr = float(current_ratio)
        if cr >= 2.0:
            bs_score += 2.0
            bs_evidence_parts.append(f"Strong liquidity: current ratio {cr:.1f}x")
        elif cr >= 1.5:
            bs_score += 1.0
            bs_evidence_parts.append(f"Adequate liquidity: current ratio {cr:.1f}x")

    # Goodwill risk — acquisition-heavy balance sheets can hide impairments
    if goodwill is not None and total_assets and total_assets > 0:
        gw_ratio = float(goodwill) / float(total_assets)
        if gw_ratio > 0.50:
            bs_score -= 1.0  # Only deduction in this module
            bs_evidence_parts.append(f"High goodwill: {gw_ratio:.0%} of assets — acquisition risk")
        elif gw_ratio <= 0.15:
            bs_score += 1.0
            bs_evidence_parts.append(f"Low goodwill: {gw_ratio:.0%} of assets — organic growth")

    bs_score = max(0.0, bs_score)  # floor at 0
    evidence = "; ".join(bs_evidence_parts) if bs_evidence_parts else "Balance sheet data unavailable"
    scores.append(CriterionScore(
        name="balance_sheet_quality", score=bs_score, max_score=5.0,
        weight=1.0, evidence=evidence
    ))
    return scores


def score_quality_trifecta(
    gross_margin: float | None,
    roic: float | None,
    fcf_yield: float | None,
) -> list[CriterionScore]:
    """
    Quality trifecta bonus (max 5 pts).
    Awards extra points when ALL three quality metrics are above threshold simultaneously.
    A company with great margins, great returns AND strong FCF generation is a compounder.
    """
    scores = []

    if gross_margin is None or roic is None or fcf_yield is None:
        scores.append(CriterionScore(
            name="quality_trifecta", score=0.0, max_score=5.0,
            weight=1.0, evidence="Quality trifecta data unavailable"
        ))
        return scores

    gm = float(gross_margin)
    rc = float(roic)
    fy = float(fcf_yield)

    # Elite trifecta: GM > 50%, ROIC > 15%, FCF yield > 5%
    if gm >= 0.50 and rc >= 0.15 and fy >= 0.05:
        score = 5.0
        evidence = f"Elite quality trifecta: GM {gm:.0%} + ROIC {rc:.0%} + FCF yield {fy:.0%}"
    # Strong trifecta: GM > 35%, ROIC > 10%, FCF yield > 3%
    elif gm >= 0.35 and rc >= 0.10 and fy >= 0.03:
        score = 3.0
        evidence = f"Strong quality trifecta: GM {gm:.0%} + ROIC {rc:.0%} + FCF yield {fy:.0%}"
    # Partial trifecta: 2 of 3 metrics above threshold
    elif sum([gm >= 0.35, rc >= 0.10, fy >= 0.03]) >= 2:
        score = 1.5
        evidence = "Partial quality alignment: 2 of 3 metrics above threshold"
    else:
        score = 0.0
        evidence = f"Quality metrics below trifecta threshold: GM {gm:.0%}, ROIC {rc:.0%}, FCF yield {fy:.0%}"

    scores.append(CriterionScore(
        name="quality_trifecta", score=score, max_score=5.0,
        weight=1.0, evidence=evidence
    ))
    return scores


def score_earnings_integrity(
    revenue: float | None = None,
    revenue_prior: float | None = None,
    accounts_receivable: float | None = None,
    accounts_receivable_prior: float | None = None,
    net_income: float | None = None,
    fcf: float | None = None,
) -> list[CriterionScore]:
    """
    Earnings integrity check (max 3 pts — can be negative as risk signal).
    Detects potential revenue recognition issues via AR vs revenue growth check.
    """
    scores = []

    if (revenue is None or revenue_prior is None or
            accounts_receivable is None or accounts_receivable_prior is None):
        scores.append(CriterionScore(
            name="earnings_integrity", score=0.0, max_score=3.0,
            weight=1.0, evidence="Earnings integrity data unavailable"
        ))
        return scores

    rev = float(revenue)
    rev_p = float(revenue_prior)
    ar = float(accounts_receivable)
    ar_p = float(accounts_receivable_prior)

    if rev_p <= 0 or ar_p <= 0:
        scores.append(CriterionScore(
            name="earnings_integrity", score=0.0, max_score=3.0,
            weight=1.0, evidence="Earnings integrity: base year data insufficient"
        ))
        return scores

    rev_growth = (rev - rev_p) / rev_p
    ar_growth  = (ar - ar_p) / ar_p

    # Channel stuffing / aggressive recognition: AR growing much faster than revenue
    ar_vs_rev = ar_growth - rev_growth

    if ar_vs_rev > 0.25:
        # AR growing >25% faster than revenue — significant red flag
        score = 0.0
        evidence = f"Earnings quality concern: AR growing {ar_vs_rev:.0%} faster than revenue"
    elif ar_vs_rev > 0.10:
        score = 1.0
        evidence = f"Mild AR growth vs revenue: monitor receivables trajectory"
    elif ar_vs_rev <= 0.05:
        # AR in line with or lagging revenue — clean earnings
        score = 3.0
        evidence = f"Clean earnings: AR growth in line with revenue growth"
    else:
        score = 2.0
        evidence = "Earnings quality: AR growth slightly ahead of revenue"

    scores.append(CriterionScore(
        name="earnings_integrity", score=score, max_score=3.0,
        weight=1.0, evidence=evidence
    ))
    return scores
