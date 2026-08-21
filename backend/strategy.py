"""
strategy.py -- Session 2: Strategy Engine

Reads price_history from MySQL, computes short/long SMAs, generates
buy/sell/hold signals on SMA crossover (Golden Cross / Death Cross),
and plots price + both SMAs with crossover points marked.

Usage:
    python strategy.py AAPL
    python strategy.py AAPL --short 50 --long 200
    python strategy.py AAPL --no-show   # save PNG only, skip interactive window
"""

import argparse
import sys

import matplotlib.pyplot as plt
import mysql.connector
import pandas as pd

# --- DB config: match whatever is hardcoded in ingest.py ---
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "YOUR_PASSWORD_HERE",          # <-- fill in to match ingest.py
    "database": "backtester",
}


def load_price_history(ticker: str) -> pd.DataFrame:
    """Read price_history for one ticker into a DataFrame, sorted by date."""
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        query = """
            SELECT date, open, high, low, close, volume
            FROM price_history
            WHERE ticker = %s
            ORDER BY date ASC
        """
        df = pd.read_sql(query, conn, params=(ticker,))
    finally:
        conn.close()

    if df.empty:
        raise ValueError(
            f"No rows found for ticker '{ticker}' in price_history. "
            f"Did you run ingest.py for it first?"
        )

    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    return df


def compute_signals(df: pd.DataFrame, short_window: int, long_window: int) -> pd.DataFrame:
    """Add short/long SMA columns and a signal column based on crossover."""
    df = df.copy()
    df["sma_short"] = df["close"].rolling(window=short_window).mean()
    df["sma_long"] = df["close"].rolling(window=long_window).mean()

    # Position: True when short SMA is above long SMA
    above = df["sma_short"] > df["sma_long"]

    # A crossover happens where 'above' flips relative to the previous row
    crossed_up = above & ~above.shift(1, fill_value=False)     # Golden Cross
    crossed_down = ~above & above.shift(1, fill_value=False)   # Death Cross

    df["signal"] = "HOLD"
    df.loc[crossed_up, "signal"] = "BUY"
    df.loc[crossed_down, "signal"] = "SELL"

    # Rows before the long SMA has enough data are meaningless -> mark HOLD
    df.loc[df["sma_long"].isna(), "signal"] = "HOLD"

    return df


def plot_signals(df: pd.DataFrame, ticker: str, short_window: int, long_window: int,
                  out_path: str, show: bool) -> None:
    fig, ax = plt.subplots(figsize=(14, 7))

    ax.plot(df.index, df["close"], label="Close", color="#333333", linewidth=1)
    ax.plot(df.index, df["sma_short"], label=f"SMA {short_window}", color="#1f77b4", linewidth=1.2)
    ax.plot(df.index, df["sma_long"], label=f"SMA {long_window}", color="#ff7f0e", linewidth=1.2)

    buys = df[df["signal"] == "BUY"]
    sells = df[df["signal"] == "SELL"]

    ax.scatter(buys.index, buys["close"], marker="^", color="green", s=120,
               label="Golden Cross (BUY)", zorder=5)
    ax.scatter(sells.index, sells["close"], marker="v", color="red", s=120,
               label="Death Cross (SELL)", zorder=5)

    ax.set_title(f"{ticker} -- SMA Crossover Strategy ({short_window}/{long_window})")
    ax.set_xlabel("Date")
    ax.set_ylabel("Price")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"Saved plot to {out_path}")

    if show:
        plt.show()
    else:
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Session 2: SMA crossover strategy engine")
    parser.add_argument("ticker", help="Ticker symbol, e.g. AAPL")
    parser.add_argument("--short", type=int, default=50, help="Short SMA window (default 50)")
    parser.add_argument("--long", type=int, default=200, help="Long SMA window (default 200)")
    parser.add_argument("--no-show", action="store_true", help="Save PNG only, skip interactive window")
    args = parser.parse_args()

    ticker = args.ticker.upper()

    print(f"Loading price history for {ticker}...")
    df = load_price_history(ticker)
    print(f"Loaded {len(df)} rows: {df.index.min().date()} -> {df.index.max().date()}")

    print(f"Computing SMA {args.short}/{args.long} and crossover signals...")
    df = compute_signals(df, args.short, args.long)

    n_buy = (df["signal"] == "BUY").sum()
    n_sell = (df["signal"] == "SELL").sum()
    print(f"Signals generated: {n_buy} BUY (Golden Cross), {n_sell} SELL (Death Cross)")

    if n_buy:
        print("\nGolden Cross dates:")
        for d in df[df["signal"] == "BUY"].index:
            print(f"  {d.date()}")
    if n_sell:
        print("\nDeath Cross dates:")
        for d in df[df["signal"] == "SELL"].index:
            print(f"  {d.date()}")

    out_path = f"{ticker.lower()}_signals.png"
    plot_signals(df, ticker, args.short, args.long, out_path, show=not args.no_show)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
