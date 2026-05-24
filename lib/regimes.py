"""Regime detection via Gaussian HMM on log returns.

Fits a Hidden Markov Model to asset returns and reorders states by ascending
mean return so state 0 = most bearish, state N-1 = most bullish. Deterministic
via fixed random_state. Cached so re-fitting is cheap on repeated views.
"""
from __future__ import annotations

import warnings
from typing import Optional

import numpy as np
import pandas as pd
import streamlit as st

from lib.data import get_history

# hmmlearn emits sklearn FutureWarnings; suppress for a clean UI.
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)


REGIME_LABELS = {
    2: ["Risk-Off", "Risk-On"],
    3: ["Bearish", "Neutral", "Bullish"],
    4: ["Crisis", "Bearish", "Neutral", "Bullish"],
}

REGIME_COLORS = {
    2: ["#FF4040", "#00D26A"],
    3: ["#FF4040", "#888888", "#00D26A"],
    4: ["#8B0000", "#FF4040", "#888888", "#00D26A"],
}


@st.cache_data(ttl=3600, show_spinner=False)
def fit_regimes(
    ticker: str,
    period: str = "5y",
    n_states: int = 3,
    seed: int = 42,
) -> Optional[dict]:
    """Fit Gaussian HMM on log returns. Returns None on failure.

    Returns dict with:
        dates:   DatetimeIndex aligned with returns/states
        prices:  np.array of close prices
        returns: np.array of log returns in percent
        states:  np.array of state labels (reordered: 0=bearish ... N-1=bullish)
        means:   per-state mean daily return (%)
        vols:    per-state daily std (%)
        trans:   reordered transition matrix (N x N)
        n_states: int
        converged: bool
    """
    from hmmlearn.hmm import GaussianHMM

    df = get_history(ticker, period=period, interval="1d")
    if df.empty or len(df) < 100:
        return None

    # Log returns, scaled to percent (helps HMM numerical stability)
    close = df["Close"].dropna()
    log_ret = np.log(close).diff().dropna() * 100.0
    if len(log_ret) < 100:
        return None

    X = log_ret.values.reshape(-1, 1)

    model = GaussianHMM(
        n_components=n_states,
        covariance_type="full",
        n_iter=500,
        tol=1e-4,
        random_state=seed,
    )
    try:
        model.fit(X)
        raw_states = model.predict(X)
    except Exception:
        return None

    # Reorder by ascending mean return: state 0 = worst, N-1 = best
    means = model.means_.flatten()
    order = np.argsort(means)
    remap = {int(old): int(new) for new, old in enumerate(order)}
    states = np.array([remap[int(s)] for s in raw_states])

    means_sorted = means[order]
    covars_sorted = np.array([model.covars_[i][0, 0] for i in order])
    vols_sorted = np.sqrt(covars_sorted)
    trans_sorted = model.transmat_[np.ix_(order, order)]

    return {
        "dates":     log_ret.index,
        "prices":    close.loc[log_ret.index].values,
        "returns":   log_ret.values,
        "states":    states,
        "means":     means_sorted,
        "vols":      vols_sorted,
        "trans":     trans_sorted,
        "n_states":  n_states,
        "converged": bool(model.monitor_.converged),
    }


def regime_labels(n_states: int) -> list[str]:
    return REGIME_LABELS.get(n_states, [f"State {i}" for i in range(n_states)])


def regime_colors(n_states: int) -> list[str]:
    return REGIME_COLORS.get(n_states, ["#888888"] * n_states)


def regime_spans(states: np.ndarray, dates: pd.Index) -> list[tuple]:
    """Compress consecutive same-state indices into (start_date, end_date, state) spans."""
    if len(states) == 0:
        return []
    spans = []
    cur = int(states[0])
    start = 0
    for i in range(1, len(states)):
        if int(states[i]) != cur:
            spans.append((dates[start], dates[i - 1], cur))
            start = i
            cur = int(states[i])
    spans.append((dates[start], dates[len(states) - 1], cur))
    return spans