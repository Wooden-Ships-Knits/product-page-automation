"""Build page — a table of products; run them all; stream the log + links."""
import bootstrap  # noqa: F401  — first: sets sys.path + chdir

import time

import pandas as pd
import streamlit as st
from ui import apply_theme
from auth import require_auth
from services import run_lock
from services.runner import BuildRun, extract_links

apply_theme("Build · PPA", icon="🧵")
require_auth()

PRODUCTION_TYPES = ["unfix", "fixed", "sample", "sale_stock", "o4"]

st.title("Build product pages")
st.caption("One row per product. Add rows with the ➕ at the bottom of the table.")

# ---- lock state banner -----------------------------------------------------
if run_lock.is_locked():
    cur = run_lock.current() or {}
    st.warning(f"A run is in progress ({cur.get('label', '?')}). Wait for it to finish.")
    if st.button("Force-clear lock (only if a previous run crashed)"):
        run_lock.release()
        st.rerun()

# ---- editable table --------------------------------------------------------
blank = pd.DataFrame(
    [{"Season": "26 Fall", "Style": "", "Colors": "", "Production": "unfix"}]
)
edited = st.data_editor(
    blank,
    num_rows="dynamic",
    use_container_width=True,
    key="build_table",
    column_config={
        "Season": st.column_config.TextColumn("Season", help="e.g. 26 Fall", width="small"),
        "Style": st.column_config.TextColumn("Style", help="Master-data DESCRIPTION (exact)", width="large"),
        "Colors": st.column_config.TextColumn(
            "Colors", help="Comma-separated, e.g.  BLACK /PURE SNOW, NAVY", width="large"),
        "Production": st.column_config.SelectboxColumn("Production", options=PRODUCTION_TYPES, required=True),
    },
)

run_clicked = st.button("Run build", type="primary")

# ---- run -------------------------------------------------------------------
if run_clicked:
    rows, errors = [], []
    for i, r in edited.iterrows():
        style = str(r.get("Style") or "").strip()
        if not style:
            continue  # skip empty rows
        colors = [c.strip() for c in str(r.get("Colors") or "").split(",") if c.strip()]
        prod = str(r.get("Production") or "").strip()
        season = str(r.get("Season") or "").strip() or "26 Fall"
        if not colors:
            errors.append(f"'{style}': add at least one color.")
        if prod not in PRODUCTION_TYPES:
            errors.append(f"'{style}': pick a production type.")
        rows.append({"season": season, "Styles": style.upper(), "Colors": colors, "Production": prod})

    if errors:
        for e in errors:
            st.error(e)
        st.stop()
    if not rows:
        st.error("Add at least one row with a Style and Colors.")
        st.stop()

    try:
        run_lock.acquire("build")
    except run_lock.RunBusy:
        st.error("A run is already in progress.")
        st.stop()

    st.info(f"Running {len(rows)} product(s)…")
    run = BuildRun(rows)
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
        st.success(f"Finished {len(rows)} product(s).")

    links = extract_links(text)
    if links:
        st.subheader("Product links")
        for url in links:
            st.link_button(url.split("/products/")[-1] + " · open in Shopify", url)
    else:
        st.caption("No Shopify product links were produced (skips, or errors — check the log).")
