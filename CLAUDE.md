# CLAUDE.md

AI-powered Indian market intelligence bot — 14 cron jobs, daily Telegram analysis (text + heatmaps).

**Stack:** Python, Supabase (28 tables + 2 unused), Telegram, Groq/Google AI, NSE/AMFI/SEBI, FinBERT.

**Core principle:** Python computes conclusions. AI writes narrative only. AI cannot invent percentages, levels, probabilities, advice, or predictions.

**Output pipeline:** Python computes → AI narrates → Validator checks → Send or Fallback

---

## Jobs (GitHub Actions, stateless)

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

**Workflow config (15 files in `.github/workflows/`):** All use `actions/cache@v4` keyed on `hashFiles('requirements.txt')` + Python version, `timeout-minutes: 5` at job level + `timeout-minutes: 4` on run steps. `setup-python` step has `id: python` so `steps.python.outputs.python-version` resolves correctly in cache keys. Target: **<2 min runtime** (current ~3 min post-optimization).

---

## Key Modules (by layer)

**Data:** `data_fetcher` (yfinance batch download for 14 macro anchors, parallel ThreadPoolExecutor fallback), `nse_session` (5-min TTL, circuit-broken), `db` (Supabase CRUD+purge, non-blocking field warnings), `macro_fetcher`, `cftc_fetcher`

**Context:** `context_engine` (Bull/Bear 8-signal, global risk, phase classifier), `signal_arbitrator` (gap analysis, master signal), `mechanism_map` (24 macro→India mappings), `consequence_engine` (India impact multipliers, regime impact vs 252-day baseline, 30% variance cap, WTI/Brent coherence check)

**Derivatives:** `options_engine` (PCR, max pain, GEX, skew), `options_multi` (term structure), `fii_derivatives` (F&O participant OI)

**Valuation:** `valuation_engine` (P/E, P/B, risk premium, reverse DCF), `rolling_quant` (percentiles, divergences, correlations, scenarios)

**Intelligence:** `prompt_engine` (relevance scoring), `quant_enrichment` (Fear/Greed, factor attribution), `prediction_tracker` (Brier scores, dynamic weights, override-aware scorecard vs `final_regime`)

**Quality:** `output_validator` (26 patterns), `block_validator` (10 gates), `validation_helper` (`output_scrubber` 3-stage pipeline: ghost regime → leakage → trading signals), `validator` (news trust), `staleness_detector`, `compute_budget` (graceful degradation)

**Output:** `formatters` (11 blocks, `_fmt_rupee()` for correct sign placement), `telegram_sender` (mockable for tests), `heatmap_generator`, `sector_heatmap`, `commodity_heatmap`, `technical_analysis`, `metrics`, `simplicity_engine`, `delta_renderer` (regime card with `_regime_emoji()` mapping BULL→🟢 DEFENSIVE/BEAR→🔴 NEUTRAL→⚪)

**Specialized:** `insider_tracker`, `shareholding_tracker`, `fii_sector`, `fii_concentration`, `earnings_tracker`, `beta_tracker`, `vol_persistence`, `turnover_ratio`, `factor_engine`, `sector_rs`, `market_internals`, `reversal_patterns`, `threshold_alerts`, `api_budget`, `bulk_block_deals`, `credit_monitor`, `mf_flows`

---

## AI Routing (`src/ai_engine.py`)

- `ai.analyze("fast")` → Groq (llama-3.3-70b) → Google fallback
- `ai.analyze("volume")` → Google (gemini-2.0-flash) → Groq fallback
- `ai.has_quota()` — pre-checks provider quota (60s cache), deterministic fallback before LLM call
- `ai.sentiment(text)` → FinBERT via HuggingFace API (circuit-broken)
- Max tokens: 1000, Temperature: 0.3
- Strong-conviction fallback triggers when AI exhausted AND 2+ extremes: USDINR≥90, Brent≥90, VIX≥20, Gold≥4000, FII streak≥3

---

## Key Patterns

