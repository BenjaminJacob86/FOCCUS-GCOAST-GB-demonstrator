"""FOCCUS demonstrator — two-page Streamlit app (About + Dashboard).

Run (German Bight, default):
  streamlit run app_pmtiles_assessment_two_paged_s3.py

Run (Black Sea / Douglas data):
  APP_CONFIG=config/black_sea_douglas.yaml streamlit run app_pmtiles_assessment_two_paged_s3.py
"""

from __future__ import annotations

import streamlit as st

from app_config import get_config
from foccus_about_page import render_about_page

cfg = get_config()

st.set_page_config(
    page_title=cfg.page_title,
    layout="wide",
    initial_sidebar_state="collapsed",
)

about = st.Page(render_about_page, title="About", icon="📖", default=True)
dashboard = st.Page("foccus_dashboard_page.py", title="Dashboard", icon="🗺️")

pg = st.navigation([about, dashboard])
pg.run()
