"""
Insider Buying page — cluster buys, conviction-ranked purchases, full Form 4 feed.
"""

from __future__ import annotations

import asyncio

import streamlit as st

from src.dashboard.components.db_helpers import (
    get_all_insider_purchases,
    get_cluster_buys,
    get_top_conviction_purchases,
    submit_feedback,
    get_company_recommendation,
)
from src.dashboard.components.styles import (
    apply_theme,
    fmt_dollar,
    score_pill,
    section_header,
    empty_state,
    BG_CARD, BG_CARD_ALT, BORDER, GOLD, GREEN, RED, AMBER, TEXT_PRIMARY, TEXT_MUTED, TEXT_DIM,
)


def _conviction_pill(score: float) -> str:
    color = GREEN if score >= 70 else (AMBER if score >= 40 else RED)
    return (
        f'<span style="background:{color}22;color:{color};border:1px solid {color}44;'
        f'padding:2px 9px;border-radius:8px;font-size:0.78rem;font-weight:700">'
        f'{score:.0f}</span>'
    )


def _cluster_badge() -> str:
    return (
        f'<span style="background:{GOLD}22;color:{GOLD};border:1px solid {GOLD}44;'
        f'padding:1px 7px;border-radius:6px;font-size:0.7rem;font-weight:700">CLUSTER</span>'
    )


