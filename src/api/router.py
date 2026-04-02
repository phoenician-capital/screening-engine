"""
REST API router — serves the React frontend.
All endpoints are under /api/v1/
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid as _uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["api"])


# ── DB session factory ─────────────────────────────────────────────────────────
# Single shared engine with connection pool — reused across all requests
_engine = create_async_engine(
    settings.db.dsn,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,        # verify connections before use
    pool_recycle=1800,         # recycle connections every 30 min
)
_session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


def _make_session():
    """Return the shared engine and session factory."""
    return _engine, _session_factory


async def _get_session():
    async with _session_factory() as session:
        yield session, _engine


# ── Helpers ────────────────────────────────────────────────────────────────────
def _pct(v) -> float | None:
    return round(float(v) * 100, 2) if v is not None else None

def _f(v) -> float | None:
    return round(float(v), 4) if v is not None else None

def _fmt_cap(v) -> str:
    if v is None: return "—"
    v = float(v)
    if v >= 1e9: return f"${v/1e9:.1f}B"
    if v >= 1e6: return f"${v/1e6:.0f}M"
    return f"${v:,.0f}"


# ── Global screening job state ─────────────────────────────────────────────────
_SCREENING_JOB: dict = {}
_SCREENING_LOCK = threading.Lock()

# ── Global IR scan job state ───────────────────────────────────────────────────
_IR_SCAN_JOB: dict = {}
_IR_SCAN_LOCK = threading.Lock()

# ── SSE event streaming ────────────────────────────────────────────────────────
import queue as _queue
_SCREENING_EVENTS: _queue.Queue = _queue.Queue()
# Async subscribers: each SSE connection gets its own asyncio.Queue
_SSE_SUBSCRIBERS: list = []
_SSE_LOCK = threading.Lock()


# ══════════════════════════════════════════════════════════════════════════════
# RECOMMENDATIONS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/recommendations")
async def get_recommendations(limit: int = Query(100, le=1000)):
    """Top-ranked recommendations with company and metric data — portfolio holdings excluded."""
    async with _session_factory() as session:
            from src.db.repositories.recommendation_repo import RecommendationRepository
            from src.db.repositories.company_repo import CompanyRepository
            from src.db.repositories.metric_repo import MetricRepository
            from src.db.repositories.portfolio_repo import PortfolioRepository

            rec_repo  = RecommendationRepository(session)
            co_repo   = CompanyRepository(session)
            met_repo  = MetricRepository(session)
            port_repo = PortfolioRepository(session)

            try:
                portfolio_holdings = await port_repo.get_active()
                portfolio_tickers  = {h.ticker for h in portfolio_holdings}
            except Exception:
                portfolio_tickers = set()

            # Fetch a larger batch to account for portfolio filtering
            try:
                all_recs = await rec_repo.get_top_ranked(limit=min(limit * 2, 1000))
            except Exception:
                all_recs = []

            recs = [r for r in all_recs if r.ticker not in portfolio_tickers][:limit]

            # Batch fetch companies and metrics for all recs at once (not one-by-one)
            tickers = [r.ticker for r in recs]
            try:
                companies = await co_repo.get_many_by_tickers(tickers) if hasattr(co_repo, 'get_many_by_tickers') else {}
                metrics = await met_repo.get_many_latest(tickers) if hasattr(met_repo, 'get_many_latest') else {}
            except Exception:
                companies, metrics = {}, {}

            rows = []
            for r in recs:
                co  = companies.get(r.ticker) if isinstance(companies, dict) else None
                met = metrics.get(r.ticker) if isinstance(metrics, dict) else None

                if not co:
                    try:
                        co = await co_repo.get_by_ticker(r.ticker)
                    except Exception:
                        co = None
                if not met:
                    try:
                        met = await met_repo.get_latest(r.ticker)
                    except Exception:
                        met = None

                # Parse analyst thesis from scoring_detail
                sd       = r.scoring_detail or {}
                criteria = sd.get("criteria", [])
                thesis_entry = next((c for c in criteria if c.get("name") == "analyst_thesis"), None)
                thesis, diligence, verdict, analyst_note = "", [], "", ""
                if thesis_entry:
                    ev = thesis_entry.get("evidence", "")
                    if "THESIS:" in ev:
                        thesis = ev.split("THESIS:")[1].split("|")[0].strip()
                    if "DILIGENCE:" in ev:
                        dil = ev.split("DILIGENCE:")[1]
                        if "VERDICT:" in dil:
                            dil = dil.split("VERDICT:")[0]
                        diligence = [q.strip() for q in dil.split("|") if q.strip()]
                    if "VERDICT:" in ev:
                        verdict = ev.split("VERDICT:")[1].strip()

                # Agent dimension scores
                agent_dims = {"business_quality", "unit_economics", "capital_returns",
                              "growth_quality", "balance_sheet", "phoenician_fit"}
                dimensions = []
                for c in criteria:
                    if c.get("name") in agent_dims and c.get("max_score", 0) > 0:
                        mx  = c["max_score"]
                        sc  = c["score"]
                        raw = round(sc / mx * 100) if mx else 0
                        ev  = c.get("evidence", "")
                        if ev.startswith("[Agent"):
                            ev = ev.split("] ", 1)[-1] if "] " in ev else ev
                        dimensions.append({
                            "name":     c["name"],
                            "label":    c["name"].replace("_", " ").title(),
                            "score":    raw,
                            "evidence": ev,  # full evidence — no truncation
                        })

                # Bear case + DCF from analyst_thesis evidence
                bear_case, dcf_result = [], ""
                if thesis_entry:
                    ev = thesis_entry.get("evidence", "")
                    if "BEAR CASE:" in ev:
                        bear_raw = ev.split("BEAR CASE:")[1]
                        if "DCF:" in bear_raw:
                            bear_raw = bear_raw.split("DCF:")[0]
                        elif "DILIGENCE:" in bear_raw:
                            bear_raw = bear_raw.split("DILIGENCE:")[0]
                        bear_case = [b.strip() for b in bear_raw.split("|") if b.strip()]
                    if "DCF:" in ev:
                        dcf_raw = ev.split("DCF:")[1]
                        if "DCF reasoning:" in dcf_raw:
                            dcf_raw = dcf_raw.split("DCF reasoning:")[0]
                        elif "DILIGENCE:" in dcf_raw:
                            dcf_raw = dcf_raw.split("DILIGENCE:")[0]
                        dcf_result = dcf_raw.strip().split("|")[0].strip()

                rows.append({
                    "id":           str(r.id),
                    "rank":         r.rank,
                    "ticker":       r.ticker,
                    "name":         co.name         if co else "",
                    "exchange":          co.exchange           if co else "",
                    "country":           co.country            if co else "",
                    "sector":            co.gics_sector        if co else "",
                    "founder_led":       co.is_founder_led     if co else False,
                    "discovery_source":  getattr(co, "discovery_source", None) if co else None,
                    "market_tier":       getattr(co, "market_tier", 1)          if co else 1,
                    "market_cap":   _f(co.market_cap_usd) if co and co.market_cap_usd else None,
                    "market_cap_fmt": _fmt_cap(co.market_cap_usd if co else None),
                    "fit_score":    _f(r.fit_score),
                    "risk_score":   _f(r.risk_score),
                    "rank_score":   _f(r.rank_score),
                    "status":       r.status,
                    "inspired_by":  r.inspired_by,
                    # Financials
                    "gross_margin":       _pct(met.gross_margin)        if met else None,
                    "roic":               _pct(met.roic)                if met else None,
                    "fcf_yield":          _pct(met.fcf_yield)           if met else None,
                    "revenue_growth_yoy": _pct(met.revenue_growth_yoy)  if met else None,
                    "net_debt_ebitda":    _f(met.net_debt_ebitda)       if met else None,
                    "ev_ebit":            _f(met.ev_ebit)               if met else None,
                    "analyst_count":      met.analyst_count             if met else None,
                    # AI outputs
                    "memo_text":         r.memo_text,
                    "thesis":            thesis,
                    "diligence":         diligence,
                    "verdict":           verdict,
                    "dimensions":        dimensions,
                    "bear_case":         bear_case,
                    "dcf_result":        dcf_result,
                    "portfolio_comparison": r.portfolio_comparison,
                })
            return rows


class FeedbackBody(BaseModel):
    action: str          # research_now | watch | reject
    reason: str | None = None
    notes: str | None = None  # NEW: Rich analyst notes for learning

    @field_validator('notes')
    @classmethod
    def _truncate_notes(cls, v):
        """Soft cap at 2000 chars to prevent absurdly large notes."""
        return v[:2000] if v else v


@router.post("/recommendations/{ticker}/feedback")
async def submit_feedback(ticker: str, body: FeedbackBody):
    async with _session_factory() as session:
            from src.db.models.feedback import Feedback
            from src.db.repositories.recommendation_repo import RecommendationRepository
            from src.orchestration.pipelines.bidirectional_feedback_pipeline import (
                BidirectionalFeedbackPipeline,
            )

            repo = RecommendationRepository(session)
            rec  = await repo.get_latest_for_ticker(ticker)
            if not rec:
                raise HTTPException(404, f"No recommendation found for {ticker}")

            fb = Feedback(
                recommendation_id=rec.id,
                ticker=ticker,
                action=body.action,
                reject_reason=body.reason,
                notes=body.notes,  # NEW: Store analyst notes
            )
            session.add(fb)

            status_map = {"research_now": "researching", "watch": "watched", "reject": "rejected"}
            if body.action in status_map:
                await repo.update_status(rec.id, status_map[body.action])

            await session.flush()

            # NEW: Trigger bidirectional learning pipeline
            try:
                pipeline = BidirectionalFeedbackPipeline(session)
                await pipeline.process_feedback(fb)
                logger.info(f"Bidirectional feedback learning triggered for {ticker}")
            except Exception as e:
                logger.error(f"Feedback learning failed for {ticker}: {e}")
                # Don't block feedback submission on learning failure

            await session.commit()
            return {"ok": True, "ticker": ticker, "action": body.action}


# ══════════════════════════════════════════════════════════════════════════════
# SCREENING RUN
# ══════════════════════════════════════════════════════════════════════════════

class RunScreeningBody(BaseModel):
    max_companies: int = 20


@router.get("/screening/events")
async def screening_events():
    """Server-Sent Events stream for real-time screening progress."""
    import json as _json
    loop = asyncio.get_event_loop()
    q: asyncio.Queue = asyncio.Queue()
    with _SSE_LOCK:
        _SSE_SUBSCRIBERS.append((loop, q))

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=20.0)
                    yield f"data: {_json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            with _SSE_LOCK:
                try:
                    _SSE_SUBSCRIBERS.remove((loop, q))
                except ValueError:
                    pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


def _emit_event(event_type: str, data: dict | None = None, **kwargs):
    """Emit an event to SSE stream."""
    import json as _json
    payload = {
        "type": event_type,
        "timestamp": time.time(),
        **(data or {}),
        **kwargs,
    }
    try:
        _SCREENING_EVENTS.put_nowait(payload)
    except _queue.Full:
        pass  # Drop event if queue is full
    # Push to all async SSE subscribers (non-blocking, thread-safe)
    with _SSE_LOCK:
        dead = []
        for loop, q in _SSE_SUBSCRIBERS:
            try:
                loop.call_soon_threadsafe(q.put_nowait, payload)
            except Exception:
                dead.append((loop, q))
        for d in dead:
            _SSE_SUBSCRIBERS.remove(d)


@router.post("/screening/run")
async def start_screening(body: RunScreeningBody):
    """Kick off a background screening run."""
    with _SCREENING_LOCK:
        if _SCREENING_JOB.get("running"):
            return {"ok": False, "message": "A run is already in progress"}
        _SCREENING_JOB.clear()
        _SCREENING_JOB.update({
            "running": True, "done": False, "error": None,
            "step": 1, "step_label": "Discovering companies",
            "tickers_found": 0, "scored": 0, "top_n": [],
            "d1": "", "d2": "", "d3": "", "d4": "",
            "t0": time.time(), "elapsed": 0,
        })

    async def _bg_async():
        try:
            t0 = _SCREENING_JOB["t0"]
            _SCREENING_JOB.update({"step": 1, "step_label": "Discovering companies"})
            _emit_event("screening_started", step=1, step_label="Discovering companies", timestamp=time.time())

            # Discover companies
            from src.orchestration.discovery.universe_expander import UniverseExpander
            from sqlalchemy.pool import NullPool
            from sqlalchemy import text
            eng = create_async_engine(settings.db.dsn, echo=False, poolclass=NullPool)
            fac = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
            try:
                async with fac() as sess:
                    try:
                        exp = UniverseExpander(sess)
                        tickers = await exp.expand_via_screener(max_companies=body.max_companies)
                    except Exception as e:
                        logger.warning(f"Discovery failed ({e}), falling back to portfolio companies")
                        await sess.rollback()
                        result = await sess.execute(text("SELECT ticker FROM portfolio_holdings WHERE is_active = true LIMIT :limit"), {"limit": body.max_companies})
                        tickers = [row[0] for row in result.fetchall()]
            finally:
                await eng.dispose()

            _SCREENING_JOB.update({
                "tickers_found": len(tickers),
                "d1": f"{len(tickers)} candidates · {time.time()-t0:.0f}s",
                "step": 2, "step_label": "Screening Selection Team",
            })
            _emit_event("discovery_complete", tickers_found=len(tickers), elapsed=time.time()-t0)

            # Score companies with progress callback
            from src.orchestration.pipelines.scoring_pipeline import ScoringPipeline
            from src.shared.scoring_state import ScreeningProgress

            _STEP_LABELS = {
                "init":      "Initialising",
                "selection": "Selection Team Pre-Filtering",
                "scoring":   "Scoring with AI Analyst",
                "ranking":   "Ranking Results",
                "complete":  "Complete",
            }

            def _on_progress(progress: ScreeningProgress):
                """Update job state and emit SSE event for progress updates."""
                update: dict = {
                    "step": progress.step,
                    "current_ticker": progress.current_ticker,
                    "current_agent": progress.current_agent,
                    "companies_scored": progress.companies_scored,
                    "failed_companies": progress.failed_companies,
                }
                # Keep step_label in sync
                if progress.step in _STEP_LABELS:
                    update["step_label"] = _STEP_LABELS[progress.step]
                _SCREENING_JOB.update(update)
                _emit_event("screening_progress", **progress.dict())

            eng = create_async_engine(settings.db.dsn, echo=False, poolclass=NullPool)
            fac = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
            try:
                async with fac() as sess:
                    pipe = ScoringPipeline(sess)
                    t2 = time.time()
                    scored = await pipe.run(
                        tickers=tickers or None,
                        run_type="manual",
                        on_progress=_on_progress,
                    )
            finally:
                await eng.dispose()

            _SCREENING_JOB.update({
                "scored": len(scored) if isinstance(scored, list) else 0,
                "d2": f"{_SCREENING_JOB['scored']} companies · {time.time()-t2:.1f}s",
                "step": "complete", "step_label": "Complete",
            })
            _emit_event("screening_complete", scored=len(scored) if isinstance(scored, list) else 0, elapsed=time.time()-t2)
            _SCREENING_JOB.update({
                "d3": "Rankings saved to database",
                "done": True, "running": False,
                "elapsed": round(time.time() - t0),
            })
            _emit_event("screening_done", done=True, elapsed=round(time.time()-t0))
        except Exception as e:
            logger.exception(f"Background screening error: {e}")
            _SCREENING_JOB.update({"error": str(e), "done": True, "running": False})
            _emit_event("screening_error", error=str(e))

    def _bg():
        """Wrapper to run async code in background thread."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_bg_async())
        finally:
            # Gracefully cancel remaining tasks before closing
            try:
                pending = asyncio.all_tasks(loop)
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

    threading.Thread(target=_bg, daemon=False, name="api_screening_bg").start()
    return {"ok": True, "message": "Screening started"}


