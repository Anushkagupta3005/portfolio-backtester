"""
run_rsi_backtest.py -- Session 5: RSI through the existing BacktestEngine

Proves the engine is genuinely strategy-agnostic: zero changes to
backtest.py, just a different signal DataFrame plugged in.

Usage:
    python run_rsi_backtest.py AAPL
    python run_rsi_backtest.py AAPL --period 14 --oversold 30 --overbought 70
"""

import argparse
import sys

from backtest import BacktestEngine, load_prices, plot_backtest
from rsi_strategy import compute_signals as compute_rsi_signals


def main():
    parser = argparse.ArgumentParser(description="Run RSI strategy through BacktestEngine")
    parser.add_argument("ticker", help="Ticker symbol, e.g. AAPL")
    parser.add_argument("--period", type=int, default=14)
    parser.add_argument("--oversold", type=int, default=30)
    parser.add_argument("--overbought", type=int, default=70)
    args = parser.parse_args()

    ticker = args.ticker.upper()

    print(f"\n  Loading {ticker} from database ...")
    # backtest.py's load_prices() returns date as a column already
    df = load_prices(ticker)
    print(f"  Loaded {len(df)} rows")

    # rsi_strategy.py's compute_signals() expects date as the index
    # (that's how load_price_history() in rsi_strategy.py hands it off),
    # so set/reset the index to match each function's expectation.
    df_indexed = df.set_index("date")
    df_indexed = compute_rsi_signals(df_indexed, args.period, args.oversold, args.overbought)
    df_signals = df_indexed.reset_index()  # back to a date column for BacktestEngine

    buys = (df_signals["signal"] == "BUY").sum()
    sells = (df_signals["signal"] == "SELL").sum()
    print(f"  Signals: {buys} BUY  /  {sells} SELL")

    engine = BacktestEngine(initial_capital=100_000)
    portfolio_df = engine.run(df_signals)

    engine.print_trade_log()
    engine.print_summary()

    plot_backtest(portfolio_df, f"{ticker} (RSI)", engine.trades, engine.initial_capital)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)