"""
Rankings page — top-ranked companies with score pills, dimension breakdown,
and inline reject reason modal.
"""

from __future__ import annotations

import asyncio

import streamlit as st

from src.dashboard.components.db_helpers import get_top_recommendations, submit_feedback
from src.dashboard.components.styles import (
    apply_theme,
    action_badge,
    fmt_market_cap,
    fmt_pct,
    score_pill,
    score_color,
    empty_state,
    BG_CARD, BG_CARD_ALT, BG_PAGE, BORDER, ACCENT, ACCENT2,
    GREEN, RED, AMBER, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, TEXT_DIM,
)
GOLD = ACCENT

_REJECT_REASONS = [
    "Too expensive",
    "Weak moat / low quality",
    "Poor unit economics",
    "No insider alignment",
    "Too well-covered",
    "Limited growth runway",
    "Too risky",
    "Already known / duplicate",
]

_DIMENSION_LABELS = {
    "founder_ownership":    "Founder",
    "business_quality":     "Quality",
    "unit_economics":       "Unit Econ",
    "valuation_asymmetry":  "Valuation",
    "information_edge":     "Info Edge",
    "scalability":          "Scale",
}

_SECTOR_MAP = {
    "10": "Energy", "15": "Materials", "20": "Industrials",
    "25": "Cons. Disc.", "30": "Cons. Stap.", "35": "Health Care",
    "40": "Financials", "45": "IT", "50": "Comm. Svc.",
    "55": "Utilities", "60": "Real Estate",
}


def _dimension_pills(scoring_detail: dict | None) -> str:
    if not scoring_detail:
        return '<span style="color:#484f58;font-size:0.72rem">No score detail</span>'
    criteria = scoring_detail.get("criteria", [])
    if not criteria:
        return ""
    pills = []
    for c in criteria:
        if not isinstance(c, dict):
            continue
        name = c.get("name", "")
        score = float(c.get("score", 0))
        max_s = float(c.get("max_score", 20))
        pct = score / max_s * 100 if max_s else 0
        color = score_color(pct)
        short = _DIMENSION_LABELS.get(name, name[:6])
        pills.append(
            f'<span title="{name}: {score:.0f}/{max_s:.0f}" '
            f'style="background:{color}22;color:{color};border:1px solid {color}44;'
            f'padding:1px 6px;border-radius:6px;font-size:0.68rem;font-weight:600;'
            f'white-space:nowrap;margin-right:3px">{short}</span>'
        )
    return "".join(pills)


def _founder_badge(is_founder: bool | None) -> str:
    if is_founder:
        return (
            f'<span style="background:{GOLD}22;color:{GOLD};border:1px solid {GOLD}44;'
            f'padding:1px 7px;border-radius:6px;font-size:0.68rem;font-weight:600">Founder-Led</span>'
        )
    return ""


