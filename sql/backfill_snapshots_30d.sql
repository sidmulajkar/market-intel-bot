-- Backfill: 30 days of daily_market_snapshot with REAL price data
-- Generated: 2026-05-20T18:29:02.961695
-- 261 days, all data from yfinance
-- Scores are APPROXIMATE (from prices only) — daily cron will replace with real

ALTER TABLE daily_market_snapshot
    ADD COLUMN IF NOT EXISTS structural_score DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS sentiment_score DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS cluster_gap DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS data_quality TEXT DEFAULT 'real';

INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-05-20', 24683.9, 17.39, 18.09, 65.38, 3280.3, 100.12, 4.48, 85.37, 4.62, 57, 54, 54, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-05-21', 24813.45, 17.55, 20.87, 64.91, 3309.3, 99.56, 4.6, 85.54, 4.64, 0.52, 59, 56, 54, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-05-22', 24609.7, 17.26, 20.28, 64.44, 3292.3, 99.96, 4.55, 85.6, 4.65, -0.82, 55, 52, 52, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-05-23', 24853.15, 17.28, 22.29, 64.78, 3363.6, 99.11, 4.51, 85.97, 4.81, 0.99, 62, 59, 56, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, dxy, usdinr, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-05-26', 25001.15, 18.02, 98.93, 85.2, 0.6, 60, 57, 54, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    dxy = EXCLUDED.dxy,
    usdinr = EXCLUDED.usdinr,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-05-27', 24826.2, 18.54, 18.96, 64.09, 3299.1, 99.52, 4.43, 85.16, 4.71, -0.7, 55, 51, 50, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-05-28', 24752.45, 18.02, 19.31, 64.9, 3293.6, 99.88, 4.48, 85.36, 4.64, -0.3, 56, 53, 52, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-05-29', 24833.6, 16.42, 19.18, 64.15, 3317.1, 99.28, 4.42, 85.39, 4.65, 0.33, 61, 58, 56, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-05-30', 24750.7, 16.08, 18.57, 63.9, 3288.9, 99.33, 4.42, 85.36, 4.65, -0.33, 59, 56, 55, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-06-02', 24716.6, 17.16, 18.36, 64.63, 3370.6, 98.7, 4.46, 85.52, 4.83, -0.14, 60, 56, 54, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-06-03', 24542.5, 16.56, 17.69, 65.63, 3350.2, 99.25, 4.46, 85.36, 4.81, -0.7, 58, 54, 54, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-06-04', 24620.2, 15.75, 17.61, 64.86, 3373.5, 98.79, 4.36, 85.71, 4.86, 0.32, 62, 59, 57, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-06-05', 24750.9, 15.08, 18.48, 65.34, 3350.7, 98.74, 4.39, 85.9, 4.91, 0.53, 64, 61, 58, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-06-06', 25003.05, 14.63, 16.77, 66.47, 3322.7, 99.19, 4.51, 85.88, 4.83, 1.02, 65, 62, 60, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-06-09', 25103.2, 14.69, 17.16, 67.04, 3332.1, 98.94, 4.48, 85.79, 4.91, 0.4, 63, 61, 59, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-06-10', 25104.25, 14.02, 16.95, 66.87, 3320.9, 99.05, 4.47, 85.76, 4.88, 0.0, 63, 60, 59, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-06-11', 25141.4, 13.67, 17.26, 69.77, 3321.3, 98.63, 4.41, 85.65, 4.8, 0.15, 65, 62, 60, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-06-12', 24888.2, 14.02, 18.02, 69.36, 3380.9, 97.92, 4.36, 85.47, 4.82, -1.01, 63, 59, 57, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-06-13', 24718.6, 15.08, 20.82, 74.23, 3431.2, 98.18, 4.42, 85.69, 4.8, -0.68, 62, 58, 56, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-06-16', 24946.5, 14.84, 19.11, 73.23, 3396.4, 98.0, 4.45, 86.25, 4.83, 0.92, 66, 63, 60, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-06-17', 24853.4, 14.4, 21.6, 76.45, 3386.6, 98.82, 4.39, 86.1, 4.8, -0.37, 62, 59, 58, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-06-18', 24812.05, 14.28, 20.14, 76.7, 3389.8, 98.91, 4.4, 86.36, 4.84, -0.17, 63, 60, 58, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, usdinr, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-06-19', 24793.25, 14.26, 86.61, -0.08, 61, 58, 59, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    usdinr = EXCLUDED.usdinr,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-06-20', 25112.4, 13.67, 20.62, 77.01, 3368.1, 98.71, 4.38, 86.58, 4.83, 1.29, 67, 65, 62, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-06-23', 24971.9, 14.05, 19.83, 71.48, 3377.7, 98.42, 4.32, 86.58, 4.84, -0.56, 63, 59, 58, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-06-24', 25044.35, 13.64, 17.48, 67.14, 3317.4, 97.86, 4.29, 86.23, 4.87, 0.29, 67, 63, 60, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-06-25', 25244.75, 12.96, 16.76, 67.68, 3327.1, 97.68, 4.29, 85.9, 4.91, 0.8, 69, 66, 62, 4, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-06-26', 25549.0, 12.59, 16.59, 67.73, 3333.5, 97.15, 4.25, 86.01, 5.07, 1.21, 72, 69, 64, 5, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-06-27', 25637.8, 12.39, 16.32, 67.77, 3273.7, 97.4, 4.28, 85.67, 5.07, 0.35, 69, 66, 63, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-06-30', 25517.05, 12.79, 16.73, 67.61, 3294.4, 96.88, 4.23, 85.46, 5.03, -0.47, 68, 64, 60, 4, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-07-01', 25541.8, 12.53, 16.83, 67.11, 3336.7, 96.82, 4.25, 85.71, 5.05, 0.1, 69, 66, 62, 4, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-07-02', 25453.4, 12.45, 16.64, 69.11, 3348.0, 96.78, 4.29, 85.64, 5.15, -0.35, 69, 65, 61, 4, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-07-03', 25405.3, 12.39, 16.38, 68.8, 3331.6, 97.18, 4.35, 85.69, 5.1, -0.19, 68, 65, 61, 4, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, brent, gold, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-07-04', 25461.0, 12.32, 68.29, 3332.5, 85.32, 5.02, 0.22, 64, 62, 62, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-07-07', 25461.3, 12.56, 17.79, 69.58, 3332.2, 97.48, 4.39, 85.5, 4.98, 0.0, 68, 65, 62, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-07-08', 25522.5, 12.2, 16.81, 70.15, 3307.0, 97.51, 4.41, 85.89, 5.64, 0.24, 69, 66, 63, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-07-09', 25476.1, 11.94, 15.94, 70.19, 3311.6, 97.47, 4.34, 85.71, 5.44, -0.18, 68, 65, 62, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-07-10', 25355.25, 11.67, 15.78, 68.64, 3317.4, 97.65, 4.35, 85.71, 5.55, -0.47, 67, 64, 62, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-07-11', 25149.85, 11.82, 16.4, 70.36, 3356.0, 97.85, 4.42, 85.73, 5.56, -0.81, 66, 63, 61, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-07-14', 25082.3, 11.98, 17.2, 69.21, 3351.5, 98.08, 4.43, 85.82, 5.51, -0.27, 67, 64, 62, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-07-15', 25195.8, 11.48, 17.38, 68.71, 3329.8, 98.62, 4.49, 85.97, 5.55, 0.45, 68, 66, 64, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-07-16', 25212.05, 11.24, 17.16, 68.52, 3352.5, 98.39, 4.45, 85.99, 5.5, 0.06, 68, 65, 64, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-07-17', 25111.45, 11.24, 16.52, 69.52, 3340.1, 98.73, 4.46, 85.89, 5.49, -0.4, 66, 63, 63, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-07-18', 24968.4, 11.39, 16.41, 69.28, 3353.0, 98.48, 4.43, 86.05, 5.58, -0.57, 66, 63, 62, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-07-21', 25090.7, 11.2, 16.65, 69.21, 3401.9, 97.85, 4.37, 86.15, 5.61, 0.49, 70, 67, 65, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-07-22', 25060.9, 10.75, 16.5, 68.59, 3439.2, 97.39, 4.34, 86.2, 5.7, -0.12, 70, 67, 64, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-07-23', 25219.9, 10.52, 15.37, 68.51, 3394.1, 97.21, 4.39, 86.34, 5.8, 0.63, 72, 70, 66, 4, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-07-24', 25062.1, 10.72, 15.39, 69.18, 3371.0, 97.38, 4.41, 86.4, 5.78, -0.63, 69, 65, 63, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-07-25', 24837.0, 11.28, 14.93, 68.44, 3334.0, 97.65, 4.39, 86.43, 5.76, -0.9, 67, 63, 62, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-07-28', 24680.9, 12.06, 15.03, 70.04, 3309.1, 98.66, 4.42, 86.51, 5.59, -0.63, 65, 62, 61, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-07-29', 24821.1, 11.53, 15.98, 72.51, 3323.4, 98.91, 4.33, 86.78, 5.6, 0.57, 68, 65, 64, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-07-30', 24855.05, 11.21, 15.48, 73.24, 3295.8, 99.94, 4.38, 87.06, 5.57, 0.14, 65, 63, 64, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-07-31', 24768.35, 11.54, 16.72, 72.53, 3293.2, 100.03, 4.36, 87.71, 4.33, -0.35, 63, 61, 63, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-08-01', 24565.35, 11.98, 20.38, 69.67, 3347.7, 98.69, 4.22, 87.49, 4.41, -0.82, 64, 61, 61, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-08-04', 24722.75, 11.97, 17.52, 68.76, 3374.4, 98.78, 4.2, 87.25, 4.41, 0.64, 68, 65, 64, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-08-05', 24649.55, 11.71, 17.85, 67.64, 3381.9, 98.78, 4.2, 87.89, 4.36, -0.3, 66, 63, 62, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-08-06', 24574.2, 11.96, 16.77, 66.89, 3380.0, 98.18, 4.22, 87.72, 4.39, -0.31, 66, 63, 62, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-08-07', 24596.15, 11.69, 16.57, 66.43, 3400.3, 98.4, 4.24, 87.76, 4.38, 0.09, 67, 65, 63, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-08-08', 24363.3, 12.03, 15.15, 66.59, 3439.1, 98.18, 4.28, 87.43, 4.46, -0.95, 65, 61, 61, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-08-11', 24585.05, 12.22, 16.25, 66.63, 3353.1, 98.52, 4.27, 87.49, 4.42, 0.91, 68, 66, 64, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-08-12', 24487.4, 12.23, 14.73, 66.12, 3348.9, 98.1, 4.29, 87.66, 4.51, -0.4, 66, 63, 61, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-08-13', 24619.35, 12.14, 14.49, 65.63, 3358.7, 97.84, 4.24, 87.6, 4.48, 0.54, 69, 66, 63, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-08-14', 24631.3, 12.36, 14.83, 66.84, 3335.2, 98.25, 4.29, 87.45, 4.46, 0.05, 67, 64, 62, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-08-15', 15.09, 65.85, 3336.0, 97.85, 4.33, 87.69, 4.48, 64, 61, 58, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-08-18', 24876.95, 12.34, 14.99, 66.6, 3331.7, 98.17, 4.34, 87.51, 4.46, 67, 64, 62, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-08-19', 24980.65, 11.79, 15.57, 65.79, 3313.4, 98.27, 4.3, 87.3, 4.41, 0.42, 68, 66, 64, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-08-20', 25050.55, 11.79, 15.69, 66.84, 3343.4, 98.22, 4.3, 87.08, 4.43, 0.28, 68, 65, 63, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-08-21', 25083.75, 11.37, 16.6, 67.67, 3336.9, 98.62, 4.33, 87.02, 4.43, 0.13, 67, 65, 64, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-08-22', 24870.1, 11.73, 14.22, 67.73, 3374.4, 97.72, 4.26, 87.29, 4.45, -0.85, 66, 63, 61, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-08-25', 24967.75, 11.76, 14.79, 68.8, 3373.8, 98.43, 4.28, 87.33, 4.47, 0.39, 68, 65, 64, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-08-26', 24712.05, 12.19, 14.62, 67.22, 3388.6, 98.23, 4.26, 87.61, 4.45, -1.02, 64, 61, 60, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-08-27', 14.85, 68.05, 3404.6, 98.23, 4.24, 87.6, 4.41, 64, 60, 58, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-08-28', 24500.9, 12.18, 14.43, 68.62, 3431.8, 97.81, 4.21, 87.66, 4.46, 68, 65, 62, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-08-29', 24426.85, 11.75, 15.36, 68.12, 3473.7, 97.77, 4.23, 87.59, 4.52, -0.3, 68, 64, 62, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, usdinr, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-09-01', 24625.05, 11.29, 88.17, 0.81, 66, 65, 65, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    usdinr = EXCLUDED.usdinr,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-09-02', 24579.6, 11.4, 17.17, 69.14, 3549.4, 98.4, 4.28, 88.0, 4.57, -0.18, 67, 64, 63, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-09-03', 24715.05, 10.93, 16.35, 67.6, 3593.2, 98.14, 4.21, 88.0, 4.56, 0.55, 70, 67, 65, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-09-04', 24734.3, 10.85, 15.3, 66.99, 3565.8, 98.35, 4.18, 88.07, 4.49, 0.08, 68, 66, 65, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-09-05', 24741.0, 10.78, 15.18, 65.5, 3613.2, 97.77, 4.09, 88.19, 4.48, 0.03, 69, 67, 65, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-09-08', 24773.15, 10.84, 15.11, 66.02, 3638.1, 97.45, 4.05, 88.19, 4.49, 0.13, 70, 67, 65, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-09-09', 24868.6, 10.69, 15.04, 66.39, 3643.3, 97.79, 4.07, 87.98, 4.5, 0.39, 70, 68, 65, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-09-10', 24973.1, 10.54, 15.35, 67.49, 3643.6, 97.78, 4.03, 88.22, 4.55, 0.42, 71, 68, 66, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-09-11', 25005.5, 10.36, 14.71, 66.37, 3636.9, 97.54, 4.01, 88.05, 4.59, 0.13, 71, 68, 65, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-09-12', 25114.0, 10.12, 14.76, 66.99, 3649.4, 97.55, 4.06, 88.27, 4.59, 0.43, 72, 69, 66, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-09-15', 25069.2, 10.4, 15.69, 67.44, 3682.2, 97.3, 4.03, 88.28, 4.66, -0.18, 70, 67, 65, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-09-16', 25239.1, 10.27, 16.36, 68.47, 3688.9, 96.63, 4.03, 88.12, 4.63, 0.68, 74, 71, 67, 4, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-09-17', 25330.25, 10.25, 15.72, 67.95, 3681.8, 96.87, 4.08, 87.88, 4.57, 0.36, 73, 70, 66, 4, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-09-18', 25423.6, 9.89, 15.7, 67.44, 3643.7, 97.35, 4.1, 87.91, 4.54, 0.37, 72, 69, 67, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-09-19', 25327.05, 9.97, 15.45, 66.68, 3671.5, 97.64, 4.14, 88.21, 4.57, -0.38, 70, 67, 65, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-09-22', 25202.35, 10.56, 16.1, 66.57, 3740.7, 97.33, 4.14, 88.1, 4.57, -0.49, 69, 66, 64, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-09-23', 25169.5, 10.63, 16.64, 67.63, 3780.6, 97.26, 4.12, 88.3, 4.58, -0.13, 70, 67, 65, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-09-24', 25056.9, 10.52, 16.18, 69.31, 3732.1, 97.87, 4.15, 88.81, 4.75, -0.45, 68, 65, 64, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-09-25', 24890.85, 10.78, 16.74, 69.42, 3736.9, 98.55, 4.17, 88.78, 4.7, -0.66, 66, 63, 63, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-09-26', 24654.7, 11.43, 15.29, 70.13, 3775.3, 98.15, 4.19, 88.77, 4.72, -0.95, 65, 62, 62, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-09-29', 24634.9, 11.37, 16.12, 67.97, 3820.9, 97.91, 4.14, 88.68, 4.84, -0.08, 68, 65, 63, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-09-30', 24611.1, 11.07, 16.28, 67.02, 3840.8, 97.77, 4.15, 88.7, 4.8, -0.1, 69, 66, 64, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-10-01', 24836.3, 10.29, 16.29, 65.35, 3867.5, 97.71, 4.11, 88.84, 4.83, 0.92, 72, 70, 67, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-10-02', 16.63, 64.11, 3839.7, 97.85, 4.09, 88.68, 4.9, 64, 61, 58, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-10-03', 24894.25, 10.06, 16.65, 64.53, 3880.8, 97.72, 4.12, 88.72, 5.06, 70, 68, 66, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-10-06', 25077.65, 10.19, 16.37, 65.47, 3948.5, 98.11, 4.16, 88.74, 4.99, 0.74, 71, 69, 67, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-10-07', 25108.3, 10.05, 17.24, 65.45, 3976.6, 98.58, 4.13, 88.72, 5.05, 0.12, 69, 67, 66, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-10-08', 25046.15, 10.31, 16.3, 66.25, 4043.3, 98.85, 4.13, 88.74, 5.05, -0.25, 67, 65, 65, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-10-09', 25181.8, 10.12, 16.43, 65.22, 3946.3, 99.54, 4.15, 88.78, 5.08, 0.54, 68, 66, 67, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-10-10', 25285.35, 10.1, 21.66, 62.73, 3975.9, 98.98, 4.05, 88.87, 4.85, 0.41, 69, 67, 66, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-10-13', 25227.35, 11.01, 19.03, 63.32, 4108.6, 99.27, 4.05, 88.76, 5.1, -0.23, 66, 63, 64, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-10-14', 25145.5, 11.16, 20.81, 62.39, 4138.7, 99.05, 4.02, 88.67, 4.98, -0.32, 66, 63, 63, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-10-15', 25323.55, 10.53, 20.64, 61.91, 4176.9, 98.79, 4.05, 88.78, 4.97, 0.71, 69, 67, 66, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-10-16', 25585.3, 10.87, 25.31, 61.06, 4280.2, 98.39, 3.98, 87.81, 4.96, 1.03, 71, 69, 66, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-10-17', 25709.85, 11.63, 20.78, 61.29, 4189.9, 98.43, 4.01, 87.99, 4.93, 0.49, 68, 66, 64, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-10-20', 25843.15, 11.36, 18.23, 61.01, 4336.4, 98.59, 3.99, 88.0, 5.0, 0.52, 68, 66, 65, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-10-21', 25868.6, 11.3, 17.87, 61.32, 4087.7, 98.93, 3.96, 87.88, 4.93, 0.1, 67, 64, 64, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-10-22', 18.6, 62.59, 4044.4, 98.9, 3.95, 88.0, 4.96, 62, 59, 58, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-10-23', 25891.4, 11.73, 17.3, 65.99, 4125.5, 98.94, 3.99, 87.74, 5.08, 66, 63, 63, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-10-24', 25795.15, 11.59, 16.37, 65.94, 4118.4, 98.95, 4.0, 87.78, 5.09, -0.37, 65, 63, 62, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-10-27', 25966.05, 11.86, 15.79, 65.62, 4001.9, 98.78, 4.0, 87.83, 5.14, 0.66, 68, 65, 64, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-10-28', 25936.2, 11.95, 16.42, 64.4, 3966.2, 98.69, 3.98, 88.22, 5.14, -0.11, 66, 63, 62, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-10-29', 26053.9, 11.97, 16.92, 64.92, 3983.7, 99.22, 4.06, 88.23, 5.23, 0.45, 66, 64, 63, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-10-30', 25877.85, 12.07, 16.91, 65.0, 4001.3, 99.53, 4.09, 88.35, 5.08, -0.68, 63, 60, 61, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-10-31', 25722.1, 12.15, 17.44, 65.07, 3982.2, 99.8, 4.1, 88.63, 5.07, -0.6, 62, 60, 61, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-11-03', 25763.35, 12.67, 17.17, 64.89, 4000.3, 99.87, 4.11, 88.78, 5.05, 0.16, 63, 61, 62, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-11-04', 25597.65, 12.65, 19.0, 64.44, 3947.7, 100.22, 4.09, 88.72, 4.93, -0.64, 61, 58, 60, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-11-05', 18.01, 63.52, 3980.3, 100.2, 4.16, 88.73, 4.96, 60, 57, 58, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-11-06', 25509.7, 12.41, 19.5, 63.38, 3979.9, 99.73, 4.09, 88.56, 4.95, 64, 61, 62, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-11-07', 25492.3, 12.56, 19.08, 63.63, 3999.4, 99.6, 4.09, 88.67, 4.94, -0.07, 63, 61, 61, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-11-10', 25574.35, 12.3, 17.6, 64.06, 4111.8, 99.62, 4.11, 88.66, 5.09, 0.32, 65, 63, 63, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-11-11', 25694.95, 12.49, 17.28, 65.16, 4106.8, 99.46, 4.12, 88.71, 5.05, 0.47, 65, 63, 63, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-11-12', 25875.8, 12.11, 17.51, 62.71, 4204.4, 99.48, 4.07, 88.47, 5.09, 0.7, 66, 64, 64, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-11-13', 25879.15, 12.16, 20.0, 63.01, 4186.9, 99.18, 4.11, 88.59, 5.09, 0.01, 65, 63, 62, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-11-14', 25910.05, 11.94, 19.83, 64.39, 4087.6, 99.27, 4.15, 88.82, 5.05, 0.12, 65, 63, 63, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-11-17', 26013.45, 11.79, 22.38, 64.2, 4068.3, 99.59, 4.13, 88.68, 5.0, 0.4, 66, 64, 64, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-11-18', 25910.05, 12.1, 24.69, 64.89, 4061.3, 99.55, 4.12, 88.64, 4.96, -0.4, 63, 61, 62, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-11-19', 26052.65, 11.97, 23.66, 63.51, 4077.7, 100.23, 4.13, 88.56, 5.01, 0.55, 64, 63, 64, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-11-20', 26192.15, 12.14, 26.42, 63.38, 4056.5, 100.16, 4.11, 88.49, 4.96, 0.54, 64, 63, 63, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-11-21', 26068.15, 13.63, 23.43, 62.56, 4076.7, 100.18, 4.06, 88.69, 5.01, -0.47, 60, 58, 59, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-11-24', 25959.5, 13.24, 20.52, 63.37, 4091.9, 100.14, 4.04, 89.63, 4.96, -0.42, 61, 58, 60, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-11-25', 25884.8, 12.24, 18.56, 62.48, 4139.2, 99.66, 4.0, 89.15, 5.0, -0.29, 63, 61, 62, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-11-26', 26205.3, 11.97, 17.19, 63.13, 4165.2, 99.6, 4.0, 89.15, 5.1, 1.24, 67, 66, 65, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, usdinr, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-11-27', 26215.55, 11.79, 89.16, 0.04, 64, 62, 63, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    usdinr = EXCLUDED.usdinr,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-11-28', 26202.95, 11.62, 16.35, 63.2, 4218.3, 99.46, 4.02, 89.36, 5.19, -0.05, 65, 63, 63, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-12-01', 26175.75, 11.63, 17.24, 63.17, 4239.3, 99.41, 4.1, 89.35, 5.22, -0.1, 65, 63, 63, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-12-02', 26032.2, 11.23, 16.59, 62.45, 4186.6, 99.36, 4.09, 89.61, 5.16, -0.55, 64, 62, 63, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-12-03', 25986.0, 11.21, 16.08, 62.67, 4199.3, 98.85, 4.06, 89.92, 5.31, -0.18, 66, 64, 63, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-12-04', 26033.75, 10.82, 15.78, 63.26, 4211.8, 98.99, 4.11, 90.17, 5.29, 0.18, 67, 65, 65, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-12-05', 26186.45, 10.32, 15.41, 63.75, 4212.9, 98.99, 4.14, 89.84, 5.38, 0.59, 69, 67, 66, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-12-08', 25960.55, 11.13, 16.66, 62.49, 4187.2, 99.09, 4.17, 89.94, 5.36, -0.86, 64, 61, 62, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-12-09', 25839.65, 10.95, 16.93, 61.94, 4206.7, 99.22, 4.19, 90.13, 5.24, -0.47, 65, 63, 63, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-12-10', 25758.0, 10.91, 15.77, 62.21, 4196.4, 98.79, 4.16, 89.92, 5.28, -0.32, 66, 64, 64, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-12-11', 25898.55, 10.4, 14.85, 61.28, 4285.5, 98.35, 4.14, 89.79, 5.43, 0.55, 70, 68, 66, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-12-12', 26046.95, 10.11, 15.74, 61.12, 4300.1, 98.4, 4.19, 90.25, 5.28, 0.57, 70, 68, 67, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-12-15', 26027.3, 10.25, 16.5, 60.56, 4306.7, 98.15, 4.18, 90.58, 5.34, -0.08, 69, 66, 65, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-12-16', 25860.1, 10.06, 16.48, 58.92, 4304.5, 98.15, 4.15, 90.78, 5.29, -0.64, 68, 65, 64, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-12-17', 25818.55, 9.84, 17.62, 59.68, 4347.5, 98.37, 4.15, 90.95, 5.36, -0.16, 69, 66, 66, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-12-18', 25815.55, 9.71, 16.87, 59.82, 4339.5, 98.43, 4.12, 90.41, 5.37, -0.01, 69, 67, 66, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-12-19', 25966.4, 9.52, 14.91, 60.47, 4361.4, 98.6, 4.15, 90.26, 5.44, 0.58, 71, 69, 68, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-12-22', 26172.4, 9.68, 14.08, 62.07, 4444.6, 98.29, 4.17, 89.57, 5.44, 0.79, 72, 70, 68, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-12-23', 26177.15, 9.38, 14.0, 62.38, 4482.8, 97.94, 4.17, 89.6, 5.48, 0.02, 71, 68, 67, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-12-24', 26142.1, 9.19, 13.47, 62.24, 4480.6, 97.98, 4.14, 89.51, 5.5, -0.13, 70, 68, 67, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-12-26', 26042.3, 9.15, 13.6, 60.64, 4529.1, 98.02, 4.14, 90.11, 5.77, -0.38, 70, 67, 66, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-12-29', 25942.1, 9.72, 14.2, 61.94, 4325.1, 98.04, 4.12, 89.83, 5.49, -0.38, 69, 66, 66, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-12-30', 25938.85, 9.68, 14.33, 61.92, 4370.1, 98.24, 4.13, 89.9, 5.73, -0.01, 70, 67, 66, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2025-12-31', 26129.6, 9.48, 14.95, 60.85, 4325.6, 98.28, 4.16, 89.77, 5.63, 0.74, 72, 70, 68, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-01-01', 26146.55, 0.06, 60, 58, 58, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-01-02', 26328.55, 9.45, 14.51, 60.75, 4314.4, 98.42, 4.19, 89.96, 5.64, 0.7, 71, 69, 68, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-01-05', 26250.3, 10.02, 14.9, 61.76, 4436.9, 98.27, 4.16, 90.01, 5.92, -0.3, 69, 66, 65, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-01-06', 26178.7, 10.02, 14.75, 60.7, 4482.2, 98.58, 4.18, 90.23, 6.01, -0.27, 68, 65, 65, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-01-07', 26140.75, 9.95, 15.38, 59.96, 4449.3, 98.68, 4.14, 90.17, 5.81, -0.14, 68, 66, 66, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-01-08', 25876.85, 10.6, 15.45, 61.99, 4449.7, 98.93, 4.18, 89.86, 5.75, -1.01, 65, 62, 63, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-01-09', 25683.3, 10.93, 14.49, 63.34, 4490.3, 99.13, 4.17, 89.91, 5.86, -0.75, 65, 62, 63, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-01-12', 25790.25, 11.37, 15.12, 63.87, 4604.3, 98.86, 4.19, 90.24, 5.99, 0.42, 68, 65, 64, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-01-13', 25732.3, 11.2, 15.98, 65.47, 4589.2, 99.13, 4.17, 90.13, 5.97, -0.22, 66, 63, 63, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-01-14', 25665.6, 11.32, 16.75, 66.52, 4626.3, 99.13, 4.14, 90.27, 6.01, -0.26, 65, 63, 63, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-01-15', 15.84, 63.76, 4616.3, 99.32, 4.16, 90.18, 5.95, 61, 59, 58, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-01-16', 25694.35, 11.37, 15.86, 64.13, 4588.4, 99.39, 4.23, 90.36, 5.79, 65, 63, 64, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, usdinr, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-01-19', 25585.5, 11.83, 90.7, -0.42, 63, 60, 62, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    usdinr = EXCLUDED.usdinr,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-01-20', 25232.5, 12.73, 20.09, 64.92, 4759.6, 98.64, 4.3, 90.9, 5.77, -1.38, 62, 58, 59, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-01-21', 25157.5, 13.78, 16.9, 65.24, 4831.8, 98.76, 4.25, 91.12, 5.73, -0.3, 63, 60, 59, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-01-22', 25289.9, 13.35, 15.64, 64.06, 4908.8, 98.36, 4.25, 91.54, 5.74, 0.53, 67, 64, 61, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-01-23', 25048.65, 14.19, 16.09, 65.88, 4976.2, 97.6, 4.24, 91.56, 5.91, -0.95, 63, 59, 57, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-01-26', 16.15, 65.59, 5079.7, 97.04, 4.21, 91.5, 5.98, 66, 62, 58, 4, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-01-27', 25175.4, 14.45, 16.35, 67.57, 5079.9, 96.22, 4.22, 91.71, 5.83, 68, 64, 58, 6, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-01-28', 25342.75, 13.53, 16.35, 68.4, 5301.6, 96.45, 4.25, 91.53, 5.89, 0.66, 70, 67, 61, 6, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-01-29', 25418.9, 13.37, 16.88, 70.71, 5318.4, 96.28, 4.23, 92.04, 6.18, 0.3, 70, 66, 61, 5, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-01-30', 25320.65, 13.63, 17.44, 70.69, 4713.9, 96.99, 4.24, 91.78, 5.9, -0.39, 67, 63, 59, 4, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-02-02', 25088.4, 13.87, 16.34, 66.3, 4622.5, 97.61, 4.28, 91.69, 5.8, -0.92, 64, 60, 58, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-02-03', 25727.55, 12.9, 18.0, 67.33, 4903.7, 97.44, 4.27, 90.25, 6.06, 2.55, 74, 72, 66, 6, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-02-04', 25776.0, 12.25, 18.64, 69.46, 4920.4, 97.62, 4.28, 90.42, 5.83, 0.19, 68, 65, 62, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-02-05', 25642.8, 12.17, 21.77, 67.55, 4861.4, 97.82, 4.21, 90.12, 5.8, -0.52, 66, 63, 61, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-02-06', 25693.7, 11.94, 20.37, 68.05, 4951.2, 97.63, 4.21, 90.31, 5.86, 0.2, 69, 66, 63, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-02-09', 25867.3, 12.19, 17.36, 69.04, 5050.9, 96.82, 4.2, 90.59, 5.95, 0.68, 71, 68, 64, 4, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-02-10', 25935.15, 11.67, 17.79, 68.8, 5003.8, 96.8, 4.15, 90.82, 5.9, 0.26, 71, 68, 64, 4, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-02-11', 25953.85, 11.55, 17.65, 69.4, 5071.6, 96.83, 4.17, 90.59, 5.95, 0.07, 71, 67, 63, 4, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-02-12', 25807.2, 11.73, 20.82, 67.52, 4923.7, 96.93, 4.1, 90.74, 5.77, -0.57, 69, 65, 62, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-02-13', 25471.1, 13.29, 20.6, 67.75, 5022.0, 96.88, 4.06, 90.56, 5.79, -1.3, 65, 61, 58, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, usdinr, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-02-16', 25682.75, 13.33, 90.57, 0.83, 64, 62, 62, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    usdinr = EXCLUDED.usdinr,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-02-17', 25725.4, 12.67, 20.29, 67.42, 4882.9, 97.16, 4.05, 90.78, 5.63, 0.17, 69, 65, 62, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-02-18', 25819.35, 12.22, 19.62, 70.35, 4986.5, 97.7, 4.08, 90.63, 5.79, 0.37, 69, 66, 63, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-02-19', 25454.35, 13.46, 20.23, 71.66, 4975.9, 97.93, 4.07, 90.79, 5.73, -1.41, 62, 58, 57, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-02-20', 25571.25, 14.36, 19.09, 71.76, 5059.3, 97.8, 4.09, 91.04, 5.83, 0.46, 66, 63, 59, 4, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-02-23', 25713.0, 14.17, 21.01, 71.49, 5204.7, 97.7, 4.03, 90.73, 5.77, 0.55, 67, 64, 60, 4, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-02-24', 25424.65, 14.15, 19.55, 70.77, 5155.8, 97.88, 4.03, 91.02, 5.92, -1.12, 62, 58, 57, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-02-25', 25482.5, 13.49, 17.93, 70.85, 5206.4, 97.7, 4.05, 90.92, 5.98, 0.23, 67, 64, 60, 4, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-02-26', 25496.55, 13.06, 18.63, 70.75, 5176.5, 97.79, 4.02, 90.95, 5.95, 0.06, 67, 64, 61, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-02-27', 25178.65, 13.7, 19.86, 72.48, 5230.5, 97.61, 3.96, 91.01, 6.0, -1.25, 63, 59, 57, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-03-02', 24865.7, 17.13, 21.44, 77.74, 5294.4, 98.38, 4.05, 91.08, 5.89, -1.24, 58, 53, 51, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-03-03', 23.57, 81.4, 5107.4, 99.05, 4.06, 91.56, 5.77, 62, 59, 58, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-03-04', 24480.5, 21.14, 21.15, 81.4, 5120.2, 98.77, 4.08, 92.01, 5.86, 55, 51, 47, 4, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-03-05', 24765.9, 17.86, 23.75, 85.41, 5065.3, 99.32, 4.15, 92.12, 5.75, 1.17, 61, 58, 55, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-03-06', 24450.45, 19.88, 29.49, 92.69, 5146.1, 98.99, 4.13, 91.79, 5.76, -1.27, 48, 45, 43, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-03-09', 24028.05, 23.36, 25.5, 98.96, 5091.5, 99.18, 4.14, 91.94, 5.8, -1.73, 38, 35, 33, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-03-10', 24261.6, 18.91, 24.93, 87.8, 5229.7, 98.83, 4.14, 91.22, 5.9, 0.97, 58, 56, 52, 4, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-03-11', 23866.85, 21.06, 24.23, 91.98, 5167.4, 99.23, 4.21, 92.17, 5.85, -1.63, 46, 42, 41, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-03-12', 23639.15, 21.52, 27.29, 100.46, 5115.8, 99.74, 4.27, 92.23, 5.82, -0.95, 40, 39, 37, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-03-13', 23151.1, 22.65, 27.19, 103.14, 5052.5, 100.36, 4.28, 92.39, 5.71, -2.06, 33, 32, 32, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-03-16', 23408.8, 21.6, 23.51, 100.21, 4994.0, 99.71, 4.22, 92.56, 5.79, 1.11, 46, 45, 41, 4, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-03-17', 23581.15, 19.79, 22.37, 103.42, 5001.0, 99.58, 4.2, 92.28, 5.73, 0.74, 45, 45, 42, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-03-18', 23777.8, 18.72, 25.09, 107.38, 4889.9, 100.09, 4.26, 92.39, 5.55, 0.83, 43, 44, 42, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-03-19', 23002.15, 22.8, 24.06, 108.65, 4600.7, 99.23, 4.28, 93.25, 5.43, -3.26, 29, 27, 26, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-03-20', 23114.5, 22.81, 26.78, 112.19, 4570.4, 99.65, 4.39, 93.08, 5.34, 0.49, 35, 35, 32, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-03-23', 22512.65, 26.73, 26.15, 99.94, 4404.1, 98.95, 4.33, 93.9, 5.44, -2.6, 32, 28, 25, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-03-24', 22912.4, 24.74, 26.95, 104.49, 4399.3, 99.43, 4.39, 93.24, 5.42, 1.78, 41, 41, 35, 6, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-03-25', 23306.45, 24.64, 25.33, 102.22, 4549.8, 99.6, 4.33, 94.3, 5.53, 1.72, 42, 42, 36, 6, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-03-26', 27.44, 108.01, 4375.5, 99.9, 4.42, 94.69, 5.45, 45, 46, 46, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-03-27', 22819.6, 26.8, 31.05, 112.57, 4492.0, 100.15, 4.44, 94.31, 5.47, 28, 28, 24, 4, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-03-30', 22331.4, 27.89, 30.61, 112.78, 4526.0, 100.51, 4.34, 94.78, 5.48, -2.14, 20, 19, 18, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-03-31', 25.25, 118.35, 4647.6, 99.96, 4.31, 94.36, 5.59, 40, 43, 42, 1, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-04-01', 22679.4, 25.01, 24.54, 101.16, 4783.2, 99.65, 4.32, 93.48, 5.62, 38, 37, 33, 4, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-04-02', 22713.1, 25.52, 23.87, 109.03, 4651.5, 100.03, 4.31, 92.64, 5.56, 0.15, 32, 32, 28, 4, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, usdinr, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-04-03', 92.97, 60, 58, 58, 0, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    usdinr = EXCLUDED.usdinr,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-04-06', 22968.25, 25.47, 24.17, 109.77, 4656.8, 99.98, 4.34, 92.97, 5.58, 31, 31, 28, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-04-07', 23123.65, 24.7, 25.78, 109.27, 4657.1, 99.64, 4.34, 92.82, 5.54, 0.68, 35, 35, 31, 4, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-04-08', 23997.35, 19.7, 21.04, 94.75, 4749.5, 99.13, 4.29, 92.86, 5.76, 3.78, 59, 59, 52, 7, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-04-09', 23775.1, 20.43, 19.49, 95.92, 4792.2, 98.82, 4.29, 92.27, 5.75, -0.93, 46, 44, 41, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-04-10', 24050.6, 18.85, 19.23, 95.2, 4761.9, 98.65, 4.32, 92.47, 5.87, 1.16, 54, 53, 48, 5, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-04-13', 23842.65, 20.5, 19.12, 99.36, 4742.4, 98.37, 4.3, 94.51, 5.98, -0.86, 45, 43, 39, 4, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-04-14', 18.36, 94.79, 4825.0, 98.12, 4.26, 94.95, 6.07, 57, 55, 53, 2, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-04-15', 24231.3, 18.67, 18.17, 94.93, 4800.0, 98.06, 4.28, 93.17, 6.07, 53, 51, 46, 5, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-04-16', 24196.75, 18.09, 17.94, 99.39, 4785.4, 98.22, 4.31, 93.39, 6.07, -0.14, 50, 48, 45, 3, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-04-17', 24353.55, 17.21, 17.48, 90.38, 4857.6, 98.1, 4.25, 93.05, 6.1, 0.65, 59, 57, 52, 5, 'historical_price_based')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-04-20', 24364.85, 18.79, 18.87, 95.48, 4806.6, 98.05, 4.25, 92.6, 6.04, 0.05, 53, 50, 46, 4, 'estimated_from_prices')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-04-21', 24576.6, 17.53, 19.5, 98.48, 4698.4, 98.41, 4.29, 93.12, 6.0, 0.87, 53, 52, 48, 4, 'estimated_from_prices')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-04-22', 24378.1, 18.3, 18.92, 101.91, 4732.5, 98.59, 4.29, 93.62, 6.12, -0.81, 46, 44, 42, 2, 'estimated_from_prices')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-04-23', 24173.05, 18.59, 19.31, 105.07, 4705.1, 98.8, 4.32, 93.8, 6.08, -0.84, 43, 42, 40, 2, 'estimated_from_prices')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-04-24', 23897.95, 19.71, 18.71, 105.33, 4722.3, 98.51, 4.31, 94.11, 6.02, -1.14, 41, 40, 37, 3, 'estimated_from_prices')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-04-27', 24092.7, 18.38, 18.02, 108.23, 4675.4, 98.48, 4.34, 94.25, 6.02, 0.81, 46, 46, 42, 4, 'estimated_from_prices')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-04-28', 23995.7, 18.05, 17.83, 111.26, 4591.5, 98.62, 4.35, 94.26, 5.91, -0.4, 41, 41, 38, 3, 'estimated_from_prices')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-04-29', 24177.65, 17.44, 18.81, 118.03, 4545.2, 98.92, 4.42, 94.65, 5.88, 0.76, 41, 43, 40, 3, 'estimated_from_prices')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-04-30', 23997.55, 18.46, 16.89, 114.01, 4614.7, 98.08, 4.39, 94.92, 5.93, -0.74, 39, 39, 36, 3, 'estimated_from_prices')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-05-01', 16.99, 108.17, 4629.9, 98.21, 4.38, 94.76, 5.93, 48, 49, 46, 3, 'estimated_from_prices')
