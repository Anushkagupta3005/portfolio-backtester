"""
Session 3: Backtest Engine — Trade Simulation & P&L Tracking
=============================================================
Simulates trades from strategy signals and tracks portfolio performance.

Design:  Strategy-agnostic.  The BacktestEngine class accepts any DataFrame
         with (date, close, signal) columns, so it works with SMA crossover
         today and Buy-and-Hold / RSI / anything else tomorrow — no rework.

Rules:   Long-only, all-in position sizing, whole shares, no transaction
         costs or slippage (noted in limitations).

Usage:   python backtest.py <TICKER>
         e.g.  python backtest.py AAPL
"""

import sys
import pandas as pd
import mysql.connector
import matplotlib
matplotlib.use("TkAgg")          # interactive window on macOS
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


# ═══════════════════════════════════════════════════════════════════════
#  DATA & SIGNAL GENERATION  (reused from strategy.py — same logic)
# ═══════════════════════════════════════════════════════════════════════

def load_prices(ticker: str) -> pd.DataFrame:
    """Load OHLCV from MySQL (same connection as ingest.py / strategy.py)."""
    conn = mysql.connector.connect(
        host="localhost", user="root", password="YOUR_PASSWORD_HERE", database="backtester"
    )
    query = """
        SELECT date, open, high, low, close, volume
          FROM price_history
         WHERE ticker = %s
         ORDER BY date
    """
    df = pd.read_sql(query, conn, params=(ticker,))
    conn.close()
    df["date"] = pd.to_datetime(df["date"])
    return df


def compute_sma_signals(
    df: pd.DataFrame, short_window: int = 50, long_window: int = 200
) -> pd.DataFrame:
    """
    Compute SMA crossover signals (Golden Cross / Death Cross).
    Returns a copy of df with added columns: sma_short, sma_long, signal.
    """
    df = df.copy()
    df["sma_short"] = df["close"].rolling(window=short_window).mean()
    df["sma_long"]  = df["close"].rolling(window=long_window).mean()
    df["signal"]    = "HOLD"

    prev_short = df["sma_short"].shift(1)
    prev_long  = df["sma_long"].shift(1)

    golden = (prev_short <= prev_long) & (df["sma_short"] > df["sma_long"])
    death  = (prev_short >= prev_long) & (df["sma_short"] < df["sma_long"])

    df.loc[golden, "signal"] = "BUY"
    df.loc[death,  "signal"] = "SELL"
    return df


# ═══════════════════════════════════════════════════════════════════════
#  BACKTEST ENGINE  (strategy-agnostic)
# ═══════════════════════════════════════════════════════════════════════

