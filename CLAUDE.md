# CLAUDE.md

AI-powered Indian market intelligence bot — 14 cron jobs, daily Telegram analysis (text + heatmaps).

**Stack:** Python, Supabase (30 tables + 2 unused), Telegram, Groq/Google AI, NSE/AMFI/SEBI, FinBERT.

**Core principle:** Python computes conclusions. AI writes narrative only. AI cannot invent percentages, levels, probabilities, advice, or predictions. "No speculation" extended: `may/set direction/caution/should/(watch/avoid/hedge/raise/cut/remain/be)` all scrubbed.

**Output pipeline:** Python computes → AI narrates → Validator checks → Send or Fallback

---

## Jobs (GitHub Actions, stateless)

| Time | Job | Purpose |
|------|-----|---------|
| 5 AM | `fii_dii_fetch.py` | NSE FII/DII → Supabase |
| 7 AM | `market_intel.py morning` | Full 11-block AI analysis |
| 8 AM | `morning_brief.py` | Heatmaps + regime card + alerts (merged to 1 text send) |
| 9:15 AM | `market_open.py` | AI-free opening brief (deterministic Python postscript) |
| 12:30 PM | `midday_scan.py` | Regime scanner (skip gate on big moves) |
| 3:30 PM | `market_close.py` | EOD summary + derivatives + scenarios |
| 6 PM | `market_intel.py evening` | Full analysis + derivatives |
| 8 PM | `evening_report.py` | US session heatmap + outlook (populated with posture watch levels) |
| Sunday | `weekly_digest.py` | Scorecard + institutional signals |

**Workflow config (15 files in `.github/workflows/`):** All use `actions/cache@v4` keyed on `hashFiles('requirements.txt')` + Python version, `timeout-minutes: 10` at job level + `timeout-minutes: 8` on run steps. `setup-python` has `id: python` so `steps.python.outputs.python-version` resolves in cache keys. Target: **<3 min runtime** (current ~2.5 min).

**Architecture constraint — no Docker:** We run on GitHub Actions free tier. Docker would add image pull/startup time (30-60s per job) without fixing real bottlenecks. The runtime ceiling is set by API wait times (yfinance, NSE, Groq, Google AI, Supabase) and Python import/module load overhead, not OS/runtime provisioning. All future optimization must come from **code logic and inference patterns**, not deployment architecture:
  - **Do:** lazy imports, circuit breakers to skip redundant calls, cache Supabase reads intra-job, parallelize independent API fetches, skip expensive computations when data is insufficient, reduce LLM prompt token count
  - **Don't:** change runner type, containerize, add servers, share state across jobs (stateless by design)
  - Current 2.5 min is within target; optimizations target headroom for when API latency spikes or new compute-heavy blocks are added.

---

## Key Modules (by layer)

**Data:** `data_fetcher` (yfinance batch download for 16 macro anchors, parallel ThreadPoolExecutor fallback), `nse_session` (5-min TTL, circuit-broken), `db` (Supabase CRUD+purge, non-blocking field warnings), `macro_fetcher`, `cftc_fetcher`, `csv_data` (CSV bootstrap + quality gate + fallback to Supabase/yfinance)

**Context:** `context_engine` (Bull/Bear 8-signal, global risk, phase classifier), `signal_arbitrator` (gap analysis, master signal), `mechanism_map` (24 macro→India mappings), `consequence_engine` (India impact multipliers, regime impact vs 252-day baseline, 30% variance cap, WTI/Brent coherence check)

**Derivatives:** `options_engine` (PCR, max pain, GEX, skew via v3 NSE API + file cache), `options_multi` (term structure), `fii_derivatives` (F&O participant OI)

**Valuation:** `valuation_engine` (P/E, P/B, risk premium, reverse DCF), `rolling_quant` (percentiles, divergences, correlations, scenarios)

**Intelligence:** `prompt_engine` (relevance scoring), `quant_enrichment` (Fear/Greed, factor attribution), `prediction_tracker` (Brier scores, dynamic weights, override-aware scorecard vs `final_regime`)

**Quality:** `output_validator` (26 patterns), `block_validator` (10 gates), `validation_helper` (`output_scrubber` 3-stage pipeline: ghost regime → leakage → trading signals), `validator` (news trust), `staleness_detector`, `compute_budget` (graceful degradation)

**Output:** `formatters` (11 blocks, `_fmt_rupee()` for sign placement, scenario block with `_HISTORICAL_CONTEXT` for 5 risk scenarios), `telegram_sender` (mockable), `heatmap_generator`, `delta_renderer` (regime card with `_regime_emoji()`: BULL→🟢 DEFENSIVE/BEAR→🔴 NEUTRAL→⚪)

**Specialized:** `insider_tracker`, `shareholding_tracker`, `fii_sector`, `fii_concentration`, `earnings_tracker`, `beta_tracker`, `vol_persistence`, `turnover_ratio`, `factor_engine`, `sector_rs`, `market_internals`, `reversal_patterns`, `threshold_alerts`, `api_budget`, `bulk_block_deals`, `credit_monitor`, `mf_flows`, `scenario_engine`, `flow_velocity`

**Institutional Context (T3):** `economic_calendar` (144 event CSV, RBI/CPI/GDP/Fiscal/Global, 12-month lookahead), `corporate_actions` (NSE corp-info API, watchlist + Nifty 50, dividend/bonus/split/buyback)

