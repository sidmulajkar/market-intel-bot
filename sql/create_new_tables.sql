-- ============================================================
-- Market Intel Bot: New Supabase Tables
-- Run this in Supabase SQL Editor
-- ============================================================

-- 1. VALUATION HISTORY
-- Stores daily Nifty P/E, P/B, Dividend Yield, Earnings Yield
-- Used for: historical percentile computation (3-year window)
-- Written by: src/valuation_engine.py via src/db.py save_valuation_snapshot()
-- Read by: src/db.py get_valuation_history() → formatters.py format_valuation_block()

CREATE TABLE IF NOT EXISTS valuation_history (
    date           DATE NOT NULL,
    index_name     TEXT NOT NULL DEFAULT 'NIFTY 50',
    pe             DOUBLE PRECISION,
    pb             DOUBLE PRECISION,
    div_yield      DOUBLE PRECISION,
    earnings_yield DOUBLE PRECISION,
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (date, index_name)
);

-- Index for fast percentile queries
CREATE INDEX IF NOT EXISTS idx_valuation_history_index_date
    ON valuation_history (index_name, date DESC);

-- Auto-purge: delete rows older than 3 years (1095 days)
-- Handled by db.py purge_old_data() or use Supabase pg_cron:
-- DELETE FROM valuation_history WHERE date < NOW() - INTERVAL '3 years';


-- 2. MARKET BREADTH HISTORY
-- Stores daily advance/decline ratios for McClellan Oscillator and percentile
-- Used by: src/data_fetcher.py compute_mcclellan() and format_market_breadth()
-- Written by: jobs/market_intel.py via src/db.py save_breadth_snapshot()

CREATE TABLE IF NOT EXISTS market_breadth_history (
    date       DATE PRIMARY KEY,
    advances   INTEGER NOT NULL,
    declines   INTEGER NOT NULL,
    ratio      DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_breadth_history_date
    ON market_breadth_history (date DESC);

-- Auto-purge: delete rows older than 90 days
-- Handled by db.py purge_old_data() or use Supabase pg_cron:
-- DELETE FROM market_breadth_history WHERE date < NOW() - INTERVAL '90 days';


-- ============================================================
-- VERIFICATION QUERIES (run after creating tables)
-- ============================================================

-- Check tables exist:
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN ('valuation_history', 'market_breadth_history');

-- Expected: 2 rows

-- Check indexes:
SELECT indexname FROM pg_indexes
WHERE tablename IN ('valuation_history', 'market_breadth_history');

-- Expected: idx_valuation_history_index_date, idx_breadth_history_date

-- Test insert (valuation):
INSERT INTO valuation_history (date, index_name, pe, pb, div_yield, earnings_yield)
VALUES ('2026-05-16', 'NIFTY 50', 20.59, 3.24, NULL, 4.86)
ON CONFLICT (date, index_name) DO NOTHING;

-- Test insert (breadth):
INSERT INTO market_breadth_history (date, advances, declines, ratio)
VALUES ('2026-05-16', 1850, 650, 2.85)
ON CONFLICT (date) DO NOTHING;

-- Verify data:
SELECT * FROM valuation_history ORDER BY date DESC LIMIT 5;
SELECT * FROM market_breadth_history ORDER BY date DESC LIMIT 5;
