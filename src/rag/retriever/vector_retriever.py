"""
Vector-based retriever for RAG — searches embedding store for relevant chunks.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.llm.embeddings import embed_single

logger = logging.getLogger(__name__)


class VectorRetriever:
    """Retrieve relevant document chunks via vector similarity search."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(
        self,
        query: str,
        ticker: str | None = None,
        doc_type: str | None = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Embed query and find most similar chunks in pgvector.
        Returns list of {id, score, text, metadata}.
        """
        query_embedding = await embed_single(query)

        # Build pgvector query with optional filters
        filters = []
        params: dict[str, Any] = {
            "embedding": str(query_embedding),
            "top_k": top_k,
        }

        if ticker:
            filters.append("e.ticker = :ticker")
            params["ticker"] = ticker

        if doc_type:
            filters.append("d.doc_type = :doc_type")
            params["doc_type"] = doc_type

        where_clause = ""
        if filters:
            where_clause = "WHERE " + " AND ".join(filters)

        sql = text(f"""
            SELECT
                e.id,
                e.chunk_text,
                e.chunk_index,
                e.metadata,
                e.doc_id,
                e.ticker,
                d.doc_type,
                d.source_url,
                1 - (e.embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM embeddings e
            JOIN documents d ON e.doc_id = d.id
            {where_clause}
            ORDER BY e.embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
        """)

        result = await self.session.execute(sql, params)
        rows = result.fetchall()

        chunks = []
        for row in rows:
            chunks.append({
                "id": str(row.id),
                "text": row.chunk_text,
                "chunk_index": row.chunk_index,
                "score": float(row.similarity) if row.similarity else 0.0,
                "metadata": {
                    "doc_id": str(row.doc_id),
                    "ticker": row.ticker,
                    "doc_type": row.doc_type,
                    "source_url": row.source_url,
                    **(row.metadata or {}),
                },
            })

        logger.info(
            "Retrieved %d chunks for query '%s...' (ticker=%s)",
            len(chunks), query[:50], ticker,
        )
        return chunks
