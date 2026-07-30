"""Simple shared-password gate.

Password comes from the PPA_APP_PASSWORD env var, defaulting to 'webadmin123'.
Override it on the VM (docker-compose env) so the real password isn't only in code.

Call require_auth() at the top of every page (after apply_theme) — it blocks the
page with st.stop() until the correct password is entered. Auth is per browser
session (st.session_state).
"""
import hmac
import os

import streamlit as st

_SESSION_KEY = "ppa_authed"


def _expected_password() -> str:
    return os.getenv("PPA_APP_PASSWORD", "webadmin123")


def require_auth() -> None:
    # Already signed in this session → show a logout control and continue.
    if st.session_state.get(_SESSION_KEY):
        with st.sidebar:
            if st.button("Log out"):
                st.session_state[_SESSION_KEY] = False
                st.rerun()
        return

    # Login screen.
    st.title("🔒 PPA Console")
    st.caption("Enter the password to continue.")
    with st.form("login"):
        pw = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Enter")
    if submitted:
        if hmac.compare_digest(pw, _expected_password()):
            st.session_state[_SESSION_KEY] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()  # nothing below renders until authenticated
