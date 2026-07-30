"""Shared UI helpers: page config + theming (background/colors/font).

Theme is applied via injected CSS so it works regardless of where Streamlit
reads its config from. Tweak the COLORS below to restyle the whole app.
"""
import streamlit as st

# ---- tweak these to change the look ---------------------------------------
BG        = "#14141f"   # page background
BG2       = "#20202e"   # cards / inputs / sidebar
ACCENT    = "#e07a5f"   # buttons, highlights
TEXT      = "#f2f2f5"   # main text
MUTED     = "#9aa0b0"   # secondary text
# ---------------------------------------------------------------------------

_CSS = f"""
<style>
  .stApp {{ background: {BG}; color: {TEXT}; }}
  section[data-testid="stSidebar"] {{ background: {BG2}; }}
  h1, h2, h3, h4 {{ color: {TEXT}; }}
  .stApp p, .stApp label, .stApp span {{ color: {TEXT}; }}
  div.stButton > button, div.stDownloadButton > button {{
      background: {ACCENT}; color: #14141f; border: 0; border-radius: 10px;
      font-weight: 600; padding: 0.5rem 1.1rem;
  }}
  div.stButton > button:hover {{ filter: brightness(1.08); }}
  .stTextInput input, .stSelectbox div[data-baseweb="select"] > div {{
      background: {BG2}; color: {TEXT};
  }}
  code, pre, .stCode {{ background: {BG2} !important; }}
  #MainMenu, footer {{ visibility: hidden; }}
  .ppa-muted {{ color: {MUTED}; font-size: 0.9rem; }}
</style>
"""


def apply_theme(title: str, icon: str = "🧵") -> None:
    """Call at the very top of every page (before other st.* calls)."""
    st.set_page_config(page_title=title, page_icon=icon, layout="wide")
    st.markdown(_CSS, unsafe_allow_html=True)
