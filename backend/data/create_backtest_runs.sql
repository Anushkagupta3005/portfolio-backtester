-- Session 8: History & Notes
-- Run this once against your existing `backtester` database.
-- (mysql -u <user> -p backtester < create_backtest_runs.sql)

CREATE TABLE IF NOT EXISTS backtest_runs (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    ticker        VARCHAR(16)     NOT NULL,
    strategy      VARCHAR(32)     NOT NULL,
    start_date    DATE            NULL,       -- NULL means "from inception" (no filter was applied)
    end_date      DATE            NULL,       -- NULL means "to latest"
    total_return  DECIMAL(10, 2)  NOT NULL,
    cagr          DECIMAL(10, 2)  NOT NULL,
    sharpe_ratio  DECIMAL(10, 2)  NOT NULL,
    max_drawdown  DECIMAL(10, 2)  NOT NULL,
    final_value   DECIMAL(14, 2)  NOT NULL,
    note          TEXT            NULL,
    created_at    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_ticker (ticker),
    INDEX idx_created_at (created_at)
);