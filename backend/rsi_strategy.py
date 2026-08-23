"""
rsi_strategy.py -- Session 5: RSI Strategy

Reads price_history from MySQL, computes the 14-day RSI, generates
buy/sell/hold signals on threshold crossing (oversold / overbought),
and plots price + RSI with the 30/70 bands and signal points marked.

Signal convention (immediate cross):
    BUY  the moment RSI crosses BELOW 30 (oversold -> expect a bounce)
    SELL the moment RSI crosses ABOVE 70 (overbought -> expect a pullback)

Usage:
    python rsi_strategy.py AAPL
    python rsi_strategy.py AAPL --period 14 --oversold 30 --overbought 70
    python rsi_strategy.py AAPL --no-show   # save PNG only, skip interactive window
"""

import argparse
import sys

import matplotlib.pyplot as plt
import mysql.connector

import pandas as pd

# --- DB config: match whatever is hardcoded in ingest.py / strategy.py ---
from config import DB_CONFIG


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


def compute_rsi(close: pd.Series, period: int) -> pd.Series:
    """
    Wilder's RSI.

    1. day-over-day price change
    2. split into gains (up days) and losses (down days, as positive numbers)
    3. average gain / average loss over the window, smoothed Wilder-style
       (this is the standard RSI smoothing -- a plain rolling mean is a
       common simplification but drifts from the textbook definition over
       long series, so we use the proper exponential form here)
    4. RS = avg_gain / avg_loss ; RSI = 100 - (100 / (1 + RS))
    """
    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    # Wilder's smoothing = an EMA with alpha = 1/period
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    # Where avg_loss is 0 (straight up move for `period` days), RS is inf -> RSI = 100
    rsi = rsi.where(avg_loss != 0, 100.0)

    return rsi


def compute_signals(df: pd.DataFrame, period: int, oversold: int, overbought: int) -> pd.DataFrame:
    """Add an rsi column and a signal column based on threshold crossing."""
    df = df.copy()
    df["rsi"] = compute_rsi(df["close"], period)

    below_oversold = df["rsi"] < oversold
    above_overbought = df["rsi"] > overbought

    # Immediate-cross convention: signal fires only on the day the threshold
    # is first crossed, not on every day RSI remains beyond it.
    crossed_into_oversold = below_oversold & ~below_oversold.shift(1, fill_value=False)
    crossed_into_overbought = above_overbought & ~above_overbought.shift(1, fill_value=False)

    df["signal"] = "HOLD"
    df.loc[crossed_into_oversold, "signal"] = "BUY"
    df.loc[crossed_into_overbought, "signal"] = "SELL"

    # Rows before RSI has enough data are meaningless -> mark HOLD
    df.loc[df["rsi"].isna(), "signal"] = "HOLD"

    return df


def plot_signals(df: pd.DataFrame, ticker: str, period: int, oversold: int, overbought: int,
                  out_path: str, show: bool) -> None:
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9), sharex=True,
                                    gridspec_kw={"height_ratios": [2, 1]})

    # --- Top panel: price with BUY/SELL markers ---
    ax1.plot(df.index, df["close"], label="Close", color="#333333", linewidth=1)

    buys = df[df["signal"] == "BUY"]
    sells = df[df["signal"] == "SELL"]

    ax1.scatter(buys.index, buys["close"], marker="^", color="green", s=120,
                label="RSI < oversold (BUY)", zorder=5)
    ax1.scatter(sells.index, sells["close"], marker="v", color="red", s=120,
                label="RSI > overbought (SELL)", zorder=5)

    ax1.set_title(f"{ticker} -- RSI({period}) Strategy ({oversold}/{overbought})")
    ax1.set_ylabel("Price")
    ax1.legend(loc="upper left")
    ax1.grid(alpha=0.3)

    # --- Bottom panel: RSI with threshold bands ---
    ax2.plot(df.index, df["rsi"], label=f"RSI({period})", color="#8e44ad", linewidth=1.2)
    ax2.axhline(overbought, color="red", linestyle="--", linewidth=1, alpha=0.7)
    ax2.axhline(oversold, color="green", linestyle="--", linewidth=1, alpha=0.7)
    ax2.fill_between(df.index, oversold, overbought, color="gray", alpha=0.08)
    ax2.set_ylim(0, 100)
    ax2.set_xlabel("Date")
    ax2.set_ylabel("RSI")
    ax2.legend(loc="upper left")
    ax2.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"Saved plot to {out_path}")

    if show:
        plt.show()
    else:
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Session 5: RSI strategy engine")
    parser.add_argument("ticker", help="Ticker symbol, e.g. AAPL")
    parser.add_argument("--period", type=int, default=14, help="RSI lookback period (default 14)")
    parser.add_argument("--oversold", type=int, default=30, help="Oversold threshold (default 30)")
    parser.add_argument("--overbought", type=int, default=70, help="Overbought threshold (default 70)")
    parser.add_argument("--no-show", action="store_true", help="Save PNG only, skip interactive window")
    args = parser.parse_args()

    ticker = args.ticker.upper()

    print(f"Loading price history for {ticker}...")
    df = load_price_history(ticker)
    print(f"Loaded {len(df)} rows: {df.index.min().date()} -> {df.index.max().date()}")

    print(f"Computing RSI({args.period}) and {args.oversold}/{args.overbought} threshold signals...")
    df = compute_signals(df, args.period, args.oversold, args.overbought)

    n_buy = (df["signal"] == "BUY").sum()
    n_sell = (df["signal"] == "SELL").sum()
    print(f"Signals generated: {n_buy} BUY (oversold), {n_sell} SELL (overbought)")

    if n_buy:
        print("\nBUY (oversold cross) dates:")
        for d in df[df["signal"] == "BUY"].index:
            print(f"  {d.date()}  RSI={df.loc[d, 'rsi']:.1f}")
    if n_sell:
        print("\nSELL (overbought cross) dates:")
        for d in df[df["signal"] == "SELL"].index:
            print(f"  {d.date()}  RSI={df.loc[d, 'rsi']:.1f}")

    out_path = f"{ticker.lower()}_rsi_signals.png"
    plot_signals(df, ticker, args.period, args.oversold, args.overbought, out_path, show=not args.no_show)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)