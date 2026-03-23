"""
Price alert queries.
"""

from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import select, update

from src.db.models.price_alert import PriceAlert
from src.db.repositories.base_repo import BaseRepository


class PriceAlertRepository(BaseRepository[PriceAlert]):
    model = PriceAlert

    async def get_active(self) -> Sequence[PriceAlert]:
        stmt = (
            select(PriceAlert)
            .where(PriceAlert.status == "active")
            .order_by(PriceAlert.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_triggered(self) -> Sequence[PriceAlert]:
        stmt = (
            select(PriceAlert)
            .where(PriceAlert.status == "triggered")
            .order_by(PriceAlert.triggered_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_history(self, limit: int = 50) -> Sequence[PriceAlert]:
        stmt = (
            select(PriceAlert)
            .where(PriceAlert.status.in_(["triggered", "dismissed", "expired"]))
            .order_by(PriceAlert.triggered_at.desc().nullslast())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def dismiss(self, alert_id: uuid.UUID) -> None:
        stmt = (
            update(PriceAlert)
            .where(PriceAlert.id == alert_id)
            .values(status="dismissed")
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def get_for_ticker(self, ticker: str) -> Sequence[PriceAlert]:
        stmt = (
            select(PriceAlert)
            .where(PriceAlert.ticker == ticker)
            .order_by(PriceAlert.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