**Synthesis (T4):** `stress_index` (Z-score weighted composite: VIX 25%, FII 25%, USDINR 15%, Brent 15%, Skew 10%, Breadth 10% → 0-100 score, Supabase `stress_history` table), `clone_engine` (6D macro state vector → Euclidean nearest-neighbor → top-3 historical matches → 30D Nifty forward return + max DD)

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
- **Intel compressed fallback:** When regime unchanged + VIX stable, shows `Defensive | USDINR ₹94.99, Brent $90, VIX 16 | Override: compound_stress | No new catalyst.` — includes regime context + macro data + override reason. Compressed one-liner also appends `⚠️ {event}` when `get_high_impact_soon(days=2)` finds a high-impact calendar event.
- **Economic calendar (T3.1):** Static CSV `data/econ_calendar_india_2026_27.csv` (144 events, 12-month lookahead). `load_calendar()` → `get_upcoming_events(days=7)` → `format_calendar()`. Also `get_high_impact_today/tomorrow/soon()`. Wired into market_intel block 1 + morning_brief regime card + compressed fingerprint.
- **Corporate actions (T3.2):** `src/corporate_actions.py` — NSE corp-info API per symbol. Filters dividend/bonus/split/buyback with ex-date within 30 days, outputs 7-day window. Target: watchlist + Nifty 50 (~150 symbols). 0.15s delay between requests. Supabase table `corporate_actions` with PK `(symbol, ex_date, action_type)`. Wired into `market_open.py` right after gap list.
- **Midday breadth + sector RS (T1.2/T1.3):** `midday_scan.py` fetches live A/D from NSE marketStatus + sector RS leaders/laggards to replace static gap data at 12:30.
- **Flow Velocity (T2.1):** `src/flow_velocity.py` compares 5D vs 21D rolling FII/DII means, Z-score ±1.5 → ACCEL/DECEL/NEUTRAL, + DII floor ratio. Wired into `formatters.py:format_flows()`.
- **Turnover ratio (T2.3):** `fetch_nse_volumes()` in `data_fetcher.py` queries NSE marketStatus turnover. `turnover_ratio.py` wired into `market_intel.py` block 7.
- **Options momentum delta (T2.4):** `midday_scan.py` compares 09:15 morning snapshot PCR/GEX/Skew vs current midday. Output: `📊 Options Delta (vs 09:15): PCR 0.92 → 0.85 ↑`.
- **Post-close funding/carry (T2.2):** `INDIA10Y=X` added to macro anchors (15 total). Evening block 10 includes IND-US 10Y spread vs 5D avg + FII F&O long-short ratio.
- **No local imports in `main()`:** Local `from X import Y` inside `main()` shadows module-level imports. Only use names already imported at module scope.

---

## Macro Anchors (16, batch yfinance download)

`USDINR=X` · `BZ=F` · `GC=F` · `^INDIAVIX` · `DX-Y.NYB` · `^TNX` · `^VIX` · `HYG` · `CL=F` · `JPY=X` · `EURUSD=X` · `SI=F` · `HG=F` · `2YY=F` · `INDIA10Y=X` · `ES=F` · `NQ=F` · `^N225`

---

## Supabase Tables (32 referenced, all exist)

**Core:** `watchlist`, `mf_watchlist`, `bot_state`, `sent_alerts`, `market_snapshots`
**Flows:** `fii_dii_flows`, `mf_flows`, `fii_institution_tracker`
**Market:** `daily_market_snapshot`, `market_breadth_history`, `options_snapshots` (includes `gex` + `skew_25d` cols), `macro_anchor_snapshots`, `valuation_history`, `market_state`, `corporate_actions`, `stress_history`
**Intelligence:** `daily_predictions`, `prediction_outcomes`, `signal_accuracy_log`, `correlation_matrix`, `divergence_log`, `forecast_log`, `analytics_ledger`, `clone_history`
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

## Project Status (Phases 0-36, reviewed)

**58+ modules, 270+ functions, 14 cron jobs, 31 Supabase tables, 15 workflow files.**

### Phase 34: DEPLOYMENT ✅ — Score: 10/10

### Phase 35: T-PHASE INSTITUTIONAL UPGRADE ✅ — 6/6 steps, 0 errors

**T0: Temporal bugs fixed:**
- 9:15 AI excised entirely → deterministic Python postscript `📌 Open Posture: {regime} | {gaps} | {consequence}`
- SEBI staleness label `⚠️ filings lag ~10 days` on bulk/block deals
- US equity movers suppressed before 19:00 IST (time gate in market_close.py)
- Delta Tracker stores 07:00 fingerprint → compressed one-liner at 18:00 if unchanged

**T1: Existing infra wired to all time slots:**
- Derivatives block (PCR, GEX, skew) wired into market_open.py + midday_scan.py
- Live A/D breadth via NSE marketStatus + sector RS leaders/laggards in midday_scan

**T2: New institutional modules:**
- `src/flow_velocity.py` — 5D vs 21D FII/DII rolling means, Z-score ±1.5, DII floor ratio
- `turnover_ratio.py` wired into market_intel block 7 via `fetch_nse_volumes()`
- Intraday options momentum delta (PCR/GEX/Skew vs 09:15) in midday_scan
- `INDIA10Y=X` + `ES=F` + `NQ=F` + `^N225` added to macro anchors (16 total) + evening block 10 funding/carry (IND-US spread, FII F&O L/S)

