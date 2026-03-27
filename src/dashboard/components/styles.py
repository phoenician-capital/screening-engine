"""
Phoenician Capital — Enterprise Dark Theme
Bloomberg-class financial terminal aesthetic.
Deep navy/charcoal, gold accents, precision typography.
"""

from __future__ import annotations

import streamlit as st

# ── Palette ───────────────────────────────────────────────────────────────────
BG_BASE        = "#0a0e1a"       # deep navy — page background
BG_SURFACE     = "#0f1422"       # slightly lighter — sidebar
BG_CARD        = "#141927"       # card/panel background
BG_CARD_HOVER  = "#1a2035"       # card hover
BG_INPUT       = "#1e253a"       # input fields
BG_TABLE_ROW   = "#141927"
BG_TABLE_ALT   = "#111825"
BG_TABLE_HEAD  = "#0d1120"

BORDER         = "#1e2840"       # subtle border
BORDER_LIGHT   = "#242d42"       # lighter border
BORDER_FOCUS   = "#3d5a9e"       # focus ring

GOLD           = "#c9a84c"       # primary brand accent
GOLD_LIGHT     = "#e8c96e"
GOLD_BG        = "#1a1600"

ACCENT_BLUE    = "#3d7eff"       # blue — info / links
ACCENT_BLUE_BG = "#0a1430"

GREEN          = "#00d4a0"       # positive / high score
GREEN_BG       = "#001a14"
GREEN_DARK     = "#00a87e"

RED            = "#ff4d6a"       # negative / high risk
RED_BG         = "#1a0010"
RED_DARK       = "#cc3d56"

AMBER          = "#f5a623"       # medium / watch
AMBER_BG       = "#1a1000"

TEAL           = "#00c2d4"
PURPLE         = "#7c3aed"

TEXT_PRIMARY   = "#e8eaf0"       # near-white
TEXT_SECONDARY = "#a0aabe"       # muted silver
TEXT_MUTED     = "#5a6480"       # dim
TEXT_DIM       = "#2e3752"       # very dim
TEXT_GOLD      = "#c9a84c"

FONT_MONO      = '"JetBrains Mono", "Fira Code", "Cascadia Code", "Courier New", monospace'
FONT_SANS      = '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif'


# ── Score helpers ─────────────────────────────────────────────────────────────
def score_color(score: float, inverted: bool = False) -> str:
    if inverted:
        if score >= 60: return RED
        if score >= 35: return AMBER
        return GREEN
    if score >= 70: return GREEN
    if score >= 50: return AMBER
    return RED

def score_bg(score: float, inverted: bool = False) -> str:
    if inverted:
        if score >= 60: return RED_BG
        if score >= 35: return AMBER_BG
        return GREEN_BG
    if score >= 70: return GREEN_BG
    if score >= 50: return AMBER_BG
    return RED_BG


def score_pill(score: float, max_score: float = 100, inverted: bool = False, label: str = "") -> str:
    color = score_color(score, inverted=inverted)
    bg    = score_bg(score, inverted=inverted)
    display = f"{score:.0f}"
    if max_score != 100:
        display = f"{score:.0f}/{max_score:.0f}"
    lbl = f" {label}" if label else ""
    return (
        f'<span style="background:{bg};color:{color};border:1px solid {color}40;'
        f'padding:2px 10px;border-radius:3px;font-size:0.75rem;font-weight:700;'
        f'letter-spacing:0.03em;white-space:nowrap;font-family:{FONT_MONO};'
        f'font-variant-numeric:tabular-nums">'
        f'{display}{lbl}</span>'
    )


def mini_pill(label: str, color: str = GOLD) -> str:
    return (
        f'<span style="background:{color}15;color:{color};border:1px solid {color}30;'
        f'padding:1px 8px;border-radius:3px;font-size:0.68rem;font-weight:600;'
        f'letter-spacing:0.04em;white-space:nowrap">{label}</span>'
    )


