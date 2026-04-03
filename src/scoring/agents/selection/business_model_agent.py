"""Business Model Agent — Clarity verification for selection."""

from __future__ import annotations

import logging

from src.scoring.agents.base_agent import AgentDecision, BaseAgent
from src.shared.llm.client_factory import complete as _llm_complete

logger = logging.getLogger(__name__)


class BusinessModelAgent(BaseAgent):
    """
    Stage 1 Selection Agent: Business model clarity.
    Flags: Conglomerates with unclear core business, complex structures.
    """

    def __init__(self):
        super().__init__("BusinessModelAgent")

    async def evaluate(
        self,
        ticker: str,
        company_name: str,
        description: str | None = None,
        segments: list[dict] | None = None,
    ) -> AgentDecision:
        """Evaluate mandate compliance and business model clarity via LLM."""

        result = await self._assess_with_llm(
            ticker=ticker,
            company_name=company_name,
            description=description or "",
            segment_count=len(segments) if segments else 0,
        )

        return AgentDecision(
            passed=result["passed"],
            score=None,
            reason=result["reason"],
            metadata={"segment_count": len(segments) if segments else None},
        )

    async def _assess_with_llm(
        self,
        ticker: str,
        company_name: str,
        description: str,
        segment_count: int,
    ) -> dict:
        """Single LLM call: mandate gate + business model clarity."""

        prompt = f"""You are a pre-screening agent for Phoenician Capital, a fund that invests ONLY in high-quality small and mid-cap compounders — founder-led or owner-operated businesses with durable competitive advantages, high returns on capital, and reinvestment-driven growth.

COMPANY: {ticker} — {company_name}
DESCRIPTION: {description or "No description available."}
REPORTED SEGMENTS: {segment_count if segment_count else "unknown"}

═══════════════════════════════════════════════════════
STEP 1 — MANDATE EXCLUSION CHECK (instant reject if yes)
═══════════════════════════════════════════════════════
Reject IMMEDIATELY if the company is in ANY of these categories — no exceptions:

FINANCIAL INTERMEDIARIES: Banks, savings institutions, credit unions, thrifts, mortgage lenders, insurance companies (life, P&C, specialty), reinsurance, BDCs, finance companies, consumer lending, payment networks acting as principals (e.g. card issuers)
NOTE: Fintech SOFTWARE companies (SaaS payments infrastructure, core banking software, compliance tech) are NOT excluded — only intermediaries that take balance-sheet risk.

REAL ASSETS / COMMODITIES: REITs, real estate developers/operators, oil & gas E&P, oil services, pipelines, coal, metals mining, gold/silver miners, fertilisers, chemicals commodities, timber

REGULATED MONOPOLIES: Electric utilities, gas utilities, water utilities, telecom carriers (not software), railroad infrastructure

CAPITAL-INTENSIVE CYCLICALS: Airlines, cruise lines, shipping/maritime, auto manufacturers (not software/EV-tech), steel, cement, paper/pulp

LOW-VALUE SERVICES: Staffing & BPO, temp agencies, facility management, cleaning services, food/restaurant chains, hotel/hospitality operators

DIVERSIFIED CONGLOMERATES: Companies with 4+ unrelated business segments with no identifiable core compounder business

═══════════════════════════════════════════════════════
STEP 2 — BUSINESS MODEL CLARITY (only if Step 1 passed)
═══════════════════════════════════════════════════════
If not excluded, assess whether the business model is clear enough for investment analysis:
- Is there an identifiable, focused primary business?
- Does it have characteristics of a compounder (recurring revenue, pricing power, scalability)?
- Is the description sufficient to understand how they make money?

If description is missing or too vague to make any determination, PASS the company — the analyst agent will investigate further.

═══════════════════════════════════════════════════════
RESPOND IN THIS EXACT JSON FORMAT:
{{
  "passed": true or false,
  "reason": "one clear sentence explaining the decision"
}}

Examples:
{{"passed": false, "reason": "Regional bank — financial intermediary, excluded by mandate"}}
{{"passed": false, "reason": "Electric utility — regulated monopoly, excluded by mandate"}}
{{"passed": false, "reason": "Diversified conglomerate with 6 unrelated segments, no identifiable core business"}}
{{"passed": true, "reason": "B2B SaaS company with recurring revenue and clear software-focused business model"}}
{{"passed": true, "reason": "Insufficient description to assess — passing to analyst for investigation"}}
"""
        try:
            import json
            response = await _llm_complete(
                prompt,
                model="claude-haiku-4-5",
                temperature=0,
                max_tokens=150,
            )
            if isinstance(response, str):
                text = response.strip()
                if "```" in text:
                    for part in text.split("```"):
                        part = part.strip().lstrip("json").strip()
                        if part.startswith("{"):
                            text = part
                            break
                start, end = text.find("{"), text.rfind("}")
                if start != -1 and end != -1:
                    data = json.loads(text[start:end+1])
                    return {
                        "passed": bool(data.get("passed", True)),
                        "reason": str(data.get("reason", "LLM assessment complete")),
                    }
            return {"passed": True, "reason": "LLM response unparseable — passing to analyst"}
        except Exception as e:
            logger.warning(f"BusinessModelAgent LLM call failed for {ticker}: {e}")
            return {"passed": True, "reason": f"LLM error — passing to analyst: {e}"}
