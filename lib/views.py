"""Screens (Bloomberg function codes). Each function renders one view."""
from __future__ import annotations

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from lib.data import (
    COMMODITIES_AND_CRYPTO,
    INDICES,
    RATES_AND_FX,
    format_large,
    get_financials,
    get_history,
    get_info,
    get_quote,
    get_quotes_batch,
)
from lib.regimes import (
    fit_regimes,
    regime_colors,
    regime_labels,
    regime_spans,
)
from lib.backtest import STRATEGIES, run_backtest   
from lib.styles import colored_pct, section


# --- HOME: Market Overview -------------------------------------------------

def home_view():
    section("GLOBAL MARKETS · SNAPSHOT")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        _quote_table("EQUITY INDICES", INDICES)
    with col_b:
        _quote_table("RATES & FX", RATES_AND_FX)
    with col_c:
        _quote_table("COMMODITIES & CRYPTO", COMMODITIES_AND_CRYPTO)

    section("S&P 500 · 1Y")
    df = get_history("^GSPC", period="1y", interval="1d")
    if not df.empty:
        fig = go.Figure(go.Scatter(
            x=df.index, y=df["Close"],
            line=dict(color="#FF8800", width=1.5),
            fill="tozeroy", fillcolor="rgba(255,136,0,0.08)",
        ))
        fig.update_layout(_chart_layout(height=320))
        fig.update_yaxes(title="", tickformat=",.0f")
        st.plotly_chart(fig, use_container_width=True)


def _quote_table(title: str, mapping: dict[str, str]):
    st.markdown(f"**{title}**")
    df = get_quotes_batch(list(mapping.values()))
    if df.empty:
        st.warning("No data.")
        return
    # Map ticker -> friendly label
    reverse = {v: k for k, v in mapping.items()}
    df["Label"] = df["ticker"].map(reverse)
    df["Price"] = df["price"].map(lambda x: f"{x:,.2f}")
    df["Chg%"] = df["pct_change"].map(lambda x: f"{x:+.2f}%")
    out = df[["Label", "Price", "Chg%"]].rename(columns={"Label": ""})

    def color_pct(val):
        if isinstance(val, str) and val.endswith("%"):
            color = "#00D26A" if val.startswith("+") else "#FF4040"
            return f"color: {color}"
        return ""

    styled = out.style.map(color_pct, subset=["Chg%"])
    st.dataframe(styled, hide_index=True, use_container_width=True)


# --- DES: Security Description ---------------------------------------------

def des_view(ticker: str):
    if not ticker:
        st.info("Enter a ticker in the command bar above (e.g. AAPL).")
        return

    info = get_info(ticker)
    quote = get_quote(ticker)
    if not info and not quote:
        st.error(f"No data found for {ticker}.")
        return

    name = info.get("longName") or info.get("shortName") or ticker.upper()
    section(f"{ticker.upper()} · {name}")

    # Top-line quote block
    if quote:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("PRICE", f"{quote['price']:,.2f} {quote['currency']}",
                  f"{quote['change']:+.2f} ({quote['pct_change']:+.2f}%)")
        c2.metric("PREV CLOSE", f"{quote['prev_close']:,.2f}")
        c3.metric("DAY HIGH", f"{(quote.get('day_high') or 0):,.2f}")
        c4.metric("DAY LOW",  f"{(quote.get('day_low') or 0):,.2f}")
        c5.metric("VOLUME",   format_large(quote.get("volume")))

    section("PROFILE")
    profile_cols = st.columns(4)
    profile_cols[0].markdown(f"**Sector**\n\n{info.get('sector', '—')}")
    profile_cols[1].markdown(f"**Industry**\n\n{info.get('industry', '—')}")
    profile_cols[2].markdown(f"**Country**\n\n{info.get('country', '—')}")
    profile_cols[3].markdown(f"**Employees**\n\n{format_large(info.get('fullTimeEmployees'))}")

    if info.get("longBusinessSummary"):
        st.markdown(f"_{info['longBusinessSummary']}_")

    section("KEY STATISTICS")
    stats = {
        "Market Cap":    format_large(info.get("marketCap")),
        "Enterprise Val": format_large(info.get("enterpriseValue")),
        "P/E (TTM)":     _fmt(info.get("trailingPE")),
        "Fwd P/E":       _fmt(info.get("forwardPE")),
        "EPS (TTM)":     _fmt(info.get("trailingEps")),
        "Div Yield":     _fmt_pct(info.get("dividendYield")),
        "Beta":          _fmt(info.get("beta")),
        "52W High":      _fmt(info.get("fiftyTwoWeekHigh")),
        "52W Low":       _fmt(info.get("fiftyTwoWeekLow")),
        "Shares Out":    format_large(info.get("sharesOutstanding")),
        "Float":         format_large(info.get("floatShares")),
        "Short % Float": _fmt_pct(info.get("shortPercentOfFloat")),
    }
    stat_cols = st.columns(6)
    for i, (k, v) in enumerate(stats.items()):
        stat_cols[i % 6].markdown(f"**{k}**\n\n`{v}`")


