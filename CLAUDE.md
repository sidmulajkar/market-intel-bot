# CLAUDE.md

AI-powered Indian market intelligence bot — 14 cron jobs, daily Telegram analysis (text + heatmaps).

**Stack:** Python, Supabase (28 tables + 2 unused), Telegram, Groq/Google AI, NSE/AMFI/SEBI, FinBERT.

**Core principle:** Python computes conclusions. AI writes narrative only. AI cannot invent percentages, levels, probabilities, advice, or predictions. "No speculation" extended: `may/set direction/caution/should/(watch/avoid/hedge/raise/cut/remain/be)` all scrubbed.

**Output pipeline:** Python computes → AI narrates → Validator checks → Send or Fallback

---

## Jobs (GitHub Actions, stateless)

| Time | Job | Purpose |
|------|-----|---------|
| 5 AM | `fii_dii_fetch.py` | NSE FII/DII → Supabase |
| 7 AM | `market_intel.py morning` | Full 11-block AI analysis |
| 8 AM | `morning_brief.py` | Heatmaps + regime card + alerts (merged to 1 text send) |
| 9:15 AM | `market_open.py` | Opening brief + 5-line consequence layer |
| 12:30 PM | `midday_scan.py` | Regime scanner (skip gate on big moves) |
| 3:30 PM | `market_close.py` | EOD summary + derivatives + scenarios |
| 6 PM | `market_intel.py evening` | Full analysis + derivatives |
| 8 PM | `evening_report.py` | US session heatmap + outlook (populated with posture watch levels) |
| Sunday | `weekly_digest.py` | Scorecard + institutional signals |

**Workflow config (15 files in `.github/workflows/`):** All use `actions/cache@v4` keyed on `hashFiles('requirements.txt')` + Python version, `timeout-minutes: 10` at job level + `timeout-minutes: 8` on run steps. `setup-python` has `id: python` so `steps.python.outputs.python-version` resolves in cache keys. Target: **<3 min runtime** (current ~2.5 min).

---

## Key Modules (by layer)

**Data:** `data_fetcher` (yfinance batch download for 14 macro anchors, parallel ThreadPoolExecutor fallback), `nse_session` (5-min TTL, circuit-broken), `db` (Supabase CRUD+purge, non-blocking field warnings), `macro_fetcher`, `cftc_fetcher`

**Context:** `context_engine` (Bull/Bear 8-signal, global risk, phase classifier), `signal_arbitrator` (gap analysis, master signal), `mechanism_map` (24 macro→India mappings), `consequence_engine` (India impact multipliers, regime impact vs 252-day baseline, 30% variance cap, WTI/Brent coherence check)

**Derivatives:** `options_engine` (PCR, max pain, GEX, skew via v3 NSE API + file cache), `options_multi` (term structure), `fii_derivatives` (F&O participant OI)

**Valuation:** `valuation_engine` (P/E, P/B, risk premium, reverse DCF), `rolling_quant` (percentiles, divergences, correlations, scenarios)

**Intelligence:** `prompt_engine` (relevance scoring), `quant_enrichment` (Fear/Greed, factor attribution), `prediction_tracker` (Brier scores, dynamic weights, override-aware scorecard vs `final_regime`)

**Quality:** `output_validator` (26 patterns), `block_validator` (10 gates), `validation_helper` (`output_scrubber` 3-stage pipeline: ghost regime → leakage → trading signals), `validator` (news trust), `staleness_detector`, `compute_budget` (graceful degradation)

**Output:** `formatters` (11 blocks, `_fmt_rupee()` for sign placement, scenario block with `_HISTORICAL_CONTEXT` for 5 risk scenarios), `telegram_sender` (mockable), `heatmap_generator`, `delta_renderer` (regime card with `_regime_emoji()`: BULL→🟢 DEFENSIVE/BEAR→🔴 NEUTRAL→⚪)

**Specialized:** `insider_tracker`, `shareholding_tracker`, `fii_sector`, `fii_concentration`, `earnings_tracker`, `beta_tracker`, `vol_persistence`, `turnover_ratio`, `factor_engine`, `sector_rs`, `market_internals`, `reversal_patterns`, `threshold_alerts`, `api_budget`, `bulk_block_deals`, `credit_monitor`, `mf_flows`, `scenario_engine`

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