ON CONFLICT (date) DO UPDATE SET
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-05-04', 24119.3, 18.3, 18.29, 114.44, 4519.5, 98.47, 4.45, 94.9, 5.8, 40, 41, 37, 4, 'estimated_from_prices')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-05-05', 24032.8, 17.91, 17.38, 109.87, 4555.8, 98.48, 4.42, 95.26, 5.94, -0.36, 42, 42, 39, 3, 'estimated_from_prices')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-05-06', 24330.95, 16.68, 17.39, 101.27, 4681.9, 98.02, 4.36, 95.18, 6.14, 1.24, 54, 54, 49, 5, 'estimated_from_prices')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-05-07', 24326.65, 16.62, 17.08, 100.06, 4699.8, 98.25, 4.39, 94.61, 6.13, -0.02, 52, 50, 47, 3, 'estimated_from_prices')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-05-08', 24176.15, 16.84, 17.19, 101.29, 4720.4, 97.84, 4.36, 94.25, 6.25, -0.62, 50, 48, 45, 3, 'estimated_from_prices')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-05-11', 23815.85, 18.55, 18.38, 104.21, 4718.7, 97.94, 4.41, 94.43, 6.41, -1.49, 43, 42, 39, 3, 'estimated_from_prices')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-05-12', 23379.55, 19.28, 17.99, 107.77, 4677.6, 98.29, 4.46, 95.39, 6.49, -1.83, 39, 37, 35, 2, 'estimated_from_prices')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-05-13', 23412.6, 19.43, 17.87, 105.63, 4697.7, 98.48, 4.48, 95.63, 6.64, 0.14, 44, 44, 40, 4, 'estimated_from_prices')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-05-14', 23689.6, 18.61, 17.26, 105.72, 4678.1, 98.88, 4.46, 95.7, 6.57, 1.18, 47, 48, 43, 5, 'estimated_from_prices')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-05-15', 23643.5, 18.79, 18.43, 109.26, 4555.8, 99.27, 4.59, 95.71, 6.25, -0.19, 40, 41, 39, 2, 'estimated_from_prices')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-05-18', 23649.95, 19.63, 17.82, 112.1, 4552.5, 98.97, 4.62, 95.97, 6.27, 0.03, 39, 39, 36, 3, 'estimated_from_prices')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-05-19', 23618.0, 18.68, 18.06, 111.28, 4506.3, 99.3, 4.67, 96.27, 6.16, -0.14, 39, 40, 38, 2, 'estimated_from_prices')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;
INSERT INTO daily_market_snapshot (date, nifty_close, india_vix, cboe_vix, brent, gold, dxy, us_10y, usdinr, copper, nifty_return_1d, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality)
VALUES ('2026-05-20', 23659.0, 18.44, 17.94, 108.11, 4508.0, 99.34, 4.64, 96.81, 6.25, 0.17, 42, 43, 41, 2, 'estimated_from_prices')
ON CONFLICT (date) DO UPDATE SET
    nifty_close = EXCLUDED.nifty_close,
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    usdinr = EXCLUDED.usdinr,
    copper = EXCLUDED.copper,
    nifty_return_1d = EXCLUDED.nifty_return_1d,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap,
    data_quality = EXCLUDED.data_quality;

-- Verify
SELECT date, nifty_close, india_vix, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality
FROM daily_market_snapshot ORDER BY date DESC LIMIT 35;