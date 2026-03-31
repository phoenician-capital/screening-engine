"""
Recommendation queries.
"""

from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import select, update

from src.db.models.recommendation import Recommendation
from src.db.repositories.base_repo import BaseRepository


class RecommendationRepository(BaseRepository[Recommendation]):
    model = Recommendation

    async def get_top_ranked(
        self, limit: int = 20, status: str | None = None
    ) -> Sequence[Recommendation]:
        stmt = select(Recommendation).order_by(Recommendation.rank.asc())
        if status:
            stmt = stmt.where(Recommendation.status == status)
        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_latest_for_ticker(self, ticker: str) -> Recommendation | None:
        stmt = (
            select(Recommendation)
            .where(Recommendation.ticker == ticker)
            .order_by(Recommendation.generated_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(self, rec_id: uuid.UUID, status: str) -> None:
        stmt = (
            update(Recommendation)
            .where(Recommendation.id == rec_id)
            .values(status=status)
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def update_memo(
        self, rec_id: uuid.UUID, memo_text: str, citations: list
    ) -> None:
        stmt = (
            update(Recommendation)
            .where(Recommendation.id == rec_id)
            .values(memo_text=memo_text, citations=citations)
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def get_by_scoring_run(
        self, run_id: uuid.UUID
    ) -> Sequence[Recommendation]:
        stmt = (
            select(Recommendation)
            .where(Recommendation.scoring_run_id == run_id)
            .order_by(Recommendation.rank.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
