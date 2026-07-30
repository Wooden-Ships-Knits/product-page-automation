"""Build page — set inputs, run production(), stream the log, show product links."""
import bootstrap  # noqa: F401  — first: sets sys.path + chdir

import time

import streamlit as st
from ui import apply_theme
from auth import require_auth
from services import run_lock
from services.runner import BuildRun, extract_links

apply_theme("Build · PPA", icon="🧵")
require_auth()

PRODUCTION_TYPES = ["unfix", "fixed", "sample", "sale_stock", "o4"]

st.title("Build product pages")

# ---- lock state banner -----------------------------------------------------
if run_lock.is_locked():
    cur = run_lock.current() or {}
    st.warning(f"A run is in progress ({cur.get('label', '?')}). Wait for it to finish.")
    if st.button("Force-clear lock (only if a previous run crashed)"):
        run_lock.release()
        st.rerun()

# ---- input form ------------------------------------------------------------
with st.form("build"):
    season = st.text_input("Season", value="26 Fall", help="e.g. '26 Fall' or '26 Spring'")
    style = st.text_input("Style", help="Must match the master-data DESCRIPTION exactly")
    colors_raw = st.text_input("Colors", help="One or more, comma-separated (e.g. BLACK /PURE SNOW)")
    prod_type = st.selectbox("Production type", PRODUCTION_TYPES)
    confirm = st.checkbox("I understand this creates/updates **live Shopify products**.")
    submitted = st.form_submit_button("Run build")

if submitted:
    colors = [c.strip() for c in colors_raw.split(",") if c.strip()]
    if not style.strip() or not colors:
        st.error("Style and at least one color are required.")
        st.stop()
    if not confirm:
        st.error("Please tick the confirmation box before running.")
        st.stop()

    try:
        run_lock.acquire("build")
    except run_lock.RunBusy:
        st.error("A run is already in progress.")
        st.stop()

    data = [{"Styles": style.strip().upper(), "Colors": colors, "Production": prod_type}]
    st.info(f"Running **{style.strip().upper()}** · {colors} · {prod_type} · {season}")

    run = BuildRun(data, season.strip())
    run.start()

    log_box = st.empty()
    text = ""
    try:
        while run.is_running():
            text += run.drain()
            log_box.code(text or "starting…", language="text")
            time.sleep(0.4)
        text += run.drain()          # flush the tail
        log_box.code(text, language="text")
    finally:
        run_lock.release()

    # ---- results -----------------------------------------------------------
    st.divider()
    if run.error:
        st.error("Build finished with an error — see the log above.")
    else:
        st.success("Build finished.")

    links = extract_links(text)
    if links:
        st.subheader("Product links")
        for url in links:
            st.link_button(url.split("/products/")[-1] + " · open in Shopify", url)
    else:
        st.caption("No Shopify product link was produced (skipped, or an error occurred).")
