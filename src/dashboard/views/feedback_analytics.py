"""
Analytics page — action rates, reject reason distribution, weight evolution,
recent action feed.
"""

from __future__ import annotations

import asyncio

import streamlit as st

from src.dashboard.components.db_helpers import (
    get_action_rates,
    get_recent_actions,
    get_weight_evolution,
    load_current_settings,
)
from src.dashboard.components.styles import (
    apply_theme,
    action_badge,
    kpi_card_html,
    section_header,
    empty_state,
    BG_CARD, BG_CARD_ALT, BORDER, GOLD, GREEN, RED, AMBER, TEXT_PRIMARY, TEXT_MUTED, TEXT_DIM,
)

_DIMENSION_LABELS = {
    "founder_ownership":   "Founder & Ownership",
    "business_quality":    "Business Quality",
    "unit_economics":      "Unit Economics",
    "valuation_asymmetry": "Valuation",
    "information_edge":    "Information Edge",
    "scalability":         "Scalability",
}

_DEFAULT_WEIGHTS = {
    "founder_ownership":   16.67,
    "business_quality":    16.67,
    "unit_economics":      16.67,
    "valuation_asymmetry": 16.67,
    "information_edge":    16.67,
    "scalability":         16.67,
}


def render() -> None:
    apply_theme()

    st.markdown(
        f'<h1 style="margin:0;color:{TEXT_PRIMARY}">Analytics</h1>'
        f'<div style="color:{TEXT_MUTED};font-size:0.78rem;margin-top:2px">'
        f'Decision patterns, scoring weight evolution, and recent activity</div>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<div style="height:12px"></div>', unsafe_allow_html=True)

    rates = asyncio.run(get_action_rates())
    recent = asyncio.run(get_recent_actions(limit=20))
    weight_evolution = asyncio.run(get_weight_evolution())

    total = rates.get("total", 0)

    # ── KPI row ───────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(kpi_card_html("Total Actions", str(total)), unsafe_allow_html=True)
    with k2:
        st.markdown(
            kpi_card_html("Research Rate", f"{rates.get('research_rate', 0):.1f}%",
                          sub=f"{rates.get('research_now', 0)} companies"),
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown(
            kpi_card_html("Watch Rate", f"{rates.get('watch_rate', 0):.1f}%",
                          sub=f"{rates.get('watch', 0)} companies"),
            unsafe_allow_html=True,
        )
    with k4:
        st.markdown(
            kpi_card_html("Reject Rate", f"{rates.get('reject_rate', 0):.1f}%",
                          sub=f"{rates.get('reject', 0)} companies"),
            unsafe_allow_html=True,
        )

    st.markdown(f'<div style="height:20px"></div>', unsafe_allow_html=True)

    # ── Action distribution + Reject reasons ─────────────────────────────────
    row1_c1, row1_c2 = st.columns(2)

    with row1_c1:
        st.markdown(section_header("Action Distribution"), unsafe_allow_html=True)
        if total > 0:
            import pandas as pd
            dist_data = {
                "Action": ["Research Now", "Watch", "Reject"],
                "Count":  [rates["research_now"], rates["watch"], rates["reject"]],
            }
            df_dist = pd.DataFrame(dist_data).set_index("Action")
            st.bar_chart(df_dist, color=GOLD)
        else:
            empty_state("📊", "No feedback data yet.")

    with row1_c2:
        st.markdown(section_header("Reject Reason Breakdown"), unsafe_allow_html=True)

        # Pull from feedback summary
        from src.dashboard.components.db_helpers import get_feedback_summary
        summary = asyncio.run(get_feedback_summary())
        reasons = summary.get("reject_reasons", [])

        if reasons:
            import pandas as pd
            df_r = pd.DataFrame(reasons)
            df_r.columns = ["Reason", "Count"]
            df_r = df_r.set_index("Reason").sort_values("Count", ascending=True)
            st.bar_chart(df_r)
        else:
            empty_state("📋", "No reject reasons recorded yet.")

    st.markdown(f'<div style="height:20px"></div>', unsafe_allow_html=True)

    # ── Scoring weights ───────────────────────────────────────────────────────
    row2_c1, row2_c2 = st.columns([3, 2])

    with row2_c1:
        st.markdown(section_header("Weight Evolution", "How scoring dimension weights have shifted over time"), unsafe_allow_html=True)
        if weight_evolution:
            import pandas as pd
            df_w = pd.DataFrame(weight_evolution)
            if "run_at" in df_w.columns:
                df_w = df_w.set_index("run_at")
            df_w = df_w.rename(columns=_DIMENSION_LABELS)
            st.line_chart(df_w)
        else:
            empty_state("📈", "Weight evolution data will appear after multiple scoring runs.")

    with row2_c2:
        st.markdown(section_header("Current vs Default Weights"), unsafe_allow_html=True)
        cfg = load_current_settings()
        cats = cfg.get("categories", {})

        weight_rows = []
        for key, label in _DIMENSION_LABELS.items():
            current = cats.get(key, {}).get("weight", _DEFAULT_WEIGHTS.get(key, 16.67))
            default = _DEFAULT_WEIGHTS.get(key, 16.67)
            delta = current - default
            delta_str = f"+{delta:.1f}" if delta > 0 else f"{delta:.1f}" if delta != 0 else "—"
            delta_color = GREEN if delta > 0 else (RED if delta < 0 else TEXT_DIM)
            weight_rows.append(
                f'<tr style="border-bottom:1px solid {BORDER}">'
                f'<td style="color:{TEXT_MUTED};font-size:0.8rem;padding:8px 12px">{label}</td>'
                f'<td style="color:{TEXT_PRIMARY};font-size:0.85rem;font-weight:600;padding:8px;text-align:right">{current:.1f}</td>'
                f'<td style="color:{delta_color};font-size:0.82rem;padding:8px 12px;text-align:right">{delta_str}</td>'
                f'</tr>'
            )

        st.markdown(
            f'<table style="width:100%;border-collapse:collapse;background:{BG_CARD};'
            f'border:1px solid {BORDER};border-radius:8px;overflow:hidden">'
            f'<thead><tr style="background:#1c2128">'
            f'<th style="color:{TEXT_MUTED};font-size:0.7rem;text-transform:uppercase;letter-spacing:0.08em;'
            f'padding:8px 12px;text-align:left">Dimension</th>'
            f'<th style="color:{TEXT_MUTED};font-size:0.7rem;text-transform:uppercase;letter-spacing:0.08em;'
            f'padding:8px;text-align:right">Weight</th>'
            f'<th style="color:{TEXT_MUTED};font-size:0.7rem;text-transform:uppercase;letter-spacing:0.08em;'
            f'padding:8px 12px;text-align:right">vs Default</th>'
            f'</tr></thead><tbody>{"".join(weight_rows)}</tbody></table>',
            unsafe_allow_html=True,
        )

    st.markdown(f'<div style="height:20px"></div>', unsafe_allow_html=True)

    # ── Recent Actions feed ───────────────────────────────────────────────────
    st.markdown(section_header("Recent Actions", "Last 20 analyst decisions"), unsafe_allow_html=True)

    if not recent:
        empty_state("📝", "No analyst actions recorded yet.")
    else:
        st.markdown(
            f"""
            <div style="background:{BG_CARD};border:1px solid {BORDER};
                        border-radius:8px;overflow:hidden">
              <div style="display:grid;grid-template-columns:130px 90px 120px 140px 1fr;
                          gap:8px;padding:8px 14px;background:#1c2128">
                <div style="color:{TEXT_MUTED};font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em">Date</div>
                <div style="color:{TEXT_MUTED};font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em">Ticker</div>
                <div style="color:{TEXT_MUTED};font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em">Action</div>
                <div style="color:{TEXT_MUTED};font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em">Reason</div>
                <div style="color:{TEXT_MUTED};font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em">Notes</div>
              </div>
            """,
            unsafe_allow_html=True,
        )

        for a in recent:
            st.markdown(
                f'<div style="display:grid;grid-template-columns:130px 90px 120px 140px 1fr;'
                f'gap:8px;padding:8px 14px;border-top:1px solid {BORDER};align-items:center">'
                f'<div style="color:{TEXT_DIM};font-size:0.75rem">{a["date"]}</div>'
                f'<div style="color:{TEXT_PRIMARY};font-size:0.82rem;font-weight:600">{a["ticker"]}</div>'
                f'<div>{action_badge(a["action"])}</div>'
                f'<div style="color:{TEXT_MUTED};font-size:0.78rem">{a["reject_reason"]}</div>'
                f'<div style="color:{TEXT_MUTED};font-size:0.78rem">{a.get("notes","")[:80]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown("</div>", unsafe_allow_html=True)