def action_badge(action: str) -> str:
    configs = {
        "research_now": (GREEN,  GREEN_BG,  "Research Now"),
        "watch":        (AMBER,  AMBER_BG,  "Watch"),
        "reject":       (RED,    RED_BG,    "Pass"),
    }
    color, bg, label = configs.get(action, (TEXT_MUTED, BG_CARD, action.title()))
    return (
        f'<span style="background:{bg};color:{color};border:1px solid {color}40;'
        f'padding:2px 10px;border-radius:3px;font-size:0.71rem;font-weight:700;'
        f'letter-spacing:0.05em">{label}</span>'
    )


def status_badge(status: str) -> str:
    configs = {
        "pending":     (TEXT_MUTED, BG_INPUT,  "Pending"),
        "researching": (GREEN,      GREEN_BG,  "Researching"),
        "watched":     (AMBER,      AMBER_BG,  "Watched"),
        "rejected":    (RED,        RED_BG,    "Passed"),
    }
    color, bg, label = configs.get(status, (TEXT_MUTED, BG_INPUT, status.title()))
    return (
        f'<span style="background:{bg};color:{color};border:1px solid {color}30;'
        f'padding:2px 9px;border-radius:3px;font-size:0.70rem;font-weight:600;'
        f'letter-spacing:0.04em">{label}</span>'
    )


def score_bar_html(score: float, max_score: float, label: str, evidence: str = "") -> str:
    pct   = min(100, (score / max_score) * 100) if max_score > 0 else 0
    norm  = score / max_score * 100 if max_score > 0 else 0
    color = score_color(norm)
    evid_html = (
        f'<div style="color:{TEXT_MUTED};font-size:0.69rem;margin-top:3px;'
        f'font-family:{FONT_SANS};line-height:1.4">{evidence}</div>'
        if evidence else ""
    )
    return f"""
<div style="margin-bottom:14px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px">
    <span style="color:{TEXT_SECONDARY};font-size:0.80rem;font-weight:500;font-family:{FONT_SANS}">{label}</span>
    <span style="color:{color};font-size:0.80rem;font-weight:700;font-family:{FONT_MONO};
                 font-variant-numeric:tabular-nums">{score:.1f}&thinsp;/&thinsp;{max_score:.0f}</span>
  </div>
  <div style="background:{BG_INPUT};border-radius:2px;height:4px;overflow:hidden">
    <div style="width:{pct:.1f}%;background:linear-gradient(90deg,{color}80,{color});
                height:100%;border-radius:2px;transition:width 0.4s ease"></div>
  </div>
  {evid_html}
</div>"""


def kpi_card_html(label: str, value: str, sub: str = "", delta: str = "", delta_positive: bool | None = None) -> str:
    delta_color = TEXT_MUTED
    if delta:
        delta_color = GREEN if delta_positive is True else (RED if delta_positive is False else AMBER)
    delta_html = f'<div style="color:{delta_color};font-size:0.75rem;margin-top:4px;font-family:{FONT_MONO}">{delta}</div>' if delta else ""
    sub_html   = f'<div style="color:{TEXT_MUTED};font-size:0.70rem;margin-top:4px;font-family:{FONT_SANS}">{sub}</div>' if sub else ""
    return f"""
<div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:6px;
            padding:18px 22px;height:100%;border-top:2px solid {GOLD};
            box-shadow:0 4px 24px rgba(0,0,0,0.25)">
  <div style="color:{TEXT_MUTED};font-size:0.65rem;font-weight:700;
              text-transform:uppercase;letter-spacing:0.12em;margin-bottom:10px;
              font-family:{FONT_SANS}">{label}</div>
  <div style="color:{TEXT_PRIMARY};font-size:1.65rem;font-weight:700;
              line-height:1;font-variant-numeric:tabular-nums;
              font-family:{FONT_MONO}">{value}</div>
  {sub_html}{delta_html}
</div>"""


