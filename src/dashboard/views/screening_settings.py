"""
Settings — edit screening criteria, scoring weights, and hard filters.
All changes saved to scoring_weights.yaml and take effect on the next run.
"""
from __future__ import annotations
from pathlib import Path
import yaml
import streamlit as st
from src.config.settings import settings

_WEIGHTS_FILE = Path(settings.scoring.weights_file)

_DIM_LABELS = {
    "founder_ownership":   "Founder & Ownership",
    "business_quality":    "Business Quality",
    "unit_economics":      "Unit Economics",
    "valuation_asymmetry": "Valuation",
    "information_edge":    "Information Edge",
    "scalability":         "Scalability",
}
_DIM_DEFAULTS = {k: 16.67 for k in _DIM_LABELS}

_RISK_LABELS = {
    "leverage":               "Leverage",
    "customer_concentration": "Customer Concentration",
    "regulatory_risk":        "Regulatory Risk",
    "mgmt_turnover":          "Management Turnover",
    "accounting_flags":       "Accounting Quality",
    "geographic_risk":        "Geographic Risk",
}


def _load() -> dict:
    if _WEIGHTS_FILE.exists():
        with open(_WEIGHTS_FILE) as f:
            return yaml.safe_load(f) or {}
    return {}


def _save(data: dict) -> None:
    with open(_WEIGHTS_FILE, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def _section(title: str, subtitle: str = "") -> None:
    sub = f'<div style="font-size:0.81rem;color:#6b7280;margin-top:3px">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f'<div style="margin:28px 0 16px;padding-bottom:10px;border-bottom:1px solid #e8eaed">'
        f'<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:0.09em;color:#374151">{title}</div>{sub}</div>',
        unsafe_allow_html=True,
    )


