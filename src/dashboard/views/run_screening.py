"""
Run Screening — one-click workflow:
  1. Discover companies (auto-detects mode from input)
  2. Ingest (market data, filings)
  3. Score and rank
  4. Save top N to DB
"""
from __future__ import annotations
import asyncio
import concurrent.futures
import time
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from src.config.settings import settings
import streamlit as st


# Persistent executor — never shut down, survives Streamlit rerenders
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="screening")


def _run(coro, timeout: int = 1800):
    def _target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    future = _EXECUTOR.submit(_target)
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        raise RuntimeError(f"Operation timed out after {timeout}s")


def _engine_factory():
    engine = create_async_engine(
        settings.db.dsn,
        echo=False,
        pool_size=2,
        max_overflow=2,
        pool_timeout=30,
        pool_recycle=300,      # recycle connections every 5 min
        pool_pre_ping=True,    # test connection before use
    )
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, factory


def _card(content: str) -> str:
    return (
        f'<div style="background:#ffffff;border:1px solid #e8eaed;border-radius:8px;'
        f'padding:24px 28px;margin-bottom:16px">{content}</div>'
    )


def _step_row(number: str, label: str, status: str, detail: str = "") -> str:
    colors = {
        "waiting": ("#9ca3af", "#f9fafb", "Waiting"),
        "running": ("#d97706", "#fffbeb", "Running..."),
        "done":    ("#059669", "#f0fdf4", "Done"),
        "error":   ("#dc2626", "#fef2f2", "Error"),
    }
    color, bg, badge_text = colors.get(status, colors["waiting"])
    detail_html = (
        f'<div style="color:#6b7280;font-size:0.78rem;margin-top:4px">{detail}</div>'
        if detail else ""
    )
    return f"""
<div style="display:flex;align-items:flex-start;gap:16px;padding:14px 0;
            border-bottom:1px solid #f3f4f6">
  <div style="width:28px;height:28px;border-radius:50%;
              background:{bg};border:1px solid {color}33;
              display:flex;align-items:center;justify-content:center;
              font-size:0.75rem;font-weight:700;color:{color};
              flex-shrink:0;margin-top:1px">{number}</div>
  <div style="flex:1">
    <div style="font-size:0.88rem;font-weight:500;color:#111827">{label}</div>
    {detail_html}
  </div>
  <div style="background:{bg};color:{color};border:1px solid {color}33;
              padding:2px 10px;border-radius:4px;font-size:0.72rem;font-weight:600;
              white-space:nowrap;margin-top:2px">{badge_text}</div>
</div>"""


# ── Async runners ───────────────────────────────────────────────────────────────

async def _discover_and_ingest(max_companies: int, mode: str,
                                theme: str = "", sim_ticker: str = "") -> list[str]:
    from src.orchestration.discovery.universe_expander import UniverseExpander
    engine, factory = _engine_factory()
    try:
        async with factory() as session:
            expander = UniverseExpander(session)
            if mode == "thematic":
                tickers = await expander.expand_via_thematic(theme)
                await expander.ingest_new_tickers(tickers[:max_companies])
                return tickers[:max_companies]
            elif mode == "similarity":
                tickers = await expander.expand_via_similarity(sim_ticker)
                await expander.ingest_new_tickers(tickers[:max_companies])
                return tickers[:max_companies]
            else:
                return await expander.expand_via_screener(max_companies=max_companies)
    finally:
        await engine.dispose()


async def _score(tickers: list[str] | None) -> list[dict]:
    from src.orchestration.pipelines.scoring_pipeline import ScoringPipeline
    engine, factory = _engine_factory()
    try:
        async with factory() as session:
            pipeline = ScoringPipeline(session)
            return await pipeline.run(tickers=tickers, run_type="manual")
    finally:
        await engine.dispose()


async def _get_top_n() -> list[dict]:
    from src.db.repositories.recommendation_repo import RecommendationRepository
    from src.db.repositories.company_repo import CompanyRepository
    from src.config.scoring_weights import load_scoring_weights
    top_n = int(load_scoring_weights().get("ranking", {}).get("top_n_results", 5))
    engine, factory = _engine_factory()
    try:
        async with factory() as session:
            rec_repo = RecommendationRepository(session)
            co_repo  = CompanyRepository(session)
            recs     = await rec_repo.get_top_ranked(limit=top_n)
            rows = []
            for r in recs:
                co = await co_repo.get_by_ticker(r.ticker)
                rows.append({
                    "rank":       r.rank,
                    "ticker":     r.ticker,
                    "name":       co.name if co else "",
                    "exchange":   co.exchange if co else "",
                    "market_cap": float(co.market_cap_usd) if co and co.market_cap_usd else None,
                    "fit_score":  float(r.fit_score),
                    "risk_score": float(r.risk_score),
                    "rank_score": float(r.rank_score),
                    "status":     r.status,
                })
            return rows
    finally:
        await engine.dispose()