**Bug fix:** Removed all `from X import Y` inside `main()` — Python treats them as local vars, shadowing module-level imports. Use only module-level names in `main()`.

**Test results:** 8 jobs, 7 messages, 0 errors on full-day dry run. `test_all_outputs.py` 7/7 sections pass.

### Phase 36: T3 INSTITUTIONAL CONTEXT ✅ — 2/2 steps, 0 errors

**T3.1: Economic Calendar (`src/economic_calendar.py` + `data/econ_calendar_india_2026_27.csv`):**
- 144 curated events (RBI MPC, CPI/WPI, GDP, Fiscal, Global) spanning Jun 2026 → Jun 2027
- `get_upcoming_events(days=7)` → block 1 of both market_intel runs
- `get_high_impact_soon(days=2)` → compressed fingerprint replaces `| No new catalyst` with `| ⚠️ India GDP (Q4 FY26)`
- Calendar appended to morning_brief regime card
- Compressed evening delta also shows high-impact alerts

**T3.2: Corporate Actions (`src/corporate_actions.py`):**
- NSE corp-info API fetcher for watchlist + Nifty 50 (~150 symbols)
- Parses dividend/bonus/split/buyback with ex-date within 30 days, outputs 7-day window
- Persisted to `corporate_actions` Supabase table `PK(symbol, ex_date, action_type)`
- Wired into `market_open.py` right after gap list at 09:15
- **Optimization:** Live Nifty 50 only on weekdays (~15s), watchlist reads from Supabase cache (populated Sunday by `weekly_digest.py`)

### Phase 37 (T4.1): COMPOSITE STRESS INDEX ✅ — 1/1 step, 0 errors

**`src/stress_index.py`** — Z-score weighted composite (VIX 25%, FII 25%, USDINR 15%, Brent 15%, Skew 10%, Breadth 10%) → 0-100 score. Supabase `stress_history` table.

**Wiring:**
- **First banner line** in 07:00/12:30/18:00 outputs (before regime line)
- **Regime arbiter hook:** Score >80 for 2+ consecutive days → force DEFENSIVE override
- Auto-saved to Supabase on every market_intel run

### Phase 38 (T4.2): HISTORICAL CLONE ENGINE ✅ — 1/1 step, 0 errors

**Verification (2026-05-31):** Full-day dry run (real API keys) — 8 jobs, 7 messages, 0 errors. Clone engine + stress index gracefully return empty on weekends (insufficient historical data). 94% morning/evening duplicate content confirmed expected on weekends (both use same deterministic fallback). Weekday live run required for full validation.

**`src/clone_engine.py`** — Replaces static `_HISTORICAL_CONTEXT` strings + `scenario_engine.find_historical_clones()` with 6D macro state vector Euclidean nearest-neighbor matching and empirical forward returns. Zero speculation.

**Architecture:**
- **6D State Vector:** VIX, USDINR, Brent, DXY, FII 5D cumulative, PCR — all as expanding percentiles (0-1)
- **Distance Metric:** Weighted Euclidean distance across 6D (weights: VIX/FII 0.20 each, USDINR/Brent 0.15, DXY/PCR 0.15)
- **Forward Returns:** Nifty 30D forward return + max drawdown via yfinance `^NSEI` history
- **Pre-computation:** Fetch 5y yfinance macro history + Supabase FII/PCR history; pandas expanding percentile; numpy vectorized distance
- **Exclusion zone:** Last 30 days excluded; minimum 1 year (252 sessions) lookback

**Output format (deterministic, no AI involvement):**
```
🔬 Historical Clones (Macro State Match)
Active Scenario: Geopolitical | Oil Shock
1. 2013-08-19 | Dist: 0.12
   30D Fwd: -8.2% | Max DD: -12.1%
2. 2018-09-21 | Dist: 0.18
   30D Fwd: -4.1% | Max DD: -6.8%
Median 30D Fwd: -3.4% | Median Max DD: -6.8%
```

**Wiring:**
- `market_intel.py` — Emitted after stress banner, before header (both 07:00 morning + 18:00 evening runs)
- `formatters.py:format_scenario_block()` — Updated to call clone engine for `market_close.py` output
- `save_clones()` — Persists to `clone_history` Supabase table with `PK(trade_date, clone_date)`
- **Scrubber rule** — `(Clone|clone|Historical Clone).*?(could|may|might|will|if|likely|possibly|probably)` added to `_BLOCKED_PATTERNS` in `validation_helper.py`

**Key design decisions:**
- `ScenarioDetector` kept active for scenario label detection → passed into clone block as `Active Scenario:` line
- `find_clones()` accepts raw values (no state dependency) — callable from any job
- `get_current_fii_5d()` helper fetches 5D cumulative FII from Supabase when not available in job context
- Fallback to 4D macro vector when FII/PCR history is too short (`current_fii_5d=None` skips FII, `current_pcr=None` skips PCR)
- `format_scenario_block()` falls back to legacy scenario-only output if clone engine returns `insufficient_data`
- Pandas `expanding().rank(pct=True)` for O(n) percentile computation (not O(n) per window)
- Scipy-free: uses `np.mean(vals <= val)` for percentile (no scipy dependency)

---

**Supabase Storage Budget (2 GB limit)**

All new data must have a corresponding entry in `src/purge_manager.py:RETENTION_POLICY`. Single source of truth — imported by `sunday_backfill.py` and `db.py`.

