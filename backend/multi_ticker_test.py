"""
Session 6: Multi-Ticker Testing
=================================
Runs SMA / RSI / Buy-and-Hold across a list of tickers spanning different
sectors, to check whether any strategy's edge (or lack of one) holds up
outside a single-stock, single-regime test.

No engine or strategy code is touched -- this just loops the same
per-ticker logic from metrics_three_way.py and aggregates the results.

Usage:
    python multi_ticker_test.py
    python multi_ticker_test.py --tickers AAPL MSFT JPM
"""

import argparse
import sys

import pandas as pd

from backtest import BacktestEngine, load_prices, compute_sma_signals
from metrics import compute_buyhold_signals, compute_metrics
from rsi_strategy import compute_signals as compute_rsi_signals

DEFAULT_TICKERS = ["AAPL", "MSFT", "JPM", "XOM", "KO", "PFE", "CAT", "DIS", "NVDA"]


def run_all_strategies(ticker: str) -> dict:
    """
    Run SMA, RSI, and Buy-and-Hold for one ticker through the unmodified
    BacktestEngine, and return each strategy's compute_metrics() dict.
    """
    df = load_prices(ticker)

    # SMA
    sma_df = compute_sma_signals(df)
    sma_engine = BacktestEngine(initial_capital=100_000)
    sma_portfolio = sma_engine.run(sma_df)
    sma_metrics = compute_metrics(sma_portfolio, 100_000)
    sma_metrics["completed_trades"] = len(sma_engine.trades)
    sma_metrics["win_rate"] = (
        round(100 * sum(1 for t in sma_engine.trades if t["pnl"] > 0) / len(sma_engine.trades), 1)
        if sma_engine.trades else None
    )

    # RSI
    rsi_df_indexed = compute_rsi_signals(df.set_index("date"), period=14,
                                          oversold=30, overbought=70)
    rsi_df = rsi_df_indexed.reset_index()
    rsi_engine = BacktestEngine(initial_capital=100_000)
    rsi_portfolio = rsi_engine.run(rsi_df)
    rsi_metrics = compute_metrics(rsi_portfolio, 100_000)
    rsi_metrics["completed_trades"] = len(rsi_engine.trades)
    rsi_metrics["win_rate"] = (
        round(100 * sum(1 for t in rsi_engine.trades if t["pnl"] > 0) / len(rsi_engine.trades), 1)
        if rsi_engine.trades else None
    )

    # Buy-and-Hold
    bh_df = compute_buyhold_signals(df)
    bh_engine = BacktestEngine(initial_capital=100_000)
    bh_portfolio = bh_engine.run(bh_df)
    bh_metrics = compute_metrics(bh_portfolio, 100_000)

    return {"SMA": sma_metrics, "RSI": rsi_metrics, "Buy & Hold": bh_metrics}


def print_summary_table(results: dict):
    """
    results: {ticker: {strategy_name: metrics_dict}}
    Prints one row per ticker per strategy, plus per-strategy averages.
    """
    print(f"\n{'='*100}")
    print("  SESSION 6 -- MULTI-TICKER RESULTS")
    print(f"{'='*100}")

    header = f"    {'Ticker':<8}{'Strategy':<14}{'Return':>10}{'CAGR':>9}{'Sharpe':>9}{'MaxDD':>9}{'Trades':>8}{'WinRate':>9}"
    print(header)
    print(f"    {'-'*96}")

    for ticker, strategies in results.items():
        for name, m in strategies.items():
            trades = m.get("completed_trades", "-")
            win_rate = f"{m['win_rate']:.0f}%" if m.get("win_rate") is not None else "-"
            print(f"    {ticker:<8}{name:<14}{m['total_return']:>9.1f}%{m['cagr']:>8.1f}%"
                  f"{m['sharpe_ratio']:>9.2f}{m['max_drawdown']:>8.1f}%{str(trades):>8}{win_rate:>9}")
        print(f"    {'-'*96}")

    # ── per-strategy averages across all tickers ──
    print(f"\n    AVERAGES ACROSS ALL {len(results)} TICKERS")
    print(f"    {'-'*96}")
    for name in ["SMA", "RSI", "Buy & Hold"]:
        returns = [results[t][name]["total_return"] for t in results]
        sharpes = [results[t][name]["sharpe_ratio"] for t in results]
        dds = [results[t][name]["max_drawdown"] for t in results]
        print(f"    {name:<14}avg return {sum(returns)/len(returns):>7.1f}%   "
              f"avg Sharpe {sum(sharpes)/len(sharpes):>5.2f}   "
              f"avg MaxDD {sum(dds)/len(dds):>6.1f}%")

    # ── win counts: how many tickers did each strategy "win" on return? ──
    print(f"\n    BEST TOTAL RETURN, BY TICKER")
    print(f"    {'-'*96}")
    win_counts = {"SMA": 0, "RSI": 0, "Buy & Hold": 0}
    for ticker, strategies in results.items():
        best = max(strategies, key=lambda n: strategies[n]["total_return"])
        win_counts[best] += 1
        print(f"    {ticker:<8}-> {best}")
    print(f"\n    Win counts: " + "  ".join(f"{k}: {v}" for k, v in win_counts.items()))
    print(f"{'='*100}\n")


def main():
    parser = argparse.ArgumentParser(description="Session 6: multi-ticker strategy comparison")
    parser.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS,
                         help="Space-separated tickers (default: 9-ticker sector spread)")
    args = parser.parse_args()

    tickers = [t.upper() for t in args.tickers]
    results = {}

    for ticker in tickers:
        print(f"  Running {ticker} ...")
        try:
            results[ticker] = run_all_strategies(ticker)
        except Exception as e:
            print(f"  Skipped {ticker}: {e}", file=sys.stderr)

    print_summary_table(results)

    # save a CSV for later reference / README table
    rows = []
    for ticker, strategies in results.items():
        for name, m in strategies.items():
            rows.append({
                "ticker": ticker, "strategy": name,
                "total_return_pct": m["total_return"], "cagr_pct": m["cagr"],
                "sharpe": m["sharpe_ratio"], "max_drawdown_pct": m["max_drawdown"],
                "completed_trades": m.get("completed_trades"),
                "win_rate_pct": m.get("win_rate"),
            })
    out_df = pd.DataFrame(rows)
    out_df.to_csv("session6_multi_ticker_results.csv", index=False)
    print(f"  Saved session6_multi_ticker_results.csv")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)