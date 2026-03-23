"""
Pipeline Runner page — manually trigger ingestion, scoring, memo generation,
and universe discovery. 2×2 card grid with status feedback.
"""

from __future__ import annotations

import asyncio

import streamlit as st
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config.settings import settings
from src.dashboard.components.styles import (
    apply_theme,
    section_header,
    BG_CARD, BG_CARD_ALT, BORDER, GOLD, GREEN, RED, AMBER, TEXT_PRIMARY, TEXT_MUTED, TEXT_DIM,
)


def _make_session():
    engine = create_async_engine(settings.db.dsn, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, factory


def _status_badge(state: str) -> str:
    colors = {"Idle": TEXT_DIM, "Running": AMBER, "Done": GREEN, "Error": RED}
    color = colors.get(state, TEXT_DIM)
    return (
        f'<span style="background:{color}18;color:{color};border:1px solid {color}44;'
        f'padding:2px 9px;border-radius:8px;font-size:0.72rem;font-weight:600">{state}</span>'
    )


def _card_header(title: str, icon: str, state: str = "Idle") -> str:
    return (
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">'
        f'<div style="color:{TEXT_PRIMARY};font-size:0.95rem;font-weight:700">{icon} {title}</div>'
        f'{_status_badge(state)}'
        f'</div>'
    )


def render() -> None:
    apply_theme()

    st.markdown(
        f'<h1 style="margin:0;color:{TEXT_PRIMARY}">Pipeline Runner</h1>'
        f'<div style="color:{TEXT_MUTED};font-size:0.78rem;margin-top:2px">'
        f'Manually trigger any pipeline step. The scheduler runs these automatically.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<div style="height:16px"></div>', unsafe_allow_html=True)

    # Session state for results
    for k in ["ingest_result", "score_result", "memo_result", "discover_result"]:
        if k not in st.session_state:
            st.session_state[k] = None

    # ── Row 1: Ingest + Score ─────────────────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        ingest_state = "Done" if st.session_state.ingest_result else "Idle"
        st.markdown(
            f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-top:3px solid {GOLD};'
            f'border-radius:10px;padding:20px 22px;min-height:220px">',
            unsafe_allow_html=True,
        )
        st.markdown(card_html := _card_header("Ingest Data", "📥", ingest_state), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        ticker_input = st.text_input(
            "Tickers to ingest (comma-separated)",
            placeholder="e.g. AAPL, MSFT, NVDA",
            key="ingest_tickers",
        )
        if st.button("Run Ingestion", key="btn_ingest", use_container_width=True):
            if ticker_input.strip():
                tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]
                with st.spinner(f"Ingesting {len(tickers)} ticker(s)…"):
                    result = asyncio.run(_run_ingestion(tickers))
                st.session_state.ingest_result = result
            else:
                st.warning("Enter at least one ticker.")

        if st.session_state.ingest_result:
            st.success(f"Ingestion complete: {st.session_state.ingest_result}")

    with col2:
        score_state = "Done" if st.session_state.score_result else "Idle"
        st.markdown(
            f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-top:3px solid {GOLD};'
            f'border-radius:10px;padding:20px 22px;min-height:220px">',
            unsafe_allow_html=True,
        )
        st.markdown(_card_header("Run Scoring", "⚡", score_state), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        sc1, sc2 = st.columns(2)
        with sc1:
            run_type = st.selectbox("Run type", ["manual", "daily", "weekly"], key="score_run_type")
        with sc2:
            score_tickers = st.text_input(
                "Specific tickers (blank = all)",
                placeholder="blank = full universe",
                key="score_tickers_input",
            )

        if st.button("Run Scoring Pipeline", key="btn_score", use_container_width=True):
            tickers = [t.strip().upper() for t in score_tickers.split(",") if t.strip()] if score_tickers else None
            with st.spinner("Running scoring pipeline…"):
                result = asyncio.run(_run_scoring(tickers, run_type))
            st.session_state.score_result = result

        if st.session_state.score_result:
            scored = st.session_state.score_result
            st.success(f"Scored {len(scored) if isinstance(scored, list) else scored} companies")
            if isinstance(scored, list) and scored:
                import pandas as pd
                df = pd.DataFrame(scored[:10])
                if "ticker" in df.columns:
                    cols = [c for c in ["ticker", "fit_score", "risk_score", "rank_score", "rank"] if c in df.columns]
                    st.dataframe(df[cols], use_container_width=True, hide_index=True)

    st.markdown(f'<div style="height:16px"></div>', unsafe_allow_html=True)

    # ── Row 2: Memos + Discover ───────────────────────────────────────────────
    col3, col4 = st.columns(2)

    with col3:
        memo_state = "Done" if st.session_state.memo_result else "Idle"
        st.markdown(
            f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-top:3px solid {GOLD};'
            f'border-radius:10px;padding:20px 22px;min-height:220px">',
            unsafe_allow_html=True,
        )
        st.markdown(_card_header("Generate Memos", "📄", memo_state), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        memo_n = st.slider("Top N companies", min_value=1, max_value=50, value=10, key="memo_top_n")
        if st.button("Generate Memos", key="btn_memos", use_container_width=True):
            with st.spinner(f"Generating memos for top {memo_n}…"):
                result = asyncio.run(_run_memos(memo_n))
            st.session_state.memo_result = result

        if st.session_state.memo_result:
            n = len(st.session_state.memo_result) if isinstance(st.session_state.memo_result, list) else st.session_state.memo_result
            st.success(f"Generated {n} memo(s)")

    with col4:
        disc_state = "Done" if st.session_state.discover_result else "Idle"
        st.markdown(
            f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-top:3px solid {GOLD};'
            f'border-radius:10px;padding:20px 22px;min-height:220px">',
            unsafe_allow_html=True,
        )
        st.markdown(_card_header("Discover Universe", "🔭", disc_state), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        dc1, dc2 = st.columns(2)
        with dc1:
            disc_strategy = st.selectbox(
                "Strategy",
                ["Market Screener", "Similarity Search", "Thematic Search"],
                key="disc_strategy",
            )
        with dc2:
            disc_input = st.text_input(
                "Input (optional)",
                placeholder="ticker or theme…",
                key="disc_input",
            )

        if st.button("Expand Universe", key="btn_discover", use_container_width=True):
            with st.spinner("Running universe expansion…"):
                result = asyncio.run(_run_discovery(disc_strategy, disc_input))
            st.session_state.discover_result = result

        if st.session_state.discover_result:
            r = st.session_state.discover_result
            if isinstance(r, dict):
                st.success(
                    f"Found {r.get('new_tickers', 0)} new tickers — "
                    f"ingested {r.get('ingested', 0)}"
                )
            else:
                st.success(str(r))

    # ── Clear results ─────────────────────────────────────────────────────────
    st.markdown(f'<div style="height:16px"></div>', unsafe_allow_html=True)
    if st.button("Clear All Results", key="btn_clear"):
        for k in ["ingest_result", "score_result", "memo_result", "discover_result"]:
            st.session_state[k] = None
        st.rerun()


# ── Async runners ─────────────────────────────────────────────────────────────

async def _run_ingestion(tickers: list[str]):
    from src.ingestion.workers.ingestion_worker import IngestionWorker
    engine, factory = _make_session()
    try:
        async with factory() as session:
            worker = IngestionWorker(session)
            results = await worker.ingest_batch(tickers)
            await session.commit()
        return results
    finally:
        await engine.dispose()


async def _run_scoring(tickers: list[str] | None, run_type: str):
    from src.orchestration.pipelines.scoring_pipeline import ScoringPipeline
    engine, factory = _make_session()
    try:
        async with factory() as session:
            pipeline = ScoringPipeline(session)
            return await pipeline.run(tickers=tickers, run_type=run_type)
    finally:
        await engine.dispose()


async def _run_memos(top_n: int):
    from src.orchestration.pipelines.memo_pipeline import MemoPipeline
    engine, factory = _make_session()
    try:
        async with factory() as session:
            pipeline = MemoPipeline(session)
            return await pipeline.generate_top_memos(top_n=top_n)
    finally:
        await engine.dispose()


async def _run_discovery(strategy: str, user_input: str):
    from src.orchestration.discovery.universe_expander import UniverseExpander
    engine, factory = _make_session()
    try:
        async with factory() as session:
            expander = UniverseExpander(session)
            if strategy == "Similarity Search" and user_input:
                new_tickers = await expander.expand_via_similarity(user_input.upper().strip())
            elif strategy == "Thematic Search" and user_input:
                new_tickers = await expander.expand_via_thematic(user_input)
            else:
                new_tickers = await expander.expand_via_screener()
            ingested = await expander.ingest_new_tickers(new_tickers[:20])
            await session.commit()
            return {"new_tickers": len(new_tickers), "ingested": ingested}
    finally:
        await engine.dispose()
