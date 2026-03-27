"""
Financial Analyst Agent — AI-powered scoring using Claude's judgment.

Replaces pure Python threshold scoring with a senior analyst agent that:
- Reads 5 years of financial history + pre-computed trend signals
- Actively seeks disconfirming evidence via 4 targeted web searches
- Writes a mandatory bear case before scoring
- Self-critiques scores before output
- Chooses DCF assumptions based on business quality research
- Scores each dimension with reasoning, like a real analyst

The agent scores 6 core dimensions (0-100 each), then the FitScorer
combines them with optional bonus criteria into the final Fit Score.
"""
from __future__ import annotations

import json
import logging
import math
from typing import Any

from src.db.models.company import Company
from src.db.models.metric import Metric
from src.shared.types import CriterionScore

logger = logging.getLogger(__name__)


def _pct(v) -> str:
    if v is None:
        return "N/A"
    return f"{float(v)*100:.1f}%"


def _usd(v) -> str:
    if v is None:
        return "N/A"
    v = float(v)
    if abs(v) >= 1e9:
        return f"${v/1e9:.1f}B"
    if abs(v) >= 1e6:
        return f"${v/1e6:.0f}M"
    return f"${v:,.0f}"


def _compute_trend_signals(historical: list[dict]) -> dict:
    """
    Pre-compute analytical trend signals from 5-year income statement history.
    Returns a dict of signals for display + DCF inputs.
    """
    if not historical or len(historical) < 2:
        return {}

    sorted_hist = sorted(historical, key=lambda x: x.get("date", ""))[-5:]  # oldest first

    rev_series  = []
    ni_series   = []
    gm_series   = []
    ebit_series = []

    for h in sorted_hist:
        rev  = h.get("revenue")
        gp   = h.get("grossProfit")
        ebit = h.get("ebit") or h.get("operatingIncome")
        ni   = h.get("netIncome") or h.get("bottomLineNetIncome")

        if rev and rev > 0:
            rev_series.append(float(rev))
            if gp:
                gm_series.append(float(gp) / float(rev) * 100)
        if ni is not None:
            ni_series.append(float(ni))
        if ebit and ebit > 0:
            ebit_series.append(float(ebit))

    signals: dict[str, Any] = {}

    # ── Gross margin trend ─────────────────────────────────────────────────────
    if len(gm_series) >= 2:
        gm_change = gm_series[-1] - gm_series[0]
        if gm_change > 2:
            gm_trend = f"Expanding  (+{gm_change:.1f}pp: {gm_series[0]:.1f}% → {gm_series[-1]:.1f}%)"
        elif gm_change < -2:
            gm_trend = f"Contracting ({gm_change:.1f}pp: {gm_series[0]:.1f}% → {gm_series[-1]:.1f}%)"
        else:
            gm_trend = f"Stable     ({gm_series[0]:.1f}% → {gm_series[-1]:.1f}%)"
        signals["gm_trend"] = gm_trend

    # ── Revenue growth consistency ─────────────────────────────────────────────
    if len(rev_series) >= 3:
        yoy_growths = [
            (rev_series[i] / rev_series[i-1] - 1) * 100
            for i in range(1, len(rev_series))
        ]
        avg_growth = sum(yoy_growths) / len(yoy_growths)
        if len(yoy_growths) >= 2:
            variance = sum((g - avg_growth) ** 2 for g in yoy_growths) / len(yoy_growths)
            sd_growth = math.sqrt(variance)
            if sd_growth < 4:
                consistency = f"Consistent (σ={sd_growth:.1f}pp, avg {avg_growth:.1f}%)"
            elif sd_growth < 10:
                consistency = f"Moderate   (σ={sd_growth:.1f}pp, avg {avg_growth:.1f}%)"
            else:
                consistency = f"Lumpy/Volatile (σ={sd_growth:.1f}pp, avg {avg_growth:.1f}%)"
            signals["rev_consistency"] = consistency
            signals["avg_rev_growth"] = avg_growth
            signals["last_rev_growth"] = yoy_growths[-1]
            signals["yoy_growths"] = yoy_growths

        # Rev CAGR
        n = len(rev_series) - 1
        cagr_rev = (rev_series[-1] / rev_series[0]) ** (1 / n) - 1
        signals["cagr_rev"] = cagr_rev
        signals["rev_series"] = rev_series

    # ── NI CAGR ────────────────────────────────────────────────────────────────
    if len(ni_series) >= 3:
        ni_pos = [n for n in ni_series if n > 0]
        if len(ni_pos) >= 2:
            n = len(ni_series) - 1
            if ni_series[0] > 0 and ni_series[-1] > 0:
                cagr_ni = (ni_series[-1] / ni_series[0]) ** (1 / n) - 1
                signals["cagr_ni"] = cagr_ni
                signals["ni_series"] = ni_series

    # ── Operating leverage ─────────────────────────────────────────────────────
    if "cagr_rev" in signals and "cagr_ni" in signals:
        cagr_rev = signals["cagr_rev"]
        cagr_ni  = signals["cagr_ni"]
        diff = (cagr_ni - cagr_rev) * 100
        if diff > 2:
            signals["op_leverage"] = f"Present    (NI CAGR {cagr_ni*100:.1f}% > Rev CAGR {cagr_rev*100:.1f}%)"
        elif diff < -2:
            signals["op_leverage"] = f"Absent     (NI CAGR {cagr_ni*100:.1f}% < Rev CAGR {cagr_rev*100:.1f}% — margin compression)"
        else:
            signals["op_leverage"] = f"Neutral    (NI CAGR {cagr_ni*100:.1f}% ≈ Rev CAGR {cagr_rev*100:.1f}%)"

    # ── Down years ─────────────────────────────────────────────────────────────
    rev_down = 0
    ni_down  = 0
    if len(rev_series) >= 2:
        rev_down = sum(1 for i in range(1, len(rev_series)) if rev_series[i] < rev_series[i-1])
    if len(ni_series) >= 2:
        ni_down = sum(1 for i in range(1, len(ni_series)) if ni_series[i] < ni_series[i-1])
    n_years = len(rev_series) - 1 if len(rev_series) >= 2 else 0
    if n_years > 0:
        if rev_down == 0 and ni_down == 0:
            signals["down_years"] = f"0 of {n_years} — no down years (strong consistency)"
        else:
            signals["down_years"] = f"Rev: {rev_down} of {n_years}, NI: {ni_down} of {n_years}"
    signals["ni_down_count"] = ni_down
    signals["rev_down_count"] = rev_down

    # ── Growth trajectory ──────────────────────────────────────────────────────
    if "avg_rev_growth" in signals and "last_rev_growth" in signals:
        avg = signals["avg_rev_growth"]
        last = signals["last_rev_growth"]
        diff = last - avg
        if diff > 3:
            signals["trajectory"] = f"Accelerating (last yr {last:.1f}% vs avg {avg:.1f}%)"
        elif diff < -3:
            signals["trajectory"] = f"Decelerating (last yr {last:.1f}% vs avg {avg:.1f}%)"
        else:
            signals["trajectory"] = f"Stable       (last yr {last:.1f}% vs avg {avg:.1f}%)"

    # ── EBIT CAGR (for DCF) ────────────────────────────────────────────────────
    if len(ebit_series) >= 2:
        signals["ebit_series"] = ebit_series
        n3 = min(3, len(ebit_series) - 1)
        n5 = len(ebit_series) - 1
        if n3 >= 1 and ebit_series[-n3-1] > 0 and ebit_series[-1] > 0:
            signals["cagr_ebit_3yr"] = (ebit_series[-1] / ebit_series[-n3-1]) ** (1/n3) - 1
        if n5 >= 1 and ebit_series[0] > 0 and ebit_series[-1] > 0:
            signals["cagr_ebit_5yr"] = (ebit_series[-1] / ebit_series[0]) ** (1/n5) - 1
        signals["current_ebit"] = ebit_series[-1]

    return signals


