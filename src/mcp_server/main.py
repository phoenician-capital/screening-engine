"""
MCP Server — FastAPI application exposing all tools as endpoints.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.shared.logging import setup_logging

from src.mcp_server.tools.sec_filings_tool import router as sec_router
from src.mcp_server.tools.transcripts_tool import router as transcripts_router
from src.mcp_server.tools.news_tool import router as news_router
from src.mcp_server.tools.extractor_tool import router as extractor_router
from src.mcp_server.tools.embedder_tool import router as embedder_router
from src.mcp_server.tools.vector_tool import router as vector_router
from src.mcp_server.tools.database_tool import router as database_router
from src.mcp_server.tools.scheduler_tool import router as scheduler_router
from src.api.router import router as api_router


async def _run_startup_migrations() -> None:
    """Run idempotent schema migrations on startup."""
    import logging
    _log = logging.getLogger(__name__)
    try:
        from src.config.settings import settings
        import psycopg2

        conn = psycopg2.connect(
            host=settings.db.host, port=settings.db.port,
            dbname=settings.db.name, user=settings.db.user,
            password=settings.db.password,
            sslmode="require" if settings.db.ssl else "prefer",
            connect_timeout=10,
        )
        conn.autocommit = True
        cur = conn.cursor()
        # Migration 013: rename 'metadata' → 'pattern_metadata' in learned pattern tables
        for table in ("selection_learned_patterns", "scoring_learned_patterns"):
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                f"WHERE table_name='{table}' AND column_name='metadata'"
            )
            if cur.fetchone():
                cur.execute(f"ALTER TABLE {table} RENAME COLUMN metadata TO pattern_metadata")
                _log.info("Migration 013: renamed metadata → pattern_metadata in %s", table)
        cur.close()
        conn.close()
    except Exception as exc:
        import logging as _l
        _l.getLogger(__name__).warning("Startup migration failed (non-fatal): %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    await _run_startup_migrations()
    yield


app = FastAPI(
    title="Phoenician Capital — Screening Engine MCP Server",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS — allow React dev server + production nginx ────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

# ── React frontend API ───────────────────────────────────────────
app.include_router(api_router)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "phoenician-screening-engine"}

# ── Serve React frontend static files as fallback ──────────────────
# Mount AFTER all routers so API routes take precedence
frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    # Serve /assets/* (hashed JS/CSS bundles)
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

    # Catch-all: serve index.html for React Router paths
    # Only triggers if no API route matched above
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        # If it looks like a static file request, try to serve it from dist
        candidate = frontend_dist / full_path
        if candidate.exists() and candidate.is_file():
            return FileResponse(str(candidate))
        # Otherwise serve index.html for React Router to handle
        return FileResponse(str(frontend_dist / "index.html"))
