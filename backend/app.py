"""
app.py -- Session 7: Flask API

Wraps the existing backend (BacktestEngine, signal generators, metrics)
behind HTTP endpoints. No new backtest logic here -- this file only
translates HTTP requests into calls to code that already exists and is
already validated (backtest.py, rsi_strategy.py, metrics.py).

Endpoints:
    GET  /api/tickers            -> list of tickers available in the DB
    GET  /api/strategies         -> list of supported strategy names
    POST /api/backtest           -> run one strategy for one ticker, return
                                     metrics + trade log + portfolio time series

Usage:
    python app.py
    (starts a dev server on http://localhost:5000)
"""

from flask import Flask, jsonify, request
from flask_cors import CORS

from backtest import BacktestEngine, load_prices, compute_sma_signals
from metrics import compute_buyhold_signals, compute_metrics
from rsi_strategy import compute_signals as compute_rsi_signals
from config import DB_CONFIG

import mysql.connector

app = Flask(__name__)
CORS(app)  # allow the Angular dev server (different port) to call this API

STRATEGIES = ["SMA", "RSI", "Buy & Hold"]


def get_available_tickers() -> list[str]:
    """Distinct tickers currently loaded in price_history."""
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT ticker FROM price_history ORDER BY ticker")
    tickers = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return tickers


def run_strategy(ticker: str, strategy: str, start_date: str = None, end_date: str = None) -> dict:
    """
    Run one strategy for one ticker through the unmodified BacktestEngine.
    Returns a JSON-serializable dict: metrics, trade log, portfolio series.
    """
    df = load_prices(ticker)

    if start_date:
        df = df[df["date"] >= start_date]
    if end_date:
        df = df[df["date"] <= end_date]

    if df.empty:
        raise ValueError(f"No price data for {ticker} in the given date range.")

    df = df.reset_index(drop=True)

    if strategy == "SMA":
        signal_df = compute_sma_signals(df)
    elif strategy == "RSI":
        signal_df_indexed = compute_rsi_signals(df.set_index("date"), period=14,
                                                  oversold=30, overbought=70)
        signal_df = signal_df_indexed.reset_index()
    elif strategy == "Buy & Hold":
        signal_df = compute_buyhold_signals(df)
    else:
        raise ValueError(f"Unknown strategy: {strategy}. Must be one of {STRATEGIES}")

    engine = BacktestEngine(initial_capital=100_000)
    portfolio_df = engine.run(signal_df)
    metrics = compute_metrics(portfolio_df, 100_000)

    trade_log = [
        {
            "entry_date": t["entry_date"].strftime("%Y-%m-%d"),
            "entry_price": t["entry_price"],
            "exit_date": t["exit_date"].strftime("%Y-%m-%d"),
            "exit_price": t["exit_price"],
            "shares": t["shares"],
            "pnl": t["pnl"],
            "pnl_pct": t["pnl_pct"],
        }
        for t in engine.trades
    ]

    portfolio_series = [
        {"date": row["date"].strftime("%Y-%m-%d"), "value": row["portfolio_value"]}
        for _, row in portfolio_df.iterrows()
    ]

    return {
        "ticker": ticker,
        "strategy": strategy,
        "metrics": {
            "total_return": metrics["total_return"],
            "cagr": metrics["cagr"],
            "sharpe_ratio": metrics["sharpe_ratio"],
            "max_drawdown": metrics["max_drawdown"],
            "final_value": metrics["final_value"],
        },
        "completed_trades": len(engine.trades),
        "trade_log": trade_log,
        "portfolio_series": portfolio_series,
    }


@app.route("/api/tickers", methods=["GET"])
def api_tickers():
    try:
        return jsonify({"tickers": get_available_tickers()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/strategies", methods=["GET"])
def api_strategies():
    return jsonify({"strategies": STRATEGIES})


@app.route("/api/backtest", methods=["POST"])
def api_backtest():
    data = request.get_json(force=True)

    ticker = data.get("ticker")
    strategy = data.get("strategy")
    start_date = data.get("start_date")  # optional, "YYYY-MM-DD"
    end_date = data.get("end_date")      # optional, "YYYY-MM-DD"

    if not ticker or not strategy:
        return jsonify({"error": "Both 'ticker' and 'strategy' are required."}), 400

    try:
        result = run_strategy(ticker.upper(), strategy, start_date, end_date)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Internal error: {e}"}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5001)