"""
Company detail page — 5-tab deep dive: Memo, Scores, Financials, Feedback, Documents.
"""

from __future__ import annotations

import asyncio

import streamlit as st

from src.dashboard.components.db_helpers import (
    get_company,
    get_company_documents,
    get_company_feedback_history,
    get_company_metrics,
    get_company_recommendation,
    submit_feedback,
)
from src.dashboard.components.styles import (
    apply_theme,
    action_badge,
    fmt_dollar,
    fmt_market_cap,
    fmt_multiple,
    fmt_pct,
    kpi_card_html,
    score_bar_html,
    score_color,
    score_pill,
    section_header,
    status_badge,
    empty_state,
    BG_CARD, BG_PAGE, BORDER, ACCENT, GREEN, RED, AMBER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, TEXT_DIM,
)
GOLD = ACCENT
BG_CARD_ALT = BG_PAGE

_DIMENSION_DISPLAY = {
    "founder_ownership":   ("Founder & Ownership",   16.67),
    "business_quality":    ("Business Quality",       16.67),
    "unit_economics":      ("Unit Economics",         16.67),
    "valuation_asymmetry": ("Valuation",              16.67),
    "information_edge":    ("Information Edge",       16.67),
    "scalability":         ("Scalability",            16.67),
}
_RISK_DISPLAY = {
    "leverage":               ("Leverage Risk",          25),
    "customer_concentration": ("Customer Concentration", 15),
    "regulatory_risk":        ("Regulatory Risk",        15),
    "mgmt_turnover":          ("Management Turnover",    15),
    "accounting_flags":       ("Accounting Quality",     15),
    "geographic_risk":        ("Geographic Risk",        15),
}


