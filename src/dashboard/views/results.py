"""
Results — clean table view of all scored companies from the database.
Sortable, filterable. Click a row to expand the investment memo.
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
            recs     = await rec_repo.get_top_ranked(limit=limit)  # load all
            rows = []
            for r in recs:
                co  = await co_repo.get_by_ticker(r.ticker)
                met = await met_repo.get_latest(r.ticker)
                rows.append({
                    "rank":         r.rank,
                    "ticker":       r.ticker,
                    "name":         co.name         if co  else "",
                    "exchange":     co.exchange     if co  else "",
                    "country":      co.country      if co  else "",
                    "sector":       co.gics_sector  if co  else "",
                    "founder_led":  co.is_founder_led if co else None,
                    "market_cap":   float(co.market_cap_usd) if co and co.market_cap_usd else None,
                    "fit_score":    float(r.fit_score),
                    "risk_score":   float(r.risk_score),
                    "rank_score":   float(r.rank_score),
                    "status":       r.status,
                    "memo_text":    r.memo_text,
                    # key metrics
                    "gross_margin":       float(met.gross_margin)       if met and met.gross_margin       else None,
                    "roic":               float(met.roic)               if met and met.roic               else None,
                    "fcf_yield":          float(met.fcf_yield)          if met and met.fcf_yield          else None,
                    "revenue_growth_yoy": float(met.revenue_growth_yoy) if met and met.revenue_growth_yoy else None,
                    "net_debt_ebitda":    float(met.net_debt_ebitda)    if met and met.net_debt_ebitda    else None,
                    "ev_ebit":            float(met.ev_ebit)            if met and met.ev_ebit            else None,
                    "analyst_count":      met.analyst_count             if met else None,
                    "insider_ownership":  float(met.insider_ownership_pct) if met and met.insider_ownership_pct else None,
                    "memo_text":          r.memo_text,
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
    # rec_id_ticker is (rec_id_str, ticker)
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
        c  = "#dc2626" if score >= 60 else ("#d97706" if score >= 35 else "#059669")
    else:
        c  = "#059669" if score >= 70 else ("#d97706" if score >= 50 else "#dc2626")
    bg = {"#059669": "#f0fdf4", "#d97706": "#fffbeb", "#dc2626": "#fef2f2"}[c]
    return (
        f'<span style="background:{bg};color:{c};border:1px solid {c}33;'
        f'padding:2px 9px;border-radius:4px;font-size:0.76rem;font-weight:700;'
        f'font-variant-numeric:tabular-nums">{score:.0f}</span>'
    )

def _status_tag(status):
    cfg = {
        "pending":     ("#9ca3af", "#f9fafb"),
        "researching": ("#059669", "#f0fdf4"),
        "watched":     ("#d97706", "#fffbeb"),
        "rejected":    ("#dc2626", "#fef2f2"),
    }
    c, bg = cfg.get(status, ("#9ca3af", "#f9fafb"))
    label = {"pending":"Pending","researching":"Researching","watched":"Watched","rejected":"Rejected"}.get(status, status.title())
    return (
        f'<span style="background:{bg};color:{c};border:1px solid {c}33;'
        f'padding:2px 9px;border-radius:4px;font-size:0.72rem;font-weight:600">{label}</span>'
    )


# ── Page ────────────────────────────────────────────────────────────────────────

def render() -> None:
    st.markdown("""
    <div style="margin-bottom:24px">
      <div style="font-size:1.35rem;font-weight:700;color:#111827;letter-spacing:-0.01em">Results</div>
      <div style="font-size:0.84rem;color:#6b7280;margin-top:4px">
        All scored companies, ranked by composite score. Click a row to expand.
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Load ALL results first ─────────────────────────────────────────────────
    rows = _run(_load_results(limit=500))

    # ── Filter / controls bar ─────────────────────────────────────────────────
    fc1, fc2, fc3, fc4, fc5, fc6 = st.columns([2, 1, 1, 1, 1, 1])
    with fc1:
        search = st.text_input("Search", placeholder="Ticker or company name…", label_visibility="collapsed")
    with fc2:
        min_fit = st.selectbox("Min Fit", ["Any fit", "30+", "40+", "50+", "60+", "70+"], label_visibility="collapsed")
    with fc3:
        max_risk = st.selectbox("Max Risk", ["Any risk", "< 15", "< 25", "< 40", "< 55"], label_visibility="collapsed")
    with fc4:
        status_f = st.selectbox("Status", ["All", "Pending", "Researching", "Watched", "Rejected"], label_visibility="collapsed")
    with fc5:
        # Build sector list from loaded data
        sectors = sorted(set(r.get("sector","") for r in rows if r.get("sector")))
        sector_f = st.selectbox("Sector", ["All sectors"] + sectors, label_visibility="collapsed")
    with fc6:
        sort_by = st.selectbox("Sort", ["Score", "Fit", "Risk ↑", "Market Cap"], label_visibility="collapsed")

    st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)

    if not rows:
        st.markdown("""
        <div style="background:#ffffff;border:1px solid #e8eaed;border-radius:8px;
                    padding:48px 28px;text-align:center;margin-top:8px">
          <div style="font-size:0.9rem;font-weight:500;color:#374151;margin-bottom:6px">No results yet</div>
          <div style="font-size:0.82rem;color:#9ca3af">
            Go to Run Screening and run the workflow first.
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
        st.info("No companies match the current filters.")
        return

    # ── Count line ─────────────────────────────────────────────────────────────
    # rows is already the full loaded set (before filters applied to display)
    st.markdown(
        f'<div style="font-size:0.76rem;color:#9ca3af;margin-bottom:10px">'
        f'{len(rows)} companies</div>',
        unsafe_allow_html=True,
    )

    # ── Table header ──────────────────────────────────────────────────────────
    HEADERS = ["#", "Ticker", "Company", "Mkt Cap", "Fit", "Risk", "Score",
               "Gross Mgn", "ROIC", "FCF Yld", "Rev Gth", "ND/EBITDA", "Status", "Action"]
    TH = "".join(
        f'<th style="padding:9px 12px;font-size:0.66rem;font-weight:600;'
        f'text-transform:uppercase;letter-spacing:0.07em;color:#9ca3af;'
        f'background:#f9fafb;border-bottom:1px solid #e8eaed;'
        f'white-space:nowrap;text-align:{"right" if i >= 3 else "left"}">{h}</th>'
        for i, h in enumerate(HEADERS)
    )

    # ── Rows ──────────────────────────────────────────────────────────────────
    ROWS_HTML = ""
    for idx, r in enumerate(rows):
        bg = "#ffffff" if idx % 2 == 0 else "#fafafa"
        rn = r.get("rank") or (idx + 1)
        rank_cell = (
            f'<span style="background:#111827;color:#fff;width:22px;height:22px;'
            f'border-radius:50%;display:inline-flex;align-items:center;justify-content:center;'
            f'font-size:0.7rem;font-weight:700">{rn}</span>'
            if isinstance(rn, int) and rn <= 3
            else f'<span style="font-size:0.82rem;color:#6b7280;font-weight:500">{rn}</span>'
        )
        founder = (
            '<span style="background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;'
            'padding:1px 6px;border-radius:3px;font-size:0.67rem;font-weight:600;'
            'margin-left:6px">F</span>'
            if r.get("founder_led") else ""
        )
        inspired = (
            f'<span style="background:#fffbeb;color:#92400e;border:1px solid #fde68a;'
            f'padding:1px 6px;border-radius:3px;font-size:0.67rem;font-weight:600;'
            f'margin-left:6px">via {r["inspired_by"]}</span>'
            if r.get("inspired_by") else ""
        )
        ROWS_HTML += (
            f'<tr style="background:{bg};cursor:pointer">'
            f'<td style="padding:9px 12px;border-bottom:1px solid #f3f4f6">{rank_cell}</td>'
            f'<td style="padding:9px 12px;border-bottom:1px solid #f3f4f6;'
            f'font-weight:700;font-size:0.88rem;color:#111827;white-space:nowrap">'
            f'{r["ticker"]}{founder}{inspired}</td>'
            f'<td style="padding:9px 12px;border-bottom:1px solid #f3f4f6;'
            f'font-size:0.82rem;color:#374151;max-width:160px;overflow:hidden;'
            f'text-overflow:ellipsis;white-space:nowrap">{r.get("name","")}</td>'
            f'<td style="padding:9px 12px;border-bottom:1px solid #f3f4f6;'
            f'text-align:right;font-size:0.82rem;color:#374151;'
            f'font-variant-numeric:tabular-nums">{_fmt_cap(r.get("market_cap"))}</td>'
            f'<td style="padding:9px 12px;border-bottom:1px solid #f3f4f6;text-align:right">'
            f'{_score_tag(r["fit_score"])}</td>'
            f'<td style="padding:9px 12px;border-bottom:1px solid #f3f4f6;text-align:right">'
            f'{_score_tag(r["risk_score"], inverted=True)}</td>'
            f'<td style="padding:9px 12px;border-bottom:1px solid #f3f4f6;text-align:right">'
            f'{_score_tag(r["rank_score"])}</td>'
            f'<td style="padding:9px 12px;border-bottom:1px solid #f3f4f6;text-align:right;'
            f'font-size:0.82rem;color:#374151;font-variant-numeric:tabular-nums">'
            f'{_fmt_pct(r.get("gross_margin"))}</td>'
            f'<td style="padding:9px 12px;border-bottom:1px solid #f3f4f6;text-align:right;'
            f'font-size:0.82rem;color:#374151;font-variant-numeric:tabular-nums">'
            f'{_fmt_pct(r.get("roic"))}</td>'
            f'<td style="padding:9px 12px;border-bottom:1px solid #f3f4f6;text-align:right;'
            f'font-size:0.82rem;color:#374151;font-variant-numeric:tabular-nums">'
            f'{_fmt_pct(r.get("fcf_yield"))}</td>'
            f'<td style="padding:9px 12px;border-bottom:1px solid #f3f4f6;text-align:right;'
            f'font-size:0.82rem;color:#374151;font-variant-numeric:tabular-nums">'
            f'{_fmt_pct(r.get("revenue_growth_yoy"))}</td>'
            f'<td style="padding:9px 12px;border-bottom:1px solid #f3f4f6;text-align:right;'
            f'font-size:0.82rem;color:#374151;font-variant-numeric:tabular-nums">'
            f'{_fmt_mult(r.get("net_debt_ebitda"))}</td>'
            f'<td style="padding:9px 12px;border-bottom:1px solid #f3f4f6">'
            f'{_status_tag(r["status"])}</td>'
            f'<td style="padding:9px 12px;border-bottom:1px solid #f3f4f6"></td>'
            f'</tr>'
        )

    st.markdown(
        f'<div style="background:#ffffff;border:1px solid #e8eaed;border-radius:8px;'
        f'overflow:auto">'
        f'<table style="width:100%;border-collapse:collapse">'
        f'<thead><tr>{TH}</tr></thead>'
        f'<tbody>{ROWS_HTML}</tbody>'
        f'</table></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div style="height:24px"></div>', unsafe_allow_html=True)

    # ── Expandable row detail ─────────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:0.7rem;font-weight:600;text-transform:uppercase;'
        'letter-spacing:0.09em;color:#9ca3af;margin-bottom:10px">Company Detail</div>',
        unsafe_allow_html=True,
    )

    selected = st.selectbox(
        "Select company",
        options=["— select —"] + [f"{r['ticker']}  {r.get('name','')}" for r in rows],
        label_visibility="collapsed",
    )

    if selected and selected != "— select —":
        ticker = selected.split()[0]
        row = next((r for r in rows if r["ticker"] == ticker), None)
        if row:
            st.markdown(f"""
            <div style="background:#ffffff;border:1px solid #e8eaed;border-radius:8px;
                        padding:24px 28px;margin-bottom:12px">
              <div style="display:flex;align-items:baseline;gap:12px;margin-bottom:16px;
                          flex-wrap:wrap">
                <span style="font-size:1.3rem;font-weight:700;color:#111827">{row['ticker']}</span>
                <span style="font-size:0.92rem;color:#374151">{row.get('name','')}</span>
                <span style="font-size:0.78rem;color:#9ca3af">{row.get('exchange','')} · {row.get('country','')}</span>
                {('<span style="background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;'
                  'padding:2px 8px;border-radius:4px;font-size:0.74rem;font-weight:600">Founder-Led</span>'
                  if row.get('founder_led') else '')}
              </div>
              <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px">
                {_kpi("Fit Score",   f"{row['fit_score']:.0f}", "/ 100")}
                {_kpi("Risk Score",  f"{row['risk_score']:.0f}", "/ 100")}
                {_kpi("Rank Score",  f"{row['rank_score']:.1f}", "")}
                {_kpi("Market Cap",  _fmt_cap(row.get('market_cap')), "")}
              </div>
              <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px">
                {_kpi("Gross Margin",  _fmt_pct(row.get('gross_margin')), "")}
                {_kpi("ROIC",          _fmt_pct(row.get('roic')), "")}
                {_kpi("FCF Yield",     _fmt_pct(row.get('fcf_yield')), "")}
                {_kpi("Rev Growth YoY",_fmt_pct(row.get('revenue_growth_yoy')), "")}
              </div>
            </div>
            """, unsafe_allow_html=True)

            # Investment Memo — always shown
            memo = row.get("memo_text")
            pc   = row.get("portfolio_comparison") or {}
            sd   = row.get("scoring_detail") or {}

            st.markdown(
                '<div style="font-size:0.67rem;font-weight:600;text-transform:uppercase;'
                'letter-spacing:0.08em;color:#9ca3af;margin:16px 0 8px">Investment Memo</div>',
                unsafe_allow_html=True,
            )
            if memo:
                st.markdown(
                    f'<div style="background:#f9fafb;border:1px solid #e8eaed;border-radius:6px;'
                    f'padding:16px 20px;font-size:0.84rem;line-height:1.75;color:#374151">'
                    f'{memo.replace(chr(10), "<br>")}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div style="background:#f9fafb;border:1px solid #e8eaed;border-radius:6px;'
                    'padding:16px 20px;font-size:0.84rem;color:#9ca3af">'
                    'No memo generated — run screening again to generate comparison memos.</div>',
                    unsafe_allow_html=True,
                )

            # Scoring breakdown
            criteria = sd.get("criteria", [])
            if criteria:
                with st.expander("Scoring breakdown"):
                    cols = st.columns(2)
                    fit_c  = [c for c in criteria if c.get("max_score", 0) > 0 and c.get("name") not in ("leverage","geographic_risk","earnings_quality")]
                    risk_c = [c for c in criteria if c.get("name") in ("leverage","geographic_risk","earnings_quality","coverage_risk")]
                    for i, c in enumerate(fit_c):
                        mx = c.get("max_score", 1) or 1
                        sc = c.get("score", 0)
                        pct = min(100, int(sc / mx * 100))
                        bar_c = "#059669" if pct >= 70 else ("#d97706" if pct >= 40 else "#dc2626")
                        with cols[i % 2]:
                            st.markdown(
                                f'<div style="margin-bottom:10px">'
                                f'<div style="display:flex;justify-content:space-between;'
                                f'font-size:0.75rem;color:#374151;margin-bottom:3px">'
                                f'<span>{c["name"].replace("_"," ").title()}</span>'
                                f'<span style="font-weight:600">{sc:.0f}/{mx:.0f}</span></div>'
                                f'<div style="background:#e8eaed;border-radius:2px;height:4px">'
                                f'<div style="background:{bar_c};width:{pct}%;height:4px;border-radius:2px"></div>'
                                f'</div>'
                                f'<div style="font-size:0.7rem;color:#9ca3af;margin-top:2px">'
                                f'{c.get("evidence","")}</div></div>',
                                unsafe_allow_html=True,
                            )

            # Actions
            _REJECT_REASONS = [
                "Too expensive", "Weak moat / low quality", "Poor unit economics",
                "No insider alignment", "Too well-covered", "Limited growth runway",
                "Too risky", "Already known",
            ]
            ac1, ac2, ac3, _ = st.columns([1, 1, 1, 4])
            with ac1:
                if st.button("Research Now", key=f"res_{ticker}", use_container_width=True):
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
                if st.button("Reject", key=f"rej_toggle_{ticker}", use_container_width=True):
                    k = f"rej_open_{ticker}"
                    st.session_state[k] = not st.session_state.get(k, False)

            if st.session_state.get(f"rej_open_{ticker}"):
                rr1, rr2, rr3 = st.columns([3, 3, 1])
                with rr1:
                    reason = st.selectbox("Reason", _REJECT_REASONS, key=f"reason_{ticker}", label_visibility="collapsed")
                with rr2:
                    notes = st.text_input("Note", placeholder="Optional note", key=f"rnote_{ticker}", label_visibility="collapsed")
                with rr3:
                    if st.button("Confirm", key=f"rej_confirm_{ticker}", use_container_width=True):
                        rec_id = _run(_get_rec_id(ticker))
                        if rec_id:
                            _run(_submit_feedback((rec_id, ticker), "reject", reason))
                            st.session_state[f"rej_open_{ticker}"] = False
                            st.rerun()


def _kpi(label: str, value: str, sub: str) -> str:
    sub_html = f'<div style="font-size:0.72rem;color:#9ca3af;margin-top:2px">{sub}</div>' if sub else ""
    return (
        f'<div style="background:#f9fafb;border:1px solid #e8eaed;border-radius:6px;padding:12px 14px">'
        f'<div style="font-size:0.67rem;font-weight:600;text-transform:uppercase;'
        f'letter-spacing:0.08em;color:#9ca3af;margin-bottom:5px">{label}</div>'
        f'<div style="font-size:1.15rem;font-weight:700;color:#111827;'
        f'font-variant-numeric:tabular-nums">{value}</div>'
        f'{sub_html}</div>'
    )
