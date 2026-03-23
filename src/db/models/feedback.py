"""
Analyst feedback on recommendations.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models.base import Base


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recommendations.id"), index=True
    )
    ticker: Mapped[str] = mapped_column(String(20), index=True)
    analyst_id: Mapped[str | None] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(20))  # reject | watch | research_now
    reject_reason: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    recommendation: Mapped["Recommendation"] = relationship(
        back_populates="feedback_entries"
    )

    def __repr__(self) -> str:
        return f"<Feedback {self.action} on {self.ticker}>"