# --- GP: Price Chart -------------------------------------------------------

def gp_view(ticker: str):
    if not ticker:
        st.info("Enter a ticker in the command bar above.")
        return

    c1, c2, c3 = st.columns([2, 2, 6])
    period = c1.selectbox("Period", ["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"], index=3)
    chart_type = c2.selectbox("Type", ["Candlestick", "Line", "OHLC"], index=0)
    overlays = c3.multiselect("Overlays", ["SMA 20", "SMA 50", "SMA 200", "Bollinger (20,2)"],
                              default=["SMA 50", "SMA 200"])

    df = get_history(ticker, period=period, interval="1d")
    if df.empty:
        st.error(f"No history for {ticker}.")
        return

    section(f"{ticker.upper()} · PRICE · {period.upper()}")

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.03, row_heights=[0.75, 0.25],
                        subplot_titles=("", ""))

    if chart_type == "Candlestick":
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
            increasing_line_color="#00D26A", decreasing_line_color="#FF4040",
            name="Price",
        ), row=1, col=1)
    elif chart_type == "OHLC":
        fig.add_trace(go.Ohlc(
            x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
            increasing_line_color="#00D26A", decreasing_line_color="#FF4040",
            name="Price",
        ), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["Close"], line=dict(color="#FF8800", width=1.8), name="Close",
        ), row=1, col=1)

    # Overlays
    for w in (20, 50, 200):
        if f"SMA {w}" in overlays:
            sma = df["Close"].rolling(w).mean()
            fig.add_trace(go.Scatter(x=df.index, y=sma,
                                     line=dict(width=1), name=f"SMA{w}"), row=1, col=1)
    if "Bollinger (20,2)" in overlays:
        m = df["Close"].rolling(20).mean()
        s = df["Close"].rolling(20).std()
        fig.add_trace(go.Scatter(x=df.index, y=m + 2 * s, line=dict(color="#888", width=1),
                                 name="BB upper"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=m - 2 * s, line=dict(color="#888", width=1),
                                 fill="tonexty", fillcolor="rgba(136,136,136,0.08)",
                                 name="BB lower"), row=1, col=1)

    # Volume
    colors = ["#00D26A" if c >= o else "#FF4040" for o, c in zip(df["Open"], df["Close"])]
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], marker_color=colors,
                         name="Volume", showlegend=False), row=2, col=1)

    fig.update_layout(_chart_layout(height=620, legend=True))
    fig.update_xaxes(rangeslider_visible=False, row=1, col=1)
    st.plotly_chart(fig, use_container_width=True)


# --- FA: Fundamentals ------------------------------------------------------

def fa_view(ticker: str):
    if not ticker:
        st.info("Enter a ticker in the command bar above.")
        return

    fin = get_financials(ticker)
    if not fin or all(isinstance(v, pd.DataFrame) and v.empty for v in fin.values()):
        st.error(f"No financials for {ticker}.")
        return

    c1, c2 = st.columns([1, 9])
    freq = c1.radio("Freq", ["Annual", "Quarterly"], horizontal=False, label_visibility="collapsed")
    suf = "_a" if freq == "Annual" else "_q"

    section(f"{ticker.upper()} · INCOME STATEMENT ({freq.upper()})")
    _render_statement(fin.get(f"income{suf}"))

    section(f"{ticker.upper()} · BALANCE SHEET ({freq.upper()})")
    _render_statement(fin.get(f"balance{suf}"))

    section(f"{ticker.upper()} · CASH FLOW ({freq.upper()})")
    _render_statement(fin.get(f"cashflow{suf}"))


