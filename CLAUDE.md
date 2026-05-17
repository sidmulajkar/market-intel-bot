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
