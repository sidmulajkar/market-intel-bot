# CLAUDE.md

Indian market intel bot — 14 cron jobs, daily Telegram (text + heatmaps).  
**Stack:** Python, Supabase (30 tables), Telegram, Groq/Gemini, NSE/AMFI/SEBI, FinBERT.

**Core rule:** Python computes, AI narrates. No invented data, no advice. Scrubber catches 26 patterns (bidirectional, last-pass in `send_text()`).

---

## Jobs (GHA, stateless)

| Time | Job | Purpose |
|------|-----|---------|
| 5AM | `fii_dii_fetch` | NSE FII/DII → Supabase |
| 7AM | `market_intel morning` | Full 11-block AI |
| 8AM | `morning_brief` | Heatmaps + regime card (1 text) |
| 9:15 | `market_open` | Python-only open brief (no AI) |
| 12:30 | `midday_scan` | Skip gate (>1% Nifty or skip); breadth + sector RS + options delta |
| 15:30 | `market_close` | EOD + pillars + derivatives + drawdown |
| 18:00 | `market_intel evening` | Delta tracker → compressed if unchanged |
| 20:00 | `evening_report` | US session + outlook |
| Sun | `weekly_digest` | Scorecard + institutional signals |
| Sun 02:00 | `sunday_backfill` | CSV consolidation + purge |
| Sun 02:15 | `sunday_simulation` | Pillar metrics pre-compute |
| Sun 02:30 | `sunday_calibration` | Walk-forward backtest |
| Mon–Fri | `intraday_pulse` | 30-min Nifty+VIX (state-change-only) |
| Fri | `deals_tracker`, `credit_monitor`, `mf_flows`, `insider_tracker` | Specialized |

**CI:** `actions/cache@v4` keyed on `hashFiles('requirements.txt')`, `timeout-minutes:10`, `setup-python` with `id:python`. Target <3 min runtime.

---

## AI Routing

| Mode | Primary | Fallback |
|------|---------|----------|
| `analyze("fast")` | Groq (llama-3.3-70b) | Gemini-2.0-flash |
| `analyze("volume")` | Gemini-2.0-flash | Groq |
| `sentiment(text)` | FinBERT (HuggingFace, circuit-broken) | — |

- Max tokens: 1000, Temp: 0.3. `has_quota()` pre-checks (60s cache).
- Strong-conviction fallback: AI exhausted + 2+ extremes (USDINR≥90, Brent≥90, VIX≥20, Gold≥4000, FII streak≥3).

---

## Macro Anchors (19, yfinance batch)

`USDINR=X` · `BZ=F` · `GC=F` · `^INDIAVIX` · `DX-Y.NYB` · `^TNX` · `^VIX` · `HYG` · `LQD` · `SOXX` · `CL=F` · `JPY=X` · `EURUSD=X` · `SI=F` · `HG=F` · `2YY=F` · `ES=F` · `NQ=F` · `^N225`

---

## Core Modules

- **Data:** `data_fetcher` (batch yfinance, ThreadPool), `nse_session` (5-min TTL, circuit-broken), `db` (Supabase CRUD+purge), `csv_data` (CSV reader + quality gate + fallback), `data_fusion` (CSV+Supabase+live merge)
- **Context:** `context_engine` (BB 8-signal, phase classifier), `signal_arbitrator` (gap→master signal), `global_arbiter` (4-state), `consequence_engine` (India impact multipliers, 252D baseline, 30% variance cap, WTI/Brent coherence), `transmission_mechanics` (6 causal chains: RBI dilemma, freight→CPI, USD debt, carry yield, Eurodollar gap, denominator effect)
- **Derivatives:** `options_engine` (PCR, max pain, GEX, skew, magnetic levels via v3 NSE + file cache), `fii_derivatives` (F&O OI)
- **Pillars (P2):** `pillar_classifier` — 6 dims (Stagflation, West Asia, EM Contagion, Carry Unwind, De-dollarization, Tech Cycle), threshold-gated weight-normalized scoring, ↑↓ arrows in detection
- **Intelligence:** `prompt_engine`, `quant_enrichment`, `prediction_tracker` (Brier, override-aware vs final_regime)
- **Synthesis:** `stress_index` (Z-score composite: VIX 25%, FII 25%, USDINR 15%, Brent 15%, Skew 10%, Breadth 10%), `clone_engine` (6D India + 5D Global + transmission, Euclidean NN), `drawdown_anatomy`, `sector_rs` (LEADING/PEAKING/LAGGING/RECOVERING), `flow_velocity` (5D vs 21D Z-score), `scenario_engine`
- **Quality:** `output_validator` (26 patterns), `validation_helper` (3-stage: leakage → ghost regime → trading signals, incl `Posture:` lines + `OMCs`/`oil importers`), `block_validator`, `validator` (news trust), `staleness_detector`, `compute_budget`
- **Output:** `formatters` (11 blocks, `format_scenario_block` includes pillars + transmission + clones), `telegram_sender` (mockable, final-pass scrubber), `heatmap_generator`, `delta_renderer`, `bot_handler` (6 commands: /stress /clone /flows /gex /sectors /whatif)
- **Specialized:** `economic_calendar` (144 events CSV, 12mo lookahead), `corporate_actions` (NSE corp-info API), `insider_tracker`, `fii_sector`, `fii_decomposition`, `dii_capacity`, `intraday_pulse`, `mf_flows`, `turnover_ratio`, `market_internals`, `bulk_block_deals`