def _render_statement(df: pd.DataFrame | None):
    if df is None or df.empty:
        st.info("No data.")
        return
    # Format as large numbers, newest periods first (yfinance returns cols sorted)
    fmt = df.copy()
    fmt.columns = [c.strftime("%Y-%m-%d") if hasattr(c, "strftime") else str(c) for c in fmt.columns]
    fmt = fmt.map(lambda x: format_large(x) if pd.notna(x) else "—")
    st.dataframe(fmt, use_container_width=True)


# --- WATCH: Watchlist ------------------------------------------------------

DEFAULT_WATCH = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "SPY", "QQQ"]


def watch_view():
    if "watchlist" not in st.session_state:
        st.session_state.watchlist = DEFAULT_WATCH.copy()

    section("WATCHLIST")
    c1, c2, c3 = st.columns([3, 1, 6])
    new = c1.text_input("Add ticker", placeholder="e.g. AMD", label_visibility="collapsed")
    if c2.button("Add", use_container_width=True) and new:
        tk = new.upper().strip()
        if tk not in st.session_state.watchlist:
            st.session_state.watchlist.append(tk)
            st.rerun()

    if not st.session_state.watchlist:
        st.info("Watchlist empty. Add tickers above.")
        return

    df = get_quotes_batch(st.session_state.watchlist)
    if df.empty:
        st.warning("No data available.")
        return

    df = df[["ticker", "price", "change", "pct_change", "day_high", "day_low", "volume"]]
    df["price"]      = df["price"].map(lambda x: f"{x:,.2f}")
    df["change"]     = df["change"].map(lambda x: f"{x:+.2f}")
    df["pct_change"] = df["pct_change"].map(lambda x: f"{x:+.2f}%")
    df["day_high"]   = df["day_high"].map(lambda x: f"{x:,.2f}" if pd.notna(x) else "—")
    df["day_low"]    = df["day_low"].map(lambda x: f"{x:,.2f}" if pd.notna(x) else "—")
    df["volume"]     = df["volume"].map(format_large)
    df.columns = ["Ticker", "Last", "Chg", "Chg%", "High", "Low", "Volume"]

    def color_neg_pos(val):
        if isinstance(val, str) and (val.startswith("+") or val.startswith("-")):
            return "color: #00D26A" if val.startswith("+") else "color: #FF4040"
        return ""

    styled = df.style.map(color_neg_pos, subset=["Chg", "Chg%"])
    st.dataframe(styled, hide_index=True, use_container_width=True)

    # Remove
    c1, c2 = st.columns([3, 7])
    rem = c1.selectbox("Remove ticker", [""] + st.session_state.watchlist,
                       label_visibility="collapsed")
    if c2.button("Remove") and rem:
        st.session_state.watchlist.remove(rem)
        st.rerun()

# --- HRH: Historical Regimes (HMM) ----------------------------------------

