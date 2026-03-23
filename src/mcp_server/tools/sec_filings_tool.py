"""
MCP Tool: sec_filings.search / sec_filings.fetch
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from src.ingestion.sources.sec_edgar import SECEdgarClient
from src.mcp_server.middleware.error_handler import tool_endpoint

router = APIRouter()
client = SECEdgarClient()


class SearchRequest(BaseModel):
    query: str
    form_types: list[str] | None = None
    date_from: str | None = None
    date_to: str | None = None
    limit: int = 50


class FetchRequest(BaseModel):
    cik: str
    accession_no: str
    sections: list[str] | None = None


@router.post("/search")
@tool_endpoint
async def search(req: SearchRequest):
    results = await client.search_filings(
        query=req.query,
        form_types=req.form_types,
        date_from=req.date_from,
        date_to=req.date_to,
        limit=req.limit,
    )
    return {"results": results}


@router.post("/fetch")
@tool_endpoint
async def fetch(req: FetchRequest):
    result = await client.fetch_filing(
        cik=req.cik,
        accession_no=req.accession_no,
        sections=req.sections,
    )
    return result
