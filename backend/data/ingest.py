"""
ingest.py

Fetches historical OHLCV price data for a ticker via yfinance,
cleans it, and upserts it into the `price_history` MySQL table.

Usage:
    python ingest.py AAPL 2018-01-01 2026-01-01
"""

import sys
import mysql.connector
import yfinance as yf

# ---- MySQL connection config ----
# Update these to match your local setup.
from config import DB_CONFIG

def fetch_price_data(ticker: str, start_date: str, end_date: str):
    """Pull OHLCV data from yfinance for the given ticker and date range."""
    print(f"Fetching {ticker} from {start_date} to {end_date}...")
    df = yf.download(ticker, start=start_date, end=end_date, auto_adjust=True)

    if df.empty:
        raise ValueError(f"No data returned for {ticker}. Check the ticker/date range.")

    # yfinance sometimes returns MultiIndex columns when auto_adjust=True
    # for a single ticker — flatten if needed.
    if isinstance(df.columns, __import__("pandas").MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.reset_index()  # turns the Date index into a column
    return df


def clean_price_data(df):
    """
    Handle the messiness real price data has:
    - Drop any rows with missing OHLCV values (shouldn't happen often,
      but corporate actions / data gaps can cause NaNs)
    - auto_adjust=True in fetch already handles splits/dividends by
      adjusting historical prices, so we don't need to do that manually
    """
    before = len(df)
    df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
    dropped = before - len(df)
    if dropped:
        print(f"Dropped {dropped} rows with missing data.")
    return df


def upsert_price_data(df, ticker: str):
    """Insert rows into MySQL, updating on conflict (ticker, date)."""
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    insert_query = """
        INSERT INTO price_history (ticker, date, open, high, low, close, volume)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            open = VALUES(open),
            high = VALUES(high),
            low = VALUES(low),
            close = VALUES(close),
            volume = VALUES(volume)
    """

    rows = [
        (
            ticker,
            row["Date"].date(),
            float(row["Open"]),
            float(row["High"]),
            float(row["Low"]),
            float(row["Close"]),
            int(row["Volume"]),
        )
        for _, row in df.iterrows()
    ]

    cursor.executemany(insert_query, rows)
    conn.commit()

    print(f"Upserted {cursor.rowcount} rows for {ticker}.")

    cursor.close()
    conn.close()


def main():
    if len(sys.argv) != 4:
        print("Usage: python ingest.py TICKER START_DATE END_DATE")
        print("Example: python ingest.py AAPL 2018-01-01 2026-01-01")
        sys.exit(1)

    ticker, start_date, end_date = sys.argv[1], sys.argv[2], sys.argv[3]

    df = fetch_price_data(ticker, start_date, end_date)
    df = clean_price_data(df)
    upsert_price_data(df, ticker)

    print("Done.")


if __name__ == "__main__":
    main()