def hrh_view(ticker: str):
    """Gaussian HMM regime detection on log returns."""
    if not ticker:
        ticker = "^GSPC"

    c1, c2, c3, c4 = st.columns([2, 2, 2, 4])
    period = c1.selectbox("Lookback", ["2y", "5y", "10y", "max"], index=1,
                          key="hrh_period")
    n_states = int(c2.selectbox("Regimes", [2, 3, 4], index=1, key="hrh_n"))
    show_tm = c3.checkbox("Transition matrix", value=True, key="hrh_tm")

    section(f"{ticker.upper()} · HMM REGIMES · {n_states} STATES · {period.upper()}")

    with st.spinner("Fitting Gaussian HMM..."):
        res = fit_regimes(ticker, period=period, n_states=n_states)

    if res is None:
        st.error(
            f"Could not fit regimes on {ticker}. Need ≥100 observations; "
            "try a longer lookback or a more liquid ticker."
        )
        return

    labels = regime_labels(n_states)
    colors = regime_colors(n_states)

    # --- Current regime banner -------------------------------------------
    current = int(res["states"][-1])
    current_date = res["dates"][-1].strftime("%Y-%m-%d")
    ann_ret_cur = res["means"][current] * 252
    ann_vol_cur = res["vols"][current] * np.sqrt(252)
    self_trans = res["trans"][current, current]
    exp_dur = 1.0 / (1.0 - self_trans) if self_trans < 0.9999 else float("inf")

    banner = f"""
    <div style="background:{colors[current]}22;border-left:4px solid {colors[current]};
                padding:10px 16px;margin:6px 0 12px 0;">
      <div style="color:{colors[current]};font-size:11px;letter-spacing:2px;">
        CURRENT REGIME · {current_date}
      </div>
      <div style="color:#E6E6E6;font-size:22px;font-weight:bold;margin-top:2px;">
        {labels[current]}
      </div>
      <div style="color:#AAA;font-size:12px;margin-top:4px;">
        Ann. return {ann_ret_cur:+.1f}% · Ann. vol {ann_vol_cur:.1f}% ·
        Expected duration {exp_dur:.1f} days
      </div>
    </div>
    """
    st.markdown(banner, unsafe_allow_html=True)
    if not res["converged"]:
        st.warning("HMM did not fully converge — try a longer lookback.")

    # --- Price chart with regime shading ---------------------------------
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=res["dates"], y=res["prices"],
        line=dict(color="#FF8800", width=1.5),
        name="Price",
        hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.2f}<extra></extra>",
    ))
    for start, end, st_idx in regime_spans(res["states"], res["dates"]):
        fig.add_vrect(
            x0=start, x1=end,
            fillcolor=colors[st_idx], opacity=0.18, line_width=0,
            layer="below",
        )
    fig.update_layout(_chart_layout(height=420, legend=False))
    fig.update_yaxes(title="Price")
    for i, lbl in enumerate(labels):
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(size=10, color=colors[i], symbol="square"),
            name=lbl, showlegend=True,
        ))
    fig.update_layout(showlegend=True,
                      legend=dict(orientation="h", y=-0.15, x=0,
                                  bgcolor="rgba(0,0,0,0)"))
    st.plotly_chart(fig, use_container_width=True)

    # --- Regime statistics ----------------------------------------------
    section("REGIME STATISTICS")
    stats_rows = []
    for i in range(n_states):
        mask = res["states"] == i
        freq = float(mask.mean())
        mu = float(res["means"][i])
        sigma = float(res["vols"][i])
        ann_ret = mu * 252
        ann_vol = sigma * np.sqrt(252)
        sharpe = ann_ret / ann_vol if ann_vol > 0 else 0.0
        self_p = float(res["trans"][i, i])
        dur = 1.0 / (1.0 - self_p) if self_p < 0.9999 else float("inf")
        stats_rows.append({
            "Regime":      labels[i],
            "Frequency":   f"{freq*100:.1f}%",
            "μ daily":     f"{mu:+.3f}%",
            "σ daily":     f"{sigma:.3f}%",
            "Ann. Return": f"{ann_ret:+.1f}%",
            "Ann. Vol":    f"{ann_vol:.1f}%",
            "Sharpe":      f"{sharpe:+.2f}",
            "Persistence": f"{self_p:.3f}",
            "Exp. Duration (d)": f"{dur:.1f}" if dur != float("inf") else "—",
        })
    stats_df = pd.DataFrame(stats_rows)

    def color_regime(val):
        try:
            idx = labels.index(val)
            return f"background-color: {colors[idx]}33; color: {colors[idx]}"
        except ValueError:
            return ""

    styled = stats_df.style.map(color_regime, subset=["Regime"])
    st.dataframe(styled, hide_index=True, use_container_width=True)

    # --- Transition matrix ----------------------------------------------
    if show_tm:
        section("TRANSITION MATRIX")
        tm = res["trans"]
        heat = go.Figure(go.Heatmap(
            z=tm,
            x=labels, y=labels,
            text=[[f"{v:.3f}" for v in row] for row in tm],
            texttemplate="%{text}",
            colorscale=[[0, "#000000"], [0.5, "#4A2500"], [1, "#FF8800"]],
            zmin=0, zmax=1,
            showscale=False,
        ))
        heat.update_layout(
            _chart_layout(height=320),
            xaxis_title="To", yaxis_title="From",
        )
        heat.update_yaxes(autorange="reversed")
        st.plotly_chart(heat, use_container_width=True)

