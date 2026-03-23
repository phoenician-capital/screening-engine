"""
Phoenician Capital — Screening Engine
Run: streamlit run src/dashboard/app.py --server.port 5000
"""
from __future__ import annotations
import logging
import sys
import streamlit as st

# Initialise logging so all pipeline logs appear in docker logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
    force=True,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

st.set_page_config(
    page_title="Phoenician Capital",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Inter", sans-serif;
    -webkit-font-smoothing: antialiased;
}

/* Page background */
.stApp { background: #f5f6f8; }
.block-container { padding: 2.5rem 2.5rem 2rem !important; max-width: 1280px; }

/* Hide Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 1px solid #e2e5ea !important;
}
[data-testid="stSidebar"] > div:first-child {
    padding: 0 !important;
}

/* Radio nav — hide the default radio widget chrome */
[data-testid="stSidebar"] [data-testid="stRadio"] > label {
    display: none !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] > div {
    display: flex !important;
    flex-direction: column !important;
    gap: 0 !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] [data-baseweb="radio"] {
    background: transparent !important;
    padding: 0 !important;
    margin: 0 !important;
}
/* The actual radio button row */
[data-testid="stSidebar"] [data-testid="stRadio"] [data-baseweb="radio"] > label {
    padding: 10px 20px !important;
    margin: 0 !important;
    cursor: pointer !important;
    width: 100% !important;
    border-radius: 0 !important;
    border-left: 3px solid transparent !important;
    transition: background 0.1s !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] [data-baseweb="radio"] > label:hover {
    background: #f3f4f6 !important;
}
/* Hide the circle dot */
[data-testid="stSidebar"] [data-testid="stRadio"] [data-baseweb="radio"] span:first-child {
    display: none !important;
}
/* Label text */
[data-testid="stSidebar"] [data-testid="stRadio"] [data-baseweb="radio"] > label > div > p {
    font-size: 0.84rem !important;
    color: #6b7280 !important;
    font-weight: 400 !important;
    margin: 0 !important;
}
/* Selected item */
[data-testid="stSidebar"] [data-testid="stRadio"] [aria-checked="true"] > label {
    background: #f3f4f6 !important;
    border-left-color: #111827 !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] [aria-checked="true"] > label > div > p {
    color: #111827 !important;
    font-weight: 600 !important;
}

/* ── Buttons ── */
.stButton > button {
    background: #ffffff;
    border: 1px solid #d1d5db;
    color: #374151;
    border-radius: 5px;
    font-size: 0.82rem;
    font-weight: 500;
    padding: 6px 16px;
    transition: border-color 0.1s, color 0.1s;
    width: 100%;
    box-shadow: none !important;
}
.stButton > button:hover {
    border-color: #111827;
    color: #111827;
    background: #fafafa;
}
.stButton > button:focus { outline: none !important; box-shadow: none !important; }

/* ── Inputs ── */
.stTextInput input, .stNumberInput input {
    background: #ffffff !important;
    border: 1px solid #d1d5db !important;
    border-radius: 5px !important;
    font-size: 0.85rem !important;
    color: #111827 !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
    border-color: #111827 !important;
    box-shadow: 0 0 0 2px rgba(17,24,39,0.08) !important;
}
div[data-baseweb="select"] > div {
    background: #ffffff !important;
    border-color: #d1d5db !important;
    border-radius: 5px !important;
    font-size: 0.85rem !important;
}

/* ── Sliders ── */
[data-testid="stSlider"] [role="slider"] { background: #111827 !important; border-color: #111827 !important; }
[data-testid="stSlider"] div[class*="InnerTrack"] { background: #111827 !important; }

/* ── Checkboxes ── */
[data-testid="stCheckbox"] label { font-size: 0.84rem !important; color: #374151 !important; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: transparent;
    border-bottom: 1px solid #e8eaed;
    gap: 0;
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    color: #9ca3af;
    border-bottom: 2px solid transparent;
    padding: 9px 20px;
    font-size: 0.83rem;
    font-weight: 500;
    margin-bottom: -1px;
}
.stTabs [aria-selected="true"] {
    color: #111827 !important;
    border-bottom-color: #111827 !important;
    font-weight: 600 !important;
    background: transparent !important;
}

/* ── Expanders ── */
[data-testid="stExpander"] {
    background: #ffffff;
    border: 1px solid #e8eaed;
    border-radius: 6px;
}

/* ── Misc ── */
.stAlert { border-radius: 5px !important; font-size: 0.84rem !important; }
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 2px; }
[data-testid="stDataFrame"] { border: 1px solid #e8eaed; border-radius: 6px; overflow: hidden; }
hr { border-color: #e8eaed !important; margin: 16px 0 !important; }
</style>
""", unsafe_allow_html=True)

# ── Session state ──────────────────────────────────────────────────────────────
if "page" not in st.session_state:
    st.session_state.page = "Run Screening"

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    # Brand header
    st.markdown("""
    <div style="padding:28px 20px 16px">
      <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.14em;color:#111827">Phoenician Capital</div>
      <div style="font-size:0.68rem;color:#9ca3af;margin-top:3px">Screening Engine</div>
    </div>
    <div style="height:1px;background:#e2e5ea;margin:0 0 8px"></div>
    """, unsafe_allow_html=True)

    # Nav — single radio widget, no gaps
    pages = ["Run Screening", "Results", "Portfolio Monitor", "Settings"]
    selected = st.radio(
        "nav",
        pages,
        index=pages.index(st.session_state.page),
        label_visibility="collapsed",
    )
    if selected != st.session_state.page:
        st.session_state.page = selected
        st.rerun()

    # Footer
    st.markdown("""
    <div style="padding:24px 20px 20px">
      <div style="font-size:0.64rem;color:#d1d5db;border-top:1px solid #e8eaed;padding-top:12px">
        Confidential — Internal Use Only
      </div>
    </div>
    """, unsafe_allow_html=True)

# ── Route ──────────────────────────────────────────────────────────────────────
page = st.session_state.page

if page == "Run Screening":
    from src.dashboard.views.run_screening import render
    render()
elif page == "Results":
    from src.dashboard.views.results import render
    render()
elif page == "Portfolio Monitor":
    from src.dashboard.views.portfolio_monitor import render
    render()
elif page == "Settings":
    from src.dashboard.views.screening_settings import render
    render()
