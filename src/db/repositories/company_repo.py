"""
Company-specific queries.
"""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select, update

from src.db.models.company import Company
from src.db.repositories.base_repo import BaseRepository


class CompanyRepository(BaseRepository[Company]):
    model = Company

    async def get_by_ticker(self, ticker: str) -> Company | None:
        return await self.get_by_id(ticker)

    async def get_active(self, limit: int = 5000) -> Sequence[Company]:
        stmt = select(Company).where(Company.is_active.is_(True)).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_sector(self, gics_sector: str) -> Sequence[Company]:
        stmt = select(Company).where(Company.gics_sector == gics_sector)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_in_market_cap_range(
        self, min_cap: float, max_cap: float
    ) -> Sequence[Company]:
        stmt = (
            select(Company)
            .where(Company.market_cap_usd >= min_cap)
            .where(Company.market_cap_usd <= max_cap)
            .where(Company.is_active.is_(True))
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def upsert(self, data: dict) -> Company:
        existing = await self.get_by_ticker(data["ticker"])
        if existing:
            stmt = (
                update(Company)
                .where(Company.ticker == data["ticker"])
                .values(**{k: v for k, v in data.items() if k != "ticker"})
            )
            await self.session.execute(stmt)
            await self.session.flush()
            return await self.get_by_ticker(data["ticker"])
        company = Company(**data)
        return await self.create(company)

    async def get_tickers_not_in_db(self, tickers: list[str]) -> list[str]:
        stmt = select(Company.ticker).where(Company.ticker.in_(tickers))
        result = await self.session.execute(stmt)
        existing = {row[0] for row in result.all()}
        return [t for t in tickers if t not in existing]
