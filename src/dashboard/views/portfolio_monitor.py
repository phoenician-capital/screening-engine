"""
Portfolio Monitor — tracks IR events, 8-K signals, insider clusters,
and portfolio analog recommendations for the 19 holdings.
"""
from __future__ import annotations

import asyncio
import concurrent.futures

import streamlit as st

from src.dashboard.components.styles import apply_theme, section_header, BG_CARD, BORDER, TEXT_PRIMARY, TEXT_MUTED, GREEN, AMBER, RED

GOLD = AMBER  # alias


def _run(coro, timeout: int = 120):
    def _target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="dashboard")
    return ex.submit(_target).result(timeout=timeout)


def _engine():
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from src.config.settings import settings
    engine = create_async_engine(settings.db.dsn, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, factory


async def _load_ir_events(lookback_days: int = 14) -> list[dict]:
    import datetime as dt
    from sqlalchemy import select
    from src.db.models.document import Document
    engine, factory = _engine()
    cutoff = dt.datetime.utcnow() - dt.timedelta(days=lookback_days)
    try:
        async with factory() as session:
            from sqlalchemy.ext.asyncio import AsyncSession
            result = await session.execute(
                select(Document)
                .where(Document.doc_type == "ir_event", Document.ingested_at >= cutoff)
                .order_by(Document.ingested_at.desc())
                .limit(50)
            )
            docs = result.scalars().all()
            return [
                {
                    "ticker": d.ticker,
                    "event_type": (d.meta or {}).get("event_type", "other"),
                    "title": d.title or "",
                    "url": d.source_url,
                    "event_date": (d.meta or {}).get("event_date"),
                    "company_name": (d.meta or {}).get("company_name", d.ticker),
                    "ingested_at": d.ingested_at.strftime("%Y-%m-%d %H:%M") if d.ingested_at else "",
                }
                for d in docs
            ]
    finally:
        await engine.dispose()


async def _load_8k_alerts(lookback_days: int = 7, min_relevance: float = 0.6) -> list[dict]:
    from src.db.repositories.document_repo import DocumentRepository
    engine, factory = _engine()
    try:
        async with factory() as session:
            repo = DocumentRepository(session)
            docs = await repo.get_by_meta_filter("8k_signal", min_relevance, lookback_days)
            return [
                {
                    "ticker": d.ticker,
                    "signal_type": (d.meta or {}).get("signal_type", "other"),
                    "sentiment": (d.meta or {}).get("sentiment", "neutral"),
                    "relevance_score": float((d.meta or {}).get("relevance_score", 0)),
                    "summary": (d.meta or {}).get("summary", ""),
                    "published_at": d.published_at.strftime("%Y-%m-%d") if d.published_at else "",
                }
                for d in docs
            ]
    finally:
        await engine.dispose()


async def _load_analog_recs(limit: int = 20) -> list[dict]:
    from src.db.repositories.recommendation_repo import RecommendationRepository
    from src.db.repositories.company_repo import CompanyRepository
    engine, factory = _engine()
    try:
        async with factory() as session:
            from sqlalchemy import select
            from src.db.models.recommendation import Recommendation
            result = await session.execute(
                select(Recommendation)
                .where(Recommendation.inspired_by.isnot(None))
                .order_by(Recommendation.generated_at.desc())
                .limit(limit)
            )
            recs = result.scalars().all()
            co_repo = CompanyRepository(session)
            rows = []
            for r in recs:
                co = await co_repo.get_by_ticker(r.ticker)
                rows.append({
                    "ticker": r.ticker,
                    "name": co.name if co else "",
                    "inspired_by": r.inspired_by,
                    "fit_score": float(r.fit_score),
                    "rank_score": float(r.rank_score),
                    "status": r.status,
                })
            return rows
    finally:
        await engine.dispose()


async def _run_ir_scan() -> dict:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from src.config.settings import settings
    from src.ingestion.workers.ir_monitor_worker import IRMonitorWorker
    engine = create_async_engine(settings.db.dsn, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            worker = IRMonitorWorker()
            events = await worker.run(session)
            await session.commit()
            return {"new_events": len(events), "events": events}
    finally:
        await engine.dispose()


_EVENT_TYPE_COLORS = {
    "earnings_date": ("#1d4ed8", "#eff6ff"),
    "agm": ("#7c3aed", "#f5f3ff"),
    "presentation": ("#059669", "#f0fdf4"),
    "annual_report": ("#d97706", "#fffbeb"),
    "interim_report": ("#d97706", "#fffbeb"),
    "press_release": ("#374151", "#f9fafb"),
    "webcast": ("#0891b2", "#f0f9ff"),
    "other": ("#9ca3af", "#f9fafb"),
}

_SIGNAL_COLORS = {
    "buyback_authorization": ("#059669", "#f0fdf4"),
    "ceo_change": ("#d97706", "#fffbeb"),
    "ma_announcement": ("#1d4ed8", "#eff6ff"),
    "restatement": ("#dc2626", "#fef2f2"),
    "earnings_release": ("#374151", "#f9fafb"),
    "debt_issuance": ("#9ca3af", "#f9fafb"),
    "other": ("#9ca3af", "#f9fafb"),
}


def _event_badge(event_type: str) -> str:
    c, bg = _EVENT_TYPE_COLORS.get(event_type, ("#9ca3af", "#f9fafb"))
    label = event_type.replace("_", " ").title()
    return (
        f'<span style="background:{bg};color:{c};border:1px solid {c}33;'
        f'padding:1px 8px;border-radius:3px;font-size:0.7rem;font-weight:600">{label}</span>'
    )


def _signal_badge(signal_type: str) -> str:
    c, bg = _SIGNAL_COLORS.get(signal_type, ("#9ca3af", "#f9fafb"))
    label = signal_type.replace("_", " ").title()
    return (
        f'<span style="background:{bg};color:{c};border:1px solid {c}33;'
        f'padding:1px 8px;border-radius:3px;font-size:0.7rem;font-weight:600">{label}</span>'
    )


def render() -> None:
    apply_theme()

    st.markdown(
        f'<h1 style="margin:0;color:{TEXT_PRIMARY}">Portfolio Monitor</h1>'
        f'<div style="color:{TEXT_MUTED};font-size:0.78rem;margin-top:2px">'
        f'Live intelligence feed for your 19 portfolio holdings.</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)

    # Manual scan button
    c1, c2 = st.columns([5, 1])
    with c2:
        if st.button("Scan IR Sites Now", key="btn_ir_scan", use_container_width=True):
            with st.spinner("Scanning 19 IR websites — this takes 3–5 minutes..."):
                try:
                    result = _run(_run_ir_scan(), timeout=600)
                    st.success(f"Scan complete — {result['new_events']} new events found.")
                    st.rerun()
                except Exception as e:
                    # Scan may have partially completed — reload to show whatever was stored
                    st.info("Scan ran — refreshing results. Some companies may have timed out.")
                    st.rerun()

    # ── Load data ────────────────────────────────────────────────────────────
    ir_events = _run(_load_ir_events(lookback_days=14))
    alerts_8k = _run(_load_8k_alerts(lookback_days=7, min_relevance=0.6))
    analogs = _run(_load_analog_recs(limit=20))

    # ── 1. IR Events ─────────────────────────────────────────────────────────
    st.markdown(section_header("Portfolio IR Events", "New events from company IR websites (last 14 days)"), unsafe_allow_html=True)
    st.markdown(f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:8px;padding:16px 20px">', unsafe_allow_html=True)

    if ir_events:
        hdr = (
            f'<div style="display:grid;grid-template-columns:70px 110px 1fr 120px 100px;'
            f'gap:8px;padding:0 0 8px;border-bottom:1px solid {BORDER};'
            f'font-size:0.65rem;font-weight:600;text-transform:uppercase;letter-spacing:0.07em;color:#9ca3af">'
            f'<div>Ticker</div><div>Type</div><div>Title</div><div>Date</div><div>Detected</div></div>'
        )
        rows = ""
        for e in ir_events:
            title = e["title"][:80]
            url = e.get("url")
            title_html = f'<a href="{url}" target="_blank" style="color:#1d4ed8;text-decoration:none">{title}</a>' if url else title
            rows += (
                f'<div style="display:grid;grid-template-columns:70px 110px 1fr 120px 100px;'
                f'gap:8px;padding:9px 0;border-bottom:1px solid #f3f4f6;align-items:center">'
                f'<div style="font-weight:700;font-size:0.84rem;color:{TEXT_PRIMARY}">{e["ticker"]}</div>'
                f'<div>{_event_badge(e["event_type"])}</div>'
                f'<div style="font-size:0.82rem;color:#374151">{title_html}</div>'
                f'<div style="font-size:0.78rem;color:#6b7280">{e.get("event_date","—")}</div>'
                f'<div style="font-size:0.72rem;color:#9ca3af">{e.get("ingested_at","")[:10]}</div>'
                f'</div>'
            )
        st.markdown(hdr + rows, unsafe_allow_html=True)
    else:
        st.markdown(
            f'<div style="font-size:0.83rem;color:{TEXT_MUTED};padding:8px 0">'
            f'No IR events in the last 14 days. Click "Scan IR Sites Now" to fetch latest events.</div>',
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)

    # ── 2. High-Signal 8-Ks ──────────────────────────────────────────────────
    st.markdown(section_header("SEC 8-K Signals", "High-relevance 8-K filings from the last 7 days"), unsafe_allow_html=True)
    st.markdown(f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:8px;padding:16px 20px">', unsafe_allow_html=True)

    if alerts_8k:
        for s in alerts_8k:
            sent_c = {"positive": GREEN, "negative": RED, "neutral": "#9ca3af"}.get(s["sentiment"], "#9ca3af")
            st.markdown(
                f'<div style="padding:10px 0;border-bottom:1px solid #f3f4f6">'
                f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;flex-wrap:wrap">'
                f'<span style="font-weight:700;font-size:0.88rem;color:{TEXT_PRIMARY}">{s["ticker"]}</span>'
                f'{_signal_badge(s["signal_type"])}'
                f'<span style="font-size:0.72rem;color:{sent_c}">{s["sentiment"]}</span>'
                f'<span style="font-size:0.72rem;color:#9ca3af;margin-left:auto">{s["published_at"]}</span>'
                f'</div>'
                f'<div style="font-size:0.82rem;color:#374151">{s["summary"]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            f'<div style="font-size:0.83rem;color:{TEXT_MUTED};padding:8px 0">'
            f'No high-signal 8-K filings detected in the last 7 days.</div>',
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)

    # ── 3. Portfolio Analogs ──────────────────────────────────────────────────
    st.markdown(section_header("Portfolio Analogs", "Candidates seeded by similarity to your holdings"), unsafe_allow_html=True)
    st.markdown(f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:8px;padding:16px 20px">', unsafe_allow_html=True)

    if analogs:
        for a in analogs:
            fit_c = "#059669" if a["fit_score"] >= 60 else ("#d97706" if a["fit_score"] >= 40 else "#dc2626")
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:12px;padding:8px 0;'
                f'border-bottom:1px solid #f3f4f6;flex-wrap:wrap">'
                f'<span style="font-weight:700;font-size:0.88rem;color:{TEXT_PRIMARY};width:60px">{a["ticker"]}</span>'
                f'<span style="font-size:0.82rem;color:#374151;flex:1">{a["name"]}</span>'
                f'<span style="background:#f9fafb;color:#6b7280;border:1px solid #e5e7eb;'
                f'padding:1px 8px;border-radius:3px;font-size:0.72rem">Inspired by {a["inspired_by"]}</span>'
                f'<span style="background:{fit_c}15;color:{fit_c};border:1px solid {fit_c}33;'
                f'padding:1px 8px;border-radius:3px;font-size:0.72rem;font-weight:600">'
                f'Fit {a["fit_score"]:.0f}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            f'<div style="font-size:0.83rem;color:{TEXT_MUTED};padding:8px 0">'
            f'No portfolio analogs yet. Run screening with "Portfolio Similarity" mode to find global analogs.</div>',
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)
