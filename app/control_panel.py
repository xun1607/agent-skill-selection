"""Local Registry and SWE-bench experiment console.

Run from the repository root:
    streamlit run app/control_panel.py
"""
from pathlib import Path
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

st.set_page_config(
    page_title="Agent skill experiment console",
    page_icon=":material/science:",
    layout="wide",
)

page = st.navigation(
    [
        st.Page("app_pages/registry.py", title="Registry", icon=":material/database:"),
        st.Page("app_pages/swebench_runs.py", title="SWE-bench experiments", icon=":material/science:"),
    ],
    position="top",
)

st.title(page.title, icon=page.icon)
page.run()
