"""
Feedback loop — processes analyst feedback to adjust scoring weights.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.config.scoring_weights import load_scoring_weights
from src.db.repositories import FeedbackRepository

logger = logging.getLogger(__name__)


class FeedbackLoop:
    """Analyze feedback patterns and adjust scoring weights."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.feedback_repo = FeedbackRepository(session)

    async def compute_adjustments(self, days: int = 30) -> dict[str, float]:
        """
        Analyze recent feedback to compute weight adjustments.
        Returns dict of {criterion_name: adjustment_delta}.
        """
        recent = await self.feedback_repo.get_recent_feedback(days=days)

        if not recent:
            return {}

        # Count accepts (research_now) vs rejects
        accept_count = sum(1 for f in recent if f.action == "research_now")
        reject_count = sum(1 for f in recent if f.action == "reject")
        total = accept_count + reject_count

        if total < 5:
            logger.info("Not enough feedback for adjustment (%d total)", total)
            return {}

        # Analyze reject reasons
        reason_summary = await self.feedback_repo.get_reject_reasons_summary()

        adjustments: dict[str, float] = {}

        # If many rejects for valuation → boost valuation weight
        for item in reason_summary:
            reason = item["reason"]
            count = item["count"]
            ratio = count / total

            if reason == "valuation_unattractive" and ratio > 0.3:
                adjustments["valuation_asymmetry"] = 2.0  # Boost by 2 points
            elif reason == "mgmt_quality" and ratio > 0.3:
                adjustments["founder_ownership"] = 2.0
            elif reason == "too_cyclical" and ratio > 0.2:
                adjustments["business_quality"] = 1.5

        # Compute precision
        precision = accept_count / total if total > 0 else 0
        logger.info(
            "Feedback analysis: %d accepts, %d rejects (precision: %.1f%%)",
            accept_count, reject_count, precision * 100,
        )

        return adjustments

    async def apply_adjustments(self, adjustments: dict[str, float]) -> None:
        """Apply weight adjustments to the scoring config YAML."""
        if not adjustments:
            return

        config = load_scoring_weights(force_reload=True)
        categories = config.get("categories", {})

        for category_name, delta in adjustments.items():
            if category_name in categories:
                old_weight = categories[category_name].get("weight", 0)
                new_weight = old_weight + delta
                categories[category_name]["weight"] = max(5.0, min(35.0, new_weight))
                logger.info(
                    "Adjusted %s weight: %.1f → %.1f",
                    category_name, old_weight, new_weight,
                )

        # Normalize weights to sum to 100
        total_weight = sum(c.get("weight", 0) for c in categories.values())
        if total_weight != 100:
            factor = 100.0 / total_weight
            for cat in categories.values():
                cat["weight"] = round(cat["weight"] * factor, 1)

        # Write back
        weights_path = settings.scoring.weights_file
        with open(weights_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        logger.info("Scoring weights updated and saved to %s", weights_path)
