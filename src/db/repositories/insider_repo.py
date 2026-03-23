"""
Insider purchase queries.
"""

from __future__ import annotations

import datetime as dt
from typing import Sequence

from sqlalchemy import func as sqlfunc, select

from src.db.models.insider_purchase import InsiderPurchase
from src.db.repositories.base_repo import BaseRepository


class InsiderRepository(BaseRepository[InsiderPurchase]):
    model = InsiderPurchase

    async def get_recent(self, days: int = 30) -> Sequence[InsiderPurchase]:
        cutoff = dt.date.today() - dt.timedelta(days=days)
        stmt = (
            select(InsiderPurchase)
            .where(InsiderPurchase.transaction_date >= cutoff)
            .where(InsiderPurchase.is_open_market.is_(True))
            .order_by(InsiderPurchase.transaction_date.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_cluster_buys(self, days: int = 14) -> Sequence[InsiderPurchase]:
        cutoff = dt.date.today() - dt.timedelta(days=days)
        stmt = (
            select(InsiderPurchase)
            .where(InsiderPurchase.transaction_date >= cutoff)
            .where(InsiderPurchase.is_cluster.is_(True))
            .where(InsiderPurchase.is_open_market.is_(True))
            .order_by(InsiderPurchase.conviction_score.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_top_conviction(self, limit: int = 20, days: int = 30) -> Sequence[InsiderPurchase]:
        cutoff = dt.date.today() - dt.timedelta(days=days)
        stmt = (
            select(InsiderPurchase)
            .where(InsiderPurchase.transaction_date >= cutoff)
            .where(InsiderPurchase.is_open_market.is_(True))
            .order_by(InsiderPurchase.conviction_score.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_for_ticker(self, ticker: str) -> Sequence[InsiderPurchase]:
        stmt = (
            select(InsiderPurchase)
            .where(InsiderPurchase.ticker == ticker)
            .order_by(InsiderPurchase.transaction_date.desc())
            .limit(20)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_cluster_purchases_for_ticker(
        self, ticker: str, days: int = 30
    ) -> Sequence[InsiderPurchase]:
        cutoff = dt.date.today() - dt.timedelta(days=days)
        stmt = (
            select(InsiderPurchase)
            .where(
                InsiderPurchase.ticker == ticker,
                InsiderPurchase.transaction_date >= cutoff,
                InsiderPurchase.is_open_market.is_(True),
            )
            .order_by(InsiderPurchase.transaction_date.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
