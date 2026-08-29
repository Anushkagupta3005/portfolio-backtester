# Basis

A full-stack, strategy-agnostic backtesting engine for evaluating trading strategies against real historical stock data — built to answer one question honestly: does a strategy that looks great actually work, or did it just get lucky on one stock?

## The finding

RSI's backtest on AAPL alone showed a **100% win rate** — every single trade profitable. That looked like a genuinely strong strategy.

It wasn't. Tested across 9 tickers spanning different sectors (tech, banking, energy, consumer staples, healthcare, industrials, media), RSI's average Sharpe ratio collapsed to **0.12**. The 100% win rate on AAPL was a byproduct of AAPL's strong multi-year uptrend — on a trending stock, almost any "buy dips, sell rallies" strategy looks skilled, because the underlying asset is doing the work. RSI actually lost money outright on two of the nine tickers (DIS, NVDA).

Buy & Hold won on 7 of 9 tickers. SMA offered moderate trend-following with real, visible wins and losses. RSI traded return for drawdown protection but didn't beat the other two on a risk-adjusted basis outside of AAPL's specific conditions.

The **Compare Strategies** view in the dashboard makes this checkable live, on any ticker — not just a claim in this README.

## What it does

Pick a ticker, a strategy, and a date range. The engine simulates a $100,000 portfolio trading on that strategy's signals against real historical prices, then reports risk-adjusted performance — not just raw returns.

- **Data layer**: historical daily OHLCV data pulled from Yahoo Finance (`yfinance`) into MySQL. New tickers can be added on demand — from the terminal via `ingest.py`, or directly from the dashboard's "Add Ticker" control, which reuses the same fetch/clean/upsert pipeline
- **Three interchangeable strategies**: SMA Crossover (Golden/Death Cross), RSI (14-day, 30/70 thresholds), and Buy & Hold as a baseline
- **One backtest engine**: a single `BacktestEngine` class simulates trades from any strategy's buy/sell signals without knowing which strategy produced them — long-only, all-in position sizing, no transaction costs modeled (see Limitations)
- **Metrics layer**: Sharpe ratio, CAGR, max drawdown, and volatility computed from first principles, not a library call
- **Flask REST API** wrapping the engine, backed by an **Angular dashboard** with live charts, a run history, and inline notes

## Dashboard

**Run Backtest** — pick a ticker, strategy, and date range and run it live. Returns:
- Seven stat tiles: Total Return, CAGR, Sharpe Ratio, Max Drawdown, Volatility, Final Value, Completed Trades
- Four charts: portfolio value over time, drawdown over time, price with buy/sell signal markers, and the RSI oscillator with 30/70 threshold bands (for RSI runs — non-RSI strategies show a win/loss breakdown instead)
- A trade log with entry/exit prices and P&L per trade, exportable as CSV with a running P&L column
- A tabbed explorer shown before the first run: quick-pick ticker/strategy cards (including an "Add Ticker" control to pull in a new symbol on demand), a plain-language explainer of how each strategy works, and a preview of what the results will look like
- A sticky summary bar (ticker, strategy, return, Sharpe, drawdown, final value) that stays visible while scrolling through results
- One-click "Save to History" once a run completes

**Compare Strategies** — runs all three strategies on one ticker at once, overlays their portfolio-value curves on a single chart, and ranks them by return with side-by-side Sharpe, CAGR, and max drawdown. This is the view that surfaces the RSI finding above on any ticker you choose.

**History** — every saved run, newest first, with an editable note field per run. Useful for flagging a result that looks suspicious — like RSI's initial AAPL numbers — before it's been investigated further.

## Architecture

```
Data Layer (yfinance → MySQL)
        ↓
Strategy Engine (SMA / RSI / Buy & Hold → buy/sell/hold signals)
        ↓
Backtest Engine (strategy-agnostic trade simulation)
        ↓
Metrics Layer (Sharpe, CAGR, max drawdown, volatility)
        ↓
Flask API (backtest, compare, history, ticker ingestion)
        ↓
Angular Dashboard (Run Backtest · Compare Strategies · History)
```

## Stack

- **Backend**: Python, Flask, pandas, yfinance, mysql-connector-python
- **Database**: MySQL
- **Frontend**: Angular, Chart.js

## Running it locally

```bash
# Backend
cd backend
source venv/bin/activate
python app.py          # runs on localhost:5001

# Frontend (separate terminal)
cd portfolio-dashboard
ng serve                # runs on localhost:4200
```

You'll need a local MySQL database named `backtester` with a `price_history` table (populated via `python -m data.ingest TICKER START END`, or through the dashboard's Add Ticker control) and a `backtest_runs` table (see `backend/data/create_backtest_runs.sql`), plus a local `config.py` with your DB credentials (gitignored, not included).

## Limitations

No transaction costs or slippage modeled, price-action signals only (no fundamentals/macro), and single-asset backtests only — no multi-asset portfolio allocation.

## Status

Complete. Built and validated across 8 development sessions:

1. Data layer (Yahoo Finance ingestion into MySQL)
2. Strategy engine (SMA crossover signal generation)
3. Backtest engine (strategy-agnostic trade simulation)
4. Metrics layer (Sharpe ratio, CAGR, max drawdown)
5. RSI strategy + three-way comparison
6. Multi-ticker validation across 9 tickers — the session that surfaced the core finding above
7. Flask API + Angular dashboard
8. Compare Strategies view, run History with notes, CSV export, ticker ingestion from the dashboard, and a full visual redesign

This project was built to demonstrate a specific thing: that a rigorous test can overturn an impressive-looking result, and that the difference matters. Everything else — the dashboard, the charts, the history — exists to make that finding checkable, not to pad the feature list.
