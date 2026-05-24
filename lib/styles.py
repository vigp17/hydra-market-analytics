"""Styling: injects CSS to give Streamlit a terminal look + reusable header."""
from datetime import datetime

import streamlit as st


CSS = """
<style>
/* Tighten layout */
.block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; max-width: 100% !important; }

/* Monospace everywhere */
html, body, [class*="css"], .stMarkdown, .stText, .stDataFrame {
    font-family: "JetBrains Mono", "Menlo", "Consolas", monospace !important;
}

/* Header bar */
.term-header {
    background: #000;
    border-bottom: 2px solid #FF8800;
    padding: 6px 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 12px;
    color: #E6E6E6;
    margin-bottom: 0.5rem;
}
.term-header .brand { color: #FF8800; font-weight: bold; letter-spacing: 2px; }
.term-header .time  { color: #FFC266; }

/* Tickertape-style mini quotes */
.mini-quote { display: inline-block; padding: 4px 10px; border-right: 1px solid #222; font-size: 12px; }
.mini-quote .tk { color: #FFC266; font-weight: bold; }
.mini-quote .px { color: #E6E6E6; margin: 0 6px; }
.pos { color: #00D26A; }
.neg { color: #FF4040; }

/* Section headers */
.section-head {
    color: #FF8800;
    border-bottom: 1px solid #222;
    padding-bottom: 4px;
    margin: 8px 0 8px 0;
    font-size: 13px;
    letter-spacing: 1px;
}

/* Data tables: darker, tighter */
[data-testid="stDataFrame"] { font-size: 12px; }

/* Sidebar: orange accents */
[data-testid="stSidebar"] { border-right: 1px solid #222; }
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2 { color: #FF8800 !important; }

/* Radio labels as function codes */
[data-testid="stSidebar"] label p { font-family: monospace !important; }

/* Remove Streamlit branding */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
</style>
"""


def apply_theme():
    st.markdown(CSS, unsafe_allow_html=True)


def render_header():
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    html = f"""
    <div class="term-header">
      <div class="brand">☰ HYDRA</div>
      <div class="time">{now}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def section(title: str):
    st.markdown(f'<div class="section-head">{title}</div>', unsafe_allow_html=True)


def colored_pct(pct: float) -> str:
    cls = "pos" if pct >= 0 else "neg"
    sign = "+" if pct >= 0 else ""
    return f'<span class="{cls}">{sign}{pct:.2f}%</span>'
