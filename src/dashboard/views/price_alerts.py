"""
Price Alerts page — set price targets, triage triggered alerts, view history.
"""

from __future__ import annotations

import asyncio
import datetime as dt

import streamlit as st

from src.dashboard.components.db_helpers import (
    create_price_alert,
    dismiss_alert,
    get_active_price_targets,
    get_alert_history,
    get_triggered_alerts,
    submit_feedback,
    get_company_recommendation,
)
from src.dashboard.components.styles import (
    apply_theme,
    fmt_dollar,
    section_header,
    empty_state,
    BG_CARD, BG_CARD_ALT, BORDER, GOLD, GREEN, RED, AMBER, TEXT_PRIMARY, TEXT_MUTED, TEXT_DIM,
)


def render() -> None:
    apply_theme()

    # ── Header ────────────────────────────────────────────────────────────────
    hc1, hc2 = st.columns([4, 2])
    with hc1:
        st.markdown(
            f'<h1 style="margin:0;color:{TEXT_PRIMARY}">Price Alerts</h1>'
            f'<div style="color:{TEXT_MUTED};font-size:0.78rem;margin-top:2px">'
            f'Set price targets and get notified when stocks reach your entry level</div>',
            unsafe_allow_html=True,
        )
    with hc2:
        if st.button("+ Set Price Target", key="open_new_alert", use_container_width=True):
            st.session_state["new_alert_open"] = not st.session_state.get("new_alert_open", False)

    # ── New alert form ────────────────────────────────────────────────────────
    if st.session_state.get("new_alert_open"):
        st.markdown(
            f'<div style="background:{BG_CARD};border:1px solid {GOLD}44;border-left:4px solid {GOLD};'
            f'border-radius:8px;padding:16px 20px;margin:12px 0">',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="color:{GOLD};font-size:0.8rem;font-weight:700;margin-bottom:12px">'
            f'NEW PRICE TARGET</div>',
            unsafe_allow_html=True,
        )
        na1, na2, na3, na4, na5 = st.columns([1, 1, 2, 1, 1])
        with na1:
            new_ticker = st.text_input("Ticker", placeholder="AAPL", key="new_ticker").upper().strip()
        with na2:
            new_price = st.number_input("Target Price ($)", min_value=0.01, value=50.0, step=0.5, key="new_price")
        with na3:
            new_notes = st.text_input("Rationale / Notes", placeholder="Wait for pullback to 15x FCF", key="new_notes")
        with na4:
            new_expiry = st.date_input("Expires (optional)", value=None, key="new_expiry")
        with na5:
            st.markdown('<div style="height:26px"></div>', unsafe_allow_html=True)
            if st.button("Create Alert", key="create_alert", use_container_width=True):
                if new_ticker and new_price > 0:
                    expiry = new_expiry if new_expiry else None
                    asyncio.run(create_price_alert(new_ticker, new_price, new_notes, expiry))
                    st.session_state["new_alert_open"] = False
                    st.success(f"Price target set: {new_ticker} @ ${new_price:.2f}")
                    st.rerun()
                else:
                    st.error("Ticker and target price are required.")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(f'<div style="height:12px"></div>', unsafe_allow_html=True)

    # ── Load data ─────────────────────────────────────────────────────────────
    triggered = asyncio.run(get_triggered_alerts())
    active = asyncio.run(get_active_price_targets())

    # ── Section 1: Triggered Alerts ───────────────────────────────────────────
    if triggered:
        st.markdown(
            section_header(f"Triggered Alerts ({len(triggered)})", "These stocks have hit or dropped below your target price"),
            unsafe_allow_html=True,
        )

        for a in triggered:
            ticker = a["ticker"]
            pct_below = a.get("pct_below")
            pct_str = f"{pct_below:.1f}% below target" if pct_below is not None else ""
            triggered_price = fmt_dollar(a.get("triggered_price"))
            target_price = fmt_dollar(a["target_price"])

            st.markdown(
                f'<div class="ph-alert-triggered">'
                f'<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px">'
                f'<div>'
                f'  <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">'
                f'    <span style="color:{TEXT_PRIMARY};font-size:1.05rem;font-weight:800">{ticker}</span>'
                f'    <span style="color:{RED};font-size:0.8rem;font-weight:600">{a.get("name","")}</span>'
                f'  </div>'
                f'  <div style="color:{TEXT_MUTED};font-size:0.8rem">'
                f'    Target: <span style="color:{TEXT_PRIMARY};font-weight:600">{target_price}</span>'
                f'    &nbsp;·&nbsp; Triggered at: <span style="color:{RED};font-weight:600">{triggered_price}</span>'
                f'    {(" &nbsp;·&nbsp; <span style=color:"+RED+";font-weight:600>"+pct_str+"</span>") if pct_str else ""}'
                f'  </div>'
                f'  {"<div style=color:"+TEXT_DIM+";font-size:0.72rem;margin-top:4px>"+a.get(chr(110)+"otes","")+"</div>" if a.get("notes") else ""}'
                f'  <div style="color:{TEXT_DIM};font-size:0.72rem;margin-top:4px">Triggered: {a.get("triggered_at","—")}</div>'
                f'</div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            ac1, ac2, ac3, ac4 = st.columns([1, 1, 1, 6])
            with ac1:
                if st.button("Research Now", key=f"trig_research_{a['id']}", use_container_width=True):
                    rec = asyncio.run(get_company_recommendation(ticker))
                    if rec:
                        asyncio.run(submit_feedback(rec["id"], ticker, "research_now", notes=f"Price alert triggered at {triggered_price}"))
                        st.success(f"{ticker} → Research Now")
                        st.rerun()
            with ac2:
                if st.button("Watch", key=f"trig_watch_{a['id']}", use_container_width=True):
                    rec = asyncio.run(get_company_recommendation(ticker))
                    if rec:
                        asyncio.run(submit_feedback(rec["id"], ticker, "watch", notes=f"Price alert triggered"))
                        st.info(f"{ticker} → Watchlist")
                        st.rerun()
            with ac3:
                if st.button("Dismiss", key=f"trig_dismiss_{a['id']}", use_container_width=True):
                    asyncio.run(dismiss_alert(a["id"]))
                    st.rerun()

        st.markdown(f'<div style="height:20px"></div>', unsafe_allow_html=True)

    # ── Section 2: Active Targets ─────────────────────────────────────────────
    st.markdown(section_header("Active Targets", "Monitoring these price levels"), unsafe_allow_html=True)

    if not active:
        empty_state("🔔", 'No active price targets. Click "+ Set Price Target" to add one.')
    else:
        # Column header
        st.markdown(
            f"""
            <div style="display:grid;grid-template-columns:90px 1fr 110px 110px 80px 1fr 110px 160px;
                        gap:6px;padding:7px 12px;
                        background:{BG_CARD_ALT};border:1px solid {BORDER};border-radius:8px 8px 0 0">
              {"".join(
                f'<div style="color:{TEXT_MUTED};font-size:0.67rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em">{h}</div>'
                for h in ["Ticker","Company","Target","Current","Distance","Notes","Expires","Actions"]
              )}
            </div>
            """,
            unsafe_allow_html=True,
        )

        today = dt.date.today()

        for a in active:
            ticker = a["ticker"]
            target = a["target_price"]
            current = a.get("current_price")
            current_str = fmt_dollar(current) if current else "—"
            target_str = fmt_dollar(target)

            # Distance coloring
            if current:
                dist_pct = (target - current) / target * 100
                if dist_pct <= 5:
                    row_bg = f"{RED}0a"
                    dist_color = RED
                elif dist_pct <= 15:
                    row_bg = f"{AMBER}08"
                    dist_color = AMBER
                else:
                    row_bg = "transparent"
                    dist_color = TEXT_MUTED
                dist_str = f"{dist_pct:.1f}% away"
            else:
                row_bg = "transparent"
                dist_color = TEXT_DIM
                dist_str = "—"

            # Expiry check
            expires = a.get("expires_at", "—")
            if expires and expires != "—":
                try:
                    exp_date = dt.date.fromisoformat(str(expires))
                    days_left = (exp_date - today).days
                    exp_color = RED if days_left <= 7 else (AMBER if days_left <= 30 else TEXT_MUTED)
                    expires_html = f'<span style="color:{exp_color}">{expires}</span>'
                except Exception:
                    expires_html = expires
            else:
                expires_html = f'<span style="color:{TEXT_DIM}">—</span>'

            st.markdown(
                f'<div style="display:grid;grid-template-columns:90px 1fr 110px 110px 80px 1fr 110px 160px;'
                f'gap:6px;padding:9px 12px;background:{BG_CARD};border:1px solid {BORDER};'
                f'border-top:none;align-items:center">'
                f'<div style="color:{TEXT_PRIMARY};font-size:0.88rem;font-weight:700">{ticker}</div>'
                f'<div style="color:{TEXT_MUTED};font-size:0.78rem">{a.get("name","")}</div>'
                f'<div style="color:{TEXT_PRIMARY};font-size:0.85rem;font-weight:600">{target_str}</div>'
                f'<div style="color:{TEXT_MUTED};font-size:0.82rem">{current_str}</div>'
                f'<div style="color:{dist_color};font-size:0.78rem;font-weight:600">{dist_str}</div>'
                f'<div style="color:{TEXT_MUTED};font-size:0.75rem">{a.get("notes","")[:60]}</div>'
                f'<div style="font-size:0.75rem">{expires_html}</div>'
                f'<div></div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Action buttons
            act1, act2, act3 = st.columns([1, 1, 8])
            with act1:
                if st.button("Detail →", key=f"alert_detail_{a['id']}", use_container_width=True):
                    st.session_state.detail_ticker = ticker
                    st.session_state.page = "Company Detail"
                    st.rerun()
            with act2:
                if st.button("Remove", key=f"alert_remove_{a['id']}", use_container_width=True):
                    asyncio.run(dismiss_alert(a["id"]))
                    st.rerun()

    # ── Section 3: Alert History ──────────────────────────────────────────────
    with st.expander("Alert History"):
        history = asyncio.run(get_alert_history(limit=50))
        if not history:
            empty_state("📋", "No alert history yet.")
        else:
            import pandas as pd
            df = pd.DataFrame([
                {
                    "Ticker": h["ticker"],
                    "Target ($)": fmt_dollar(h["target_price"]),
                    "Triggered At ($)": fmt_dollar(h["triggered_price"]) if h.get("triggered_price") else "—",
                    "Status": h["status"].title(),
                    "Date": h["triggered_at"],
                    "Notes": h.get("notes", "")[:60],
                }
                for h in history
            ])
            st.dataframe(df, use_container_width=True, hide_index=True)