class BacktestEngine:
    """
    Simulates a long-only portfolio from BUY / SELL / HOLD signals.

    Position sizing : all-in (buy as many whole shares as cash allows)
    Exit rule       : full liquidation on SELL
    Shorting        : none — SELL with no position is ignored
    Costs           : none modeled (flagged as a known limitation)
    """

    def __init__(self, initial_capital: float = 100_000):
        self.initial_capital = initial_capital
        self.trades: list[dict]    = []   # completed round-trip trades
        self.portfolio_df: pd.DataFrame = pd.DataFrame()
        # open-position tracking (for summary)
        self._open_entry_price: float = 0.0
        self._open_entry_date  = None
        self._open_shares: int = 0

    # ── core loop ────────────────────────────────────────────────────

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Walk through *df* day by day, execute signals, record snapshots.

        Required columns: date, close, signal  (signal ∈ {BUY, SELL, HOLD})
        Returns: DataFrame of daily portfolio snapshots.
        """
        cash   = self.initial_capital
        shares = 0
        entry_price = 0.0
        entry_date  = None
        self.trades = []
        snapshots   = []

        for _, row in df.iterrows():
            date   = row["date"]
            price  = row["close"]
            signal = row["signal"]

            # ── execute ──
            if signal == "BUY" and shares == 0:
                shares      = int(cash // price)   # whole shares only
                entry_price = price
                entry_date  = date
                cash       -= shares * price

            elif signal == "SELL" and shares > 0:
                proceeds = shares * price
                pnl      = (price - entry_price) * shares
                pnl_pct  = (price - entry_price) / entry_price * 100

                self.trades.append({
                    "entry_date":  entry_date,
                    "entry_price": entry_price,
                    "exit_date":   date,
                    "exit_price":  price,
                    "shares":      shares,
                    "pnl":         round(pnl, 2),
                    "pnl_pct":     round(pnl_pct, 2),
                })

                cash  += proceeds
                shares = 0
                entry_price = 0.0
                entry_date  = None

            # ── daily snapshot ──
            snapshots.append({
                "date":            date,
                "cash":            round(cash, 2),
                "shares":          shares,
                "price":           price,
                "portfolio_value": round(cash + shares * price, 2),
            })

        self.portfolio_df = pd.DataFrame(snapshots)

        # remember open position for summary
        self._open_shares      = shares
        self._open_entry_price = entry_price
        self._open_entry_date  = entry_date
        return self.portfolio_df

    # ── reporting ────────────────────────────────────────────────────

    def print_trade_log(self):
        """Print each completed round-trip trade with P&L."""
        print(f"\n{'='*72}")
        print("  TRADE LOG — completed round-trip trades")
        print(f"{'='*72}")

        if not self.trades:
            print("  (no completed trades)")
            return

        for i, t in enumerate(self.trades, 1):
            tag = "WIN " if t["pnl"] >= 0 else "LOSS"
            print(f"\n  Trade {i}  [{tag}]")
            print(f"    Entry : {t['entry_date'].strftime('%Y-%m-%d')}  "
                  f"@ ${t['entry_price']:,.2f}")
            print(f"    Exit  : {t['exit_date'].strftime('%Y-%m-%d')}  "
                  f"@ ${t['exit_price']:,.2f}")
            days = (t["exit_date"] - t["entry_date"]).days
            print(f"    Held  : {days} calendar days   |   "
                  f"Shares: {t['shares']}")
            print(f"    P&L   : ${t['pnl']:+,.2f}  ({t['pnl_pct']:+.2f}%)")

    def print_summary(self):
        """Print portfolio-level summary statistics."""
        pdf = self.portfolio_df
        final_value  = pdf["portfolio_value"].iloc[-1]
        total_return = (final_value - self.initial_capital) / self.initial_capital * 100

        start_date = pdf["date"].iloc[0].strftime("%Y-%m-%d")
        end_date   = pdf["date"].iloc[-1].strftime("%Y-%m-%d")

        wins   = [t for t in self.trades if t["pnl"] > 0]
        losses = [t for t in self.trades if t["pnl"] <= 0]

        print(f"\n{'='*72}")
        print("  PORTFOLIO SUMMARY")
        print(f"{'='*72}")
        print(f"    Period:           {start_date}  →  {end_date}")
        print(f"    Initial Capital:  ${self.initial_capital:>14,.2f}")
        print(f"    Final Value:      ${final_value:>14,.2f}")
        print(f"    Total Return:     {total_return:>13.2f}%")
        print(f"    Completed Trades: {len(self.trades):>14d}")
        print(f"      Wins:           {len(wins):>14d}")
        print(f"      Losses:         {len(losses):>14d}")

        if self.trades:
            win_rate = len(wins) / len(self.trades) * 100
            print(f"    Win Rate:         {win_rate:>13.1f}%")

            total_pnl = sum(t["pnl"] for t in self.trades)
            print(f"    Realized P&L:     ${total_pnl:>14,.2f}")

            avg_win  = (sum(t["pnl"] for t in wins) / len(wins)) if wins else 0
            avg_loss = (sum(t["pnl"] for t in losses) / len(losses)) if losses else 0
            print(f"    Avg Win:          ${avg_win:>14,.2f}")
            print(f"    Avg Loss:         ${avg_loss:>14,.2f}")

        # open position warning
        if self._open_shares > 0:
            last_price   = pdf["price"].iloc[-1]
            unrealized   = (last_price - self._open_entry_price) * self._open_shares
            unreal_pct   = ((last_price - self._open_entry_price)
                           / self._open_entry_price * 100)
            print(f"\n    ** OPEN POSITION (not in realized P&L) **")
            print(f"    Entry:       {self._open_entry_date.strftime('%Y-%m-%d')}  "
                  f"@ ${self._open_entry_price:,.2f}")
            print(f"    Shares:      {self._open_shares}")
            print(f"    Last Price:  ${last_price:,.2f}")
            print(f"    Unrealized:  ${unrealized:+,.2f}  ({unreal_pct:+.2f}%)")

        print(f"{'='*72}\n")


# ═══════════════════════════════════════════════════════════════════════
#  VISUALIZATION
# ═══════════════════════════════════════════════════════════════════════

def plot_backtest(portfolio_df: pd.DataFrame, ticker: str, trades: list,
                  initial_capital: float):
    """
    Two-panel chart:
      Top:    portfolio value over time, trade entry/exit markers, shaded
              holding periods (green = winning trade, red = losing trade)
      Bottom: underlying stock price for context
    Saves PNG + shows interactive window.
    """
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(14, 9), sharex=True,
        gridspec_kw={"height_ratios": [2, 1]},
    )
    fig.suptitle(f"{ticker} — SMA Crossover Backtest  "
                 f"(${initial_capital:,.0f} start)",
                 fontsize=14, fontweight="bold")

    dates = portfolio_df["date"]
    pval  = portfolio_df["portfolio_value"]

    # ── top panel: portfolio value ──
    ax1.plot(dates, pval, color="#2196F3", linewidth=1.5, label="Portfolio Value")
    ax1.axhline(y=initial_capital, color="gray", linestyle="--",
                alpha=0.5, label="Initial Capital")

    for t in trades:
        color = "#4CAF50" if t["pnl"] >= 0 else "#F44336"
        ax1.axvspan(t["entry_date"], t["exit_date"], alpha=0.07, color=color)

        # entry marker (▲)
        mask_e = portfolio_df["date"] == t["entry_date"]
        if mask_e.any():
            ax1.plot(t["entry_date"], pval[mask_e].values[0],
                     marker="^", color="#4CAF50", markersize=10, zorder=5)
        # exit marker (▼)
        mask_x = portfolio_df["date"] == t["exit_date"]
        if mask_x.any():
            ax1.plot(t["exit_date"], pval[mask_x].values[0],
                     marker="v", color="#F44336", markersize=10, zorder=5)

    ax1.set_ylabel("Portfolio Value ($)")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)
    ax1.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: f"${x:,.0f}")
    )

    # ── bottom panel: stock price ──
    ax2.plot(dates, portfolio_df["price"], color="#FF9800",
             linewidth=1, label=f"{ticker} Close Price")
    ax2.set_ylabel("Stock Price ($)")
    ax2.set_xlabel("Date")
    ax2.legend(loc="upper left")
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    fig.autofmt_xdate(rotation=30)

    plt.tight_layout()

    filename = f"backtest_{ticker}.png"
    plt.savefig(filename, dpi=150, bbox_inches="tight")
    print(f"  Chart saved: {filename}")
    plt.show()


# ═══════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python backtest.py <TICKER>")
        sys.exit(1)

    ticker = sys.argv[1].upper()
    print(f"\n  Loading {ticker} from database ...")

    # 1  load
    df = load_prices(ticker)
    print(f"  Loaded {len(df)} rows")

    # 2  signals
    df = compute_sma_signals(df)
    buys  = (df["signal"] == "BUY").sum()
    sells = (df["signal"] == "SELL").sum()
    print(f"  Signals: {buys} BUY  /  {sells} SELL")

    # 3  backtest
    engine = BacktestEngine(initial_capital=100_000)
    portfolio_df = engine.run(df)

    # 4  results
    engine.print_trade_log()
    engine.print_summary()

    # 5  chart
    plot_backtest(portfolio_df, ticker, engine.trades, engine.initial_capital)