def render() -> None:
    st.markdown("""
    <div style="margin-bottom:28px">
      <div style="font-size:1.35rem;font-weight:700;color:#111827;letter-spacing:-0.01em">Settings</div>
      <div style="font-size:0.84rem;color:#6b7280;margin-top:4px">
        Configure screening criteria. Changes take effect on the next run.
      </div>
    </div>
    """, unsafe_allow_html=True)

    cfg  = _load()
    hard = cfg.get("hard_filters", {})
    cats = cfg.get("categories", {})
    rank = cfg.get("ranking", {})

    # ── 1. Hard Filters ───────────────────────────────────────────────────────
    _section("Hard Filters", "Companies failing any active filter are excluded before scoring begins")

    st.markdown('<div style="background:#ffffff;border:1px solid #e8eaed;border-radius:8px;padding:24px 28px">', unsafe_allow_html=True)

    hc1, hc2, hc3 = st.columns(3)

    with hc1:
        st.markdown('<div style="font-size:0.72rem;font-weight:600;color:#374151;margin-bottom:12px">Market Cap</div>', unsafe_allow_html=True)
        min_cap = st.number_input(
            "Min ($M)",
            min_value=0, max_value=5000,
            value=int(float(hard.get("hard_min_market_cap", 100_000_000)) / 1e6),
            step=25,
        )
        max_cap = st.number_input(
            "Max ($B)",
            min_value=1, max_value=100,
            value=int(float(hard.get("hard_max_market_cap", 10_000_000_000)) / 1e9),
            step=1,
        )

    with hc2:
        st.markdown('<div style="font-size:0.72rem;font-weight:600;color:#374151;margin-bottom:12px">Financial Thresholds</div>', unsafe_allow_html=True)
        leverage_on = st.checkbox(
            "Leverage cap (Net Debt / EBITDA)",
            value=True,
        )
        max_lev = st.number_input(
            "Max Net Debt / EBITDA",
            min_value=0.0, max_value=20.0,
            value=float(hard.get("max_leverage", 5.0)),
            step=0.5,
            disabled=not leverage_on,
        )
        margin_on = st.checkbox(
            "Gross margin floor",
            value=True,
        )
        min_margin = st.number_input(
            "Min gross margin (%)",
            min_value=0, max_value=90,
            value=int(float(hard.get("min_gross_margin_2yr", 0.20)) * 100),
            step=5,
            disabled=not margin_on,
        )

    with hc3:
        st.markdown('<div style="font-size:0.72rem;font-weight:600;color:#374151;margin-bottom:12px">Sector Exclusions</div>', unsafe_allow_html=True)
        excl_sectors = hard.get("excluded_gics_sectors", ["10", "55"])
        excl_energy    = st.checkbox("Energy (GICS 10)",        value="10" in excl_sectors)
        excl_utilities = st.checkbox("Utilities (GICS 55)",     value="55" in excl_sectors)
        excl_biotech   = st.checkbox("Biotech (GICS 35201010)", value=True)

        st.markdown('<div style="margin-top:12px;font-size:0.72rem;font-weight:600;color:#374151;margin-bottom:6px">Geography Exclusions</div>', unsafe_allow_html=True)
        excl_china  = st.checkbox("Mainland China", value=True)
        excl_russia = st.checkbox("Russia",         value=True)
        excl_iran   = st.checkbox("Iran",           value=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # ── 2. Scoring Dimension Weights ──────────────────────────────────────────
    _section("Scoring Dimension Weights", "Each dimension contributes to the Fit Score (0–100). Total must equal 100.")

    st.markdown('<div style="background:#ffffff;border:1px solid #e8eaed;border-radius:8px;padding:24px 28px">', unsafe_allow_html=True)

    wc1, wc2 = st.columns(2)
    new_weights: dict[str, float] = {}
    dim_keys = list(_DIM_LABELS.keys())

    for i, key in enumerate(dim_keys):
        label   = _DIM_LABELS[key]
        current = float(cats.get(key, {}).get("weight", _DIM_DEFAULTS[key]))
        col     = wc1 if i % 2 == 0 else wc2
        with col:
            new_weights[key] = st.slider(label, min_value=5.0, max_value=35.0, value=current, step=0.5, key=f"w_{key}")

    total = sum(new_weights.values())
    ok    = abs(total - 100) < 0.5
    c     = "#059669" if ok else "#dc2626"
    st.markdown(
        f'<div style="text-align:right;margin-top:8px;font-size:0.83rem">'
        f'Total: <span style="color:{c};font-weight:700;font-variant-numeric:tabular-nums">'
        f'{total:.1f}</span> / 100'
        f'{"" if ok else " — must equal 100"}</div>',
        unsafe_allow_html=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # ── 3. Ranking Formula ────────────────────────────────────────────────────
    _section("Ranking Formula", "How Fit and Risk scores are combined into the final composite rank")

    st.markdown('<div style="background:#ffffff;border:1px solid #e8eaed;border-radius:8px;padding:24px 28px">', unsafe_allow_html=True)

    rc1, rc2, rc3 = st.columns([2, 2, 3])
    cur_fit = int(float(rank.get("fit_weight", 0.50)) * 100)

    with rc1:
        fit_w = st.number_input("Fit Score weight (%)", min_value=10, max_value=90, value=cur_fit, step=5)
    with rc2:
        risk_w = 100 - fit_w
        st.markdown(
            f'<div style="padding-top:26px;font-size:0.85rem;color:#374151">'
            f'Risk penalty: <strong>{risk_w}%</strong></div>',
            unsafe_allow_html=True,
        )
    with rc3:
        st.markdown(
            f'<div style="padding-top:20px;font-size:0.79rem;color:#9ca3af;'
            f'font-family:ui-monospace,monospace;line-height:1.6">'
            f'rank = fit × {fit_w/100:.2f} − risk × {risk_w/100:.2f}'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Save ──────────────────────────────────────────────────────────────────
    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    sc1, sc2, sc3 = st.columns([2, 1, 2])
    with sc2:
        save = st.button("Save Changes", key="save_settings", use_container_width=True)

    if save:
        if not ok:
            st.error(f"Dimension weights must sum to 100 (currently {total:.1f}). Adjust sliders before saving.")
        else:
            # Build new sectors list
            new_sectors = []
            if excl_energy:    new_sectors.append("10")
            if excl_utilities: new_sectors.append("55")
            new_sub = ["35201010"] if excl_biotech else []

            new_cats = {}
            for key in dim_keys:
                existing = cats.get(key, {})
                new_cats[key] = {**existing, "weight": new_weights[key]}

            new_cfg = {
                **cfg,
                "hard_filters": {
                    **hard,
                    "excluded_gics_sectors":       new_sectors,
                    "excluded_gics_sub_industries": new_sub,
                    "max_leverage":                max_lev if leverage_on else 999.0,
                    "min_gross_margin_2yr":        (min_margin / 100.0) if margin_on else -999.0,
                    "hard_min_market_cap":         min_cap * 1_000_000,
                    "hard_max_market_cap":         max_cap * 1_000_000_000,
                },
                "categories": new_cats,
                "ranking": {
                    **rank,
                    "fit_weight":           fit_w / 100,
                    "risk_penalty_weight":  risk_w / 100,
                },
            }
            # Reload weights cache so next scoring run picks up changes immediately
            from src.config.scoring_weights import load_scoring_weights
            load_scoring_weights(force_reload=True)

            # Audit log — append to a simple JSONL file
            import datetime as _dt, json as _json
            audit_path = _WEIGHTS_FILE.parent / "settings_audit.jsonl"
            audit_entry = {
                "timestamp": _dt.datetime.utcnow().isoformat() + "Z",
                "weights": {k: new_weights[k] for k in dim_keys},
                "fit_weight": fit_w / 100,
                "risk_weight": risk_w / 100,
                "max_leverage": max_lev if leverage_on else None,
                "min_gross_margin": (min_margin / 100.0) if margin_on else None,
                "min_market_cap_m": min_cap,
                "max_market_cap_b": max_cap,
            }
            with open(audit_path, "a") as _f:
                _f.write(_json.dumps(audit_entry) + "\n")

            _save(new_cfg)
            st.success("Settings saved. Changes are active immediately for the next scoring run.")
