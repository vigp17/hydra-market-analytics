# HYDRA

> _Cut off one head, two grow back._

A multi-headed market terminal. Bloomberg-style function codes, keyboard-first command bar, amber on black. Every function is another head — price graphs, fundamentals, watchlists, macro, regimes — served from one command surface.

![status](https://img.shields.io/badge/status-v1-orange) ![python](https://img.shields.io/badge/python-3.10%2B-blue) ![streamlit](https://img.shields.io/badge/streamlit-1.32%2B-red)

## Heads

Type a function code in the command bar or click it in the sidebar:

| Code    | Name                   | Description |
|---------|------------------------|-------------|
| `HOME`  | Market Overview        | Global indices, rates, FX, commodities, crypto snapshot |
| `DES`   | Security Description   | Company profile, sector, key statistics |
| `GP`    | Price Graph            | OHLC/candlestick chart with SMAs and Bollinger overlays |
| `FA`    | Fundamentals           | Income statement, balance sheet, cash flow (annual/quarterly) |
| `HRH`   | Historical Regimes     | Gaussian HMM regime detection on log returns — regime shading, per-regime statistics, transition matrix |
| `WATCH` | Watchlist              | Live quote table for tracked tickers |

**Command bar syntax** (Bloomberg convention):

```
AAPL DES      → Apple · Security Description
NVDA GP       → NVIDIA · Price Graph
MSFT FA       → Microsoft · Fundamentals
HOME          → Market overview
WATCH         → Watchlist
```

## Quick start

```bash
git clone <your-repo> hydra
cd hydra
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`.

## Architecture

```
hydra/
├── app.py                  # entry: command bar, routing, state
├── lib/
│   ├── data.py             # yfinance wrappers, caching, reference tickers
│   ├── views.py            # function-code screens (one head per view)
│   └── styles.py           # CSS + header
├── .streamlit/config.toml  # dark terminal theme
└── requirements.txt
```

Design notes:

- **Caching.** Quotes TTL 60s, history TTL 5m, fundamentals TTL 1h — via `@st.cache_data`.
- **Data source.** Free tier only: `yfinance` (delayed ~15m). No API keys required.
- **Resilience.** Every fetch wrapped in try/except so partial data never crashes a head.
- **Aesthetic.** Monospace everywhere, amber (#FF8800) on black, green/red P&L coloring.
- **Extensibility.** Each head is a single function in `lib/views.py`. Add a new function code by adding a function and wiring it into the router in `app.py`.

## Roadmap — more heads

v2 candidates (roughly in priority order):

- [x] `HRH`  — Historical regime analysis (HMM-based) ✓ _shipped_
- [ ] `ECO`  — FRED macro data (Fed funds, CPI, unemployment, GDP, yield curve)
- [ ] `EQS`  — Equity screener (P/E, market cap, sector filters)
- [ ] `N`    — News feed (RSS from WSJ, Reuters, FT)
- [ ] `OMON` — Options chain + IV smile
- [ ] `BT`   — Backtester scaffolding (plug regimes → strategy overlay)
- [ ] Polygon / Alpha Vantage upgrade path for higher-rate data

## Deploy

Push to GitHub, connect to [Streamlit Community Cloud](https://streamlit.io/cloud) — free hosting, auto-deploys on commit.

## Disclaimer

Data is delayed and provided for educational use. Not investment advice. Not for trading.