def section_header(title: str, subtitle: str = "") -> str:
    sub_html = (
        f'<div style="color:{TEXT_MUTED};font-size:0.78rem;margin-top:4px;'
        f'font-weight:400;font-family:{FONT_SANS}">{subtitle}</div>'
    ) if subtitle else ""
    return f"""
<div style="margin:32px 0 16px;padding-bottom:12px;
            border-bottom:1px solid {BORDER}">
  <div style="color:{GOLD};font-size:0.65rem;font-weight:700;
              text-transform:uppercase;letter-spacing:0.14em;
              font-family:{FONT_SANS}">{title}</div>
  {sub_html}
</div>"""


def divider_html() -> str:
    return f'<hr style="border:none;border-top:1px solid {BORDER};margin:22px 0">'


# ── Full CSS ───────────────────────────────────────────────────────────────────
_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');

/* ── Reset & Base ──────────────────────────────── */
html, body, [class*="css"] {{
    font-family: {FONT_SANS};
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}}
.stApp {{
    background-color: {BG_BASE};
    color: {TEXT_PRIMARY};
}}
.block-container {{
    padding-top: 2rem !important;
    padding-left: 2.5rem !important;
    padding-right: 2.5rem !important;
    max-width: 1440px;
}}

/* ── Hide Streamlit chrome ─────────────────────── */
#MainMenu, footer, header {{ visibility: hidden; }}
[data-testid="stToolbar"] {{ display: none; }}
[data-testid="stDecoration"] {{ display: none; }}

/* ── Sidebar ──────────────────────────────────── */
[data-testid="stSidebar"] {{
    background: {BG_SURFACE} !important;
    border-right: 1px solid {BORDER} !important;
}}
[data-testid="stSidebar"] > div:first-child {{
    padding: 0 !important;
}}
[data-testid="stSidebar"] .stMarkdown p {{
    color: {TEXT_MUTED};
    font-size: 0.75rem;
}}

/* Radio nav */
[data-testid="stSidebar"] [data-testid="stRadio"] > label {{
    display: none !important;
}}
[data-testid="stSidebar"] [data-testid="stRadio"] > div {{
    display: flex !important;
    flex-direction: column !important;
    gap: 0 !important;
}}
[data-testid="stSidebar"] [data-testid="stRadio"] [data-baseweb="radio"] {{
    background: transparent !important;
    padding: 0 !important;
    margin: 0 !important;
}}
[data-testid="stSidebar"] [data-testid="stRadio"] [data-baseweb="radio"] > label {{
    padding: 11px 22px !important;
    margin: 0 !important;
    cursor: pointer !important;
    width: 100% !important;
    border-radius: 0 !important;
    border-left: 2px solid transparent !important;
    transition: all 0.15s ease !important;
}}
[data-testid="stSidebar"] [data-testid="stRadio"] [data-baseweb="radio"] > label:hover {{
    background: {BG_CARD} !important;
}}
[data-testid="stSidebar"] [data-testid="stRadio"] [data-baseweb="radio"] span:first-child {{
    display: none !important;
}}
[data-testid="stSidebar"] [data-testid="stRadio"] [data-baseweb="radio"] > label > div > p {{
    font-size: 0.82rem !important;
    color: {TEXT_MUTED} !important;
    font-weight: 400 !important;
    margin: 0 !important;
    letter-spacing: 0.01em !important;
}}
[data-testid="stSidebar"] [data-testid="stRadio"] [aria-checked="true"] > label {{
    background: {BG_CARD} !important;
    border-left-color: {GOLD} !important;
}}
[data-testid="stSidebar"] [data-testid="stRadio"] [aria-checked="true"] > label > div > p {{
    color: {TEXT_PRIMARY} !important;
    font-weight: 600 !important;
}}

/* ── Typography ───────────────────────────────── */
h1 {{
    color: {TEXT_PRIMARY} !important;
    font-size: 1.5rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em !important;
}}
h2 {{
    color: {TEXT_PRIMARY} !important;
    font-size: 1.1rem !important;
    font-weight: 600 !important;
}}
h3 {{
    color: {TEXT_SECONDARY} !important;
    font-size: 0.92rem !important;
    font-weight: 600 !important;
}}

