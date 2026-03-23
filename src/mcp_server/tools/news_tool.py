"""
MCP Tool: news.search / web.read
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from src.ingestion.sources.news import NewsClient
from src.mcp_server.middleware.error_handler import tool_endpoint

router = APIRouter()
client = NewsClient()


class SearchRequest(BaseModel):
    query: str
    tickers: list[str] | None = None
    date_from: str | None = None
    limit: int = 20


class ReadRequest(BaseModel):
    url: str


@router.post("/search")
@tool_endpoint
async def search(req: SearchRequest):
    articles = await client.search(
        query=req.query,
        tickers=req.tickers,
        date_from=req.date_from,
        limit=req.limit,
    )
    return {"articles": articles}


@router.post("/read")
@tool_endpoint
async def read(req: ReadRequest):
    result = await client.read_url(req.url)
    return result