def _compute_dcf_inputs(
    signals: dict,
    metrics: Metric,
    current_price: float | None,
    market_tier: int = 1,
) -> dict:
    """Build DCF inputs dict from pre-computed signals + current metrics."""
    ebit = signals.get("current_ebit") or (float(metrics.ebit) if metrics.ebit else None)
    nopat = ebit * 0.78 if ebit and ebit > 0 else None  # EBIT × (1 − 22% tax)

    shares = float(metrics.shares_outstanding) if metrics.shares_outstanding and float(metrics.shares_outstanding) > 0 else None
    market_cap = float(metrics.market_cap_usd) if metrics.market_cap_usd and float(metrics.market_cap_usd) > 0 else None
    base_wacc = 0.09 if market_tier == 1 else 0.11

    return {
        "nopat": nopat,
        "shares": shares,
        "price": current_price,
        "market_cap": market_cap,
        "cagr_ebit_3yr": signals.get("cagr_ebit_3yr"),
        "cagr_ebit_5yr": signals.get("cagr_ebit_5yr"),
        "base_wacc": base_wacc,
        "market_tier": market_tier,
    }


def _run_dcf(assumptions: dict, dcf_inputs: dict) -> dict | None:
    """
    Run 2-stage NOPAT DCF with agent-chosen assumptions.
    Hard caps prevent hallucinated inputs from breaking the model.
    Outputs intrinsic equity value vs current market cap (no per-share needed).
    Returns {intrinsic_equity, market_cap, discount_pct, label, ...} or None.
    """
    try:
        nopat      = dcf_inputs.get("nopat")
        market_cap = dcf_inputs.get("market_cap")
        shares     = dcf_inputs.get("shares")
        price      = dcf_inputs.get("price")

        if not nopat or nopat <= 0:
            return None

        g1 = min(0.35, max(-0.05, float(assumptions.get("stage1_growth_pct", 8)) / 100))
        g2 = min(0.05, max(0.01,  float(assumptions.get("stage2_terminal_pct", 3)) / 100))
        w  = min(0.18, max(0.07,  float(assumptions.get("wacc_pct", 9)) / 100))

        if w <= g2:
            w = g2 + 0.04  # prevent division by zero

        # Stage 1: 5-year NOPAT projection, discounted
        pv1 = sum(nopat * (1 + g1)**t / (1 + w)**t for t in range(1, 6))

        # Stage 2: terminal value at year 5
        nopat5 = nopat * (1 + g1)**5
        tv     = nopat5 * (1 + g2) / (w - g2)
        pv2    = tv / (1 + w)**5

        intrinsic_equity = pv1 + pv2

        # Prefer per-share output; fall back to total equity value vs market cap
        if shares and shares > 0:
            intrinsic_per_share = intrinsic_equity / shares
            compare_price = price
            if compare_price and compare_price > 0:
                discount_pct = (intrinsic_per_share - compare_price) / intrinsic_per_share * 100
            elif market_cap and market_cap > 0:
                compare_price = market_cap / shares
                discount_pct = (intrinsic_per_share - compare_price) / intrinsic_per_share * 100
            else:
                discount_pct = None
        elif market_cap and market_cap > 0:
            intrinsic_per_share = None
            discount_pct = (intrinsic_equity - market_cap) / intrinsic_equity * 100
        else:
            return None  # nothing to compare against

        if discount_pct is not None:
            if discount_pct > 20:
                label = f"trading {discount_pct:.1f}% BELOW intrinsic value — margin of safety"
            elif discount_pct < -20:
                label = f"trading {abs(discount_pct):.1f}% ABOVE intrinsic value — priced for perfection"
            else:
                label = f"trading near intrinsic value ({discount_pct:+.1f}%)"
        else:
            label = "current price unavailable"

        return {
            "intrinsic_per_share": intrinsic_per_share,
            "intrinsic_equity": intrinsic_equity,
            "current_price": price,
            "market_cap": market_cap,
            "discount_pct": discount_pct,
            "label": label,
            "g1": g1, "g2": g2, "w": w,
        }
    except Exception as e:
        logger.debug("DCF computation failed: %s", e)
        return None


