# CLAUDE.md

AI-powered Indian market intelligence bot — 14 cron jobs, daily Telegram analysis (text + heatmaps).

**Stack:** Python, Supabase (28 tables + 2 unused), Telegram, Groq/Google AI, NSE/AMFI/SEBI, FinBERT.

**Core principle:** Python computes conclusions. AI writes narrative only. AI cannot invent percentages, levels, probabilities, advice, or predictions.

**Output pipeline:** Python computes → AI narrates → Validator checks → Send or Fallback

---

## Jobs (GitHub Actions, stateless, ~30s actual, 10-20min timeout)

| Time | Job | Purpose |
|------|-----|---------|
| 5 AM | `fii_dii_fetch.py` | NSE FII/DII → Supabase |
| 7 AM | `market_intel.py morning` | Full 11-block AI analysis |
| 8 AM | `morning_brief.py` | Heatmaps + regime card + alerts |
| 9:15 AM | `market_open.py` | Opening brief + consequence layer |
| 12:30 PM | `midday_scan.py` | Regime scanner (skip gate on big moves) |
| 3:30 PM | `market_close.py` | EOD summary + movers |
| 6 PM | `market_intel.py evening` | Full analysis + derivatives |
| 8 PM | `evening_report.py` | US session heatmap + outlook |
| Sunday | `weekly_digest.py` | Scorecard + institutional signals |

---

## Key Modules (by layer)

**Data:** `data_fetcher` (yfinance/Finnhub/NSE/AMFI), `nse_session` (5-min TTL), `db` (Supabase CRUD+purge), `macro_fetcher`, `cftc_fetcher`

**Context:** `context_engine` (Bull/Bear 8-signal, global risk, phase classifier), `signal_arbitrator` (gap analysis, master signal), `mechanism_map` (24 macro→India mappings), `consequence_engine` (India impact multipliers + regime impact vs 252-day baseline)

**Derivatives:** `options_engine` (PCR, max pain, GEX, skew), `options_multi` (term structure), `fii_derivatives` (F&O participant OI)

**Valuation:** `valuation_engine` (P/E, P/B, risk premium, reverse DCF), `rolling_quant` (percentiles, divergences, correlations, scenarios)

**Intelligence:** `prompt_engine` (relevance scoring), `quant_enrichment` (Fear/Greed, factor attribution), `prediction_tracker` (Brier scores, dynamic weights)

**Quality:** `output_validator` (26 patterns), `block_validator` (10 gates), `validation_helper`, `validator` (news trust), `staleness_detector`, `compute_budget` (graceful degradation)

**Output:** `formatters` (11 blocks), `telegram_sender`, `heatmap_generator`, `sector_heatmap`, `commodity_heatmap`, `technical_analysis`, `metrics`, `simplicity_engine`

**Specialized:** `insider_tracker`, `shareholding_tracker`, `fii_sector`, `fii_concentration`, `earnings_tracker`, `beta_tracker`, `vol_persistence`, `turnover_ratio`, `factor_engine`, `sector_rs`, `market_internals`, `reversal_patterns`, `threshold_alerts`, `api_budget`

---

## AI Routing (`src/ai_engine.py`)

- `ai.analyze("fast")` → Groq (llama-3.3-70b) → Google fallback
- `ai.analyze("volume")` → Google (gemini-2.0-flash) → Groq fallback
- `ai.sentiment(text)` → FinBERT via HuggingFace API
- Max tokens: 1000, Temperature: 0.3
- Strong-conviction fallback triggers when AI exhausted AND 2+ extremes: USDINR≥90, Brent≥90, VIX≥20, Gold≥4000, FII streak≥3

---

## Key Patterns

- **Macro sanity guards (two-layer):** Wide absurdity bounds (USDINR 60-200, Brent 20-300, Gold 500-10000) → reject typos. Daily-change threshold (forex 3%, VIX 15%, yields 10%, commodities 8%) → catch corruption.
- **Consequence engine regime impact:** When price deviates >5% from 252-day baseline (DXY >4%, VIX >3%), shows baseline deviation instead of daily noise. Severity emojis: 📌 neutral, ⚠️ elevated/high, 🚨 stress/extreme. Signed values use `{:+.1f}`.
- **NSE APIs:** Require session cookies — use `nse_session.py`. Options chain: `/api/option-chain-indices`. Valuation: `/api/allIndices`.
- **All formatters return `""` on failure.** NaN handled via `_safe_float()`.
- **Pre-computed interpretations:** `run_contextualization()` computes VIX/FII/Absorption once, stores in `ctx`.
- **Signal weights:** Dynamic from accuracy log (>65% → ×1.3, <45% → ×0.7).

---

## Macro Anchors

`USDINR=X` · `BZ=F` · `GC=F` · `^INDIAVIX` · `DX-Y.NYB` · `^TNX` · `^VIX` · `HYG` · `CL=F`

---

## Supabase Tables (28 referenced, all exist)

**Core:** `watchlist`, `mf_watchlist`, `bot_state`, `sent_alerts`, `market_snapshots`

**Flows:** `fii_dii_flows`, `mf_flows`, `fii_institution_tracker`

**Market:** `daily_market_snapshot`, `market_breadth_history`, `options_snapshots`, `macro_anchor_snapshots`, `valuation_history`, `market_state`

**Intelligence:** `daily_predictions`, `prediction_outcomes`, `signal_accuracy_log`, `correlation_matrix`, `divergence_log`, `forecast_log`, `analytics_ledger`

**Analytics:** `factor_scores_history`, `sector_rs_history`, `earnings_surprises`, `market_internals_history`, `cftc_positioning_history`, `analysis_cache`, `shareholding_snapshots`

SQL schema: `sql/create_new_tables.sql`

---

## Env Vars

| AI Jobs | Data Jobs |
|---------|-----------|
| `GROQ_API_KEY`, `GOOGLE_AI_KEY` (not `GOOGLE_API_KEY`), `HF_KEY`, `FINNHUB_KEY` | `SUPABASE_URL`, `SUPABASE_KEY` |
| `SUPABASE_URL`, `SUPABASE_KEY` | `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` |
| `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` | |

---

## Project Status: SHIPPED (Phase 0-28)

**55+ modules, 260+ functions, 14 cron jobs, 28 Supabase tables.**

### Architecture Decisions
- Consequence engine: static multiplier table, zero DB dependency
- Master Signal: structural vs sentiment cluster gap analysis
- Regime card: unified output (replaces Dashboard + Master Signal + MF Intelligence)
- Pre-send: 10 hard gates before Telegram
- Dynamic signal weights from accuracy log

### Remaining
- Inline glossary for Tier 1 terms (PCR, GEX, DXY)
- Weekly self-audit (bot metrics in Sunday digest)
- Brier calibration (needs more prediction data)
- Percentile doesn't count ties → biased low
- `fii_streak` vs `fii_streak_days` key inconsistency
- `google.generativeai` deprecated → migrate to `google.genai`

### Test Commands
- `.venv/bin/python3 test_all_outputs.py` — 7 sections, 26 patterns
- `.venv/bin/python3 test_supabase_full.py` — 20 Supabase feature checks
- Both require `SUPABASE_URL` + `SUPABASE_KEY` from `../apikeys.txt`
