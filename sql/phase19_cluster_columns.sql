-- Phase 19: Add cluster scores to daily_market_snapshot
-- Run this in Supabase SQL editor before running bootstrap_master_signal.py

ALTER TABLE daily_market_snapshot
    ADD COLUMN IF NOT EXISTS structural_score DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS sentiment_score DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS cluster_gap DOUBLE PRECISION;