**Three categories:**
- **HISTORICAL** — archived to CSV Sunday, then purged via two-phase commit (archived=true AND age > retention)
- **OPERATIONAL** — time-based purge only, no CSV archive
- **REFERENCE** — never purged (static/config data)

**Retention summary:**

| Category | Tables | Purge trigger |
|----------|--------|---------------|
| Historical | macro_anchor_snapshots, fii_dii_flows, market_breadth_history, stress_history, valuation_history | archived=true + 365d |
| Operational | market_state(90d), analysis_cache(7d), sent_alerts(30d), forecast_log(90d), clone_history(180d), signal_accuracy_log(365d), prediction_outcomes(90d), analytics_ledger(90d), cftc_positioning_history(270d), factor_scores_history(180d), sector_rs_history(180d), market_internals_history(180d), corporate_actions(90d), earnings_surprises(730d), options_snapshots(7d) | age-based |
| Reference | watchlist, mf_watchlist, bot_state | never |

**Safety guarantees:**
- **Two-phase archive**: Row marked `archived=true` before deletion. Purge only deletes rows that are BOTH archived AND older than retention.
- **Supabase-as-buffer**: Even after CSV write, data stays in Supabase 365 days as live backup.
- **Git-history-as-backup**: Every Sunday commit is a snapshot. Revert to last week if CSV is corrupted.
- **Conditional purge**: `sunday_purge.yml` only runs if `sunday_backfill.yml` succeeded (workflow_run conclusion check).

**Usage:**

```python
from src.purge_manager import purge_expired_tables, get_retention_days, is_historical_table

# Called by sunday_backfill.py (after CSV push succeeds) and db.py (operational purge)
result = purge_expired_tables(supabase_client, dry_run=True)   # preview
result = purge_expired_tables(supabase_client, dry_run=False)  # execute

# Helpers
days = get_retention_days("clone_history")          # → 180
is_hist = is_historical_table("stress_history")    # → True
```

## Execution Plan (Analyst Review — Institutional Terminal 10/10)

### Items Already Done
| Item | Status | Commit |
|------|--------|--------|
| `fii_streak` → `fii_streak_days` key consistency | ✅ Fixed | `formatters.py:2141` |
| `google.generativeai` → `google.genai` | ✅ Migrated | `ai_engine.py:29-46` |
| SQL tables deployed (stress, corp actions, clone) | ✅ Done | Supabase public schema |
| Daily market snapshot → market_state JSONB | ✅ Complete | `db.py:939` writes to JSONB |

### Items Already In Place (no action needed)
| Claimed Gap | Reality | Location |
|---|---|---|
| `(could\|would\|will\|might)` scrubber | Already exists | `validation_helper.py:63` |
| Imperative scrubber (watch/monitor/avoid/…) | Already exists | `validation_helper.py:65-66` |
| Unqualified adjective scrubber | Already exists | `validation_helper.py:67` |
| Arrow advice scrubber | Already exists | `validation_helper.py:48,68` |
| `"gap expected?"`, `"key level to watch"` | Never existed in any prompt | Verified all 7 methods |
| Cu/Au ratio | Already computed | `context_engine.py:1428` |
| Per-strike GEX | Already computed (full list, only top 5 returned) | `options_engine.py:248-274` |
| Inline glossary (Tier 1 + Tier 2) | Already implemented | `formatters.py:333-385` |

### Phase 39 (A0): AI Prompt Sanitization — ~5 min
**The only outstanding AI prompt issue:** `stock_analysis_prompt` is missing the anti-forecast constraint present in all other prompts, and contains speculative instructions:
- Line 428: `Trend: Bullish/Bearish/Neutral + reason (consider technicals)` → replace with `Price Action: describe today's actual price move`
- Line 429: `Key Levels: Support and Resistance` → replace with `Key Levels: actual session high/low`
- Line 431: `Signal: BUY / SELL / HOLD / WATCH` → remove entire line (trading signal violation)
- Line 432: `Risk: Low/Medium/High + main risk` → replace with factual observation only
- Add the standard `CRITICAL CONSTRAINT` footer present in all other prompts

**Storage impact:** None (code-only change).

### Phase 40 (A1): GEX Magnetic Levels — ~2 hr
**New formatter function** in `formatters.py` — `format_gex_levels()`.
- Read `gex_by_strike` list (already computed in `options_engine.py:compute_gex()`, currently discarded locally)
- Return full list from `compute_gex()` as new key `"gex_by_strike"`
- Formatter finds: highest positive net GEX below spot → magnetic support; highest negative above spot → magnetic resistance; strike where cumulative GEX crosses zero → pin
- Output: `🧲 GEX LEVELS: Support 23,400 (Strong) | Resistance 23,800 (Moderate) | Pin: 23,500`
- Wire into: 9:15 AM market_open.py, 12:30 PM Options Delta, 3:30 PM market_close.py

**Storage impact:** None (no new DB writes — reads existing options chain).

### Phase 41 (A2a): Drawdown Anatomy — ~3 hr
**New module:** `src/drawdown_anatomy.py`
- Fetch Nifty 1Y historical data from yfinance
- Compute: 252D high, current drawdown %, velocity (5D drawdown rate), historical recovery time (median sessions from past drawdowns of similar depth)
- Output: `📉 DRAWDOWN: -5.8% from 252D high | Velocity: -0.8%/day (RAPID) | Historical recovery: 23 sessions (median)`
- Wire into: 3:30 PM market_close.py

