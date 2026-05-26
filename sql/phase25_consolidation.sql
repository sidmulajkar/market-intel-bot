-- Phase 25: MarketState + Forecast + Analytics Ledger
-- Consolidates 16 scattered tables into 3 core tables.
-- Run these in Supabase SQL editor.

-- ── 1. market_state ──────────────────────────────────────────────────────────
-- Single JSONB row per day — entire MarketState object.
-- Replaces: market_snapshots, daily_market_snapshot, options_snapshots,
--           valuation_history, market_breadth_history, fii_dii_flows (for ML purposes)

CREATE TABLE IF NOT EXISTS market_state (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    trade_date DATE NOT NULL UNIQUE,
    state JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for date range queries
CREATE INDEX IF NOT EXISTS idx_market_state_date ON market_state (trade_date DESC);

-- RLS
ALTER TABLE market_state ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all read" ON market_state FOR SELECT USING (true);
CREATE POLICY "Allow all write" ON market_state FOR ALL USING (true);

-- ── 2. forecast_log ─────────────────────────────────────────────────────────
-- Structured AI forecasts with Brier scoring.
-- Replaces: daily_predictions, prediction_outcomes

CREATE TABLE IF NOT EXISTS forecast_log (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    trade_date DATE NOT NULL,
    forecast JSONB NOT NULL,                    -- {direction, probability_up, confidence, signals}
    outcome JSONB,                              -- {actual_return, brier_score, label, direction_correct}
    created_at TIMESTAMPTZ DEFAULT NOW(),
    scored_at TIMESTAMPTZ,
    UNIQUE(trade_date)
);

CREATE INDEX IF NOT EXISTS idx_forecast_date ON forecast_log (trade_date DESC);

ALTER TABLE forecast_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all read" ON forecast_log FOR SELECT USING (true);
CREATE POLICY "Allow all write" ON forecast_log FOR ALL USING (true);

-- ── 3. analytics_ledger ─────────────────────────────────────────────────────
-- Merges: signal_accuracy_log, divergence_log, correlation_matrix, prediction_outcomes
-- JSONB with category tag for efficient querying.

CREATE TABLE IF NOT EXISTS analytics_ledger (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    date DATE NOT NULL,
    category TEXT NOT NULL,                     -- 'signal_accuracy', 'divergence', 'correlation', 'prediction_outcome'
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analytics_date ON analytics_ledger (date DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_category ON analytics_ledger (category);
CREATE INDEX IF NOT EXISTS idx_analytics_date_category ON analytics_ledger (date DESC, category);

ALTER TABLE analytics_ledger ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all read" ON analytics_ledger FOR SELECT USING (true);
CREATE POLICY "Allow all write" ON analytics_ledger FOR ALL USING (true);

-- ── 4. shareholding_snapshots ───────────────────────────────────────────────
-- Promoter/FII/DII/Public % with QoQ comparison.
-- UNIQUE(symbol, quarter) enables upsert without duplicate key errors.

CREATE TABLE IF NOT EXISTS shareholding_snapshots (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    symbol TEXT NOT NULL,
    quarter TEXT NOT NULL,
    data JSONB NOT NULL,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE(symbol, quarter)
);

ALTER TABLE shareholding_snapshots ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all read" ON shareholding_snapshots FOR SELECT USING (true);
CREATE POLICY "Allow all write" ON shareholding_snapshots FOR ALL USING (true);
