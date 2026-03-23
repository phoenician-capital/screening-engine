"""
Analyst-set price targets / alerts.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.models.base import Base


class PriceAlert(Base):
    __tablename__ = "price_alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ticker: Mapped[str] = mapped_column(
        String(20), ForeignKey("companies.ticker"), index=True
    )
    target_price: Mapped[float] = mapped_column(Numeric)
    notes: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[dt.date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(
        String(20), default="active", index=True
    )  # active | triggered | dismissed | expired
    triggered_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    triggered_price: Mapped[float | None] = mapped_column(Numeric)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<PriceAlert {self.ticker} target={self.target_price} status={self.status}>"