**Storage impact:** None runtime. ~2s additional yfinance call.

### Phase 42 (A2b): Sector Rotation Phases — ~1 hr
**Extend** `sector_rs.py` — add `LEADING / PEAKING / LAGGING / RECOVERING` classification.
- Phase = combination of `rs_score` level (above/below 50) × `momentum_1m` direction (positive/negative)
- Output: `LEADING: IT (+0.2σ, ↑) | PEAKING: BANK (+0.1σ, ↓) | LAGGING: METAL (-0.3σ, ↓)`
- Wire into: 12:30 PM midday_scan.py

**Storage impact:** None (computed in-memory from already-fetched sector data).

### Phase 43 (A3): Telegram Command Interactivity — ~4 hr
**Extend** `src/bot_handler.py` — add 6 commands:
- `/stress` — read latest from `stress_history`, show score + top drivers
- `/clone` — read latest from `clone_history`, show top 3 clones
- `/flows` — read latest from `fii_dii_flows`, show net + velocity
- `/gex` — read latest from `options_snapshots`, show GEX + levels
- `/sectors` — read latest from `sector_rs_history`, show leaders/laggards
- `/whatif brent 100` — run `compute_consequence("brent", 100)` inline

All commands: pure Supabase reads (sub-second), zero AI, zero live API calls.
Update `/help` text with new commands.

**Storage impact:** None (reads existing tables). GHA minutes: ~+20/mo if we reduce polling to 1-min.

### Phase 44 (A4): Pinned Inline Glossary — ~30 min
**Add** `pin_message()` to `src/telegram_sender.py` — calls Telegram `pinChatMessage` API.
Send glossary definitions (PCR, GEX, DXY, FII, DII, VIX) once and pin to group.

**Storage impact:** None.

### Phase 45 (G1): Global Nervous System (2 new tickers) — ~1 hr
**Add to** `data_fetcher.py:fetch_macro_anchors()`:
- `LQD` (iShares IG Corporate Bond ETF) — global credit stress baseline (we have HYG, need IG)
- `SOXX` (Semiconductors ETF) — global growth cycle canary

**Wire existing Cu/Au ratio** to the global arbiter and clone engine.
Also add `VALID_RANGES` / `_MAX_DAILY_CHANGE_PCT` entries for the 2 new tickers.

**Storage impact:** +2 rows/day in `macro_anchor_snapshots` (already purged at 90 days). ~4KB/year.

### Phase 46 (G2): Global Regime Arbiter — ~3 hr
**New module:** `src/global_arbiter.py`
- Compute 4-state classification via Z-scores on already-fetched data:
  1. `GLOBAL_RISK_ON`: DXY⬇, HYG/LQD⬆, Cu/Au⬆, VIX < 15
  2. `GLOBAL_RISK_OFF`: DXY⬆, HYG/LQD⬇, USDJPY⬇, VIX > 20
  3. `GLOBAL_STAGFLATION`: Brent⬆, Gold⬆, Cu⬇, DXY⬆
  4. `GLOBAL_LIQUIDITY_DRAWDOWN`: US10Y⬆ + DXY⬆ simultaneously
- Wire to `signal_arbitrator.py` with Hierarchy Rule:
  - If `STAGFLATION` or `LIQUIDITY_DRAWDOWN`: **Force** India to DEFENSIVE
  - If `RISK_OFF`: **Cap** India at NEUTRAL (ban BULL)
  - If `RISK_ON`: **Allow** full India regime range

**Storage impact:** Persist to `market_state.state.global_regime` JSONB (already covered by 1095d purge on `market_state`).

### Phase 47 (G3): 2-Tier Global Clone Engine — ~4 hr
**Extend** `src/clone_engine.py` — add Tier 1 Global Clone alongside existing 6D India clone:
- **Tier 1 (Global):** 5D vector `[DXY_pctile, US10Y_pctile, HYG_pctile, Cu/Au_pctile, USDJPY_pctile]` → match to SPY + MSCI EM 30D forward returns via yfinance
- **Tier 2 (Transmission):** For each global clone date, query Nifty 30D forward return from same yfinance history
- Combined output format:
  ```
  🌍 GLOBAL CLONE: 2013-08-19 (Taper Tantrum) | Dist: 0.14
  Global: SPX -5.1% | MSCI EM -12.4%
  India Transmission: Nifty -8.2% | Max DD: -12.1%
  ```
- Keep existing India clone (more precise for India-specific patterns)

**Storage impact:** +1 record/day × 3 clones = 3 rows/day in `clone_history` (add purge at 30 days). ~1KB/year.

### Phase 48 (G4): Cross-Border Transmission Matrix — ~5 hr
**Extend** `src/consequence_engine.py` — 3 additions:
1. **Route `INDIA10Y=X`** through consequence multipliers (currently fetched but unused). Add to `CONSEQUENCE_MULTIPLIERS` and `_BASELINE`.
2. **Compute Net FII Carry Yield:** `IND-US 10Y Spread - INR 1M Forward Premium`. Thresholds: < 2% = elastic FII flows; > 4% = India insulated.
3. **Dynamic DXY→INR elasticity:** Replace current hardcoded 0.85 coefficient with rolling regression (60-day window) from `macro_anchor_snapshots`. If current INR depreciation exceeds historical DXY elasticity → RBI intervention signal. If below → temporary DII defense.