# --- BT: Backtester -------------------------------------------------------

def bt_view(ticker: str):
    """Vectorized backtest of regime strategies vs buy-and-hold."""
    if not ticker:
        ticker = "^GSPC"

    c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 3])
    strat_label = c1.selectbox(
        "Strategy",
        list(STRATEGIES.values()),
        index=2,  # default: Regime Long Non-Bearish
        key="bt_strat",
    )
    strat_key = next(k for k, v in STRATEGIES.items() if v == strat_label)
    period = c2.selectbox("Period", ["5y", "10y", "max"], index=1, key="bt_period")
    walk_fwd = c3.checkbox("Walk-forward", value=False, key="bt_wf",
                           help="Expanding-window HMM refit, no look-ahead bias. Slower.")
    cost_bps = float(c4.number_input("Cost (bps)", value=5.0, min_value=0.0,
                                     step=1.0, key="bt_cost"))
    n_states = int(c5.selectbox("Regimes", [2, 3, 4], index=1, key="bt_n"))

    section(f"{ticker.upper()} · BACKTEST · {strat_label.upper()} · {period.upper()}")

    # Honesty banner
    if strat_key == "buy_hold":
        pass
    elif walk_fwd:
        st.info(
            "**Walk-forward mode.** HMM refits every ~quarter on an expanding window "
            "using only past data. No look-ahead bias. Slower — initial fit takes a moment."
        )
    else:
        st.warning(
            "⚠ **In-sample mode.** HMM is fit on the full history, so regime labels "
            "use future information. For illustration only — not an honest backtest. "
            "Toggle **Walk-forward** for rigorous results."
        )

    spinner_msg = "Running walk-forward backtest..." if walk_fwd else "Running backtest..."
    with st.spinner(spinner_msg):
        res = run_backtest(
            ticker, period=period, strategy=strat_key, n_states=n_states,
            walk_forward=walk_fwd, cost_bps=cost_bps,
        )

    if res is None:
        st.error(f"Could not backtest {ticker}. Try a different ticker or longer period.")
        return

    m_s = res["strat_metrics"]
    m_b = res["bh_metrics"]

    # --- Equity curve ----------------------------------------------------
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=res["dates"], y=res["strat_equity"],
        line=dict(color="#FF8800", width=2),
        name="Strategy",
        hovertemplate="%{x|%Y-%m-%d}<br>%{y:.3f}x<extra>Strategy</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=res["dates"], y=res["bh_equity"],
        line=dict(color="#888888", width=1.5, dash="dot"),
        name="Buy & Hold",
        hovertemplate="%{x|%Y-%m-%d}<br>%{y:.3f}x<extra>B&H</extra>",
    ))
    fig.update_layout(_chart_layout(height=380, legend=True))
    fig.update_yaxes(title="Equity (log scale)", type="log")
    fig.update_layout(legend=dict(orientation="h", y=-0.15, x=0,
                                   bgcolor="rgba(0,0,0,0)"))
    st.plotly_chart(fig, use_container_width=True)

    # --- Headline metrics row --------------------------------------------
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("CAGR",         f"{m_s['cagr']*100:+.2f}%",
              f"{(m_s['cagr']-m_b['cagr'])*100:+.2f} vs B&H")
    c2.metric("Sharpe",       f"{m_s['sharpe']:+.2f}",
              f"{m_s['sharpe']-m_b['sharpe']:+.2f} vs B&H")
    c3.metric("Max Drawdown", f"{m_s['max_dd']*100:.1f}%",
              f"{(m_s['max_dd']-m_b['max_dd'])*100:+.1f} vs B&H",
              delta_color="inverse")
    c4.metric("Calmar",       f"{m_s['calmar']:+.2f}",
              f"{m_s['calmar']-m_b['calmar']:+.2f} vs B&H")

    # --- Full metrics table ----------------------------------------------
    section("PERFORMANCE · FULL METRICS")
    rows = [
        ("Total Return",     f"{m_s['total_return']*100:+.1f}%",  f"{m_b['total_return']*100:+.1f}%"),
        ("CAGR",             f"{m_s['cagr']*100:+.2f}%",          f"{m_b['cagr']*100:+.2f}%"),
        ("Annualized Vol",   f"{m_s['vol']*100:.2f}%",            f"{m_b['vol']*100:.2f}%"),
        ("Sharpe",           f"{m_s['sharpe']:+.2f}",             f"{m_b['sharpe']:+.2f}"),
        ("Sortino",          f"{m_s['sortino']:+.2f}",            f"{m_b['sortino']:+.2f}"),
        ("Max Drawdown",     f"{m_s['max_dd']*100:.1f}%",         f"{m_b['max_dd']*100:.1f}%"),
        ("Calmar",           f"{m_s['calmar']:+.2f}",             f"{m_b['calmar']:+.2f}"),
        ("Win Rate (daily)", f"{m_s['win_rate']*100:.1f}%",       f"{m_b['win_rate']*100:.1f}%"),
    ]
    perf = pd.DataFrame(rows, columns=["Metric", "Strategy", "Buy & Hold"])
    st.dataframe(perf, hide_index=True, use_container_width=True)

    # --- Trade / exposure stats ------------------------------------------
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Trades", f"{res['n_trades']:,}")
    c2.metric("Transaction Cost Drag", f"{res['total_cost_pct']:.2f}%")
    avg_exposure = float(np.mean(np.abs(res["position"]))) * 100
    c3.metric("Avg. Exposure", f"{avg_exposure:.1f}%")

    # --- Drawdown (underwater) -------------------------------------------
    section("DRAWDOWN · UNDERWATER")
    peak_s = np.maximum.accumulate(res["strat_equity"])
    dd_s = (res["strat_equity"] - peak_s) / peak_s * 100
    peak_b = np.maximum.accumulate(res["bh_equity"])
    dd_b = (res["bh_equity"] - peak_b) / peak_b * 100

    fig_dd = go.Figure()
    fig_dd.add_trace(go.Scatter(
        x=res["dates"], y=dd_s,
        line=dict(color="#FF8800", width=1.5),
        fill="tozeroy", fillcolor="rgba(255,136,0,0.15)",
        name="Strategy",
    ))
    fig_dd.add_trace(go.Scatter(
        x=res["dates"], y=dd_b,
        line=dict(color="#888", width=1, dash="dot"),
        name="Buy & Hold",
    ))
    fig_dd.update_layout(_chart_layout(height=240, legend=True))
    fig_dd.update_yaxes(title="Drawdown (%)")
    fig_dd.update_layout(legend=dict(orientation="h", y=-0.25, x=0,
                                      bgcolor="rgba(0,0,0,0)"))
    st.plotly_chart(fig_dd, use_container_width=True)


# --- Helpers ---------------------------------------------------------------

def _chart_layout(height=500, legend=False):
    return dict(
        height=height,
        margin=dict(l=0, r=0, t=10, b=10),
        paper_bgcolor="#000",
        plot_bgcolor="#000",
        font=dict(family="monospace", color="#E6E6E6", size=11),
        xaxis=dict(gridcolor="#1a1a1a", zerolinecolor="#1a1a1a"),
        yaxis=dict(gridcolor="#1a1a1a", zerolinecolor="#1a1a1a"),
        showlegend=legend,
        legend=dict(bgcolor="rgba(0,0,0,0.6)", bordercolor="#222", borderwidth=1),
        hovermode="x unified",
    )


def _fmt(x, nd=2):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "—"
    try:
        return f"{float(x):,.{nd}f}"
    except Exception:
        return "—"


def _fmt_pct(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "—"
    try:
        v = float(x)
        # yfinance sometimes returns already-in-pct (0.0123 = 1.23%)
        if abs(v) < 1:
            v *= 100
        return f"{v:.2f}%"
    except Exception:
        return "—"
