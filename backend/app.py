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
                                     metrics + trade log + all chart series
                                     (portfolio value, drawdown, price+signals,
                                     RSI where applicable)

Usage:
    python app.py
    (starts a dev server on http://localhost:5001)
"""

import numpy as np
import pandas as pd
from datetime import date
from flask import Flask, jsonify, request
from flask_cors import CORS

from backtest import BacktestEngine, load_prices, compute_sma_signals
from metrics import compute_buyhold_signals, compute_metrics
from rsi_strategy import compute_signals as compute_rsi_signals
from data.ingest import fetch_price_data, clean_price_data, upsert_price_data
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


def compute_volatility(portfolio_df) -> float:
    """
    Annualized volatility (%) of the portfolio's daily returns.

    Same daily-returns series compute_metrics already builds internally
    for the Sharpe ratio (np.std of daily returns), just expressed as an
    annualized percentage on its own rather than folded into Sharpe.
    Kept here instead of touching metrics.py, since that file is already
    validated and this is a pure derived stat, not a change to any
    existing calculation.
    """
    values = portfolio_df["portfolio_value"].values
    daily_returns = np.diff(values) / values[:-1]
    daily_vol = np.std(daily_returns, ddof=1)
    annualized_vol_pct = daily_vol * np.sqrt(252) * 100
    return round(float(annualized_vol_pct), 2)


def build_drawdown_series(portfolio_df) -> list[dict]:
    """
    Running drawdown (%) at every point in the portfolio curve.
    Same math as metrics.compute_metrics's max_drawdown calc, but returns
    the full series instead of just the max, so the frontend can chart it.
    """
    values = portfolio_df["portfolio_value"].values
    running_max = np.maximum.accumulate(values)
    drawdown_pct = (running_max - values) / running_max * 100

    return [
        {"date": row["date"].strftime("%Y-%m-%d"), "drawdown": round(float(dd), 2)}
        for (_, row), dd in zip(portfolio_df.iterrows(), drawdown_pct)
    ]


def build_price_series(df, signal_df) -> list[dict]:
    """
    Close price for every day, with the signal ('BUY' / 'SELL' / 'HOLD')
    that fired on that day so the frontend can mark entry/exit points
    directly on the price line without recomputing anything.
    """
    return [
        {
            "date": row["date"].strftime("%Y-%m-%d"),
            "price": round(float(row["close"]), 2),
            "signal": row["signal"],
        }
        for _, row in signal_df.iterrows()
    ]


def build_rsi_series(rsi_signal_df) -> list[dict]:
    """
    RSI value per day (NaN during the warm-up period, before there's
    enough data for the rolling calculation -- dropped rather than sent
    as null so the frontend doesn't have to special-case it).
    """
    out = []
    for date, row in rsi_signal_df.iterrows():
        if pd.isna(row["rsi"]):
            continue
        out.append({"date": date.strftime("%Y-%m-%d"), "rsi": round(float(row["rsi"]), 2)})
    return out


def safe_json_number(value, fallback=0.0) -> float:
    """
    Guard against non-finite floats (inf, -inf, nan) reaching jsonify.
    Standard JSON has no representation for these -- Flask's jsonify
    will emit the literal token `Infinity`, which is invalid JSON and
    breaks JSON.parse on the Angular side. This happens in practice
    when a strategy produces zero completed trades over a very short
    date range (zero-variance daily returns -> divide-by-zero in the
    Sharpe ratio calc). Rather than patch the validated metrics.py,
    the API layer sanitizes right before serialization.
    """
    if value is None:
        return fallback
    try:
        f = float(value)
    except (TypeError, ValueError):
        return fallback
    return f if np.isfinite(f) else fallback


def run_strategy(ticker: str, strategy: str, start_date: str = None, end_date: str = None) -> dict:
    """
    Run one strategy for one ticker through the unmodified BacktestEngine.
    Returns a JSON-serializable dict: metrics, trade log, and every series
    the frontend needs to render all four charts (portfolio value,
    drawdown, price+signals, RSI).
    """
    df = load_prices(ticker)

    if start_date:
        df = df[df["date"] >= start_date]
    if end_date:
        df = df[df["date"] <= end_date]

    if df.empty:
        raise ValueError(f"No price data for {ticker} in the given date range.")

    df = df.reset_index(drop=True)

    rsi_series = []  # only populated when strategy == "RSI"

    if strategy == "SMA":
        signal_df = compute_sma_signals(df)
    elif strategy == "RSI":
        signal_df_indexed = compute_rsi_signals(df.set_index("date"), period=14,
                                                  oversold=30, overbought=70)
        rsi_series = build_rsi_series(signal_df_indexed)
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
            "total_return": safe_json_number(metrics["total_return"]),
            "cagr": safe_json_number(metrics["cagr"]),
            "sharpe_ratio": safe_json_number(metrics["sharpe_ratio"]),
            "max_drawdown": safe_json_number(metrics["max_drawdown"]),
            "volatility": safe_json_number(compute_volatility(portfolio_df)),
            "final_value": safe_json_number(metrics["final_value"]),
        },
        "completed_trades": len(engine.trades),
        "trade_log": trade_log,
        "portfolio_series": portfolio_series,
        "drawdown_series": build_drawdown_series(portfolio_df),
        "price_series": build_price_series(df, signal_df),
        "rsi_series": rsi_series,
    }


@app.route("/api/tickers", methods=["GET"])
def api_tickers():
    try:
        return jsonify({"tickers": get_available_tickers()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tickers", methods=["POST"])
def api_add_ticker():
    """
    Add a new ticker to price_history by reusing ingest.py's actual
    fetch/clean/upsert pipeline (same functions, same behavior as
    running `python -m data.ingest TICKER START END` from the terminal)
    -- this endpoint is just an HTTP front door onto that existing,
    already-validated logic, not a reimplementation of it.

    Defaults the date range to 2018-01-01 through today if not given,
    matching the range every other ticker in the project was ingested
    with, so a newly added ticker lines up with the rest for Compare
    Strategies and multi-ticker analysis.
    """
    data = request.get_json(force=True)

    ticker = data.get("ticker")
    if not ticker:
        return jsonify({"error": "'ticker' is required."}), 400
    ticker = ticker.strip().upper()

    start_date = data.get("start_date") or "2018-01-01"
    end_date = data.get("end_date") or date.today().isoformat()

    try:
        df = fetch_price_data(ticker, start_date, end_date)
        df = clean_price_data(df)
        upsert_price_data(df, ticker)
    except ValueError as e:
        # fetch_price_data raises ValueError for an empty/invalid ticker
        # -- this is a person-facing input error, not a server fault
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Could not fetch or save data for {ticker}: {e}"}), 500

    return jsonify({
        "ticker": ticker,
        "rows_loaded": len(df),
        "start_date": start_date,
        "end_date": end_date,
        "added": True,
    }), 201


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


@app.route("/api/compare", methods=["POST"])
def api_compare():
    """
    Run all three strategies (SMA, RSI, Buy & Hold) for one ticker over
    the same date range and return them together, so the frontend can
    overlay their portfolio-value curves and rank them side by side.

    No new backtest logic -- three ordinary calls to run_strategy, same
    function /api/backtest already uses. If one strategy fails (e.g. not
    enough data for RSI's warm-up period), that strategy's entry carries
    an "error" field instead of aborting the whole comparison, so the
    other two still come back usable.
    """
    data = request.get_json(force=True)

    ticker = data.get("ticker")
    start_date = data.get("start_date")
    end_date = data.get("end_date")

    if not ticker:
        return jsonify({"error": "'ticker' is required."}), 400

    ticker = ticker.upper()
    results = {}

    for strategy in STRATEGIES:
        try:
            results[strategy] = run_strategy(ticker, strategy, start_date, end_date)
        except ValueError as e:
            results[strategy] = {"error": str(e)}
        except Exception as e:
            results[strategy] = {"error": f"Internal error: {e}"}

    # rank by total_return among strategies that succeeded, worst-first
    # error entries excluded from ranking but still returned so the
    # frontend can show "unavailable" for that strategy rather than
    # silently dropping it
    rankable = [
        (name, r["metrics"]["total_return"])
        for name, r in results.items()
        if "error" not in r
    ]
    rankable.sort(key=lambda x: x[1], reverse=True)
    ranking = [name for name, _ in rankable]

    return jsonify({
        "ticker": ticker,
        "results": results,
        "ranking": ranking,
    })


@app.route("/api/history", methods=["GET"])
def api_history_list():
    """
    All saved runs, newest first. Read-only summary fields only (no
    trade_log or chart series) -- History is a list view, not a
    re-render of the original backtest; if the person wants the full
    result again, that's a fresh /api/backtest call, not a replay.
    """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, ticker, strategy, start_date, end_date,
                   total_return, cagr, sharpe_ratio, max_drawdown,
                   final_value, note, created_at
              FROM backtest_runs
             ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        for row in rows:
            # DATE/TIMESTAMP columns come back as python date/datetime
            # objects from the connector, not JSON-serializable as-is
            row["start_date"] = row["start_date"].strftime("%Y-%m-%d") if row["start_date"] else None
            row["end_date"] = row["end_date"].strftime("%Y-%m-%d") if row["end_date"] else None
            row["created_at"] = row["created_at"].strftime("%Y-%m-%d %H:%M:%S")
            # DECIMAL columns come back as python Decimal, not
            # JSON-serializable by Flask's default encoder
            for key in ("total_return", "cagr", "sharpe_ratio", "max_drawdown", "final_value"):
                row[key] = float(row[key])

        return jsonify({"runs": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/history", methods=["POST"])
def api_history_save():
    """
    Save one already-computed run's summary to history. The person has
    already run a backtest (via /api/backtest or /api/compare) and
    chosen to keep it -- this endpoint does not re-run anything, it
    only persists the metrics the frontend already has in hand.
    """
    data = request.get_json(force=True)

    required = ["ticker", "strategy", "total_return", "cagr", "sharpe_ratio", "max_drawdown", "final_value"]
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing required field(s): {', '.join(missing)}"}), 400

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO backtest_runs
                (ticker, strategy, start_date, end_date,
                 total_return, cagr, sharpe_ratio, max_drawdown, final_value, note)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data["ticker"], data["strategy"],
            data.get("start_date"), data.get("end_date"),
            data["total_return"], data["cagr"], data["sharpe_ratio"],
            data["max_drawdown"], data["final_value"], data.get("note"),
        ))
        new_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"id": new_id, "saved": True}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/history/<int:run_id>", methods=["PATCH"])
def api_history_update_note(run_id):
    """
    Update just the note on an existing saved run. This is the only
    field History lets you edit after saving -- the metrics themselves
    are a historical record of what that run actually produced and
    shouldn't silently change.
    """
    data = request.get_json(force=True)
    if "note" not in data:
        return jsonify({"error": "'note' is required."}), 400

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("UPDATE backtest_runs SET note = %s WHERE id = %s", (data["note"], run_id))
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return jsonify({"error": f"No saved run with id {run_id}."}), 404
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"id": run_id, "updated": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/history/<int:run_id>", methods=["DELETE"])
def api_history_delete(run_id):
    """Remove one saved run from history."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM backtest_runs WHERE id = %s", (run_id,))
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return jsonify({"error": f"No saved run with id {run_id}."}), 404
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"id": run_id, "deleted": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5001)