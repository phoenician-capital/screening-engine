"""
Generates a full investment memo using Claude — reads like a senior analyst wrote it.
Covers business model, financial quality, portfolio fit, risks, and next steps.
"""
from __future__ import annotations

import asyncio
import logging

from src.db.models.company import Company
from src.db.models.metric import Metric
from src.shared.types import CriterionScore

logger = logging.getLogger(__name__)


def _pct(v: float | None, decimals: int = 1) -> str:
    if v is None:
        return "N/A"
    return f"{v * 100:.{decimals}f}%"


def _usd(v: float | None) -> str:
    if v is None:
        return "N/A"
    if abs(v) >= 1e9:
        return f"${v/1e9:.1f}B"
    if abs(v) >= 1e6:
        return f"${v/1e6:.0f}M"
    return f"${v:,.0f}"


def _mult(v: float | None) -> str:
    if v is None:
        return "N/A"
    return f"{v:.1f}x"


async def generate_memo(
    company: Company,
    metrics: Metric,
    fit_score: float,
    risk_score: float,
    fit_criteria: list[CriterionScore],
    risk_criteria: list[CriterionScore],
    portfolio_avg: dict,
) -> tuple[str, dict]:
    """
    Generates a full LLM-powered investment memo.
    Falls back to a structured template memo if LLM is unavailable.
    Returns (memo_text, portfolio_comparison_dict).
    """
    try:
        memo = await _generate_llm_memo(
            company, metrics, fit_score, risk_score,
            fit_criteria, risk_criteria, portfolio_avg
        )
    except Exception as e:
        logger.warning("LLM memo failed for %s: %s — using template", company.ticker, e)
        memo = _template_memo(company, metrics, fit_score, risk_score,
                              fit_criteria, risk_criteria, portfolio_avg)

    comparison = _build_comparison(metrics, portfolio_avg, company)
    return memo, comparison


async def _generate_llm_memo(
    company: Company,
    metrics: Metric,
    fit_score: float,
    risk_score: float,
    fit_criteria: list[CriterionScore],
    risk_criteria: list[CriterionScore],
    portfolio_avg: dict,
) -> str:
    from src.shared.llm.client_factory import complete_with_search
    from src.config.settings import settings

    # Build financial snapshot
    fin = _financial_snapshot(metrics)
    strengths = _top_criteria(fit_criteria, top=5, min_pct=0.5)
    risks     = _top_criteria(risk_criteria, top=3, min_pct=0.1)
    port_cmp  = _portfolio_comparison_text(metrics, portfolio_avg, company)

    prompt = f"""You are a senior analyst at Phoenician Capital — a global public-equity fund with a private-equity mindset that focuses on founder-led, capital-light compounders with durable competitive advantages.

Write a structured investment memo for the following company. Be specific, direct, and analytical. Reference actual numbers. No filler phrases.

═══ COMPANY ═══
Name:        {company.name}
Ticker:      {company.ticker}
Country:     {company.country}
Sector:      {company.gics_sector or "Unknown"}
Market Cap:  {_usd(float(metrics.market_cap_usd) if metrics.market_cap_usd else None)}
Website:     {company.website or "N/A"}
Description: {(company.description or "")[:500] or "Not available"}

═══ FINANCIAL SNAPSHOT ═══
{fin}

═══ SCORING ═══
Fit Score:  {fit_score:.0f}/100
Risk Score: {risk_score:.0f}/100
Top Strengths: {", ".join(strengths) if strengths else "None above threshold"}
Risk Flags:    {", ".join(risks) if risks else "None detected"}

═══ vs. PHOENICIAN PORTFOLIO ═══
{port_cmp}

═══ REQUIRED OUTPUT FORMAT ═══
Write the memo in exactly this structure. Each section must be substantive — minimum 2-3 sentences per section. Do NOT use placeholder text.

## Business Model
[Explain what the company does, how it makes money, who its customers are, and what makes its model defensible. Be specific about the revenue model (subscription, transactional, recurring, project-based). Mention key products/services by name if known.]

## Investment Thesis
[2-3 sentences: why this company is compelling RIGHT NOW. Reference specific financial metrics. What is the key insight that makes this interesting?]

## Why It Fits Phoenician DNA
[Map explicitly to Phoenician criteria: founder-led or owner-operator culture, unit economics quality (gross margin, ROIC, FCF), underfollowed/information edge, margin of safety, scalability. Score each dimension specifically — don't be generic.]

## Financial Quality Assessment
[Analyze the numbers: gross margin trend, ROIC vs cost of capital, FCF conversion, revenue growth quality, balance sheet strength. Highlight what's impressive and what concerns you. Compare to sector norms.]

## Portfolio Fit
[{port_cmp}]
[Explain whether this adds diversification or concentration. How does it compare to similar holdings? Does it complement or overlap with existing positions?]

## Key Risks
[3-5 specific risks with explanations. Not generic market risk — company-specific risks. Reference actual metrics where relevant (e.g., if leverage is a concern, cite the actual ND/EBITDA ratio).]

## Valuation
[Assess whether the current valuation is attractive, fair, or expensive based on available multiples (EV/EBIT, P/FCF, EV/EBITDA). Compare to sector. What is the implied upside/downside scenario?]

## Diligence Checklist
[5-7 specific questions an analyst should answer before investing. These should be company-specific, not generic.]

## Recommended Action
[One of: RESEARCH NOW / WATCH / PASS — with a 1-sentence rationale]"""

    try:
        response = await complete_with_search(
            prompt=prompt,
            model=settings.llm.memo_model or settings.llm.primary_model,
            max_searches=2,
            system="You are a senior investment analyst. Write substantive, specific memos. Always reference actual numbers. Never use placeholder text or generic phrases.",
        )
        return response.strip()
    except Exception as e:
        logger.warning("LLM memo generation failed for %s: %s", company.ticker, e)
        return _template_memo(company, metrics, fit_score, risk_score,
                              fit_criteria, risk_criteria, portfolio_avg)


