"""
Insider purchases sourced from SEC Form 4 filings.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.models.base import Base


class InsiderPurchase(Base):
    __tablename__ = "insider_purchases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ticker: Mapped[str] = mapped_column(
        String(20), ForeignKey("companies.ticker"), index=True
    )
    insider_name: Mapped[str] = mapped_column(String(255))
    insider_title: Mapped[str | None] = mapped_column(String(100))  # CEO | CFO | Director
    shares: Mapped[int | None] = mapped_column(Integer)
    price_per_share: Mapped[float | None] = mapped_column(Numeric)
    total_value: Mapped[float | None] = mapped_column(Numeric)
    transaction_date: Mapped[dt.date] = mapped_column(Date, index=True)
    form4_url: Mapped[str | None] = mapped_column(Text)
    is_open_market: Mapped[bool] = mapped_column(Boolean, default=True)
    conviction_score: Mapped[float | None] = mapped_column(Numeric)  # 0–100
    is_cluster: Mapped[bool] = mapped_column(Boolean, default=False)
    near_52wk_low: Mapped[bool] = mapped_column(Boolean, default=False)
    cluster_window_days: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<InsiderPurchase {self.ticker} {self.insider_name} ${self.total_value:,.0f}>"
