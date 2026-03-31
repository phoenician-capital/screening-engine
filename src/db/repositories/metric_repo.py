"""
Metrics time-series queries.
"""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select

from src.db.models.metric import Metric
from src.db.repositories.base_repo import BaseRepository


class MetricRepository(BaseRepository[Metric]):
    model = Metric

    async def get_latest(self, ticker: str) -> Metric | None:
        stmt = (
            select(Metric)
            .where(Metric.ticker == ticker)
            .order_by(Metric.period_end.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_history(
        self, ticker: str, period_type: str = "annual", limit: int = 5
    ) -> Sequence[Metric]:
        stmt = (
            select(Metric)
            .where(Metric.ticker == ticker, Metric.period_type == period_type)
            .order_by(Metric.period_end.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_sector_medians(self, gics_sector: str) -> dict:
        """Compute sector median multiples for valuation comparison."""
        from sqlalchemy import func as sqlfunc

        stmt = (
            select(
                sqlfunc.percentile_cont(0.5)
                .within_group(Metric.ev_ebit)
                .label("median_ev_ebit"),
                sqlfunc.percentile_cont(0.5)
                .within_group(Metric.ev_fcf)
                .label("median_ev_fcf"),
                sqlfunc.percentile_cont(0.5)
                .within_group(Metric.gross_margin)
                .label("median_gross_margin"),
            )
            .join(Metric.company)
            .where(Metric.company.has(gics_sector=gics_sector))
        )
        result = await self.session.execute(stmt)
        row = result.one_or_none()
        if not row:
            return {}
        return {
            "median_ev_ebit": row.median_ev_ebit,
            "median_ev_fcf": row.median_ev_fcf,
            "median_gross_margin": row.median_gross_margin,
        }