**Storage impact:** None (reads existing `macro_anchor_snapshots` and `INDIA10Y=X`).

### Phase 49 (CH): Codebase Health — ~2 hr
- **Drop `daily_market_snapshot`** table (262 rows, deprecated). Verify `market_state` JSONB covers all consumed fields (70% matched, remaining 30% unused by any code path → safe to drop after weekday dry-run).
- **Economic calendar CSV staleness check** — add alert in Sunday digest if CSV last row < 30 days from today.
- **Weekly self-audit** — add bot metrics (uptime, accuracy, data completeness) to Sunday digest.
- **Brier calibration** — enable when `n >= 10` predictions available.

---

## Execution Priority

| # | Phase | Item | Effort | Runtime Impact | Storage Impact | Status |
|---|-------|------|--------|----------------|----------------|--------|
| 1 | A0 | Fix stock_analysis_prompt | 5 min | 0s | None | ✅ |
| 2 | A4 | Pinned glossary | 30 min | 0s | None | ✅ |
| 3 | A1 | GEX Magnetic Levels | 2 hr | 0s | None | ✅ |
| 4 | A2b | Sector Rotation Phases | 1 hr | 0s | None | ✅ |
| 5 | A2a | Drawdown Anatomy | 3 hr | +2s | None | ✅ |
| 6 | G1 | LQD + SOXX tickers | 1 hr | +1s | +2 rows/d (purged 90d) | ✅ |
| 7 | G2 | Global Regime Arbiter | 3 hr | +0.1s | JSONB (purged 1095d) | ✅ |
| 8 | A3 | Telegram commands | 4 hr | 0s | None (reads only) | ✅ |
| 9 | G4 | Transmission Matrix | 5 hr | +1-2s | None | ✅ |
| 10 | G3 | 2-Tier Global Clone | 4 hr | +3-5s | +3 rows/d (purged 30d) | ✅ |
| 11 | CH | Codebase health | 2 hr | 0s | Drops old table | ✅ |

**Total effort:** ~25 hours coding  
**Total runtime budget consumed:** ~8-10s out of 180s available (~5.5%)  
**GHA minutes impact:** Negligible (+~20/mo for bot handler polling)  
**Storage budget headroom:** Well under 2GB at current pace (~5MB/month growth without purge)

## Current Progress (Phase 39 onward)

**A0 ✅** — `stock_analysis_prompt` fixed (4 speculative lines removed, CRITICAL CONSTRAINT footer added). Dead code (zero call sites), fixed in place.  
**A1 ✅** — `compute_gex()` returns full `gex_by_strike` list. `format_gex_levels()` computes magnetic support/resistance/pin with strength labels (Strong/Moderate/Weak). Wired into market_open, midday_scan, market_close.  
**A2a ✅** — `src/drawdown_anatomy.py` — drawdown % from 252D high, 5D velocity, historical recovery time via yfinance. Wired into market_close.py.  
**A2b ✅** — Sector phases (LEADING/PEAKING/RECOVERING/LAGGING) from rs_score × momentum_1m. Z-score σ notation. Wired into midday_scan.py (replaces old leader/laggard logic).  
**A3 ✅** — 6 Telegram commands: `/stress` (stress_history), `/clone` (clone_history), `/flows` (fii_dii_flows), `/gex` (options_snapshots), `/sectors` (sector_rs_history), `/whatif <var> <val>` (compute_consequence with 15 aliases). Zero AI, zero live API. HELP_TEXT + dispatch updated.  
**A4 ✅** — `pin_message()` + `send_pinned_glossary()` added to telegram_sender.py. Glossary from formatters.py TIER1 (6) + TIER2 (15). Dry-run verified. Needs Telegram admin to accept pin.  
**G1 ✅** — LQD + SOXX added to data_fetcher.py (VALID_RANGES, _MAX_DAILY_CHANGE_PCT, anchors — 19 total). New fields on MarketState.Macro (lqd, soxx, usd_jpy, es, nq). pipeline_adapters.py updated.  
**G2 ✅** — `src/global_arbiter.py` (4-state: RISK_ON/RISK_OFF/STAGFLATION/LIQUIDITY_DRAWDOWN/NEUTRAL). Wired into regime_arbiter.py at Layer 1b: STAGFLATION/LIQUIDITY_DRAWDOWN → FORCE DEFENSIVE, RISK_OFF → cap at NEUTRAL, RISK_ON → no restriction. State persisted via `state.global_regime`. Calibration gate: backtested against 4 historical episodes (2013 Taper 100% RISK_OFF, 2018 EM 100% RISK_OFF, 2020 COVID corrected to RISK_OFF, 2022 Fed corrected to RISK_OFF). US10Y_LIQUIDITY_STRESS tuned 4.5→4.25.  
**G3 ✅** — 2-Tier Global Clone Engine. Tier 1: 5D global vector `[DXY, US10Y, HYG, Cu/Au, USDJPY]` → SPY + MSCI EM forward returns. Tier 2: Nifty transmission. `find_global_clones()` + `format_global_clone_block()` in `clone_engine.py`. Wired into `formatters.py:format_scenario_block()` and `market_intel.py`.  
**G4 ✅** — Cross-Border Transmission Matrix: India 10Y routed through consequence multipliers, `compute_net_fii_carry_yield()` (IND-US spread), `compute_dxy_inr_elasticity()` (60D rolling regression).  
**Analyst 1 P0/P1 ✅** — FII streak direction bug (used streak count not net sign), `Watch:` → `Triggers:`, `monitor` removed from triggers, Transition Phase re-scrubbed, DXY sign error (below baseline = relief not pressure), posture confidence aligned to verdict confidence. Stress EXTREME (≥80) forces full analysis over compressed one-liner.  
**10 missing DB purge entries added** — stress_history (180d), clone_history (180d), factor_scores_history (180d), sector_rs_history (180d), market_internals_history (180d), corporate_actions (90d), forecast_log (270d), analytics_ledger (270d), cftc_positioning_history (270d), earnings_surprises (730d).  
**CH ✅** — Calendar CSV staleness check (`check_calendar_staleness()` in economic_calendar.py) alerts Sunday digest when CSV expires. Weekly self-audit (`compute_self_audit()`) checks market_state/fii_flow/stress/clone data completeness. Brier calibration verified (already gated at n<10 in render_scorecard). `daily_market_snapshot` drop postponed until weekday verification.

