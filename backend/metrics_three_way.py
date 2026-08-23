"""
Session 5: Metrics Layer, extended — SMA vs RSI vs Buy-and-Hold
=================================================================
Same compute_metrics() from Session 4 (untouched, already strategy-agnostic).
print_comparison() and plot_comparison() are generalized here to take any
number of named strategies instead of being hardcoded to exactly two.

Usage:   python metrics_three_way.py <TICKER>
         e.g.  python metrics_three_way.py AAPL
"""

import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from backtest import BacktestEngine, load_prices, compute_sma_signals
from metrics import compute_buyhold_signals, compute_metrics
from rsi_strategy import compute_signals as compute_rsi_signals


# ═══════════════════════════════════════════════════════════════════════
#  COMPARISON DISPLAY  (generalized to N strategies)
# ═══════════════════════════════════════════════════════════════════════

def print_comparison_n(ticker: str, strategies: dict):
    """
    strategies: {name: metrics_dict} for any number of strategies,
    e.g. {"SMA Crossover": sma_metrics, "RSI": rsi_metrics, "Buy & Hold": bh_metrics}
    """
    names = list(strategies.keys())

    print(f"\n{'='*80}")
    print(f"  {ticker} — STRATEGY COMPARISON: {' vs '.join(names)}")
    print(f"{'='*80}")

    col_width = 16
    header = f"    {'Metric':<18}" + "".join(f"{n:>{col_width}}" for n in names)
    print(header)
    print(f"    {'─'*(18 + col_width * len(names))}")

    def row(label, key, fmt):
        cells = "".join(f"{fmt(strategies[n][key]):>{col_width}}" for n in names)
        print(f"    {label:<18}{cells}")

    row("Total Return", "total_return", lambda v: f"{v:.2f}%")
    row("CAGR",         "cagr",         lambda v: f"{v:.2f}%")
    row("Sharpe Ratio", "sharpe_ratio", lambda v: f"{v:.2f}")
    row("Max Drawdown", "max_drawdown", lambda v: f"{v:.2f}%")
    row("Final Value",  "final_value",  lambda v: f"${v:,.2f}")

    # ── Drawdown detail ──
    print(f"\n    {'─'*(18 + col_width * len(names))}")
    print(f"    MAX DRAWDOWN DETAIL")
    print(f"    {'─'*(18 + col_width * len(names))}")

    for name, m in strategies.items():
        recovery_str = (m["max_dd_recovery"].strftime("%Y-%m-%d")
                       if m["max_dd_recovery"] else "not yet recovered")
        print(f"    {name}:")
        print(f"      Peak:     {m['max_dd_start'].strftime('%Y-%m-%d')}")
        print(f"      Trough:   {m['max_dd_end'].strftime('%Y-%m-%d')}")
        print(f"      Recovery: {recovery_str}")
        print(f"      Drop:     -{m['max_drawdown']:.2f}%")

    # ── Verdict ──
    print(f"\n    {'─'*(18 + col_width * len(names))}")
    print(f"    VERDICT")
    print(f"    {'─'*(18 + col_width * len(names))}")

    best_return = max(names, key=lambda n: strategies[n]["total_return"])
    best_sharpe = max(names, key=lambda n: strategies[n]["sharpe_ratio"])
    best_dd     = min(names, key=lambda n: strategies[n]["max_drawdown"])

    print(f"    Best total return:      {best_return} "
          f"({strategies[best_return]['total_return']:.2f}%)")
    print(f"    Best risk-adjusted (Sharpe): {best_sharpe} "
          f"({strategies[best_sharpe]['sharpe_ratio']:.2f})")
    print(f"    Best drawdown protection: {best_dd} "
          f"(-{strategies[best_dd]['max_drawdown']:.2f}%)")

    print(f"{'='*80}\n")


# ═══════════════════════════════════════════════════════════════════════
#  COMPARISON CHART  (generalized to N strategies)
# ═══════════════════════════════════════════════════════════════════════

