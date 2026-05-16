# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered market intelligence bot that sends Telegram messages (text + heatmap images) on a daily schedule. Two execution paths:

- **Path A (Visual)**: `fetch → heatmap_generator → send_image → Telegram` — no AI model involved
- **Path B (AI)**: `fetch → formatters.py → master_prompt.txt → ai_engine.analyze() → send_text → Telegram`

## Architecture

```
src/                   # Library modules (shared)
├── data_fetcher.py    # yfinance, Finnhub, NSE, AMFI data fetching
├── ai_engine.py      # AI routing (Groq → Google fallback)
├── formatters.py     # Data → block string (Path B)
├── db.py             # Supabase CRUD + purge logic
├── validator.py      # News trust scoring
├── telegram_sender.py # Telegram delivery
├── heatmap_generator.py # World equity heatmap
├── sector_heatmap.py  # India sector heatmap
├── commodity_heatmap.py # USDINR/Brent/Gold heatmap
└── ...

jobs/                  # Entry points (triggered by GitHub Actions)
├── morning_brief.py   # 8:00 AM: heatmaps + short AI brief
├── market_intel.py    # 7:00 AM / 6:00 PM: full 10-block AI analysis
├── fii_dii_fetch.py   # 5:00 AM: NSE FII/DII CSV → Supabase
├── mf_intelligence.py # 8th monthly: AMFI category flows → Supabase
├── mf_flows.py       # Personal MF watchlist (NAV tracking)
├── market_close.py   # EOD summary + winners/losers
├── evening_report.py  # 8:00 PM: US session heatmap
└── ...

.github/workflows/     # GitHub Actions (workflow_dispatch only)
cron-job.org/          # Triggers workflows at specific IST times
```

## AI Routing

`src/ai_engine.py` handles all AI calls:

- `ai.analyze(task="fast", prompt)` → Groq (llama-3.3-70b) → Google (gemini-1.5-flash)
- `ai.analyze(task="volume", prompt)` → Google (gemini-1.5-flash) → Groq
- `ai.sentiment(text)` → FinBERT via HuggingFace API

## Formatter Rules

Every function in `formatters.py` must:
1. Return `str` — the formatted block for the prompt
2. Return `""` (empty string) on any failure — never raise
3. Not import or call `ai_engine`
4. Compute trends/anomalies in the formatter (DB stores raw data only)

## Path B: market_intel.py

Uses `config/master_prompt.txt` with block placeholders `{block_1}` through `{block_10}`:
- Morning mode: blocks 1, 2, 4, 6, 8
- Evening mode: all 10 blocks (Phase 2 adds 3, 5, 7, 9)

Prompt assembly: replace placeholders, remove empty block headers with regex.

## Environment Variables (verified names)

| Variable | Used in |
|----------|---------|
| `GROQ_API_KEY` | ai_engine.py |
| `GOOGLE_AI_KEY` | ai_engine.py (NOT GOOGLE_API_KEY) |
| `HF_KEY` | ai_engine.py |
| `FINNHUB_KEY` | data_fetcher.py |
| `SUPABASE_URL`, `SUPABASE_KEY` | db.py |
| `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` | telegram_sender.py |

## Supabase Tables

- `watchlist`, `mf_watchlist`, `bot_state`, `sent_alerts` — existing, unchanged
- `market_snapshots` — global indices saved by morning_brief
- `fii_dii_flows` — daily NSE FII/DII (date PK, 61-day purge)
- `mf_flows` — monthly AMFI category flows (month+category PK, 2-month purge)

## Cron-job.org

All workflow triggers are external (cron-job.org → GitHub workflow_dispatch). No cron schedules in GitHub Actions. Jobs run Mon-Fri only.

## Key Patterns

- Path setup in job files: `sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))`
- Supabase lazy init: `from supabase import create_client` inside `get_client()`
- Image generation: PIL + Pilmoji, fonts from `/usr/share/fonts/truetype/dejavu/`
- NSE data: CSV download from `nseindia.com/archives/nsccl/fii_dii/FII_DII_CM_{date}.csv` (requires session cookies)
- AMFI data: `amfiindia.com/spages/NAVAll.txt` (public, no auth)

## Adding a New Job

1. Create `jobs/{job_name}.py` with `main()` entry point
2. Create `.github/workflows/{job_name}.yml` with `workflow_dispatch`
3. Add cron-job.org entry to trigger the workflow
4. For Path B: add formatter to `formatters.py`, add block to `config/master_prompt.txt`

---

## Phase 1 Intelligence Layer (Implemented)

**Core Principle**: Python computes conclusions. AI writes narrative only.

### Context Engine (`src/context_engine.py`)
- `run_contextualization()` — full pipeline: FII/DII context + VIX/DXY + Bull/Bear score
- `get_fii_dii_context()` — z-score vs 4W avg, streak detection, DII absorption, sparse data guards
- `get_vix_regime()` — HIGH/LOW/NORMAL/UNKNOWN classification
- `get_dxy_signal()` — RISING (>0.5%) / FALLING (<-0.5%) / FLAT
- `compute_bull_bear_score()` — weighted -40 to +40, returns confidence + dominant_factor
- `get_market_narrative()` — cross-signal rule matrix (8 patterns: triple threat, dollar-FII, India-specific, etc.)
- `format_context_for_ai()` — pre-formatted for Block 0 injection

### Options Engine (`src/options_engine.py`)
- `fetch_nse_options_chain()` — NSE API, selects expiry (skip if <3 days)
- `compute_max_pain()` — strike with highest total OI
- `compute_pcr()` — near-money only (±10% of spot), contrarian labeling (>1.4 = CONTRARIAN BULL)
- `compute_oi_zones()` — near-money only (±5% of spot), top 3 support/resistance
- `compute_oi_shifts()` — evening vs morning snapshot diff (Supabase)
- `store_options_snapshot()` — stores for evening diff

### Block 0: MARKET POSTURE
- Injected BEFORE all other blocks in master_prompt.txt
- Contains: Bull/Bear score, confidence, dominant factor, pre-written narrative

### AI Response Validation
- Minimum 50 words required, fallback to raw data if invalid, never send blank

### Supabase Tables
- `options_snapshots` — stores morning/evening PCR, max_pain, OI zones

### Entry Points
- `market_intel.py --mode morning/evening` — full analysis with context + options
- `morning_brief.py` — heatmaps + short text
- `evening_report.py` — US session + EOD summary
