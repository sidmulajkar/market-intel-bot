-- Phase 33 Patch 5: Schema consolidation
-- Migrate daily_market_snapshot → market_state JSONB (state.daily_snapshot)
-- The flat table is deprecated. New code reads/writes market_state JSONB.
--
-- Run this in Supabase SQL Editor AFTER deploying new code.

-- ── 1. Deprecate daily_market_snapshot ──────────────────────────────────────
-- Keep the table for 30 days as safety net. New code no longer references it.
-- After verifying market_state JSONB contains all snapshot data, drop it:
--   DROP TABLE IF EXISTS daily_market_snapshot;

COMMENT ON TABLE daily_market_snapshot IS 'DEPRECATED 2026-05-28 — use market_state.state.daily_snapshot JSONB instead';

-- ── 2. Ensure market_state has proper SERIAL PK (some schemas use BIGINT IDENTITY)
-- Both work — no migration needed if table already exists from phase25_consolidation.sql

-- ── 3. Verification: confirm market_state has daily_snapshot data ───────────
-- After new code runs for 1 day, check:
--   SELECT trade_date, state->'daily_snapshot'->>'nifty_close' as nifty
--   FROM market_state
--   WHERE state ? 'daily_snapshot'
--   ORDER BY trade_date DESC LIMIT 5;
