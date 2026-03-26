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


def _load_analyst_prompts(
    company: Company,
    metrics: Metric,
    financial_history_str: str,
) -> tuple[str, str]:
    """Load system and scoring prompts from Jinja2 templates."""
    from src.prompts.loader import load_prompt
    system = load_prompt("scoring/analyst_system.j2")
    user   = load_prompt(
        "scoring/analyst_score.j2",
        name=company.name,
        ticker=company.ticker,
        country=company.country or "Unknown",
        sector=company.gics_sector or "Unknown",
        market_cap=_usd(float(metrics.market_cap_usd) if metrics.market_cap_usd else None),
        description=(company.description or "")[:400],
        financial_history=financial_history_str,
    )
    return system, user


async def score_with_analyst_agent(
    company: Company,
    metrics: Metric,
    historical: list[dict] | None = None,
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
        system, prompt = _load_analyst_prompts(company, metrics, fin_history)

        response = await complete_with_search(
            prompt=prompt,
            system=system,
            model=settings.llm.primary_model,
            max_searches=0,  # no search — we provide all data
            temperature=0.1,
        )

        # Parse JSON
        text = response.strip()
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("No JSON in response")
        data = json.loads(text[start:end+1])

        # Convert to CriterionScore list
        criteria = []
        dimension_map = {
            "business_quality":  ("Business Quality",  30.0),
            "unit_economics":    ("Unit Economics",     25.0),
            "capital_returns":   ("Capital Returns",    20.0),
            "growth_quality":    ("Growth Quality",     15.0),
            "balance_sheet":     ("Balance Sheet",       5.0),
            "phoenician_fit":    ("Phoenician Fit",      5.0),
        }

        total_weight = 100.0
        for key, (name, weight) in dimension_map.items():
            if key not in data:
                continue
            raw_score  = float(data[key]["score"])
            evidence   = data[key].get("evidence", "")
            # Scale: agent returns 0-100, we scale to weight-proportional pts
            # e.g. business_quality weight=30 → max_pts=30, score=(raw/100)*30
            max_pts    = weight
            pts        = (raw_score / 100.0) * max_pts
            criteria.append(CriterionScore(
                name=key, score=pts, max_score=max_pts,
                weight=1.0, evidence=f"[Agent {raw_score}/100] {evidence}"
            ))

        # Log verdict
        verdict = data.get("analyst_verdict", "")
        note    = data.get("analyst_note", "")
        logger.info("Analyst agent for %s: verdict=%s note=%s",
                    company.ticker, verdict, note[:80])

        return criteria

    except Exception as e:
        logger.warning("Analyst agent failed for %s: %s — falling back to Python scoring",
                       company.ticker, e)
        return []
