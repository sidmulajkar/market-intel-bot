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
- **Market State** — 8-signal weighted composite phase classifier (EXPANSION/RECOVERY/NEUTRAL/DISTRIBUTION/CONTRACTION), stance = phase × confidence, risk watch pattern detection
- **Cross-Asset** — 12+ regime detectors synthesized into single label (RISK_ON/RISK_OFF/STAGFLATION/etc.) with confirmation %
- **Institutional** — Sector regime, volatility compression, risk appetite, breadth thrust, FII footprint (all from stored data, zero API cost)
- **Earnings** — Season regime (PEAK_WEEK/ACTIVE/APPROACHING/QUIET) from dynamic yfinance calendar
- **Signal Arbitration** — Master signal synthesis with contradiction scoring, dynamic weights from accuracy log

---

## Architecture

```
src/                       # Library modules (shared)
├── data_fetcher.py        # yfinance, Finnhub, NSE, AMFI, RSS, smallcap ratio, McClellan
├── ai_engine.py           # AI routing (Groq ↔ Google fallback), FinBERT sentiment
├── formatters.py          # Data → block string (Path B), quant enrichment calls
├── metrics.py             # Canonical metric functions (compute_flow_metrics, VIX/FII/absorption interpretations)
├── context_engine.py      # Bull/Bear (8 signals), global risk, VIX spread, credit stress, momentum, yield spread, cross-asset regime, market phase classifier
├── quant_enrichment.py    # Percentiles, cross-signals, backtest, contrarian, consensus
├── technical_analysis.py  # RSI, 200-DMA, S/R, MACD, Bollinger Bands from OHLCV
├── valuation_engine.py    # Nifty P/E, P/B, earnings yield, risk premium, reverse DCF
├── macro_fetcher.py       # Macro calendar, RBI policy tracker, real rate
├── mechanism_map.py       # Macro event → India sector impact mapping (21 mechanisms)
├── options_engine.py      # NSE options chain, max pain, PCR, GEX, skew, advanced OI
├── fii_derivatives.py     # F&O participant OI data (FII/DII/Client long/short)
├── fii_sector.py          # FPI sector-wise data (SEBI/NSE), sector rotation
├── insider_tracker.py     # NSE bulk/block deals, Indian stock filtering, pattern detection
├── shareholding_tracker.py # Promoter/FII/DII/Public % with QoQ comparison
├── nse_session.py         # Unified NSE session manager with TTL, ErrorBudget
├── db.py                  # Supabase CRUD + purge logic
├── validator.py           # News trust scoring, staleness detection, India linkage
├── validation_helper.py   # Reusable AI output validation for all jobs
├── output_validator.py    # 26-pattern AI output validator (stale levels, hallucinated %, advice, confidence)
├── telegram_sender.py     # Telegram delivery
├── heatmap_generator.py   # World equity heatmap
├── sector_heatmap.py      # India sector heatmap
├── commodity_heatmap.py   # USDINR/Brent/Gold heatmap
├── consequence_engine.py  # India impact multiplier table, compound consequences (USDINR amplifier)
├── signal_arbitrator.py   # Gap analysis, confidence split, regime detection, accumulation signals
├── block_validator.py     # Per-block 4-layer check, pre-send integrity checklist (10 gates)
├── compute_budget.py      # Graceful degradation: time tracking, stage management, block dropping
└── rolling_quant.py       # Rolling quant engine (percentiles, divergences, correlations, regime shifts)

jobs/                      # Entry points (triggered by GitHub Actions)
├── market_intel.py        # 7:00 AM / 6:00 PM: full 11-block AI analysis + Market State Dashboard
├── morning_brief.py       # 8:00 AM: heatmaps + short brief + Market State Dashboard
├── evening_report.py      # 8:00 PM: US session heatmap + Market State Dashboard
├── midday_scan.py         # 12:30 PM: market regime scanner (not per-stock alerts)
├── market_open.py         # 9:15 AM: opening briefing with dynamic top movers
├── market_close.py        # 3:30 PM: EOD summary with dynamic top movers
├── weekly_digest.py       # Sunday: prediction scorecard, FII pattern, regime shift, institutional signals
├── fii_dii_fetch.py       # 5:00 AM: NSE FII/DII → Supabase
├── mf_intelligence.py     # 8th monthly: AMFI category flows → Supabase
├── mf_flows.py            # Personal MF watchlist (NAV tracking)
├── insider_tracker.py     # Bulk/block deals with AI interpretation
└── ...

config/
├── master_prompt.txt      # AI prompt template with interpretation rules
├── macro_calendar.json    # Indian macro events (CPI, RBI MPC, IIP dates)
├── settings.json          # Basic settings (timezone, market, AI provider)
├── watchlist.json         # Default stock watchlist (fallback)
└── mf_watchlist.json      # Default MF scheme codes (fallback)

sql/
├── create_new_tables.sql  # Supabase table creation (valuation_history, market_breadth_history)
├── phase19_cluster_columns.sql  # ALTER TABLE for structural_score/sentiment_score/cluster_gap
└── backfill_snapshots_30d.sql   # Generated by backfill script

# One-time scripts (not cron jobs)
backfill_daily_snapshots.py  # Backfill 1 year of daily_market_snapshot from yfinance (261 rows)
backfill_mf_flows.py         # Backfill MF flows from AMFI (live fetch)
bootstrap_master_signal.py   # Bootstrap today's real scores + cluster scores

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
| Global Risk Composite | CBOE VIX + HYG + DXY + Gold + Copper | RISK-ON / RISK-OFF / MIXED |
| Risk Mood | Global Risk Composite | 0-100 calibrated score with visual mood bar |
| VIX Spread | CBOE VIX - India VIX | Global vs local fear |
| Credit Stress | HYG weekly change | Liquidity crisis indicator |
| Yield Spread | India G-Sec - US 10Y | FII carry trade incentive |
| Real Rate | Repo - CPI | Policy tightness |
| Momentum (12M) | Nifty 252-day return | Bull/bear regime |
| Smallcap/Largecap | Nifty Smallcap 250 / Nifty 50 | Risk appetite, cycle position |
| Oil+INR | Brent + USDINR | Current account stress |

## Pre-computed Interpretations (Phase 23)

AI receives conclusions, not raw numbers. Three interpretations computed once in `run_contextualization()`, stored in `ctx`, formatted into AI prompt:

| Interpretation | Trigger | Example Output |
|---------------|---------|---------------|
| VIX | VIX price + percentile | "VIX 16.5 normal — no volatility signal." |
| FII Flow | flow_metrics (streak, z-score, trend) | "FII heavy single-day selling (₹-4,357Cr). Moderate selling." |
| DII Absorption | FII net + DII net | "DII absorbing 115% of FII outflow — more than offsetting." |

Requires Supabase `fii_dii_flows` table for FII and Absorption. VIX works with just macro anchor data.

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
| `daily_market_snapshot` | date | 3 years | Unified daily metrics for rolling quant engine |
| `correlation_matrix` | id+date | 1 year | Rolling signal correlations (weekly) |
| `signal_accuracy_log` | id+date | 1 year | Per-signal hit rates for dynamic weighting |
| `divergence_log` | id+date | 90 days | Cross-asset divergence tracking |
| `macro_anchor_snapshots` | id | 30 days | 15 anchor daily values |
| `fii_institution_tracker` | id | 30 days | SWF/Pension Fund tracking |
| `daily_predictions` | id | 30 days | Evening predictions with regime |
| `prediction_outcomes` | id | 30 days | Morning validation results |

SQL to create new tables: `sql/create_new_tables.sql`

## Phase 11: Rolling Quant Engine (`src/rolling_quant.py`)

Core statistical intelligence module. Reads from `daily_market_snapshot` (252+ days).

| Feature | Function | What It Does |
|---------|----------|--------------|
| Percentile Ranking | `percentile_rank()` | Where any value sits vs 1Y/2Y/3Y history |
| Z-Score | `rolling_z_score()` | Mean reversion signal (>2.5 = extreme) |
| All Percentiles | `compute_all_percentiles()` | 19 metrics ranked simultaneously |
| Divergence Detection | `detect_divergences()` | 5 cross-asset divergences (Gold+Dollar, Nifty+Breadth, VIX+FII, Copper+Nifty, India+CBOE VIX) |
| Seasonal Patterns | `compute_seasonal_context()` | Monthly/weekly effects, expiry week detection |
| Scenario Matching | `compute_scenario_match()` | Find historical periods with similar conditions |
| Correlations | `compute_rolling_correlations()` | 6 signal pairs (FII→return, PCR→return, DXY↔FII, VIX↔Nifty, Gold↔DXY, Brent↔Nifty) |
| Relative Value | `compute_relative_value()` | ERP vs historical, ERP vs US, Nifty fair value bands, Gold/Nifty ratio |
| Mean Reversion | `compute_mean_reversion_signals()` | 252-day z-score extremes |
| Regime Shifts | `detect_statistical_regime_shifts()` | 20D vs 60D rolling comparison |
| Full Engine | `run_rolling_quant_engine()` | Runs all 8 components, returns structured data |
| Format | `format_rolling_quant_block()` | Formats all for AI prompt injection |

## Phase 11: Options Flow Inference (`src/options_engine.py`)

| Function | What It Does |
|----------|--------------|
| `infer_options_flow()` | OI+price movement → long/short/covering/liquidation classification |
| `format_options_flow()` | Formats institutional activity + unusual strikes for AI |

## Phase 11: Signal Accuracy + Dynamic Weighting (`src/prediction_tracker.py`)

| Function | What It Does |
|----------|--------------|
| `record_signals_that_fired()` | Logs which signals fired + outcome (called morning after validation) |
| `get_dynamic_signal_weights()` | Computes hit rate per signal, returns weight multipliers |
| `format_signal_weights()` | Formats accuracy stats for AI prompt |

Weight rules: >65% hit rate → ×1.3 (amplified) | <45% → ×0.7 (penalized) | else → ×1.0

## Phase 11: Smart Threshold Alerts (`src/threshold_alerts.py`)

8 threshold triggers: Nifty crash (>1.5%), Nifty surge (>2%), VIX spike (>20%), FII outflow (>₹3000Cr), PCR extreme (>1.5 or <0.6), Bull/Bear extreme (<20 or >80).

| Function | What It Does |
|----------|--------------|
| `check_thresholds()` | Checks current values against all thresholds |
| `format_threshold_alerts()` | Formats breach alerts with action context |
| `run_threshold_check()` | Full threshold check with context |

## Phase 11: DB Functions (`src/db.py`)

New functions: `save_daily_market_snapshot()`, `get_daily_market_snapshots()`, `get_snapshot_metric_history()`, `save_correlation()`, `get_correlations()`, `log_signal_accuracy()`, `get_signal_accuracy()`, `log_divergence()`, `get_recent_divergences()`, `get_bot_state()`, `set_bot_state()`.

## Phase 12 Session 1: Bug Fixes

| Fix | File | What Changed |
|-----|------|-------------|
| `options_snapshots` purge | `db.py` | Added 7-day purge to `purge_old_data()` |
| NSE session shared | `fii_tracker.py`, `options_engine.py` | Refactored to use `nse_session.nse_get()` |
| Execution time tracking | `market_intel.py` | Added 6 timing points + 4-min warning |
| yfinance sleep | `data_fetcher.py` | Added `time.sleep(1)` between chunks |
| Weight dampening | `prediction_tracker.py` | ±10% max change/week, persisted to `bot_state` |
| Correlation staleness | `rolling_quant.py` | Added "computed [date]" to output |

## Phase 12 Session 2: CFTC + Factors + Sector RS

### CFTC COT Fetcher (`src/cftc_fetcher.py`)

| Function | What It Does |
|----------|--------------|
| `fetch_cftc_data()` | Fetch weekly CFTC positioning data |
| `fetch_cftc_summary()` | Positioning analysis for 5 contracts (USD, EUR, JPY, Gold, Crude) |
| `run_cftc_analysis()` | Full pipeline — percentile ranking, trend, contrarian signals |
| `format_cftc_summary()` | Formats for AI prompt |

Key insight: Commercials = smart money (tend to lead reversals). Speculators = trend-followers (extreme positioning = mean reversion signal).

### Factor Attribution Engine (`src/factor_engine.py`)

| Function | What It Does |
|----------|--------------|
| `compute_momentum_factor()` | 12M/3M/1M return regime |
| `compute_value_factor()` | P/E percentile vs history |
| `compute_quality_factor()` | ERP (earnings yield vs risk-free rate) |
| `compute_size_factor()` | Large vs small cap breadth proxy |
| `run_factor_attribution()` | All 4 factors + dominant factor |
| `format_factor_attribution()` | Formats for AI prompt |

Tells you WHY the market moved, not just that it moved.

### Sector RS Quantified (`src/sector_rs.py`)

| Function | What It Does |
|----------|--------------|
| `fetch_sector_data()` | Batch fetch 11 Nifty sector indices |
| `compute_relative_strength()` | RS score 0-100 vs Nifty 50 (1W/1M/3M weighted) |
| `run_sector_rs_analysis()` | Full pipeline — ranked sectors + rotation signal |
| `format_sector_rs()` | Formats top 3 + bottom 3 + full table |

Sector rotation: defensive (FMCG/Pharma) = risk-off, cyclical (Metal/Auto/Energy) = risk-on.

## Phase 12 Session 3: Earnings + Internals + Multi-Expiry

### Earnings Surprise Tracker (`src/earnings_tracker.py`)

| Function | What It Does |
|----------|--------------|
| `fetch_earnings_calendar()` | Upcoming Nifty 50 earnings (yfinance) |
| `fetch_earnings_history()` | Historical EPS actual vs estimate |
| `fetch_post_earnings_move()` | Stock move 5 days before/after earnings |
| `compute_surprise_stats()` | Avg move per surprise magnitude |
| `run_earnings_analysis()` | Full pipeline — upcoming + historical analysis |

Key insight: Compare current IV-implied move vs historical avg move. If IV implies ±3% but historical avg is ±1.5%, options are pricing MORE uncertainty than normal.

### Market Internals Composite (`src/market_internals.py`)

| Function | What It Does |
|----------|--------------|
| `score_ad_ratio()` | A/D ratio → 0-100 health score |
| `score_high_low()` | New High/Low ratio → 0-100 |
| `score_volume_breadth()` | Advancing vs declining volume → 0-100 |
| `score_ma_breadth()` | % stocks above 20/50/200MA → 0-100 |
| `score_mcclellan()` | McClellan oscillator → 0-100 |
| `compute_internals_composite()` | Weighted composite of all 5 |
| `run_internals_analysis()` | Full pipeline + classification |

Score < 30 = rally on weak internals (unsustainable). Score > 70 = healthy broad rally.

### Options Multi-Expiry (`src/options_multi.py`)

| Function | What It Does |
|----------|--------------|
| `analyze_multi_expiry()` | Term structure, gamma, pinning across expiries |
| `_bs_gamma()` | Black-Scholes gamma for pinning analysis |
| `run_multi_expiry_analysis()` | Full pipeline — 3 expiries analyzed |

Near expiry = high gamma = pinning. Far expiry = low gamma = directional bets. Term structure backwardation = fear.

## Phase 12 Session 4: Low-Priority Polish (7 modules)

### Cross-Asset Beta Tracker (`src/beta_tracker.py`)

| Function | What It Does |
|----------|--------------|
| `compute_rolling_beta()` | Rolling 90-day beta between Nifty and any asset |
| `compute_all_betas()` | Betas for DXY, Gold, Brent, USD/INR, VIX |
| `format_betas()` | Formats for AI prompt |

Beta > 1 = Nifty amplified moves. Beta < 0 = Nifty moves opposite. High beta spike = macro-driven market.

### FII Concentration HHI (`src/fii_concentration.py`)

| Function | What It Does |
|----------|--------------|
| `compute_hhi()` | Herfindahl-Hirschman Index of flow distribution |
| `compute_fii_concentration()` | HHI from FII bulk/block deals |
| `format_fii_concentration()` | Top 5 stocks + concentration alert |

HHI > 2500 = highly concentrated (fragile). HHI < 1000 = widely distributed (sustainable).

### Volatility Regime Persistence (`src/vol_persistence.py`)

| Function | What It Does |
|----------|--------------|
| `compute_regime_persistence()` | Track how long VIX stays in regime + predict remaining |
| `format_vol_persistence()` | Current streak vs historical avg |

"VIX HIGH for 12 days, avg 18d — overextended, regime shift likely."

### Derivative Turnover Ratio (`src/turnover_ratio.py`)

| Function | What It Does |
|----------|--------------|
| `compute_turnover_ratio()` | F&O volume / cash volume |
| `format_turnover()` | Speculation signal + bubble detection |

Ratio > 3x = bubble territory. Ratio > 2x = retail FOMO.

### Data Staleness Detection (`src/staleness_detector.py`)

| Function | What It Does |
|----------|--------------|
| `check_data_staleness()` | Single source freshness check |
| `check_batch_staleness()` | Multiple sources at once |
| `format_staleness()` | Alerts for stale data |

Flags data older than threshold. Prevents analysis on stale NSE data.

### Reversal Pattern Detector (`src/reversal_patterns.py`)

| Function | What It Does |
|----------|--------------|
| `detect_v_bottom()` | 3+ down days + sharp reversal |
| `detect_failed_breakout()` | New 20D high → close back below |
| `detect_exhaustion_gap()` | Gap >1% + volume spike |
| `detect_mean_reversion()` | Price >3% above/below 20MA |
| `detect_all_patterns()` | Run all detectors |

### API Failure Budget (`src/api_budget.py`)

| Function | What It Does |
|----------|--------------|
| `record_api_call()` | Log success/failure per source |
| `get_api_reliability()` | Success rate over N days |
| `format_api_budget()` | Alert if reliability < 90% |

Tracks persistent failure rates. Alerts if NSE/YFinance reliability drops.

## Phase 13: Coherence Engineering

### Signal Arbitrator (`src/signal_arbitrator.py`)

| Function | What It Does |
|----------|--------------|
| `arbitrate_signals()` | Weighted consensus from 6 composite scores |
| `normalize_signal()` | Normalize different signal types to 0-100 |
| `format_master_signal()` | Master signal with contradiction context |

Clusters signals into Structural (Bull/Bear, Internals, Factor) vs Sentiment (Fear/Greed, PCR, VIX). Detects contradictions (spread >40pts). Output: single coherent MASTER SIGNAL.

### Prompt Engine (`src/prompt_engine.py`)

| Function | What It Does |
|----------|--------------|
| `score_block_relevance()` | Score each block 0-4 by today's relevance |
| `rank_blocks()` | Rank blocks by relevance score |
| `assemble_coherent_prompt()` | Dynamic assembly: top 4 full, rest compressed |
| `check_prompt_length()` | Verify prompt within AI attention window |

Prevents attention dilution. AI receives RIGHT 450 words, not random 450 words.

### Output Validator (`src/output_validator.py`)

| Function | What It Does |
|----------|--------------|
| `extract_claims()` | Extract directional tone, numbers, flow direction from AI text |
| `validate_output()` | Compare claims against ground truth data |
| `validate_against_ground_truth()` | Check tone vs Bull/Bear, flow vs FII, numbers vs Nifty |

Pre-send consistency check. Major contradiction → discard AI output → send raw data fallback.

### Validation Helper (`src/validation_helper.py`)

| Function | What It Does |
|----------|--------------|
| `validate_and_send()` | Wraps validate_output with ground_truth construction. Used by morning_brief.py and evening_report.py to validate ALL AI outputs |

Ensures stale levels, hallucinated %, and advice detection apply to every Telegram message — not just market_intel.py output.

## Phase 14: Simplicity Engine

### Simplicity Engine (`src/simplicity_engine.py`)

| Function | What It Does |
|----------|--------------|
| `generate_simple_lines()` | Translate all signals into max 4 emoji-tagged one-liners |
| `translate_fii_signal()` | FII selling 8 days → "🔴 Foreign selling 8 days — tiring" |
| `translate_contradiction()` | Contradiction HIGH → "⚠️ Signals fighting — wait" |
| `translate_internals()` | Score 72 → "🟢 Market breadth healthy" |
| `translate_factor()` | BEARISH → "🔴 Expensive stocks getting punished" |
| `translate_confidence()` | Score 38 → "🟡 Low conviction — small bets only" |
| `translate_hhi()` | HHI 5312 → "⚠️ Few big players — one exit = sharp move" |
| `translate_turnover()` | 3.2x → "🔴 Retail gambling — top likely near" |
| `translate_pcr()` | PCR 1.4 → "🔴 Heavy put bracing for drop" |
| `format_simple_block()` | Formats as Block -1 (always first in prompt) |

This is what separates institutional intelligence from raw data. Every number → feeling + action.

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

## Phase 15: Output Quality & MF Intelligence

### Mechanism Map (`src/mechanism_map.py` — NEW)

Maps macro events to India sector impact. 24 mechanisms defined (21 macro + 3 geopolitical: hormuz_risk, iran_conflict, sanctions_tariff).

| Function | What It Does |
|----------|--------------|
| `detect_triggered_mechanisms()` | Check macro anchors against thresholds, return triggered mechanisms |
| `format_mechanism_triggers()` | Format triggered mechanisms with BEARISH/BULLISH sectors |
| `get_mechanism_for_news()` | Word-boundary keyword matching for news headlines |
| `get_india_linkage_for_event()` | Get concise India impact string for a mechanism |

Mechanisms: oil_spike/crash, dxy_strength/weakness, china_pmi_miss/stimulus, us_yield_rise/fall, gold_rally, vix_spike/collapse, fed_hawkish/dovish, boj_hike, rbi_rate_cut/hike, inr_depreciation/appreciation, copper_rally/crash, hyg_stress.

### Market State Dashboard Redesign (`src/formatters.py`)

| Change | What |
|--------|------|
| Always shows lean | Bullish/Bearish/Neutral (never "no edge") |
| Conviction level | HIGH/MEDIUM/LOW from signal alignment |
| Key Evidence | FII streak, DII absorption, VIX regime with numbers |
| Conflicting Signals | PCR contrarian, VIX complacency, FII/DII divergence |
| Signal Alignment Bar | Text-based progress bar (10 chars) |
| Phase labels | "Transition — waiting for catalyst" instead of "Mixed signals" |

### News India Linkage (`src/formatters.py` — `_format_news_line()`)

Auto-detects mechanism from headline, adds India impact:
```
⦿ Fed signals rate hike (0.25%). (Reuters)
   → FII outflow risk, INR depreciation | BEARISH: All EM assets | BULLISH: IT
