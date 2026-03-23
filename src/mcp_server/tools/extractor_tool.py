"""
MCP Tool: extractor.parse_financials / extractor.extract_claims
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from src.extraction.financial import FinancialParser
from src.extraction.claims import ClaimExtractor
from src.mcp_server.middleware.error_handler import tool_endpoint

router = APIRouter()
financial_parser = FinancialParser()
claim_extractor = ClaimExtractor()


class ParseFinancialsRequest(BaseModel):
    doc_id: str | None = None
    text: str


class ExtractClaimsRequest(BaseModel):
    doc_id: str | None = None
    text: str
    claim_types: list[str] | None = None


@router.post("/parse_financials")
@tool_endpoint
async def parse_financials(req: ParseFinancialsRequest):
    result = await financial_parser.parse(text=req.text, doc_id=req.doc_id)
    return result


@router.post("/extract_claims")
@tool_endpoint
async def extract_claims(req: ExtractClaimsRequest):
    claims = await claim_extractor.extract(
        text=req.text,
        claim_types=req.claim_types,
        doc_id=req.doc_id,
    )
    return {"claims": claims}
