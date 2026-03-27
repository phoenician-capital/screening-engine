"""
REST API router — serves the React frontend.
All endpoints are under /api/v1/
"""
from __future__ import annotations

import asyncio
import threading
import time
import uuid as _uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.config.settings import settings

router = APIRouter(prefix="/api/v1", tags=["api"])


# ── DB session factory ─────────────────────────────────────────────────────────
def _make_session():
    engine = create_async_engine(settings.db.dsn, echo=False, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, factory


async def _get_session():
    engine, factory = _make_session()
    try:
        async with factory() as session:
            yield session, engine
    finally:
        await engine.dispose()


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


# ══════════════════════════════════════════════════════════════════════════════
# RECOMMENDATIONS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/recommendations")
async def get_recommendations(limit: int = Query(500, le=1000)):
    """Top-ranked recommendations with company and metric data — portfolio holdings excluded."""
    engine, factory = _make_session()
    try:
        async with factory() as session:
            from src.db.repositories.recommendation_repo import RecommendationRepository
            from src.db.repositories.company_repo import CompanyRepository
            from src.db.repositories.metric_repo import MetricRepository
            from src.db.repositories.portfolio_repo import PortfolioRepository

            rec_repo  = RecommendationRepository(session)
            co_repo   = CompanyRepository(session)
            met_repo  = MetricRepository(session)
            port_repo = PortfolioRepository(session)

            portfolio_holdings = await port_repo.get_active()
            portfolio_tickers  = {h.ticker for h in portfolio_holdings}

            all_recs = await rec_repo.get_top_ranked(limit=limit)
            recs = [r for r in all_recs if r.ticker not in portfolio_tickers]
            rows = []
            for r in recs:
                co  = await co_repo.get_by_ticker(r.ticker)
                met = await met_repo.get_latest(r.ticker)

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
                            "evidence": ev[:280],
                        })

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
                    "portfolio_comparison": r.portfolio_comparison,
                })
            return rows
    finally:
        await engine.dispose()


class FeedbackBody(BaseModel):
    action: str          # research_now | watch | reject
    reason: str | None = None


@router.post("/recommendations/{ticker}/feedback")
async def submit_feedback(ticker: str, body: FeedbackBody):
    engine, factory = _make_session()
    try:
        async with factory() as session:
            from src.db.models.feedback import Feedback
            from src.db.repositories.recommendation_repo import RecommendationRepository

            repo = RecommendationRepository(session)
            rec  = await repo.get_latest_for_ticker(ticker)
            if not rec:
                raise HTTPException(404, f"No recommendation found for {ticker}")

            fb = Feedback(
                recommendation_id=rec.id,
                ticker=ticker,
                action=body.action,
                reject_reason=body.reason,
            )
            session.add(fb)

            status_map = {"research_now": "researching", "watch": "watched", "reject": "rejected"}
            if body.action in status_map:
                await repo.update_status(rec.id, status_map[body.action])

            await session.commit()
            return {"ok": True, "ticker": ticker, "action": body.action}
    finally:
        await engine.dispose()


# ══════════════════════════════════════════════════════════════════════════════
# SCREENING RUN
# ══════════════════════════════════════════════════════════════════════════════

def _run_sync(coro):
    """Run a coroutine in an isolated thread+event-loop."""
    import concurrent.futures
    result_holder = [None]
    error_holder  = [None]
    done = threading.Event()

    def _target():
        import concurrent.futures as cf
        executor = cf.ThreadPoolExecutor(max_workers=16, thread_name_prefix="api_screening")
        loop = asyncio.new_event_loop()
        loop.set_default_executor(executor)
        asyncio.set_event_loop(loop)
        try:
            result_holder[0] = loop.run_until_complete(coro)
        except Exception as e:
            error_holder[0] = e
        finally:
            try:
                pending = asyncio.all_tasks(loop)
                for t in pending: t.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.close()
            finally:
                executor.shutdown(wait=True, cancel_futures=True)
            done.set()

    threading.Thread(target=_target, daemon=True).start()
    done.wait()
    if error_holder[0]:
        raise error_holder[0]
    return result_holder[0]


