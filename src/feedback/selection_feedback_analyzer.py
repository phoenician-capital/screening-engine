"""
Selection Feedback Analyzer — Extracts learnings when analyst rejects a selected company.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.feedback import Feedback
from src.db.models.recommendation import Recommendation
from src.db.models.company import Company
from src.db.models.metric import Metric
from src.db.models.learned_patterns import SelectionLearnedPattern
from src.shared.llm.client_factory import get_llm_client

logger = logging.getLogger(__name__)


class SelectionFeedbackAnalyzer:
    """
    When analyst rejects a company that was selected (passed selection filters),
    analyze: did selection team miss something?
    Extract learnings for selection filters.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.llm = get_llm_client()

    async def analyze(
        self,
        feedback: Feedback,
        company: Company,
        metrics: Metric,
        selection_detail: dict | None = None,
    ) -> list[dict]:
        """
        Compare: "Why did selection pass this, but analyst rejected it?"

        Returns: List of learnings/adjustments for selection team.
        """

        learnings = []

        # Only process rejections (not "watch" or "research_now")
        if feedback.action != "reject":
            return learnings

        if not feedback.notes:
            return learnings

        # Parse analyst's concerns from notes using LLM
        concerns = await self._extract_concerns(feedback.notes)
        if not concerns:
            return learnings

        logger.info(f"Selection learning for {feedback.ticker}: {len(concerns)} concerns")

        # For each concern, check if selection team should have caught it
        for concern in concerns:

            # Concern: "Unsustainable buybacks"
            if "buyback" in concern.lower() or "repurchase" in concern.lower():
                if metrics and metrics.buyback_to_fcf_ratio:
                    learning = {
                        "type": "missed_red_flag",
                        "agent": "red_flag",
                        "issue": "Unsustainable buyback ratio not caught",
                        "metric": "buyback_to_fcf_ratio",
                        "current_threshold": 1.0,
                        "suggested_threshold": 0.8,  # More aggressive threshold
                        "severity": "high",
                        "company_ticker": company.ticker,
                        "actual_value": float(metrics.buyback_to_fcf_ratio),
                    }
                    learnings.append(learning)

            # Concern: "Unclear business model" or conglomerate signal
            if (
                "unclear" in concern.lower()
                or "confusing" in concern.lower()
                or "conglomerate" in concern.lower()
            ):
                learning = {
                    "type": "miscalibration",
                    "agent": "business_model",
                    "issue": "Business marked as clear when analyst found it unclear",
                    "company_ticker": company.ticker,
                    "reason": concern,
                    "severity": "high",
                }
                learnings.append(learning)

            # Concern: "Stock dilution / APIC growing" or "excessive compensation"
            if (
                "dilution" in concern.lower()
                or "apic" in concern.lower()
                or "compensation" in concern.lower()
            ):
                learning = {
                    "type": "missed_red_flag",
                    "agent": "red_flag",
                    "issue": "Stock dilution/compensation issue not flagged",
                    "metric": "stock_dilution_rate",
                    "severity": "high",
                    "company_ticker": company.ticker,
                    "reason": concern,
                }
                learnings.append(learning)

            # Concern: "Weak profitability" or "low margins"
            if "margin" in concern.lower() or "profitability" in concern.lower():
                if metrics and metrics.gross_margin:
                    learning = {
                        "type": "threshold_adjustment",
                        "agent": "filter",
                        "issue": "Gross margin threshold may be too lenient",
                        "metric": "gross_margin",
                        "current_threshold": 0.30,
                        "suggested_threshold": 0.35,
                        "company_ticker": company.ticker,
                        "actual_value": float(metrics.gross_margin),
                        "severity": "medium",
                    }
                    learnings.append(learning)

            # Concern: "No founder alignment" or "no insider ownership"
            if "founder" in concern.lower() or "insider" in concern.lower():
                learning = {
                    "type": "filter_requirement",
                    "agent": "founder",
                    "issue": "Founder/insider alignment too lax",
                    "suggested_min_ownership": 0.10,  # Stricter
                    "company_ticker": company.ticker,
                    "severity": "medium",
                }
                learnings.append(learning)

            # Concern: "Weak growth" or "stagnation"
            if "growth" in concern.lower() or "stagnant" in concern.lower():
                learning = {
                    "type": "threshold_adjustment",
                    "agent": "growth",
                    "issue": "Growth rate threshold too low",
                    "metric": "revenue_growth_3yr_cagr",
                    "current_threshold": 0.03,
                    "suggested_threshold": 0.05,
                    "company_ticker": company.ticker,
                    "severity": "medium",
                }
                learnings.append(learning)

            # Concern: "High leverage" or "too much debt"
            if "leverage" in concern.lower() or "debt" in concern.lower():
                if metrics and metrics.net_debt_ebitda:
                    learning = {
                        "type": "threshold_adjustment",
                        "agent": "filter",
                        "issue": "Leverage threshold too permissive",
                        "metric": "net_debt_ebitda",
                        "current_threshold": 4.0,
                        "suggested_threshold": 3.5,
                        "company_ticker": company.ticker,
                        "actual_value": float(metrics.net_debt_ebitda),
                        "severity": "high",
                    }
                    learnings.append(learning)

        return learnings

    async def _extract_concerns(self, notes: str) -> list[str]:
        """
        Parse analyst notes to extract specific concerns using LLM.
        Example: "FCF $70M but buyback $210M, also unclear business"
        → ["unsustainable buybacks", "unclear business model"]
        """

        if not notes or len(notes.strip()) < 10:
            return []

        prompt = f"""Analyst notes: "{notes}"

Extract the specific concerns, red flags, or reasons for rejection mentioned.
Return ONLY a JSON list of concern strings, one per issue.
Example: ["unsustainable buybacks", "unclear business model", "too much leverage"]

If no specific concerns found, return empty list: []
Be thorough — capture all distinct concerns mentioned."""

        try:
            # FIX: Removed output_format="json" parameter (doesn't exist)
            response = await self.llm.complete(
                prompt,
                model="claude-haiku",
                temperature=0
            )

            # Response is a string, parse it as JSON
            if isinstance(response, str):
                concerns = json.loads(response)
                return concerns if isinstance(concerns, list) else []
            return response if isinstance(response, list) else []
        except json.JSONDecodeError as je:
            logger.warning(f"Failed to parse LLM response as JSON for notes: {je}")
            return []
        except Exception as e:
            logger.warning(f"Failed to extract concerns from notes: {e}")
            return []