def plot_comparison_n(portfolios: dict, ticker: str, strategies: dict,
                      initial_capital: float):
    """
    portfolios: {name: portfolio_df}
    strategies: {name: metrics_dict}  (same keys as portfolios)
    """
    names = list(portfolios.keys())
    colors = ["#2196F3", "#8e44ad", "#FF9800", "#4CAF50", "#F44336"]  # extend if needed

    fig, (ax1, ax2, ax3) = plt.subplots(
        3, 1, figsize=(14, 11), sharex=True,
        gridspec_kw={"height_ratios": [3, 1.5, 1]},
    )

    sharpe_str = "  |  ".join(f"{n}: {strategies[n]['sharpe_ratio']}" for n in names)
    dd_str     = "  |  ".join(f"{n}: -{strategies[n]['max_drawdown']:.1f}%" for n in names)
    fig.suptitle(
        f"{ticker} — {' vs '.join(names)}\n"
        f"Sharpe -> {sharpe_str}\nMax DD -> {dd_str}",
        fontsize=12, fontweight="bold",
    )

    # ── Top: portfolio value ──
    for i, name in enumerate(names):
        pdf = portfolios[name]
        ax1.plot(pdf["date"], pdf["portfolio_value"],
                 color=colors[i % len(colors)], linewidth=1.5, label=name)
    ax1.axhline(y=initial_capital, color="gray", linestyle="--",
                alpha=0.4, label="Initial Capital")
    ax1.set_ylabel("Portfolio Value ($)")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:,.0f}"))

    # ── Middle: drawdown ──
    for i, name in enumerate(names):
        pdf = portfolios[name]
        values = pdf["portfolio_value"].values
        running = np.maximum.accumulate(values)
        dd = (running - values) / running * 100
        ax2.fill_between(pdf["date"], 0, -dd, alpha=0.35,
                         color=colors[i % len(colors)], label=f"{name} Drawdown")
    ax2.set_ylabel("Drawdown (%)")
    ax2.legend(loc="lower left")
    ax2.grid(True, alpha=0.3)

    # ── Bottom: stock price (same for all strategies, just take the first) ──
    first_pdf = portfolios[names[0]]
    ax3.plot(first_pdf["date"], first_pdf["price"], color="gray",
             linewidth=0.8, label=f"{ticker} Price")
    ax3.set_ylabel("Price ($)")
    ax3.set_xlabel("Date")
    ax3.legend(loc="upper left")
    ax3.grid(True, alpha=0.3)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    fig.autofmt_xdate(rotation=30)

    plt.tight_layout()

    filename = f"metrics_3way_{ticker}.png"
    plt.savefig(filename, dpi=150, bbox_inches="tight")
    print(f"  Chart saved: {filename}")
    plt.show()


# ═══════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python metrics_three_way.py <TICKER>")
        sys.exit(1)

    ticker = sys.argv[1].upper()
    print(f"\n  Loading {ticker} from database ...")

    df = load_prices(ticker)
    print(f"  Loaded {len(df)} rows")

    # ── SMA Crossover ──
    print(f"\n  Running SMA Crossover backtest ...")
    sma_df = compute_sma_signals(df)
    sma_engine = BacktestEngine(initial_capital=100_000)
    sma_portfolio = sma_engine.run(sma_df)

    # ── RSI ──
    print(f"  Running RSI backtest ...")
    rsi_df_indexed = compute_rsi_signals(df.set_index("date"), period=14,
                                          oversold=30, overbought=70)
    rsi_df = rsi_df_indexed.reset_index()
    rsi_engine = BacktestEngine(initial_capital=100_000)
    rsi_portfolio = rsi_engine.run(rsi_df)

    # ── Buy-and-Hold ──
    print(f"  Running Buy-and-Hold benchmark ...")
    bh_df = compute_buyhold_signals(df)
    bh_engine = BacktestEngine(initial_capital=100_000)
    bh_portfolio = bh_engine.run(bh_df)

    # ── metrics ──
    sma_metrics = compute_metrics(sma_portfolio, 100_000)
    rsi_metrics = compute_metrics(rsi_portfolio, 100_000)
    bh_metrics  = compute_metrics(bh_portfolio, 100_000)

    strategies = {
        "SMA Crossover": sma_metrics,
        "RSI":           rsi_metrics,
        "Buy & Hold":    bh_metrics,
    }
    portfolios = {
        "SMA Crossover": sma_portfolio,
        "RSI":           rsi_portfolio,
        "Buy & Hold":    bh_portfolio,
    }

    print_comparison_n(ticker, strategies)
    plot_comparison_n(portfolios, ticker, strategies, 100_000)