def _financial_snapshot(m: Metric) -> str:
    lines = []
    if m.revenue:
        lines.append(f"Revenue:      {_usd(float(m.revenue))}")
    if m.gross_margin is not None:
        lines.append(f"Gross Margin: {_pct(float(m.gross_margin))}")
    if m.ebit_margin is not None:
        lines.append(f"EBIT Margin:  {_pct(float(m.ebit_margin))}")
    if m.roic is not None:
        lines.append(f"ROIC:         {_pct(float(m.roic))}")
    if m.roe is not None:
        lines.append(f"ROE:          {_pct(float(m.roe))}")
    if m.revenue_growth_yoy is not None:
        lines.append(f"Rev Growth:   {_pct(float(m.revenue_growth_yoy))}")
    if m.fcf is not None:
        lines.append(f"FCF:          {_usd(float(m.fcf))}")
    if m.fcf_yield is not None:
        lines.append(f"FCF Yield:    {_pct(float(m.fcf_yield))}")
    if m.net_debt_ebitda is not None:
        lines.append(f"ND/EBITDA:    {_mult(float(m.net_debt_ebitda))}")
    if m.ev_ebit is not None:
        lines.append(f"EV/EBIT:      {_mult(float(m.ev_ebit))}")
    if m.capex_to_revenue is not None:
        lines.append(f"CapEx/Rev:    {_pct(float(m.capex_to_revenue))}")
    if m.analyst_count is not None:
        lines.append(f"Analyst Coverage: {m.analyst_count} analysts")
    if m.insider_ownership_pct is not None:
        lines.append(f"Insider Ownership: {_pct(float(m.insider_ownership_pct))}")
    return "\n".join(lines) if lines else "Financial data not available"


def _top_criteria(criteria: list[CriterionScore], top: int, min_pct: float) -> list[str]:
    eligible = [c for c in criteria if c.max_score > 0 and (c.score / c.max_score) >= min_pct]
    eligible.sort(key=lambda c: c.score / c.max_score, reverse=True)
    return [c.name.replace("_", " ").title() for c in eligible[:top]]