---

## Key Patterns

- **Regime Arbiter:** Single compute 08:00 → `market_state.final_regime`. Downstream read-only. Global Arbiter Layer 1b (STAGFLATION/LIQUIDITY→FORCE DEFENSIVE, RISK_OFF→cap NEUTRAL). Pillar Layer (Fragility hook). Overrides: `concurrent_breach`, `stress_index`. `_defensive_triggers()` shows escalation/de-escalation thresholds.
- **CSV-first:** Historical data in CSV (1,304 rows, 24 cols). Supabase = present day only. Sunday backfill reads Supabase → appends to CSV → two-phase commit → conditional purge. Weekday reads: CSV(5Y) → Supabase gap → live. `sunday_simulation` pre-computes pillar_metrics + clone cache.
- **NSE v3 options:** Two-step (`contract-info` → expiry → `chain-v3`). File cache fallback. Options fallback: ① Supabase ② MarketState ③ live fetch ④ file cache.
- **Compressed fallback:** Regime unchanged + VIX stable + stress < 80 → one-liner. Shows regime + macro data + high-impact events. Stress ≥ 80 forces full analysis.
- **Delta tracker:** Morning fingerprint stored; evening compares thresholds (Nifty 0.3%, VIX 1.5, USDINR 0.5%, Brent 3%, FII 500 Cr, regime). Compressed if unchanged.
- **Skip gate (midday):** Nifty >1% OR VIX spike >20% OR 5%+ stock moves. `(< 1.0% threshold)` notation.
- **Headline dedup:** MD5 hash → `market_state.seen_headlines` JSONB.
- **Scrubber (3-stage):** Leakage → `_strip_ghost_regime` → `_strip_trading_signals` (26 patterns incl `Posture:`, `OMCs`, `oil importers`). Runs in `send_text()` on ALL output.
- **Macro sanity:** Wide bounds + daily-change thresholds (forex 3%, VIX 15%, yields 10%, commodities 8%).
- **Consequence:** Baseline deviation >5% (DXY>4%, VIX>3%) = show. Severity: 📌/⚠️/🚨. 30% variance cap.
- **Signal weights:** Dynamic from accuracy (>65% ×1.3, <45% ×0.7).
- **Scorecard:** Brier + calibration. Suppressed n<10. Override-aware vs `final_regime`.
- **No local imports in `main()`:** Use module-level imports only.
- **All formatters return `""` on failure.** NaN via `_safe_float()`.
- **Intraday pulse:** 30-min Nifty+VIX → CALM/WATCH/ALERT. State-change-only sends. `intraday_pulse` table (7d retention).
- **Pillar detection:** Detection lines show dims with ↑(stress)/↓(relief). 6 pillars. Score normalizes by total weight (breadth requirement).
- **Transmission chains:** Wired into `format_scenario_block()` per active pillar. 6 deterministic functions (RBI dilemma, freight→CPI, USD debt, carry yield, Eurodollar gap, denominator effect).

---

## Supabase Storage Budget (2GB limit)

**Retention:**

| Category | Tables | Purge |
|----------|--------|-------|
| Historical | macro_anchor_snapshots, fii_dii_flows, market_breadth_history, stress_history, valuation_history | archived=true + 365d |
| Operational | market_state(90d), analysis_cache(7d), sent_alerts(30d), forecast_log(90d), clone_history(180d), pillar_metrics(365d), intraday_pulse(7d), signal_accuracy_log(365d), prediction_outcomes(90d), analytics_ledger(90d), cftc_positioning_history(270d), factor_scores(180d), sector_rs(180d), market_internals(180d), corporate_actions(90d), earnings_surprises(730d), options_snapshots(7d) | age |
| Reference | watchlist, mf_watchlist, bot_state | never |

