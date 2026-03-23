"""
Generated recommendations with memos and scoring details.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models.base import Base


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ticker: Mapped[str] = mapped_column(
        String(20), ForeignKey("companies.ticker"), index=True
    )
    scoring_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scoring_runs.id")
    )

    # Scores
    fit_score: Mapped[float] = mapped_column(Numeric)
    risk_score: Mapped[float] = mapped_column(Numeric)
    rank_score: Mapped[float] = mapped_column(Numeric)
    rank: Mapped[int | None] = mapped_column(Integer)

    # Memo
    memo_text: Mapped[str | None] = mapped_column(Text)
    citations: Mapped[list | None] = mapped_column(JSONB)
    scoring_detail: Mapped[dict | None] = mapped_column(JSONB)
    portfolio_comparison: Mapped[dict | None] = mapped_column(JSONB)
    inspired_by: Mapped[str | None] = mapped_column(String(20))

    # Status
    status: Mapped[str] = mapped_column(
        String(20), default="pending", index=True
    )

    generated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="recommendations")
    feedback_entries: Mapped[list["Feedback"]] = relationship(back_populates="recommendation")

    def __repr__(self) -> str:
        return f"<Recommendation {self.ticker} fit={self.fit_score} rank={self.rank}>"
