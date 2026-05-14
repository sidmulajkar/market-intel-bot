# Deployment Guide — Market Intel Bot Phase 1

This guide deploys Phase 1 without disrupting existing workflows (morning_brief, market_close, etc.).

---

## Overview

Phase 1 adds **3 new Supabase tables** and **4 new GitHub Actions jobs**. Existing jobs (`morning_brief`, `market_close`, `market_open`, `evening_report`, etc.) are **unchanged**.

```
New jobs triggered by cron-job.org → GitHub Actions:
──────────────────────────────────────────────────
5:00 AM IST   fii_dii_fetch.py   → fii_dii_fetch.yml
7:00 AM IST   market_intel.py    → market_intel_morning.yml
6:00 PM IST   market_intel.py    → market_intel_evening.yml
8th of month  mf_intelligence.py → mf_intelligence.yml
```

---

## Step 1: Create Supabase Tables

Go to your Supabase project → **SQL Editor** and run each block below.

### 1a. `fii_dii_flows` table

```sql
-- FII/DII daily flow data
-- Retention: 61 trading days (purged by trading-day-aware logic in db.py)
CREATE TABLE IF NOT EXISTS fii_dii_flows (
    date        DATE    NOT NULL,
    fiinet_cr   NUMERIC NOT NULL DEFAULT 0,
    diinet_cr   NUMERIC NOT NULL DEFAULT 0,
    net_cr      NUMERIC NOT NULL DEFAULT 0,
    source      TEXT    NOT NULL DEFAULT 'NSE',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ,
    PRIMARY KEY (date)
);

-- Enable RLS (match existing table pattern)
ALTER TABLE fii_dii_flows ENABLE ROW LEVEL SECURITY;

-- Allow anon read/write (matches existing bot behavior)
CREATE POLICY "allow_all_fii_dii" ON fii_dii_flows
    FOR ALL USING (true) WITH CHECK (true);

-- Auto-expire (optional — purge also runs in app code)
-- ALTER TABLE fii_dii_flows SET (
--   row_security = true,
--   expires = '61 days'
-- );

COMMENT ON TABLE fii_dii_flows IS 'Daily FII/DII net flows from NSE India';
```

### 1b. `mf_flows` table

```sql
-- Mutual Fund category monthly flow data
-- Retention: 2 months rolling (purged in db.py purge_old_data)
CREATE TABLE IF NOT EXISTS mf_flows (
    month          DATE        NOT NULL,
    category       TEXT        NOT NULL,
    amount_cr      NUMERIC     NOT NULL DEFAULT 0,
    sip_amount_cr  NUMERIC,
    source         TEXT        NOT NULL DEFAULT 'AMFI',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at     TIMESTAMPTZ,
    PRIMARY KEY (month, category)
);

-- Enable RLS
ALTER TABLE mf_flows ENABLE ROW LEVEL SECURITY;

CREATE POLICY "allow_all_mf_flows" ON mf_flows
    FOR ALL USING (true) WITH CHECK (true);

COMMENT ON TABLE mf_flows IS 'Monthly MF category flows from AMFI (aggregated from NAVAll.txt)';
```

### 1c. Verify existing tables still work

Existing tables (`watchlist`, `mf_watchlist`, `bot_state`, `sent_alerts`, `market_snapshots`, `analysis_cache`) are **unchanged**. No migration needed for them.

Run this to confirm:
```sql
-- Check all 6 existing tables still exist
SELECT 'watchlist'       as tbl, count(*) as rows FROM watchlist
UNION ALL SELECT 'mf_watchlist',    count(*) FROM mf_watchlist
UNION ALL SELECT 'bot_state',       count(*) FROM bot_state
UNION ALL SELECT 'sent_alerts',     count(*) FROM sent_alerts
UNION ALL SELECT 'market_snapshots',count(*) FROM market_snapshots
UNION ALL SELECT 'analysis_cache',  count(*) FROM analysis_cache;
-- Existing tables should return rows (or 0 if empty)
```

---

## Step 2: Add GitHub Secrets

Go to **GitHub repo → Settings → Secrets and variables → Actions → New repository secret**.

Add these secrets (values from your existing `.env` or Supabase dashboard):

| Secret | Value |
|--------|-------|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_KEY` | Your Supabase anon/service key |
| `TELEGRAM_TOKEN` | Your Telegram bot token |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID |
| `GROQ_API_KEY` | Your Groq API key |
| `GOOGLE_AI_KEY` | Your Google AI Studio key |
| `HF_KEY` | Your HuggingFace API key |
| `FINNHUB_KEY` | Your Finnhub API key |

> **Note**: `GOOGLE_AI_KEY` (not `GOOGLE_API_KEY`) — this is the verified env var name from `src/ai_engine.py`.

Existing workflows (`morning_brief.yml`, `market_close.yml`, etc.) already have their secrets configured. No changes needed to them.

---

## Step 3: Configure cron-job.org

Go to **cron-job.org** and create 4 jobs:

### 3a. FII/DII Fetch (5:00 AM IST daily)

```
URL: https://api.github.com/repos/{owner}/{repo}/actions/workflows/fii_dii_fetch.yml/dispatch
Method: POST
Headers:
  Authorization: token {GITHUB_TOKEN}
  Accept: application/vnd.github.v3+json