class RunScreeningBody(BaseModel):
    max_companies: int = 20


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

    def _bg():
        try:
            t0 = _SCREENING_JOB["t0"]
            _SCREENING_JOB.update({"step": 1, "step_label": "Discovering companies"})

            async def _discover():
                from src.orchestration.discovery.universe_expander import UniverseExpander
                from sqlalchemy.pool import NullPool
                eng = create_async_engine(settings.db.dsn, echo=False, poolclass=NullPool)
                fac = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
                try:
                    async with fac() as sess:
                        exp = UniverseExpander(sess)
                        return await exp.expand_via_screener(max_companies=body.max_companies)
                finally:
                    await eng.dispose()

            tickers = _run_sync(_discover())
            _SCREENING_JOB.update({
                "tickers_found": len(tickers),
                "d1": f"{len(tickers)} candidates · {time.time()-t0:.0f}s",
                "step": 2, "step_label": "Scoring with AI Analyst Agent",
            })

            async def _score():
                from src.orchestration.pipelines.scoring_pipeline import ScoringPipeline
                eng = create_async_engine(settings.db.dsn, echo=False, poolclass=NullPool)
                fac = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
                try:
                    async with fac() as sess:
                        pipe = ScoringPipeline(sess)
                        return await pipe.run(tickers=tickers or None, run_type="manual")
                finally:
                    await eng.dispose()

            t2 = time.time()
            scored = _run_sync(_score())
            _SCREENING_JOB.update({
                "scored": len(scored) if isinstance(scored, list) else 0,
                "d2": f"{_SCREENING_JOB['scored']} companies · {time.time()-t2:.1f}s",
                "step": 3, "step_label": "Persisting results",
            })
            _SCREENING_JOB.update({
                "d3": "Rankings saved to database",
                "done": True, "running": False,
                "elapsed": round(time.time() - t0),
            })
        except Exception as e:
            _SCREENING_JOB.update({"error": str(e), "done": True, "running": False})

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

    def _bg():
        try:
            t0 = _SCREENING_JOB["t0"]

            async def _get_tickers():
                eng = create_async_engine(settings.db.dsn, echo=False, poolclass=NullPool)
                fac = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
                try:
                    async with fac() as sess:
                        from src.db.repositories.portfolio_repo import PortfolioRepository
                        repo = PortfolioRepository(sess)
                        holdings = await repo.get_active()
                        return [h.ticker for h in holdings]
                finally:
                    await eng.dispose()

            tickers = _run_sync(_get_tickers())

            # Ingest any portfolio tickers that have no metrics yet
            async def _ingest_missing():
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
                        return len(missing)
                finally:
                    await eng.dispose()

            n_ingested = _run_sync(_ingest_missing())
            _SCREENING_JOB.update({
                "tickers_found": len(tickers),
                "d1": f"{len(tickers)} holdings · {n_ingested} ingested",
                "step": 2, "step_label": "Scoring with AI Analyst Agent",
            })

            async def _score():
                from src.orchestration.pipelines.scoring_pipeline import ScoringPipeline
                eng = create_async_engine(settings.db.dsn, echo=False, poolclass=NullPool)
                fac = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
                try:
                    async with fac() as sess:
                        pipe = ScoringPipeline(sess)
                        return await pipe.run(tickers=tickers, run_type="portfolio_scan", bypass_data_check=True)
                finally:
                    await eng.dispose()

            t2 = time.time()
            scored = _run_sync(_score())
            _SCREENING_JOB.update({
                "scored": len(scored) if isinstance(scored, list) else 0,
                "d2": f"{_SCREENING_JOB['scored']} holdings scored · {time.time()-t2:.1f}s",
                "d3": "Rankings saved to database",
                "step": 3, "done": True, "running": False,
                "elapsed": round(time.time() - t0),
            })
        except Exception as e:
            _SCREENING_JOB.update({"error": str(e), "done": True, "running": False})

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
    engine, factory = _make_session()
    try:
        async with factory() as session:
            from src.db.repositories.portfolio_repo import PortfolioRepository
            from src.db.repositories import MetricRepository, RecommendationRepository
            repo     = PortfolioRepository(session)
            m_repo   = MetricRepository(session)
            rec_repo = RecommendationRepository(session)

            holdings = await repo.get_active()
            avg      = await repo.get_avg_metrics()

            rows = []
            for h in holdings:
                metrics = await m_repo.get_latest(h.ticker)
                rec     = await rec_repo.get_latest_for_ticker(h.ticker)

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

            return {"holdings": rows, "summary": avg}
    finally:
        await engine.dispose()


