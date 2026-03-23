"""
Portfolio holdings repository.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.portfolio import PortfolioHolding


class PortfolioRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active(self) -> list[PortfolioHolding]:
        result = await self.session.execute(
            select(PortfolioHolding)
            .where(PortfolioHolding.is_active == True)
            .order_by(PortfolioHolding.date_added.desc().nullslast())
        )
        return list(result.scalars().all())

    async def get_by_ticker(self, ticker: str) -> PortfolioHolding | None:
        result = await self.session.execute(
            select(PortfolioHolding)
            .where(PortfolioHolding.ticker == ticker, PortfolioHolding.is_active == True)
        )
        return result.scalar_one_or_none()

    async def add(self, holding: PortfolioHolding) -> PortfolioHolding:
        self.session.add(holding)
        await self.session.flush()
        return holding

    async def remove(self, ticker: str) -> None:
        result = await self.session.execute(
            select(PortfolioHolding).where(PortfolioHolding.ticker == ticker)
        )
        h = result.scalar_one_or_none()
        if h:
            h.is_active = False
            await self.session.flush()

    async def get_sector_weights(self) -> dict[str, float]:
        """Return {sector: total_position_usd} for active holdings."""
        holdings = await self.get_active()
        weights: dict[str, float] = {}
        for h in holdings:
            if h.sector and h.position_size_usd:
                weights[h.sector] = weights.get(h.sector, 0.0) + float(h.position_size_usd)
        return weights

    async def get_avg_metrics(self) -> dict:
        """Return portfolio-average metrics for comparison."""
        holdings = await self.get_active()
        if not holdings:
            return {}
        gms   = [float(h.entry_gross_margin)   for h in holdings if h.entry_gross_margin   is not None]
        roics = [float(h.entry_roic)            for h in holdings if h.entry_roic            is not None]
        evs   = [float(h.entry_ev_ebit)         for h in holdings if h.entry_ev_ebit         is not None]
        revgs = [float(h.entry_revenue_growth)  for h in holdings if h.entry_revenue_growth  is not None]
        return {
            "avg_gross_margin":    sum(gms)   / len(gms)   if gms   else None,
            "avg_roic":            sum(roics) / len(roics) if roics else None,
            "avg_ev_ebit":         sum(evs)   / len(evs)   if evs   else None,
            "avg_revenue_growth":  sum(revgs) / len(revgs) if revgs else None,
            "holding_count":       len(holdings),
            "sectors":             list({h.sector for h in holdings if h.sector}),
        }
