"""
Ranker — combines fit score, risk score, and feedback adjustments
to produce final rankings.
"""

from __future__ import annotations

import logging
from typing import Sequence

from src.config.scoring_weights import load_scoring_weights
from src.shared.types import ScoringResult

logger = logging.getLogger(__name__)


class Ranker:
    """Produce final ranked list from scoring results."""

    def __init__(self) -> None:
        config = load_scoring_weights()
        ranking = config.get("ranking", {})
        self.fit_weight = ranking.get("fit_weight", 0.70)
        self.risk_weight = ranking.get("risk_penalty_weight", 0.30)
        self.decay_per_reject = ranking.get("feedback_decay_per_reject", 0.02)
        self.boost_per_accept = ranking.get("feedback_boost_per_accept", 0.03)

    def compute_rank_score(
        self,
        fit_score: float,
        risk_score: float,
        feedback_stats: dict[str, int] | None = None,
    ) -> float:
        """
        Compute final rank score.
        rank_score = fit_score * fit_weight - risk_score * risk_weight + feedback_adj
        """
        base = fit_score * self.fit_weight - risk_score * self.risk_weight

        # Feedback adjustment
        adjustment = 0.0
        if feedback_stats:
            rejects = feedback_stats.get("reject", 0)
            accepts = feedback_stats.get("research_now", 0)
            adjustment = (accepts * self.boost_per_accept * 100) - (
                rejects * self.decay_per_reject * 100
            )

        return base + adjustment

    def rank(self, results: list[ScoringResult]) -> list[ScoringResult]:
        """Sort results by rank_score descending, assign rank positions."""
        # Filter out disqualified
        active = [r for r in results if not r.disqualified]
        active.sort(key=lambda r: r.rank_score, reverse=True)

        logger.info(
            "Ranked %d companies (%d disqualified)",
            len(active),
            len(results) - len(active),
        )
        return active