# ══════════════════════════════════════════════════════════════════════════════
# PORTFOLIO SIGNALS — IR events + news per holding
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/portfolio/scan-ir")
async def scan_ir():
    """Run IR monitor scan + news fetch across all active portfolio holdings."""
    engine, factory = _make_session()
    try:
        async with factory() as session:
            from src.db.repositories.portfolio_repo import PortfolioRepository
            from src.db.models.document import Document
            from src.db.repositories.document_repo import DocumentRepository
            from src.ingestion.workers.ir_monitor_worker import IRMonitorWorker
            from src.shared.llm.client_factory import complete
            from src.prompts import load_prompt
            from src.ingestion.sources.news.client import NewsClient
            import datetime as _dt

            # 1. IR events
            worker = IRMonitorWorker()
            new_events = await worker.run(session)

            # 2. News — fetch for all holdings and store, replacing stale articles
            portfolio_repo = PortfolioRepository(session)
            doc_repo = DocumentRepository(session)
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

                    # Delete existing news articles for this ticker (refresh)
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

            # Run news fetches concurrently (max 5 at a time)
            sem = asyncio.Semaphore(5)
            async def _guarded(h):
                async with sem:
                    return await _fetch_news(h)

            news_counts = await asyncio.gather(*[_guarded(h) for h in holdings], return_exceptions=True)
            total_news = sum(n for n in news_counts if isinstance(n, int))

            await session.commit()
            return {
                "ok": True,
                "new_ir_events": len(new_events),
                "news_articles": total_news,
            }
    finally:
        await engine.dispose()


@router.get("/portfolio/{ticker}/signals")
async def get_ticker_signals(ticker: str):
    """Return IR events + news for a single portfolio holding — both read from DB."""
    engine, factory = _make_session()
    try:
        async with factory() as session:
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
    finally:
        await engine.dispose()


# ══════════════════════════════════════════════════════════════════════════════
# INSIDER ACTIVITY
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/insiders")
async def get_insiders(days: int = Query(30, le=180)):
    engine, factory = _make_session()
    try:
        async with factory() as session:
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
    finally:
        await engine.dispose()


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
    engine, factory = _make_session()
    try:
        async with factory() as session:
            from src.db.repositories.recommendation_repo import RecommendationRepository
            from src.db.repositories.company_repo import CompanyRepository
            from src.db.repositories.feedback_repo import FeedbackRepository

            rec_repo  = RecommendationRepository(session)
            co_repo   = CompanyRepository(session)
            fb_repo   = FeedbackRepository(session)

            recs     = await rec_repo.get_top_ranked(limit=500)
            all_cos  = await co_repo.get_active()
            feedback = await fb_repo.get_recent_feedback(days=60)

            research = sum(1 for r in recs if r.status == "researching")
            watched  = sum(1 for r in recs if r.status == "watched")
            avg_fit  = round(sum(float(r.fit_score) for r in recs) / len(recs), 1) if recs else 0

            return {
                "total_universe":    len(all_cos),
                "ranked":            len(recs),
                "in_research":       research,
                "on_watchlist":      watched,
                "avg_fit_score":     avg_fit,
                "recent_decisions":  len(feedback),
            }
    finally:
        await engine.dispose()
