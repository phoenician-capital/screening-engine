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

# Apply the dark enterprise theme
from src.dashboard.components.styles import apply_theme, _CSS
apply_theme()

# ── Session state ──────────────────────────────────────────────────────────────
if "page" not in st.session_state:
    st.session_state.page = "Run Screening"

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    # Brand identity block
    st.markdown("""
    <div style="padding:32px 22px 20px">
      <div style="font-size:0.60rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.22em;color:#5a6480;margin-bottom:10px">
        PHOENICIAN CAPITAL
      </div>
      <div style="font-size:1.05rem;font-weight:700;color:#e8eaf0;
                  letter-spacing:-0.01em;line-height:1.2">
        Screening<br>Engine
      </div>
      <div style="margin-top:8px;font-size:0.68rem;color:#c9a84c;
                  font-weight:500;letter-spacing:0.04em">
        AI-Powered · Global Universe
      </div>
    </div>
    <div style="height:1px;background:linear-gradient(90deg,transparent,#1e2840,transparent);
                margin:0 0 16px"></div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="padding:0 22px 6px">
      <div style="font-size:0.60rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.14em;color:#2e3752">NAVIGATION</div>
    </div>
    """, unsafe_allow_html=True)

    pages = ["Run Screening", "Results", "Portfolio Monitor", "Filters"]
    selected = st.radio(
        "nav",
        pages,
        index=pages.index(st.session_state.page),
        label_visibility="collapsed",
    )
    if selected != st.session_state.page:
        st.session_state.page = selected
        st.rerun()

    # Spacer then status
    st.markdown("""
    <div style="height:1px;background:linear-gradient(90deg,transparent,#1e2840,transparent);
                margin:20px 0 16px"></div>
    <div style="padding:0 22px 28px">
      <div style="font-size:0.60rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.12em;color:#2e3752;margin-bottom:10px">SYSTEM</div>
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:7px">
        <div style="width:6px;height:6px;border-radius:50%;background:#00d4a0;
                    box-shadow:0 0 6px #00d4a080"></div>
        <span style="font-size:0.73rem;color:#5a6480">Engine Online</span>
      </div>
      <div style="display:flex;align-items:center;gap:8px">
        <div style="width:6px;height:6px;border-radius:50%;background:#00d4a0;
                    box-shadow:0 0 6px #00d4a080"></div>
        <span style="font-size:0.73rem;color:#5a6480">Analyst Agent Ready</span>
      </div>
    </div>
    <div style="padding:16px 22px;border-top:1px solid #1e2840">
      <div style="font-size:0.62rem;color:#2e3752;letter-spacing:0.04em">
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
elif page == "Filters":
    from src.dashboard.views.screening_settings import render
    render()