/* ── Buttons ──────────────────────────────────── */
.stButton > button {{
    background: {BG_CARD};
    border: 1px solid {BORDER_LIGHT};
    color: {TEXT_SECONDARY};
    border-radius: 5px;
    font-size: 0.81rem;
    font-weight: 500;
    padding: 7px 18px;
    transition: all 0.15s ease;
    box-shadow: none;
    letter-spacing: 0.02em;
}}
.stButton > button:hover {{
    border-color: {GOLD};
    color: {GOLD};
    background: {GOLD_BG};
}}
.stButton > button:focus {{
    box-shadow: 0 0 0 2px {GOLD}30 !important;
    outline: none !important;
}}

/* ── Inputs ───────────────────────────────────── */
.stTextInput input,
.stNumberInput input {{
    background: {BG_INPUT} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 5px !important;
    color: {TEXT_PRIMARY} !important;
    font-size: 0.84rem !important;
}}
.stTextInput input:focus,
.stNumberInput input:focus {{
    border-color: {BORDER_FOCUS} !important;
    box-shadow: 0 0 0 2px {BORDER_FOCUS}25 !important;
}}
div[data-baseweb="select"] > div {{
    background: {BG_INPUT} !important;
    border-color: {BORDER} !important;
    color: {TEXT_PRIMARY} !important;
    border-radius: 5px !important;
}}
div[data-baseweb="select"] > div:focus-within {{
    border-color: {BORDER_FOCUS} !important;
}}

/* ── Metrics ──────────────────────────────────── */
[data-testid="stMetric"] {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-top: 2px solid {GOLD};
    border-radius: 6px;
    padding: 16px 20px !important;
    box-shadow: 0 4px 20px rgba(0,0,0,0.2);
}}
[data-testid="stMetricLabel"] {{
    color: {TEXT_MUTED} !important;
    font-size: 0.64rem !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.12em !important;
}}
[data-testid="stMetricValue"] {{
    color: {TEXT_PRIMARY} !important;
    font-size: 1.6rem !important;
    font-weight: 700 !important;
    font-family: {FONT_MONO} !important;
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
    padding: 10px 20px;
    font-size: 0.81rem;
    font-weight: 500;
    margin-bottom: -1px;
    letter-spacing: 0.03em;
    transition: color 0.15s;
}}
.stTabs [data-baseweb="tab"]:hover {{
    color: {TEXT_SECONDARY};
}}
.stTabs [aria-selected="true"] {{
    color: {GOLD} !important;
    border-bottom-color: {GOLD} !important;
    background: transparent !important;
    font-weight: 600 !important;
}}
.stTabs [data-baseweb="tab-panel"] {{
    padding: 22px 0 0;
}}

/* ── Expanders ────────────────────────────────── */
[data-testid="stExpander"] {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-bottom: 8px;
}}
[data-testid="stExpander"] summary {{
    color: {TEXT_SECONDARY};
    font-size: 0.85rem;
    font-weight: 500;
}}
[data-testid="stExpander"] summary:hover {{
    color: {TEXT_PRIMARY};
}}

/* ── DataFrames ───────────────────────────────── */
[data-testid="stDataFrame"] {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    overflow: hidden;
}}

/* ── Dropdown popovers ────────────────────────── */
[data-baseweb="popover"] ul {{
    background: {BG_CARD} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 6px !important;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4) !important;
}}
[data-baseweb="popover"] li {{
    color: {TEXT_PRIMARY} !important;
    font-size: 0.82rem !important;
}}
[data-baseweb="popover"] li:hover {{
    background: {BG_CARD_HOVER} !important;
}}

/* ── Sliders ──────────────────────────────────── */
[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"] {{
    background: {GOLD} !important;
    border-color: {GOLD} !important;
}}
[data-testid="stSlider"] [data-baseweb="slider"] div[class*="InnerTrack"] {{
    background: {GOLD} !important;
}}

/* ── Checkboxes ───────────────────────────────── */
[data-testid="stCheckbox"] label {{
    color: {TEXT_SECONDARY} !important;
    font-size: 0.84rem !important;
}}

