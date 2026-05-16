# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered market intelligence bot that sends Telegram messages (text + heatmap images) on a daily schedule. Two execution paths:

- **Path A (Visual)**: `fetch → heatmap_generator → send_image → Telegram` — no AI model involved
- **Path B (AI)**: `fetch → formatters.py → master_prompt.txt → ai_engine.analyze() → send_text → Telegram`

## Architecture

```
src/                       # Library modules (shared)
├── data_fetcher.py        # yfinance, Finnhub, NSE, AMFI, RSS data fetching
├── ai_engine.py           # AI routing (Groq ↔ Google fallback), FinBERT sentiment
├── formatters.py          # Data → block string (Path B), quant enrichment calls
├── quant_enrichment.py    # Percentiles, cross-signal correlations, regime detection, news impact scoring
├── technical_analysis.py  # RSI, 200-DMA, S/R, MACD, Bollinger Bands from OHLCV
├── fii_derivatives.py     # F&O participant OI data (FII/DII/Client long/short)
├── fii_sector.py          # FPI sector-wise data (SEBI/NSE), sector rotation
├── context_engine.py      # Bull/Bear scoring, z-scores, streaks, DII absorption, narratives
├── options_engine.py      # NSE options chain, max pain, PCR, OI zones, OI shifts
├── insider_tracker.py     # NSE bulk/block deals, Indian stock filtering
├── db.py                  # Supabase CRUD + purge logic
├── validator.py           # News trust scoring
├── telegram_sender.py     # Telegram delivery
├── heatmap_generator.py   # World equity heatmap
├── sector_heatmap.py      # India sector heatmap
├── commodity_heatmap.py   # USDINR/Brent/Gold heatmap
└── ...

jobs/                      # Entry points (triggered by GitHub Actions)
├── market_intel.py        # 7:00 AM / 6:00 PM: full 10-block AI analysis (Path B)
├── morning_brief.py       # 8:00 AM: heatmaps + short AI brief
├── evening_report.py      # 8:00 PM: US session heatmap
├── fii_dii_fetch.py       # 5:00 AM: NSE FII/DII → Supabase
├── mf_intelligence.py     # 8th monthly: AMFI category flows → Supabase
├── mf_flows.py            # Personal MF watchlist (NAV tracking)
├── market_close.py        # EOD summary + winners/losers
├── insider_tracker.py     # Bulk/block deals with AI interpretation
└── ...

.github/workflows/         # GitHub Actions (workflow_dispatch only)
cron-job.org/              # Triggers workflows at specific IST times
```

## AI Routing

`src/ai_engine.py` handles all AI calls:

- `ai.analyze(task="fast", prompt)` → Groq (llama-3.3-70b) → Google (gemini-1.5-flash)
- `ai.analyze(task="volume", prompt)` → Google (gemini-1.5-flash) → Groq
- `ai.sentiment(text)` → FinBERT via HuggingFace API
- Both Groq and Google now receive SYSTEM_PROMPT (quant-focused persona)
- Max tokens: 1000 (both), Temperature: 0.3

## Formatter Rules

Every function in `formatters.py` must:
1. Return `str` — the formatted block for the prompt
2. Return `""` (empty string) on any failure — never raise
3. Not import or call `ai_engine`
4. Compute trends/anomalies in the formatter (DB stores raw data only)
5. Add quant context: percentiles, significance labels, historical comparisons

## Path B: market_intel.py

Uses `config/master_prompt.txt` with block placeholders `{block_0}` through `{block_10}`:
- Block 0: Market Posture (Bull/Bear from context_engine)
- Block 1: Global Indices + Market Breadth + Nifty Technical Levels
- Block 2: Macro Anchors (USDINR, Brent, Gold, VIX, DXY)
- Block 3: Sector FPI Activity (FPI sector-wise flows, rotation signals)
- Block 4: FII/DII Flows + F&O Participant Positioning
- Block 5: Derivatives (PCR, Max Pain, OI Zones from options_engine)
- Block 6: News Intelligence (Global + Indian, FinBERT sentiment, impact scoring)
- Block 7: Insider Activity (NSE bulk/block deals, Indian stocks only)
- Block 8: Watchlist + Technical Analysis (RSI, S/R, MACD, Bollinger)
- Block 9: Macro Calendar (Phase 2 — not yet implemented)
- Block 10: MF Flow Intelligence (industry-wide AMFI category data)