def _build_financial_history(
    metrics: Metric,
    historical: list[dict] | None,
    current_price: float | None = None,
    market_tier: int = 1,
) -> tuple[str, dict, dict]:
    """
    Build structured multi-year financial history string for the agent.
    Returns (history_string, trend_signals, dcf_inputs).
    """
    lines = []

    # ── Current year snapshot ──────────────────────────────────────────────────
    lines.append("── CURRENT YEAR ──")
    lines.append(f"Revenue:      {_usd(metrics.revenue)}")
    lines.append(f"Gross Margin: {_pct(metrics.gross_margin)}")
    lines.append(f"EBIT Margin:  {_pct(metrics.ebit_margin)}")
    lines.append(f"Net Income:   {_usd(metrics.net_income)}")
    lines.append(f"ROIC:         {_pct(metrics.roic)}")
    lines.append(f"FCF:          {_usd(metrics.fcf)}")
    lines.append(f"FCF Yield:    {_pct(metrics.fcf_yield)}")
    lines.append(f"Capex/Rev:    {_pct(metrics.capex_to_revenue)}")
    lines.append(f"Net Debt/EBITDA: {f'{float(metrics.net_debt_ebitda):.1f}x' if metrics.net_debt_ebitda else 'N/A'}")
    lines.append(f"EV/EBIT:      {f'{float(metrics.ev_ebit):.1f}x' if metrics.ev_ebit else 'N/A'}")
    lines.append(f"Rev Growth YoY: {_pct(metrics.revenue_growth_yoy)}")

    # ── Multi-year history table ───────────────────────────────────────────────
    signals: dict = {}
    dcf_inputs: dict = {}

    if historical and len(historical) > 1:
        lines.append("\n── HISTORICAL TREND ──")
        lines.append(f"{'Year':<8} {'Revenue':>10} {'Gross Mgn':>10} {'EBIT Mgn':>10} {'Net Income':>11}")
        lines.append("-" * 55)

        for h in sorted(historical, key=lambda x: x.get("date", ""), reverse=True)[:5]:
            date = h.get("date", "")[:4]
            rev  = h.get("revenue")
            gp   = h.get("grossProfit")
            ebit = h.get("ebit") or h.get("operatingIncome")
            ni   = h.get("netIncome") or h.get("bottomLineNetIncome")
            gm   = (float(gp)/float(rev)*100) if gp and rev else None
            em   = (float(ebit)/float(rev)*100) if ebit and rev else None

            rev_str = f"${float(rev)/1e6:.0f}M" if rev else "N/A"
            ni_str  = f"${float(ni)/1e6:.0f}M"  if ni  else "N/A"
            gm_str  = f"{gm:.1f}%" if gm else "N/A"
            em_str  = f"{em:.1f}%" if em else "N/A"
            lines.append(f"{date:<8} {rev_str:>10} {gm_str:>10} {em_str:>10} {ni_str:>11}")

        # ── Pre-compute trend signals ──────────────────────────────────────────
        signals = _compute_trend_signals(historical)

        if signals:
            lines.append("\n── TREND SIGNALS ──")
            if "gm_trend" in signals:
                lines.append(f"Gross Margin Trend:    {signals['gm_trend']}")
            if "rev_consistency" in signals:
                lines.append(f"Revenue Growth:        {signals['rev_consistency']}")
            if "op_leverage" in signals:
                lines.append(f"Operating Leverage:    {signals['op_leverage']}")
            if "down_years" in signals:
                lines.append(f"Down Years (Rev/NI):   {signals['down_years']}")
            if "trajectory" in signals:
                lines.append(f"Growth Trajectory:     {signals['trajectory']}")
            if "cagr_rev" in signals:
                n = len(signals.get("rev_series", [])) - 1
                lines.append(f"Revenue {n}yr CAGR:     {signals['cagr_rev']*100:.1f}%")
            if "cagr_ni" in signals:
                n = len(signals.get("ni_series", [])) - 1
                lines.append(f"Net Income {n}yr CAGR:  {signals['cagr_ni']*100:.1f}%")

        # ── DCF inputs block ───────────────────────────────────────────────────
        dcf_inputs = _compute_dcf_inputs(signals, metrics, current_price, market_tier)
        nopat = dcf_inputs.get("nopat")
        shares = dcf_inputs.get("shares")

        if nopat and nopat > 0:
            lines.append("\n── DCF INPUTS (use these to set your dcf_assumptions below) ──")
            lines.append(f"NOPAT (current):     {_usd(nopat)}   [EBIT × (1−22% tax)]")
            if "cagr_ebit_3yr" in dcf_inputs and dcf_inputs["cagr_ebit_3yr"] is not None:
                lines.append(f"EBIT CAGR (3yr):     {dcf_inputs['cagr_ebit_3yr']*100:.1f}%")
            if "cagr_ebit_5yr" in dcf_inputs and dcf_inputs["cagr_ebit_5yr"] is not None:
                lines.append(f"EBIT CAGR (5yr):     {dcf_inputs['cagr_ebit_5yr']*100:.1f}%")
            if "gm_trend" in signals:
                margin_dir = "Expanding" if "Expanding" in signals["gm_trend"] else ("Contracting" if "Contracting" in signals["gm_trend"] else "Stable")
                lines.append(f"EBIT Margin Trend:   {margin_dir}")
            lines.append(f"Base WACC:           {dcf_inputs['base_wacc']*100:.1f}%   (Tier-{'1' if market_tier==1 else '2'} market; adjust ±1–3% for company risk)")
            if shares:
                lines.append(f"Shares Outstanding:  {shares/1e6:.1f}M")
            if current_price:
                lines.append(f"Current Price:       ${current_price:.2f}")

    return "\n".join(lines), signals, dcf_inputs


