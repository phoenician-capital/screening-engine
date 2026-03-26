"""
Financial Analyst Agent — AI-powered scoring using Claude's judgment.

Replaces pure Python threshold scoring with a senior analyst agent that:
- Reads 5 years of financial history
- Assesses quality, consistency, and trend — not just point-in-time numbers
- Scores each dimension with reasoning, like a real analyst
- Returns structured scores + evidence for each criterion

The agent scores 6 core dimensions (0-100 each), then the FitScorer
combines them with optional bonus criteria into the final Fit Score.
"""
from __future__ import annotations

import json
import logging
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


def _build_financial_history(metrics: Metric, historical: list[dict] | None) -> str:
    """Build a structured multi-year financial history string for the agent."""
    lines = []

    # Current year snapshot
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

    # Multi-year history if available
    if historical and len(historical) > 1:
        lines.append("\n── HISTORICAL TREND ──")
        lines.append(f"{'Year':<8} {'Revenue':>10} {'Gross Mgn':>10} {'EBIT Mgn':>10} {'Net Income':>11} {'Rev Growth':>11}")
        lines.append("-" * 65)

        rev_series = []
        ni_series = []

        for h in sorted(historical, key=lambda x: x.get("date", ""), reverse=True)[:5]:
            date = h.get("date", "")[:4]
            rev  = h.get("revenue")
            gp   = h.get("grossProfit")
            ebit = h.get("ebit") or h.get("operatingIncome")
            ni   = h.get("netIncome") or h.get("bottomLineNetIncome")
            gm   = (gp/rev*100) if gp and rev else None
            em   = (ebit/rev*100) if ebit and rev else None

            if rev:
                rev_series.append(rev)
            if ni:
                ni_series.append(ni)

            rev_str  = f"${rev/1e6:.0f}M" if rev else "N/A"
            ni_str   = f"${ni/1e6:.0f}M" if ni else "N/A"
            gm_str   = f"{gm:.1f}%" if gm else "N/A"
            em_str   = f"{em:.1f}%" if em else "N/A"
            lines.append(f"{date:<8} {rev_str:>10} {gm_str:>10} {em_str:>10} {ni_str:>11}")

        # Compute CAGRs
        if len(rev_series) >= 3:
            rev_sorted = list(reversed(rev_series))
            cagr_rev = (rev_sorted[-1] / rev_sorted[0]) ** (1/(len(rev_sorted)-1)) - 1
            lines.append(f"\nRevenue {len(rev_sorted)-1}yr CAGR: {cagr_rev*100:.1f}%")

        if len(ni_series) >= 3:
            ni_sorted = list(reversed(ni_series))
            if ni_sorted[0] and ni_sorted[0] > 0 and ni_sorted[-1] > 0:
                cagr_ni = (ni_sorted[-1] / ni_sorted[0]) ** (1/(len(ni_sorted)-1)) - 1
                lines.append(f"Net Income {len(ni_sorted)-1}yr CAGR: {cagr_ni*100:.1f}%")

    return "\n".join(lines)


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

    # Holdings list
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
    user   = load_prompt(
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
) -> list[CriterionScore]:
    """
    Use Claude as a financial analyst agent to score the company.
    Returns list of CriterionScore compatible with the existing scoring pipeline.
    Falls back to empty list (Python scoring takes over) if agent fails.
    """
    try:
        from src.shared.llm.client_factory import complete_with_search
        from src.config.settings import settings

        fin_history = _build_financial_history(metrics, historical)
        system, prompt = _load_analyst_prompts(
            company, metrics, fin_history, portfolio_avg, sector_medians, feedback_context
        )

        response = await complete_with_search(
            prompt=prompt,
            system=system,
            model=settings.llm.primary_model,
            max_searches=2,  # 2 searches: business model + recent developments
            temperature=0.1,
        )

        # Parse JSON — handle extra text before/after JSON block
        text = response.strip()
        # Try direct parse first
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Extract JSON block between first { and matching }
            start = text.find("{")
            if start == -1:
                raise ValueError("No JSON found in agent response")
            # Find the matching closing brace by counting depth
            depth = 0
            end = -1
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

        # ── Extract LLM scores — agent has full freedom ──────────────────────
        criteria = []

        # Per-dimension scores for UI breakdown display
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
            raw   = float(data[key]["score"])
            ev    = data[key].get("evidence", "")
            pts   = (raw / 100.0) * weight
            criteria.append(CriterionScore(
                name=key, score=pts, max_score=weight,
                weight=1.0, evidence=f"[Agent {raw:.0f}/100] {ev}"
            ))

        # ── Overall fit score — LLM's holistic judgment (0-100) ──────────────
        # This is the primary score used for ranking — NOT a weighted average
        overall_fit = float(data.get("overall_fit_score", 0))
        criteria.append(CriterionScore(
            name="overall_fit",
            score=overall_fit,
            max_score=100.0,
            weight=1.0,
            evidence=f"LLM overall fit score: {overall_fit:.0f}/100",
        ))

        # ── Risk score — LLM assesses risk directly (0-100) ──────────────────
        risk_score = float(data.get("risk_score", 10))
        risk_ev    = data.get("risk_evidence", "")
        criteria.append(CriterionScore(
            name="llm_risk_score",
            score=risk_score,
            max_score=100.0,
            weight=1.0,
            evidence=f"[Risk {risk_score:.0f}/100] {risk_ev}",
        ))

        # ── Thesis, diligence, verdict — display only ─────────────────────────
        verdict   = data.get("analyst_verdict", "")
        note      = data.get("analyst_note", "")
        thesis    = data.get("investment_thesis", "")
        questions = data.get("diligence_questions", [])
        logger.info("Analyst agent for %s: fit=%d risk=%d verdict=%s | %s",
                    company.ticker, overall_fit, risk_score, verdict, note[:100])

        q_text = " | ".join(questions[:3]) if questions else ""
        criteria.append(CriterionScore(
            name="analyst_thesis",
            score=0.0, max_score=0.0, weight=0.0,
            evidence=f"THESIS: {thesis} | DILIGENCE: {q_text} | VERDICT: {verdict}",
        ))

        return criteria

    except Exception as e:
        logger.warning("Analyst agent failed for %s: %s — falling back to Python scoring",
                       company.ticker, e)
        return []