Body (optional):
  {"ref": "main"}

Schedule: 0 5 * * 1-5
  (Mon-Fri at 5:00 AM IST = 23:30 UTC previous day)
```

### 3b. Market Intel Morning (7:00 AM IST daily)

```
URL: https://api.github.com/repos/{owner}/{repo}/actions/workflows/market_intel_morning.yml/dispatch
Method: POST
Headers: Same as above
Schedule: 30 6 * * 1-5
  (Mon-Fri at 6:30 AM IST = 1:00 UTC)
```

### 3c. Market Intel Evening (6:00 PM IST daily)

```
URL: https://api.github.com/repos/{owner}/{repo}/actions/workflows/market_intel_evening.yml/dispatch
Method: POST
Headers: Same as above
Schedule: 0 18 * * 1-5
  (Mon-Fri at 6:00 PM IST = 12:30 UTC)
```

### 3d. MF Intelligence (8th of month, Mon-Fri)

```
URL: https://api.github.com/repos/{repo}/actions/workflows/mf_intelligence.yml/dispatch
Method: POST
Headers: Same as above
Schedule: 0 8 8 * 1-5
  (8th of month, Mon-Fri at 8:00 AM IST = 2:30 UTC)
```

> **GitHub Personal Access Token**: You need a GitHub PAT with `repo` scope to trigger workflows via cron-job.org. Add it to cron-job.org as the Authorization header.

---

## Step 4: Verify Installation

After running the jobs for the first time:

### 4a. Check GitHub Actions logs

Each workflow should complete without errors:
- `fii_dii_fetch.yml` → "FII/DII: N/5 rows upserted"
- `market_intel_morning.yml` → "Market Intel sent"
- `market_intel_evening.yml` → "Market Intel sent"
- `mf_intelligence.yml` → "MF Intelligence: N categories saved"

### 4b. Check Supabase data

```sql
-- Check fii_dii_flows populated
SELECT date, fiinet_cr, diinet_cr, net_cr
FROM fii_dii_flows
ORDER BY date DESC LIMIT 5;

-- Check mf_flows populated
SELECT month, category, amount_cr
FROM mf_flows
ORDER BY month DESC, amount_cr DESC;
```

### 4c. Check Telegram

You should receive:
- Morning market intel at ~7:05 AM IST
- Evening market intel at ~6:05 PM IST
- FII/DII fetch silently runs (no Telegram output unless it fails)

---

## Step 5: Verify Existing Workflows Still Work

Existing jobs are **unchanged** — no action needed. But verify:
```sql
-- Check market_snapshots still being written (by morning_brief)
SELECT date FROM market_snapshots ORDER BY date DESC LIMIT 3;

-- Check sent_alerts still working
SELECT date, symbol, alert_type FROM sent_alerts ORDER BY date DESC LIMIT 5;
```

---

## Rollback Plan

If something goes wrong:

| Scenario | Rollback Action |
|----------|----------------|
| New jobs failing | Disable cron-job.org jobs, existing workflows unaffected |
| Supabase table issues | Drop new tables — existing tables untouched |
| Data corruption | `DELETE FROM fii_dii_flows` / `DELETE FROM mf_flows` — no effect on existing tables |
| Full revert | `git revert` the Phase 1 commits — removes all new files + db changes |

---

## Dependencies Check

Phase 1 uses **only existing dependencies** (verified in `requirements.txt`):
- `yfinance` — `fetch_macro_anchors()`
- `pandas` — `format_flows()`, `format_mf_flows()` (already in requirements)
- `requests` — FII/DII fetch, MF intelligence
- `pytz` — timezone handling
- `supabase` — DB client (already in requirements)

No new packages need to be added.

---

## Troubleshooting

### "Table fii_dii_flows not found"
→ Run the CREATE TABLE SQL from Step 1a in Supabase SQL Editor.

### "FII/DII fetch failed — no data returned"
→ NSE endpoint may require updated headers. Check GitHub Actions log for the specific error. NSE occasionally changes their API structure.

### "Market Intel: All data sources failed"
→ At least one block (global indices or news) should always return data. Check that `FINNHUB_KEY` and internet access are working in the GitHub runner.

### "MF Intelligence: 0 categories saved"
→ This is expected if running before the 8th of the month. The job runs on cron but exits early with a "weekend" check on non-trading days.

### "Python import error: pandas"
→ pandas is already in `requirements.txt`. If the workflow fails, check the `pip install` step logs.

---

## Architecture Preservation

This deployment **does not modify**:
- `src/ai_engine.py` (AI routing unchanged)
- `src/validator.py` (news validation unchanged)
- `src/telegram_sender.py` (Telegram sending unchanged)
- `jobs/morning_brief.py` (existing morning heatmap job)
- `jobs/market_close.py` (existing EOD job)
- `jobs/evening_report.py` (existing evening global report)
- `jobs/market_open.py` (existing market open job)
- `jobs/weekly_digest.py` (existing weekly job)
- `jobs/midday_scan.py` (existing midday job)
- `jobs/credit_monitor.py`, `jobs/insider_tracker.py`, `jobs/deals_tracker.py`

All existing workflows and jobs continue to work identically.