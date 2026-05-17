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


-- ============================================================
-- 3. DAILY PREDICTIONS — Signal Accuracy Tracker
-- Stores parsed AI predictions for validation against outcomes
-- Written by: src/prediction_tracker.py parse_and_store_prediction()
-- ============================================================

CREATE TABLE IF NOT EXISTS daily_predictions (
    date            DATE PRIMARY KEY,
    run_type        TEXT NOT NULL DEFAULT 'morning',
    regime          TEXT,
    confidence      TEXT,
    dominant_factor TEXT,
    bull_pct        INTEGER,
    base_pct        INTEGER,
    bear_pct        INTEGER,
    headline        TEXT,
    nifty_close     DOUBLE PRECISION,
    raw_output      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 4. PREDICTION OUTCOMES — Accuracy Validation Results
-- Written by: src/prediction_tracker.py validate_yesterday_prediction()
-- ============================================================

CREATE TABLE IF NOT EXISTS prediction_outcomes (
    prediction_date     DATE PRIMARY KEY REFERENCES daily_predictions(date),
    actual_nifty_close  DOUBLE PRECISION,
    actual_nifty_change DOUBLE PRECISION,
    regime_correct      BOOLEAN,
    bull_accuracy       DOUBLE PRECISION,
    bear_accuracy       DOUBLE PRECISION,
    brier_score         DOUBLE PRECISION,
    evaluated_at        TIMESTAMPTZ DEFAULT NOW()
);


-- ============================================================
-- 5. MACRO ANCHOR SNAPSHOTS — Phase 8 Institutional Intelligence
-- Stores daily macro anchor values for historical percentile + cross-asset correlation
-- Written by: jobs/market_intel.py via src/db.py save_macro_snapshot()
-- Retention: 90 days
-- ============================================================

CREATE TABLE IF NOT EXISTS macro_anchor_snapshots (
    date              DATE NOT NULL,
    symbol            TEXT NOT NULL,
    name              TEXT,
    price             DOUBLE PRECISION,
    change_pct        DOUBLE PRECISION,
    weekly_change_pct DOUBLE PRECISION,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (date, symbol)
);

CREATE INDEX IF NOT EXISTS idx_macro_snapshots_symbol_date
    ON macro_anchor_snapshots (symbol, date DESC);

-- Auto-purge: delete rows older than 90 days
-- DELETE FROM macro_anchor_snapshots WHERE date < NOW() - INTERVAL '90 days';


-- ============================================================
-- 6. FII INSTITUTION TRACKER — Phase 8 SWF/Pension Fund Tracking
-- Tracks institutional investor registrations and activity
-- Written by: src/fii_tracker.py
-- Retention: 180 days
-- ============================================================

CREATE TABLE IF NOT EXISTS fii_institution_tracker (
    id                SERIAL PRIMARY KEY,
    date              DATE NOT NULL,
    institution_name  TEXT NOT NULL,
    institution_type  TEXT,  -- 'swf', 'pension', 'hedge_fund', 'etf', 'bank'
    country           TEXT,
    signal_type       TEXT,  -- 'new_registration', 'exit', 'block_deal', 'bulk_deal', 'announcement'
    amount_cr         DOUBLE PRECISION,
    details           TEXT,
    source            TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fii_tracker_date
    ON fii_institution_tracker (date DESC);

CREATE INDEX IF NOT EXISTS idx_fii_tracker_institution
    ON fii_institution_tracker (institution_name, date DESC);


-- ============================================================
-- VERIFICATION: Check all 6 tables exist
-- ============================================================

SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN ('valuation_history', 'market_breadth_history', 'daily_predictions', 'prediction_outcomes', 'macro_anchor_snapshots', 'fii_institution_tracker');


-- ============================================================
-- 7. DAILY MARKET SNAPSHOT — Rolling Statistical Memory
-- Unified daily record enabling percentile ranking, scenario matching,
-- correlation engine, and divergence detection across ALL metrics.
-- Written by: market_intel.py (evening) via db.py save_daily_market_snapshot()
-- Retention: 3 years (1095 days)
-- Size: ~100KB/year — negligible vs 2GB Supabase limit
-- ============================================================

CREATE TABLE IF NOT EXISTS daily_market_snapshot (
    date                DATE PRIMARY KEY,

    -- Price & Returns
    nifty_close         DOUBLE PRECISION,
    nifty_return_1d     DOUBLE PRECISION,   -- daily % change
    nifty_return_5d     DOUBLE PRECISION,   -- 5-day % change

    -- Breadth
    advance_decline_ratio DOUBLE PRECISION,
    advances            INTEGER,
    declines            INTEGER,
    total_market_volume DOUBLE PRECISION,

    -- Valuation
    nifty_pe            DOUBLE PRECISION,
    nifty_pb            DOUBLE PRECISION,
    earnings_yield      DOUBLE PRECISION,   -- 1/PE * 100

    -- Volatility
    india_vix           DOUBLE PRECISION,
    cboe_vix            DOUBLE PRECISION,
    vix_spread          DOUBLE PRECISION,   -- CBOE - India

    -- Macro Anchors
    usdinr              DOUBLE PRECISION,
    brent               DOUBLE PRECISION,
    gold                DOUBLE PRECISION,
    dxy                 DOUBLE PRECISION,
    us_10y              DOUBLE PRECISION,
    copper              DOUBLE PRECISION,

    -- Flows
    fii_net             DOUBLE PRECISION,   -- Cr
    dii_net             DOUBLE PRECISION,   -- Cr
    fii_fno_net         DOUBLE PRECISION,   -- F&O position

    -- Derivatives
    pcr                 DOUBLE PRECISION,
    max_pain            DOUBLE PRECISION,
    put_oi_total        DOUBLE PRECISION,
    call_oi_total       DOUBLE PRECISION,

    -- Computed Intelligence
    bull_bear_score     DOUBLE PRECISION,   -- 0-100
    fear_greed_score    DOUBLE PRECISION,   -- 0-100
    momentum_12m        DOUBLE PRECISION,   -- 12M return %
    carry_risk_index    DOUBLE PRECISION,   -- 0-100

    -- Metadata
    run_type            TEXT DEFAULT 'evening',  -- morning/evening
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_daily_snapshot_date
    ON daily_market_snapshot (date DESC);

-- Auto-purge: delete rows older than 3 years (1095 days)
-- Handled by db.py purge_old_data()


-- ============================================================
-- 8. CORRELATION MATRIX — Rolling signal correlations
-- Stores computed correlations for weekly digest and dynamic weighting
-- Written by: quant_enrichment.py compute_rolling_correlations()
-- Updated weekly (not daily — saves compute)
-- ============================================================

CREATE TABLE IF NOT EXISTS correlation_matrix (
    id              SERIAL PRIMARY KEY,
    date            DATE NOT NULL,
    window_days     INTEGER NOT NULL DEFAULT 90,
    pair_name       TEXT NOT NULL,          -- 'fii_vs_nifty_1d', 'pcr_vs_nifty_3d', etc.
    correlation     DOUBLE PRECISION,       -- -1.0 to +1.0
    p_value         DOUBLE PRECISION,       -- statistical significance
    sample_size     INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_correlation_date_pair
    ON correlation_matrix (date DESC, pair_name);

-- ============================================================
-- 9. SIGNAL ACCURACY LOG — Per-signal hit rates for dynamic weighting
-- Tracks which signals are actually predictive vs noise
-- Written by: prediction_tracker.py
-- ============================================================

CREATE TABLE IF NOT EXISTS signal_accuracy_log (
    id              SERIAL PRIMARY KEY,
    date            DATE NOT NULL,
    signal_name     TEXT NOT NULL,          -- 'fii_streak_bearish', 'pcr_contrarian_bull', etc.
    signal_value    DOUBLE PRECISION,       -- the signal's raw value when it fired
    predicted_direction TEXT,               -- 'UP', 'DOWN', 'FLAT'
    actual_direction    TEXT,               -- 'UP', 'DOWN', 'FLAT'
    hit             BOOLEAN,               -- predicted == actual
    nifty_return    DOUBLE PRECISION,       -- actual 1D return %
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_signal_accuracy_name
    ON signal_accuracy_log (signal_name, date DESC);

-- ============================================================
-- 10. DIVERGENCE LOG — Active cross-asset divergences
-- Written by: context_engine.py detect_divergences()
-- ============================================================

CREATE TABLE IF NOT EXISTS divergence_log (
    id              SERIAL PRIMARY KEY,
    date            DATE NOT NULL,
    divergence_type TEXT NOT NULL,          -- 'gold_dollar_both_rising', 'nifty_up_breadth_down', etc.
    severity        TEXT,                   -- 'HIGH', 'MEDIUM', 'LOW'
    description     TEXT,
    asset_1         TEXT,
    asset_1_change  DOUBLE PRECISION,
    asset_2         TEXT,
    asset_2_change  DOUBLE PRECISION,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_divergence_date
    ON divergence_log (date DESC);


-- ============================================================
-- VERIFICATION: Check all 10 tables exist
-- ============================================================

SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN (
    'valuation_history', 'market_breadth_history',
    'daily_predictions', 'prediction_outcomes',
    'macro_anchor_snapshots', 'fii_institution_tracker',
    'daily_market_snapshot', 'correlation_matrix',
    'signal_accuracy_log', 'divergence_log'
);


-- ============================================================
-- 11. CFTC POSITIONING HISTORY — Weekly USD futures positioning
-- Written by: cftc_fetcher.py
-- Retention: 1 year (52 weeks)
-- ============================================================

CREATE TABLE IF NOT EXISTS cftc_positioning_history (
    date                DATE NOT NULL,
    contract_name       TEXT NOT NULL,
    speculator_net      DOUBLE PRECISION,
    commercial_net      DOUBLE PRECISION,
    open_interest       DOUBLE PRECISION,
    speculator_percentile DOUBLE PRECISION,
    trend               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (date, contract_name)
);

CREATE INDEX IF NOT EXISTS idx_cftc_date ON cftc_positioning_history (date DESC);


-- ============================================================
-- 12. FACTOR SCORES HISTORY — Daily factor attribution
-- Written by: factor_engine.py
-- Retention: 1 year (365 days)
-- ============================================================

CREATE TABLE IF NOT EXISTS factor_scores_history (
    date                DATE PRIMARY KEY,
    momentum_score      DOUBLE PRECISION,
    value_score         DOUBLE PRECISION,
    quality_score       DOUBLE PRECISION,
    size_score          DOUBLE PRECISION,
    dominant_factor     TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_factor_date ON factor_scores_history (date DESC);


-- ============================================================
-- 13. SECTOR RS HISTORY — Daily sector relative strength
-- Written by: sector_rs.py
-- Retention: 1 year (365 days)
-- ============================================================

CREATE TABLE IF NOT EXISTS sector_rs_history (
    date                DATE NOT NULL,
    sector_name         TEXT NOT NULL,
    rs_score            DOUBLE PRECISION,
    rs_1w               DOUBLE PRECISION,
    rs_1m               DOUBLE PRECISION,
    rs_3m               DOUBLE PRECISION,
    rank                INTEGER,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (date, sector_name)
);

CREATE INDEX IF NOT EXISTS idx_sector_rs_date ON sector_rs_history (date DESC);


-- ============================================================
-- 14. EARNINGS SURPRISES — Nifty 50 earnings tracking
-- Written by: earnings_tracker.py
-- Retention: 2 years (730 days)
-- ============================================================

CREATE TABLE IF NOT EXISTS earnings_surprises (
    ticker              TEXT NOT NULL,
    earnings_date       DATE NOT NULL,
    eps_actual          DOUBLE PRECISION,
    eps_estimate        DOUBLE PRECISION,
    surprise_pct        DOUBLE PRECISION,
    stock_move_1d       DOUBLE PRECISION,
    stock_move_5d       DOUBLE PRECISION,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (ticker, earnings_date)
);

CREATE INDEX IF NOT EXISTS idx_earnings_date ON earnings_surprises (earnings_date DESC);


-- ============================================================
-- 15. MARKET INTERNALS HISTORY — Daily composite health score
-- Written by: market_internals.py
-- Retention: 1 year (365 days)
-- ============================================================

CREATE TABLE IF NOT EXISTS market_internals_history (
    date                DATE PRIMARY KEY,
    composite_score     DOUBLE PRECISION,
    ad_score            DOUBLE PRECISION,
    high_low_score      DOUBLE PRECISION,
    volume_score        DOUBLE PRECISION,
    ma_score            DOUBLE PRECISION,
    mcclellan_score     DOUBLE PRECISION,
    classification      TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_internals_date ON market_internals_history (date DESC);


-- ============================================================
-- VERIFICATION: Check all 15 tables exist
-- ============================================================

SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN (
    'valuation_history', 'market_breadth_history',
    'daily_predictions', 'prediction_outcomes',
    'macro_anchor_snapshots', 'fii_institution_tracker',
    'daily_market_snapshot', 'correlation_matrix',
    'signal_accuracy_log', 'divergence_log',
    'cftc_positioning_history', 'factor_scores_history',
    'sector_rs_history', 'earnings_surprises', 'market_internals_history'
);