# ── Page ────────────────────────────────────────────────────────────────────────

def render() -> None:
    st.markdown("""
    <div style="margin-bottom:24px">
      <div style="font-size:1.35rem;font-weight:700;color:#111827;letter-spacing:-0.01em">
        Run Screening
      </div>
      <div style="font-size:0.84rem;color:#6b7280;margin-top:4px">
        Discover, ingest, and score companies in one step.
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Controls ───────────────────────────────────────────────────────────────
    c1, c2 = st.columns([1, 4])
    with c1:
        run_clicked = st.button("Run Screening", key="run_btn", use_container_width=True)
    with c2:
        max_co = st.number_input("Max companies to screen", min_value=5, max_value=200,
                                 value=20, step=5, label_visibility="collapsed", key="screen_max")

    mode, theme, sim_ticker = "screener", "", ""

    # ── Workflow ───────────────────────────────────────────────────────────────
    if run_clicked:
        st.session_state.pop("run_results", None)
        st.session_state.pop("run_error",   None)

        steps_ph  = st.empty()
        result_ph = st.empty()

        def render_steps(s1, s2, s3, s4, d1="", d2="", d3="", d4=""):
            steps_ph.markdown(
                _card(
                    "<div style='font-size:0.7rem;font-weight:600;text-transform:uppercase;"
                    "letter-spacing:0.09em;color:#9ca3af;margin-bottom:4px'>Progress</div>"
                    + _step_row("1", "Discover companies",          s1, d1)
                    + _step_row("2", "Ingest data (filings, news)", s2, d2)
                    + _step_row("3", "Score and rank",               s3, d3)
                    + _step_row("4", f"Save top results to database",s4, d4)
                ),
                unsafe_allow_html=True,
            )

        tickers: list[str] = []
        render_steps("running", "waiting", "waiting", "waiting",
                     d1="Scanning EDGAR universe for candidates...")

        try:
            t0 = time.time()
            render_steps("running", "running", "waiting", "waiting",
                         d1="Scanning EDGAR universe for candidates...")

            tickers = _run(_discover_and_ingest(max_co, mode, theme, sim_ticker))
            elapsed = time.time() - t0
            d1 = f"Found {len(tickers)} candidates in {elapsed:.0f}s"
            d2 = "Financials from SEC EDGAR XBRL"
            render_steps("done", "done", "running", "waiting", d1=d1, d2=d2)

            t2 = time.time()
            scored = _run(_score(tickers if tickers else None))
            n_scored = len(scored) if isinstance(scored, list) else 0
            d3 = f"{n_scored} companies scored in {time.time()-t2:.1f}s"
            render_steps("done", "done", "done", "running", d1=d1, d2=d2, d3=d3)

            t3 = time.time()
            top_n = _run(_get_top_n())
            d4 = f"Top {len(top_n)} saved in {time.time()-t3:.1f}s"
            render_steps("done", "done", "done", "done", d1=d1, d2=d2, d3=d3, d4=d4)

            import datetime as _dt
            st.session_state.run_results      = top_n
            st.session_state.run_completed_at = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
            total_time = time.time() - t0

            result_ph.markdown(
                f'<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;'
                f'padding:16px 24px;margin-top:16px;display:flex;align-items:center;gap:16px">'
                f'<div style="font-size:0.85rem;color:#065f46;font-weight:500">'
                f'Complete — {len(tickers)} screened, top {len(top_n)} saved.'
                f'</div>'
                f'<div style="margin-left:auto;font-size:0.78rem;color:#6b7280">'
                f'{total_time:.0f}s total</div></div>',
                unsafe_allow_html=True,
            )

        except Exception as err:
            st.session_state.run_error = str(err)
            result_ph.error(str(err))

    # ── Show results ──────────────────────────────────────────────────────────
    if st.session_state.get("run_results") and not run_clicked:
        top_n = st.session_state.run_results
        st.markdown(
            '<div style="margin-top:24px;margin-bottom:12px;font-size:0.7rem;font-weight:600;'
            'text-transform:uppercase;letter-spacing:0.09em;color:#9ca3af">Last Run Results</div>',
            unsafe_allow_html=True,
        )
        _render_results_table(top_n)
        st.markdown(
            '<div style="margin-top:10px;font-size:0.78rem;color:#9ca3af">'
            'View full details on the Results page.</div>',
            unsafe_allow_html=True,
        )

    elif not run_clicked and not st.session_state.get("run_results"):
        try:
            db_results = _run(_get_top_n())
            if db_results:
                st.session_state.run_results = db_results
                st.rerun()
        except Exception:
            pass

        if not st.session_state.get("run_results"):
            st.markdown("""
            <div style="background:#ffffff;border:1px solid #e8eaed;border-radius:8px;
                        padding:48px 28px;text-align:center;margin-top:8px">
              <div style="font-size:0.9rem;font-weight:500;color:#374151;margin-bottom:6px">
                No screening has been run yet
              </div>
              <div style="font-size:0.82rem;color:#9ca3af">
                Click Run Screening. Leave the box empty for a broad market sweep,
                type a ticker to find similar companies, or type a theme.
              </div>
            </div>
            """, unsafe_allow_html=True)


def _render_results_table(rows: list[dict]) -> None:
    def fmt_cap(v):
        if v is None: return "—"
        if v >= 1e9:  return f"${v/1e9:.1f}B"
        if v >= 1e6:  return f"${v/1e6:.0f}M"
        return f"${v:,.0f}"

    def score_tag(score, inverted=False):
        if inverted:
            c = "#dc2626" if score >= 60 else ("#d97706" if score >= 35 else "#059669")
        else:
            c = "#059669" if score >= 60 else ("#d97706" if score >= 40 else "#dc2626")
        bg = {"#059669": "#f0fdf4", "#d97706": "#fffbeb", "#dc2626": "#fef2f2"}[c]
        return (
            f'<span style="background:{bg};color:{c};border:1px solid {c}33;'
            f'padding:2px 9px;border-radius:4px;font-size:0.76rem;font-weight:700;'
            f'font-variant-numeric:tabular-nums">{score:.0f}</span>'
        )

    headers = ["Rank", "Ticker", "Company", "Exchange", "Mkt Cap", "Fit", "Risk", "Score"]
    TH = "".join(
        f'<th style="text-align:{"right" if i > 3 else "left"};padding:10px 14px;'
        f'font-size:0.68rem;font-weight:600;text-transform:uppercase;letter-spacing:0.07em;'
        f'color:#9ca3af;background:#f9fafb;border-bottom:1px solid #e8eaed">{h}</th>'
        for i, h in enumerate(headers)
    )

    rows_html = ""
    for i, r in enumerate(rows):
        bg = "#ffffff" if i % 2 == 0 else "#fafafa"
        rn = r.get("rank") or (i + 1)
        rank_badge = (
            f'<span style="background:#111827;color:#fff;width:24px;height:24px;'
            f'border-radius:50%;display:inline-flex;align-items:center;justify-content:center;'
            f'font-size:0.72rem;font-weight:700">{rn}</span>'
            if isinstance(rn, int) and rn <= 3 else
            f'<span style="color:#6b7280;font-size:0.82rem;font-weight:600">{rn}</span>'
        )
        rows_html += (
            f'<tr style="background:{bg}">'
            f'<td style="padding:10px 14px;border-bottom:1px solid #f3f4f6">{rank_badge}</td>'
            f'<td style="padding:10px 14px;border-bottom:1px solid #f3f4f6;font-weight:700;font-size:0.88rem;color:#111827">{r["ticker"]}</td>'
            f'<td style="padding:10px 14px;border-bottom:1px solid #f3f4f6;font-size:0.83rem;color:#374151">{r.get("name","")}</td>'
            f'<td style="padding:10px 14px;border-bottom:1px solid #f3f4f6;font-size:0.78rem;color:#9ca3af">{r.get("exchange","")}</td>'
            f'<td style="padding:10px 14px;border-bottom:1px solid #f3f4f6;text-align:right;font-size:0.83rem;color:#374151;font-variant-numeric:tabular-nums">{fmt_cap(r.get("market_cap"))}</td>'
            f'<td style="padding:10px 14px;border-bottom:1px solid #f3f4f6;text-align:right">{score_tag(r["fit_score"])}</td>'
            f'<td style="padding:10px 14px;border-bottom:1px solid #f3f4f6;text-align:right">{score_tag(r["risk_score"], inverted=True)}</td>'
            f'<td style="padding:10px 14px;border-bottom:1px solid #f3f4f6;text-align:right">{score_tag(r["rank_score"])}</td>'
            f'</tr>'
        )

    st.markdown(
        f'<div style="background:#ffffff;border:1px solid #e8eaed;border-radius:8px;overflow:hidden">'
        f'<table style="width:100%;border-collapse:collapse">'
        f'<thead><tr>{TH}</tr></thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table></div>',
        unsafe_allow_html=True,
    )
