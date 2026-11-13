"""Fallow entry point. Run with: streamlit run app.py

This file sets up the page, the shared look, and the top navigation. Each
screen lives in ``views/``.
"""

from __future__ import annotations

import streamlit as st

from fallow_ui import inject_css
from larder.llm.client import load_project_env

load_project_env()

st.set_page_config(page_title="Fallow", page_icon=":material/eco:", layout="wide")
inject_css()

nav = st.navigation(
    [
        st.Page("views/dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True),
        st.Page("views/pantry.py", title="Pantry", icon=":material/kitchen:", url_path="pantry"),
        st.Page("views/farm.py", title="Soil & farm", icon=":material/agriculture:", url_path="farm"),
        st.Page("views/health.py", title="Health", icon=":material/monitor_heart:", url_path="health"),
        st.Page("views/recipes.py", title="Food & recipes", icon=":material/restaurant_menu:", url_path="recipes"),
        st.Page("views/cycle.py", title="Cycle", icon=":material/compost:", url_path="cycle"),
    ],
    position="top",
)
nav.run()