**Analyst Review Regressions (2026-05-31) — 5 items:**
1. **CRITICAL: DXY β sanity guard** — `compute_dxy_inr_elasticity()` returned β=0.08 from low-correlation backfill data. Added `abs(beta) < 0.3` fallback to 0.85 (`consequence_engine.py:311`).
2. **CRITICAL: Stress score 95→59 swing** — Not a bug. Previous 95 was spurious (~20 data points). Post-backfill (252 pts) Z-score gives correct 59. Explained, no code change.
3. **MODERATE: Consequence baseline deviations** — Already present in output (`Brent above baseline (11%)`, `Copper above baseline by 42%`). No fix needed.
4. **MINOR: US10Y duplicate name** — `format_consequence_line()` repeated "US10Y 4.45%: US10Y above baseline...". Fixed via summary-prefix detection (`consequence_engine.py:531`).
5. **POLISH: `compound_stress` → `concurrent_breach`** — Override label renamed to avoid naming collision with stress index. Compressed one-liner now shows `Override: concurrent_breach` (`regime_arbiter.py:133`).

**Final verification (2026-05-31):** All 7/7 test suites pass. 8 jobs, 7 messages, 0 errors in full-day dry run. `data/econ_calendar_india_2026_27.csv` (5.6KB, 144 events) tracked in repo. Supabase `stress_history`/`corporate_actions`/`clone_history` tables exist. 15 workflow files pass infrastructure audit (cache@v4, timeout, python-id, env vars).

---
## CSV-First Architecture (Phase 1–3)

**Core insight:** Historical macro data is immutable. Every weekday job was refetching 5 years of unchanging data from yfinance — 14 `period="5y"` calls per market_intel run just for the clone engine.

**Shift:** CSV is the database for the past. Supabase is the database for the present. Heavy compute moves to Sunday. Weekdays become lightweight reads.

### Data Flow (One Direction Only)

```
LIVE DATA (yfinance, NSE API)
         │
         ▼
  ┌────────────────┐
  │  Supabase      │  ← WRITE path for today's data
  │  (operational) │    Every job writes current day to Supabase
  └───────┬────────┘
          │ Sunday 02:00 UTC — consolidation reads last 7 days
          ▼
  ┌────────────────┐
  │  CSV files     │  ← WRITE path for history
  │  (repo/data/)  │    sunday_backfill.py: read Supabase → append to CSV
  └───────┬────────┘
          │ Git push [skip ci]
          ▼
  ┌────────────────┐
  │  Git history   │  ← Immutable snapshot per Sunday
  └────────────────┘

  WEEKDAY READ PATH (data_fusion.py):
    CSV (5Y) → Supabase gap (last 7 days not yet archived) → live today
```

### Data Files (repo/data/)

| File | Rows | Size | Source | Updated |
|------|------|------|--------|---------|
| `anchor_history.csv` | ~1,304 | 474 KB | yfinance (5Y) + Supabase overlay | Sunday (delta) |
| `nifty_history.csv` | ~1,235 | 118 KB | yfinance (5Y) | Sunday (delta) |
| `fii_dii_history.csv` | ~58 | 1.6 KB | Supabase only (limited NSE history) | Sunday (delta) |
| `stress_history.csv` | — | — | Supabase stress_history | Sunday (delta) |
| `econ_calendar_india_2026_27.csv` | 144 | 5.6 KB | Static (manual update) | As needed |
| `scenario_clones_cache.csv` | — | — | Pre-computed distances | Sunday simulation (Phase 2) |
| `backtest_results.csv` | — | — | Walk-forward results | Sunday calibration (Phase 2) |

### Core Modules

**`src/sunday_backfill.py`** — The ONLY code that writes to CSV.
- Reads last 7 days from Supabase for each dataset
- Appends to CSV with deduplication (keep=last)
- Validates: no all-NaN cols, no zero prices, no >3% daily gaps, monotonic dates
- Marks Supabase rows `archived=true` after CSV write (two-phase commit)
- Git commits + pushes ONLY if ALL datasets succeed
- Runs conditional purge only if git push succeeded