Prompt assembly: replace placeholders, remove empty block headers with regex.

## Quant Enrichment Layer (`src/quant_enrichment.py`)

Pre-computes intelligence from raw data before sending to AI:

- `compute_percentile()` — where does current value sit vs history?
- `compute_cross_signals()` — 7 cross-signal patterns with historical win rates
- `detect_regime_transition()` — VIX/FII regime changes
- `score_news_impact()` — HIGH/MEDIUM/LOW impact scoring with category tags
- `generate_scenarios()` — probability-weighted bull/bear/base scenarios

## Technical Analysis (`src/technical_analysis.py`)

Computes from existing OHLCV data (zero API cost):

- `compute_rsi()` — RSI(14) with overbought/oversold labels
- `compute_moving_averages()` — 20/50/200-DMA with distance %
- `compute_support_resistance()` — swing high/low + psychological levels
- `compute_macd()` — MACD line, signal, histogram, crossover detection
- `compute_bollinger_bands()` — upper/lower bands, %B position
- `compute_full_analysis()` — runs all indicators, returns complete picture

## FII/DII Intelligence

### Cash Market (`context_engine.py` + `formatters.py` format_flows)
- Z-score vs 20D avg, consecutive streak detection, DII absorption ratio
- 5-day stats, 4-week trend with labels (deteriorating/improving/mixed)

### F&O Positioning (`src/fii_derivatives.py`)
- NSE F&O participant-wise OI (FII/DII/Client long/short)
- FII long/short ratio, hedging vs directional detection
- Appended to Block 4

### Sector FPI (`src/fii_sector.py`)
- SEBI/NSE FPI sector-wise investment data
- Top inflows/outflows, rotation signals
- Fills Block 3

## News Pipeline

### Sources
- **Global**: Finnhub (general + forex + crypto categories)
- **Indian**: RSS feeds (Economic Times, MoneyControl, Livemint)

### Processing
- Trust scoring: source-name matching (validator.py)
- Sentiment: FinBERT via HuggingFace (ai_engine.py)
- Impact scoring: quant_enrichment.py (HIGH/MEDIUM/LOW + category tags)
- Format: split Global News / India News in Block 6

## Environment Variables

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
- `options_snapshots` — morning/evening PCR, max_pain, OI zones (7-day purge)

## Cron-job.org

All workflow triggers are external (cron-job.org → GitHub workflow_dispatch). No cron schedules in GitHub Actions. Jobs run Mon-Fri only.

## Key Patterns

- Path setup in job files: `sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))`
- Supabase lazy init: `from supabase import create_client` inside `get_client()`
- Image generation: PIL + Pilmoji, fonts from `/usr/share/fonts/truetype/dejavu/`
- NSE data: requires session cookies (hit homepage first, then API)
- AMFI data: `amfiindia.com/spages/NAVAll.txt` (public, no auth)
- Insider filtering: `_is_valid_indian_symbol()` rejects ETFs, non-Indian instruments
- NaN handling: `_safe_float()` throughout data pipelines

## Adding a New Job

1. Create `jobs/{job_name}.py` with `main()` entry point
2. Create `.github/workflows/{job_name}.yml` with `workflow_dispatch`
3. Add cron-job.org entry to trigger the workflow
4. For Path B: add formatter to `formatters.py`, add block to `config/master_prompt.txt`

## AI Output Format

The master prompt instructs the AI to produce structured quant output:
```
📊 REGIME: [Risk-on/Risk-off/Neutral] (confidence: X%)
📈 HEADLINE: [Most important number + historical context]
🔑 KEY SIGNALS: [2-3 signals with numbers + percentiles]
📊 CROSS-SIGNALS: [Active correlation patterns]
⚠️ SCENARIOS: [Bull/Bear/Base with probabilities]
```

Every number must have context — no bare numbers without "since [date]", "Xth percentile", or "vs [benchmark]".
