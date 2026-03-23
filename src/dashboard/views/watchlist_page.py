"""
Watchlist page — companies being tracked with current scores and notes.
"""

from __future__ import annotations

import asyncio

import streamlit as st

from src.dashboard.components.db_helpers import (
    get_watchlist_with_scores,
    remove_from_watchlist,
    submit_feedback,
)
from src.dashboard.components.styles import (
    apply_theme,
    fmt_market_cap,
    score_pill,
    empty_state,
    BG_CARD, BG_CARD_ALT, BORDER, GOLD, GREEN, RED, TEXT_PRIMARY, TEXT_MUTED, TEXT_DIM,
)


def render() -> None:
    apply_theme()

    hc1, hc2 = st.columns([4, 2])
    with hc1:
        st.markdown(
            f'<h1 style="margin:0;color:{TEXT_PRIMARY}">Watchlist</h1>'
            f'<div style="color:{TEXT_MUTED};font-size:0.78rem;margin-top:2px">'
            f'Companies you are tracking for catalysts or better entry points</div>',
            unsafe_allow_html=True,
        )

    entries = asyncio.run(get_watchlist_with_scores())

    if not entries:
        empty_state(
            "👁",
            'No companies on your watchlist. Click "Watch" on any ranking to add one.',
        )
        return

    # Count badge
    st.markdown(
        f'<div style="color:{TEXT_MUTED};font-size:0.82rem;margin-bottom:16px">'
        f'{len(entries)} companies being tracked</div>',
        unsafe_allow_html=True,
    )

    # ── Column header ─────────────────────────────────────────────────────────
    st.markdown(
        f"""
        <div style="display:grid;grid-template-columns:100px 1fr 90px 80px 80px 1fr 200px;
                    gap:8px;padding:6px 12px;
                    background:{BG_CARD_ALT};border:1px solid {BORDER};
                    border-radius:8px 8px 0 0">
          <div style="color:{TEXT_MUTED};font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em">Ticker</div>
          <div style="color:{TEXT_MUTED};font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em">Company</div>
          <div style="color:{TEXT_MUTED};font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em">Mkt Cap</div>
          <div style="color:{TEXT_MUTED};font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em">Fit</div>
          <div style="color:{TEXT_MUTED};font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em">Risk</div>
          <div style="color:{TEXT_MUTED};font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em">Notes / Trigger</div>
          <div style="color:{TEXT_MUTED};font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em">Actions</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for e in entries:
        eid = e["id"]
        ticker = e["ticker"]
        fit = e.get("fit_score")
        risk = e.get("risk_score")
        fit_pill = score_pill(fit) if fit is not None else '<span style="color:#484f58">—</span>'
        risk_pill = score_pill(risk, inverted=True) if risk is not None else '<span style="color:#484f58">—</span>'
        mkt_cap = fmt_market_cap(e.get("market_cap_usd"))
        exch = e.get("exchange") or ""
        notes = e.get("trigger_condition") or "—"
        added = e.get("added_at", "—")

        st.markdown(
            f"""
            <div style="display:grid;grid-template-columns:100px 1fr 90px 80px 80px 1fr 200px;
                        gap:8px;padding:10px 12px;
                        background:{BG_CARD};border:1px solid {BORDER};border-top:none;
                        align-items:center">
              <div>
                <span style="color:{TEXT_PRIMARY};font-size:0.9rem;font-weight:700">{ticker}</span>
                <div style="color:{TEXT_DIM};font-size:0.7rem">{added}</div>
              </div>
              <div>
                <div style="color:{TEXT_PRIMARY};font-size:0.82rem">{e.get("name","")}</div>
                <div style="color:{TEXT_MUTED};font-size:0.72rem">{exch}</div>
              </div>
              <div style="color:{TEXT_MUTED};font-size:0.82rem">{mkt_cap}</div>
              <div>{fit_pill}</div>
              <div>{risk_pill}</div>
              <div style="color:{TEXT_MUTED};font-size:0.78rem;line-height:1.4">{notes}</div>
              <div></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Action buttons — placed after HTML row
        act_cols = st.columns([1, 1, 1, 1, 1, 1, 2, 2, 2, 2])
        rec_id = e.get("rec_id")

        with act_cols[6]:
            if st.button("Full Detail →", key=f"wl_detail_{eid}", use_container_width=True):
                st.session_state.detail_ticker = ticker
                st.session_state.page = "Company Detail"
                st.rerun()

        with act_cols[7]:
            if rec_id and st.button("Research Now", key=f"wl_research_{eid}", use_container_width=True):
                asyncio.run(submit_feedback(rec_id, ticker, "research_now"))
                st.success(f"{ticker} → Research Now")
                st.rerun()

        with act_cols[8]:
            if st.button("Remove", key=f"wl_remove_{eid}", use_container_width=True):
                asyncio.run(remove_from_watchlist(eid))
                st.rerun()
