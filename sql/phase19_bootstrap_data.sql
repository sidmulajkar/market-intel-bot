-- Phase 19: Bootstrap Master Signal Historical Data
-- Generated: 2026-05-20T16:40:54.099547
--
-- This SQL contains:
--   1. Column migration (idempotent)
--   2. Today's REAL snapshot (2026-05-20)
--   3. Backfilled cluster scores for 1 existing rows
--
-- Run in Supabase SQL editor, OR:
-- python bootstrap_master_signal.py --insert

-- Step 1: Ensure columns exist
ALTER TABLE daily_market_snapshot
    ADD COLUMN IF NOT EXISTS structural_score DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS sentiment_score DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS cluster_gap DOUBLE PRECISION;

-- Step 2: Today's REAL snapshot (from live data fetch)
INSERT INTO daily_market_snapshot (date, india_vix, cboe_vix, usdinr, brent, gold, dxy, us_10y, copper, fii_net, dii_net, bull_bear_score, structural_score, sentiment_score, cluster_gap)
VALUES ('2026-05-20', 18.44, 17.96, 96.81, 108.35, 4496.8, 99.35, 4.67, 6.25, -2442.9, 3862.08, 50, 62, 39, 23)
ON CONFLICT (date) DO UPDATE SET
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    usdinr = EXCLUDED.usdinr,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    copper = EXCLUDED.copper,
    fii_net = EXCLUDED.fii_net,
    dii_net = EXCLUDED.dii_net,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap;

-- Step 3: Backfill cluster scores for 1 existing rows
-- These rows already have bull_bear_score; adding structural/sentiment/gap
INSERT INTO daily_market_snapshot (date, bull_bear_score, structural_score, sentiment_score, cluster_gap)
VALUES ('2026-05-17', 45, 47, 49, 2)
ON CONFLICT (date) DO UPDATE SET
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap;

-- Verify
SELECT date, bull_bear_score, structural_score, sentiment_score, cluster_gap
FROM daily_market_snapshot
ORDER BY date DESC LIMIT 35;