```

Word-boundary matching prevents false positives ("fed" ≠ "federal"). Exception-safe (catches all exceptions to isolate mechanism failures).

### Pre-Market Alerts Redesign (`jobs/morning_brief.py`)

| Change | What |
|--------|------|
| Sector grouping | `🔴 STEEL: TATASTEEL -3.3% (Vol 3.2x), JSWSTEEL -2.8%` |
| Sector WHY context | News headlines matched to sectors via SECTOR_KEYWORDS |
| Lowered threshold | 3.0% → 2.5% |
| Volume ratio | Shows `Vol 2.3x` instead of just "Volume spike!" |

### Morning Brief + News Redesign

| File | Change |
|------|--------|
| `src/ai_engine.py` | `morning_brief_prompt()` restructured for editorial ⦿ bullets |
| `src/formatters.py` | `_format_news_line()` uses ⦿ editorial style + India linkage |
| `config/master_prompt.txt` | Added editorial news instruction + NEWS section in output format |

### MF Intelligence — Two Layers

**Layer 1: Daily Inferred** (`compute_mf_intelligence()`) — No DB dependency, works on Day 1.
| Score | Inputs | What It Tells You |
|-------|--------|-------------------|
| Retail Participation | Smallcap ratio, VIX, DII net | Retail confidence, SIP additions likely |
| Institutional Quality | DII absorption, DII net, VIX | MF deploying, redemption pressure |
| Category Rotation | Smallcap/largecap, VIX, gold | Equity growth vs defensive rotation |

**Layer 2: AMFI Behavior Index** (`compute_mf_behavior_index()`) — Requires 2+ months of DB data.
| Sub-Signal | What It Measures |
|------------|-----------------|
| SIP Momentum | MoM SIP change — retail conviction |
| Retail Rotation | Small Cap / Large Cap ratio — FOMO vs defensive |
| Redemption Pressure | Outflow categories + DII selling — forced selling risk |
| Thematic FOMO | Sectoral fund spike vs 3M avg — contrarian bearish |
| Defensive Shift | Debt+Gold vs equity ratio — risk-off signal |

**Design principle:** AMFI monthly data is lagging. Infer MF behavior daily from signals already fetched. AMFI confirmed data, when available, prepends to inferred signals.

### MF Flow Signals (`src/formatters.py` — `format_mf_flows()`)

Enhanced AMFI category flow formatter (evening Block 10):

| Signal | What |
|--------|------|
| Rotation Index | Small Cap / Large Cap ratio (>2x = bubble signal) |
| Risk Appetite | Equity vs Debt+Gold flows (risk-on/off) |
| Streak Detection | 3+ consecutive months inflow/outflow per category |

---

## Project Status: SHIPPED

**Phase 0-23 complete.** 55+ modules, 260+ functions, 14 cron jobs, 16 Supabase tables. Rating: 8.5/10.

### What's Built
| Phase | Modules | Key Features |
|-------|---------|-------------|
| 0-7 | Core infra, data, analysis, output | Telegram, AI, data fetchers, options, valuation, technicals, formatters |
| 8-10 | Institutional macro, regime, SWF | 16 macro signals, regime detection, SWF tracker, top movers |
| 11 | Rolling quant engine | Percentiles, divergences, scenarios, correlations, seasonal, relative value |
| 12 | 13 new modules | CFTC, factors, sector RS, earnings, internals, multi-expiry, beta, HHI, vol persistence, turnover, staleness, reversal patterns, API budget |
| 13 | 7 coherence modules | Signal arbitrator, prompt engine, output validator, FII cross-ref, daily state, temporal context, confidence engine |
| 14 | Simplicity engine | Emoji-tagged one-liners for new investors |
| 15 | Output quality + MF intelligence | Mechanism map, dashboard redesign, sector alerts, editorial news, India linkage, MF Behavior Index, daily MF inference |
| 16 | P2-P5 + bug fixes | Temporal duration, FII matrix, percentile fix, MF pace, 9 bug fixes |
| 18 | Consequence Layer | `consequence_engine.py` (multiplier table, 10 variables), compound consequences (USDINR amplifier), Indian Basket approximation, net market impact, output validator commodity check |
| 19 | Master Signal Diagnostic | Gap analysis, confidence split, score trending, consequence layer, regime detection (3 regimes), accumulation/distribution signals, pre-send checklist (10 gates), block validator (4-layer check) |
| 20 | Final Polish | USDINR amplifier on consequences, Gold-VIX divergence (6th type), prediction accountability in weekly digest (Brier + per-signal hit rates), signal weights injected into AI prompt |
| 23 | Risk Mood + Pre-computed Interpretations | Gold/Copper in risk composite, calibrated 0-100 mood bar, graceful degradation (ComputeBudget), consequence price injection, word-boundary sector matching, VIX/FII/Absorption pre-computed interpretations, 26-pattern validator, output-type scoping |

### Data Foundation
- `daily_market_snapshot`: 261 rows (1 year backfill from yfinance)
- `mf_flows`: 12 AMFI categories (live fetch)
- data_quality tiers: 'real' (daily cron), 'estimated_from_prices' (30d), 'historical_price_based' (older)
- All percentiles valid (176+ rows)

### Key Architecture Decisions
- Consequence engine: static multiplier table, zero DB dependency
- Master Signal: structural vs sentiment cluster gap analysis
- Trending: yesterday always valid, 30D/percentile needs ≥10 real rows
- Regime detection: pre-labels before AI writes narrative
- Confidence: split into directional vs regime confidence
- Pre-send: 10 hard gates before Telegram send

### Phase 21: Output Quality Overhaul (25 fixes)

**Root cause:** AI was filling gaps with invention instead of saying "insufficient data". Python 8.5/10, AI output 5.5/10. Fix: constrain AI + validate output + detect silent failures.

**Quality trajectory:** 5.6/10 → 8.2/10 → 8.5/10 (floor = ceiling)

#### Phase 1: Core Fixes (8)
| Fix | File | What |
|-----|------|------|
| Absorption math | `formatters.py` | 0% → 123% (same-day flows, not weekly) |
| Stale level gate | `output_validator.py` | Rejects levels >15% from Nifty (15000-30000 range) |
| Prompt constraints | `master_prompt.txt` | ABSOLUTE CONSTRAINTS section (no %, no advice, no invented levels) |
| SYSTEM_PROMPT | `ai_engine.py` | Removed "probability-weighted scenarios (bull/bear/base with %)" |
| Advice filter | `output_validator.py` | 19 keywords: long/short/buy/sell/consider adding/investors should/recommend |
| Hallucinated % | `output_validator.py` | Bidirectional regex: "55% bullish" + "bullish 55%" + "55 percent bull" |
| Signal transparency | `formatters.py` | Individual signals with 🟢🔴🟡 icons, unfired reasons, direction counts |
| Geopolitical | `mechanism_map.py` | hormuz_risk, iran_conflict, sanctions_tariff mechanisms |

#### Phase 2: Integrity (5)
| Fix | File | What |
|-----|------|------|
| Fallback completeness | `output_validator.py` + `market_intel.py` | 12 keys: regime, absorption, dii_net, vix_percentile, signal summary |
| VIX percentile-aware | `formatters.py` | 78th %ile = ELEVATED, not NORMAL (percentile > absolute threshold) |
| FII persistent label | `formatters.py` | CV-based: "persistent outflows" when CV < 0.15 across 4 weeks |
| S/R rendering | `technical_analysis.py` | support_2/resistance_2 now rendered (was computed but hidden) |
| Direction counts | `formatters.py` | "🟢1 🔴1 🟡2" instead of opaque "1/4 aligned" |

#### Phase 3: Polish (3)
| Fix | File | What |
|-----|------|------|
| Extended regex | `output_validator.py` | "55% bullish", "probability of 55%", "55 percent bull" |
| Fallback regime | `output_validator.py` | Regime + absorption + "Signal: Mixed — no directional call" |
| Streak maturity | `formatters.py` | "8d streak — mature" (avg 8.2d from real data) |

#### Data Guards (3)
| Fix | File | What |
|-----|------|------|
| 5-day stats | `formatters.py` | "accumulating (X/5 days)" when <3 days |
| 4-week trend | `formatters.py` | Suppress when <2 weeks, "accumulating" for 2-3 weeks |
| Dashboard total | `formatters.py` | Guard on fii_4w_avg validity (NaN → "4W avg accumulating") |

#### Floor Levers (3)
| Fix | File | What |
|-----|------|------|
| Source health | `market_intel.py` | Replaces broken staleness detector (was using datetime.now()). Checks 9 blocks + 3 data objects. Failed sources flagged in AI prompt. |
| AI hardening | `output_validator.py` | 6 new advice keywords + 8 confidence phrases ("high probability", "likely to", "will rise") |
| Cross-block consistency | `output_validator.py` | 3 checks: absorption vs regime label, VIX %ile vs tone, net impact vs narrative |

#### Critical Bug Fixes (2)
| Fix | File | What |
|-----|------|------|
| Severity downgrade | `output_validator.py` | MINOR consistency issues no longer overwrite MAJOR severity from advice/hallucination |
| Variable name | `market_intel.py` | `fii_context` (always None) → `fii_ctx` (actual data) in source health check |

#### Data Foundation
- `fii_dii_flows`: 52 rows backfilled (March-May 2026) via `backfill_fii_dii.py`
- Rolling windows now real: 5-day stats, 4-week trend, z-score, streak avg
- `backfill_fii_dii.py`: one-time script, reads `sql/fii-dii-data.json`

#### Validator Coverage (26 patterns)
| Category | Patterns | Severity |
|----------|----------|----------|
| Hallucinated % | 55% bull, 55% bullish, probability of 55%, 55 percent bull | MAJOR |
| Hallucinated confidence | high probability, likely to, will rise/fall, expected to rise/fall | MAJOR |
| Trade advice | long on, short the, buy, sell, consider adding, investors should, recommend, expect Nifty/market to | MAJOR |
| Stale levels | Nifty level >15% from spot (15000-30000 range) | MAJOR |
| Commodity mismatch | Brent/Gold/USDINR >15% from actual | MAJOR |
| Consistency | absorption vs regime, VIX %ile vs tone, net impact vs narrative | MINOR |

#### Output Architecture
```
Python computes → AI narrates → Validator checks → Send or Fallback
```
- AI cannot invent: percentages, levels, probabilities, advice, predictions
- Fallback shows: regime, absorption, signal summary (not just raw numbers)
- Source health: missing blocks flagged explicitly, never silently omitted
- Cross-block: absorption/VIX/flow contradictions caught before send

### Phase 22: Output Quality + News Intelligence Overhaul (9 fixes)

**All fixes verified via `test_telegram_output.py` — 9/9 PASS.**

#### P0: Calculation Fixes (4)
| Fix | File | What | Before | After |
|-----|------|------|--------|-------|
| VIX → Sentiment inversion | `signal_arbitrator.py:42` | `normalize_to_100(50 - value, 13, 47)` | VIX 22 → 76 BULLISH | VIX 22 → 44 BEARISH |
| Absorption centralization | `formatters.py` | `compute_absorption(fii, dii)` helper, 4 call sites | Block 4: 123% ✅, Dashboard: 0% ❌ | All paths use same function |
| Ordinal suffixes | `rolling_quant.py`, `formatters.py`, `valuation_engine.py` | `_ordinal()` everywhere | "73th percentile" | "73rd percentile" |
| FII percentile fallback | `formatters.py:85-95, 132-142` | Falls back to `fii_dii_flows` table | "insufficient data" for FII | Uses FII/DII table data |

#### P1: Reasoning Fixes (2)
| Fix | File | What |
|-----|------|------|
| ERP vs P/E bridge | `formatters.py:507`, `valuation_engine.py:240` | When P/E < 40th %ile AND ERP < 0: "P/E historically cheap but ERP negative → bonds more attractive" |
| Validation on ALL AI outputs | `src/validation_helper.py` (new), `jobs/morning_brief.py`, `jobs/evening_report.py` | `validate_and_send()` wrapper with ground-truth comparison catches stale levels (17,800 when Nifty=23,659) |

#### P2: News Quality Fixes (3)
| Fix | File | What |
|-----|------|------|
| News staleness detection | `src/validator.py` | `.news_seen.json` cache (24h TTL), tags `seen_before`, `freshness_score` 0-10. Formatter shows `[previously covered]`, `[stale (3/10)]` |
| India linkage enforcement | `src/validator.py` | `_check_india_linkage()` scores: India=10, macro=7, sector=6, no-impact=3. Filters <5 unless Bloomberg/Reuters. Formatter shows `[Global]` tag |
| Block deal pattern recognition | `src/insider_tracker.py` | `_detect_deal_patterns()` finds: promoter→institutional transfers, cross-trades at matched price, accumulation. `format_insider_summary()` adds `🔍 Pattern Analysis` section |

### What's Left (Phase 23)
- Inline glossary for Tier 1 terms (PCR, GEX, DXY explained on first use)
- Weekly self-audit output (bot performance metrics in Sunday digest)
- Brier calibration fix (needs more prediction data)
- Percentile doesn't count ties — biased low

### Phase 23: Risk Mood + Consequences + Degradation + Pre-computed Interpretations

**All features validated with live Supabase — `test_supabase_full.py` 20/20 PASS, `test_all_outputs.py` 7/7 sections PASS.**

#### Multi-Signal Risk Mood
| Fix | File | What |
|-----|------|------|
| Gold/Copper activation | `context_engine.py:955-1086` | Added Gold weekly change (fear proxy) and Copper weekly change (growth proxy) to global risk composite. Each contributes -1 to +1 to score |
| Risk mood 0-100 | `context_engine.py` | `risk_mood = min(100, max(0, round(50 + score * 100 / 16)))`. Calibrated: moderate stress = 31/100, not 10/100 |
| Mood bar visual | `formatters.py:2271-2284` | `format_market_posture()` shows █░ progress bar with emoji color coding (65+ green, <35 red) |
| Copper/Gold context | `context_engine.py:685-697` | Emoji-level annotation (🔴 recession, 🟠 growth slowing, 🟢 healthy growth) |

#### Graceful Degradation Chain
| Fix | File | What |
|-----|------|------|
| ComputeBudget | `src/compute_budget.py` (NEW, 191 lines) | `ComputeBudget` class: time tracking, stage management, skip decisions. Progressive thresholds: 75% drops blocks 9,10; 90% drops 3,7,8; 95% only 0,1,2 survive |
| Budget wiring | `jobs/market_intel.py` | Budget initialization, block skipping, health logging before AI call |

#### Consequence Engine Price Injection
| Fix | File | What |
|-----|------|------|
| Price in consequence strings | `consequence_engine.py` | `compute_consequence()` now includes `current_price` and `change_pct` in return dict. `format_consequence_line()` injects price: "⚠️ Brent $85 (-3.0%): CAD impact..." |

#### Sector WHY Logic Refinement
| Fix | File | What |
|-----|------|------|
| Word-boundary matching | `jobs/morning_brief.py:244-249` | Replaced substring matching with compiled regex: `re.compile(rf"(?i)\b{pat}\b")`. No more false positives ("fed" ≠ "federal", "ai" ≠ "main") |

#### Pre-computed Interpretations
| Fix | File | What |
|-----|------|------|
| VIX interpretation | `src/metrics.py` + `context_engine.py:2679-2691` | Computes VIX risk level + narrative once, stores in ctx. Validated: 3 regimes (EXTREME/HIDDEN/NORMAL) |
| FII interpretation | `src/metrics.py` + `context_engine.py` | Detects persistent selling, transition signals, conviction level. With Supabase: "FII heavy single-day selling (₹-4,357Cr). Moderate selling." |
| DII absorption interpretation | `src/metrics.py` + `context_engine.py` | Flags broad distribution, absorption sustainability, DII fatigue risk. With Supabase: "DII absorbing 115% of FII outflow — more than offsetting." |
| AI prompt injection | `context_engine.py:771-791` | All 3 interpretations formatted into `format_context_for_ai_full()`. AI receives conclusions, not raw numbers |
| Dashboard integration | `formatters.py:574-575, 1874-1875` | FII/Absorption interpretations used in flow formatting + market state dashboard |

#### Validation Pipeline
| Fix | File | What |
|-----|------|------|
| `market_intel` validation config | `validation_helper.py:112-117` | Added `market_intel` to `_OUTPUT_TYPE_CONFIG` with all 4 checks (stale_level, hallucinated_pct, advice, confidence) |
| Output-type scoping | `validation_helper.py:194-259` | `_validate_with_output_type()` filters checks per output type. Midday passes hallucinated %, weekly rejects |
| Retry logic | `validation_helper.py:173-191` | Targeted retry on MAJOR violation — builds specific retry_instruction telling AI exactly what to fix |

#### Bugs Fixed During Supabase Validation
| Fix | File | What |
|-----|------|------|
| `get_market_narrative` crash | `context_engine.py:428` | `dii_absorbed` was numeric (not string) — added numeric-to-label conversion: `≥0.8→High, ≥0.4→Medium, <0.4→Low` |
| `format_market_state_dashboard` crash | `formatters.py:1877-1891` | `fii_net`, `streak`, `direction` initialized at top from `flow_metrics` or `fii_context` — available for all evidence branches |
| Test API mismatches | `test_supabase_full.py` | Fixed `db_client→get_client`, `total_seconds→max_seconds`, `format_consequence_line` signature |

### Structural Ceiling
Real-time data + alternative data = need paid infrastructure. Not buildable free.

### Supabase Data State (as of 2026-05-26)
| Table | Rows | Status |
|-------|------|--------|
| `fii_dii_flows` | 37 | Mar-May 2026, latest 2026-05-22 |
| `daily_market_snapshot` | 211 | Sufficient for rolling quant (≥100) |
| `valuation_history` | 9 | PE=20.71, PB=3.28 |
| `market_breadth_history` | 1 | Needs more data |
| `watchlist` | 11 stocks | Active |

### Test Commands
- `python3 test_all_outputs.py` — 7 sections, 26 patterns, syntax + imports
- `.venv/bin/python3 test_supabase_full.py` — 20 Supabase-dependent feature checks with live data
- Both require: `SUPABASE_URL` + `SUPABASE_KEY` env vars from `../apikeys.txt`
