"""
HYDRA — A multi-headed market terminal.
Each function code is another head. Cut one off, two grow back.

Command bar syntax (Bloomberg convention):
    <TICKER> <FUNCTION>     e.g.  AAPL DES    NVDA GP    MSFT FA
    <FUNCTION>              e.g.  HOME        WATCH

Supported functions: HOME, DES, GP, FA, HRH, WATCH
"""
from __future__ import annotations

import streamlit as st

from lib.styles import apply_theme, render_header
from lib.views import bt_view, des_view, fa_view, gp_view, home_view, hrh_view,  watch_view

st.set_page_config(
    page_title="HYDRA",
    page_icon="☰",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_theme()
render_header()

# --- State ----------------------------------------------------------------

if "ticker" not in st.session_state:
    st.session_state.ticker = "AAPL"
if "function" not in st.session_state:
    st.session_state.function = "HOME"


# --- Sidebar: function menu -----------------------------------------------

st.sidebar.markdown("## FUNCTIONS")
FUNCTIONS = {
    "HOME":  "Market Overview",
    "DES":   "Security Description",
    "GP":    "Price Graph",
    "FA":    "Fundamentals",
    "HRH":   "Historical Regimes",
    "BT":    "Backtester",
    "WATCH": "Watchlist",
}
for code, label in FUNCTIONS.items():
    if st.sidebar.button(f"{code:<6} · {label}", use_container_width=True, key=f"nav_{code}"):
        st.session_state.function = code

st.sidebar.markdown("---")
st.sidebar.markdown(
    "<small style='color:#888'>"
    "Data: yfinance (free, 15-min delayed).<br>"
    "Not for trading use."
    "</small>",
    unsafe_allow_html=True,
)


# --- Command bar ----------------------------------------------------------

c1, c2, c3 = st.columns([4, 2, 2])
with c1:
    cmd = st.text_input(
        "Command",
        value=f"{st.session_state.ticker} {st.session_state.function}",
        label_visibility="collapsed",
        placeholder="e.g.  AAPL DES    |    NVDA GP    |    HOME",
        key="cmd_input",
    )
with c2:
    go_clicked = st.button("GO", use_container_width=True, type="primary")
with c3:
    st.markdown(
        f"<div style='text-align:right;color:#FFC266;padding-top:6px;font-size:12px'>"
        f"▸ {st.session_state.function} · {st.session_state.ticker}"
        f"</div>",
        unsafe_allow_html=True,
    )


# Parse the command whenever GO is pressed or on first load
def parse_cmd(raw: str) -> tuple[str, str]:
    parts = [p.strip().upper() for p in raw.split() if p.strip()]
    if not parts:
        return (st.session_state.ticker, st.session_state.function)
    # Forms: "<TICKER> <FUNC>"  |  "<FUNC>"  |  "<TICKER>"
    known = set(FUNCTIONS.keys())
    if len(parts) == 1:
        if parts[0] in known:
            return (st.session_state.ticker, parts[0])
        return (parts[0], "DES")
    # Two or more parts: first is ticker, last is function if recognized
    tk = parts[0]
    fn = parts[-1] if parts[-1] in known else st.session_state.function
    return (tk, fn)


if go_clicked:
    tk, fn = parse_cmd(cmd)
    st.session_state.ticker = tk
    st.session_state.function = fn
    st.rerun()


# --- Route ----------------------------------------------------------------

fn = st.session_state.function
tk = st.session_state.ticker

if fn == "HOME":
    home_view()
elif fn == "DES":
    des_view(tk)
elif fn == "GP":
    gp_view(tk)
elif fn == "FA":
    fa_view(tk)
elif fn == "HRH":
    hrh_view(tk)
elif fn == "BT":
    bt_view(tk)
elif fn == "WATCH":
    watch_view()
else:
    st.error(f"Unknown function: {fn}")