def _build_portfolio_context(portfolio_avg: dict | None) -> str:
    """Build a concise portfolio context string for the agent."""
    if not portfolio_avg or not portfolio_avg.get("holding_count"):
        return "No portfolio context available."

    lines = [f"Phoenician Capital currently holds {portfolio_avg.get('holding_count', 0)} positions:"]
    if portfolio_avg.get("avg_gross_margin"):
        lines.append(f"  Portfolio avg gross margin: {portfolio_avg['avg_gross_margin']*100:.1f}%")
    if portfolio_avg.get("avg_roic"):
        lines.append(f"  Portfolio avg ROIC:         {portfolio_avg['avg_roic']*100:.1f}%")
    if portfolio_avg.get("avg_revenue_growth"):
        lines.append(f"  Portfolio avg revenue growth: {portfolio_avg['avg_revenue_growth']*100:.1f}%")
    if portfolio_avg.get("avg_fcf_yield"):
        lines.append(f"  Portfolio avg FCF yield:    {portfolio_avg['avg_fcf_yield']*100:.1f}%")
    if portfolio_avg.get("avg_net_debt_ebitda"):
        lines.append(f"  Portfolio avg ND/EBITDA:    {portfolio_avg['avg_net_debt_ebitda']:.1f}x")

    holdings = portfolio_avg.get("holdings", [])
    if holdings:
        lines.append(f"  Holdings: {', '.join(h.get('ticker','') for h in holdings[:19])}")

    return "\n".join(lines)


