"""
Settings page — edit hard filters, scoring dimension weights, ranking formula,
output settings, Phoenician Intelligence config, and insider buying tracker.
All changes are saved to scoring_weights.yaml and take effect on the next run.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import datetime as dt

import streamlit as st

from src.dashboard.components.db_helpers import load_current_settings, save_settings


def _run(coro, timeout: int = 30):
    def _target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="dashboard")
        return ex.submit(_target).result(timeout=timeout)


def _engine():
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from src.config.settings import settings
    engine = create_async_engine(settings.db.dsn, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, factory


async def _load_portfolio() -> list[dict]:
    from src.db.repositories.portfolio_repo import PortfolioRepository
    engine, factory = _engine()
    try:
        async with factory() as session:
            repo = PortfolioRepository(session)
            holdings = await repo.get_active()
            return [
                {
                    "id": str(h.id),
                    "ticker": h.ticker,
                    "name": h.name or "",
                    "sector": h.sector or "",
                    "entry_price": float(h.entry_price) if h.entry_price else None,
                    "position_size_usd": float(h.position_size_usd) if h.position_size_usd else None,
                    "date_added": str(h.date_added) if h.date_added else "",
                    "notes": h.notes or "",
                }
                for h in holdings
            ]
    finally:
        await engine.dispose()


async def _add_holding(ticker: str, name: str, sector: str, entry_price: float | None,
                        position_usd: float | None, notes: str) -> None:
    from src.db.models.portfolio import PortfolioHolding
    from src.db.repositories.portfolio_repo import PortfolioRepository
    engine, factory = _engine()
    try:
        async with factory() as session:
            repo = PortfolioRepository(session)
            h = PortfolioHolding(
                ticker=ticker.upper().strip(),
                name=name.strip() or None,
                sector=sector.strip() or None,
                entry_price=entry_price,
                position_size_usd=position_usd,
                date_added=dt.date.today(),
                notes=notes.strip() or None,
            )
            await repo.add(h)
            await session.commit()
    finally:
        await engine.dispose()


async def _remove_holding(ticker: str) -> None:
    from src.db.repositories.portfolio_repo import PortfolioRepository
    engine, factory = _engine()
    try:
        async with factory() as session:
            repo = PortfolioRepository(session)
            await repo.remove(ticker)
            await session.commit()
    finally:
        await engine.dispose()


def _render_portfolio_section() -> None:
    from src.dashboard.components.styles import TEXT_PRIMARY, TEXT_MUTED, BORDER, BG_CARD_ALT

    holdings = _run(_load_portfolio())

    if holdings:
        # Table of current holdings
        hdr = (
            f'<div style="display:grid;grid-template-columns:80px 1fr 1fr 100px 120px 80px;'
            f'gap:8px;padding:6px 0;border-bottom:1px solid {BORDER};'
            f'font-size:0.67rem;font-weight:600;text-transform:uppercase;'
            f'letter-spacing:0.07em;color:#9ca3af;margin-bottom:4px">'
            f'<div>Ticker</div><div>Name</div><div>Sector</div>'
            f'<div style="text-align:right">Entry Price</div>'
            f'<div style="text-align:right">Position</div><div></div></div>'
        )
        rows_html = hdr
        for h in holdings:
            ep = f"${h['entry_price']:,.2f}" if h.get("entry_price") else "—"
            ps = f"${h['position_size_usd']/1e6:.2f}M" if h.get("position_size_usd") and h["position_size_usd"] >= 1e6 else (f"${h['position_size_usd']:,.0f}" if h.get("position_size_usd") else "—")
            rows_html += (
                f'<div style="display:grid;grid-template-columns:80px 1fr 1fr 100px 120px 80px;'
                f'gap:8px;padding:7px 0;border-bottom:1px solid #f3f4f6;align-items:center">'
                f'<div style="font-weight:700;font-size:0.84rem;color:{TEXT_PRIMARY}">{h["ticker"]}</div>'
                f'<div style="font-size:0.82rem;color:#374151">{h["name"]}</div>'
                f'<div style="font-size:0.82rem;color:#6b7280">{h["sector"]}</div>'
                f'<div style="font-size:0.82rem;color:#374151;text-align:right">{ep}</div>'
                f'<div style="font-size:0.82rem;color:#374151;text-align:right">{ps}</div>'
                f'<div></div></div>'
            )
        st.markdown(
            f'<div style="background:{BG_CARD_ALT};border:1px solid {BORDER};border-radius:6px;'
            f'padding:12px 16px;margin-bottom:16px">{rows_html}</div>',
            unsafe_allow_html=True,
        )

        # Remove a holding
        tickers_list = [h["ticker"] for h in holdings]
        rc1, rc2 = st.columns([2, 1])
        with rc1:
            to_remove = st.selectbox("Remove holding", ["— select —"] + tickers_list,
                                     key="portfolio_remove", label_visibility="collapsed")
        with rc2:
            if st.button("Remove", key="btn_remove_holding", use_container_width=True):
                if to_remove != "— select —":
                    _run(_remove_holding(to_remove))
                    st.success(f"{to_remove} removed from portfolio.")
                    st.rerun()
    else:
        st.markdown(
            f'<div style="font-size:0.83rem;color:{TEXT_MUTED};margin-bottom:12px">'
            f'No holdings on record. Add your current positions below so the engine can compare '
            f'candidates against your portfolio quality and sector exposure.</div>',
            unsafe_allow_html=True,
        )

    # Add new holding form
    st.markdown(
        f'<div style="font-size:0.72rem;font-weight:600;text-transform:uppercase;'
        f'letter-spacing:0.07em;color:#9ca3af;margin:14px 0 8px">Add Position</div>',
        unsafe_allow_html=True,
    )
    a1, a2, a3 = st.columns([1, 2, 2])
    with a1:
        new_ticker = st.text_input("Ticker", placeholder="e.g. AAPL", key="ph_ticker", label_visibility="collapsed")
    with a2:
        new_name = st.text_input("Company name", placeholder="Company name (optional)", key="ph_name", label_visibility="collapsed")
    with a3:
        new_sector = st.selectbox("Sector", [
            "", "Information Technology", "Financials", "Health Care",
            "Consumer Discretionary", "Consumer Staples", "Industrials",
            "Communication Services", "Energy", "Materials", "Real Estate", "Utilities",
        ], key="ph_sector", label_visibility="collapsed")
    b1, b2, b3, b4 = st.columns([1, 1, 2, 1])
    with b1:
        new_price = st.number_input("Entry price ($)", min_value=0.0, value=0.0, step=0.01, format="%.2f", key="ph_price", label_visibility="collapsed")
    with b2:
        new_pos = st.number_input("Position size ($)", min_value=0.0, value=0.0, step=1000.0, format="%.0f", key="ph_pos", label_visibility="collapsed")
    with b3:
        new_notes = st.text_input("Notes", placeholder="Optional notes", key="ph_notes", label_visibility="collapsed")
    with b4:
        if st.button("Add", key="btn_add_holding", use_container_width=True):
            if new_ticker.strip():
                _run(_add_holding(
                    ticker=new_ticker,
                    name=new_name,
                    sector=new_sector,
                    entry_price=new_price if new_price > 0 else None,
                    position_usd=new_pos if new_pos > 0 else None,
                    notes=new_notes,
                ))
                st.success(f"{new_ticker.upper()} added to portfolio.")
                st.rerun()
            else:
                st.error("Ticker is required.")
from src.dashboard.components.styles import (
    apply_theme,
    section_header,
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


def render() -> None:
    apply_theme()

    st.markdown(
        f'<h1 style="margin:0;color:{TEXT_PRIMARY}">Settings</h1>'
        f'<div style="color:{TEXT_MUTED};font-size:0.78rem;margin-top:2px">'
        f'Configure screening parameters. Changes take effect on the next scoring run.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<div style="height:16px"></div>', unsafe_allow_html=True)

    cfg = load_current_settings()
    hard = cfg.get("hard_filters", {})
    cats = cfg.get("categories", {})
    ranking = cfg.get("ranking", {})

    changes: dict = {"hard_filters": {}, "categories": {}, "ranking": {}}

    # ── 1. Hard Filters — Round 1 ─────────────────────────────────────────────
    st.markdown(section_header("Round 1 — Hard Filters", "Pass/fail. Companies failing any filter are excluded entirely."), unsafe_allow_html=True)
    st.markdown(f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:10px;padding:20px 24px">', unsafe_allow_html=True)

    hf1, hf2, hf3 = st.columns(3)

    with hf1:
        st.markdown(f'<div style="color:{GOLD};font-size:0.78rem;font-weight:600;margin-bottom:10px">Excluded Countries</div>', unsafe_allow_html=True)
        excl_countries = hard.get("excluded_countries", ["CN","RU","IR","KP","SY","BY"])
        exc_cn = st.checkbox("China (mainland)", value="CN" in excl_countries, key="exc_cn")
        exc_ru = st.checkbox("Russia", value="RU" in excl_countries, key="exc_ru")
        exc_ir = st.checkbox("Iran", value="IR" in excl_countries, key="exc_ir")
        exc_kp = st.checkbox("North Korea", value="KP" in excl_countries, key="exc_kp")
        exc_sy = st.checkbox("Syria", value="SY" in excl_countries, key="exc_sy")
        exc_by = st.checkbox("Belarus", value="BY" in excl_countries, key="exc_by")
        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
        st.markdown(f'<div style="color:{GOLD};font-size:0.78rem;font-weight:600;margin-bottom:10px">Excluded Sectors</div>', unsafe_allow_html=True)
        excl_s = hard.get("excluded_gics_sectors", ["10","55"])
        excl_energy    = st.checkbox("Energy (GICS 10)", value="10" in excl_s, key="excl_energy")
        excl_utilities = st.checkbox("Utilities (GICS 55)", value="55" in excl_s, key="excl_utilities")
        excl_biotech   = st.checkbox("Biotech (GICS 35201010)", value="35201010" in hard.get("excluded_gics_sub_industries", []), key="excl_biotech")

    with hf2:
        st.markdown(f'<div style="color:{GOLD};font-size:0.78rem;font-weight:600;margin-bottom:10px">Market Cap Range</div>', unsafe_allow_html=True)
        min_cap = st.number_input("Min Market Cap ($M)", min_value=0, max_value=50000,
            value=int(float(hard.get("min_market_cap_usd", 100_000_000)) / 1e6),
            step=50, key="min_cap")
        max_cap = st.number_input("Max Market Cap ($B)", min_value=1, max_value=500,
            value=int(float(hard.get("max_market_cap_usd", 10_000_000_000)) / 1e9),
            step=1, key="max_cap")
        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
        st.markdown(f'<div style="color:{GOLD};font-size:0.78rem;font-weight:600;margin-bottom:10px">Liquidity</div>', unsafe_allow_html=True)
        min_vol = st.number_input("Min Avg Daily Volume ($K)", min_value=0, max_value=100000,
            value=int(float(hard.get("min_avg_daily_volume_usd", 500_000)) / 1e3),
            step=100, key="min_vol")

    with hf3:
        st.markdown(f'<div style="color:{GOLD};font-size:0.78rem;font-weight:600;margin-bottom:10px">Financial Floors</div>', unsafe_allow_html=True)
        min_gm = st.number_input("Min Gross Margin (%)", min_value=0, max_value=100,
            value=int(float(hard.get("min_gross_margin", 0.15)) * 100),
            step=5, key="min_gm")
        max_lev = st.number_input("Max Net Debt / EBITDA", min_value=0.0, max_value=20.0,
            value=float(hard.get("max_leverage", 5.0)),
            step=0.5, key="max_lev")
        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
        st.markdown(f'<div style="color:{GOLD};font-size:0.78rem;font-weight:600;margin-bottom:10px">Final Gate</div>', unsafe_allow_html=True)
        min_score = st.number_input("Min Fit Score to include (0–100)", min_value=0, max_value=100,
            value=int(float(hard.get("min_composite_score", 50))),
            step=5, key="min_score")
        top_n = st.number_input("Top N results per run", min_value=1, max_value=20,
            value=int(float(cfg.get("ranking", {}).get("top_n_results", 5))),
            step=1, key="top_n")

    st.markdown("</div>", unsafe_allow_html=True)

    # Build new hard_filters
    new_excl_countries = []
    for code, selected in [("CN",exc_cn),("RU",exc_ru),("IR",exc_ir),("KP",exc_kp),("SY",exc_sy),("BY",exc_by)]:
        if selected:
            new_excl_countries.append(code)
    new_sectors = []
    if excl_energy:    new_sectors.append("10")
    if excl_utilities: new_sectors.append("55")
    new_sub_industries = ["35201010"] if excl_biotech else []

    changes["hard_filters"] = {
        **hard,
        "excluded_countries": new_excl_countries,
        "excluded_gics_sectors": new_sectors,
        "excluded_gics_sub_industries": new_sub_industries,
        "min_market_cap_usd": min_cap * 1_000_000,
        "max_market_cap_usd": max_cap * 1_000_000_000,
        "min_avg_daily_volume_usd": min_vol * 1_000,
        "min_gross_margin": min_gm / 100.0,
        "max_leverage": max_lev,
        "min_composite_score": min_score,
    }

    st.markdown(f'<div style="height:20px"></div>', unsafe_allow_html=True)

    # ── 2. Scoring Dimension Weights ──────────────────────────────────────────
    st.markdown(
        section_header("Scoring Dimension Weights", "Each dimension 5–35 pts. Total must equal 100."),
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:10px;padding:20px 24px">',
        unsafe_allow_html=True,
    )

    wc1, wc2 = st.columns(2)
    new_weights: dict[str, float] = {}
    dim_keys = list(_DIMENSION_LABELS.keys())

    for i, key in enumerate(dim_keys):
        label = _DIMENSION_LABELS[key]
        current_w = float(cats.get(key, {}).get("weight", 16.67))
        col = wc1 if i % 2 == 0 else wc2
        with col:
            new_weights[key] = st.slider(
                label,
                min_value=5.0,
                max_value=35.0,
                value=current_w,
                step=0.5,
                key=f"w_{key}",
            )

    total_weight = sum(new_weights.values())
    weight_color = GREEN if abs(total_weight - 100) < 0.1 else RED
    st.markdown(
        f'<div style="text-align:right;margin-top:8px">'
        f'<span style="color:{TEXT_MUTED};font-size:0.82rem">Total: </span>'
        f'<span style="color:{weight_color};font-size:1rem;font-weight:700">{total_weight:.1f}</span>'
        f'<span style="color:{TEXT_MUTED};font-size:0.82rem"> / 100</span>'
        f'{"<span style=color:"+RED+";font-size:0.78rem;margin-left:8px>⚠ Must equal 100</span>" if abs(total_weight - 100) >= 0.1 else ""}'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    # Build new categories block
    new_cats = {}
    for key in dim_keys:
        existing_cat = cats.get(key, {})
        new_cats[key] = {**existing_cat, "weight": new_weights[key]}
    changes["categories"] = new_cats

    st.markdown(f'<div style="height:20px"></div>', unsafe_allow_html=True)

    # ── 3. Ranking Formula ────────────────────────────────────────────────────
    st.markdown(section_header("Ranking Formula", "Fit and Risk weighting for the composite rank score"), unsafe_allow_html=True)
    st.markdown(
        f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:10px;padding:20px 24px">',
        unsafe_allow_html=True,
    )

    rc1, rc2, rc3 = st.columns([2, 2, 3])
    cur_fit_w = float(ranking.get("fit_weight", 0.50)) * 100
    with rc1:
        fit_w = st.number_input("Fit Weight (%)", min_value=10, max_value=90, value=int(cur_fit_w), step=5, key="fit_w")
    with rc2:
        risk_w = 100 - fit_w
        st.markdown(
            f'<div style="padding-top:28px;color:{TEXT_MUTED};font-size:0.85rem">'
            f'Risk Penalty: <span style="color:{TEXT_PRIMARY};font-weight:600">{risk_w}%</span></div>',
            unsafe_allow_html=True,
        )
    with rc3:
        st.markdown(
            f'<div style="padding-top:20px;color:{TEXT_DIM};font-size:0.8rem;line-height:1.5">'
            f'rank = fit × {fit_w/100:.2f} − risk × {risk_w/100:.2f} + feedback_adj</div>',
            unsafe_allow_html=True,
        )

    changes["ranking"] = {
        **ranking,
        "fit_weight": fit_w / 100,
        "risk_penalty_weight": risk_w / 100,
        "top_n_results": top_n,
    }

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown(f'<div style="height:20px"></div>', unsafe_allow_html=True)

    # ── 4. Scoring Thresholds ─────────────────────────────────────────────────
    st.markdown(section_header("Round 2 — Scoring Thresholds", "Adjust tiered cutoffs for each criterion"), unsafe_allow_html=True)
    st.markdown(f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:10px;padding:20px 24px">', unsafe_allow_html=True)

    bq = cats.get("business_quality",  {}).get("sub_criteria", {})
    fo = cats.get("founder_ownership", {}).get("sub_criteria", {})
    ue = cats.get("unit_economics",    {}).get("sub_criteria", {})
    ie = cats.get("information_edge",  {}).get("sub_criteria", {})
    va = cats.get("valuation_asymmetry", {}).get("sub_criteria", {})
    sc = cats.get("scalability", {}).get("sub_criteria", {})

    # Business Quality
    st.markdown(f'<div style="color:{GOLD};font-size:0.78rem;font-weight:600;margin-bottom:10px">Business Quality</div>', unsafe_allow_html=True)
    q1, q2, q3, q4 = st.columns(4)
    with q1:
        gm_exc  = st.number_input("Gross Margin Excellent (%)", 1, 99, int(bq.get("gross_margin",{}).get("thresholds",{}).get("excellent",0.70)*100), 5, key="gm_exc")
        gm_good = st.number_input("Gross Margin Good (%)",      1, 99, int(bq.get("gross_margin",{}).get("thresholds",{}).get("good",0.50)*100), 5, key="gm_good")
        gm_floor= st.number_input("Gross Margin Floor (%)",     0, 99, int(bq.get("gross_margin",{}).get("thresholds",{}).get("moderate",0.30)*100), 5, key="gm_floor")
    with q2:
        om_exc  = st.number_input("Op Margin Excellent (%)", 1, 99, int(bq.get("operating_margin",{}).get("thresholds",{}).get("excellent",0.25)*100), 5, key="om_exc")
        om_good = st.number_input("Op Margin Good (%)",      1, 99, int(bq.get("operating_margin",{}).get("thresholds",{}).get("good",0.15)*100), 5, key="om_good")
        om_weak = st.number_input("Op Margin Min (%)",       0, 99, int(bq.get("operating_margin",{}).get("thresholds",{}).get("weak",0.10)*100), 5, key="om_weak")
    with q3:
        rg_exc  = st.number_input("Rev Growth Excellent (%)", 1, 99, int(bq.get("revenue_growth",{}).get("thresholds",{}).get("excellent",0.20)*100), 5, key="rg_exc")
        rg_good = st.number_input("Rev Growth Good (%)",      1, 99, int(bq.get("revenue_growth",{}).get("thresholds",{}).get("good",0.12)*100), 5, key="rg_good")
        rg_weak = st.number_input("Rev Growth Min (%)",       1, 99, int(bq.get("revenue_growth",{}).get("thresholds",{}).get("weak",0.08)*100), 5, key="rg_weak")
    with q4:
        roa_exc  = st.number_input("ROA Excellent (%)", 1, 50, int(bq.get("roa_roe",{}).get("thresholds",{}).get("roa_excellent",0.15)*100), 1, key="roa_exc")
        roa_good = st.number_input("ROA Good (%)",      1, 50, int(bq.get("roa_roe",{}).get("thresholds",{}).get("roa_good",0.08)*100), 1, key="roa_good")
        roe_exc  = st.number_input("ROE Excellent (%)", 1, 80, int(bq.get("roa_roe",{}).get("thresholds",{}).get("roe_excellent",0.35)*100), 5, key="roe_exc")

    # Unit Economics
    st.markdown(f'<div style="color:{GOLD};font-size:0.78rem;font-weight:600;margin:12px 0 10px">Unit Economics</div>', unsafe_allow_html=True)
    u1, u2, u3, u4 = st.columns(4)
    with u1:
        fcfy_exc  = st.number_input("FCF Yield Excellent (%)", 1, 30, int(ue.get("fcf_yield",{}).get("thresholds",{}).get("excellent",0.08)*100), 1, key="fcfy_exc")
        fcfy_good = st.number_input("FCF Yield Good (%)",      1, 30, int(ue.get("fcf_yield",{}).get("thresholds",{}).get("good",0.05)*100), 1, key="fcfy_good")
        fcfy_weak = st.number_input("FCF Yield Min (%)",       1, 20, int(ue.get("fcf_yield",{}).get("thresholds",{}).get("weak",0.03)*100), 1, key="fcfy_weak")
    with u2:
        fni_exc  = st.number_input("FCF/NI Excellent", 0.1, 2.0, float(ue.get("fcf_to_net_income",{}).get("thresholds",{}).get("excellent",0.90)), 0.05, key="fni_exc", format="%.2f")
        fni_good = st.number_input("FCF/NI Good",      0.1, 2.0, float(ue.get("fcf_to_net_income",{}).get("thresholds",{}).get("good",0.70)), 0.05, key="fni_good", format="%.2f")
        fni_weak = st.number_input("FCF/NI Min",       0.1, 2.0, float(ue.get("fcf_to_net_income",{}).get("thresholds",{}).get("weak",0.50)), 0.05, key="fni_weak", format="%.2f")
    with u3:
        cx_exc  = st.number_input("Capex/Rev Excellent (%)", 1, 30, int(ue.get("low_capex_intensity",{}).get("thresholds",{}).get("excellent",0.05)*100), 1, key="cx_exc")
        cx_good = st.number_input("Capex/Rev Good (%)",      1, 30, int(ue.get("low_capex_intensity",{}).get("thresholds",{}).get("good",0.10)*100), 1, key="cx_good")
        cx_weak = st.number_input("Capex/Rev Max (%)",       1, 50, int(ue.get("low_capex_intensity",{}).get("thresholds",{}).get("weak",0.15)*100), 1, key="cx_weak")

    # Valuation
    st.markdown(f'<div style="color:{GOLD};font-size:0.78rem;font-weight:600;margin:12px 0 10px">Valuation</div>', unsafe_allow_html=True)
    v1, v2, v3 = st.columns(3)
    with v1:
        ee_exc  = st.number_input("EV/EBITDA Excellent (≤)", 1, 50, int(va.get("ev_ebitda",{}).get("thresholds",{}).get("excellent",8)), 1, key="ee_exc")
        ee_good = st.number_input("EV/EBITDA Good (≤)",      1, 50, int(va.get("ev_ebitda",{}).get("thresholds",{}).get("good",13)), 1, key="ee_good")
        ee_fair = st.number_input("EV/EBITDA Fair (≤)",      1, 80, int(va.get("ev_ebitda",{}).get("thresholds",{}).get("fair",18)), 1, key="ee_fair")
    with v2:
        pf_exc  = st.number_input("P/FCF Excellent (≤)", 1, 50, int(va.get("price_to_fcf",{}).get("thresholds",{}).get("excellent",12)), 1, key="pf_exc")
        pf_good = st.number_input("P/FCF Good (≤)",      1, 60, int(va.get("price_to_fcf",{}).get("thresholds",{}).get("good",20)), 1, key="pf_good")
        pf_fair = st.number_input("P/FCF Fair (≤)",      1, 80, int(va.get("price_to_fcf",{}).get("thresholds",{}).get("fair",30)), 1, key="pf_fair")
    with v3:
        pg_exc  = st.number_input("PEG Excellent (≤)", 0.1, 5.0, float(va.get("peg_ratio",{}).get("thresholds",{}).get("excellent",0.8)), 0.1, key="pg_exc", format="%.1f")
        pg_good = st.number_input("PEG Good (≤)",      0.1, 5.0, float(va.get("peg_ratio",{}).get("thresholds",{}).get("good",1.3)),    0.1, key="pg_good", format="%.1f")
        pg_fair = st.number_input("PEG Fair (≤)",      0.1, 5.0, float(va.get("peg_ratio",{}).get("thresholds",{}).get("fair",2.0)),    0.1, key="pg_fair", format="%.1f")

    # Ownership & Coverage
    st.markdown(f'<div style="color:{GOLD};font-size:0.78rem;font-weight:600;margin:12px 0 10px">Ownership & Coverage</div>', unsafe_allow_html=True)
    o1, o2, o3, o4 = st.columns(4)
    with o1:
        io_exc  = st.number_input("Insider Own. Excellent (%)", 1, 80, int(fo.get("insider_ownership",{}).get("thresholds",{}).get("excellent",0.20)*100), 5, key="io_exc")
        io_good = st.number_input("Insider Own. Good (%)",      1, 50, int(fo.get("insider_ownership",{}).get("thresholds",{}).get("good",0.10)*100), 5, key="io_good")
    with o2:
        ic_min_tx = st.number_input("Min insider tx ($K)", 1, 10000, int(fo.get("insider_conviction",{}).get("min_transaction_usd",50000)/1000), 25, key="ic_min_tx")
        ic_strong = st.number_input("Strong insider tx ($K)", 1, 50000, int(fo.get("insider_conviction",{}).get("strong_transaction_usd",1000000)/1000), 100, key="ic_strong")
        ic_window = st.number_input("Cluster window (days)", 1, 90, int(fo.get("insider_conviction",{}).get("cluster_window_days",14)), 1, key="ic_window")
    with o3:
        ac_exc  = st.number_input("Max Analysts Excellent", 0, 20, int(ie.get("analyst_coverage",{}).get("thresholds",{}).get("excellent",2)), 1, key="ac_exc")
        ac_good = st.number_input("Max Analysts Good",      1, 30, int(ie.get("analyst_coverage",{}).get("thresholds",{}).get("good",5)), 1, key="ac_good")
    with o4:
        mc_min = st.number_input("Sweet spot min ($M)", 0, 10000, int(ie.get("market_cap_sweet_spot",{}).get("min_usd",300_000_000)/1e6), 50, key="mc_min")
        mc_max_ss = st.number_input("Sweet spot max ($B)", 1, 100, int(ie.get("market_cap_sweet_spot",{}).get("max_usd",3_000_000_000)/1e9), 1, key="mc_max_ss")

    # Scalability
    st.markdown(f'<div style="color:{GOLD};font-size:0.78rem;font-weight:600;margin:12px 0 10px">Scalability</div>', unsafe_allow_html=True)
    s1, s2, _ = st.columns(3)
    with s1:
        rr_exc  = st.number_input("Recurring Rev. Excellent (%)", 1, 100, int(sc.get("recurring_revenue",{}).get("thresholds",{}).get("excellent",0.80)*100), 5, key="rr_exc")
        rr_good = st.number_input("Recurring Rev. Good (%)",      1, 100, int(sc.get("recurring_revenue",{}).get("thresholds",{}).get("good",0.60)*100), 5, key="rr_good")
        rr_weak = st.number_input("Recurring Rev. Min (%)",       1, 100, int(sc.get("recurring_revenue",{}).get("thresholds",{}).get("weak",0.40)*100), 5, key="rr_weak")

    # Collect all threshold changes
    new_thresholds = {
        "business_quality": {
            "gross_margin":     {"excellent": gm_exc/100,  "good": gm_good/100, "moderate": gm_floor/100},
            "operating_margin": {"excellent": om_exc/100,  "good": om_good/100, "weak": om_weak/100},
            "revenue_growth":   {"excellent": rg_exc/100,  "good": rg_good/100, "weak": rg_weak/100},
            "roa_roe":          {"roa_excellent": roa_exc/100, "roa_good": roa_good/100, "roe_excellent": roe_exc/100},
        },
        "unit_economics": {
            "fcf_yield":          {"excellent": fcfy_exc/100, "good": fcfy_good/100, "weak": fcfy_weak/100},
            "fcf_to_net_income":  {"excellent": fni_exc, "good": fni_good, "weak": fni_weak},
            "low_capex_intensity":{"excellent": cx_exc/100, "good": cx_good/100, "weak": cx_weak/100},
        },
        "valuation_asymmetry": {
            "ev_ebitda":    {"excellent": ee_exc, "good": ee_good, "fair": ee_fair},
            "price_to_fcf": {"excellent": pf_exc, "good": pf_good, "fair": pf_fair},
            "peg_ratio":    {"excellent": pg_exc, "good": pg_good, "fair": pg_fair},
        },
        "founder_ownership": {
            "insider_ownership":  {"excellent": io_exc/100, "good": io_good/100},
            "insider_conviction": {"min_transaction_usd": ic_min_tx*1000, "strong_transaction_usd": ic_strong*1000, "cluster_window_days": ic_window},
        },
        "information_edge": {
            "analyst_coverage":    {"excellent": ac_exc, "good": ac_good},
            "market_cap_sweet_spot": {"min_usd": mc_min*1_000_000, "max_usd": mc_max_ss*1_000_000_000},
        },
        "scalability": {
            "recurring_revenue": {"excellent": rr_exc/100, "good": rr_good/100, "weak": rr_weak/100},
        },
    }

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown(f'<div style="height:20px"></div>', unsafe_allow_html=True)

    # ── 5. Output Settings ────────────────────────────────────────────────────
    st.markdown(section_header("Output Settings"), unsafe_allow_html=True)
    st.markdown(
        f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:10px;padding:20px 24px">',
        unsafe_allow_html=True,
    )
    oc1, oc2 = st.columns(2)
    with oc1:
        daily_memos = st.number_input("Daily memos generated", min_value=1, max_value=50, value=5, key="daily_memos")
    with oc2:
        weekly_memos = st.number_input("Weekly memos generated", min_value=1, max_value=100, value=20, key="weekly_memos")
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown(f'<div style="height:20px"></div>', unsafe_allow_html=True)

    # ── 5. Phoenician Intelligence ────────────────────────────────────────────
    st.markdown(section_header("Phoenician Intelligence Integration"), unsafe_allow_html=True)
    st.markdown(
        f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:10px;padding:20px 24px">',
        unsafe_allow_html=True,
    )
    pi_enabled = st.checkbox("Enable PI integration", value=False, key="pi_enabled")
    if pi_enabled:
        pic1, pic2 = st.columns(2)
        with pic1:
            pi_endpoint = st.text_input("PI API Endpoint", placeholder="https://pi.phoenician.capital/api/diligence", key="pi_endpoint")
        with pic2:
            pi_key = st.text_input("API Key", type="password", placeholder="sk-…", key="pi_key")
        send_scores = st.checkbox("Send screener data with request", value=True, key="pi_send_scores")
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown(f'<div style="height:20px"></div>', unsafe_allow_html=True)

    # ── 6. Insider Buying Tracker ─────────────────────────────────────────────
    st.markdown(section_header("Insider Buying Tracker"), unsafe_allow_html=True)
    st.markdown(
        f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:10px;padding:20px 24px">',
        unsafe_allow_html=True,
    )
    ibc1, ibc2 = st.columns(2)
    with ibc1:
        lookback_days = st.number_input("Lookback window (days)", min_value=7, max_value=180, value=30, step=7, key="ib_lookback")
    with ibc2:
        min_tx_value = st.number_input("Min transaction value ($K)", min_value=1, max_value=10000, value=50, step=10, key="ib_min_tx")
    cluster_window = st.number_input("Cluster window (days — insiders must buy within this period)", min_value=3, max_value=30, value=14, step=1, key="ib_cluster_window")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(f'<div style="height:20px"></div>', unsafe_allow_html=True)

    # ── 7. Portfolio Holdings ─────────────────────────────────────────────────
    st.markdown(section_header("Portfolio Holdings", "Current positions used to compare candidates during screening"), unsafe_allow_html=True)
    st.markdown(
        f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:10px;padding:20px 24px">',
        unsafe_allow_html=True,
    )
    _render_portfolio_section()
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown(f'<div style="height:20px"></div>', unsafe_allow_html=True)

    # ── Save button ───────────────────────────────────────────────────────────
    st.markdown(f'<div style="height:24px"></div>', unsafe_allow_html=True)
    sc1, sc2, sc3 = st.columns([2, 1, 2])
    with sc2:
        if st.button("Save All Changes", key="btn_save", use_container_width=True):
            if abs(total_weight - 100) >= 0.5:
                st.error(f"Dimension weights must sum to 100 (currently {total_weight:.1f}). Adjust before saving.")
            else:
                # Merge threshold changes into category sub_criteria
                merged_cats = changes["categories"]
                for cat_key, sub_dict in new_thresholds.items():
                    cat = merged_cats.setdefault(cat_key, {})
                    sub = cat.setdefault("sub_criteria", {})
                    for crit_key, thr in sub_dict.items():
                        existing = sub.get(crit_key, {})
                        # Separate threshold keys from non-threshold keys (e.g. min_transaction_usd)
                        thr_keys = {"excellent","good","fair","weak","moderate",
                                    "roa_excellent","roa_good","roa_weak",
                                    "roe_excellent","roe_good","roe_weak"}
                        threshold_vals = {k:v for k,v in thr.items() if k in thr_keys}
                        direct_vals    = {k:v for k,v in thr.items() if k not in thr_keys}
                        if threshold_vals:
                            existing_thr = existing.get("thresholds", {})
                            existing_thr.update(threshold_vals)
                            existing["thresholds"] = existing_thr
                        existing.update(direct_vals)
                        sub[crit_key] = existing
                    cat["sub_criteria"] = sub
                    merged_cats[cat_key] = cat

                new_cfg = {
                    **cfg,
                    "hard_filters": changes["hard_filters"],
                    "categories": merged_cats,
                    "ranking": changes["ranking"],
                }
                save_settings(new_cfg)
                # Bust the weights cache so next run picks up new thresholds
                from src.config.scoring_weights import load_scoring_weights
                load_scoring_weights(force_reload=True)
                st.success("Settings saved. They will take effect on the next scoring run.")
