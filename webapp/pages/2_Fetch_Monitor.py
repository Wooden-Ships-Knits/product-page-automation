"""Fetch Monitor — view the hourly fetch log and run it on demand."""
import bootstrap  # noqa: F401  — first: sets sys.path + chdir

import streamlit as st
from ui import apply_theme
from services import run_lock, fetch

apply_theme("Fetch Monitor · PPA", icon="🧵")

st.title("Hourly fetch monitor")
st.caption("fetch_id.fetch() + fetch_image.list_shop_files() — refreshes the PP SY LIST & Links storage snapshots.")

col1, col2 = st.columns([3, 1])
col1.metric("Last run (from log)", fetch.last_run_hint())
if col2.button("🔄 Refresh log"):
    st.rerun()

# ---- run on demand ---------------------------------------------------------
st.divider()
if run_lock.is_locked():
    st.warning("A run is in progress — can't start a fetch right now.")
else:
    if st.button("Run fetch now"):
        try:
            run_lock.acquire("fetch")
        except run_lock.RunBusy:
            st.error("A run is already in progress.")
            st.stop()
        log_box = st.empty()
        text = ""
        try:
            for line in fetch.run_fetch_streaming():
                text += line
                log_box.code(text, language="text")
        finally:
            run_lock.release()
        st.success("Fetch finished.")

# ---- log tail --------------------------------------------------------------
st.divider()
st.subheader("cron_fetch.log (tail)")
st.code(fetch.read_log(), language="text")