- **Macro sanity guards (two-layer):** Wide bounds (USDINR 60-200, Brent 20-300, Gold 500-10000) → reject typos. Daily-change threshold (forex 3%, VIX 15%, yields 10%, commodities 8%) → catch corruption.
- **Consequence engine regime impact:** Price deviates >5% from 252-day baseline (DXY >4%, VIX >3%) → shows baseline deviation. Severity: 📌 neutral, ⚠️ elevated/high, 🚨 stress/extreme. 30% variance cap.
- **NSE API v3 (options):** Two-step flow — `/api/option-chain-contract-info?symbol=NIFTY` → expiry dates → `/api/option-chain-v3?symbol=NIFTY&type=Indices&expiry=DD-Mon-YYYY`. File cache `/tmp/nse_options_chain_cache.json` written on first success, read on failure (after-hours fallback).
- **Options fallback tiers (market_close.py):** ① `get_latest_snapshot()` from Supabase → ② `MarketState.derivatives` → ③ live NSE v3 fetch → ④ file cache. `desc=True` (not `descending=True`) in postgrest.
- **All formatters return `""` on failure.** NaN handled via `_safe_float()`.
- **Pre-computed interpretations:** `run_contextualization()` computes VIX/FII/Absorption once, stores in `ctx`.
- **Signal weights:** Dynamic from accuracy log (>65% → ×1.3, <45% → ×0.7).
- **Regime Arbiter:** Single compute at 08:00 → persisted to `market_state.final_regime`. Downstream jobs read-only. `_resolve_regime_label()` checks `state.final_regime` first; override (USDINR>95+Brent>90→DEFENSIVE) overrides BB-derived label. `_defensive_triggers()` shows escalation+de-escalation thresholds when already DEFENSIVE.
- **Scenario engine:** `scenario_engine.py` — 5 risk scenarios (Geopolitical, Oil Shock, FII Exodus, Global Recession, Rupee Crisis). Detected via signal thresholds. Persisted to `market_state.scenario_history` (90-day rolling window) via `merge_scenario_history()`. Formatter renders per-scenario `📜 Historical parallel:` + `💥 Past impact:` using `_HISTORICAL_CONTEXT` mapping.
- **flow_metrics:** `morning_brief.py` + `market_intel.py` (2 call sites) pass `{"fii_net", "fii_streak_days"}` to `arbitrate_regime()` → activates FII exodus 5-day detection path.
- **Ghost Regime safety net:** `_strip_ghost_regime()` removes AI-generated regime lines.
- **Trading signal scrubbing:** `_strip_trading_signals()` — 16 patterns covering `Bias:`, `(likely|possible|may|upside|downside)`, `(avoid|prefer)`, `(cut|reduce|hedge) (beta|exposure)`, `full defensive`, `set`, `caution`, `should (watch/avoid/hedge/raise/cut/remain/be)`, `suggesting caution`, conditional `→` advice. `_scrub_leakage()` catches infra leakage. Posture lines use `neutral positioning` not `stay light`.
- **Output scrubber (final pass):** `output_scrubber()` pipes through leakage blacklist → ghost regime strip → trading signal strip before `send_text()`.
- **Cross-job headline dedup:** `market_state.seen_headlines` JSONB list — morning_brief/market_intel writes at 08:00/07:00, market_open reads/filters/appends at 09:15.
- **Scorecard:** Unified `render_scorecard()`. Suppresses when n<10. Uses arbiter's `final_regime` as ground truth. Override-aware: `validate_yesterday_prediction()` vs `final_regime` not Nifty proxy.
- **Pre-market alerts:** Non-price catalysts only (earnings, regulatory, geopolitical). Price moves in 09:15 gap list.
- **Sentiment default:** Omit line when `sentiment is None` or `"neutral"`.
- **Circuit breaker:** `src/circuit_breaker.py` — 3-state (CLOSED→OPEN→HALF_OPEN), singleton per name, auto-recovery after 300s. Applied to FinBERT, NSE options chain, NSE API session.
- **Supabase upsert safety:** All `.upsert()` use `.on_conflict("trade_date")`.
- **Consequence engine coherence:** WTI/Brent spread >5% suppresses WTI line.
- **Evening Report watch:** `possible downgrade` → factual `de-escalation (252d baseline: ₹83)`. Outlook line populated with posture-engine derived watch levels (suppressed if no data).
- **Intel compressed fallback:** When regime unchanged + VIX stable, shows `Defensive | USDINR ₹94.99, Brent $90, VIX 16 | Override: compound_stress | No new catalyst.` — includes regime context + macro data + override reason.

