"""
MCP Tool: vector.upsert / vector.search
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_session
from src.rag.retriever.vector_retriever import VectorRetriever
from src.mcp_server.middleware.error_handler import tool_endpoint

router = APIRouter()


class VectorSearchRequest(BaseModel):
    query: str
    ticker: str | None = None
    doc_type: str | None = None
    top_k: int = 10


class VectorUpsertRequest(BaseModel):
    records: list[dict]
    collection: str = "documents"


@router.post("/search")
@tool_endpoint
async def search(req: VectorSearchRequest, session: AsyncSession = Depends(get_session)):
    retriever = VectorRetriever(session)
    results = await retriever.search(
        query=req.query,
        ticker=req.ticker,
        doc_type=req.doc_type,
        top_k=req.top_k,
    )
    return {"results": results}


@router.post("/upsert")
@tool_endpoint
async def upsert(req: VectorUpsertRequest, session: AsyncSession = Depends(get_session)):
    # Bulk upsert via raw SQL for pgvector
    from sqlalchemy import text
    import uuid

    count = 0
    for record in req.records:
        sql = text("""
            INSERT INTO embeddings (id, doc_id, ticker, chunk_text, chunk_index, embedding, metadata)
            VALUES (:id, :doc_id, :ticker, :chunk_text, :chunk_index, :embedding::vector, :metadata::jsonb)
            ON CONFLICT (id) DO UPDATE SET
                embedding = EXCLUDED.embedding,
                chunk_text = EXCLUDED.chunk_text,
                metadata = EXCLUDED.metadata
        """)
        await session.execute(sql, {
            "id": record.get("id", str(uuid.uuid4())),
            "doc_id": record.get("doc_id"),
            "ticker": record.get("ticker"),
            "chunk_text": record.get("text", ""),
            "chunk_index": record.get("chunk_index", 0),
            "embedding": str(record["embedding"]),
            "metadata": str(record.get("metadata", {})),
        })
        count += 1

    await session.commit()
    return {"upserted_count": count}
