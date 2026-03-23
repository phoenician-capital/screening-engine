"""
Clean light theme — Phoenician Capital Screening Engine.
White background, sharp type, minimal chrome. No icons.
"""

from __future__ import annotations

import streamlit as st

# ── Palette ───────────────────────────────────────────────────────────────────
BG_BASE      = "#ffffff"
BG_PAGE      = "#f7f8fa"
BG_CARD      = "#ffffff"
BG_CARD_ALT  = "#f7f8fa"
BORDER       = "#e2e5ea"
BORDER_LIGHT = "#eef0f3"
ACCENT       = "#1a1f2e"        # near-black — primary action / active
ACCENT2      = "#2d5be3"        # blue — links, active indicators
GREEN        = "#0d7a4e"
GREEN_BG     = "#eaf7f1"
RED          = "#c0392b"
RED_BG       = "#fdf2f1"
AMBER        = "#8a6000"
AMBER_BG     = "#fdf8ec"
TEXT_PRIMARY = "#0f1117"
TEXT_SECONDARY = "#4a5568"
TEXT_MUTED   = "#8a94a6"
TEXT_DIM     = "#c4cad4"

# ── Score helpers ─────────────────────────────────────────────────────────────
def score_color(score: float, inverted: bool = False) -> str:
    if inverted:
        if score >= 60:
            return RED
        if score >= 35:
            return AMBER
        return GREEN
    if score >= 70:
        return GREEN
    if score >= 50:
        return AMBER
    return RED

def score_bg(score: float, inverted: bool = False) -> str:
    if inverted:
        if score >= 60:
            return RED_BG
        if score >= 35:
            return AMBER_BG
        return GREEN_BG
    if score >= 70:
        return GREEN_BG
    if score >= 50:
        return AMBER_BG
    return RED_BG


def score_pill(score: float, max_score: float = 100, inverted: bool = False, label: str = "") -> str:
    color = score_color(score, inverted=inverted)
    bg = score_bg(score, inverted=inverted)
    display = f"{score:.0f}"
    if max_score != 100:
        display = f"{score:.0f}/{max_score:.0f}"
    lbl = f" {label}" if label else ""
    return (
        f'<span style="background:{bg};color:{color};border:1px solid {color}33;'
        f'padding:2px 10px;border-radius:4px;font-size:0.77rem;font-weight:700;'
        f'letter-spacing:0.01em;white-space:nowrap;font-variant-numeric:tabular-nums">'
        f'{display}{lbl}</span>'
    )


def mini_pill(label: str, color: str = ACCENT2) -> str:
    return (
        f'<span style="background:{color}12;color:{color};border:1px solid {color}33;'
        f'padding:1px 7px;border-radius:3px;font-size:0.70rem;font-weight:600;'
        f'white-space:nowrap">{label}</span>'
    )


def action_badge(action: str) -> str:
    configs = {
        "research_now": (GREEN, GREEN_BG, "Research Now"),
        "watch":        (AMBER, AMBER_BG, "Watch"),
        "reject":       (RED,   RED_BG,   "Reject"),
    }
    color, bg, label = configs.get(action, (TEXT_MUTED, BG_CARD_ALT, action.title()))
    return (
        f'<span style="background:{bg};color:{color};border:1px solid {color}44;'
        f'padding:2px 9px;border-radius:4px;font-size:0.72rem;font-weight:600">{label}</span>'
    )


def status_badge(status: str) -> str:
    configs = {
        "pending":     (TEXT_MUTED, BG_CARD_ALT, "Pending"),
        "researching": (GREEN,      GREEN_BG,     "Researching"),
        "watched":     (AMBER,      AMBER_BG,     "Watched"),
        "rejected":    (RED,        RED_BG,       "Rejected"),
    }
    color, bg, label = configs.get(status, (TEXT_MUTED, BG_CARD_ALT, status.title()))
    return (
        f'<span style="background:{bg};color:{color};border:1px solid {color}33;'
        f'padding:2px 9px;border-radius:4px;font-size:0.72rem;font-weight:600">{label}</span>'
    )