- **Macro sanity guards (two-layer):** Wide absurdity bounds (USDINR 60-200, Brent 20-300, Gold 500-10000) → reject typos. Daily-change threshold (forex 3%, VIX 15%, yields 10%, commodities 8%) → catch corruption.
- **Consequence engine regime impact:** When price deviates >5% from 252-day baseline (DXY >4%, VIX >3%), shows baseline deviation instead of daily noise. Severity emojis: 📌 neutral, ⚠️ elevated/high, 🚨 stress/extreme. Signed values use `{:+.1f}`. 30% variance cap kills hallucinated moves.
- **NSE APIs:** Require session cookies — use `nse_session.py` (circuit-broken, 5-min TTL). Options chain: `/api/option-chain-indices`. Valuation: `/api/allIndices`.
- **All formatters return `""` on failure.** NaN handled via `_safe_float()`.
- **Pre-computed interpretations:** `run_contextualization()` computes VIX/FII/Absorption once, stores in `ctx`.
- **Signal weights:** Dynamic from accuracy log (>65% → ×1.3, <45% → ×0.7).
- **Regime Arbiter:** Single computation at 08:00, persisted to Supabase `market_state.final_regime`. Downstream jobs read-only. `_resolve_regime_label()` in `delta_renderer.py` checks `state.final_regime` first — override (USDINR>95 + Brent>90 → DEFENSIVE) correctly overrides BB-derived label.
- **Regime emoji map:** `BULLISH → 🟢`, `DEFENSIVE/BEARISH → 🔴`, `NEUTRAL → ⚪` — consistent across all jobs (fixed: was `⚪` for DEFENSIVE).
- **Ghost Regime safety net:** `_strip_ghost_regime()` in `validation_helper.py` removes AI-generated regime lines before sending.
- **Trading signal scrubbing:** `_strip_trading_signals()` in `validation_helper.py` — 3rd pipeline stage, 16 patterns covering `Bias:`, `(likely|possible|may|upside|downside)`, `(avoid|prefer)`, `(cut|reduce|hedge) (beta|exposure)`, `full defensive`, conditional `→` advice. `_scrub_leakage()` catches infra leakage ("fallback sent", "unchanged since last send").
- **Output scrubber (final pass):** `output_scrubber()` pipes through leakage blacklist → ghost regime strip → trading signal strip before `send_text()`.
- **Cross-job headline dedup:** `market_state.seen_headlines` JSONB list — morning_brief/market_intel writes at 08:00/07:00, market_open reads/filters/appends at 09:15.
- **Scorecard:** Unified `render_scorecard()` in `formatters.py`. Suppresses when n<10. Uses arbiter's `final_regime` as ground truth (not Nifty-change proxy).
- **Pre-market alerts:** Non-price catalysts only (earnings, regulatory, geopolitical). Pure price moves appear in 09:15 gap list.
- **Sentiment default:** Omit line entirely when `sentiment is None` or `sentiment == "neutral"`.
- **Circuit breaker:** `src/circuit_breaker.py` — 3-state (CLOSED→OPEN→HALF_OPEN), singleton per name, auto-recovery after 300s. Applied to FinBERT, NSE options chain, NSE API session.
- **Supabase upsert safety:** All `.upsert()` calls use explicit `.on_conflict("trade_date")`.
- **MarketState field warnings:** `get_market_state()` logs non-blocking warnings when `final_regime` or `macro` fields missing.
- **Consequence engine coherence:** WTI/Brent spread >5% suppresses WTI line with data-quality log.

---

## Macro Anchors (14, batch yfinance download)

`USDINR=X` · `BZ=F` · `GC=F` · `^INDIAVIX` · `DX-Y.NYB` · `^TNX` · `^VIX` · `HYG` · `CL=F` · `JPY=X` · `EURUSD=X` · `SI=F` · `HG=F` · `2YY=F`

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

## Project Status (Phases 0-33, reviewed)

**55+ modules, 260+ functions, 14 cron jobs, 28 Supabase tables, 15 workflow files.**

### Phase 33: COMPLETE ✅ — Score: 4/10 → 10/10

**6 P0 fixes + 4 P1 structural fixes, verified via dry-run + test_all_outputs.py.**

**P0 (fatal):** (1) Regime split-brain eliminated — `_resolve_regime_label()` checks `state.final_regime` first, override `USDINR₹95.7+Brent$92→DEFENSIVE` consistent across all job timings. (2) Trading signal scrubbing — `_strip_trading_signals()` added as 3rd pipeline stage with 16 patterns. (3) Override-aware scorecard — `validate_yesterday_prediction()` compares vs arbiter `final_regime` (not Nifty-change proxy). (4) Market Close derivatives — falls back to persisted `MarketState.derivatives` when live fetch fails. (5) Emoji consistency — `_regime_emoji()` returns 🔴 for DEFENSIVE (was ⚪). (6) `_fmt_rupee()` produces `-₹655Cr` not `₹-655Cr` across 7 files.

**P1 (structural):** (7) Cross-job headline dedup — `market_intel.py` + `evening_report.py` load/save `seen_headlines`. (8) WTI/Brent coherence check — deviation >5% suppresses WTI. (9) `_defensive_triggers()` regime-aware — shows escalation + de-escalation thresholds when already DEFENSIVE. (10) `get_market_state()` non-blocking field warnings for `final_regime`/`macro`.

**Files:** `delta_renderer.py` | `validation_helper.py` | `prediction_tracker.py` | `market_close.py` | `formatters.py` | `data_fetcher.py` | `consequence_engine.py` | `posture_engine.py` | `db.py` | `market_intel.py` | `evening_report.py` | `test_all_outputs.py`

### GHA Performance: Phase 1 Quick Wins Complete

1. **Fixed pip cache key** — `id: python` added to `setup-python` in all 15 workflows so `steps.python.outputs.python-version` resolves (was empty → constant key → cache misses).
2. **Parallel fallback** — `fetch_macro_anchors()` fallback loop converted to `ThreadPoolExecutor(max_workers=6)`.
3. **Step-level timeouts** — `timeout-minutes: 4` on run steps across all workflows for faster failure signal.

### Remaining
- Inline glossary for Tier 1 terms (PCR, GEX, DXY)
- Weekly self-audit (bot metrics in Sunday digest)
- Brier calibration (needs more prediction data, n ≥ 10)
- Percentile doesn't count ties → biased low
- `fii_streak` vs `fii_streak_days` key inconsistency
- `google.generativeai` deprecated → migrate to `google.genai`
- Drop `daily_market_snapshot` table from Supabase after verifying `market_state` JSONB has all data
- GHA Phase 2: Dockerize environment for <2 min workflow runs

## Test Commands
- `.venv/bin/python3 test_all_outputs.py` — 7 sections, 26 patterns, emoji consistency check
- `.venv/bin/python3 test_supabase_full.py` — 20 Supabase feature checks
- Both require `SUPABASE_URL` + `SUPABASE_KEY` from `../apikeys.txt` (supports `KEY=value` or `KEY: value` format)