/* ── Alerts ───────────────────────────────────── */
.stAlert {{
    border-radius: 5px !important;
    font-size: 0.84rem !important;
    background: {BG_CARD} !important;
    border-color: {BORDER} !important;
}}

/* ── Dividers ─────────────────────────────────── */
hr {{
    border-color: {BORDER} !important;
    margin: 20px 0 !important;
}}

/* ── Scrollbar ────────────────────────────────── */
::-webkit-scrollbar {{ width: 5px; height: 5px; }}
::-webkit-scrollbar-track {{ background: {BG_BASE}; }}
::-webkit-scrollbar-thumb {{ background: {BORDER_LIGHT}; border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: {TEXT_DIM}; }}

/* ── Card containers ──────────────────────────── */
.ph-card {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 20px 24px;
    margin-bottom: 12px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.15);
}}
.ph-card-gold {{
    border-top: 2px solid {GOLD};
}}
.ph-card-green {{
    border-left: 3px solid {GREEN};
}}
.ph-card-red {{
    border-left: 3px solid {RED};
}}
.ph-card-amber {{
    border-left: 3px solid {AMBER};
}}

/* ── Rank badge ───────────────────────────────── */
.ph-rank {{
    background: {BG_INPUT};
    color: {TEXT_MUTED};
    width: 32px; height: 32px;
    border-radius: 50%;
    display: inline-flex;
    align-items: center; justify-content: center;
    font-size: 0.74rem; font-weight: 700;
    border: 1px solid {BORDER_LIGHT};
    font-family: {FONT_MONO};
}}
.ph-rank-top {{
    background: linear-gradient(135deg, {GOLD}, {GOLD_LIGHT});
    color: #000;
    border-color: {GOLD};
}}

/* ── Cluster card ─────────────────────────────── */
.ph-cluster-card {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-left: 3px solid {GOLD};
    border-radius: 6px;
    padding: 14px 18px;
    margin-bottom: 8px;
}}

/* ── Triggered alert card ─────────────────────── */
.ph-alert-triggered {{
    background: {RED_BG};
    border: 1px solid {RED}30;
    border-left: 3px solid {RED};
    border-radius: 6px;
    padding: 14px 18px;
    margin-bottom: 8px;
}}

/* ── Empty state ──────────────────────────────── */
.ph-empty {{
    text-align: center;
    padding: 70px 20px;
}}
.ph-empty-text {{
    font-size: 0.88rem;
    color: {TEXT_MUTED};
}}

/* ── Table header rows ────────────────────────── */
.ph-table-header {{
    background: {BG_TABLE_HEAD};
    border: 1px solid {BORDER};
    border-radius: 6px 6px 0 0;
}}
.ph-table-row {{
    background: {BG_TABLE_ROW};
    border: 1px solid {BORDER};
    border-top: none;
    transition: background 0.1s;
}}
.ph-table-row:hover {{
    background: {BG_CARD_HOVER};
}}

/* ── Company row card ─────────────────────────── */
.ph-company-card {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-bottom: 4px;
    transition: border-color 0.15s, background 0.15s;
    cursor: pointer;
}}
.ph-company-card:hover {{
    border-color: {GOLD}60;
    background: {BG_CARD_HOVER};
}}

/* ── Progress step ────────────────────────────── */
.ph-step-active {{
    animation: pulse-gold 2s ease-in-out infinite;
}}
@keyframes pulse-gold {{
    0%, 100% {{ box-shadow: 0 0 0 0 {GOLD}40; }}
    50% {{ box-shadow: 0 0 0 6px {GOLD}00; }}
}}

/* ── Mono values ──────────────────────────────── */
.ph-mono {{
    font-family: {FONT_MONO};
    font-variant-numeric: tabular-nums;
}}

/* ── Gold text ────────────────────────────────── */
.ph-gold {{ color: {GOLD}; }}
.ph-green {{ color: {GREEN}; }}
.ph-red {{ color: {RED}; }}
.ph-muted {{ color: {TEXT_MUTED}; }}
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
    st.markdown(
        f'<div class="ph-empty">'
        f'<div class="ph-empty-text">{message}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
