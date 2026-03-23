"""
Feedback queries + aggregation for scoring adjustments.
"""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import func as sqlfunc
from sqlalchemy import select

from src.db.models.feedback import Feedback
from src.db.repositories.base_repo import BaseRepository


class FeedbackRepository(BaseRepository[Feedback]):
    model = Feedback

    async def get_for_ticker(self, ticker: str) -> Sequence[Feedback]:
        stmt = (
            select(Feedback)
            .where(Feedback.ticker == ticker)
            .order_by(Feedback.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_by_action(self, ticker: str) -> dict[str, int]:
        stmt = (
            select(Feedback.action, sqlfunc.count(Feedback.id))
            .where(Feedback.ticker == ticker)
            .group_by(Feedback.action)
        )
        result = await self.session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def get_reject_reasons_summary(self) -> list[dict]:
        stmt = (
            select(
                Feedback.reject_reason,
                sqlfunc.count(Feedback.id).label("count"),
            )
            .where(Feedback.action == "reject")
            .where(Feedback.reject_reason.isnot(None))
            .group_by(Feedback.reject_reason)
            .order_by(sqlfunc.count(Feedback.id).desc())
        )
        result = await self.session.execute(stmt)
        return [{"reason": row[0], "count": row[1]} for row in result.all()]

    async def get_recent_feedback(self, days: int = 30) -> Sequence[Feedback]:
        from datetime import datetime, timedelta, timezone

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = (
            select(Feedback)
            .where(Feedback.created_at >= cutoff)
            .order_by(Feedback.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