@router.post("/screening/run-portfolio")
async def start_portfolio_scan():
    """Score only the active portfolio holdings (skip universe discovery)."""
    with _SCREENING_LOCK:
        if _SCREENING_JOB.get("running"):
            return {"ok": False, "message": "A run is already in progress"}
        _SCREENING_JOB.clear()
        _SCREENING_JOB.update({
            "running": True, "done": False, "error": None,
            "step": 1, "step_label": "Fetching portfolio data",
            "tickers_found": 0, "scored": 0, "top_n": [],
            "d1": "", "d2": "", "d3": "", "d4": "",
            "t0": time.time(), "elapsed": 0,
        })

    async def _bg_async():
        try:
            t0 = _SCREENING_JOB["t0"]

            # Get portfolio tickers
            eng = create_async_engine(settings.db.dsn, echo=False, poolclass=NullPool)
            fac = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
            try:
                async with fac() as sess:
                    from src.db.repositories.portfolio_repo import PortfolioRepository
                    repo = PortfolioRepository(sess)
                    holdings = await repo.get_active()
                    tickers = [h.ticker for h in holdings]
            finally:
                await eng.dispose()

            # Ingest missing metrics
            eng = create_async_engine(settings.db.dsn, echo=False, poolclass=NullPool)
            fac = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
            try:
                async with fac() as sess:
                    from src.db.repositories import MetricRepository
                    from src.orchestration.discovery.universe_expander import UniverseExpander
                    metric_repo = MetricRepository(sess)
                    expander = UniverseExpander(sess)
                    missing = []
                    for t in tickers:
                        m = await metric_repo.get_latest(t)
                        if not m:
                            missing.append(t)
                    if missing:
                        _SCREENING_JOB["d1"] = f"Ingesting {len(missing)} new holdings…"
                        await expander.ingest_new_tickers(missing)
                    n_ingested = len(missing)
            finally:
                await eng.dispose()

            _SCREENING_JOB.update({
                "tickers_found": len(tickers),
                "d1": f"{len(tickers)} holdings · {n_ingested} ingested",
                "step": 2, "step_label": "Scoring with AI Analyst Agent",
            })

            # Score
            from src.orchestration.pipelines.scoring_pipeline import ScoringPipeline
            eng = create_async_engine(settings.db.dsn, echo=False, poolclass=NullPool)
            fac = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
            try:
                async with fac() as sess:
                    pipe = ScoringPipeline(sess)
                    t2 = time.time()
                    scored = await pipe.run(tickers=tickers, run_type="portfolio_scan", bypass_data_check=True)
            finally:
                await eng.dispose()

            _SCREENING_JOB.update({
                "scored": len(scored) if isinstance(scored, list) else 0,
                "d2": f"{_SCREENING_JOB['scored']} holdings scored · {time.time()-t2:.1f}s",
                "d3": "Rankings saved to database",
                "step": 3, "done": True, "running": False,
                "elapsed": round(time.time() - t0),
            })
        except Exception as e:
            logger.exception(f"Background portfolio scan error: {e}")
            _SCREENING_JOB.update({"error": str(e), "done": True, "running": False})

    def _bg():
        """Wrapper to run async code in background thread."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_bg_async())
        finally:
            loop.close()

    threading.Thread(target=_bg, daemon=False, name="api_portfolio_scan_bg").start()
    return {"ok": True, "message": "Portfolio scan started"}


@router.get("/screening/status")
async def screening_status():
    """Poll the current screening run status."""
    job = dict(_SCREENING_JOB)
    if job.get("t0") and not job.get("done"):
        job["elapsed"] = round(time.time() - job["t0"])
    return job


# ══════════════════════════════════════════════════════════════════════════════
# PORTFOLIO
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/portfolio")
async def get_portfolio():
    async with _session_factory() as session:
            try:
                from src.db.repositories.portfolio_repo import PortfolioRepository
                from src.db.repositories import MetricRepository, RecommendationRepository
                repo     = PortfolioRepository(session)
                m_repo   = MetricRepository(session)
                rec_repo = RecommendationRepository(session)

                holdings = await repo.get_active()
                avg      = await repo.get_avg_metrics()

                if not holdings:
                    logger.info("No active portfolio holdings found")
                    return {"holdings": [], "summary": avg or {}}

                # Batch fetch metrics and recommendations instead of N+2 queries
                tickers = [h.ticker for h in holdings]
                try:
                    metrics_dict = await m_repo.get_many_latest(tickers) if hasattr(m_repo, 'get_many_latest') else {}
                    recs_dict = await rec_repo.get_many_latest_for_tickers(tickers) if hasattr(rec_repo, 'get_many_latest_for_tickers') else {}
                except Exception as e:
                    logger.warning(f"Batch fetch failed: {e}, falling back to individual queries")
                    metrics_dict, recs_dict = {}, {}

                rows = []
                for h in holdings:
                    try:
                        # Use batch results if available, otherwise fall back to single queries
                        metrics = metrics_dict.get(h.ticker) if metrics_dict else None
                        if not metrics:
                            metrics = await m_repo.get_latest(h.ticker)

                        rec = recs_dict.get(h.ticker) if recs_dict else None
                        if not rec:
                            rec = await rec_repo.get_latest_for_ticker(h.ticker)

                        # Parse thesis / verdict / diligence from analyst_thesis criterion
                        thesis = verdict = None
                        diligence = []
                        if rec and rec.scoring_detail:
                            criteria = rec.scoring_detail.get("criteria", [])
                            for c in criteria:
                                if c.get("name") == "analyst_thesis":
                                    ev = c.get("evidence", "")
                                    if "THESIS:" in ev:
                                        parts = ev.split("|")
                                        for p in parts:
                                            p = p.strip()
                                            if p.startswith("THESIS:"):
                                                thesis = p[7:].strip()
                                            elif p.startswith("DILIGENCE:"):
                                                diligence = [q.strip() for q in p[10:].split("|") if q.strip()]
                                            elif p.startswith("VERDICT:"):
                                                verdict = p[8:].strip()
                                    break

                        rows.append({
                            "ticker":        h.ticker,
                            "name":          h.name,
                            "sector":        h.sector or (metrics and getattr(metrics, "gics_sector", None)),
                            "date_added":    h.date_added.isoformat() if h.date_added else None,
                            # Scored signals
                            "fit_score":     _f(rec.fit_score)   if rec else None,
                            "risk_score":    _f(rec.risk_score)  if rec else None,
                            "rank_score":    _f(rec.rank_score)  if rec else None,
                            "rank":          rec.rank             if rec else None,
                            "verdict":       verdict,
                            "thesis":        thesis,
                            "diligence":     diligence,
                            # Live metrics
                            "gross_margin":      _pct(metrics.gross_margin)         if metrics and metrics.gross_margin      else None,
                            "roic":              _pct(metrics.roic)                  if metrics and metrics.roic              else None,
                            "revenue_growth":    _pct(metrics.revenue_growth_yoy)   if metrics and metrics.revenue_growth_yoy else None,
                            "fcf_yield":         _pct(metrics.fcf_yield)             if metrics and metrics.fcf_yield          else None,
                            "net_debt_ebitda":   _f(metrics.net_debt_ebitda)         if metrics and metrics.net_debt_ebitda   else None,
                            "market_cap":        _f(metrics.market_cap_usd)          if metrics and metrics.market_cap_usd    else None,
                            "ev_ebit":           _f(metrics.ev_ebit)                  if metrics and metrics.ev_ebit           else None,
                        })
                    except Exception as e:
                        logger.error(f"Error processing holding {h.ticker}: {e}")
                        # Skip this holding and continue with others
                        continue

                logger.info(f"Returned {len(rows)} portfolio holdings")
                return {"holdings": rows, "summary": avg or {}}
            except Exception as e:
                logger.error(f"Portfolio endpoint error: {e}", exc_info=True)
                raise HTTPException(500, f"Failed to fetch portfolio: {str(e)}")


# ══════════════════════════════════════════════════════════════════════════════
# PORTFOLIO SIGNALS — IR events + news per holding
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/portfolio/scan-ir")
async def scan_ir():
    """Start an IR monitor scan + news fetch in the background. Returns immediately."""
    with _IR_SCAN_LOCK:
        if _IR_SCAN_JOB.get("running"):
            return {"ok": False, "message": "A scan is already in progress"}
        _IR_SCAN_JOB.clear()
        _IR_SCAN_JOB.update({
            "running": True, "done": False, "error": None,
            "step": "Scanning IR calendars…",
            "new_ir_events": 0, "news_articles": 0,
            "t0": time.time(),
        })

    async def _bg_async():
        try:
            from src.db.repositories.portfolio_repo import PortfolioRepository
            from src.db.models.document import Document
            from src.db.repositories.document_repo import DocumentRepository
            from src.ingestion.workers.ir_monitor_worker import IRMonitorWorker
            from src.shared.llm.client_factory import complete
            from src.prompts import load_prompt
            from src.ingestion.sources.news.client import NewsClient

            eng = create_async_engine(settings.db.dsn, echo=False, poolclass=NullPool)
            fac = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
            try:
                async with fac() as session:
                    # 1. IR events
                    worker = IRMonitorWorker()
                    new_events = await worker.run(session)
                    _IR_SCAN_JOB.update({
                        "new_ir_events": len(new_events),
                        "step": "Fetching news…",
                    })

                    # 2. News
                    portfolio_repo = PortfolioRepository(session)
                    holdings = await portfolio_repo.get_active()
                    news_client = NewsClient()
                    system_prompt = load_prompt("ingestion/news_search_system.j2")

                    async def _fetch_news(holding):
                        try:
                            prompt = load_prompt(
                                "ingestion/news_search.j2",
                                query=f"{holding.ticker} {holding.name or ''} investor news earnings",
                                tickers=[holding.ticker],
                                date_from=None,
                                limit=5,
                            )
                            raw = await complete(prompt, model="sonar", system=system_prompt,
                                                max_tokens=2000, temperature=0.1)
                            articles = news_client._parse_articles(raw)[:5]

                            from sqlalchemy import delete as _del
                            from src.db.models.document import Document as _Doc
                            await session.execute(
                                _del(_Doc).where(
                                    _Doc.ticker == holding.ticker,
                                    _Doc.doc_type == "news_article",
                                )
                            )
                            for article in articles:
                                if not article.get("title"):
                                    continue
                                doc = Document(
                                    ticker=holding.ticker,
                                    doc_type="news_article",
                                    source="perplexity",
                                    source_url=article.get("url"),
                                    title=article["title"][:500],
                                    raw_text=article.get("snippet", "")[:1000],
                                    published_at=None,
                                    meta={"published_at": article.get("published_at")},
                                )
                                session.add(doc)
                            await session.flush()
                            return len(articles)
                        except Exception as e:
                            logger.warning("News fetch failed for %s: %s", holding.ticker, e)
                            return 0

                    sem = asyncio.Semaphore(5)
                    async def _guarded(h):
                        async with sem:
                            return await _fetch_news(h)

                    news_counts = await asyncio.gather(*[_guarded(h) for h in holdings], return_exceptions=True)
                    total_news = sum(n for n in news_counts if isinstance(n, int))
                    await session.commit()

            finally:
                await eng.dispose()

            _IR_SCAN_JOB.update({
                "running": False, "done": True,
                "news_articles": total_news,
                "step": "Done",
                "elapsed": round(time.time() - _IR_SCAN_JOB["t0"]),
            })
        except Exception as e:
            logger.exception("Background IR scan error: %s", e)
            _IR_SCAN_JOB.update({"error": str(e), "done": True, "running": False})

    def _bg():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_bg_async())
        finally:
            loop.close()

    threading.Thread(target=_bg, daemon=False, name="api_ir_scan_bg").start()
    return {"ok": True, "message": "IR scan started"}


@router.get("/portfolio/scan-ir/status")
async def scan_ir_status():
    """Poll the current IR scan status."""
    job = dict(_IR_SCAN_JOB)
    if job.get("t0") and not job.get("done"):
        job["elapsed"] = round(time.time() - job["t0"])
    return job


@router.get("/portfolio/{ticker}/signals")
async def get_ticker_signals(ticker: str):
    """Return IR events + news for a single portfolio holding — both read from DB."""
    async with _session_factory() as session:
            from src.db.repositories.document_repo import DocumentRepository
            doc_repo = DocumentRepository(session)

            ir_docs   = await doc_repo.get_by_ticker(ticker, doc_type="ir_event",    limit=10)
            news_docs = await doc_repo.get_by_ticker(ticker, doc_type="news_article", limit=5)

            ir_events = [
                {
                    "title":      d.title,
                    "url":        d.source_url,
                    "event_type": d.meta.get("event_type") if d.meta else None,
                    "event_date": d.published_at.date().isoformat() if d.published_at else None,
                    "snippet":    d.raw_text,
                }
                for d in ir_docs
            ]
            news = [
                {
                    "title":        d.title,
                    "url":          d.source_url,
                    "published_at": d.meta.get("published_at") if d.meta else None,
                    "snippet":      d.raw_text,
                }
                for d in news_docs
            ]

            return {"ticker": ticker, "ir_events": ir_events, "news": news}


# ══════════════════════════════════════════════════════════════════════════════
# INSIDER ACTIVITY
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/insiders")
async def get_insiders(days: int = Query(30, le=180)):
    async with _session_factory() as session:
            from src.db.repositories.insider_repo import InsiderRepository
            repo    = InsiderRepository(session)
            cluster = await repo.get_cluster_buys(days=days)
            recent  = await repo.get_recent(days=days)
            def _ser(p):
                return {
                    "ticker":        p.ticker,
                    "insider_name":  p.insider_name,
                    "insider_title": p.insider_title,
                    "shares":        p.shares,
                    "price":         _f(p.price_per_share),
                    "total_value":   _f(p.total_value),
                    "transaction_date": p.transaction_date.isoformat() if p.transaction_date else None,
                    "is_cluster":    getattr(p, "is_cluster", False),
                    "near_52wk_low": getattr(p, "near_52wk_low", False),
                }
            return {
                "cluster_buys": [_ser(p) for p in cluster],
                "recent":       [_ser(p) for p in recent],
            }


# ══════════════════════════════════════════════════════════════════════════════
# SETTINGS — hard filters + scoring weights
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/settings")
async def get_settings():
    from src.config.scoring_weights import load_scoring_weights
    return load_scoring_weights()


class SaveSettingsBody(BaseModel):
    data: dict


@router.post("/settings")
async def save_settings(body: SaveSettingsBody):
    import yaml
    from pathlib import Path
    path = Path(settings.scoring.weights_file)
    with open(path, "w") as f:
        yaml.dump(body.data, f, default_flow_style=False, sort_keys=False)
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════════
# STATS — dashboard summary numbers
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/stats")
async def get_stats():
    async with _session_factory() as session:
            from src.db.repositories.recommendation_repo import RecommendationRepository
            from src.db.repositories.feedback_repo import FeedbackRepository

            rec_repo  = RecommendationRepository(session)
            fb_repo   = FeedbackRepository(session)

            try:
                recs     = await rec_repo.get_top_ranked(limit=500)
                feedback = await fb_repo.get_recent_feedback(days=60)

                research = sum(1 for r in recs if r.status == "researching")
                watched  = sum(1 for r in recs if r.status == "watched")
                avg_fit  = round(sum(float(r.fit_score) for r in recs) / len(recs), 1) if recs else 0

                return {
                    "total_universe":    len(recs),
                    "ranked":            len(recs),
                    "in_research":       research,
                    "on_watchlist":      watched,
                    "avg_fit_score":     avg_fit,
                    "recent_decisions":  len(feedback),
                }
            except Exception:
                # Empty database or schema issue — return defaults
                return {
                    "total_universe":    0,
                    "ranked":            0,
                    "in_research":       0,
                    "on_watchlist":      0,
                    "avg_fit_score":     0,
                    "recent_decisions":  0,
                }


@router.post("/screening/reset-db")
async def reset_screening_db():
    """Wipe all screening data (companies, metrics, recommendations, documents).
    Safe to call between runs. Does not affect portfolio_holdings or feedback."""
    import psycopg2
    from src.config.settings import settings as _s
    try:
        conn = psycopg2.connect(
            host=_s.db.host, port=_s.db.port,
            dbname=_s.db.name, user=_s.db.user,
            password=_s.db.password,
            sslmode="require" if _s.db.ssl else "prefer",
            connect_timeout=10,
        )
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SET session_replication_role = replica")
        cur.execute("TRUNCATE TABLE recommendations, metrics, scoring_runs, documents, insider_purchases CASCADE")
        cur.execute("DELETE FROM companies")
        cur.execute("SET session_replication_role = DEFAULT")
        cur.close()
        conn.close()
        return {"ok": True, "message": "Screening data wiped — ready for fresh run"}
    except Exception as e:
        return {"ok": False, "message": str(e)}
