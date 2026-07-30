"""
PPA web app — entry / home.

Run from the project root:
    ./venv/bin/streamlit run webapp/app.py

Additive layer over the existing PPA code: it imports & calls main.production(),
reads Output/ and cron_fetch.log, and never modifies any core file.
"""
import bootstrap  # noqa: F401  — MUST be first: sets sys.path + chdir to project root

import os
from pathlib import Path

import streamlit as st
from ui import apply_theme

apply_theme("PPA Console", icon="🧵")

st.title("🧵 PPA Console")
st.caption("Product Page Automation — trigger builds, watch them run, monitor the hourly fetch.")

st.markdown(
    "Use the pages in the sidebar:\n"
    "- **Build** — create/update product pages from style · colors · production type.\n"
    "- **Fetch Monitor** — view the hourly fetch log and run it on demand."
)

st.divider()
st.subheader("Environment")

creds_ok = bool(list(Path("credentials").glob("*.json"))) if Path("credentials").exists() else False
env_ok = Path("Setup/.env").exists()
im_base = os.getenv("IM_COLLECTION_BASE")

c1, c2, c3 = st.columns(3)
c1.metric("Service-account key", "found" if creds_ok else "MISSING")
c2.metric("Setup/.env", "found" if env_ok else "MISSING")
c3.metric("IM source", "VM cache" if im_base else "Mac Drive mount")

st.markdown(
    f"<span class='ppa-muted'>Working dir: <code>{os.getcwd()}</code><br>"
    f"IM_COLLECTION_BASE: <code>{im_base or '(unset — using Mac Drive mount)'}</code></span>",
    unsafe_allow_html=True,
)

if not (creds_ok and env_ok):
    st.warning("Credentials or .env not found in the working dir — builds will fail until these are present.")