def render() -> None:
    apply_theme()

    # ── Page header ───────────────────────────────────────────────────────────
    hcol1, hcol2 = st.columns([4, 2])
    with hcol1:
        st.markdown(
            f'<h1 style="margin:0;color:{TEXT_PRIMARY}">Rankings</h1>'
            f'<div style="color:{TEXT_MUTED};font-size:0.78rem;margin-top:2px">'
            f'Top-ranked companies by Fit & Risk composite score</div>',
            unsafe_allow_html=True,
        )
    with hcol2:
        top_n = st.selectbox("Show top", [10, 25, 50, 100], index=1, label_visibility="collapsed")

    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)

    # ── Filter bar ────────────────────────────────────────────────────────────
    fc1, fc2, fc3, fc4 = st.columns([2, 2, 2, 2])
    with fc1:
        search = st.text_input("Search ticker / name", placeholder="e.g. AAPL", label_visibility="collapsed")
    with fc2:
        sector_filter = st.selectbox(
            "Sector",
            ["All Sectors"] + list(_SECTOR_MAP.values()),
            label_visibility="collapsed",
        )
    with fc3:
        min_fit = st.selectbox("Min Fit Score", ["Any", "≥ 40", "≥ 50", "≥ 60", "≥ 70"], label_visibility="collapsed")
    with fc4:
        status_filter = st.selectbox(
            "Status",
            ["All Statuses", "Pending", "Researching", "Watched", "Rejected"],
            label_visibility="collapsed",
        )

    st.markdown(f'<hr style="border:none;border-top:1px solid {BORDER};margin:10px 0 16px">', unsafe_allow_html=True)

    # ── Load data ─────────────────────────────────────────────────────────────
    recs = asyncio.run(get_top_recommendations(limit=top_n))

    if not recs:
        empty_state("📊", "No recommendations yet. Run the scoring pipeline from the Pipeline page.")
        return

    # Apply filters
    min_fit_val = {"Any": 0, "≥ 40": 40, "≥ 50": 50, "≥ 60": 60, "≥ 70": 70}.get(min_fit, 0)
    if search:
        s = search.upper()
        recs = [r for r in recs if s in r["ticker"] or s in r.get("name", "").upper()]
    if sector_filter != "All Sectors":
        recs = [r for r in recs if _SECTOR_MAP.get(r.get("gics_sector", ""), "") == sector_filter]
    if min_fit_val:
        recs = [r for r in recs if r["fit_score"] >= min_fit_val]
    if status_filter != "All Statuses":
        recs = [r for r in recs if r["status"] == status_filter.lower()]

    if not recs:
        empty_state("🔍", "No companies match the current filters.")
        return

    # ── Column header ─────────────────────────────────────────────────────────
    st.markdown(
        f"""
        <div style="display:grid;grid-template-columns:44px 1fr 90px 80px 80px 80px 1fr 180px;
                    gap:8px;padding:6px 12px;
                    background:{BG_CARD_ALT};border:1px solid {BORDER};
                    border-radius:8px 8px 0 0;margin-bottom:0">
          <div style="color:{TEXT_MUTED};font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em">#</div>
          <div style="color:{TEXT_MUTED};font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em">Company</div>
          <div style="color:{TEXT_MUTED};font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em">Mkt Cap</div>
          <div style="color:{TEXT_MUTED};font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em">Fit</div>
          <div style="color:{TEXT_MUTED};font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em">Risk</div>
          <div style="color:{TEXT_MUTED};font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em">Rank</div>
          <div style="color:{TEXT_MUTED};font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em">Dimensions</div>
          <div style="color:{TEXT_MUTED};font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em">Action</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Rows ──────────────────────────────────────────────────────────────────
    for rec in recs:
        rid = rec["id"]
        ticker = rec["ticker"]
        rank = rec.get("rank") or "—"
        rank_is_top = isinstance(rank, int) and rank <= 3
        rank_cls = "ph-rank-top" if rank_is_top else "ph-rank"
        fit = rec["fit_score"]
        risk = rec["risk_score"]
        rank_score = rec["rank_score"]

        fit_pill = score_pill(fit)
        risk_pill = score_pill(risk, inverted=True)
        rank_pill = score_pill(rank_score)
        dim_pills = _dimension_pills(rec.get("scoring_detail"))
        founder_badge = _founder_badge(rec.get("is_founder_led"))
        mkt_cap = fmt_market_cap(rec.get("market_cap_usd"))
        exch = rec.get("exchange") or ""

        st.markdown(
            f"""
            <div style="display:grid;grid-template-columns:44px 1fr 90px 80px 80px 80px 1fr 180px;
                        gap:8px;padding:10px 12px;
                        background:{BG_CARD};border:1px solid {BORDER};border-top:none;
                        align-items:center">
              <div><span class="{rank_cls}">{rank}</span></div>
              <div>
                <div style="display:flex;align-items:center;gap:8px">
                  <span style="color:{TEXT_PRIMARY};font-size:0.92rem;font-weight:700">{ticker}</span>
                  {founder_badge}
                </div>
                <div style="color:{TEXT_MUTED};font-size:0.75rem;margin-top:1px">{rec.get("name","")} {f"· {exch}" if exch else ""}</div>
              </div>
              <div style="color:{TEXT_MUTED};font-size:0.82rem">{mkt_cap}</div>
              <div>{fit_pill}</div>
              <div>{risk_pill}</div>
              <div>{rank_pill}</div>
              <div style="line-height:2">{dim_pills}</div>
              <div></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Action buttons row (native Streamlit — placed below the HTML row)
        act_cols = st.columns([1, 1, 1, 1, 1, 1, 3, 3, 3, 3])

        with act_cols[7]:
            if st.button("Research", key=f"research_{rid}", use_container_width=True):
                asyncio.run(submit_feedback(rid, ticker, "research_now"))
                st.success(f"{ticker} → Research Now")
                st.rerun()

        with act_cols[8]:
            if st.button("Watch", key=f"watch_{rid}", use_container_width=True):
                asyncio.run(submit_feedback(rid, ticker, "watch"))
                st.info(f"{ticker} → Watchlist")
                st.rerun()

        with act_cols[9]:
            if st.button("Reject ▾", key=f"reject_toggle_{rid}", use_container_width=True):
                key = f"show_reject_{rid}"
                st.session_state[key] = not st.session_state.get(key, False)

        # Reject reason inline modal
        if st.session_state.get(f"show_reject_{rid}"):
            with st.container():
                st.markdown(
                    f'<div style="background:{BG_CARD};border:1px solid {BORDER};'
                    f'border-left:3px solid {RED};border-radius:0 0 8px 8px;padding:12px 16px;'
                    f'margin-bottom:2px">',
                    unsafe_allow_html=True,
                )
                rr1, rr2, rr3 = st.columns([3, 3, 1])
                with rr1:
                    reason = st.selectbox(
                        "Reject reason",
                        _REJECT_REASONS,
                        key=f"reason_{rid}",
                        label_visibility="collapsed",
                    )
                with rr2:
                    notes = st.text_input(
                        "Notes (optional)",
                        placeholder="Optional note...",
                        key=f"notes_{rid}",
                        label_visibility="collapsed",
                    )
                with rr3:
                    if st.button("Confirm", key=f"confirm_reject_{rid}", use_container_width=True):
                        asyncio.run(
                            submit_feedback(rid, ticker, "reject", reject_reason=reason, notes=notes or None)
                        )
                        st.session_state[f"show_reject_{rid}"] = False
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

        # Expandable memo
        if rec.get("memo_text"):
            with st.expander(f"View Investment Memo — {ticker}"):
                st.markdown(
                    f'<div style="font-size:0.88rem;line-height:1.65;color:{TEXT_PRIMARY}">'
                    f'{rec["memo_text"]}</div>',
                    unsafe_allow_html=True,
                )
                if rec.get("citations"):
                    st.markdown(
                        f'<div style="margin-top:16px;padding-top:12px;'
                        f'border-top:1px solid {BORDER}">',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f'<div style="color:{TEXT_MUTED};font-size:0.72rem;font-weight:700;'
                        f'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px">'
                        f'Sources</div>',
                        unsafe_allow_html=True,
                    )
                    for i, cit in enumerate(rec["citations"], 1):
                        if isinstance(cit, dict):
                            doc_type = cit.get("doc_type", "")
                            title = cit.get("title", "")
                            url = cit.get("url", "")
                            link = f'<a href="{url}" target="_blank" style="color:{GOLD}">{title or url}</a>' if url else title
                            st.markdown(
                                f'<div style="font-size:0.78rem;color:{TEXT_MUTED};margin-bottom:4px">'
                                f'[{i}] {doc_type} — {link}</div>',
                                unsafe_allow_html=True,
                            )
                    st.markdown("</div>", unsafe_allow_html=True)

        # Navigate to full detail
        nav_col = st.columns([8, 2])[1]
        with nav_col:
            if st.button("Full Detail →", key=f"detail_{rid}", use_container_width=True):
                st.session_state.detail_ticker = ticker
                st.session_state.page = "Company Detail"
                st.rerun()

    st.markdown(
        f'<div style="color:{TEXT_DIM};font-size:0.72rem;text-align:right;margin-top:8px">'
        f'Showing {len(recs)} companies</div>',
        unsafe_allow_html=True,
    )
