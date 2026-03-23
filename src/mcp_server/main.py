"""
MCP Server — FastAPI application exposing all tools as endpoints.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.shared.logging import setup_logging

from src.mcp_server.tools.sec_filings_tool import router as sec_router
from src.mcp_server.tools.transcripts_tool import router as transcripts_router
from src.mcp_server.tools.news_tool import router as news_router
from src.mcp_server.tools.extractor_tool import router as extractor_router
from src.mcp_server.tools.embedder_tool import router as embedder_router
from src.mcp_server.tools.vector_tool import router as vector_router
from src.mcp_server.tools.database_tool import router as database_router
from src.mcp_server.tools.scheduler_tool import router as scheduler_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    yield


app = FastAPI(
    title="Phoenician Capital — Screening Engine MCP Server",
    version="0.1.0",
    lifespan=lifespan,
)

# ── Mount tool routers ───────────────────────────────────────────
app.include_router(sec_router, prefix="/tools/sec_filings", tags=["sec_filings"])
app.include_router(transcripts_router, prefix="/tools/transcripts", tags=["transcripts"])
app.include_router(news_router, prefix="/tools/news", tags=["news"])
app.include_router(extractor_router, prefix="/tools/extractor", tags=["extractor"])
app.include_router(embedder_router, prefix="/tools/embedder", tags=["embedder"])
app.include_router(vector_router, prefix="/tools/vector", tags=["vector"])
app.include_router(database_router, prefix="/tools/db", tags=["database"])
app.include_router(scheduler_router, prefix="/tools/scheduler", tags=["scheduler"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "phoenician-screening-engine"}
