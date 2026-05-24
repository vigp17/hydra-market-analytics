"""Data providers. Thin wrappers around yfinance with Streamlit caching."""
from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st
import yfinance as yf


# --- Reference data --------------------------------------------------------

INDICES = {
    "S&P 500":    "^GSPC",
    "NASDAQ":     "^IXIC",
    "DOW":        "^DJI",
    "RUSSELL 2K": "^RUT",
    "VIX":        "^VIX",
}

RATES_AND_FX = {
    "US 10Y":  "^TNX",
    "US 2Y":   "^IRX",
    "US 30Y":  "^TYX",
    "DXY":     "DX-Y.NYB",
    "EURUSD":  "EURUSD=X",
    "USDJPY":  "JPY=X",
}

COMMODITIES_AND_CRYPTO = {
    "GOLD":      "GC=F",
    "WTI":       "CL=F",
    "BRENT":     "BZ=F",
    "NAT GAS":   "NG=F",
    "COPPER":    "HG=F",
    "BTC-USD":   "BTC-USD",
    "ETH-USD":   "ETH-USD",
}


# --- Core fetchers ---------------------------------------------------------

@st.cache_data(ttl=60, show_spinner=False)
def get_quote(ticker: str) -> Optional[dict]:
    """Current quote + OHLCV for a ticker. Returns None on failure.

    Uses the last daily bar from history as the source of truth for
    high/low/volume (reliable even when markets are closed) and
    fast_info only for the most recent tick price (if available).
    """
    try:
        t = yf.Ticker(ticker)

        # Last 5 daily bars — robust source for OHLCV
        hist = t.history(period="5d", interval="1d", auto_adjust=False)
        if hist.empty:
            return None

        last_bar = hist.iloc[-1]
        prev_bar = hist.iloc[-2] if len(hist) > 1 else last_bar

        # fast_info gives the most recent tick during market hours.
        # Outside hours this is often stale or None — fall back to last close.
        last = None
        currency = "USD"
        try:
            fi = t.fast_info
            last = fi.get("last_price") or fi.get("lastPrice")
            currency = fi.get("currency") or "USD"
        except Exception:
            pass
        if not last:
            last = float(last_bar["Close"])
        last = float(last)

        prev = float(prev_bar["Close"])
        change = last - prev
        pct = (change / prev * 100.0) if prev else 0.0

        return {
            "ticker":     ticker.upper(),
            "price":      last,
            "change":     change,
            "pct_change": pct,
            "prev_close": prev,
            "currency":   currency,
            "day_high":   float(last_bar["High"]),
            "day_low":    float(last_bar["Low"]),
            "volume":     float(last_bar["Volume"]),
        }
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def get_info(ticker: str) -> dict:
    """Full .info dict (company description, sector, stats). Cached 5 min."""
    try:
        return yf.Ticker(ticker).info or {}
    except Exception:
        return {}


@st.cache_data(ttl=300, show_spinner=False)
def get_history(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """OHLCV history. Cached 5 min."""
    try:
        df = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
        return df if df is not None else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def get_financials(ticker: str) -> dict:
    """Annual and quarterly financial statements. Cached 1 hr."""
    try:
        t = yf.Ticker(ticker)
        return {
            "income_a":   t.financials,
            "balance_a":  t.balance_sheet,
            "cashflow_a": t.cashflow,
            "income_q":   t.quarterly_financials,
            "balance_q":  t.quarterly_balance_sheet,
            "cashflow_q": t.quarterly_cashflow,
        }
    except Exception:
        return {}


@st.cache_data(ttl=60, show_spinner=False)
def get_quotes_batch(tickers: list[str]) -> pd.DataFrame:
    """Quote table for a list of tickers. Robust to partial failures."""
    rows = []
    for tk in tickers:
        q = get_quote(tk)
        if q:
            rows.append(q)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


# --- Helpers ---------------------------------------------------------------

def format_large(n: Optional[float]) -> str:
    """Format large numbers as 1.23B / 45.6M / 789K."""
    if n is None or pd.isna(n):
        return "—"
    n = float(n)
    sign = "-" if n < 0 else ""
    n = abs(n)
    if n >= 1e12: return f"{sign}{n/1e12:.2f}T"
    if n >= 1e9:  return f"{sign}{n/1e9:.2f}B"
    if n >= 1e6:  return f"{sign}{n/1e6:.2f}M"
    if n >= 1e3:  return f"{sign}{n/1e3:.2f}K"
    return f"{sign}{n:.2f}"
