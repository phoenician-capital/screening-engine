"""
Raw document storage — filings, transcripts, news articles.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models.base import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ticker: Mapped[str] = mapped_column(
        String(20), ForeignKey("companies.ticker"), index=True
    )
    doc_type: Mapped[str] = mapped_column(String(50), index=True)
    source: Mapped[str | None] = mapped_column(String(100))  # 'sec_edgar' | 'perplexity' | ...
    source_url: Mapped[str | None] = mapped_column(Text)
    accession_no: Mapped[str | None] = mapped_column(String(50))  # SEC accession number
    title: Mapped[str | None] = mapped_column(String(500))
    raw_text: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict | None] = mapped_column(JSONB)
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="documents")
    embeddings: Mapped[list["Embedding"]] = relationship(back_populates="document")

    def __repr__(self) -> str:
        return f"<Document {self.doc_type} {self.ticker} {self.id}>"
