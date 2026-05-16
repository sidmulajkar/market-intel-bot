# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## High-Level Overview

**What:** AI-powered Indian market intelligence bot — sends daily Telegram analysis (text + heatmaps).

**Stack:** Python, Supabase, Telegram Bot, Groq/Google AI, NSE/AMFI/SEBI data, FinBERT sentiment.

**How it works:**
1. **5 AM** — Fetch FII/DII data from NSE → store in Supabase
2. **7 AM** — Morning analysis: fetch 9 macro anchors + global indices + news → format 11 blocks → AI generates quant brief → send to Telegram
3. **6 PM** — Evening analysis: full 11 blocks including derivatives, shareholding QoQ, MF flows → AI brief → Telegram

**The 11 Blocks:**
| Block | Content | Key Signals |
|-------|---------|-------------|
| 0 | Market Posture | Bull/Bear score (8 signals), global risk composite, VIX spread, credit stress |
| 1 | Global Indices + Breadth | 18 indices, A/D ratio, McClellan Oscillator, Nifty vs 200-DMA |
| 2 | Macro + Valuation | 9 anchors (USDINR, Brent, Gold, VIX, DXY, US10Y, CBOE VIX, HYG, WTI), P/E, risk premium, reverse DCF |
| 3 | Sector FPI | FPI sector-wise flows, rotation signals |
| 4 | FII/DII Flows | Cash market + F&O participant positioning |
| 5 | Derivatives | PCR, Max Pain, OI zones, GEX, 25D skew, advanced OI (6 signals) |
| 6 | News | Global + Indian, FinBERT sentiment, impact scoring, contrarian extremes |
| 7 | Insider | NSE bulk/block deals, Indian stocks only |
| 8 | Watchlist + TA | Technical analysis (RSI, MACD, Bollinger), shareholding QoQ changes |
| 9 | Macro Calendar | Upcoming events (CPI, RBI MPC, IIP), RBI policy, real rate |
| 10 | MF Flows | Industry-wide AMFI category flows, SIP trends |

**Intelligence Layers:**
- **Valuation** — Nifty P/E, P/B, earnings yield, equity risk premium, reverse DCF, 3Y percentile
- **Derivatives** — GEX (gamma exposure), 25D risk reversal (skew), 6 advanced OI signals
- **Macro** — 9 anchors batch-fetched, VIX spread (CBOE vs India), credit stress (HYG), yield spread, real rate
- **Regime** — Bull/Bear score (8 signals), 12M momentum, global risk composite
- **Contrarian** — Sentiment extremes, SIP concentration (HHI), PCR contrarian readings
- **Quant** — Percentiles, cross-signal patterns (7), backtest function, regime transitions

---

## Architecture

```
src/                       # Library modules (shared)
├── data_fetcher.py        # yfinance, Finnhub, NSE, AMFI, RSS, smallcap ratio, McClellan
├── ai_engine.py           # AI routing (Groq ↔ Google fallback), FinBERT sentiment
├── formatters.py          # Data → block string (Path B), quant enrichment calls
├── quant_enrichment.py    # Percentiles, cross-signals, backtest, contrarian, consensus
├── technical_analysis.py  # RSI, 200-DMA, S/R, MACD, Bollinger Bands from OHLCV
├── valuation_engine.py    # Nifty P/E, P/B, earnings yield, risk premium, reverse DCF
├── macro_fetcher.py       # Macro calendar, RBI policy tracker, real rate
├── context_engine.py      # Bull/Bear (8 signals), global risk, VIX spread, credit stress, momentum, yield spread
├── options_engine.py      # NSE options chain, max pain, PCR, GEX, skew, advanced OI
├── fii_derivatives.py     # F&O participant OI data (FII/DII/Client long/short)
├── fii_sector.py          # FPI sector-wise data (SEBI/NSE), sector rotation
├── insider_tracker.py     # NSE bulk/block deals, Indian stock filtering
├── shareholding_tracker.py # Promoter/FII/DII/Public % with QoQ comparison
├── nse_session.py         # Unified NSE session manager with TTL, ErrorBudget
├── db.py                  # Supabase CRUD + purge logic
├── validator.py           # News trust scoring
├── telegram_sender.py     # Telegram delivery
├── heatmap_generator.py   # World equity heatmap
├── sector_heatmap.py      # India sector heatmap
└── commodity_heatmap.py   # USDINR/Brent/Gold heatmap

jobs/                      # Entry points (triggered by GitHub Actions)
├── market_intel.py        # 7:00 AM / 6:00 PM: full 10-block AI analysis
├── morning_brief.py       # 8:00 AM: heatmaps + short AI brief
├── evening_report.py      # 8:00 PM: US session heatmap
├── fii_dii_fetch.py       # 5:00 AM: NSE FII/DII → Supabase
├── mf_intelligence.py     # 8th monthly: AMFI category flows → Supabase
├── mf_flows.py            # Personal MF watchlist (NAV tracking)
├── market_close.py        # EOD summary + winners/losers
├── insider_tracker.py     # Bulk/block deals with AI interpretation
└── ...

config/
├── master_prompt.txt      # AI prompt template with interpretation rules
├── macro_calendar.json    # Indian macro events (CPI, RBI MPC, IIP dates)
├── settings.json          # Basic settings (timezone, market, AI provider)
├── watchlist.json         # Default stock watchlist (fallback)
└── mf_watchlist.json      # Default MF scheme codes (fallback)

sql/
└── create_new_tables.sql  # Supabase table creation (valuation_history, market_breadth_history)

.github/workflows/         # GitHub Actions (workflow_dispatch only)
cron-job.org/              # Triggers workflows at specific IST times
```

