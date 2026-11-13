"""Fallow entry point. Run with: streamlit run app.py

This file sets up the page, the shared look, and the top navigation. Each
screen lives in ``views/``.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from fallow_ui import achievement_popup, inject_css, navbar
from larder.llm.client import load_project_env

load_project_env()

# Resolve from this file so the app runs from any working directory.
LOGO = str(Path(__file__).parent / "static" / "fallow-logo-app-192.png")
st.set_page_config(page_title="Fallow", page_icon=LOGO, layout="wide")
inject_css()

pages = [
    st.Page("views/dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True),
    st.Page("views/pantry.py", title="Pantry", icon=":material/kitchen:", url_path="pantry"),
    st.Page("views/farm.py", title="Soil & farm", icon=":material/agriculture:", url_path="farm"),
    st.Page("views/health.py", title="Health", icon=":material/monitor_heart:", url_path="health"),
    st.Page("views/recipes.py", title="Food & recipes", icon=":material/restaurant_menu:", url_path="recipes"),
    st.Page("views/cycle.py", title="Cycle", icon=":material/compost:", url_path="cycle"),
]
nav = st.navigation(pages, position="hidden")
navbar(pages, current=nav)
nav.run()

# A reward earned by a button on the page shows once, after the page renders.
reward = st.session_state.pop("fw_reward", None)
if reward is not None:
    achievement_popup(reward)
