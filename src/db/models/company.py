"""
Company master record.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models.base import Base


class Company(Base):
    __tablename__ = "companies"

    ticker: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    exchange: Mapped[str | None] = mapped_column(String(50))
    country: Mapped[str | None] = mapped_column(String(100))
    gics_sector: Mapped[str | None] = mapped_column(String(100))
    gics_industry_group: Mapped[str | None] = mapped_column(String(100))
    gics_industry: Mapped[str | None] = mapped_column(String(100))
    gics_sub_industry: Mapped[str | None] = mapped_column(String(100))
    market_cap_usd: Mapped[float | None] = mapped_column(Numeric)
    description: Mapped[str | None] = mapped_column(String(2000))
    website: Mapped[str | None] = mapped_column(String(500))
    cik: Mapped[str | None] = mapped_column(String(20))  # SEC CIK number
    is_founder_led: Mapped[bool | None] = mapped_column(Boolean)
    founder_name: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Discovery provenance — how and when this company entered the universe
    discovery_source: Mapped[str | None] = mapped_column(String(50))   # e.g. 'claude_dynamic', 'nasdaq_api', 'sec_edgar', 'portfolio_analog'
    market_tier: Mapped[int | None] = mapped_column()                   # 1 = primary markets, 2 = secondary markets (higher quality bar)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    metrics: Mapped[list["Metric"]] = relationship(back_populates="company")
    documents: Mapped[list["Document"]] = relationship(back_populates="company")
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="company")

    def __repr__(self) -> str:
        return f"<Company {self.ticker} '{self.name}'>"
