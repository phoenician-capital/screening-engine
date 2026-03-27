"""
Results — enterprise dark table view of all scored companies from the database.
Sortable, filterable. Select a company to expand the full investment memo.
"""
from __future__ import annotations
import asyncio
import concurrent.futures
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from src.config.settings import settings


def _run(coro, timeout: int = 120):
    def _target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="dashboard")
    future = ex.submit(_target)
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        raise RuntimeError(f"Operation timed out after {timeout}s")
    except Exception:
        raise


import streamlit as st
from src.dashboard.components.styles import (
    BG_BASE, BG_CARD, BG_INPUT, BG_CARD_HOVER, BG_TABLE_HEAD, BG_TABLE_ROW, BG_TABLE_ALT,
    BORDER, BORDER_LIGHT, BORDER_FOCUS,
    GOLD, GOLD_LIGHT, GOLD_BG,
    GREEN, GREEN_BG, GREEN_DARK,
    RED, RED_BG,
    AMBER, AMBER_BG,
    ACCENT_BLUE, ACCENT_BLUE_BG,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, TEXT_DIM,
    FONT_MONO, FONT_SANS,
)


def _engine_factory():
    engine = create_async_engine(settings.db.dsn, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, factory


async def _load_results(limit: int = 500) -> list[dict]:
    from src.db.repositories.recommendation_repo import RecommendationRepository
    from src.db.repositories.company_repo import CompanyRepository
    from src.db.repositories.metric_repo import MetricRepository
    engine, factory = _engine_factory()
    try:
        async with factory() as session:
            rec_repo = RecommendationRepository(session)
            co_repo  = CompanyRepository(session)
            met_repo = MetricRepository(session)
            recs     = await rec_repo.get_top_ranked(limit=limit)
            rows = []
            for r in recs:
                co  = await co_repo.get_by_ticker(r.ticker)
                met = await met_repo.get_latest(r.ticker)
                rows.append({
                    "rank":               r.rank,
                    "ticker":             r.ticker,
                    "name":               co.name          if co  else "",
                    "exchange":           co.exchange      if co  else "",
                    "country":            co.country       if co  else "",
                    "sector":             co.gics_sector   if co  else "",
                    "founder_led":        co.is_founder_led if co else None,
                    "market_cap":         float(co.market_cap_usd) if co and co.market_cap_usd else None,
                    "fit_score":          float(r.fit_score),
                    "risk_score":         float(r.risk_score),
                    "rank_score":         float(r.rank_score),
                    "status":             r.status,
                    "memo_text":          r.memo_text,
                    "gross_margin":       float(met.gross_margin)        if met and met.gross_margin        else None,
                    "roic":               float(met.roic)                if met and met.roic                else None,
                    "fcf_yield":          float(met.fcf_yield)           if met and met.fcf_yield           else None,
                    "revenue_growth_yoy": float(met.revenue_growth_yoy)  if met and met.revenue_growth_yoy  else None,
                    "net_debt_ebitda":    float(met.net_debt_ebitda)     if met and met.net_debt_ebitda     else None,
                    "ev_ebit":            float(met.ev_ebit)             if met and met.ev_ebit             else None,
                    "analyst_count":      met.analyst_count              if met else None,
                    "insider_ownership":  float(met.insider_ownership_pct) if met and met.insider_ownership_pct else None,
                    "portfolio_comparison": r.portfolio_comparison,
                    "scoring_detail":     r.scoring_detail,
                    "inspired_by":        r.inspired_by,
                })
            return rows
    finally:
        await engine.dispose()


async def _submit_feedback(rec_id_ticker: tuple, action: str, reason: str | None = None) -> None:
    from src.db.models.feedback import Feedback
    from src.db.repositories.recommendation_repo import RecommendationRepository
    import uuid as _uuid
    engine, factory = _engine_factory()
    rec_id, ticker = rec_id_ticker
    try:
        async with factory() as session:
            fb = Feedback(
                recommendation_id=_uuid.UUID(rec_id),
                ticker=ticker,
                action=action,
                reject_reason=reason,
            )
            session.add(fb)
            repo = RecommendationRepository(session)
            status_map = {"research_now": "researching", "watch": "watched", "reject": "rejected"}
            if action in status_map:
                await repo.update_status(_uuid.UUID(rec_id), status_map[action])
            await session.commit()
    finally:
        await engine.dispose()


async def _get_rec_id(ticker: str) -> str | None:
    from src.db.repositories.recommendation_repo import RecommendationRepository
    engine, factory = _engine_factory()
    try:
        async with factory() as session:
            repo = RecommendationRepository(session)
            rec  = await repo.get_latest_for_ticker(ticker)
            return str(rec.id) if rec else None
    finally:
        await engine.dispose()


# ── Formatting ──────────────────────────────────────────────────────────────────

def _fmt_cap(v):
    if v is None: return "—"
    if v >= 1e9: return f"${v/1e9:.1f}B"
    if v >= 1e6: return f"${v/1e6:.0f}M"
    return f"${v:,.0f}"

def _fmt_pct(v):
    if v is None: return "—"
    return f"{v*100:.1f}%"

def _fmt_mult(v):
    if v is None: return "—"
    return f"{v:.1f}x"

def _score_tag(score, inverted=False):
    if inverted:
        c  = RED   if score >= 60 else (AMBER if score >= 35 else GREEN)
        bg = RED_BG if score >= 60 else (AMBER_BG if score >= 35 else GREEN_BG)
    else:
        c  = GREEN   if score >= 70 else (AMBER if score >= 50 else RED)
        bg = GREEN_BG if score >= 70 else (AMBER_BG if score >= 50 else RED_BG)
    return (
        f'<span style="background:{bg};color:{c};border:1px solid {c}30;'
        f'padding:3px 10px;border-radius:3px;font-size:0.73rem;font-weight:700;'
        f'font-family:{FONT_MONO};font-variant-numeric:tabular-nums">{score:.0f}</span>'
    )

def _status_tag(status):
    cfg = {
        "pending":     (TEXT_MUTED, BG_INPUT),
        "researching": (GREEN,      GREEN_BG),
        "watched":     (AMBER,      AMBER_BG),
        "rejected":    (RED,        RED_BG),
    }
    c, bg = cfg.get(status, (TEXT_MUTED, BG_INPUT))
    label = {"pending":"Pending","researching":"Researching","watched":"Watched","rejected":"Passed"}.get(status, status.title())
    return (
        f'<span style="background:{bg};color:{c};border:1px solid {c}30;'
        f'padding:2px 9px;border-radius:3px;font-size:0.69rem;font-weight:600;'
        f'letter-spacing:0.04em">{label}</span>'
    )

def _kpi(label: str, value: str, sub: str = "") -> str:
    sub_html = (
        f'<div style="font-size:0.70rem;color:{TEXT_MUTED};margin-top:3px;'
        f'font-family:{FONT_SANS}">{sub}</div>'
    ) if sub else ""
    return (
        f'<div style="background:{BG_INPUT};border:1px solid {BORDER};border-radius:6px;'
        f'padding:14px 16px">'
        f'<div style="font-size:0.62rem;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:0.10em;color:{TEXT_MUTED};margin-bottom:6px">{label}</div>'
        f'<div style="font-size:1.25rem;font-weight:700;color:{TEXT_PRIMARY};'
        f'font-variant-numeric:tabular-nums;font-family:{FONT_MONO}">{value}</div>'
        f'{sub_html}</div>'
    )


# ── Page ────────────────────────────────────────────────────────────────────────

def render() -> None:
    # Page header
    st.markdown(f"""
    <div style="margin-bottom:32px;padding-bottom:20px;border-bottom:1px solid {BORDER}">
      <div style="font-size:0.62rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.14em;color:{GOLD};margin-bottom:8px">
        SCREENING RESULTS
      </div>
      <div style="font-size:1.6rem;font-weight:700;color:{TEXT_PRIMARY};
                  letter-spacing:-0.02em;line-height:1.2">
        Ranked Universe
      </div>
      <div style="font-size:0.85rem;color:{TEXT_MUTED};margin-top:6px">
        All scored companies ranked by composite score. Select a company for the full analyst report.
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Load ALL results ──────────────────────────────────────────────────────
    rows = _run(_load_results(limit=500))

    # ── Filter / controls bar ─────────────────────────────────────────────────
    fc1, fc2, fc3, fc4, fc5, fc6 = st.columns([2, 1, 1, 1, 1, 1])
    with fc1:
        search = st.text_input("Search", placeholder="Search ticker or company...", label_visibility="collapsed")
    with fc2:
        min_fit = st.selectbox("Min Fit", ["Any fit", "30+", "40+", "50+", "60+", "70+"], label_visibility="collapsed")
    with fc3:
        max_risk = st.selectbox("Max Risk", ["Any risk", "< 15", "< 25", "< 40", "< 55"], label_visibility="collapsed")
    with fc4:
        status_f = st.selectbox("Status", ["All", "Pending", "Researching", "Watched", "Rejected"], label_visibility="collapsed")
    with fc5:
        sectors = sorted(set(r.get("sector","") for r in rows if r.get("sector")))
        sector_f = st.selectbox("Sector", ["All sectors"] + sectors, label_visibility="collapsed")
    with fc6:
        sort_by = st.selectbox("Sort", ["Score", "Fit", "Risk ↑", "Market Cap"], label_visibility="collapsed")

    st.markdown(f'<div style="height:6px"></div>', unsafe_allow_html=True)

    if not rows:
        st.markdown(f"""
        <div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:8px;
                    padding:72px 28px;text-align:center;
                    box-shadow:0 4px 24px rgba(0,0,0,0.2)">
          <div style="font-size:0.62rem;font-weight:700;text-transform:uppercase;
                      letter-spacing:0.14em;color:{TEXT_DIM};margin-bottom:16px">NO DATA</div>
          <div style="font-size:1.0rem;font-weight:600;color:{TEXT_MUTED};margin-bottom:8px">
            No results available
          </div>
          <div style="font-size:0.82rem;color:{TEXT_DIM}">
            Run a screening first to populate the universe.
          </div>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── Apply filters ─────────────────────────────────────────────────────────
    min_fit_val  = {"Any fit": 0, "30+": 30, "40+": 40, "50+": 50, "60+": 60, "70+": 70}.get(min_fit, 0)
    max_risk_val = {"Any risk": 100, "< 15": 15, "< 25": 25, "< 40": 40, "< 55": 55}.get(max_risk, 100)

    if search:
        s = search.upper()
        rows = [r for r in rows if s in r["ticker"] or s in (r.get("name") or "").upper()]
    if min_fit_val:
        rows = [r for r in rows if r["fit_score"] >= min_fit_val]
    if max_risk_val < 100:
        rows = [r for r in rows if r["risk_score"] < max_risk_val]
    if status_f != "All":
        rows = [r for r in rows if r["status"] == status_f.lower()]
    if sector_f != "All sectors":
        rows = [r for r in rows if r.get("sector","") == sector_f]

    # ── Sort ──────────────────────────────────────────────────────────────────
    if sort_by == "Fit":
        rows.sort(key=lambda r: r["fit_score"], reverse=True)
    elif sort_by == "Risk ↑":
        rows.sort(key=lambda r: r["risk_score"])
    elif sort_by == "Market Cap":
        rows.sort(key=lambda r: r.get("market_cap") or 0, reverse=True)
    else:
        rows.sort(key=lambda r: r["rank_score"], reverse=True)

    if not rows:
        st.markdown(
            f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:6px;'
            f'padding:32px;text-align:center;font-size:0.85rem;color:{TEXT_MUTED}">'
            f'No companies match the current filters.</div>',
            unsafe_allow_html=True,
        )
        return

    # ── Stats bar ─────────────────────────────────────────────────────────────
    avg_fit  = sum(r["fit_score"] for r in rows) / len(rows)
    avg_risk = sum(r["risk_score"] for r in rows) / len(rows)
    research_count = sum(1 for r in rows if r["status"] == "researching")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-top:2px solid {GOLD};'
            f'border-radius:6px;padding:14px 18px;box-shadow:0 2px 12px rgba(0,0,0,0.2)">'
            f'<div style="font-size:0.62rem;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:0.12em;color:{TEXT_MUTED};margin-bottom:6px">COMPANIES</div>'
            f'<div style="font-size:1.6rem;font-weight:700;color:{TEXT_PRIMARY};'
            f'font-family:{FONT_MONO}">{len(rows)}</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-top:2px solid {GREEN};'
            f'border-radius:6px;padding:14px 18px;box-shadow:0 2px 12px rgba(0,0,0,0.2)">'
            f'<div style="font-size:0.62rem;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:0.12em;color:{TEXT_MUTED};margin-bottom:6px">AVG FIT SCORE</div>'
            f'<div style="font-size:1.6rem;font-weight:700;color:{GREEN};'
            f'font-family:{FONT_MONO}">{avg_fit:.0f}</div></div>',
            unsafe_allow_html=True,
        )
    with c3:
        risk_color = RED if avg_risk >= 40 else (AMBER if avg_risk >= 25 else GREEN)
        st.markdown(
            f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-top:2px solid {risk_color};'
            f'border-radius:6px;padding:14px 18px;box-shadow:0 2px 12px rgba(0,0,0,0.2)">'
            f'<div style="font-size:0.62rem;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:0.12em;color:{TEXT_MUTED};margin-bottom:6px">AVG RISK</div>'
            f'<div style="font-size:1.6rem;font-weight:700;color:{risk_color};'
            f'font-family:{FONT_MONO}">{avg_risk:.0f}</div></div>',
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-top:2px solid {ACCENT_BLUE};'
            f'border-radius:6px;padding:14px 18px;box-shadow:0 2px 12px rgba(0,0,0,0.2)">'
            f'<div style="font-size:0.62rem;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:0.12em;color:{TEXT_MUTED};margin-bottom:6px">IN RESEARCH</div>'
            f'<div style="font-size:1.6rem;font-weight:700;color:{ACCENT_BLUE};'
            f'font-family:{FONT_MONO}">{research_count}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown(f'<div style="height:20px"></div>', unsafe_allow_html=True)

    # ── Table ─────────────────────────────────────────────────────────────────
    HEADERS = ["#", "TICKER", "COMPANY", "MKT CAP", "FIT", "RISK", "SCORE",
               "GROSS MGN", "ROIC", "FCF YLD", "REV GRW", "ND/EBITDA", "STATUS"]
    th_base = (
        f"padding:10px 14px;font-size:0.60rem;font-weight:700;text-transform:uppercase;"
        f"letter-spacing:0.10em;color:{TEXT_MUTED};background:{BG_TABLE_HEAD};"
        f"border-bottom:1px solid {BORDER};white-space:nowrap"
    )
    TH = "".join(
        f'<th style="{th_base};text-align:{"right" if i >= 3 else "left"}">{h}</th>'
        for i, h in enumerate(HEADERS)
    )

    ROWS_HTML = ""
    for idx, r in enumerate(rows):
        bg  = BG_TABLE_ROW if idx % 2 == 0 else BG_TABLE_ALT
        rn  = r.get("rank") or (idx + 1)
        is_top3 = isinstance(rn, int) and rn <= 3

        rank_html = (
            f'<span style="background:linear-gradient(135deg,{GOLD},{GOLD_LIGHT});color:#000;'
            f'width:26px;height:26px;border-radius:50%;display:inline-flex;'
            f'align-items:center;justify-content:center;font-size:0.68rem;font-weight:800;'
            f'font-family:{FONT_MONO}">{rn}</span>'
            if is_top3 else
            f'<span style="color:{TEXT_MUTED};font-size:0.80rem;font-weight:600;'
            f'font-family:{FONT_MONO}">{rn}</span>'
        )

        founder_badge = (
            f'<span style="background:{ACCENT_BLUE_BG};color:{ACCENT_BLUE};'
            f'border:1px solid {ACCENT_BLUE}30;padding:1px 6px;border-radius:3px;'
            f'font-size:0.64rem;font-weight:700;margin-left:7px;letter-spacing:0.04em">F</span>'
            if r.get("founder_led") else ""
        )
        inspired_badge = (
            f'<span style="background:{GOLD_BG};color:{GOLD};border:1px solid {GOLD}30;'
            f'padding:1px 6px;border-radius:3px;font-size:0.62rem;font-weight:600;'
            f'margin-left:6px">↳ {r["inspired_by"]}</span>'
            if r.get("inspired_by") else ""
        )

        metric_cell = (
            f"padding:10px 14px;border-bottom:1px solid {TEXT_DIM}30;"
            f"text-align:right;font-size:0.80rem;color:{TEXT_SECONDARY};"
            f"font-family:{FONT_MONO};font-variant-numeric:tabular-nums"
        )
        base_td = f"padding:10px 14px;border-bottom:1px solid {TEXT_DIM}30"

        ROWS_HTML += (
            f'<tr style="background:{bg}">'
            f'<td style="{base_td}">{rank_html}</td>'
            f'<td style="{base_td};font-weight:700;font-size:0.87rem;color:{TEXT_PRIMARY};'
            f'font-family:{FONT_MONO};letter-spacing:0.03em;white-space:nowrap">'
            f'{r["ticker"]}{founder_badge}{inspired_badge}</td>'
            f'<td style="{base_td};font-size:0.81rem;color:{TEXT_SECONDARY};'
            f'max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'
            f'{r.get("name","")}</td>'
            f'<td style="{metric_cell}">{_fmt_cap(r.get("market_cap"))}</td>'
            f'<td style="{base_td};text-align:right">{_score_tag(r["fit_score"])}</td>'
            f'<td style="{base_td};text-align:right">{_score_tag(r["risk_score"], inverted=True)}</td>'
            f'<td style="{base_td};text-align:right">{_score_tag(r["rank_score"])}</td>'
            f'<td style="{metric_cell}">{_fmt_pct(r.get("gross_margin"))}</td>'
            f'<td style="{metric_cell}">{_fmt_pct(r.get("roic"))}</td>'
            f'<td style="{metric_cell}">{_fmt_pct(r.get("fcf_yield"))}</td>'
            f'<td style="{metric_cell}">{_fmt_pct(r.get("revenue_growth_yoy"))}</td>'
            f'<td style="{metric_cell}">{_fmt_mult(r.get("net_debt_ebitda"))}</td>'
            f'<td style="{base_td}">{_status_tag(r["status"])}</td>'
            f'</tr>'
        )

    st.markdown(
        f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:8px;'
        f'overflow:auto;box-shadow:0 4px 32px rgba(0,0,0,0.3)">'
        f'<table style="width:100%;border-collapse:collapse">'
        f'<thead><tr>{TH}</tr></thead>'
        f'<tbody>{ROWS_HTML}</tbody>'
        f'</table></div>',
        unsafe_allow_html=True,
    )

    st.markdown(f'<div style="height:32px"></div>', unsafe_allow_html=True)

    # ── Company Detail section ─────────────────────────────────────────────────
    st.markdown(f"""
    <div style="margin-bottom:14px;padding-bottom:12px;border-bottom:1px solid {BORDER}">
      <div style="font-size:0.62rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.14em;color:{GOLD}">ANALYST REPORT</div>
    </div>
    """, unsafe_allow_html=True)

    selected = st.selectbox(
        "Select company",
        options=["— select a company —"] + [f"{r['ticker']}  —  {r.get('name','')}" for r in rows],
        label_visibility="collapsed",
    )

    if selected and selected != "— select a company —":
        ticker = selected.split()[0]
        row    = next((r for r in rows if r["ticker"] == ticker), None)
        if row:
            _render_company_detail(row)


def _render_company_detail(row: dict) -> None:
    ticker = row["ticker"]

    # Header card
    founder_badge_html = (
        f'<span style="background:{ACCENT_BLUE_BG};color:{ACCENT_BLUE};'
        f'border:1px solid {ACCENT_BLUE}30;padding:3px 10px;border-radius:3px;'
        f'font-size:0.73rem;font-weight:700;letter-spacing:0.05em">FOUNDER-LED</span>'
        if row.get("founder_led") else ""
    )

    st.markdown(f"""
    <div style="background:{BG_CARD};border:1px solid {BORDER};border-top:2px solid {GOLD};
                border-radius:8px;padding:24px 28px;margin-bottom:2px;
                box-shadow:0 4px 24px rgba(0,0,0,0.25)">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;
                  flex-wrap:wrap;gap:12px;margin-bottom:20px">
        <div>
          <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
            <span style="font-size:1.6rem;font-weight:800;color:{TEXT_PRIMARY};
                         font-family:{FONT_MONO};letter-spacing:0.02em">{ticker}</span>
            <span style="font-size:1.0rem;font-weight:500;color:{TEXT_SECONDARY}">{row.get('name','')}</span>
            {founder_badge_html}
          </div>
          <div style="margin-top:6px;font-size:0.78rem;color:{TEXT_MUTED}">
            {row.get('exchange','')}&nbsp;·&nbsp;{row.get('country','')}&nbsp;·&nbsp;{row.get('sector','')}
          </div>
        </div>
        <div style="text-align:right">
          {_status_tag(row['status'])}
        </div>
      </div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px">
        {_kpi("FIT SCORE",   f"{row['fit_score']:.0f}", "/ 100")}
        {_kpi("RISK SCORE",  f"{row['risk_score']:.0f}", "/ 100 — lower is better")}
        {_kpi("RANK SCORE",  f"{row['rank_score']:.1f}", "composite")}
        {_kpi("MARKET CAP",  _fmt_cap(row.get('market_cap')), "")}
      </div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px">
        {_kpi("GROSS MARGIN",   _fmt_pct(row.get('gross_margin')), "")}
        {_kpi("ROIC",           _fmt_pct(row.get('roic')), "")}
        {_kpi("FCF YIELD",      _fmt_pct(row.get('fcf_yield')), "")}
        {_kpi("REV GROWTH YOY", _fmt_pct(row.get('revenue_growth_yoy')), "")}
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Parse analyst agent outputs
    sd       = row.get("scoring_detail") or {}
    criteria = sd.get("criteria", [])
    analyst_thesis_entry = next((c for c in criteria if c.get("name") == "analyst_thesis"), None)
    thesis, diligence_questions, agent_verdict = "", [], ""
    if analyst_thesis_entry:
        ev = analyst_thesis_entry.get("evidence", "")
        if "THESIS:" in ev:
            thesis = ev.split("THESIS:")[1].split("|")[0].strip()
        if "DILIGENCE:" in ev:
            dil_part = ev.split("DILIGENCE:")[1]
            if "VERDICT:" in dil_part:
                dil_part = dil_part.split("VERDICT:")[0]
            diligence_questions = [q.strip() for q in dil_part.split("|") if q.strip()]
        if "VERDICT:" in ev:
            agent_verdict = ev.split("VERDICT:")[1].strip()

    # ── Analyst Verdict Banner ─────────────────────────────────────────────────
    if thesis or agent_verdict:
        verdict_cfg = {
            "RESEARCH NOW": (GREEN,       GREEN_BG,  f"{GREEN}30"),
            "WATCH":        (AMBER,       AMBER_BG,  f"{AMBER}30"),
            "PASS":         (TEXT_MUTED,  BG_INPUT,  f"{TEXT_MUTED}20"),
        }
        vc, vbg, vborder = verdict_cfg.get(agent_verdict, (GOLD, GOLD_BG, f"{GOLD}30"))
        thesis_html = (
            f'<div style="font-size:0.88rem;color:{TEXT_PRIMARY};font-style:italic;'
            f'line-height:1.65;margin-top:10px;padding-top:10px;'
            f'border-top:1px solid {vborder}">'
            f'&ldquo;{thesis}&rdquo;</div>'
        ) if thesis else ""
        st.markdown(f"""
        <div style="background:{vbg};border:1px solid {vborder};border-radius:8px;
                    padding:18px 22px;margin:16px 0">
          <div style="display:flex;align-items:center;gap:12px">
            <span style="background:{vc};color:#000;padding:4px 12px;
                         border-radius:3px;font-size:0.65rem;font-weight:800;
                         white-space:nowrap;letter-spacing:0.08em">{agent_verdict or "SCORED"}</span>
            <span style="font-size:0.73rem;font-weight:600;color:{TEXT_MUTED};
                         text-transform:uppercase;letter-spacing:0.08em">AI Analyst Verdict</span>
          </div>
          {thesis_html}
        </div>
        """, unsafe_allow_html=True)

    # ── Tabs: Memo / Scoring / Diligence / Actions ────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(["Investment Memo", "Scoring Breakdown", "Diligence", "Actions"])

    with tab1:
        memo = row.get("memo_text")
        if memo:
            st.markdown(
                f'<div style="background:{BG_INPUT};border:1px solid {BORDER};border-radius:6px;'
                f'padding:22px 26px;font-size:0.86rem;line-height:1.80;color:{TEXT_SECONDARY};'
                f'font-family:{FONT_SANS}">'
                f'{memo.replace(chr(10), "<br>")}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div style="background:{BG_INPUT};border:1px solid {BORDER};border-radius:6px;'
                f'padding:22px;font-size:0.84rem;color:{TEXT_MUTED};font-style:italic">'
                f'No memo generated — re-run screening to generate analysis.</div>',
                unsafe_allow_html=True,
            )

    with tab2:
        if criteria:
            agent_dims = {"business_quality", "unit_economics", "capital_returns",
                          "growth_quality", "balance_sheet", "phoenician_fit"}
            agent_c  = [c for c in criteria if c.get("name") in agent_dims and c.get("max_score", 0) > 0]
            python_c = [c for c in criteria if c.get("name") not in agent_dims
                        and c.get("name") not in ("analyst_thesis", "overall_fit", "llm_risk_score")
                        and c.get("max_score", 0) > 0]

            if agent_c:
                st.markdown(f"""
                <div style="font-size:0.62rem;font-weight:700;text-transform:uppercase;
                            letter-spacing:0.12em;color:{GOLD};margin:0 0 14px">
                  AI ANALYST DIMENSIONS
                </div>
                """, unsafe_allow_html=True)
                cols = st.columns(2)
                for i, c in enumerate(agent_c):
                    mx  = c.get("max_score", 1) or 1
                    sc  = c.get("score", 0)
                    pct = min(100, int(sc / mx * 100))
                    bar_c = GREEN if pct >= 65 else (AMBER if pct >= 40 else RED)
                    bar_bg = GREEN_BG if pct >= 65 else (AMBER_BG if pct >= 40 else RED_BG)
                    ev = c.get("evidence", "")
                    if ev.startswith("[Agent"):
                        ev = ev.split("] ", 1)[-1] if "] " in ev else ev
                    with cols[i % 2]:
                        st.markdown(
                            f'<div style="background:{BG_INPUT};border:1px solid {BORDER};'
                            f'border-radius:6px;padding:14px 16px;margin-bottom:10px">'
                            f'<div style="display:flex;justify-content:space-between;'
                            f'align-items:center;margin-bottom:8px">'
                            f'<span style="font-size:0.80rem;font-weight:600;color:{TEXT_PRIMARY}">'
                            f'{c["name"].replace("_"," ").title()}</span>'
                            f'<span style="color:{bar_c};font-size:0.80rem;font-weight:700;'
                            f'font-family:{FONT_MONO}">{pct}/100</span></div>'
                            f'<div style="background:{TEXT_DIM}40;border-radius:2px;height:4px;margin-bottom:8px">'
                            f'<div style="background:linear-gradient(90deg,{bar_c}80,{bar_c});'
                            f'width:{pct}%;height:4px;border-radius:2px"></div></div>'
                            f'<div style="font-size:0.72rem;color:{TEXT_MUTED};line-height:1.5">'
                            f'{ev[:220]}</div></div>',
                            unsafe_allow_html=True,
                        )

            if python_c:
                st.markdown(f"""
                <div style="font-size:0.62rem;font-weight:700;text-transform:uppercase;
                            letter-spacing:0.12em;color:{TEXT_MUTED};margin:16px 0 12px">
                  SUPPLEMENTARY SIGNALS
                </div>
                """, unsafe_allow_html=True)
                cols2 = st.columns(2)
                for i, c in enumerate(python_c):
                    mx  = c.get("max_score", 1) or 1
                    sc  = c.get("score", 0)
                    pct = min(100, int(sc / mx * 100))
                    bar_c = GREEN if pct >= 70 else (AMBER if pct >= 40 else RED)
                    with cols2[i % 2]:
                        st.markdown(
                            f'<div style="background:{BG_INPUT};border:1px solid {BORDER};'
                            f'border-radius:5px;padding:10px 14px;margin-bottom:8px">'
                            f'<div style="display:flex;justify-content:space-between;'
                            f'font-size:0.76rem;color:{TEXT_SECONDARY};margin-bottom:5px">'
                            f'<span style="font-weight:500">{c["name"].replace("_"," ").title()}</span>'
                            f'<span style="font-weight:700;color:{bar_c};font-family:{FONT_MONO}">'
                            f'{sc:.0f}/{mx:.0f}</span></div>'
                            f'<div style="background:{TEXT_DIM}40;border-radius:2px;height:3px;margin-bottom:5px">'
                            f'<div style="background:{bar_c};width:{pct}%;height:3px;border-radius:2px"></div></div>'
                            f'<div style="font-size:0.70rem;color:{TEXT_MUTED};line-height:1.4">'
                            f'{c.get("evidence","")[:150]}</div></div>',
                            unsafe_allow_html=True,
                        )
        else:
            st.markdown(
                f'<div style="font-size:0.84rem;color:{TEXT_MUTED};padding:20px 0">No scoring detail available.</div>',
                unsafe_allow_html=True,
            )

    with tab3:
        if diligence_questions:
            st.markdown(f"""
            <div style="background:{AMBER_BG};border:1px solid {AMBER}30;border-radius:8px;
                        padding:18px 22px">
              <div style="font-size:0.62rem;font-weight:700;text-transform:uppercase;
                          letter-spacing:0.12em;color:{AMBER};margin-bottom:14px">
                KEY DILIGENCE QUESTIONS
              </div>
            """, unsafe_allow_html=True)
            q_html = "".join(
                f'<div style="display:flex;align-items:flex-start;gap:12px;margin-bottom:12px">'
                f'<span style="color:{GOLD};font-weight:800;font-size:0.80rem;margin-top:1px;'
                f'flex-shrink:0;font-family:{FONT_MONO}">{i+1}.</span>'
                f'<span style="font-size:0.85rem;color:{TEXT_PRIMARY};line-height:1.6">{q}</span></div>'
                for i, q in enumerate(diligence_questions[:5])
            )
            st.markdown(
                q_html + '</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div style="font-size:0.84rem;color:{TEXT_MUTED};padding:20px 0">'
                f'No diligence questions generated — run screening to get AI-generated questions.</div>',
                unsafe_allow_html=True,
            )

        # Analyst suggestion
        if agent_verdict:
            suggestion_map = {
                "RESEARCH NOW": (f"Analyst recommends initiating research within 2 weeks. High conviction fit.", GREEN,  GREEN_BG),
                "WATCH":        (f"Analyst recommends monitoring. Wait for better entry or additional data.", AMBER,  AMBER_BG),
                "PASS":         (f"Analyst recommends passing. Does not meet Phoenician mandate criteria.", TEXT_MUTED, BG_INPUT),
            }
            msg, clr, bg = suggestion_map.get(agent_verdict, ("", TEXT_MUTED, BG_INPUT))
            if msg:
                st.markdown(
                    f'<div style="background:{bg};border:1px solid {clr}30;border-radius:6px;'
                    f'padding:14px 18px;margin-top:16px">'
                    f'<div style="font-size:0.62rem;font-weight:700;text-transform:uppercase;'
                    f'letter-spacing:0.10em;color:{clr};margin-bottom:6px">AI RECOMMENDATION</div>'
                    f'<div style="font-size:0.84rem;color:{TEXT_PRIMARY};line-height:1.5">{msg}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    with tab4:
        st.markdown(f"""
        <div style="font-size:0.62rem;font-weight:700;text-transform:uppercase;
                    letter-spacing:0.12em;color:{TEXT_MUTED};margin-bottom:16px">
          ANALYST DECISION
        </div>
        """, unsafe_allow_html=True)

        _BASE_REJECT_REASONS = [
            "Too expensive", "Weak moat / low quality", "Poor unit economics",
            "No insider alignment", "Too well-covered", "Limited growth runway",
            "Too risky", "Already known",
        ]
        _REJECT_REASONS = (
            _BASE_REJECT_REASONS + [f"Unresolved: {q[:60]}" for q in diligence_questions[:3]]
            if diligence_questions else _BASE_REJECT_REASONS
        )

        ac1, ac2, ac3, _ = st.columns([1, 1, 1, 3])
        with ac1:
            btn_label = "Research Now" if agent_verdict != "RESEARCH NOW" else "Research Now ✓"
            if st.button(btn_label, key=f"res_{ticker}", use_container_width=True):
                rec_id = _run(_get_rec_id(ticker))
                if rec_id:
                    _run(_submit_feedback((rec_id, ticker), "research_now"))
                    st.success(f"{ticker} flagged for research.")
                    st.rerun()
        with ac2:
            if st.button("Watch", key=f"watch_{ticker}", use_container_width=True):
                rec_id = _run(_get_rec_id(ticker))
                if rec_id:
                    _run(_submit_feedback((rec_id, ticker), "watch"))
                    st.info(f"{ticker} added to watchlist.")
                    st.rerun()
        with ac3:
            if st.button("Pass", key=f"rej_toggle_{ticker}", use_container_width=True):
                k = f"rej_open_{ticker}"
                st.session_state[k] = not st.session_state.get(k, False)

        if st.session_state.get(f"rej_open_{ticker}"):
            st.markdown(f'<div style="height:8px"></div>', unsafe_allow_html=True)
            rr1, rr2, rr3 = st.columns([3, 3, 1])
            with rr1:
                reason = st.selectbox("Reason", _REJECT_REASONS, key=f"reason_{ticker}", label_visibility="collapsed")
            with rr2:
                notes = st.text_input("Note", placeholder="Optional note...", key=f"rnote_{ticker}", label_visibility="collapsed")
            with rr3:
                if st.button("Confirm", key=f"rej_confirm_{ticker}", use_container_width=True):
                    rec_id = _run(_get_rec_id(ticker))
                    if rec_id:
                        _run(_submit_feedback((rec_id, ticker), "reject", reason))
                        st.session_state[f"rej_open_{ticker}"] = False
                        st.rerun()