def _portfolio_comparison_text(metrics: Metric, portfolio_avg: dict, company: Company) -> str:
    if not portfolio_avg or portfolio_avg.get("holding_count", 0) == 0:
        return "No portfolio holdings on record. Add positions in Settings to enable comparison."

    lines = [f"Portfolio has {portfolio_avg.get('holding_count', 0)} holdings."]

    def _cmp(val, avg_key, label, fmt="pct", higher_better=True):
        v = float(val) if val else None
        a = portfolio_avg.get(avg_key)
        if v is None or a is None:
            return None
        diff = v - a
        better = (diff > 0) == higher_better
        arrow = "↑" if diff > 0 else "↓"
        val_str = _pct(v) if fmt == "pct" else _mult(v)
        avg_str = _pct(a) if fmt == "pct" else _mult(a)
        quality = "stronger" if better else "weaker"
        return f"{label}: {val_str} vs portfolio avg {avg_str} ({arrow} {quality})"

    comps = [
        _cmp(metrics.gross_margin, "avg_gross_margin", "Gross Margin", "pct", True),
        _cmp(metrics.roic, "avg_roic", "ROIC", "pct", True),
        _cmp(metrics.revenue_growth_yoy, "avg_revenue_growth", "Revenue Growth", "pct", True),
        _cmp(metrics.fcf_yield, "avg_fcf_yield", "FCF Yield", "pct", True),
        _cmp(metrics.ev_ebit, "avg_ev_ebit", "EV/EBIT", "mult", False),
    ]
    lines.extend(c for c in comps if c)

    sectors = portfolio_avg.get("sectors", [])
    if sectors and company.gics_sector:
        if company.gics_sector in sectors:
            lines.append(f"Sector overlap: {company.gics_sector} already in portfolio — adds concentration.")
        else:
            lines.append(f"Sector diversification: {company.gics_sector} not currently in portfolio — adds diversification.")

    return "\n".join(lines)


def _build_comparison(metrics: Metric, portfolio_avg: dict, company: Company) -> dict:
    comparison: dict = {}
    if not portfolio_avg:
        return comparison

    def _d(val, key):
        v = float(val) if val else None
        a = portfolio_avg.get(key)
        if v is not None and a is not None:
            return round(v - a, 4)
        return None

    gm_d = _d(metrics.gross_margin, "avg_gross_margin")
    if gm_d is not None:
        comparison["gross_margin_delta"] = gm_d
        comparison["gross_margin_vs_portfolio"] = f"{'above' if gm_d > 0 else 'below'} portfolio avg by {_pct(abs(gm_d))}"

    roic_d = _d(metrics.roic, "avg_roic")
    if roic_d is not None:
        comparison["roic_delta"] = roic_d

    revg_d = _d(metrics.revenue_growth_yoy, "avg_revenue_growth")
    if revg_d is not None:
        comparison["revenue_growth_delta"] = revg_d

    sectors = portfolio_avg.get("sectors", [])
    if sectors and company.gics_sector:
        comparison["sector_overlap"] = company.gics_sector in sectors

    return comparison


def _template_memo(
    company: Company,
    metrics: Metric,
    fit_score: float,
    risk_score: float,
    fit_criteria: list[CriterionScore],
    risk_criteria: list[CriterionScore],
    portfolio_avg: dict,
) -> str:
    """Structured fallback memo when LLM is unavailable."""
    strengths = _top_criteria(fit_criteria, top=3, min_pct=0.6)
    risks     = _top_criteria(risk_criteria, top=2, min_pct=0.1)
    fin       = _financial_snapshot(metrics)
    port      = _portfolio_comparison_text(metrics, portfolio_avg, company)

    return f"""## Business Model
{company.description[:400] if company.description else f"{company.name} — business description not available."}

## Investment Thesis
{company.name} ({company.ticker}) scores {fit_score:.0f}/100 on Phoenician's fit criteria with a risk score of {risk_score:.0f}/100.{f" Key strengths: {', '.join(strengths)}." if strengths else ""}

## Financial Quality Assessment
{fin}

## Portfolio Fit
{port}

## Key Risks
{f"Flagged: {', '.join(risks)}." if risks else "No material risk flags from available data."}

## Recommended Action
{"RESEARCH NOW" if fit_score >= 40 and risk_score <= 20 else "WATCH" if fit_score >= 30 else "PASS"} — Fit Score {fit_score:.0f}/100, Risk Score {risk_score:.0f}/100.
"""