def score_bar_html(score: float, max_score: float, label: str, evidence: str = "") -> str:
    pct = min(100, (score / max_score) * 100) if max_score > 0 else 0
    color = score_color(score / max_score * 100)
    bg = score_bg(score / max_score * 100)
    evid_html = (
        f'<div style="color:{TEXT_MUTED};font-size:0.71rem;margin-top:3px">{evidence}</div>'
        if evidence else ""
    )
    return f"""
<div style="margin-bottom:12px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
    <span style="color:{TEXT_SECONDARY};font-size:0.82rem;font-weight:500">{label}</span>
    <span style="color:{color};font-size:0.82rem;font-weight:700;font-variant-numeric:tabular-nums">{score:.1f}&thinsp;/&thinsp;{max_score:.0f}</span>
  </div>
  <div style="background:{BORDER};border-radius:2px;height:5px;overflow:hidden">
    <div style="width:{pct:.1f}%;background:{color};height:100%;border-radius:2px"></div>
  </div>
  {evid_html}
</div>"""


def kpi_card_html(label: str, value: str, sub: str = "", delta: str = "", delta_positive: bool | None = None) -> str:
    delta_color = TEXT_MUTED
    if delta:
        delta_color = GREEN if delta_positive is True else (RED if delta_positive is False else TEXT_MUTED)
    delta_html = f'<div style="color:{delta_color};font-size:0.77rem;margin-top:4px">{delta}</div>' if delta else ""
    sub_html = f'<div style="color:{TEXT_MUTED};font-size:0.72rem;margin-top:3px">{sub}</div>' if sub else ""
    return f"""
<div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:6px;
            padding:16px 20px;height:100%;border-top:2px solid {ACCENT}">
  <div style="color:{TEXT_MUTED};font-size:0.68rem;font-weight:600;
              text-transform:uppercase;letter-spacing:0.09em;margin-bottom:8px">{label}</div>
  <div style="color:{TEXT_PRIMARY};font-size:1.55rem;font-weight:700;
              line-height:1;font-variant-numeric:tabular-nums">{value}</div>
  {sub_html}{delta_html}
</div>"""


def section_header(title: str, subtitle: str = "") -> str:
    sub_html = f'<div style="color:{TEXT_MUTED};font-size:0.81rem;margin-top:3px;font-weight:400">{subtitle}</div>' if subtitle else ""
    return f"""
<div style="margin:28px 0 14px;padding-bottom:10px;border-bottom:1px solid {BORDER}">
  <div style="color:{TEXT_PRIMARY};font-size:0.82rem;font-weight:700;
              text-transform:uppercase;letter-spacing:0.08em">{title}</div>
  {sub_html}
</div>"""


def divider_html() -> str:
    return f'<hr style="border:none;border-top:1px solid {BORDER};margin:20px 0">'