Two-phase archive: `archived=true` → then delete archived+aged. Conditional purge runs only after backfill commit. `purge_manager.py` single source of truth.

---

## State: All Phases Done ✅

**P0-36:** 58+ modules, 270+ functions, 14 cron jobs, 31 tables, 15 workflows. Full-day dry-run: 8 jobs, 6 messages, 0 errors. Calibration 94% pass rate (7/10 episodes testable).

**P39 A0–A4:** Stock prompt sanitized, GEX magnetic levels, drawdown anatomy, sector phases, 6 Telegram commands, pinned glossary.

**P40-49:** LQD+SOXX anchors, global arbiter (4-state, 4-episode backtest), 2-tier global clone engine, cross-border transmission matrix, codebase health (calendar staleness, self-audit, purge entries).

**P1 (CSV):** `anchor_history.csv` (1,304×24), `nifty_history.csv` (1,235), `fii_dii_history.csv` (58). Backfill → purge pipeline. SHAP+EEM for clone fwd returns.

**P2 (Pillars):** `pillar_classifier.py` — 6 pillars (Stagflation, West Asia, EM Contagion, Carry Unwind, De-dollarization, Tech Cycle). Threshold-gated weight-normalized. ↑↓ arrows. `transmission_mechanics.py` — 6 deterministic chains. Wired into `format_scenario_block()` + market_intel. `sunday_simulation` pre-computes. Calibration: 94% pass (7 testable).

**P3 (Intraday):** `intraday_pulse.py` — 30-min Nifty+VIX, CALM/WATCH/ALERT, state-change-only. GHA `*/30 4-9 * * 1-5`.

**Logic audit fixes (7 items):** Trading advice stripped from posture lines, Credit_Ratio direction fixed (stress→relief), ↑↓ arrows in detection, transmission wired, override labels human-readable, midday skip notation fixed, scrubber expanded.

---

## Test Commands

- `.venv/bin/python3 test_all_outputs.py` — 7 sections, 26 patterns
- `.venv/bin/python3 test_supabase_full.py` — 20 Supabase checks
- `.venv/bin/python3 test_full_day.py` — 8-job dry-run (`DRY_RUN=1`)
- Needs `SUPABASE_URL`+`SUPABASE_KEY` from `../apikeys.txt`

---

## Env Vars

| AI Jobs | Data Jobs |
|---------|-----------|
| `GROQ_API_KEY`, `GOOGLE_AI_KEY`, `HF_KEY` | `SUPABASE_URL`, `SUPABASE_KEY` |
| `SUPABASE_URL`, `SUPABASE_KEY` | `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` |
| `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` | |

`DRY_RUN=1` enables mock mode (prints to console, no Telegram).

---

## Next Phases (Analyst 1 Proposal)

| # | Phase | Module | What | Effort |
|---|-------|--------|------|--------|
| 1 | **P4** | `fragility_index.py` + `pillar_lifecycle.py` | Unify pillars + stress into Fragility Index (Base Fragility×0.40 + Breadth×5 + Intensity×0.30). Track pillar lifecycle (EMERGING→ESCALATING→SUSTAINED→DE-ESCALATING). Wire into regime arbiter: Fragility>65 cap NEUTRAL, >85 force DEFENSIVE. | 4 hr |
| 2 | **P5** | `fii_decomposition.py` + `dii_capacity.py` + `sectoral_drag.py` | FII: Top-5 sellers, concentration metric (broad vs focused exit). DII: deployment ratio (DII net buy / DII net buy + MF new flows), 5D saturation detection, cushion erosion. Sector: Map pillar chains to actual FII sector flows + RS confirmation. | 5 hr |
| 3 | **P6** | `event_volatility.py` + pre-event positioning + intraday pillar confirmation | Event volatility profiler (5yr lookback: avg Nifty move ±?, VIX change). Pre-event PCR/skew shift detection. Intraday pillar confirmation via 30-min pulse data (Brent↑→Nifty↓ validates Stagflation transmission). | 3 hr |

**Recommendation:** Start P4 — Fragility Index bridges the gap between pillar intelligence and regime arbiter. Without it, USDINR at 94.9 (below hard 95 trigger) masks 3 pillars at 60+.
