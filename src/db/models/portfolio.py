"""
Portfolio holdings — current positions used for comparison during screening.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Boolean, Date, DateTime, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.models.base import Base


class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    sector: Mapped[str | None] = mapped_column(String(100))

    # Position details
    entry_price: Mapped[float | None] = mapped_column(Numeric)
    position_size_usd: Mapped[float | None] = mapped_column(Numeric)
    date_added: Mapped[dt.date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    ir_url: Mapped[str | None] = mapped_column(Text)
    events_url: Mapped[str | None] = mapped_column(Text)

    # Snapshot metrics at time of entry (for comparison)
    entry_gross_margin: Mapped[float | None] = mapped_column(Numeric)
    entry_roic: Mapped[float | None] = mapped_column(Numeric)
    entry_ev_ebit: Mapped[float | None] = mapped_column(Numeric)
    entry_revenue_growth: Mapped[float | None] = mapped_column(Numeric)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