def render() -> None:
    apply_theme()

    # ── Header ────────────────────────────────────────────────────────────────
    hc1, hc2 = st.columns([4, 2])
    with hc1:
        st.markdown(
            f'<h1 style="margin:0;color:{TEXT_PRIMARY}">Insider Buying</h1>'
            f'<div style="color:{TEXT_MUTED};font-size:0.78rem;margin-top:2px">'
            f'Open-market share purchases by officers and directors (SEC Form 4)</div>',
            unsafe_allow_html=True,
        )
    with hc2:
        lookback = st.selectbox("Lookback", [14, 30, 60, 90], index=1, format_func=lambda x: f"{x} days", label_visibility="collapsed")
        scan_col, _ = st.columns([1, 1])
        with scan_col:
            if st.button("Scan Now", key="scan_now", use_container_width=True):
                st.info("Form 4 scan triggered. Results will update after ingestion completes.")

    st.markdown(f'<div style="height:12px"></div>', unsafe_allow_html=True)

    # ── Load data ─────────────────────────────────────────────────────────────
    clusters = asyncio.run(get_cluster_buys(lookback_days=min(lookback, 14)))
    top_conviction = asyncio.run(get_top_conviction_purchases(limit=20, lookback_days=lookback))
    all_purchases = asyncio.run(get_all_insider_purchases(lookback_days=lookback))

    # ── Section 1: Cluster Buys ───────────────────────────────────────────────
    st.markdown(
        section_header("Cluster Buys", "Two or more insiders buying the same stock within 14 days"),
        unsafe_allow_html=True,
    )

    if not clusters:
        empty_state("🔍", f"No cluster buys detected in the last {min(lookback, 14)} days.")
    else:
        for c in clusters:
            ticker = c["ticker"]
            insider_list = ", ".join(c["insiders"][:4])
            total_val = fmt_dollar(c["total_value"])
            n_insiders = len(c["insiders"])
            dates = ", ".join(sorted(set(c.get("dates", [])))[:3])

            st.markdown(
                f'<div class="ph-cluster-card">'
                f'<div style="display:flex;justify-content:space-between;align-items:flex-start">'
                f'<div>'
                f'  <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">'
                f'    <span style="color:{TEXT_PRIMARY};font-size:1.1rem;font-weight:800">{ticker}</span>'
                f'    {_cluster_badge()}'
                f'    <span style="color:{TEXT_MUTED};font-size:0.78rem">{n_insiders} insiders · {total_val} total</span>'
                f'  </div>'
                f'  <div style="color:{TEXT_MUTED};font-size:0.78rem">{insider_list}</div>'
                f'  <div style="color:{TEXT_DIM};font-size:0.72rem;margin-top:4px">Dates: {dates}</div>'
                f'</div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            cc1, cc2, cc3 = st.columns([1, 1, 8])
            with cc1:
                if st.button("Research", key=f"cluster_research_{ticker}", use_container_width=True):
                    rec = asyncio.run(get_company_recommendation(ticker))
                    if rec:
                        asyncio.run(submit_feedback(rec["id"], ticker, "research_now", notes="Cluster insider buy signal"))
                        st.success(f"{ticker} → Research Now")
                        st.rerun()
                    else:
                        st.warning(f"No recommendation found for {ticker}. Run scoring first.")
            with cc2:
                if st.button("Watch", key=f"cluster_watch_{ticker}", use_container_width=True):
                    rec = asyncio.run(get_company_recommendation(ticker))
                    if rec:
                        asyncio.run(submit_feedback(rec["id"], ticker, "watch", notes="Cluster insider buy signal"))
                        st.info(f"{ticker} → Watchlist")
                        st.rerun()

    st.markdown(f'<div style="height:20px"></div>', unsafe_allow_html=True)

    # ── Section 2: Highest Conviction ─────────────────────────────────────────
    st.markdown(
        section_header("Highest Conviction", "Ranked by conviction score: dollar size × role weight × cluster bonus"),
        unsafe_allow_html=True,
    )

    if not top_conviction:
        empty_state("📋", f"No insider purchases found in the last {lookback} days.")
    else:
        # Table header
        st.markdown(
            f"""
            <div style="display:grid;
                        grid-template-columns:44px 80px 1fr 120px 80px 90px 90px 80px 100px 160px;
                        gap:6px;padding:7px 12px;
                        background:{BG_CARD_ALT};border:1px solid {BORDER};border-radius:8px 8px 0 0">
              {"".join(
                f'<div style="color:{TEXT_MUTED};font-size:0.67rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em">{h}</div>'
                for h in ["#","Ticker","Insider","Title","Shares","Value","Score","Cluster","Date","Action"]
              )}
            </div>
            """,
            unsafe_allow_html=True,
        )

        for p in top_conviction:
            cluster_html = _cluster_badge() if p["is_cluster"] else "—"
            conviction_html = _conviction_pill(p["conviction_score"])
            total_val = fmt_dollar(p["total_value"])
            shares = f'{p["shares"]:,}' if p.get("shares") else "—"
            filing_link = (
                f'<a href="{p["form4_url"]}" target="_blank" style="color:{GOLD};font-size:0.72rem">Form 4 ↗</a>'
                if p.get("form4_url") else ""
            )

            st.markdown(
                f"""
                <div style="display:grid;
                            grid-template-columns:44px 80px 1fr 120px 80px 90px 90px 80px 100px 160px;
                            gap:6px;padding:9px 12px;
                            background:{BG_CARD};border:1px solid {BORDER};border-top:none;
                            align-items:center">
                  <div style="color:{TEXT_MUTED};font-size:0.8rem;font-weight:600">{p["rank"]}</div>
                  <div style="color:{TEXT_PRIMARY};font-size:0.88rem;font-weight:700">{p["ticker"]}</div>
                  <div>
                    <div style="color:{TEXT_PRIMARY};font-size:0.82rem">{p["insider_name"]}</div>
                    <div style="color:{TEXT_MUTED};font-size:0.72rem">{p.get("name","")}</div>
                  </div>
                  <div style="color:{TEXT_MUTED};font-size:0.78rem">{p["insider_title"]}</div>
                  <div style="color:{TEXT_MUTED};font-size:0.82rem">{shares}</div>
                  <div style="color:{TEXT_PRIMARY};font-size:0.85rem;font-weight:600">{total_val}</div>
                  <div>{conviction_html}</div>
                  <div>{cluster_html}</div>
                  <div style="color:{TEXT_DIM};font-size:0.75rem">{p["transaction_date"]}</div>
                  <div style="font-size:0.72rem">{filing_link}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Action buttons
            ab1, ab2, ab3 = st.columns([1, 1, 8])
            with ab1:
                if st.button("Research", key=f"cv_research_{p['id']}", use_container_width=True):
                    rec = asyncio.run(get_company_recommendation(p["ticker"]))
                    if rec:
                        asyncio.run(submit_feedback(rec["id"], p["ticker"], "research_now", notes=f"Insider buy: {p['insider_name']}"))
                        st.success(f"{p['ticker']} → Research Now")
                        st.rerun()
            with ab2:
                if st.button("Watch", key=f"cv_watch_{p['id']}", use_container_width=True):
                    rec = asyncio.run(get_company_recommendation(p["ticker"]))
                    if rec:
                        asyncio.run(submit_feedback(rec["id"], p["ticker"], "watch", notes=f"Insider buy: {p['insider_name']}"))
                        st.info(f"{p['ticker']} → Watchlist")
                        st.rerun()

    # ── Section 3: Full Feed ──────────────────────────────────────────────────
    with st.expander(f"Full Feed — all {len(all_purchases)} purchases in last {lookback} days"):
        if not all_purchases:
            empty_state("📋", "No insider purchases in this period.")
        else:
            import pandas as pd
            df = pd.DataFrame([
                {
                    "Ticker": p["ticker"],
                    "Insider": p["insider_name"],
                    "Title": p["insider_title"],
                    "Shares": p.get("shares"),
                    "Price": f'${p["price_per_share"]:.2f}' if p.get("price_per_share") else "—",
                    "Total Value": fmt_dollar(p["total_value"]),
                    "Conviction": f'{p["conviction_score"]:.0f}',
                    "Cluster": "Yes" if p["is_cluster"] else "—",
                    "Date": p["transaction_date"],
                }
                for p in all_purchases
            ])
            st.dataframe(df, use_container_width=True, hide_index=True)