def _build_sector_context(sector_medians: dict | None) -> str:
    """Build sector median context for relative scoring."""
    if not sector_medians:
        return "No sector median data available — score on absolute basis."
    lines = ["Sector peer medians (from Phoenician's screened universe):"]
    if sector_medians.get("median_gross_margin"):
        lines.append(f"  Median gross margin: {sector_medians['median_gross_margin']*100:.1f}%")
    if sector_medians.get("median_roic"):
        lines.append(f"  Median ROIC:         {sector_medians['median_roic']*100:.1f}%")
    if sector_medians.get("median_ev_ebit"):
        lines.append(f"  Median EV/EBIT:      {sector_medians['median_ev_ebit']:.1f}x")
    return "\n".join(lines)


def _build_valuation_context(metrics: Metric) -> str:
    """Build valuation multiples string including P/E."""
    lines = []
    if metrics.ev_ebit:
        v = float(metrics.ev_ebit)
        if 0 < v < 200:
            lines.append(f"EV/EBIT:      {v:.1f}x")
    if metrics.ev_fcf:
        v = float(metrics.ev_fcf)
        if 0 < v < 300:
            lines.append(f"EV/FCF:       {v:.1f}x")
    if metrics.pe_ratio:
        v = float(metrics.pe_ratio)
        if 0 < v < 500:
            lines.append(f"P/E Ratio:    {v:.1f}x")
    if metrics.fcf_yield:
        fy = float(metrics.fcf_yield)
        if 0 < fy < 0.50:
            lines.append(f"FCF Yield:    {fy*100:.1f}%")
    if metrics.net_debt_ebitda:
        lines.append(f"ND/EBITDA:    {float(metrics.net_debt_ebitda):.1f}x")
    if metrics.market_cap_usd:
        lines.append(f"Market Cap:   {_usd(float(metrics.market_cap_usd))}")
    return "\n".join(lines) if lines else "Valuation data unavailable"


