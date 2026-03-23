"""
Document storage and retrieval queries.
"""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select

from src.db.models.document import Document
from src.db.repositories.base_repo import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    model = Document

    async def get_by_ticker(
        self, ticker: str, doc_type: str | None = None, limit: int = 50
    ) -> Sequence[Document]:
        stmt = select(Document).where(Document.ticker == ticker)
        if doc_type:
            stmt = stmt.where(Document.doc_type == doc_type)
        stmt = stmt.order_by(Document.published_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def exists_by_accession(self, accession_no: str) -> bool:
        stmt = select(Document.id).where(Document.accession_no == accession_no).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_by_type(
        self, doc_type: str, limit: int = 100
    ) -> Sequence[Document]:
        stmt = (
            select(Document)
            .where(Document.doc_type == doc_type)
            .order_by(Document.ingested_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_latest_by_type(
        self, ticker: str, doc_type: str
    ) -> Document | None:
        stmt = (
            select(Document)
            .where(Document.ticker == ticker, Document.doc_type == doc_type)
            .order_by(Document.ingested_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_meta_filter(
        self,
        doc_type: str,
        min_relevance: float = 0.7,
        lookback_days: int = 7,
    ) -> Sequence[Document]:
        """Return documents of a given type with meta.relevance_score >= threshold."""
        import datetime as dt
        from sqlalchemy import cast, Float, text
        cutoff = dt.datetime.utcnow() - dt.timedelta(days=lookback_days)
        stmt = (
            select(Document)
            .where(
                Document.doc_type == doc_type,
                Document.ingested_at >= cutoff,
                Document.meta.isnot(None),
                cast(Document.meta["relevance_score"].astext, Float) >= min_relevance,
            )
            .order_by(Document.ingested_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def exists_by_title_or_url(
        self, ticker: str, title: str | None, url: str | None
    ) -> bool:
        """Check if an ir_event or similar doc already exists to avoid duplicates."""
        from sqlalchemy import or_
        conditions = []
        if title:
            conditions.append(Document.title == title)
        if url:
            conditions.append(Document.source_url == url)
        if not conditions:
            return False
        stmt = (
            select(Document.id)
            .where(Document.ticker == ticker, or_(*conditions))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None