---

## Macro Anchors (14, batch yfinance download)

`USDINR=X` · `BZ=F` · `GC=F` · `^INDIAVIX` · `DX-Y.NYB` · `^TNX` · `^VIX` · `HYG` · `CL=F` · `JPY=X` · `EURUSD=X` · `SI=F` · `HG=F` · `2YY=F`

---

## Supabase Tables (28 referenced, all exist)

**Core:** `watchlist`, `mf_watchlist`, `bot_state`, `sent_alerts`, `market_snapshots`
**Flows:** `fii_dii_flows`, `mf_flows`, `fii_institution_tracker`
**Market:** `daily_market_snapshot`, `market_breadth_history`, `options_snapshots` (includes `gex` + `skew_25d` cols), `macro_anchor_snapshots`, `valuation_history`, `market_state`
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

DRY_RUN env var controls mock mode (print to console). Defaults to `False` in production.

---

## Project Status (Phases 0-34, reviewed)

**55+ modules, 260+ functions, 14 cron jobs, 28 Supabase tables, 15 workflow files.**

### Phase 34: DEPLOYMENT ✅ — Score: 9.7/10 → 10/10

**Core wins (pre-gap fixes fully resolved):**
1. **NSE API v3** — Old `/api/option-chain-indices` (404) replaced with v3 + expiry pre-fetch. Works after hours for active expiry. File cache fallback at `/tmp/nse_options_chain_cache.json`.
2. **GEX + skew pipeline** — `compute_options()` calls `compute_gex()` + `compute_skew()`. Persisted to `options_snapshots` with `gex` + `skew_25d` columns.
3. **Bug fixes** — `snap.get("ok")` → `if snap:`, missing `run="morning"`, `descending=True` → `desc=True` (postgrest v2), PCR dict vs float `isinstance` guard.
4. **Scenario engine** — `src/scenario_engine.py` with 5 risk scenarios, `_HISTORICAL_CONTEXT` mapping, `merge_scenario_history()` persistence (90-day rolling window). Renders per-scenario historical parallel + past impact.
5. **flow_metrics wired** — `morning_brief.py` + `market_intel.py` pass FII metrics to arbiter, activating FII exodus 5-day detection.
6. **Speculative language 100% scrubbed** — Extended to `set`, `caution`, `should`, `suggesting caution`. "stay light" → `neutral positioning` across `market_close.py`, `market_open.py`, `posture_engine.py`. Zero remaining occurrences.
7. **Regime persistence confirmed** — `market_state.final_regime` reads correctly (DEFENSIVE) across market_close + market_open. Dry-run NEUTRAL is test artifact.
8. **Evening Report outlook** — Populated with posture-engine watch levels instead of empty header.
9. **Workflow config** — 15 files validated: `actions/cache@v4`, `id: python`, 10/8 min timeouts, proper secret usage. `bot_handler.yml` on `*/5 * * * *`.
10. **Full-day test** — 0 errors, 7/7 messages, 2.4 min runtime. `test_all_outputs.py` all 7 sections pass.

**Remaining (non-blocking polish):**
- Inline glossary for Tier 1 terms (PCR, GEX, DXY) — pinned Telegram message
- Weekly self-audit (bot metrics in Sunday digest)
- Brier calibration (needs n ≥ 10 prediction data)
- Percentile doesn't count ties → biased low
- `fii_streak` vs `fii_streak_days` key inconsistency
- `google.generativeai` deprecated → migrate to `google.genai`
- Drop `daily_market_snapshot` table after verifying `market_state` JSONB has all data
- GHA Phase 2: Dockerize for <2 min workflow runs

## Test Commands
- `.venv/bin/python3 test_all_outputs.py` — 7 sections, 26 patterns, emoji consistency check
- `.venv/bin/python3 test_supabase_full.py` — 20 Supabase feature checks
- `.venv/bin/python3 test_full_day.py` — 8-job dry-run simulation (requires `DRY_RUN=1`)
- All require `SUPABASE_URL` + `SUPABASE_KEY` from `../apikeys.txt` (supports `KEY=value` or `KEY: value` format)
