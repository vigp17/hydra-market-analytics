"""Vectorized backtester for regime-based strategies.

Supports:
  - Buy & hold (baseline)
  - Regime long-only (long top state, flat otherwise)
  - Regime long non-bearish (long unless bottom state)
  - Regime long/short (long top, short bottom, flat middle)

Two fitting modes for regime strategies:
  - In-sample  : fast but look-ahead biased (for illustration only)
  - Walk-forward: honest — HMM refits with expanding window, no future info

All signals are shifted by 1 day so positions at day t use the signal as of
end-of-day t-1. Transaction costs applied on position changes.
"""
from __future__ import annotations

import warnings
from typing import Optional

import numpy as np
import pandas as pd
import streamlit as st

from lib.data import get_history
from lib.regimes import fit_regimes

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)


STRATEGIES = {
    "buy_hold":           "Buy & Hold",
    "regime_long":        "Regime: Long Top Only",
    "regime_long_nonbear":"Regime: Long Non-Bearish",
    "regime_long_short":  "Regime: Long/Short",
}


@st.cache_data(ttl=3600, show_spinner=False)
def run_backtest(
    ticker: str,
    period: str = "10y",
    strategy: str = "regime_long_nonbear",
    n_states: int = 3,
    walk_forward: bool = False,
    train_window: int = 756,   # 3y initial fit
    refit_every: int = 63,     # quarterly
    cost_bps: float = 5.0,
    seed: int = 42,
) -> Optional[dict]:
    """Run backtest. Returns None on failure."""
    df = get_history(ticker, period=period, interval="1d")
    if df.empty or len(df) < 300:
        return None

    close = df["Close"].dropna()
    if len(close) < 300:
        return None

    # Daily log returns; first value forced to 0
    log_ret = np.log(close).diff().fillna(0.0).values
    dates = close.index
    n = len(close)

    # --- Signal generation ------------------------------------------------
    if strategy == "buy_hold":
        signal = np.ones(n)
    else:
        # log_ret_pct: scaled for HMM numerical stability, shape (n,)
        log_ret_pct = log_ret * 100.0

        if walk_forward:
            states = _walk_forward_states(
                log_ret_pct, n_states, train_window, refit_every, seed,
            )
            valid_from = train_window
        else:
            res = fit_regimes(ticker, period=period, n_states=n_states, seed=seed)
            if res is None:
                return None
            # res["states"] is length n-1 (first NaN return dropped). Pad with 0.
            states = np.zeros(n, dtype=int)
            states[1:] = res["states"]
            valid_from = 1

        if strategy == "regime_long":
            signal = (states == n_states - 1).astype(float)
        elif strategy == "regime_long_nonbear":
            signal = (states > 0).astype(float)
        elif strategy == "regime_long_short":
            signal = np.where(states == n_states - 1, 1.0,
                    np.where(states == 0, -1.0, 0.0))
        else:
            signal = np.ones(n)

        # Before valid_from, no regime info → flat
        signal[:valid_from] = 0.0

    # --- Position: shift signal by 1 day (no look-ahead) ------------------
    position = np.zeros(n)
    position[1:] = signal[:-1]

    # --- Transaction costs on position changes ----------------------------
    pos_change = np.abs(np.diff(position, prepend=0.0))
    costs = pos_change * (cost_bps / 10_000.0)

    # --- Portfolio returns ------------------------------------------------
    strat_ret = position * log_ret - costs
    bh_ret = log_ret.copy()

    strat_equity = np.exp(np.cumsum(strat_ret))
    bh_equity = np.exp(np.cumsum(bh_ret))

    return {
        "dates":         dates,
        "position":      position,
        "strat_ret":     strat_ret,
        "bh_ret":        bh_ret,
        "strat_equity":  strat_equity,
        "bh_equity":     bh_equity,
        "strat_metrics": _metrics(strat_ret),
        "bh_metrics":    _metrics(bh_ret),
        "n_trades":      int((pos_change > 1e-9).sum()),
        "total_cost_pct": float(costs.sum() * 100.0),
        "walk_forward":  walk_forward,
        "strategy":      strategy,
        "n_states":      n_states,
        "valid_from_date": dates[valid_from] if strategy != "buy_hold" else dates[0],
    }


def _walk_forward_states(
    log_ret_pct: np.ndarray,
    n_states: int,
    train_window: int,
    refit_every: int,
    seed: int,
) -> np.ndarray:
    """Expanding-window HMM refit. Returns states aligned with input.

    At each step t >= train_window:
      - If a refit is due, fit HMM on log_ret_pct[:t+1] (all data through t)
      - Predict state at t via Viterbi on the same window
      - State labels always reordered so 0 = most bearish mean
    """
    from hmmlearn.hmm import GaussianHMM

    n = len(log_ret_pct)
    states = np.zeros(n, dtype=int)
    model = None
    remap: dict = {}

    for t in range(train_window, n):
        # Refit on the expanding window
        if (t - train_window) % refit_every == 0:
            try:
                X_train = log_ret_pct[: t + 1].reshape(-1, 1)
                mdl = GaussianHMM(
                    n_components=n_states,
                    covariance_type="full",
                    n_iter=200,
                    tol=1e-3,
                    random_state=seed,
                )
                mdl.fit(X_train)
                means = mdl.means_.flatten()
                order = np.argsort(means)
                remap = {int(old): int(new) for new, old in enumerate(order)}
                model = mdl
            except Exception:
                pass

        # Predict state at t
        if model is not None and remap:
            try:
                X_pred = log_ret_pct[: t + 1].reshape(-1, 1)
                raw_last = int(model.predict(X_pred)[-1])
                states[t] = remap.get(raw_last, 0)
            except Exception:
                states[t] = 0

    return states


def _metrics(daily_log_ret: np.ndarray) -> dict:
    """Standard performance metrics from daily log returns."""
    if len(daily_log_ret) == 0:
        return {}

    simple = np.expm1(daily_log_ret)
    equity = np.exp(np.cumsum(daily_log_ret))

    years = len(daily_log_ret) / 252.0
    total_return = equity[-1] - 1.0
    cagr = equity[-1] ** (1.0 / years) - 1.0 if years > 0 else 0.0

    vol = simple.std(ddof=1) * np.sqrt(252) if len(simple) > 1 else 0.0
    mean_ann = simple.mean() * 252
    sharpe = mean_ann / vol if vol > 0 else 0.0

    downside = simple[simple < 0]
    down_vol = downside.std(ddof=1) * np.sqrt(252) if len(downside) > 1 else 0.0
    sortino = mean_ann / down_vol if down_vol > 0 else 0.0

    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    max_dd = float(dd.min()) if len(dd) > 0 else 0.0

    calmar = cagr / abs(max_dd) if max_dd < 0 else 0.0
    win_rate = float((simple > 0).sum() / len(simple)) if len(simple) > 0 else 0.0

    return {
        "total_return": total_return,
        "cagr":         cagr,
        "vol":          vol,
        "sharpe":       sharpe,
        "sortino":      sortino,
        "max_dd":       max_dd,
        "calmar":       calmar,
        "win_rate":     win_rate,
    }