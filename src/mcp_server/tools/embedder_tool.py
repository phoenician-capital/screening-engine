"""
MCP Tool: embedder.embed
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from src.shared.llm.embeddings import embed_texts
from src.mcp_server.middleware.error_handler import tool_endpoint

router = APIRouter()


class EmbedRequest(BaseModel):
    texts: list[str]
    model: str | None = None


@router.post("/embed")
@tool_endpoint
async def embed(req: EmbedRequest):
    embeddings = await embed_texts(req.texts, model=req.model)
    return {
        "embeddings": embeddings,
        "count": len(embeddings),
        "model": req.model or "default",
    }
