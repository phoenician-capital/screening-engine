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
        """Evaluate business model clarity."""

        # Red flags for conglomerate/complex structures
        red_flags = []

        if company_name:
            # Check for holding company, conglomerate, diversified keywords
            name_lower = company_name.lower()
            conglomerate_keywords = [
                "holding", "diversified", "conglomerate", "portfolio",
                "investment company", "syndicate", "consortium",
            ]
            for kw in conglomerate_keywords:
                if kw in name_lower:
                    red_flags.append(f"Conglomerate signal: '{kw}' in name")

        # Check segment diversity (if >4 major segments, high complexity)
        if segments and len(segments) > 4:
            red_flags.append(f"High business complexity: {len(segments)} segments")

        # If we have description, use LLM to assess clarity
        clarity_issues = []
        if description:
            clarity_issues = await self._assess_clarity_with_llm(description)

        all_issues = red_flags + clarity_issues
        passed = len(all_issues) == 0

        reason = " | ".join(all_issues) if all_issues else "Clear, focused business model"

        return AgentDecision(
            passed=passed,
            score=None,
            reason=reason,
            metadata={
                "segment_count": len(segments) if segments else None,
                "clarity_issues": clarity_issues,
                "conglomerate_flags": red_flags,
            },
        )

    async def _assess_clarity_with_llm(self, description: str) -> list[str]:
        """Use LLM to assess business clarity from description."""
        prompt = f"""
Analyze this company description for business model clarity issues:

"{description}"

Is the core business clear and focused? Flag any:
1. Unclear primary revenue source
2. Mention of "various", "diverse", or undefined segments
3. Complex or hard-to-understand business model
4. Too many unrelated business lines

Return a JSON list of issues found, or empty list if clear.
Example: ["Unclear which segment is primary", "Too many unrelated businesses"]
Be strict — conglomerates should fail.
"""
        try:
            import json
            response = await _llm_complete(
                prompt,
                model="claude-haiku-4-5",
                temperature=0,
                max_tokens=256,
            )
            if isinstance(response, str):
                # Strip markdown fences if present
                text = response.strip()
                if "```" in text:
                    for part in text.split("```"):
                        part = part.strip().lstrip("json").strip()
                        if part.startswith("["):
                            text = part
                            break
                start, end = text.find("["), text.rfind("]")
                if start != -1 and end != -1:
                    issues = json.loads(text[start:end+1])
                    return issues if isinstance(issues, list) else []
            return []
        except Exception as e:
            logger.warning(f"Failed to assess clarity for description: {e}")
            return []