---

## AI Routing

`src/ai_engine.py` handles all AI calls:

- `ai.analyze(task="fast", prompt)` → Groq (llama-3.3-70b) → Google (gemini-2.0-flash)
- `ai.analyze(task="volume", prompt)` → Google (gemini-2.0-flash) → Groq
- `ai.sentiment(text)` → FinBERT via HuggingFace API
- Max tokens: 1000, Temperature: 0.3

## Macro Anchors (9 tickers, batch fetched)

| Anchor | Symbol | Purpose |
|--------|--------|---------|
| USD/INR | `USDINR=X` | INR weakness |
| Brent Crude | `BZ=F` | Energy cost, current account |
| Gold | `GC=F` | Safe haven |
| India VIX | `^INDIAVIX` | Local fear gauge |
| Dollar Index | `DX-Y.NYB` | Dollar strength = EM headwind |
| US 10Y Yield | `^TNX` | Global rates, FII allocation |
| CBOE VIX | `^VIX` | Global fear gauge |
| US High Yield | `HYG` | Credit stress proxy |
| WTI Crude | `CL=F` | Secondary oil benchmark |

## Context Engine Signals

| Signal | Source | What It Tells You |
|--------|--------|-------------------|
| Bull/Bear Score | 8 inputs | Overall market direction (0-100) |
| Global Risk Composite | CBOE VIX + HYG + DXY | RISK-ON / RISK-OFF / MIXED |
| VIX Spread | CBOE VIX - India VIX | Global vs local fear |
| Credit Stress | HYG weekly change | Liquidity crisis indicator |
| Yield Spread | India G-Sec - US 10Y | FII carry trade incentive |
| Real Rate | Repo - CPI | Policy tightness |
| Momentum (12M) | Nifty 252-day return | Bull/bear regime |
| Smallcap/Largecap | Nifty Smallcap 250 / Nifty 50 | Risk appetite, cycle position |
| Oil+INR | Brent + USDINR | Current account stress |

## Supabase Tables

| Table | PK | Retention | Purpose |
|-------|-----|-----------|---------|
| `watchlist` | symbol | Permanent | User's stock watchlist |
| `mf_watchlist` | scheme_code | Permanent | User's MF schemes |
| `bot_state` | key | Permanent | Telegram update offset |
| `sent_alerts` | id | 30 days | Alert deduplication |
| `market_snapshots` | date | 90 days | Global indices snapshot |
| `fii_dii_flows` | date | 61 trading days | Daily FII/DII data |
| `mf_flows` | month+category | 2 months | AMFI category flows |
| `options_snapshots` | date+run | 7 days | Derivatives snapshots |
| `valuation_history` | date+index_name | 3 years | P/E, P/B, DY, earnings yield |
| `market_breadth_history` | date | 90 days | A/D ratios for McClellan + percentile |

SQL to create new tables: `sql/create_new_tables.sql`

## Key Patterns

- NSE APIs require session cookies — use `src/nse_session.py` (shared session, 5-min TTL)
- Options chain: `/api/option-chain-indices` for NIFTY/BANKNIFTY (includes IV data)
- Valuation: `/api/allIndices` for P/E, P/B data
- Black-Scholes: `_bs_gamma()`, `_bs_delta()` in options_engine.py for GEX/skew
- All formatters return `""` on failure — never raise
- NaN handling: `_safe_float()` throughout

## GitHub Actions Constraint

Max 3-4 minutes per runner:
- **5 AM** `fii_dii_fetch.py` — data collection only (~1 min)
- **7 AM** `market_intel.py` morning — analysis + AI (~3 min)
- **6 PM** `market_intel.py` evening — full analysis (~3-4 min)
- **Monthly** `mf_intelligence.py` — AMFI processing (~2 min)

## Environment Variables

| Variable | Used in |
|----------|---------|
| `GROQ_API_KEY` | ai_engine.py |
| `GOOGLE_AI_KEY` | ai_engine.py (NOT GOOGLE_API_KEY) |
| `HF_KEY` | ai_engine.py |
| `FINNHUB_KEY` | data_fetcher.py |
| `SUPABASE_URL`, `SUPABASE_KEY` | db.py |
| `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` | telegram_sender.py |