def _load_analyst_prompts(
    company: Company,
    metrics: Metric,
    financial_history_str: str,
    portfolio_avg: dict | None = None,
    sector_medians: dict | None = None,
    feedback_context: str | None = None,
) -> tuple[str, str]:
    """Load system and scoring prompts from Jinja2 templates."""
    from src.prompts.loader import load_prompt
    system = load_prompt(
        "scoring/analyst_system.j2",
        feedback_context=feedback_context or "No analyst decisions recorded yet.",
    )
    user = load_prompt(
        "scoring/analyst_score.j2",
        name=company.name,
        ticker=company.ticker,
        country=company.country or "Unknown",
        sector=company.gics_sector or "Unknown",
        market_cap=_usd(float(metrics.market_cap_usd) if metrics.market_cap_usd else None),
        description=(company.description or "")[:600],
        financial_history=financial_history_str,
        valuation_context=_build_valuation_context(metrics),
        portfolio_context=_build_portfolio_context(portfolio_avg),
        sector_context=_build_sector_context(sector_medians),
    )
    return system, user


async def score_with_analyst_agent(
    company: Company,
    metrics: Metric,
    historical: list[dict] | None = None,
    portfolio_avg: dict | None = None,
    sector_medians: dict | None = None,
    feedback_context: str | None = None,
    current_price: float | None = None,
    market_tier: int = 1,
) -> list[CriterionScore]:
    """
    Use Claude as a financial analyst agent to score the company.
    Returns list of CriterionScore compatible with the existing scoring pipeline.
    Falls back to empty list (Python scoring takes over) if agent fails.
    """
    try:
        from src.shared.llm.client_factory import complete_with_search
        from src.config.settings import settings

        fin_history_str, trend_signals, dcf_inputs = _build_financial_history(
            metrics, historical, current_price=current_price, market_tier=market_tier
        )
        system, prompt = _load_analyst_prompts(
            company, metrics, fin_history_str, portfolio_avg, sector_medians, feedback_context
        )

        response = await complete_with_search(
            prompt=prompt,
            system=system,
            model=settings.llm.primary_model,
            max_searches=4,  # 4 targeted searches: moat, trajectory, bear case, valuation
            temperature=0.1,
        )

        # Parse JSON — handle extra text before/after JSON block
        text = response.strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            if start == -1:
                raise ValueError("No JSON found in agent response")
            depth = 0
            end   = -1
            for i, ch in enumerate(text[start:], start):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
            if end == -1:
                raise ValueError("Unmatched braces in agent response")
            data = json.loads(text[start:end+1])

        # ── Extract dimension scores ───────────────────────────────────────────
        criteria = []

        dimension_map = {
            "business_quality": ("Business Quality",  30.0),
            "unit_economics":   ("Unit Economics",    25.0),
            "capital_returns":  ("Capital Returns",   20.0),
            "growth_quality":   ("Growth Quality",    15.0),
            "balance_sheet":    ("Balance Sheet",      5.0),
            "phoenician_fit":   ("Phoenician Fit",     5.0),
        }
        for key, (name, weight) in dimension_map.items():
            if key not in data:
                continue
            raw = float(data[key]["score"])
            ev  = data[key].get("evidence", "")
            pts = (raw / 100.0) * weight
            criteria.append(CriterionScore(
                name=key, score=pts, max_score=weight,
                weight=1.0, evidence=f"[Agent {raw:.0f}/100] {ev}"
            ))

        # ── Overall fit score ──────────────────────────────────────────────────
        overall_fit = float(data.get("overall_fit_score", 0))
        criteria.append(CriterionScore(
            name="overall_fit",
            score=overall_fit,
            max_score=100.0,
            weight=1.0,
            evidence=f"LLM overall fit score: {overall_fit:.0f}/100",
        ))

        # ── Risk score ─────────────────────────────────────────────────────────
        risk_score = float(data.get("risk_score", 10))
        risk_ev    = data.get("risk_evidence", "")
        criteria.append(CriterionScore(
            name="llm_risk_score",
            score=risk_score,
            max_score=100.0,
            weight=1.0,
            evidence=f"[Risk {risk_score:.0f}/100] {risk_ev}",
        ))

        # ── Bear case ──────────────────────────────────────────────────────────
        bear_case = data.get("bear_case", [])
        bear_text = " | ".join(bear_case) if isinstance(bear_case, list) else str(bear_case)

        # ── DCF — run math with agent-chosen assumptions ───────────────────────
        dcf_result_text = ""
        dcf_assumptions = data.get("dcf_assumptions")
        if dcf_assumptions and dcf_inputs.get("nopat"):
            dcf_result = _run_dcf(dcf_assumptions, dcf_inputs)
            if dcf_result:
                lbl = dcf_result["label"]
                g1  = dcf_result["g1"] * 100
                g2  = dcf_result["g2"] * 100
                w   = dcf_result["w"]  * 100
                iv  = dcf_result.get("intrinsic_per_share")
                ie  = dcf_result.get("intrinsic_equity")
                if iv is not None:
                    iv_str = f"intrinsic ${iv:.2f}/share"
                elif ie is not None:
                    iv_str = f"intrinsic equity ${ie/1e9:.2f}B"
                else:
                    iv_str = "intrinsic value computed"
                dcf_result_text = (
                    f" | DCF: {iv_str} "
                    f"(Stage1 {g1:.1f}%, terminal {g2:.1f}%, WACC {w:.1f}%) — {lbl}"
                )
                if dcf_assumptions.get("reasoning"):
                    dcf_result_text += f" | DCF reasoning: {dcf_assumptions['reasoning']}"

        # ── Thesis, diligence, verdict ─────────────────────────────────────────
        verdict   = data.get("analyst_verdict", "")
        note      = data.get("analyst_note", "")
        thesis    = data.get("investment_thesis", "")
        questions = data.get("diligence_questions", [])

        logger.info(
            "Analyst agent for %s: fit=%d risk=%d verdict=%s | %s",
            company.ticker, overall_fit, risk_score, verdict, note[:100]
        )

        q_text = " | ".join(questions[:3]) if questions else ""
        criteria.append(CriterionScore(
            name="analyst_thesis",
            score=0.0, max_score=0.0, weight=0.0,
            evidence=(
                f"THESIS: {thesis}"
                f" | BEAR CASE: {bear_text}"
                f"{dcf_result_text}"
                f" | DILIGENCE: {q_text}"
                f" | VERDICT: {verdict}"
            ),
        ))

        return criteria

    except Exception as e:
        logger.warning(
            "Analyst agent failed for %s: %s — falling back to Python scoring",
            company.ticker, e
        )
        return []
