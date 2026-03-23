"""
Financial metrics — time-series per company per period.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models.base import Base


class Metric(Base):
    __tablename__ = "metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ticker: Mapped[str] = mapped_column(
        String(20), ForeignKey("companies.ticker"), index=True
    )
    period_end: Mapped[dt.date] = mapped_column(Date)
    period_type: Mapped[str] = mapped_column(String(10))  # 'annual' | 'quarter'

    # Income statement
    revenue: Mapped[float | None] = mapped_column(Numeric)
    gross_profit: Mapped[float | None] = mapped_column(Numeric)
    gross_margin: Mapped[float | None] = mapped_column(Numeric)
    ebit: Mapped[float | None] = mapped_column(Numeric)
    ebit_margin: Mapped[float | None] = mapped_column(Numeric)
    net_income: Mapped[float | None] = mapped_column(Numeric)

    # Cash flow
    fcf: Mapped[float | None] = mapped_column(Numeric)
    fcf_yield: Mapped[float | None] = mapped_column(Numeric)
    capex: Mapped[float | None] = mapped_column(Numeric)
    capex_to_revenue: Mapped[float | None] = mapped_column(Numeric)

    # Balance sheet
    net_debt: Mapped[float | None] = mapped_column(Numeric)
    net_debt_ebitda: Mapped[float | None] = mapped_column(Numeric)
    total_assets: Mapped[float | None] = mapped_column(Numeric)

    # Returns
    roic: Mapped[float | None] = mapped_column(Numeric)
    roe: Mapped[float | None] = mapped_column(Numeric)

    # Growth
    revenue_growth_yoy: Mapped[float | None] = mapped_column(Numeric)
    revenue_growth_3yr_cagr: Mapped[float | None] = mapped_column(Numeric)

    # Valuation multiples (snapshot)
    ev_ebit: Mapped[float | None] = mapped_column(Numeric)
    ev_fcf: Mapped[float | None] = mapped_column(Numeric)
    pe_ratio: Mapped[float | None] = mapped_column(Numeric)

    # Ownership / coverage
    insider_ownership_pct: Mapped[float | None] = mapped_column(Numeric)
    institutional_ownership_pct: Mapped[float | None] = mapped_column(Numeric)
    analyst_count: Mapped[int | None] = mapped_column(Integer)

    # Market data
    market_cap_usd: Mapped[float | None] = mapped_column(Numeric)
    avg_daily_volume: Mapped[float | None] = mapped_column(Numeric)
    shares_outstanding: Mapped[float | None] = mapped_column(Numeric)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="metrics")

    def __repr__(self) -> str:
        return f"<Metric {self.ticker} {self.period_type} {self.period_end}>"
