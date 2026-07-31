"""Return Products — one-button run of return_product.py with live logs."""
import bootstrap  # noqa: F401  — first: sets sys.path + chdir

import streamlit as st
from ui import apply_theme
from auth import require_auth
from services import run_lock
from services.return_products import run_return_streaming

apply_theme("Return Products · PPA", icon="🧵")
require_auth()

st.title("Return products")
st.caption(
    "Runs return_product.py — the bulk, sheet-driven create/update from the "
    "Master Grid of Return (today's worksheet)."
)

season = st.text_input(
    "Season", value="26 Fall",
    help="Which collection the styles belong to (selects the Master Data tab, e.g. 26 Fall → F26).",
)

if run_lock.is_locked():
    cur = run_lock.current() or {}
    st.warning(f"A run is in progress ({cur.get('label', '?')}). Wait for it to finish.")
    if st.button("Force-clear lock (only if a previous run crashed)"):
        run_lock.release()
        st.rerun()
else:
    if st.button("Run return products"):
        try:
            run_lock.acquire("return")
        except run_lock.RunBusy:
            st.error("A run is already in progress.")
            st.stop()

        log_box = st.empty()
        text = ""
        try:
            for line in run_return_streaming(season.strip() or "26 Fall"):
                text += line
                log_box.code(text, language="text")
        finally:
            run_lock.release()
        st.success("Return run finished — check the log above for per-row results.")
