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
import threading
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from src.config.settings import settings
import streamlit as st

from src.dashboard.components.styles import (
    BG_BASE, BG_CARD, BG_INPUT, BG_CARD_HOVER,
    BORDER, BORDER_LIGHT, BORDER_FOCUS,
    GOLD, GOLD_LIGHT, GOLD_BG,
    GREEN, GREEN_BG, RED, RED_BG, AMBER, AMBER_BG,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, TEXT_DIM,
    FONT_MONO, FONT_SANS,
)

# ── Global job state — survives Streamlit session resets and browser refreshes ──
_GLOBAL_JOB: dict = {}
_GLOBAL_JOB_LOCK = threading.Lock()


def _run(coro, timeout: int = None):
    """Run a coroutine in a completely isolated thread with its own event loop."""
    result_holder = [None]
    error_holder  = [None]
    done_event    = threading.Event()

    def _target():
        executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=16, thread_name_prefix="screening_io"
        )
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
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.close()
            finally:
                executor.shutdown(wait=True, cancel_futures=True)
            done_event.set()

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    done_event.wait()
    if error_holder[0]:
        raise error_holder[0]
    return result_holder[0]


def _engine_factory():
    from sqlalchemy.pool import NullPool
    engine = create_async_engine(settings.db.dsn, echo=False, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, factory


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


# ── UI Components ────────────────────────────────────────────────────────────────

def _step_html(number: str, label: str, status: str, detail: str = "") -> str:
    status_cfg = {
        "waiting": (TEXT_DIM,   BG_INPUT,  TEXT_MUTED,  "WAITING"),
        "running": (GOLD,       GOLD_BG,   GOLD,        "RUNNING"),
        "done":    (GREEN,      GREEN_BG,  GREEN,       "COMPLETE"),
        "error":   (RED,        RED_BG,    RED,         "ERROR"),
    }
    dot_color, dot_bg, badge_color, badge_text = status_cfg.get(status, status_cfg["waiting"])

    pulse = ' class="ph-step-active"' if status == "running" else ""
    detail_html = (
        f'<div style="color:{TEXT_MUTED};font-size:0.75rem;margin-top:3px;'
        f'font-family:{FONT_SANS};line-height:1.4">{detail}</div>'
        if detail else ""
    )
    return f"""
<div style="display:flex;align-items:flex-start;gap:16px;padding:16px 24px;
            border-bottom:1px solid {TEXT_DIM}40;position:relative">
  <div{pulse} style="width:32px;height:32px;border-radius:50%;
              background:{dot_bg};border:1px solid {dot_color}40;
              display:flex;align-items:center;justify-content:center;
              font-size:0.72rem;font-weight:700;color:{dot_color};
              flex-shrink:0;margin-top:1px;font-family:{FONT_MONO}">{number}</div>
  <div style="flex:1;min-width:0">
    <div style="font-size:0.86rem;font-weight:600;color:{TEXT_PRIMARY};
                letter-spacing:0.01em">{label}</div>
    {detail_html}
  </div>
  <div style="background:{dot_bg};color:{badge_color};border:1px solid {badge_color}30;
              padding:3px 11px;border-radius:3px;font-size:0.64rem;font-weight:700;
              white-space:nowrap;letter-spacing:0.08em;font-family:{FONT_SANS}">{badge_text}</div>
</div>"""


def _score_tag(score, inverted=False):
    if inverted:
        c  = RED   if score >= 60 else (AMBER if score >= 35 else GREEN)
        bg = RED_BG if score >= 60 else (AMBER_BG if score >= 35 else GREEN_BG)
    else:
        c  = GREEN   if score >= 60 else (AMBER if score >= 40 else RED)
        bg = GREEN_BG if score >= 60 else (AMBER_BG if score >= 40 else RED_BG)
    return (
        f'<span style="background:{bg};color:{c};border:1px solid {c}30;'
        f'padding:3px 10px;border-radius:3px;font-size:0.74rem;font-weight:700;'
        f'font-family:{FONT_MONO};font-variant-numeric:tabular-nums">{score:.0f}</span>'
    )


def _fmt_cap(v):
    if v is None: return "—"
    if v >= 1e9:  return f"${v/1e9:.1f}B"
    if v >= 1e6:  return f"${v/1e6:.0f}M"
    return f"${v:,.0f}"


def _render_results_table(rows: list[dict]) -> None:
    if not rows:
        return

    headers = ["#", "TICKER", "COMPANY", "EXCHANGE", "MKT CAP", "FIT", "RISK", "SCORE"]
    th_style = (
        f"text-align:left;padding:11px 16px;"
        f"font-size:0.62rem;font-weight:700;text-transform:uppercase;letter-spacing:0.10em;"
        f"color:{TEXT_MUTED};background:{BG_INPUT};border-bottom:1px solid {BORDER};white-space:nowrap"
    )
    th_r_style = th_style.replace("text-align:left", "text-align:right")

    TH = "".join(
        f'<th style="{th_r_style if i >= 4 else th_style}">{h}</th>'
        for i, h in enumerate(headers)
    )

    rows_html = ""
    for i, r in enumerate(rows):
        bg  = BG_CARD if i % 2 == 0 else f"{BG_INPUT}88"
        rn  = r.get("rank") or (i + 1)
        is_top = isinstance(rn, int) and rn <= 3
        rank_html = (
            f'<span style="background:linear-gradient(135deg,{GOLD},{GOLD_LIGHT});color:#000;'
            f'width:26px;height:26px;border-radius:50%;display:inline-flex;'
            f'align-items:center;justify-content:center;font-size:0.70rem;font-weight:800;'
            f'font-family:{FONT_MONO}">{rn}</span>'
            if is_top else
            f'<span style="color:{TEXT_MUTED};font-size:0.80rem;font-weight:600;'
            f'font-family:{FONT_MONO}">{rn}</span>'
        )
        td = f"padding:11px 16px;border-bottom:1px solid {TEXT_DIM}40"
        rows_html += (
            f'<tr style="background:{bg};transition:background 0.1s" '
            f'onmouseover="this.style.background=\'{BG_CARD_HOVER}\'" '
            f'onmouseout="this.style.background=\'{bg}\'">'
            f'<td style="{td}">{rank_html}</td>'
            f'<td style="{td};font-weight:700;font-size:0.88rem;color:{TEXT_PRIMARY};'
            f'font-family:{FONT_MONO};letter-spacing:0.02em">{r["ticker"]}</td>'
            f'<td style="{td};font-size:0.82rem;color:{TEXT_SECONDARY};max-width:200px;'
            f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{r.get("name","")}</td>'
            f'<td style="{td};font-size:0.75rem;color:{TEXT_MUTED}">{r.get("exchange","")}</td>'
            f'<td style="{td};text-align:right;font-size:0.82rem;color:{TEXT_SECONDARY};'
            f'font-family:{FONT_MONO}">{_fmt_cap(r.get("market_cap"))}</td>'
            f'<td style="{td};text-align:right">{_score_tag(r["fit_score"])}</td>'
            f'<td style="{td};text-align:right">{_score_tag(r["risk_score"], inverted=True)}</td>'
            f'<td style="{td};text-align:right">{_score_tag(r["rank_score"])}</td>'
            f'</tr>'
        )

    st.markdown(
        f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:8px;'
        f'overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.25)">'
        f'<table style="width:100%;border-collapse:collapse">'
        f'<thead><tr>{TH}</tr></thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table></div>',
        unsafe_allow_html=True,
    )


# ── Page ─────────────────────────────────────────────────────────────────────────

def render() -> None:
    # Page header
    st.markdown(f"""
    <div style="margin-bottom:32px;padding-bottom:20px;border-bottom:1px solid {BORDER}">
      <div style="font-size:0.62rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.14em;color:{GOLD};margin-bottom:8px">
        SCREENING ENGINE
      </div>
      <div style="font-size:1.6rem;font-weight:700;color:{TEXT_PRIMARY};
                  letter-spacing:-0.02em;line-height:1.2">
        Run Screening
      </div>
      <div style="font-size:0.85rem;color:{TEXT_MUTED};margin-top:6px">
        Discover, ingest, and score companies in a single automated workflow.
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Controls ─────────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns([2, 1, 3])
    with c1:
        run_clicked = st.button("Execute Screening Run", key="run_btn", use_container_width=True)
    with c2:
        max_co = st.number_input(
            "Max companies", min_value=5, max_value=500,
            value=20, step=5, label_visibility="collapsed", key="screen_max"
        )
    with c3:
        st.markdown(
            f'<div style="padding:7px 0;font-size:0.77rem;color:{TEXT_MUTED}">'
            f'<span style="color:{GOLD};font-weight:600">↑</span> '
            f'Global universe · AI Analyst Agent · 20 parallel streams</div>',
            unsafe_allow_html=True
        )

    st.markdown(f'<div style="height:8px"></div>', unsafe_allow_html=True)

    # ── Background job state ─────────────────────────────────────────────────
    job = _GLOBAL_JOB if _GLOBAL_JOB else None

    # ── Start new job ────────────────────────────────────────────────────────
    if run_clicked and not (job and not job.get("done")):
        _GLOBAL_JOB.clear()
        _GLOBAL_JOB.update({
            "step": 1, "done": False, "error": None,
            "tickers": [], "scored": 0, "top_n": [],
            "d1": "", "d2": "", "d3": "", "d4": "",
            "t0": time.time(),
        })
        job = _GLOBAL_JOB

        def _bg_run():
            try:
                t0 = _GLOBAL_JOB["t0"]
                _GLOBAL_JOB["step"] = 1
                tickers = _run(_discover_and_ingest(max_co, "screener", "", ""))
                _GLOBAL_JOB["tickers"] = tickers
                _GLOBAL_JOB["d1"] = f"{len(tickers)} candidates · {time.time()-t0:.0f}s"
                _GLOBAL_JOB["d2"] = "FMP + Yahoo Finance timeseries"
                _GLOBAL_JOB["step"] = 2

                t2 = time.time()
                _GLOBAL_JOB["step"] = 3
                scored = _run(_score(tickers if tickers else None))
                _GLOBAL_JOB["scored"] = len(scored) if isinstance(scored, list) else 0
                _GLOBAL_JOB["d3"] = f"{_GLOBAL_JOB['scored']} companies · {time.time()-t2:.1f}s"

                t3 = time.time()
                _GLOBAL_JOB["step"] = 4
                top_n = _run(_get_top_n())
                _GLOBAL_JOB["top_n"] = top_n
                _GLOBAL_JOB["d4"] = f"Top {len(top_n)} persisted · {time.time()-t3:.1f}s"

                import datetime as _dt
                _GLOBAL_JOB["done"] = True
                _GLOBAL_JOB["completed_at"] = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
            except Exception as err:
                _GLOBAL_JOB["error"] = str(err)
                _GLOBAL_JOB["done"]  = True

        t = threading.Thread(target=_bg_run, daemon=False, name="screening_bg")
        t.start()
        st.rerun()

    # ── Poll running job ─────────────────────────────────────────────────────
    job = _GLOBAL_JOB if _GLOBAL_JOB else None
    if job and not job.get("done"):
        step    = job.get("step", 1)
        s1      = "done" if step > 1 else "running"
        s2      = "done" if step > 2 else ("running" if step == 2 else "waiting")
        s3      = "done" if step > 3 else ("running" if step == 3 else "waiting")
        s4      = "done" if step > 4 else ("running" if step == 4 else "waiting")
        elapsed = int(time.time() - job.get("t0", time.time()))

        st.markdown(f"""
        <div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:8px;
                    overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.3);margin-bottom:20px">
          <div style="padding:16px 24px 12px;border-bottom:1px solid {BORDER};
                      display:flex;align-items:center;justify-content:space-between">
            <div style="font-size:0.62rem;font-weight:700;text-transform:uppercase;
                        letter-spacing:0.12em;color:{GOLD}">RUN IN PROGRESS</div>
            <div style="font-size:0.72rem;color:{TEXT_MUTED};font-family:{FONT_MONO}">{elapsed}s elapsed</div>
          </div>
          {_step_html("1", "Discover Companies", s1, job.get("d1") or "Scanning EDGAR universe...")}
          {_step_html("2", "Ingest Market Data", s2, job.get("d2") or ("Fetching FMP + Yahoo Finance..." if step >= 2 else ""))}
          {_step_html("3", "Score &amp; Rank", s3, job.get("d3") or ("Running AI Analyst Agent..." if step >= 3 else ""))}
          {_step_html("4", "Persist Results", s4, job.get("d4") or ("Writing to database..." if step >= 4 else ""))}
        </div>
        """, unsafe_allow_html=True)

        st.markdown(
            f'<div style="font-size:0.75rem;color:{TEXT_MUTED};text-align:center;'
            f'padding:4px">Auto-refreshing every 5 seconds</div>',
            unsafe_allow_html=True,
        )
        time.sleep(5)
        st.rerun()
        return

    # ── Show completed job ───────────────────────────────────────────────────
    if job and job.get("done"):
        if job.get("error"):
            st.markdown(f"""
            <div style="background:{RED_BG};border:1px solid {RED}40;border-radius:8px;
                        padding:20px 24px;margin-bottom:20px">
              <div style="font-size:0.62rem;font-weight:700;text-transform:uppercase;
                          letter-spacing:0.10em;color:{RED};margin-bottom:6px">RUN FAILED</div>
              <div style="font-size:0.84rem;color:{TEXT_SECONDARY};font-family:{FONT_MONO}">{job['error']}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            tickers = job.get("tickers", [])
            top_n   = job.get("top_n", [])
            total   = int(time.time() - job.get("t0", time.time()))
            completed_at = job.get("completed_at", "")

            st.markdown(f"""
            <div style="background:{GREEN_BG};border:1px solid {GREEN}30;border-radius:8px;
                        padding:18px 24px;margin-bottom:20px;
                        display:flex;align-items:center;justify-content:space-between">
              <div>
                <div style="font-size:0.62rem;font-weight:700;text-transform:uppercase;
                            letter-spacing:0.10em;color:{GREEN};margin-bottom:6px">RUN COMPLETE</div>
                <div style="font-size:0.84rem;color:{TEXT_PRIMARY};font-weight:500">
                  {len(tickers)} companies discovered &nbsp;·&nbsp;
                  {job.get('scored',0)} scored &nbsp;·&nbsp;
                  Top {len(top_n)} saved
                </div>
              </div>
              <div style="text-align:right">
                <div style="font-size:0.72rem;color:{TEXT_MUTED};font-family:{FONT_MONO}">{total}s total</div>
                <div style="font-size:0.70rem;color:{TEXT_MUTED};margin-top:2px">{completed_at}</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            # Progress recap
            st.markdown(f"""
            <div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:8px;
                        overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.2);margin-bottom:24px">
              <div style="padding:14px 24px 10px;border-bottom:1px solid {BORDER}">
                <div style="font-size:0.62rem;font-weight:700;text-transform:uppercase;
                            letter-spacing:0.12em;color:{TEXT_MUTED}">PIPELINE SUMMARY</div>
              </div>
              {_step_html("1", "Discover Companies",  "done", job.get("d1",""))}
              {_step_html("2", "Ingest Market Data",  "done", job.get("d2",""))}
              {_step_html("3", "Score &amp; Rank",    "done", job.get("d3",""))}
              {_step_html("4", "Persist Results",     "done", job.get("d4",""))}
            </div>
            """, unsafe_allow_html=True)

    # ── Show results table ───────────────────────────────────────────────────
    if job and job.get("done") and job.get("top_n") and not run_clicked:
        top_n = job.get("top_n", [])
        st.markdown(f"""
        <div style="display:flex;align-items:center;justify-content:space-between;
                    margin-bottom:14px">
          <div style="font-size:0.62rem;font-weight:700;text-transform:uppercase;
                      letter-spacing:0.12em;color:{TEXT_MUTED}">TOP RANKED COMPANIES</div>
          <div style="font-size:0.73rem;color:{TEXT_MUTED}">Full analysis on Results page</div>
        </div>
        """, unsafe_allow_html=True)
        _render_results_table(top_n)

    elif not run_clicked and not (job and job.get("top_n")):
        try:
            db_results = _run(_get_top_n())
            if db_results:
                _GLOBAL_JOB.update({"done": True, "top_n": db_results})
                st.rerun()
        except Exception:
            pass

        if not (job and job.get("top_n")):
            st.markdown(f"""
            <div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:8px;
                        padding:72px 28px;text-align:center;
                        box-shadow:0 4px 24px rgba(0,0,0,0.2)">
              <div style="font-size:0.62rem;font-weight:700;text-transform:uppercase;
                          letter-spacing:0.14em;color:{GOLD};margin-bottom:16px">READY</div>
              <div style="font-size:1.1rem;font-weight:600;color:{TEXT_PRIMARY};
                          margin-bottom:10px;letter-spacing:-0.01em">
                No screening has been run
              </div>
              <div style="font-size:0.84rem;color:{TEXT_MUTED};max-width:420px;margin:0 auto;
                          line-height:1.6">
                Click <span style="color:{GOLD};font-weight:600">Execute Screening Run</span> to start.
                The engine will discover, ingest, and score the global universe automatically.
              </div>
            </div>
            """, unsafe_allow_html=True)