def render() -> None:
    apply_theme()

    # ── Ticker input / breadcrumb ─────────────────────────────────────────────
    bc1, bc2 = st.columns([3, 1])
    with bc1:
        default = st.session_state.get("detail_ticker", "")
        ticker = st.text_input(
            "Ticker",
            value=default,
            placeholder="Enter ticker symbol…",
            label_visibility="collapsed",
        ).upper().strip()
        if ticker:
            st.session_state.detail_ticker = ticker

    with bc2:
        if st.button("← Back to Rankings", use_container_width=True):
            st.session_state.page = "Rankings"
            st.rerun()

    if not ticker:
        empty_state("🔍", "Enter a ticker symbol above to view company details.")
        return

    # ── Load data ─────────────────────────────────────────────────────────────
    company = asyncio.run(get_company(ticker))
    if not company:
        st.warning(f"**{ticker}** not found in the database.")
        return

    metrics = asyncio.run(get_company_metrics(ticker))
    rec = asyncio.run(get_company_recommendation(ticker))

    # ── Hero section ──────────────────────────────────────────────────────────
    founder_badge = ""
    if company.get("is_founder_led"):
        founder_badge = (
            f' <span style="background:{GOLD}22;color:{GOLD};border:1px solid {GOLD}44;'
            f'padding:2px 9px;border-radius:8px;font-size:0.78rem;font-weight:600">'
            f'Founder-Led</span>'
        )

    exch = company.get("exchange") or ""
    country = company.get("country") or ""
    sector = company.get("gics_sector") or ""
    industry = company.get("gics_industry") or ""
    meta_parts = [p for p in [exch, country, sector, industry] if p]
    meta = " · ".join(meta_parts)

    st.markdown(
        f"""
        <div style="background:{BG_CARD};border:1px solid {BORDER};border-top:3px solid {GOLD};
                    border-radius:10px;padding:20px 24px;margin-bottom:20px">
          <div style="display:flex;align-items:baseline;gap:12px;flex-wrap:wrap">
            <span style="color:{TEXT_PRIMARY};font-size:2rem;font-weight:800;letter-spacing:-0.01em">{ticker}</span>
            {founder_badge}
          </div>
          <div style="color:{TEXT_PRIMARY};font-size:1.05rem;font-weight:600;margin-top:4px">
            {company.get("name","")}
          </div>
          <div style="color:{TEXT_MUTED};font-size:0.8rem;margin-top:4px">{meta}</div>
          {"<div style='color:"+TEXT_MUTED+";font-size:0.78rem;margin-top:8px;line-height:1.5'>"+company.get("description","")[:300]+"…</div>" if company.get("description") else ""}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── KPI cards ─────────────────────────────────────────────────────────────
    k1, k2, k3, k4, k5 = st.columns(5)
    mkt_cap = fmt_market_cap(company.get("market_cap_usd"))
    with k1:
        st.markdown(kpi_card_html("Market Cap", mkt_cap), unsafe_allow_html=True)
    if rec:
        fit_color = score_color(rec["fit_score"])
        risk_color = score_color(rec["risk_score"], inverted=True)
        rank_color = score_color(rec["rank_score"])
        with k2:
            st.markdown(kpi_card_html("Fit Score", f"{rec['fit_score']:.0f}", sub="out of 100"), unsafe_allow_html=True)
        with k3:
            st.markdown(kpi_card_html("Risk Score", f"{rec['risk_score']:.0f}", sub="0 = lowest risk"), unsafe_allow_html=True)
        with k4:
            st.markdown(kpi_card_html("Rank Score", f"{rec['rank_score']:.1f}", sub=f"Rank #{rec.get('rank','—')}"), unsafe_allow_html=True)
        with k5:
            st.markdown(kpi_card_html("Status", rec["status"].title()), unsafe_allow_html=True)
    else:
        with k2:
            st.markdown(kpi_card_html("Fit Score", "—"), unsafe_allow_html=True)
        with k3:
            st.markdown(kpi_card_html("Risk Score", "—"), unsafe_allow_html=True)
        with k4:
            st.markdown(kpi_card_html("Rank Score", "—"), unsafe_allow_html=True)
        with k5:
            st.markdown(kpi_card_html("Status", "—"), unsafe_allow_html=True)

    st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

    # ── Action buttons (if rec exists) ────────────────────────────────────────
    if rec and rec["status"] == "pending":
        act1, act2, act3, act4 = st.columns([1, 1, 1, 5])
        with act1:
            if st.button("Research Now", key="detail_research", use_container_width=True):
                asyncio.run(submit_feedback(rec["id"], ticker, "research_now"))
                st.success("Flagged for research")
                st.rerun()
        with act2:
            if st.button("Watch", key="detail_watch", use_container_width=True):
                asyncio.run(submit_feedback(rec["id"], ticker, "watch"))
                st.info("Added to watchlist")
                st.rerun()
        with act3:
            if st.button("Reject", key="detail_reject_toggle", use_container_width=True):
                st.session_state["detail_reject_open"] = not st.session_state.get("detail_reject_open", False)

        if st.session_state.get("detail_reject_open"):
            rr1, rr2, rr3 = st.columns([3, 3, 1])
            _REJECT_REASONS = [
                "Too expensive", "Weak moat / low quality", "Poor unit economics",
                "No insider alignment", "Too well-covered", "Limited growth runway",
                "Too risky", "Already known / duplicate",
            ]
            with rr1:
                reason = st.selectbox("Reason", _REJECT_REASONS, key="detail_reason", label_visibility="collapsed")
            with rr2:
                notes = st.text_input("Notes", placeholder="Optional note…", key="detail_notes", label_visibility="collapsed")
            with rr3:
                if st.button("Confirm Reject", key="detail_confirm_reject"):
                    asyncio.run(submit_feedback(rec["id"], ticker, "reject", reject_reason=reason, notes=notes or None))
                    st.session_state["detail_reject_open"] = False
                    st.rerun()

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab_memo, tab_scores, tab_fin, tab_feedback, tab_docs = st.tabs(
        ["📄 Memo", "📊 Scores", "💰 Financials", "📝 Feedback History", "📁 Documents"]
    )

    # ── TAB 1: Memo ──────────────────────────────────────────────────────────
    with tab_memo:
        if not rec or not rec.get("memo_text"):
            empty_state("📄", "No investment memo generated yet. Run the memo pipeline from the Pipeline page.")
        else:
            mc1, mc2 = st.columns([3, 1])
            with mc1:
                st.markdown(
                    f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:8px;'
                    f'padding:24px 28px;font-size:0.88rem;line-height:1.7;color:{TEXT_PRIMARY}">'
                    f'{rec["memo_text"]}</div>',
                    unsafe_allow_html=True,
                )
            with mc2:
                citations = rec.get("citations") or []
                if citations:
                    st.markdown(
                        f'<div style="color:{TEXT_MUTED};font-size:0.72rem;font-weight:700;'
                        f'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:10px">Sources</div>',
                        unsafe_allow_html=True,
                    )
                    for i, cit in enumerate(citations, 1):
                        if isinstance(cit, dict):
                            doc_type = cit.get("doc_type", "Filing")
                            title = cit.get("title") or cit.get("source", "")
                            url = cit.get("url", "")
                            date = cit.get("date", "")
                            link_html = (
                                f'<a href="{url}" target="_blank" style="color:{GOLD};text-decoration:none">{title}</a>'
                                if url else f'<span style="color:{TEXT_PRIMARY}">{title}</span>'
                            )
                            st.markdown(
                                f'<div style="background:{BG_CARD};border:1px solid {BORDER};'
                                f'border-radius:6px;padding:8px 10px;margin-bottom:6px;font-size:0.75rem">'
                                f'<div style="color:{TEXT_MUTED};margin-bottom:2px">[{i}] {doc_type}</div>'
                                f'<div>{link_html}</div>'
                                f'{"<div style=color:"+TEXT_DIM+";font-size:0.7rem;margin-top:2px>"+date+"</div>" if date else ""}'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

    # ── TAB 2: Scores ─────────────────────────────────────────────────────────
    with tab_scores:
        if not rec or not rec.get("scoring_detail"):
            empty_state("📊", "No scoring detail available.")
        else:
            detail = rec["scoring_detail"]
            criteria = detail.get("criteria", [])
            risk_factors = detail.get("risk_factors", [])

            sc1, sc2 = st.columns(2)

            with sc1:
                st.markdown(
                    section_header("Fit Score", f"Total: {rec['fit_score']:.0f} / 100"),
                    unsafe_allow_html=True,
                )
                if criteria:
                    for c in criteria:
                        if isinstance(c, dict):
                            name = c.get("name", "")
                            display_name, default_max = _DIMENSION_DISPLAY.get(name, (name, 16.67))
                            score = float(c.get("score", 0))
                            max_s = float(c.get("max_score", default_max))
                            evidence = c.get("evidence", "")
                            st.markdown(score_bar_html(score, max_s, display_name, evidence), unsafe_allow_html=True)
                else:
                    st.markdown(
                        f'<div style="color:{TEXT_MUTED};font-size:0.82rem">No criteria breakdown available.</div>',
                        unsafe_allow_html=True,
                    )

            with sc2:
                st.markdown(
                    section_header("Risk Score", f"Total: {rec['risk_score']:.0f} / 100  (lower is better)"),
                    unsafe_allow_html=True,
                )
                if risk_factors:
                    for rf in risk_factors:
                        if isinstance(rf, dict):
                            name = rf.get("name", "")
                            display_name, default_max = _RISK_DISPLAY.get(name, (name, 15))
                            score = float(rf.get("score", 0))
                            max_s = float(rf.get("max_score", default_max))
                            evidence = rf.get("evidence", "")
                            st.markdown(score_bar_html(score, max_s, display_name, evidence, ), unsafe_allow_html=True)
                else:
                    st.markdown(
                        f'<div style="color:{TEXT_MUTED};font-size:0.82rem">No risk breakdown available.</div>',
                        unsafe_allow_html=True,
                    )

    # ── TAB 3: Financials ────────────────────────────────────────────────────
    with tab_fin:
        if not metrics:
            empty_state("💰", "No financial metrics loaded yet.")
        else:
            period = metrics.get("period_end", "Latest")
            st.markdown(
                f'<div style="color:{TEXT_MUTED};font-size:0.78rem;margin-bottom:16px">'
                f'Period: {period}</div>',
                unsafe_allow_html=True,
            )

            def _row(label: str, value: str, highlight: bool = False) -> str:
                val_color = TEXT_PRIMARY if not highlight else GOLD
                return (
                    f'<tr style="border-bottom:1px solid {BORDER}">'
                    f'<td style="color:{TEXT_MUTED};font-size:0.82rem;padding:8px 12px;'
                    f'font-weight:500;width:50%">{label}</td>'
                    f'<td style="color:{val_color};font-size:0.85rem;font-weight:600;'
                    f'padding:8px 12px;text-align:right">{value}</td></tr>'
                )

            def _section(title: str, rows: list[tuple]) -> str:
                header = (
                    f'<tr><td colspan="2" style="background:{BG_CARD_ALT if False else "#1c2128"};'
                    f'color:{GOLD};font-size:0.7rem;font-weight:700;text-transform:uppercase;'
                    f'letter-spacing:0.1em;padding:10px 12px 6px">{title}</td></tr>'
                )
                return header + "".join(_row(lbl, val) for lbl, val in rows)

            BG_CARD_ALT = "#1c2128"
            fin_html = f"""
            <table style="width:100%;border-collapse:collapse;background:{BG_CARD};
                          border:1px solid {BORDER};border-radius:8px;overflow:hidden">
              {_section("Income & Profitability", [
                  ("Revenue", fmt_dollar(metrics.get("revenue"))),
                  ("Gross Margin", fmt_pct(metrics.get("gross_margin"))),
                  ("EBIT Margin", fmt_pct(metrics.get("ebit_margin"))),
                  ("ROIC", fmt_pct(metrics.get("roic"))),
                  ("ROE", fmt_pct(metrics.get("roe"))),
              ])}
              {_section("Cash Flow", [
                  ("Free Cash Flow", fmt_dollar(metrics.get("fcf"))),
                  ("FCF Yield", fmt_pct(metrics.get("fcf_yield"))),
                  ("Capex / Revenue", fmt_pct(metrics.get("capex_to_revenue"))),
              ])}
              {_section("Balance Sheet & Leverage", [
                  ("Net Debt", fmt_dollar(metrics.get("net_debt"))),
                  ("Net Debt / EBITDA", fmt_multiple(metrics.get("net_debt_ebitda"))),
              ])}
              {_section("Growth", [
                  ("Revenue Growth YoY", fmt_pct(metrics.get("revenue_growth_yoy"))),
                  ("Revenue CAGR 3Y", fmt_pct(metrics.get("revenue_growth_3yr_cagr"))),
              ])}
              {_section("Valuation", [
                  ("EV / EBIT", fmt_multiple(metrics.get("ev_ebit"))),
                  ("EV / FCF", fmt_multiple(metrics.get("ev_fcf"))),
                  ("P/E", fmt_multiple(metrics.get("pe_ratio"))),
              ])}
              {_section("Ownership & Coverage", [
                  ("Insider Ownership", fmt_pct(metrics.get("insider_ownership_pct"))),
                  ("Institutional Ownership", fmt_pct(metrics.get("institutional_ownership_pct"))),
                  ("Analyst Coverage", str(metrics.get("analyst_count") or "—")),
              ])}
            </table>
            """
            fc1, fc2 = st.columns([1, 1])
            with fc1:
                st.markdown(fin_html, unsafe_allow_html=True)

    # ── TAB 4: Feedback History ───────────────────────────────────────────────
    with tab_feedback:
        history = asyncio.run(get_company_feedback_history(ticker))
        if not history:
            empty_state("📝", "No analyst feedback recorded for this company yet.")
        else:
            import pandas as pd
            df = pd.DataFrame(history)
            df.columns = ["Date", "Action", "Reject Reason", "Notes", "Analyst"]
            st.dataframe(df, use_container_width=True, hide_index=True)

    # ── TAB 5: Documents ─────────────────────────────────────────────────────
    with tab_docs:
        docs = asyncio.run(get_company_documents(ticker))
        if not docs:
            empty_state("📁", "No documents ingested yet for this company.")
        else:
            for d in docs:
                url = d.get("source_url", "")
                title = d.get("title") or d.get("accession_no") or "—"
                link = f'<a href="{url}" target="_blank" style="color:{GOLD};text-decoration:none">{title}</a>' if url else title
                st.markdown(
                    f'<div style="display:flex;gap:16px;align-items:baseline;'
                    f'padding:8px 0;border-bottom:1px solid {BORDER}">'
                    f'<span style="background:{GOLD}15;color:{GOLD};border:1px solid {GOLD}33;'
                    f'padding:1px 7px;border-radius:6px;font-size:0.7rem;font-weight:600;'
                    f'white-space:nowrap;min-width:60px;text-align:center">{d.get("doc_type","").upper()}</span>'
                    f'<span style="color:{TEXT_MUTED};font-size:0.75rem;white-space:nowrap">{d.get("published_at","—")}</span>'
                    f'<span style="font-size:0.82rem">{link}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
