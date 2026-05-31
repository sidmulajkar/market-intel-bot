-- ============================================================
-- Market Intel Bot: Deploy 3 missing tables
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor)
-- ============================================================

-- 1. STRESS HISTORY (T4.1)
CREATE TABLE IF NOT EXISTS stress_history (
    trade_date    DATE PRIMARY KEY,
    stress_score  DOUBLE PRECISION NOT NULL,
    raw_stress    DOUBLE PRECISION,
    top_driver_1  TEXT,
    top_driver_2  TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_stress_history_date
    ON stress_history (trade_date DESC);

-- 2. CORPORATE ACTIONS (T3.2)
CREATE TABLE IF NOT EXISTS corporate_actions (
    symbol       TEXT NOT NULL,
    ex_date      TEXT NOT NULL,
    action_type  TEXT NOT NULL,
    detail       TEXT,
    fetched_date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (symbol, ex_date, action_type)
);
CREATE INDEX IF NOT EXISTS idx_corp_actions_ex_date
    ON corporate_actions (ex_date DESC);

-- 3. CLONE HISTORY (T4.2)
CREATE TABLE IF NOT EXISTS clone_history (
    trade_date      DATE NOT NULL,
    clone_date      DATE NOT NULL,
    distance        DOUBLE PRECISION,
    scenario_label  TEXT,
    nifty_30d_fwd   DOUBLE PRECISION,
    nifty_60d_fwd   DOUBLE PRECISION,
    max_dd          DOUBLE PRECISION,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (trade_date, clone_date)
);
CREATE INDEX IF NOT EXISTS idx_clone_history_trade_date
    ON clone_history (trade_date DESC);

-- Verify all 3 exist
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN ('stress_history', 'corporate_actions', 'clone_history');