# ── Full CSS ───────────────────────────────────────────────────────────────────
_CSS = f"""
<style>
/* ── Base ─────────────────────────────────────── */
html, body, [class*="css"] {{
    font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    -webkit-font-smoothing: antialiased;
}}
.stApp {{
    background-color: {BG_PAGE};
    color: {TEXT_PRIMARY};
}}
.block-container {{
    padding-top: 2rem !important;
    max-width: 1400px;
}}

/* ── Sidebar ──────────────────────────────────── */
[data-testid="stSidebar"] {{
    background-color: {BG_CARD} !important;
    border-right: 1px solid {BORDER} !important;
}}
[data-testid="stSidebar"] .stMarkdown p {{
    color: {TEXT_MUTED};
    font-size: 0.78rem;
}}

/* ── Typography ───────────────────────────────── */
h1 {{
    color: {TEXT_PRIMARY} !important;
    font-size: 1.4rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.01em !important;
}}
h2 {{
    color: {TEXT_PRIMARY} !important;
    font-size: 1.05rem !important;
    font-weight: 600 !important;
}}
h3 {{
    color: {TEXT_SECONDARY} !important;
    font-size: 0.9rem !important;
    font-weight: 600 !important;
}}

/* ── Metrics ──────────────────────────────────── */
[data-testid="stMetric"] {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-top: 2px solid {ACCENT};
    border-radius: 6px;
    padding: 14px 18px !important;
}}
[data-testid="stMetricLabel"] {{
    color: {TEXT_MUTED} !important;
    font-size: 0.68rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.09em !important;
}}
[data-testid="stMetricValue"] {{
    color: {TEXT_PRIMARY} !important;
    font-size: 1.4rem !important;
    font-weight: 700 !important;
}}

/* ── Buttons ──────────────────────────────────── */
.stButton > button {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    color: {TEXT_SECONDARY};
    border-radius: 5px;
    font-size: 0.8rem;
    font-weight: 500;
    padding: 5px 14px;
    transition: all 0.12s ease;
    box-shadow: none;
}}
.stButton > button:hover {{
    border-color: {ACCENT};
    color: {ACCENT};
    background: {BG_PAGE};
}}
.stButton > button:focus {{
    box-shadow: 0 0 0 2px {ACCENT}22 !important;
    outline: none !important;
}}

/* ── Inputs ───────────────────────────────────── */
.stTextInput input,
.stNumberInput input {{
    background: {BG_CARD} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 5px !important;
    color: {TEXT_PRIMARY} !important;
    font-size: 0.85rem !important;
}}
.stTextInput input:focus,
.stNumberInput input:focus {{
    border-color: {ACCENT2} !important;
    box-shadow: 0 0 0 2px {ACCENT2}18 !important;
}}
div[data-baseweb="select"] > div {{
    background: {BG_CARD} !important;
    border-color: {BORDER} !important;
    color: {TEXT_PRIMARY} !important;
    border-radius: 5px !important;
}}
div[data-baseweb="select"] > div:focus-within {{
    border-color: {ACCENT2} !important;
}}

/* ── Tabs ─────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {{
    background: transparent;
    border-bottom: 1px solid {BORDER};
    gap: 0;
}}
.stTabs [data-baseweb="tab"] {{
    background: transparent;
    color: {TEXT_MUTED};
    border-bottom: 2px solid transparent;
    padding: 8px 18px;
    font-size: 0.82rem;
    font-weight: 500;
    margin-bottom: -1px;
}}
.stTabs [aria-selected="true"] {{
    color: {ACCENT} !important;
    border-bottom-color: {ACCENT} !important;
    background: transparent !important;
    font-weight: 600 !important;
}}
.stTabs [data-baseweb="tab-panel"] {{
    padding: 20px 0 0;
}}

/* ── Expanders ────────────────────────────────── */
[data-testid="stExpander"] {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-bottom: 6px;
}}
[data-testid="stExpander"] summary {{
    color: {TEXT_SECONDARY};
    font-size: 0.85rem;
    font-weight: 500;
}}

/* ── DataFrames ───────────────────────────────── */
[data-testid="stDataFrame"] {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    overflow: hidden;
}}
.dataframe thead tr th {{
    background: {BG_CARD_ALT} !important;
    color: {TEXT_MUTED} !important;
    font-size: 0.71rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.07em !important;
    border-bottom: 1px solid {BORDER} !important;
    font-weight: 600 !important;
}}
.dataframe tbody tr:hover td {{
    background: {BG_PAGE} !important;
}}
.dataframe tbody tr td {{
    color: {TEXT_PRIMARY} !important;
    font-size: 0.83rem !important;
    border-bottom: 1px solid {BORDER_LIGHT} !important;
}}

/* ── Dropdown popovers ────────────────────────── */
[data-baseweb="popover"] ul {{
    background: {BG_CARD} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 6px !important;
    box-shadow: 0 4px 16px rgba(0,0,0,0.08) !important;
}}
[data-baseweb="popover"] li {{
    color: {TEXT_PRIMARY} !important;
    font-size: 0.83rem !important;
}}
[data-baseweb="popover"] li:hover {{
    background: {BG_PAGE} !important;
}}

/* ── Sliders ──────────────────────────────────── */
[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"] {{
    background: {ACCENT} !important;
    border-color: {ACCENT} !important;
}}
[data-testid="stSlider"] [data-baseweb="slider"] div[class*="InnerTrack"] {{
    background: {ACCENT} !important;
}}

/* ── Checkboxes ───────────────────────────────── */
[data-testid="stCheckbox"] label {{
    color: {TEXT_PRIMARY} !important;
    font-size: 0.85rem !important;
}}

/* ── Alerts ───────────────────────────────────── */
.stAlert {{
    border-radius: 6px !important;
    font-size: 0.85rem !important;
}}

/* ── Dividers ─────────────────────────────────── */
hr {{
    border-color: {BORDER} !important;
    margin: 18px 0 !important;
}}

/* ── Scrollbar ────────────────────────────────── */
::-webkit-scrollbar {{ width: 5px; height: 5px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: {BORDER}; border-radius: 2px; }}
::-webkit-scrollbar-thumb:hover {{ background: {TEXT_DIM}; }}

/* ── Card containers ──────────────────────────── */
.ph-card {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 20px 24px;
    margin-bottom: 14px;
}}
.ph-card-accent {{
    border-top: 2px solid {ACCENT};
}}
.ph-card-green {{
    border-left: 3px solid {GREEN};
    background: {GREEN_BG};
}}
.ph-card-red {{
    border-left: 3px solid {RED};
    background: {RED_BG};
}}

/* ── Rank badge ───────────────────────────────── */
.ph-rank {{
    background: {BG_CARD_ALT};
    color: {TEXT_MUTED};
    width: 30px; height: 30px;
    border-radius: 50%;
    display: inline-flex;
    align-items: center; justify-content: center;
    font-size: 0.75rem; font-weight: 700;
    border: 1px solid {BORDER};
}}
.ph-rank-top {{
    background: {ACCENT};
    color: #fff;
    border-color: {ACCENT};
}}

/* ── Cluster card ─────────────────────────────── */
.ph-cluster-card {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-left: 3px solid {ACCENT};
    border-radius: 6px;
    padding: 14px 18px;
    margin-bottom: 8px;
}}

/* ── Triggered alert card ─────────────────────── */
.ph-alert-triggered {{
    background: {RED_BG};
    border: 1px solid {RED}33;
    border-left: 3px solid {RED};
    border-radius: 6px;
    padding: 14px 18px;
    margin-bottom: 8px;
}}

/* ── Empty state ──────────────────────────────── */
.ph-empty {{
    text-align: center;
    padding: 60px 20px;
    color: {TEXT_DIM};
}}
.ph-empty-icon {{
    font-size: 1.2rem;
    margin-bottom: 10px;
    opacity: 0.5;
    font-style: italic;
    color: {TEXT_MUTED};
}}
.ph-empty-text {{
    font-size: 0.88rem;
    color: {TEXT_MUTED};
}}

/* ── Table header rows ────────────────────────── */
.ph-table-header {{
    background: {BG_CARD_ALT};
    border: 1px solid {BORDER};
    border-radius: 6px 6px 0 0;
}}
.ph-table-row {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-top: none;
}}
.ph-table-row:hover {{
    background: {BG_PAGE};
}}
</style>
"""


def apply_theme() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


# ── Format helpers ────────────────────────────────────────────────────────────

def fmt_market_cap(value: float | None) -> str:
    if value is None:
        return "—"
    if value >= 1e9:
        return f"${value / 1e9:.2f}B"
    if value >= 1e6:
        return f"${value / 1e6:.0f}M"
    return f"${value:,.0f}"


def fmt_pct(value: float | None, decimals: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.{decimals}f}%"


def fmt_multiple(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.1f}x"


def fmt_dollar(value: float | None) -> str:
    if value is None:
        return "—"
    if abs(value) >= 1e9:
        return f"${value / 1e9:.2f}B"
    if abs(value) >= 1e6:
        return f"${value / 1e6:.1f}M"
    return f"${value:,.0f}"


def empty_state(icon: str, message: str) -> None:
    # icon param kept for API compatibility but not rendered as emoji
    st.markdown(
        f'<div class="ph-empty">'
        f'<div class="ph-empty-text">{message}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