**`src/purge_manager.py`** — Centralized `RETENTION_POLICY` for all Supabase tables.
- Single source of truth imported by `sunday_backfill.py` and `db.py`
- Three categories: HISTORICAL (archived+purge_archived), OPERATIONAL (age-only), REFERENCE (never)
- `purge_expired_tables()` respects two-phase: only deletes rows that are BOTH `archived=true` AND older than retention
- `get_retention_days()`, `is_historical_table()`, `archive_tables()` helpers

**`src/data_fusion.py`** — Single data access layer for all compute modules.
- `get_series(dataset, live_df)` → CSV + Supabase gap + live (merge, dedup, sort)
- `get_baselines(dataset, lookback=252)` → 252D mean for consequence engine
- `get_current_percentiles(dataset)` → expanding percentiles for pillar classifier
- `csv_freshness(dataset)` → check if CSV is within 14 days (for optional bypass)
- Bootstrap: if CSV < 252 rows, pulls older Supabase data to supplement

### Phase 1: CSV Foundation ✅

| Step | File | Status |
|------|------|--------|
| 1.1 | `scripts/generate_csvs.py` — one-time backfill from Supabase + yfinance | ✅ Done |
| 1.2 | `src/csv_data.py` — CSV reader + fusion layer | ✅ Done |
| 1.3 | Rewire clone_engine, stress_index, drawdown_anatomy to csv_data | ✅ Done |
| 1.4 | `.github/workflows/sunday_backfill.yml` — 02:00 UTC Sunday | ✅ Done |
| 1.5 | `.github/workflows/sunday_purge.yml` — conditional on backfill success | ✅ Done |
| 1.6 | Full-day dry-run: 8 jobs, 7 messages, 0 errors | ✅ Done |

**Gate to Phase 2:** Phase 1 must pass a full weekday dry-run with 0 errors.

### Phase 2: 12D Pillar Intelligence

**Goal:** Structural regime detection via 12D macro vector, dynamic transmission mechanics.

| Step | File | Status |
|------|------|--------|
| 2.1 | `src/pillar_classifier.py` — 6 pillars (Stagflation, De-dollarization, Tech Cycle, Regulatory, West Asia, EM Contagion, Carry Unwind) | Pending |
| 2.2 | Retroactive validation against historical data (check which dates trigger which pillars) | Pending |
| 2.3 | `src/transmission_mechanics.py` — RBI dilemma, USD debt, freight→CPI, carry yield | Pending |
| 2.4 | `data/scenario_clones_cache.csv` — pre-computed clone distances | Pending |
| 2.5 | `.github/workflows/sunday_simulation.yml` — 02:15 UTC Sunday | Pending |
| 2.6 | `.github/workflows/sunday_calibration.yml` — 02:30 UTC Sunday | Pending |

**Gate to Phase 3:** Pillar calibration must pass backtest against 4 historical episodes (2013 Taper, 2018 EM, 2020 COVID, 2022 Fed).

### Phase 3: Intraday Pulse

**Goal:** 30-min intraday scanner during market hours (9:15–15:30 IST).

| Step | File | Status |
|------|------|--------|
| 3.1 | `jobs/intraday_pulse.py` — Nifty spot + VIX scanner | Pending |
| 3.2 | `.github/workflows/intraday_pulse.yml` — `*/30 3:45-10:00 1-5` | Pending |
| 3.3 | Supabase `intraday_pulse` table | Pending |

### Weekday Runtime Reduction

| Job | Before (~s) | After (~s) | Savings |
|-----|-----------|-----------|---------|
| market_intel (morning) | 35-100s | 5-10s | ~86% |
| market_intel (evening) | 35-100s | 5-10s | ~86% |
| market_open | 8-12s | 3-5s | ~60% |
| midday_scan | 5-8s | 2-3s | ~60% |
| market_close | 8-12s | 3-5s | ~60% |

### SPY + EEM in Anchor CSV
SPY (S&P 500 ETF) and EEM (MSCI Emerging Markets ETF) added to anchor CSV so clone engine forward-return computation uses zero yfinance calls. Previously these required 2× `yf.Ticker().history(period="5y")` per run.

### Bootstrap Safety Net
`src/csv_data.py:get_nifty_close_series()` reads from CSV and falls back to yfinance if CSV is empty/corrupt. All callers use this function instead of raw `yf.Ticker().history()`. Bootstrap auto-generates ALL CSVs from yfinance on first `load_history()` if any are missing — runs once per session, cached thereafter.

### Data Quality Gate
`csv_data.py:_load_csv()` rejects CSVs that fail quality checks and treats them as empty (triggering fallback to Supabase/yfinance):
- **Minimum rows**: 100 for anchors/nifty, 5 for fii_dii
- **Column integrity**: core columns must exceed 30% non-NaN ratio
- **Sparse data fallback**: falls back to Supabase if a symbol has <25% coverage
- **Freshness**: `csv_freshness()` checks if latest data point is within 14 days

## Test Commands
- `.venv/bin/python3 test_all_outputs.py` — 7 sections, 26 patterns, emoji consistency check
- `.venv/bin/python3 test_supabase_full.py` — 20 Supabase feature checks
- `.venv/bin/python3 test_full_day.py` — 8-job dry-run simulation (requires `DRY_RUN=1`)
- `scripts/generate_csvs.py` — One-time CSV generation from Supabase + yfinance
- All require `SUPABASE_URL` + `SUPABASE_KEY` from `../apikeys.txt` (supports `KEY=value` or `KEY: value` format)
