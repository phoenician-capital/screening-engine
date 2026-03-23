"""
MCP Tool: transcripts.fetch
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from src.ingestion.sources.transcripts import TranscriptClient
from src.mcp_server.middleware.error_handler import tool_endpoint

router = APIRouter()
client = TranscriptClient()


class FetchRequest(BaseModel):
    ticker: str
    quarter: str


@router.post("/fetch")
@tool_endpoint
async def fetch(req: FetchRequest):
    result = await client.fetch(ticker=req.ticker, quarter=req.quarter)
    return result
