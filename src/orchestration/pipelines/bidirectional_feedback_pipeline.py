"""
Bidirectional Feedback Pipeline — Both selection and scoring teams learn from analyst feedback.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.feedback import Feedback
from src.db.models.learned_patterns import SelectionLearnedPattern, ScoringLearnedPattern
from src.db.repositories.base_repo import BaseRepository
from src.feedback.selection_feedback_analyzer import SelectionFeedbackAnalyzer

logger = logging.getLogger(__name__)


class SelectionLearningRepository(BaseRepository):
    """CRUD for selection learned patterns."""

    async def save_pattern(self, pattern_dict: dict) -> SelectionLearnedPattern:
        """Save a learned pattern from analyst feedback."""
        pattern = SelectionLearnedPattern(
            pattern_type=pattern_dict.get("type"),
            agent_type=pattern_dict.get("agent"),
            metric_name=pattern_dict.get("metric"),
            old_threshold={"value": pattern_dict.get("current_threshold")},
            new_threshold={"value": pattern_dict.get("suggested_threshold")},
            triggered_by_feedback_id=pattern_dict.get("feedback_id"),
            analyst_action=pattern_dict.get("analyst_action"),
            confidence=pattern_dict.get("confidence", 0.7),
            expires_at=datetime.utcnow() + timedelta(days=30),
            metadata=pattern_dict,
        )
        self.session.add(pattern)
        await self.session.flush()
        return pattern

    async def get_active_patterns(self, agent_type: str | None = None):
        """Get active (non-expired) learned patterns."""
        from sqlalchemy import select

        query = select(SelectionLearnedPattern).where(
            SelectionLearnedPattern.expires_at > datetime.utcnow()
        )
        if agent_type:
            query = query.where(SelectionLearnedPattern.agent_type == agent_type)

        result = await self.session.execute(query)
        return result.scalars().all()


class ScoringLearningRepository(BaseRepository):
    """CRUD for scoring learned patterns."""

    async def save_pattern(self, pattern_dict: dict) -> ScoringLearnedPattern:
        """Save a learned pattern from analyst feedback."""
        pattern = ScoringLearnedPattern(
            pattern_type=pattern_dict.get("type"),
            dimension=pattern_dict.get("dimension"),
            pattern_data=pattern_dict.get("pattern_data", {}),
            triggered_by_feedback_id=pattern_dict.get("feedback_id"),
            analyst_action=pattern_dict.get("analyst_action"),
            confidence=pattern_dict.get("confidence", 0.7),
            expires_at=datetime.utcnow() + timedelta(days=60),
            metadata=pattern_dict,
        )
        self.session.add(pattern)
        await self.session.flush()
        return pattern


class BidirectionalFeedbackPipeline:
    """
    When analyst submits feedback, both selection + scoring teams learn.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.selection_repo = SelectionLearningRepository(session)
        self.scoring_repo = ScoringLearningRepository(session)

    async def process_feedback(self, feedback: Feedback):
        """
        1. Analyze selection performance
        2. Analyze scoring performance
        3. Extract learnings for both teams
        4. Update both teams' learned patterns DB
        """

        # Ensure recommendation is loaded
        if not feedback.recommendation:
            # Try to reload recommendation explicitly
            try:
                from src.db.repositories.recommendation_repo import RecommendationRepository
                rec_repo = RecommendationRepository(self.session)
                rec = await rec_repo.get_by_id(feedback.recommendation_id)
                if not rec:
                    logger.warning(f"Feedback {feedback.id} has no recommendation, skipping learning")
                    return
            except Exception as e:
                logger.warning(f"Failed to load recommendation for feedback {feedback.id}: {e}")
                return
        else:
            company = rec.company
        metrics = rec.metrics_at_time_of_scoring if hasattr(rec, 'metrics_at_time_of_scoring') else None

        logger.info(
            f"Processing feedback for {feedback.ticker}: "
            f"action={feedback.action}, notes={bool(feedback.notes)}"
        )

        # ══════════════════════════════════════════════════════════════
        # SELECTION TEAM LEARNING
        # ══════════════════════════════════════════════════════════════

        if feedback.action == "reject" and feedback.notes:
            try:
                # If analyst rejected, selection team learns what to catch next time
                selection_analyzer = SelectionFeedbackAnalyzer(self.session)
                selection_learnings = await selection_analyzer.analyze(
                    feedback=feedback,
                    company=company,
                    metrics=metrics,
                    selection_detail=rec.scoring_detail.get("selection_detail") if rec.scoring_detail else None,
                )

                # Store learnings
                for learning in selection_learnings:
                    learning["feedback_id"] = feedback.id
                    learning["analyst_action"] = feedback.action
                    learning["confidence"] = 0.7  # Start at 70%, increase with validation
                    await self.selection_repo.save_pattern(learning)
                    logger.info(
                        f"Selection learning: {learning['type']} on {learning.get('agent', 'unknown')} "
                        f"(confidence {learning.get('confidence', 0):.0%})"
                    )
            except Exception as e:
                logger.error(f"Selection learning failed for {feedback.ticker}: {e}", exc_info=True)

        # ══════════════════════════════════════════════════════════════
        # SCORING TEAM LEARNING
        # ══════════════════════════════════════════════════════════════

        if feedback.notes:
            try:
                scoring_learnings = await self._analyze_scoring_feedback(
                    feedback, company, metrics
                )
                for learning in scoring_learnings:
                    learning["feedback_id"] = feedback.id
                    learning["analyst_action"] = feedback.action
                    await self.scoring_repo.save_pattern(learning)
                    logger.info(f"Scoring learning: {learning.get('type', 'unknown')} stored")
            except Exception as e:
                logger.error(f"Scoring learning failed for {feedback.ticker}: {e}")

        logger.info(
            f"Feedback processing complete for {feedback.ticker}: "
            f"learned patterns stored, expires in 30/60 days"
        )

    async def _analyze_scoring_feedback(
        self, feedback: Feedback, company, metrics
    ) -> list[dict]:
        """Analyze feedback for scoring team learnings (simplified for now)."""
        learnings = []

        if not feedback.notes:
            return learnings

        # Extract simple patterns: if analyst mentions "leverage", scoring team learns
        # to weight leverage more heavily
        if "leverage" in feedback.notes.lower():
            learnings.append({
                "type": "dimension_weight",
                "dimension": "capital_structure",
                "pattern_data": {
                    "issue": "leverage",
                    "suggested_weight_adjustment": +0.15,
                },
                "confidence": 0.6,
            })

        if "buyback" in feedback.notes.lower() or "repurchase" in feedback.notes.lower():
            learnings.append({
                "type": "red_flag",
                "dimension": "capital_allocation",
                "pattern_data": {
                    "issue": "unsustainable_buybacks",
                    "check": "buyback_to_fcf_ratio > 1.0",
                    "adjustment": -25,
                },
                "confidence": 0.8,
            })

        if "growth" in feedback.notes.lower() and "weak" in feedback.notes.lower():
            learnings.append({
                "type": "dimension_weight",
                "dimension": "growth_quality",
                "pattern_data": {
                    "issue": "weak_growth",
                    "suggested_weight_adjustment": +0.10,
                },
                "confidence": 0.7,
            })

        return learnings
