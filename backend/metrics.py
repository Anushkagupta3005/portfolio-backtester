"""
Session 4: Metrics Layer — Risk-Adjusted Performance & Benchmarking
=====================================================================
Computes Sharpe Ratio, Max Drawdown, and CAGR for any backtest run.
Adds a Buy-and-Hold benchmark and prints a side-by-side comparison.

Usage:   python metrics.py <TICKER>
         e.g.  python metrics.py AAPL
"""

import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ── import engine + helpers from Session 3 ──
from backtest import BacktestEngine, load_prices, compute_sma_signals


# ═══════════════════════════════════════════════════════════════════════
#  BUY-AND-HOLD SIGNAL GENERATOR
# ═══════════════════════════════════════════════════════════════════════

def compute_buyhold_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Simplest possible strategy: BUY on the first day, HOLD forever.
    Same column format as compute_sma_signals so the engine accepts it.
    """
    df = df.copy()
    df["signal"] = "HOLD"
    df.iloc[0, df.columns.get_loc("signal")] = "BUY"
    return df


# ═══════════════════════════════════════════════════════════════════════
#  METRICS COMPUTATION  (works on any portfolio_df from BacktestEngine)
# ═══════════════════════════════════════════════════════════════════════

def compute_metrics(portfolio_df: pd.DataFrame, initial_capital: float,
                    risk_free_rate: float = 0.045) -> dict:
    """
    Compute risk-adjusted metrics on a portfolio time series.

    Parameters
    ----------
    portfolio_df : DataFrame with 'date' and 'portfolio_value' columns
    initial_capital : starting dollar amount
    risk_free_rate : annualized risk-free rate (default 4.5%, approx current T-bill)

    Returns
    -------
    dict with: total_return, cagr, sharpe_ratio, max_drawdown, max_dd_start,
               max_dd_end, max_dd_recovery
    """
    values = portfolio_df["portfolio_value"].values
    dates  = portfolio_df["date"].values

    # ── Total Return ──
    final_value  = values[-1]
    total_return  = (final_value - initial_capital) / initial_capital * 100

    # ── CAGR (Compound Annual Growth Rate) ──
    trading_days = len(values)
    years        = trading_days / 252  # 252 trading days per year
    cagr         = ((final_value / initial_capital) ** (1 / years) - 1) * 100

    # ── Sharpe Ratio ──
    # daily returns from portfolio value
    daily_returns   = np.diff(values) / values[:-1]
    daily_rf        = risk_free_rate / 252  # daily risk-free rate
    excess_returns  = daily_returns - daily_rf
    sharpe_ratio    = (np.mean(excess_returns) / np.std(excess_returns,
                       ddof=1)) * np.sqrt(252)

    # ── Max Drawdown ──
    running_max   = np.maximum.accumulate(values)
    drawdown      = (running_max - values) / running_max
    max_drawdown  = np.max(drawdown) * 100  # as percentage

    # find the peak and trough dates for the worst drawdown
    trough_idx    = np.argmax(drawdown)
    peak_idx      = np.argmax(values[:trough_idx + 1])
    max_dd_start  = pd.Timestamp(dates[peak_idx])
    max_dd_end    = pd.Timestamp(dates[trough_idx])

    # did it recover? find first date after trough where value >= peak value
    peak_value    = values[peak_idx]
    recovery_mask = values[trough_idx:] >= peak_value
    if np.any(recovery_mask):
        recovery_idx   = trough_idx + np.argmax(recovery_mask)
        max_dd_recovery = pd.Timestamp(dates[recovery_idx])
    else:
        max_dd_recovery = None  # never recovered within the data

    return {
        "total_return":    round(total_return, 2),
        "cagr":            round(cagr, 2),
        "sharpe_ratio":    round(sharpe_ratio, 2),
        "max_drawdown":    round(max_drawdown, 2),
        "max_dd_start":    max_dd_start,
        "max_dd_end":      max_dd_end,
        "max_dd_recovery": max_dd_recovery,
        "final_value":     round(final_value, 2),
    }


# ═══════════════════════════════════════════════════════════════════════
#  COMPARISON DISPLAY
# ═══════════════════════════════════════════════════════════════════════

def print_comparison(ticker: str, sma_metrics: dict, bh_metrics: dict,
                     sma_trades: list):
    """Print side-by-side SMA vs Buy-and-Hold metrics."""
    print(f"\n{'='*72}")
    print(f"  {ticker} — STRATEGY COMPARISON: SMA Crossover vs Buy-and-Hold")
    print(f"{'='*72}")

    rows = [
        ("Total Return",   f"{sma_metrics['total_return']:>10.2f}%",
                           f"{bh_metrics['total_return']:>10.2f}%"),
        ("CAGR",           f"{sma_metrics['cagr']:>10.2f}%",
                           f"{bh_metrics['cagr']:>10.2f}%"),
        ("Sharpe Ratio",   f"{sma_metrics['sharpe_ratio']:>10.2f}",
                           f"{bh_metrics['sharpe_ratio']:>10.2f}"),
        ("Max Drawdown",   f"{sma_metrics['max_drawdown']:>10.2f}%",
                           f"{bh_metrics['max_drawdown']:>10.2f}%"),
        ("Final Value",    f"${sma_metrics['final_value']:>13,.2f}",
                           f"${bh_metrics['final_value']:>13,.2f}"),
    ]

    header = f"    {'Metric':<20}{'SMA Crossover':>16}{'Buy & Hold':>16}"
    print(header)
    print(f"    {'─'*52}")
    for label, sma_val, bh_val in rows:
        print(f"    {label:<20}{sma_val:>16}{bh_val:>16}")

    # ── Drawdown detail ──
    print(f"\n    {'─'*52}")
    print(f"    MAX DRAWDOWN DETAIL")
    print(f"    {'─'*52}")

    for name, m in [("SMA Crossover", sma_metrics), ("Buy & Hold", bh_metrics)]:
        recovery_str = (m["max_dd_recovery"].strftime("%Y-%m-%d")
                       if m["max_dd_recovery"] else "not yet recovered")
        print(f"    {name}:")
        print(f"      Peak:     {m['max_dd_start'].strftime('%Y-%m-%d')}")
        print(f"      Trough:   {m['max_dd_end'].strftime('%Y-%m-%d')}")
        print(f"      Recovery: {recovery_str}")
        print(f"      Drop:     -{m['max_drawdown']:.2f}%")

    # ── Verdict ──
    print(f"\n    {'─'*52}")
    print(f"    VERDICT")
    print(f"    {'─'*52}")

    if sma_metrics["total_return"] > bh_metrics["total_return"]:
        print(f"    SMA beat Buy-and-Hold on total return by "
              f"{sma_metrics['total_return'] - bh_metrics['total_return']:.2f}pp")
    else:
        print(f"    Buy-and-Hold beat SMA on total return by "
              f"{bh_metrics['total_return'] - sma_metrics['total_return']:.2f}pp")

    if sma_metrics["max_drawdown"] < bh_metrics["max_drawdown"]:
        print(f"    SMA had smaller max drawdown by "
              f"{bh_metrics['max_drawdown'] - sma_metrics['max_drawdown']:.2f}pp "
              f"(better downside protection)")
    else:
        print(f"    Buy-and-Hold had smaller max drawdown by "
              f"{sma_metrics['max_drawdown'] - bh_metrics['max_drawdown']:.2f}pp")

    if sma_metrics["sharpe_ratio"] > bh_metrics["sharpe_ratio"]:
        print(f"    SMA had better risk-adjusted return "
              f"(Sharpe {sma_metrics['sharpe_ratio']} vs {bh_metrics['sharpe_ratio']})")
    else:
        print(f"    Buy-and-Hold had better risk-adjusted return "
              f"(Sharpe {bh_metrics['sharpe_ratio']} vs {sma_metrics['sharpe_ratio']})")

    print(f"{'='*72}\n")


# ═══════════════════════════════════════════════════════════════════════
#  COMPARISON CHART
# ═══════════════════════════════════════════════════════════════════════

def plot_comparison(sma_portfolio: pd.DataFrame, bh_portfolio: pd.DataFrame,
                    ticker: str, sma_metrics: dict, bh_metrics: dict,
                    initial_capital: float):
    """
    Three-panel chart:
      Top:    both portfolio curves overlaid
      Middle: drawdown over time for both
      Bottom: stock price for context
    """
    fig, (ax1, ax2, ax3) = plt.subplots(
        3, 1, figsize=(14, 11), sharex=True,
        gridspec_kw={"height_ratios": [3, 1.5, 1]},
    )
    fig.suptitle(
        f"{ticker} — SMA Crossover vs Buy-and-Hold\n"
        f"Sharpe: {sma_metrics['sharpe_ratio']} vs {bh_metrics['sharpe_ratio']}  |  "
        f"Max DD: -{sma_metrics['max_drawdown']:.1f}% vs -{bh_metrics['max_drawdown']:.1f}%",
        fontsize=13, fontweight="bold",
    )

    dates_sma = sma_portfolio["date"]
    dates_bh  = bh_portfolio["date"]

    # ── Top: portfolio value ──
    ax1.plot(dates_sma, sma_portfolio["portfolio_value"],
             color="#2196F3", linewidth=1.5, label="SMA Crossover")
    ax1.plot(dates_bh, bh_portfolio["portfolio_value"],
             color="#FF9800", linewidth=1.5, label="Buy & Hold")
    ax1.axhline(y=initial_capital, color="gray", linestyle="--",
                alpha=0.4, label="Initial Capital")
    ax1.set_ylabel("Portfolio Value ($)")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)
    ax1.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: f"${x:,.0f}")
    )

    # ── Middle: drawdown ──
    sma_values   = sma_portfolio["portfolio_value"].values
    sma_running  = np.maximum.accumulate(sma_values)
    sma_dd       = (sma_running - sma_values) / sma_running * 100

    bh_values    = bh_portfolio["portfolio_value"].values
    bh_running   = np.maximum.accumulate(bh_values)
    bh_dd        = (bh_running - bh_values) / bh_running * 100

    ax2.fill_between(dates_sma, 0, -sma_dd, alpha=0.4, color="#2196F3",
                     label="SMA Drawdown")
    ax2.fill_between(dates_bh, 0, -bh_dd, alpha=0.4, color="#FF9800",
                     label="B&H Drawdown")
    ax2.set_ylabel("Drawdown (%)")
    ax2.legend(loc="lower left")
    ax2.grid(True, alpha=0.3)

    # ── Bottom: stock price ──
    ax3.plot(dates_sma, sma_portfolio["price"], color="gray",
             linewidth=0.8, label=f"{ticker} Price")
    ax3.set_ylabel("Price ($)")
    ax3.set_xlabel("Date")
    ax3.legend(loc="upper left")
    ax3.grid(True, alpha=0.3)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    fig.autofmt_xdate(rotation=30)

    plt.tight_layout()

    filename = f"metrics_{ticker}.png"
    plt.savefig(filename, dpi=150, bbox_inches="tight")
    print(f"  Chart saved: {filename}")
    plt.show()


# ═══════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python metrics.py <TICKER>")
        sys.exit(1)

    ticker = sys.argv[1].upper()
    print(f"\n  Loading {ticker} from database ...")

    # 1  load prices
    df = load_prices(ticker)
    print(f"  Loaded {len(df)} rows")

    # 2  run SMA crossover strategy
    print(f"\n  Running SMA Crossover backtest ...")
    sma_df     = compute_sma_signals(df)
    sma_engine = BacktestEngine(initial_capital=100_000)
    sma_portfolio = sma_engine.run(sma_df)
    sma_engine.print_trade_log()

    # 3  run Buy-and-Hold benchmark
    print(f"\n  Running Buy-and-Hold benchmark ...")
    bh_df      = compute_buyhold_signals(df)
    bh_engine  = BacktestEngine(initial_capital=100_000)
    bh_portfolio = bh_engine.run(bh_df)

    # 4  compute metrics
    sma_metrics = compute_metrics(sma_portfolio, 100_000)
    bh_metrics  = compute_metrics(bh_portfolio, 100_000)

    # 5  print comparison
    print_comparison(ticker, sma_metrics, bh_metrics, sma_engine.trades)

    # 6  plot
    plot_comparison(sma_portfolio, bh_portfolio, ticker,
                    sma_metrics, bh_metrics, 100_000)