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
| 12:30 | `midday_scan` | Skip gate (>1% Nifty or skip); breadth + sector RS + options delta + intraday pillar check |
| 15:30 | `market_close` | EOD + pillars + derivatives + drawdown |
| 18:00 | `market_intel evening` | Delta tracker → compressed if unchanged |
| 20:00 | `evening_report` | US session + outlook |
| Sun | `weekly_digest` | Scorecard + institutional signals |
| Sun 02:00 | `sunday_backfill` | CSV consolidation + purge |
| Sun 02:15 | `sunday_simulation` | Pillar metrics pre-compute |
| Sun 02:30 | `sunday_calibration` | Walk-forward backtest |
| Mon–Fri | `intraday_pulse` | 30-min Nifty+VIX (state-change-only) |
| Fri | `deals_tracker`, `credit_monitor`, `mf_flows`, `insider_tracker` | Specialized |

**CI:** `actions/cache@v4` keyed on `hashFiles('requirements.txt')`, `timeout-minutes:10`, `setup-python` with `id:python`. Skip-state persistent via `actions/cache@v4` (key `skip-state-${{ github.run_id }}`, restore-keys `skip-state-`). Target <3 min runtime.

---

## AI Architecture: Python Computes, AI Narrates

**The Iron Rule:** Data never originates inside the LLM. The LLM receives a structured data payload assembled by Python, and its only job is rhetorical transformation — turning numbers and boolean flags into readable sentences. If Python did not compute it, the AI cannot say it.

### Enforcement Strategy
| Layer | Mechanism |
|-------|-----------|
| **Input isolation** | Python builds the full prompt string; AI never receives raw API access or unvalidated data |
| **Output scrubber** | 63-pattern regex runs on **all** `send_text()` output as final-pass gate; logs stripped content to `analytics_ledger` |
| **Validation** | `output_validator.py` checks for ghost regimes, invented tickers, trading signals |
| **No temperature for facts** | Temp 0.3 on all factual summarization; max tokens 1000 to prevent rambling |
| **Structured fallback** | If AI fails/quota exhausted, Python returns bullet-point stubs from `formatters.py` |

### Routing Table

| Mode | Primary | Fallback | Temp | Tokens |
|------|---------|----------|------|--------|
| `analyze("fast")` — short narrative | Groq (llama-3.3-70b) | Gemini 2.0 Flash | 0.3 | 1000 |
| `analyze("volume")` — 11-block intel | Gemini 2.0 Flash | Groq | 0.3 | 1000 |
| `sentiment(text)` | FinBERT (HuggingFace, circuit-broken) | None | 0.0 | N/A |
| NL intent parsing (P9 Agent) | Gemini 2.0 Flash | Groq | 0.2 | 200 |

- `has_quota()` pre-checks Groq rate limits (60s cache) before routing.
- Strong-conviction fallback: AI exhausted **and** ≥2 macro extremes (USDINR≥90, Brent≥90, VIX≥20, Gold≥4000, FII streak≥3) → bypass AI, emit pre-computed alert template. Wired in `market_intel.py` before AI call.

### Prompt Engine (`src/prompt_engine.py`)
Schema-bound builder that raises exceptions if required keys are missing. The prompt itself carries scrubber rules as negative instructions to reduce hallucination before it reaches the output validator.

### Sentiment: FinBERT + Circuit Breaker
- Runs locally on news headlines (deduped via MD5 → `market_state.seen_headlines`) + Telegram retail chatter (optional).
- **Circuit breaker:** If inference >5s (cold start) or >50% neutral → fall back to **keyword polarity** (VADER-like heuristic on headlines only).
- Output: Single float `[-1.0, 1.0]` — AI is instructed: *"Sentiment is {value}. Describe it as bearish/neutral/bullish. Do not explain why."*

### P9 Agent: The "No SQL-Gen" Rule
LLM never writes a `WHERE` clause. **Intent Catalog** — 14 closed-set intents, each with a deterministic executor. The LLM only classifies which intent; Python fills slots and executes:
```python
INTENT_MAP = {
    "get_fii_decomposition": { "executor": fii_decomposition.get_for_date },
    "simulate_macro": { "executor": scenario_simulator.simulate },
    # 14 total
}
```

### Scrubber: Final-Pass Firewall
63 patterns in 4 categories (leakage, ghost regime, trading signals, price targets). If stripped, logs to `analytics_ledger` for audit.

### When AI Is Bypassed Entirely
Three conditions where the pipeline never calls AI:
| Condition | Behavior |
|-----------|----------|
| **Compressed fallback** (delta unchanged) | Python one-liner from `formatters.py` |
| **Sentinel halt** (P10 preflight fails) | Pre-computed alert: `Data integrity failure. Regime locked.` |
| **Strong conviction** (2+ extremes + AI quota exhausted) | Hard template: `DEFENSIVE regime triggered by [X]. No analysis available.` |

### Data Flow: Where AI Lives (and Where It Doesn't)
```
07:00 MARKET INTEL — AI narrates tension paragraph only (2 sentences)
08:00 MORNING BRIEF — AI: NONE (deterministic formatting)
09:15 MARKET OPEN — AI: NONE
12:30 MIDDAY SCAN — AI: NONE (computed pillar status)
15:30 MARKET CLOSE — AI: NONE (all deterministic blocks)
18:00/20:00 EVENING — AI: only if delta triggers full analysis; compressed = AI skipped
```

### Portability
To swap models (Claude, local Llama, etc.), touch only: `src/ai_engine.py` (router + prompt templates), `src/prompt_engine.py` (block ranking utilities), 63-pattern regex in `validation_helper.py` (model-agnostic). The math — fragility, lifecycle, tick counting — is pure Python.

---

## Macro Anchors (19, yfinance batch)

`USDINR=X` · `BZ=F` · `GC=F` · `^INDIAVIX` · `DX-Y.NYB` · `^TNX` · `^VIX` · `HYG` · `LQD` · `SOXX` · `CL=F` · `JPY=X` · `EURUSD=X` · `SI=F` · `HG=F` · `2YY=F` · `ES=F` · `NQ=F` · `^N225`

---

## Core Modules

- **Data:** `data_fetcher` (batch yfinance, ThreadPool), `nse_session` (5-min TTL, circuit-broken), `db` (Supabase CRUD+purge), `csv_data` (CSV reader + quality gate + fallback), `data_fusion` (CSV+Supabase+live merge)
- **Context:** `context_engine` (BB 8-signal, phase classifier), `signal_arbitrator` (gap→master signal), `global_arbiter` (4-state), `consequence_engine` (India impact multipliers, 252D baseline, 30% variance cap, WTI/Brent coherence), `transmission_mechanics` (6 causal chains: RBI dilemma, freight→CPI, USD debt, carry yield, Eurodollar gap, denominator effect)
- **Derivatives:** `options_engine` (PCR, max pain, GEX, skew, magnetic levels via v3 NSE + file cache), `fii_derivatives` (F&O OI)
- **Pillars (P2):** `pillar_classifier` — 6 dims (Stagflation, West Asia, EM Contagion, Carry Unwind, De-dollarization, Tech Cycle), threshold-gated weight-normalized scoring, ↑↓ arrows in detection
- **P4 (Fragility+Lifecycle):** `fragility_index` (Base 40%/Breadth 30%/Intensity 30%, caps BULLISH at 65, forces DEFENSIVE at 85), `pillar_lifecycle` (EMERGING×0.6→ESCALATING→SUSTAINED→DE-ESCALATING)
- **P5 (Institutional Micro):** `fii_decomposition` (entity concentration, Broad-based vs Concentrated), `dii_capacity` (deployment ratio, SATURATED/CRITICAL/COMFORTABLE), `sectoral_drag` (pillar-flow match with T-1 cache)
- **P6 (Event Dynamics):** `event_volatility` (historical Nifty/VIX profiles, n≥3), options_engine.`detect_pre_event_positioning` (PCR/Skew shift ≤2d before events), intraday_pulse.`check_intraday_pillar_confirmation` (tick-counting at 12:30)
- **Intelligence:** `prompt_engine`, `quant_enrichment`, `prediction_tracker` (Brier, override-aware vs final_regime)
- **Synthesis:** `stress_index` (Z-score composite: VIX 25%, FII 25%, USDINR 15%, Brent 15%, Skew 10%, Breadth 10%), `clone_engine` (6D India + 5D Global + transmission, Euclidean NN), `drawdown_anatomy`, `sector_rs` (LEADING/PEAKING/LAGGING/RECOVERING), `flow_velocity` (5D vs 21D Z-score), `scenario_engine`
- **Quality:** `output_validator` (26 patterns), `validation_helper` (3-stage: leakage → ghost regime → trading signals, incl `Posture:` lines + `OMCs`/`oil importers`), `block_validator`, `validator` (news trust), `staleness_detector`, `compute_budget`
- **Output:** `formatters` (11 blocks, `format_scenario_block` includes pillars + transmission + clones), `telegram_sender` (mockable, final-pass scrubber), `heatmap_generator`, `delta_renderer`, `bot_handler` (6 commands: /stress /clone /flows /gex /sectors /whatif)
- **Specialized:** `economic_calendar` (144 events CSV, 12mo lookahead), `corporate_actions` (NSE corp-info API), `insider_tracker`, `fii_sector`, `mf_flows`, `turnover_ratio`, `market_internals`, `bulk_block_deals`

---

## Key Patterns

- **Skip state: local-first, GHA-cached.** `data/skip_state.json` is primary storage for fingerprint/sent-at metadata. Supabase `bot_state` is best-effort fallback. GHA workflows cache with `actions/cache@v4` (key `skip-state-${{ github.run_id }}`, restore-keys `skip-state-`). Zero cloud dependency for gate logic.
- **Regime Arbiter:** Single compute 08:00 → `market_state.final_regime` + `market_state.final_regime_confidence` (data-completeness gauge: LOW/MEDIUM/HIGH). Downstream read-only. Global Arbiter Layer 1b (STAGFLATION/LIQUIDITY→FORCE DEFENSIVE, RISK_OFF→cap NEUTRAL). Pillar Layer (Fragility hook). `_defensive_triggers()` shows escalation/de-escalation thresholds.
- **Arbiter override hierarchy:** Only Layer 1b (Global Arbiter) + Layer 2 (Fragility Index) remain. Hard-coded price thresholds (USDINR > 94.5, Brent > 90) deleted. Fragility > 65 caps NEUTRAL, > 85 forces DEFENSIVE.
- **CSV-first:** Historical data in CSV (1,304 rows, 24 cols). Supabase = present day only. Sunday backfill reads Supabase → appends to CSV → two-phase commit → conditional purge. Weekday reads: CSV(5Y) → Supabase gap → live. `sunday_simulation` pre-computes pillar_metrics + clone cache.
- **NSE v3 options:** Two-step (`contract-info` → expiry → `chain-v3`). File cache fallback. Options fallback: ① Supabase ② MarketState ③ live fetch ④ file cache.
- **Compressed fallback:** Regime unchanged + VIX stable + stress < 80 → one-liner. Shows regime + macro data + high-impact events. Stress ≥ 80 forces full analysis.
- **Delta tracker:** Morning fingerprint stored; evening compares thresholds (Nifty 0.3%, VIX 1.5, USDINR 0.5%, Brent 3%, FII 500 Cr, regime). Compressed if unchanged.
- **Skip gate (midday):** Nifty >1% OR VIX spike >20% OR 5%+ stock moves. `(< 1.0% threshold)` notation.
- **Headline dedup:** MD5 hash → `market_state.seen_headlines` JSONB.
- **Scrubber (3-stage):** Leakage → `_strip_ghost_regime` → `_strip_trading_signals` (26 patterns incl `Posture:`, `OMCs`, `oil importers`). Runs in `send_text()` on ALL output.
- **Scrubber deterministic exemption:** Lines starting with `📌🟢🔴🟡📊📈📉⚠️🚨━` bypass `_strip_trading_signals` and `_strip_ghost_regime` (but still pass `_scrub_leakage`). Prevents false-positive stripping of deterministic output like `🟡 *REGIME: NEUTRAL*` and `No notable change`. Logic in `_is_deterministic_line()` in `validation_helper.py`.
- **No `Posture:` output from jobs.** All `Posture:` → `Context:` or `Market Context:`. `evening_report.py` uses arbiter-locked `📌 *Context:* Regime: {label}. {desc}`. `market_open.py` uses `📌 Market Context: {regime_label} | {gap_direction}`. No separate posture engine runs for output; `compute_posture` is only used for watch levels.
- **Scorecard regime validation:** `prediction_tracker.py` rejects `Transition` as a valid regime label. AI labels mapped: `Risk-on→BULLISH, Risk-off→DEFENSIVE, Neutral→NEUTRAL`. Falls back to arbiter's `final_regime` if AI prediction is empty or invalid.
- **Regime confidence (`(LOW)`/`(MEDIUM)`/`(HIGH)`):** Python-computed data-completeness gauge from `regime_arbiter.py:_count_signals()`. Counts how many of 7 data signals (VIX, Brent, DXY, FII, DII, PCR, breadth) were non-null at arbiter compute time. `HIGH`=5-7, `MEDIUM`=3-4, `LOW`=0-2. Displayed in Market Intel regime line only (`🟡 *REGIME: NEUTRAL* (LOW) | Nifty...`). Distinct from Fragility Index (structural stress) and override system (global regime force).
- **Nifty display consistency:** All jobs use live `^NSEI` from yfinance (`fetch_global_indices()`) for display. Market Intel previously used stale `nifty_history.csv` (Sunday-only updates) causing drift vs Open/Close messages. Fixed: Intel now reads live Nifty from `index_data` first, falls back to CSV. All 7 daily messages show the same Nifty value.
- **Flows block null-safe fallback:** In `market_close.py`, if `flow_metrics.ok` is False (Supabase `fii_dii_flows` has <3 rows), the main flows block emits `📌 *Flows:* Data pending (5AM fetch required)` instead of silence. FII Decomposition and DII Capacity blocks are independent (separate Supabase queries) and appear below the main flows line even when flow_metrics fails. Guard: `if not flows_block.startswith("📊 *Flows:*")` prepends the fallback.
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

## State: v0.5-beta — Phases A–C Wired, Skip Gate Live

**P0–P12:** 58+ modules, 270+ functions, 14 cron jobs, 31 tables, 15 workflows. All locked.

**P14/P16/P18 (Skip Gate + Manifest + Guardian):** ✅ Wired into 3 main jobs (market_intel, midday_scan, market_close). Fingerprint hashes raw anchors (Nifty, VIX, USDINR, Brent, DXY, FII bucket + manifest version). `should_skip()` → hard skip (<4h) or heartbeat stub (≥4h, no AI). Guardian 3-tier (GREEN/YELLOW/RED) replaces binary P10 halt. Full dry-run: 8/8 jobs, 3 of 7 messages are skip stubs on flat day.

**P27 (State Journal):** `src/state_journal.py` — `append_journal()`, `get_last_journal()`, `get_last_n_journals()`, `cleanup_journal()`. Wired into market_intel, midday_scan, market_close. Deferred in .gitignore pending Supabase key.

**P28 (Lifecycle Drift):** `detect_stale_lifecycle()` in `src/pillar_lifecycle.py` — checks pillar score trajectory for >5pt peak drop or >4pt 3-day decline while lifecycle still shows ESCALATING/SUSTAINED.

**P29 (Pillar Decay / Half-Life):** `pillar_half_lives` in `data/manifest.json` (Stagflation=10d, West Asia=7d, EM=14d, Carry=10d, DeDollar=21d, Tech=14d). `_get_pillar_decay()` in `src/fragility_index.py` — `exp(-0.1 × max(0, age - half_life))` applied in intensity computation.

**P30 (Paper P&L):** `src/prediction_tracker.py` — `position_today = map_regime_to_position(final_regime)` (+1/0/-1). Daily return = `position_yesterday × Nifty_return_today`. Friction 0.12% STT + 5bps slippage. Weekly: `Paper Track (YTD): Gross +X% | Net +Y% | Buy-Hold +Z%`.

**Supabase resilience:** `bot_state.py` uses `data/skip_state.json` as primary storage, Supabase as best-effort fallback. GHA workflows cache skip state via `actions/cache@v4`. Adaptive weights fall back to `manifest.json` on DB failure. Tombstone blocks suppressed (no "PCR unavailable" / "Data pending" noise).

**Batch-4 compliance fixes:** All `Posture:` output eliminated. `(LOW)` confidence provenance documented. Evening Intel delta gate confirmed wired. Scrubber hardened. Flows block null-safe fallback. Nifty consistency across all 7 messages. Evening Report `None.upper()` crash fixed.

**Logic audit fixes (7 items):** Trading advice stripped from posture lines, Credit_Ratio direction fixed (stress→relief), ↑↓ arrows in detection, transmission wired, override labels human-readable, midday skip notation fixed, scrubber expanded.

**Batch-4 compliance fixes:** All `Posture:` output eliminated (evening_report → regime, market_open → Market Context, morning_brief → Context from arbiter, AI prompt bans). `(LOW)` confidence provenance documented (Python `_count_signals()` in `regime_arbiter.py`). Evening Intel delta gate confirmed wired and working. Scrubber hardened — `_is_deterministic_line()` returns False for lines containing `Posture:`, `_strip_ghost_regime()` strips Posture with orphan-line cleanup. Flows block null-safe fallback with `startswith("📊 *Flows:*")` guard. Nifty consistency across all 7 messages (live `^NSEI`). Evening Report `None.upper()` crash fixed. P14 fingerprint/datetime scoping bug fixed.

---

## v0.5-beta Scorecard

**Overall: 8.1 / 10** — From expensive macro newspaper to cheap, self-regulating membrane. Now knows when it has nothing to say — and shuts up instead of burning tokens to narrate flat air.

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| **Deterministic Architecture** | 9.0/10 | P14 skip gate is battle-proven; manifest is single source of truth; "Python computes, AI narrates" enforced by infrastructure, not just convention. |
| **Operational Efficiency** | 9.0/10 | Fingerprint gate collapsed AI burn from ~14/week to ~1/week on flat days. GHA runtime <30s for stubs. Cost curve just bent. |
| **Honesty / Integrity** | 9.0/10 | Adaptive weights <1.0 explicitly confess pillars are weak predictors. Unavailable blocks suppressed, not faked. Holdout wall blocked overfitting. |
| **Data Resilience** | 8.0/10 | Bypassed Supabase 401 cleanly. Local `skip_state.json` + GHA cache is correct pattern for stateless runners. Guardian YELLOW/RED wired but not battle-tested. |
| **User Utility** | 7.5/10 | Output is surgically clean — no tombstones, no duplicate prepends. Deduction: Market Close stubs to "No material change," which means EOD flows/scorecard vanish on quiet days. |
| **Signal Validity** | 6.5/10 | Holdout wall did its job. But still zero empirical proof the regime call is better than a coin flip. P30 needs 14 days of data before this score moves. |

### What Keeps It From 9.0
- **No evidence of edge yet.** Architecture is brilliant; signal is still theoretical. After two Sunday paper P&L prints, this could jump to 8.5+ or drop to 7.5 if the regime is random.
- **Market Close is a ghost on quiet days.** A one-line stub is honest, but users may want at least a condensed flows line even when Nifty hasn't budged. Middle tier needed: minimal deterministic block for Close instead of full stub.

### Remaining Limitations
- **Options layer structurally unreliable:** NSE v3 fallback chain produces `PCR unavailable` on most days. Should be downgraded to conditional bonus block.
- **FII entity decomposition permanently 90% incomplete:** SEBI/NSE do not publish real-time entity-level flows. Module is honest but signal is noise-dressed-in-math.
- **P31/P32 not built:** Hollow liquidity detector and containment mode still designed-only.
- **No divergence block (P15):** Skip gate is blind to internal stress (VIX screaming while Nifty flat, sector divergence, macro-implied vs actual decoupling).

### Ship Verdict: Push v0.5-beta
The architecture is more honest and efficient than 99% of retail quant tooling. The remaining work is not engineering — it is **epistemological patience**. You need to know if the signal works before you polish the message.

---

## Test Commands

- `.venv/bin/python3 test_all_outputs.py` — 7 sections, 26 patterns (no API keys needed)
- `.venv/bin/python3 test_supabase_full.py` — 20 Supabase checks (needs key)
- `DRY_RUN=1 .venv/bin/python3 jobs/market_intel.py` — single job dry-run
- Needs `SUPABASE_URL`+`SUPABASE_KEY` from `../apikeys.txt` for Supabase-dependent tests only

---

## Env Vars

| AI Jobs | Data Jobs |
|---------|-----------|
| `GROQ_API_KEY`, `GOOGLE_AI_KEY`, `HF_KEY` | `SUPABASE_URL`, `SUPABASE_KEY` |
| `SUPABASE_URL`, `SUPABASE_KEY` | `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` |
| `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` | |

`DRY_RUN=1` enables mock mode (prints to console, no Telegram).

---

## Phase 4: Pillar-Regime Convergence & Lifecycle

**Core Problem:** The 12D Pillar Classifier and the Regime Arbiter are currently two separate engines that shake hands but don't share a circulatory system. The Arbiter still uses raw, hard-coded thresholds (e.g., `USDINR > 95`). The Pillars output scores (Stagflation 63, Carry 47). But if USDINR drops to 94.9, the hard trigger fails, and the Arbiter might label the regime "NEUTRAL" even if three pillars are screaming at 60+. Multi-pillar environments are structurally fragile even without a single variable breaching a hard threshold. Furthermore, a pillar appearing on Day 1 is treated identically to a pillar on Day 15. Time is a massive variable currently missing from the logic.

### 4.1: Macro Fragility Index
Replaces the binary `concurrent_breach` override with a continuous composite score measuring *breadth* of structural stress.

**Computation (3 components, weight-normalized):**
- **Base Fragility (Weight 0.40):** Existing Stress Index (VIX 25%, FII 25%, USDINR 15%, Brent 15%, Skew 10%, Breadth 10%). Measures the *immediate tactical* heat in the market — the stuff that hits Nifty today.
- **Pillar Breadth (Weight 0.30):** Count pillars scoring ≥ 40, multiply by constant 7.5. If 4 pillars are active, breadth = 30 points. Rationale: A single pillar at 80 is less dangerous to the systemic structure than four pillars at 50. Four pillars mean cross-contamination is likely (e.g., Stagflation bleeding into Carry Unwind — Brent spikes weaken INR, which accelerates carry trade exits, which feeds FII outflows, which tightens liquidity). Breadth captures systemic fragility that intensity alone misses.
- **Pillar Intensity (Weight 0.30):** Take the maximum pillar score from all 6 pillars. Measures the *severity* of the worst structural threat. A Stagflation reading of 85 demands attention even if it's the only active pillar.

**Arbiter Hook (thresholds):**
- Fragility > 65 → cap India regime at NEUTRAL. Cannot be BULLISH when structural threats are broad.
- Fragility > 85 → force DEFENSIVE. System dynamically protects itself when structural threats multiply, even if the raw Nifty price hasn't crashed yet.

**Module:** `src/fragility_index.py` (new). Single compute at 08:00 alongside `final_regime`. Writes to `market_state.fragility_score`.

### 4.2: Pillar Lifecycle Tracker
A pillar's meaning changes based on its age. This module tracks state transitions in a `pillar_lifecycle` Supabase table.

**Lifecycle States:**
- **EMERGING (Days 1-3, Score ≥ 40):** Spurious. Could be noise. Market often ignores Day 1 pillars entirely — they need time to prove persistence. During this window, no narrative changes are triggered.
- **ESCALATING (Day 3+, Score trending up over 3 consecutive days):** Dangerous. Momentum is building. Transmission mechanics are likely accelerating — the causal chains (e.g., RBI dilemma on rates, freight→CPI pass-through) are still being priced in, not yet fully discounted. This is the highest-risk window for sudden regime shifts.
- **SUSTAINED (Day 5+, Score stable near peak — within ±3 points for 3+ days):** Priced in. The market has accepted this as the baseline reality. Hedge setups are mature (vol sold, OTM puts unwound). New information is required to move the price further in this direction.
- **DE-ESCALATING (Score dropping from peak for 3+ consecutive days, Day 5+):** The primary threat is fading, but the after-effects linger (e.g., CAD widening from a sustained Brent spike persists for 6-12 months even after oil prices stabilize). Output notes these after-effects.

**Output change (before → after):**
```
Before: Stagflation — ELEVATED (63/100)
After:  Stagflation — ELEVATED (63/100) | ESCALATING (Day 4, Peak: 68)
```

This gives the reader temporal context — "this is still building, Day 4, hasn't peaked yet" — without predicting the future.

**Module:** `src/pillar_lifecycle.py` (new). Reads `pillar_metrics` history (365d retention), computes state transitions, writes lifecycle state to Supabase `pillar_lifecycle` table.

### 4.3: Regime Synthesis Arbiter Wiring
- Replace raw price-threshold overrides (e.g., `USDINR > 95`) in the Arbiter with the Fragility Index.
- **Layer 1b** (Global Arbiter — STAGFLATION/LIQUIDITY_DRAWDOWN) remains the ultimate "hard kill switch." If global regime is STAGFLATION, local Arbiter must obey.
- **Layer 2** (Fragility Index) becomes the mathematical bridge: Pillars → Fragility → Regime → Narrative. This creates a continuous chain: pillar scores feed into fragility, fragility caps/escalates the regime, regime dictates the narrative posture.

**Data flow:**
```
pillar_classifier.py → [pillar scores]
stress_index.py     → [base stress score]
                           ↓
                   fragility_index.py ← pillar_lifecycle.py
                           ↓
                   Fragility Score (0-100)
                           ↓
                   Regime Arbiter (caps/forces)
                           ↓
                   market_state.final_regime
```

---

## Phase 5: Institutional Microscopy

**Core Problem:** "FII sold ₹-3,792Cr" is an aggregate fact, but it is clinically useless for understanding survival mechanics. Is it one mega-fund rebalancing, or is it a broad-based exodus? Can DII absorb this for another week, or are they out of dry powder? Theoretical pillars (Phase 2/4) must be confirmed by actual capital flows. Without this layer, the system has macro theories with no cash-flow validation.

### 5.1: FII Decomposition
Break the aggregate FII number into structure and concentration to distinguish between a single fund derisking and a structural exodus.

**Computation:**
1. Query `fii_institution_tracker` for the last 7 days of trade data.
2. Identify the Top 5 FII entities ranked by net outflow (absolute value).
3. Compute **Concentration Metric**: `Sum(Top 5 Outflow) / Total FII Outflow`.

**Interpretation Rules:**
- **Concentration ≥ 60%:** *Concentrated exit*. A single sovereign wealth fund or large asset manager derisking. This pattern often reverses or stabilizes within 5-7 days once the rebalancing completes. Not structural.
- **Concentration < 30%:** *Broad-based exodus*. Hundreds of small funds hitting the exit simultaneously. This is structurally terrifying — it implies consensus panic, not a single trigger event. Rarely stops without major policy intervention (RBI rate cut, capital controls, or a dramatic valuation reset).

**Output:**
```
FII Decomposition: Broad-based exit (Top 5 = 32% of flows) | Top Entity: UBS (-₹820Cr)
```

**Module:** `src/fii_decomposition.py` (extends existing stub in `fii_decomposition.py`). No new Supabase table needed — reads existing `fii_institution_tracker`.

### 5.2: DII Capacity Gauge
DII absorption is not infinite. It relies on continuous mutual fund SIP inflows. This module predicts when the "DII Put" — the assumption that DII always buys the dip — will fail.

**Computation:**
1. **Deployment Ratio:** `DII Net Buy / (DII Net Buy + MF Net New Flows)` over a rolling 5-day window.
2. **DEPLOYMENT SATURATION:** If ratio > 85% for 5+ consecutive days → DII is eating into cash reserves, not deploying fresh inflows. They are selling existing holdings to fund new purchases — unsustainable.
3. **CUSHION ERODING:** Cross-check MF Net New Flows. If flows drop to near-zero (or negative) while FII selling persists → the cushion is gone. DII becomes a net seller within 2-3 sessions.

**Output:**
```
DII Capacity: 88% deployed (5D avg) | Status: SATURATED | MF Inflows: ₹+120Cr (insufficient)
```

This objectively predicts the exact moment the DII Put fails — no AI speculation, just sequential ratio tracking.

**Module:** `src/dii_capacity.py` (extends existing stub). Reads from `mf_watchlist` and historical DII flows. Writes status to `market_state` or dedicated `dii_capacity` table (7d retention).

### 5.3: Sector Flow Intelligence (Pillar-Flow Match)
Cross-reference the theoretical transmission chains of active pillars with actual FII sector flow data. This grounds macro theory in hard cash reality.

**Logic:**
1. If Stagflation is ACTIVE → transmission chain says OMC margins get squeezed (Brent↑ → under-recoveries widen), and IT gets a hedge (INR↓ → export competitiveness improves).
2. Query `fii_sector` data: Is FII actually selling Oil & Gas and buying IT?

**Classification:**
- **CONFIRMED:** Sector flows match transmission chain predictions → pillar is priced in by actual capital. The theory is validated by action.
- **UNCONFIRMED:** Sector flows diverge (e.g., Stagflation active but FII is buying O&G, not selling) → market has not priced the theoretical risk yet. The pillar represents a latent vulnerability, not an active one.

**Output:**
```
Pillar-Flow Match: Stagflation ACTIVE → FII selling O&G (-₹450Cr) ✅ Confirmed | FII buying IT (+₹320Cr) ✅ Hedged
```

**Module:** `src/sectoral_drag.py` (new). Reads `fii_sector` data + sector RS from `sector_rs`. Maps pillar names to expected sector exposures via a lookup table defined per pillar.

---

## Phase 6: Event Dynamics & Microstructure

**Core Problem:** The Risk Calendar currently outputs blind labels like "RBI MPC" with zero statistical context. The reader sees a warning but has no idea what typically happens. Markets are anchored to event cycles; volatility clusters around them in statistically predictable patterns. Without this data, the calendar is just noise.

### 6.1: Event Volatility Profiler
Map historical market behavior to upcoming calendar events. Transforms a warning into a statistical fact.

**Computation:**
1. When an event is within 7 days, look up its label in `economic_calendar` CSV (144 events, 12-month lookahead).
2. Find all past occurrences of this event label in the last 5 years of `anchor_history.csv` (1,304+ rows).
3. Compute:
   - Nifty absolute return on event day (T+0), T+1, T+2.
   - VIX percentage change from T-2 to T+2 (pre-event volatility expansion → post-event decay).
4. Minimum sample size: 3 occurrences. If fewer, suppress (insufficient data).

**Output:**
```
RBI MPC (Jun 4): Avg Nifty move ±0.9% (n=8) | VIX typically falls 1.2pts post-decision
```

**Module:** `src/event_volatility.py` (new). Reads `economic_calendar` CSV + `anchor_history.csv` + current `market_state`. Writes volatility profile to a new `event_volatility_profiles` Supabase table (365d retention).

### 6.2: Pre-Event Positioning Detector
Options markets price in event risk *before* the event happens. Detect aggressive hedging by comparing current options readings to their recent baseline.

**Computation:**
1. Within 2 days of a high-impact event (label identified by `event_volatility_profiles`), fetch current `options_snapshots` (PCR, Skew, implied volatility term structure).
2. Compare each metric to its 5-day rolling average.
3. **Put/Call Ratio (PCR):** If PCR drops > 0.15 in 3 days → Aggressive Put Hedging. Institutions are buying downside protection, not (as commonly misinterpreted) bullish call buying.
4. **Skew (difference between OTM put IV and ATM IV):** If skew spikes > +15 points from 5D average → Tail Risk Pricing. Demand for deep OTM puts far exceeds calls. Market is pricing tail events.

**Output:**
```
Pre-MPC Positioning: Aggressive put hedging (PCR 0.85 → 0.70 in 3d) | Skew elevated (+8 → +22)
```

This tells the reader that smart money is bracing for impact, derived entirely from computed math — zero speculation.

**Module:** Wired into `src/options_engine.py`. New method `detect_pre_event_positioning(event_label, lookback_days=5)`. No new table needed.

### 6.3: Intraday Pillar Confirmation
Phase 3 introduced the 30-min Intraday Pulse. Now use it to validate daily pillars in real-time during the Midday Scan.

**Computation:**
1. During Midday Scan (12:30 PM), access the intraday pulse data for the current session (30-min snapshots of Nifty and VIX).
2. For each active pillar, check the correlation of 30-min Nifty moves against 30-min moves of the pillar's primary price driver:
   - Stagflation → Brent crude (30-min ticks)
   - Carry Unwind → USDINR (30-min ticks)
   - West Asia → CBOE_VIX (30-min ticks)
3. **If Nifty drops specifically when Brent ticks up** (negative correlation in consecutive 30-min windows) → Intraday confirms Stagflation transmission is firing. The macro chain is validated in real-time.
4. **If Brent ticks up but Nifty holds flat** → Intraday divergence detected. DII ring-fencing or sector rotation is successfully absorbing the shock. The pillar exists in theory but is blocked at the microstructure level.

**Output:**
```
Intraday Pillar Check: Stagflation — Nifty reacting to Brent (confirmed) | DIVERGENCE on Carry (Nifty resilient to USDINR tick)
```

This closes the loop between macro theory and micro price action without waiting for EOD data.

**Module:** Wired into `src/midday_scan.py` + `src/intraday_pulse.py`. New function `check_intraday_pillar_confirmation(pulse_data, current_pillars)`.

---

## Phase 7: Adaptive Calibration & Regime Rotation ✅ Locked

**Concept:** The system uses static equal-weight logic for pillars. Empirical hit rates vary: EM Contagion might be a weak predictor (20%), Stagflation a strong one (80%). Phase 7 makes the system learn its own accuracy and maps historical sector behavior to pillar configurations.

### 7.1: Dynamic Pillar Weights
**Logic:** Sunday calibration walk-forward backtest measures each pillar's hit rate for predicting Nifty 5D drawdowns > 1%.

**Math:**
1. Query `signal_accuracy_log` (365d) + `pillar_metrics` history.
2. For each pillar, compute `hit_rate` (% of time pillar ≥ 40 preceded a Nifty 5D drop > 1%).
3. Compute `weight_multiplier = 1.0 + (hit_rate - 0.50)`.
4. **Clamp to [0.70, 1.30]** — prevents dominance or zeroing out.
5. Save to `market_state.dynamic_weights` JSONB.

**Fragility Index hook (P4 update):**
- *Before:* `max(pillar_scores × lifecycle_multiplier)`
- *After:* `max(pillar_scores × lifecycle_multiplier × dynamic_weight_multiplier)`

**Module:** `src/adaptive_weights.py` — `compute_pillar_weights()` reads `signal_accuracy_log`, writes `dynamic_weights` JSONB. `get_dynamic_weights()` weekday reader, defaults to 1.0.

### 7.2: Regime Rotation Map
**Logic:** Maps current active pillar configuration to historical `sector_rs` data. Pure statistical output, no trading advice.

**Algorithm:**
1. Query 5Y `pillar_metrics` + `sector_rs` from Supabase/CSV.
2. Find historical windows where current pillar mix was active at ±10 points.
3. Calculate median sector RS during those windows.
4. Output top 2 outperformers + bottom 2 underperformers.

**Scrubber rule:**
- *Allowed:* `Historical Tilt: IT (+0.4σ), Pharma (+0.2σ) | Lagged: O&G (-0.6σ), PSU Banks (-0.5σ)`
- *Blocked:* `Buy IT, Sell O&G` / `Overweight Pharma`

**Output placement:** Below `Pillar-Flow Match` block in 15:30 EOD, only when Fragility > 50. Gated in `reorder_market_blocks()` — NEUTRAL regime now includes `rotation_block`.

**Module:** `src/sector_rotation_map.py` — `compute_sector_tilt_map()` Sunday pre-compute, `format_rotation_map()` weekday reader.

---

## Phase 8: Relative Value & Cross-Border Arbitrage ✅ Locked

**Concept:** The bot currently treats India in glorious isolation, with global data only serving as "triggers" for the local framework. But capital flows are a zero-sum game between geographies. When a global fund decides to reduce EM exposure, it doesn't just sell India — it reallocates to DM bonds, US tech, or Japan value. India's underperformance relative to its EM peers is a signal in itself.

### 8.1: India vs EM Basket
- Track Nifty's relative strength against MSCI Emerging Markets ETF (EEM) over a rolling 30-day window.
- If India underperforms EEM by > 5% during this window, AND the EM Contagion pillar is concurrently ACTIVE → this signals a structural reallocation *out of India specifically*, not just a general EM exit.
- Implication: Nifty is losing its premium status within EM. The "India decoupling" narrative is failing in real-time.

**Module:** `src/value_metrics.py` — `compute_india_vs_em_rs()` computes 30D rolling RS from yfinance. `EEM` added to MACRO_ANCHORS in `data_fetcher.py`.

### 8.2: Bond/Equity Switch (ERP)
- Track the Equity Risk Premium (ERP): `(1 / Nifty PE) - India 10Y Yield`.
- Sunday pre-compute: bin 5Y CSV into 10 decile boundaries. Store as JSONB.
- Weekday: instant lookup against stored deciles.
- **Output:** `ERP: -2.12% (bottom decile) | Historical prob of positive Nifty 30D: 22% (18/82 occurrences)`.

**Module:** `src/value_metrics.py` — `compute_erp()`, `compute_erp_deciles()` Sunday pre-compute, `get_current_erp_decile()` weekday lookup, `format_erp_decile()` display. `format_erp_decile` wired into EOD supplementary block.

---

## Phase 9: Autonomous Agent Interactivity ✅ Locked

**Concept:** Phase A3 gave us basic Telegram commands (`/stress`, `/flows`, `/gex`, `/sectors`, `/whatif`, `/clone`). Phase 9 expands this into a full conversational query layer where the bot acts as an autonomous agent against its own deterministic data store. The critical constraint: zero AI number generation. AI is used only for natural language-to-SQL translation and result summarization. All numbers come from deterministic engines.

### 9.1: Scenario Simulator
- `/simulate brent 120`: Runs the Consequence Engine + Pillar Classifier + Fragility Index with `Brent` hardcoded to 120 for the current session.
- Returns: Theoretical regime shift ("Stagflation → 78/100 ELEVATED, Fragility → 81, Regime → force DEFENSIVE"), impact multipliers (import bill increase ₹X Cr), and transmission chain output.
- No AI involved — purely deterministic with one parameter overridden.

**Module:** `src/scenario_simulator.py` — override macro var → consequence → pillar → fragility → regime. Wired into `bot_handler.py` dispatch table.

### 9.2: Historical Comparator
- `/compare 2013-08-15`: Pulls the exact 12D macro vector (all 24 columns) from `anchor_history.csv` for that date.
- Side-by-side comparison with today's vector: same metrics, color-coded differences.

**Module:** `src/historical_comparator.py` — load CSV row, compare columns to current `market_state`.

### 9.3: Natural Language Query Layer
- Uses **Intent Catalog** (13 intents). User types "Why is FII selling?" → LLM classifies as `Intent: GET_FII_DECOMPOSITION` → hardcoded Supabase query → formatted reply.
- If LLM cannot map to intent with >90% confidence: "Query outside deterministic scope."

**Module:** `src/agent_query.py` — Intent Catalog, keyword + LLM classification, deterministic Supabase resolvers. Wired into `bot_handler.py`.

---

## Phase Priority & Sequencing

| Phase | Effort | Risk | Value | Depends On | Start |
|-------|--------|------|-------|------------|-------|
| P4 (Fragility+Lifecycle) | 4 hr | Low | High — closes pillar-arbiter gap | P2 (Pillars), P3 (Stress Index) | **✅ Locked** |
| P5 (Institutional Micro) | 5 hr | Medium | High — grounds pillars in cash flows | P4 (Fragility provides the regime context) | **✅ Locked** |
| P6 (Event Dynamics) | 3 hr | Low | Medium — transforms calendar into stats | P0 (Economic Calendar), Anchor History CSV | **✅ Locked** |
| P7 (Adaptive Weights) | 3 hr | Medium | Medium — system learns its own accuracy | P4 (needs Fragility Index as target), Signal Accuracy Log | **✅ Locked** |
| P8 (Relative Value) | 4 hr | High | Medium — cross-border context | P4 (needs regime context to interpret RS divergence) | **✅ Locked** |
| P9 (Agent Interactivity) | 5 hr | High | High — conversational deterministic query | All prior phases (max data surface for queries) | **✅ Locked** |
| P10 (Meta-Cognitive Sentinel) | 1 hr | Low | High — null/variance halt + regime jump cap | P4 (Fragility needed for jump validation) | **✅ Locked** |
| P11 (Institutional Armature) | 4 hr | Medium | High — liquidity freeze, debt stress, archetype collisions | P10 (pipeline hardening first) | **✅ Locked** |
| P12 (AI & Climate) | 2 hr | Low | Medium — SMH/COPX tickers, transmission upgrades | P11 (archetype matrix needed for collision entries) | **✅ Locked** |

**Summary rationale (completed):** P4 closed the pillar-arbiter gap with a continuous Fragility Index (no hard-coded thresholds). P5 grounded theoretical pillars in actual FII/DII cash flows. P6 transformed the risk calendar into statistical facts and validated pillars in real-time via intraday ticks. P7 added dynamic weights and sector rotation maps. P8 added India vs EM RS and ERP decile display. P9 added 3 agent commands (/simulate, /compare, intent-powered NL query). P10 added preflight sentinel + regime membrane (wired in both market_intel.py and market_close.py). P11 added external debt stress multiplier, liquidity freeze Welford detection, 6 archetype collision bitmasks. P12 added SMH/COPX macro anchors, AI/Climate transmission narratives, 2 new archetype matrix entries.

**All 14 cron jobs, 20 workflow files, 58+ modules, 6 Telegram commands, 3 agent commands — fully wired and tested.**

---

## ☁️ GHA/Supabase-Constrained Enhancement Spec (P7–P10)

**Current Bot (P0–P6): 9.5 / 10**
Structurally robust, deterministic market intel architecture. Mathematical loop is closed: Macro Theory (Pillars) → Temporal Momentum (Lifecycle) → Systemic Bridge (Fragility) → Cash Validation (Microscopy) → Microstructure Confirmation (Intraday/Events). "Python computes, AI narrates" religiously enforced; scrubber acts as perfect firewall.

**Constraint Audit — Original P7–P10 Logic Fails On:**
1. **GHA 10-min timeout:** 5-year walk-forward backtest across 6 pillars + 15 sectors on a GHA runner will TLE every Sunday.
2. **Supabase 2GB limit:** Strict 7d purges on high-volume tables. Storing 5Y of sector RS + pillar metric + ERP decile matrices blows the budget in 6 months.
3. **GHA stateless webhooks:** No persistent listener. GHA workflows spin up on `workflow_dispatch` and must exit within 10 min.

**Core Paradigm Shift:** Compute belongs to CSVs/Pandas (GHA runner local). State belongs to Supabase. Pre-compute mappings on Sundays, store as tiny JSONB configs, read deterministically during week.

### P7: Adaptive Calibration (GHA Edition)

**7.1 Dynamic Pillar Weights**
- **Sunday (`sunday_calibration`):** Load `anchor_history.csv`. Vectorized Pandas rolling correlation: "When Pillar X > 40, what was Nifty 5D forward return?"
- **Compute:** `weight_multiplier = 1.0 + (hit_rate - 0.50)`, clamped [0.70, 1.30].
- **Storage:** Upsert single row into `market_state`/`bot_state`: `{"dynamic_weights": {"Stagflation": 1.3, "EM_Contagion": 0.7, ...}}` (<1KB).
- **Weekday:** `fragility_index.py` reads JSONB on compute. Zero historical DB queries.

**7.2 Regime Rotation Map**
- **Original flaw:** Querying 5Y historical `sector_rs` per pillar active pulls thousands of rows.
- **GHA fix:** Sunday pre-compute expected sector tilts per pillar. Store as lookup JSONB: `{"Stagflation": {"bullish": ["IT", "Pharma"], "bearish": ["O&G", "PSU"]}}`.
- **Weekday:** At 15:30, if Stagflation active, read JSONB. Output `Historical Tilt: IT, Pharma | Lagged: O&G, PSU`. One read, <1ms.

### P8: Relative Value (GHA Edition)

**8.1 India vs EM Basket**
- Add `EEM` to the 19 macro anchors in yfinance batcher.
- Compute 30D rolling RS as Pandas columns.
- Save *current* spread to `market_state.india_vs_em`. Do not save historical series to Supabase (CSV handles history).

**8.2 Bond/Equity Switch (ERP)**
- **Original flaw:** Binning 5Y CSV into deciles dynamically on weekday takes too much CPU.
- **GHA fix:** Compute ERP decile boundaries on Sunday. Store as JSONB: `{"erp_deciles": [-2.5, -2.1, -1.8, ...]}`.
- **Weekday:** Run current day's ERP against stored boundaries. Instant lookup. Zero Pandas compute on weekdays.

### P9: Autonomous Agent (GHA Stateless Edition)

**9.1 Scenario Simulator (`/simulate brent 120`)**
- Telegram webhook triggers GHA workflow with `{"command": "simulate", "variable": "brent", "value": 120}`.
- Python fetches current day's `market_state`, overrides `macro_attrs['Brent'] = 120`, runs lightweight algebra: `consequence_engine → pillar_classifier → fragility_index → arbiter`.
- Compute time: <2s. No live API calls. Sends result, exits 0.

**9.2 Historical Comparator (`/compare 2013-08`)**
- Load `anchor_history.csv` from GHA cache. Filter to date. Compare columns to current `market_state`. Format side-by-side.

**9.3 NL Query Layer — Kill SQLGen.**
- Use **Intent Catalog**. User types "Why is FII selling?" → LLM classifies as `Intent: GET_FII_DECOMPOSITION` → hardcoded Supabase query → formatted reply.
- If LLM cannot map to intent with >90% confidence: "Query outside deterministic scope."

### P10: Meta-Cognitive Sentinel (Edge Case Armor)

Zero extra compute/storage. Defensive logic embedded at top of every job runner.

**10.1 Schema & Sanity Sentinel**
- Runs before pipeline in `market_intel.py` and `market_close.py`.
- Checks: >30% macro anchors null/0.0 → HALT. Brent daily change >30% (API glitch) → HALT.
- Action: `sys.exit(1)` with Telegram `🚨 DATA INTEGRITY FAILURE: Macro fetch >30% null. Pipeline halted. Regime locked to previous state.`

**10.2 Circuit Breaker Membrane**
- At 08:00, fetch yesterday's final regime. If today's jump is 2 steps (e.g., DEFENSIVE → BULLISH) and Fragility hasn't dropped ≥20 pts → **Block jump. Cap at NEUTRAL.**
- Rationale: Regimes don't leap 2 steps overnight without structural shift — 99% data anomaly.

### Execution Roadmap

1. **P10 (Sentinel)** — null/variance checks + regime jump-capping first. Protects pipeline from garbage data as complex features are added.
2. **P7 (Adaptive)** — Sunday backtest engine using `anchor_history.csv`, outputting only `dynamic_weights` + `sector_tilt_map` JSONBs.
3. **P8 (Relative Value)** — Add `EEM` to yfinance batcher. Compute ERP decile boundaries Sunday, store as JSONB.
4. **P9 (Agent)** — Wire 6 Telegram commands to `workflow_dispatch`, using in-memory snapshots for `/simulate`. Intent Catalog instead of SQLGen.
5. **P10b (P11 — Institutional Armature)** — HYG/LQD Welford, archetype collisions, hard-threshold debt stress flag.
6. **P11 (P12 — AI & Climate)** — `SMH`/`COPX` tickers, transmission chain upgrades, new archetype entries.

---

### P11: Sovereign & Liquidity Armature (Institutional)

Reconciled from analyst review. Zero new Supabase tables, <10s GHA runtime added.

**11.1 External Debt Stress (Hard Threshold, No Z-score)**
- Replaces synthetic "Fiscal Trap Z-Score" with boolean trigger.
- Logic: `IF US10Y > 4.5% AND USDINR > 84.0 AND FII_5D_Net < -10000 Cr` → `external_debt_stress = True`.
- Integration: Not a new arbiter layer. Multiplies `Carry Unwind` pillar's Fragility contribution by 1.5×, pushing the regime toward DEFENSIVE naturally through the existing Hierarchy.

**11.2 Liquidity Freeze (Welford HYG/LQD → Sentinel Flag)**
- Compute HYG/LQD ratio spread velocity via Welford streaming Z-score (in-memory, no DB).
- If Z-score > 3.0 in 5 days → `market_state.liquidity_freeze_active = True`.
- Decoupled from P5.2 (DII Capacity remains computationally untouched).
- Formatter reads the flag: appends `⚠️ Override: Global liquidity freeze active; domestic absorption may be overridden by dollar repatriation.` to the DII line, does not replace it.

**11.3 Forex Reserves (Manual Override, Deferred)**
- No automated ingestion (no reliable RBI API; scraping too fragile).
- `bot_state.forex_reserves_safety` JSONB boolean. Set manually during Sunday maintenance if `import_cover_months < 8`.
- If True → `EM Contagion` pillar gets 1.5× Fragility multiplier.

**11.4 Archetype Collision Matrix (Append, Not Suppress)**
- Bitmask check runs at 15:30 after all pillars computed.
- Prepends banner *above* pillar breakdown; pillar z-scores/transmission chains remain visible below.

| Active Pillar Combination | Archetype | Banner |
|:---|:---|:---|
| Carry Unwind + EM Contagion + DXY Spike | 1997 Asian Contagion | `⚠️ ARCHETYPE: Asian Crisis 1997 (Reserve depletion + EM exit + Strong Dollar)` |
| Stagflation + Liquidity Freeze | Stagflationary Freeze | `⚠️ ARCHETYPE: Stagflationary Freeze (Supply shock + Credit seized)` |
| De-dollarization + Gold Spike + CNY Strength | Multipolar Shift | `⚠️ ARCHETYPE: Bretton Woods Unraveling (Dedollarization + Hard Asset anchor)` |
| Fiscal Hard Threshold + VIX Spike + Yield Inversion | Sovereign Debt Trap | `⚠️ ARCHETYPE: Sovereign Debt Trap (Unserviceable debt + monetary tightening)` |

**Module:** `src/scenario_collision.py` (new). Reads active pillars from pillar_classifier, matches bitmask, writes `market_state.active_archetype`.

---

### P12: AI & Climate Integration (Catalyst Layer)

AI and Climate are existential macro forces, but their Indian market impact is 100% mediated through the existing 6 pillars. They are catalysts, not pillars. This phase upgrades transmission narratives and data inputs without adding architectural complexity.

**12.1 New Macro Anchors (2 tickers)**
- Add `SMH` (VanEck Semiconductor ETF) to yfinance batcher — defines AI compute cycle. SMH crash triggers `Tech Cycle` pillar faster than Nifty IT.
- Add `COPX` (Global Copper Miners ETF) — hinge between AI data centers and green grid infrastructure. COPX spike alongside Brent confirms structural inflation shift.
- We already track `HG=F` (copper futures) and `CU_AU_Ratio` in Stagflation pillar. COPX gives equity-market forward expectation of copper demand.

**12.2 Transmission Chain Narrative Upgrades**
In `transmission_mechanics.py`, existing 6 chains get updated narrative strings:
- **Stagflation chain:** Add "Heatflation" — `Brent↑ / Monsoon Failure → Food Inflation → RBI Hawkish → Rate Sensitives Drag`. Math (Brent + USDINR) already catches this; narrative now names the climate vector.
- **Tech Cycle chain:** Add "AI Displacement" — `SMH↓ / US10Y↑ → IT Offshoring Pricing Pressure → USD Inflow Risk → Rupee Vulnerability`.

**12.3 Archetype Matrix Additions (P11.4 extension)**

| Active Pillar Combination | Archetype | Banner |
|:---|:---|:---|
| Tech Cycle + Carry Unwind + DXY Spike | AI Displacement Exit | `⚠️ ARCHETYPE: AI Displacement Exit (Compute capex down + IT USD inflows at risk + Strong Dollar)` |
| Stagflation + EM Contagion + USDINR Spike | Climate/Heatflation Trap | `⚠️ ARCHETYPE: Climate/Heatflation Trap (Agri supply shock + EM debt strain + Import bill crisis)` |

---

## 🔴 Design Phase Closure: Hard Data Boundary

**What we cannot build (no free/reliable API exists):**
- SRF Utilization / G-SIB LCR — multi-day lag, no real-time free API
- TRS Leverage / Rehypothecation Velocity — most confidential data on Wall Street
- RBI FX Forward Book — structural lag in monthly bulletins
- COT Net-Short Positioning — computationally prohibitive for 10-min GHA window

**What we extracted (one viable math signal, free with existing data):**

**Bond/Equity Vol Divergence** — When yield volatility spikes while equity VIX stays flat, credit markets are panicking ahead of equities. Compute: 5D rolling std of `^TNX` changes vs 5D rolling VIX. Integration: If US10Y vol > 2σ above Welford baseline while VIX is flat → append `⚠️ BOND/EQUITY VOL DIVERGENCE: Credit market panicking ahead of equities.` to Stagflation/Carry Unwind transmission chains.

**Triangulation Rule** — Already our architecture:
1. Derivatives Layer (Price Skew): `options_engine.py` (PCR, Skew, GEX)
2. Physical Layer (Flow): `fii_dii_flows`, `fii_decomposition`, `dii_capacity`
3. Cash/Balance Layer: Macro Anchors + Consequence Engine

A pillar is `CONFIRMED` (P6.3) only when all three fire. If only one layer fires, Lifecycle keeps it `EMERGING` (×0.6).

**Final verdict:** P0–P12 architecture maps systemic risks of last 50 years using only verifiable data (price, volatility, public exchange flows). No further theoretical expansion. Design phase closed.

---

## 📦 Reference: `src/sentinel.py` (P10 Implementation)

Reference file created at `src/sentinel.py`. Two functions:

**`preflight_check(current_anchors, prev_anchors) → (is_safe, reason)`**
- Rejects if >30% of macro anchors are None/0.0
- Rejects if Brent/USDINR/DXY moved >30% daily (API glitch)

**`regime_membrane(current_regime, prev_regime, current_fragility, prev_fragility) → str`**
- If 2-step regime leap (e.g., DEFENSIVE→BULLISH) and Fragility hasn't dropped ≥20 pts → caps at NEUTRAL
- If 2-step leap toward DEFENSIVE and Fragility hasn't surged ≥20 pts → caps at NEUTRAL

### Wiring (integrated — all call sites active)

**`jobs/market_intel.py` (top of run()):** Preflight checks macro sanity before any compute. HALT on >30% null or Brent/USDINR/DXY >30% daily change.

**`src/regime_arbiter.py` (after final_regime computed):** `regime_membrane()` caps 2-step regime leaps (e.g., DEFENSIVE→BULLISH) unless Fragility moved ≥20 pts in the supporting direction.

**`jobs/market_close.py`:** Preflight at top of `main()`.

---

## P14: Fingerprint Skip Gate

**Core Problem:** 14 cron jobs run daily even when nothing changes. Regime, pillars, and macro anchors are identical to the last run. The bot still burns CPU, AI tokens, and network time recomputing what it already knows.

**The Fatal Trap:** You cannot hash the regime to skip computing the regime. Computing `pillar_mask` requires running `pillar_classifier.py`. Computing `regime` requires running `fragility_index.py` and `regime_arbiter.py`. If you compute them to check the hash, you've already paid the cost.

**Solution:** Hash **raw anchors only** — bucketed values of Nifty, VIX, USDINR, Brent, DXY, and FII flow bucket — plus manifest version. The skip gate runs in < 100ms before any heavy module loads.

```python
# Raw anchor fingerprint (NOT computed state)
canon = (
    f"N:{round(NIFTY / bucket_nifty)}|"
    f"V:{round(VIX / bucket_vix)}|"
    f"U:{round(USDINR / bucket_usdinr)}|"
    f"B:{round(BRENT / bucket_brent)}|"
    f"D:{round(DXY / bucket_dxy)}|"
    f"F:{fii_bucket}|"
    f"M:{manifest_version}"
)
fp = blake2b(canon).hexdigest()[:16]
```

**Skip gate flow in every job runner:**
1. Fetch anchors (parallel, <10s)
2. Compute raw fingerprint
3. If fingerprint == `bot_state.last_fingerprint` → skip full compute
4. **Heartbeat:** If >4h since last send, emit templated one-liner (no AI) — prevents radio silence
5. On fingerprint change: run full pipeline

**GHA state persistence:** `bot_state` table in Supabase stores `last_fingerprint` and `last_sent_at`. One tiny row, one DB write on skipped runs.

**Module:** `src/fingerprint.py` — `compute_raw_fingerprint(anchors, manifest)` and `should_skip(current_fp, last_fp, last_sent_at, heartbeat_min=240)`.

---

## P16: Lightweight Manifest (P14 Enabler)

**Core Problem:** `fingerprint_buckets` must live somewhere that Sunday calibration can tune. Hard-coding them defeats the point. Pre-computed values (ERP deciles, adaptive weights, sector tilt maps) are currently scattered across variables in `adaptive_weights.py`, `value_metrics.py`, etc. Consolidating into a single JSON enables the skip gate and makes weekday reads O(1).

**Solution:** A single `data/manifest.json` written by `sunday_calibration.py`, read by every weekday job. < 1KB, loaded in < 1ms.

**Schema:**
```json
{
  "version": "a1b2c3d",
  "generated_at": "2026-06-02T02:30:00Z",
  "fingerprint_buckets": {
    "nifty": 100, "vix": 1, "brent": 1.0, "usdinr": 0.1, "dxy": 0.5
  },
  "fragility": { "cap_neutral": 65, "force_defensive": 85 },
  "adaptive_weights": { "Stagflation": 1.3, "EM_Contagion": 0.7 },
  "sector_tilt_map": {
    "Stagflation": {"bullish": ["IT", "Pharma"], "bearish": ["O&G", "PSU Banks"]}
  },
  "erp_deciles": [-2.5, -2.1, -1.8, -1.5, -1.2, -0.9, -0.6, -0.3, 0.0, 0.4],
  "steady_state_template": "🟢 Steady state since {last_regime_time}. Regime: {regime} | Nifty: {nifty} | VIX: {vix}. No material change."
}
```

**Build rule:** `jobs/sunday_calibration.py` appends all pre-computed variables into this JSON at end of run.

**Module:** `src/manifest.py` — `load() -> dict`. Validates schema. Aborts if missing keys.

---

## P18: Guardian 2.0 (Triage System)

**Core Problem:** Current P10 sentinel is binary halt-or-go (>30% nulls → HALT, else proceed). NSE v3 falls over frequently — binary halt means the bot goes silent on minor data degradation.

**Solution:** 3-tier triage that every fetcher reports into, evaluated after all fetches complete but before compute.

| Triage | Condition | Behavior |
|--------|-----------|----------|
| **GREEN** | All live data nominal | Full pipeline |
| **YELLOW** | ≥2 delayed/timeout fetches OR >20% nulls | Suppress options/GEX blocks; append `⚠️ Delayed/Partial` to regime line; AI bypassed with deterministic stub |
| **RED** | >30% nulls or critical glitch (Brent/USDINR/DXY >30% daily) | HALT. `sys.exit(1)`. Telegram: data integrity failure. |

**Propagation:**
- If YELLOW: `context.triage = "YELLOW"` → `formatters.py` appends badge → `options_engine` skipped entirely (saves 15-30s) → AI replaced with deterministic stub
- If RED: no compute, pre-canned alert sent

**Module:** `src/guardian.py` — `Guardian` class with `check_source()`, `finalize(anchors) -> TriageLevel`. Replaces `sentinel.py` conceptually.

---

## Audit Scorecard (P0–P18)

Cold, technical audit against the codebase as documented:

| Dimension | Current | After P14+P16+P18 | Rationale |
|-----------|---------|-------------------|-----------|
| **Deterministic Architecture** | 9 / 10 | 9 / 10 | "Python computes, AI narrates" is structurally sound. Separation of concerns, scrubber, block validators, no SQL-gen. Unchanged by build phases. |
| **Signal Validity** | 6 / 10 | 8 / 10 | Pillars + Fragility are logical but thresholds (65/85) are unvalidated hypotheses. Living Thresholds via grid search (with OOS holdout) replace guesswork with evidence. Entropy check and divergence engine add conviction grading. |
| **Operational Efficiency** | 5 / 10 | 9 / 10 | Currently every job recomputes everything — ~40% waste. Fingerprint skip gate is transformative for free-tier GHA. Manifest collapses DB pressure to O(1). |
| **Data Resilience** | 5 / 10 | 8 / 10 | P10 is binary halt-or-go. NSE v3 timeout = total silence. Guardian YELLOW tier allows graceful degradation with partial data. Still vulnerable to simultaneous AI-provider outages. |
| **User Utility** | 6 / 10 | 8 / 10 | Excellent at describing smoke. Poor at saying when smoke is benign — structurally bearish. Divergence block adds "so what" on ambiguous days. No formal constructive-escalation path remains. |
| **Storage/Economics** | 7 / 10 | 9 / 10 | 400 MB of 2 GB is safe. Moving time-series lookups to manifest JSONB eliminates unnecessary DB queries. Correct free-tier pattern. |
| **Overall** | **6.2 / 10** | **8.4 / 10** | Moves from "smart risk monitor" to "tactical command center." The skip gate alone pays for the refactor in compute savings. |

---

## Forward Roadmap: v0.5-beta → v1.0

**Current state:** All Phases A–C complete. The bot went from an expensive macro newspaper to a cheap, self-regulating membrane.

### Option A: The Monk (Recommended)

Do not add features for **14 days**. Run the bot silently and collect:

| Week | What to Watch | Decision Trigger |
|------|---------------|-----------------|
| **Week 1** | First `Paper Track (YTD)` line in Sunday digest | If `Net` positive vs Buy-Hold, signal has edge |
| **Week 2** | Check adaptive weights in manifest | If weights drift further from 1.0, system is learning |
| **Week 3** | Regime accuracy vs Nifty direction | If regime calls <55% directional, Fragility is decorative |

**If P30 fails (Net alpha negative after 30 days):**
- Raise `Base Fragility` weight from 40% → 60% in `manifest.json`
- Accept the bot as a brilliant macro monitor, not a decision-support system

### Option B: The Surgeon (If you must code)

Three high-utility, low-risk additions:

#### 1. P15 Divergence Block (<100ms, zero new data calls)
Three cheap sensors inside `should_skip()` — if any fire, force full compute:
- **Cross-asset divergence:** Nifty unchanged but VIX changed >10% from last fingerprint
- **Sector divergence:** >2 sectors moving >1% opposite to Nifty
- **Macro-implied vs actual:** `|implied - actual| > 0.8%`

#### 2. Smart Market Close (middle tier, zero AI cost)
When fingerprint matches but it's the Close job, emit minimal deterministic block:
```
📌 *MARKET CLOSE*
🟡 Steady State: NEUTRAL | Nifty 23,367 (+0.1%)
📌 Flows: FII ₹-1,203Cr | DII ₹+980Cr
💤 No regime shift.
```

#### 3. "Screaming Anchor" Bypass (20 lines in `should_skip()`)
Bypass skip gate when: FII 5D crosses ±₹10,000 Cr, VIX spikes >20%, or FinBERT >0.8 on war/RBI/SEBI headline.

### Keep on the Shelf (Crisis-Only, Do Not Build Now)
- **P31 Hollow Liquidity / P32 Containment:** Designed but not built. Test when crisis happens.
- **P9+ Telegram commands:** `/lastchange`, `/regime`, `/alertme` — useful but distracting.
- **Macro Anchor Speedometer:** Delta badges on 11-block intel.

### Budget

| Addition | GHA Time | DB Storage | Writes/Run | Status |
|----------|----------|------------|------------|--------|
| P14/P16/P18 Skip Gate | -2 min saved | 0 (local file) | 1 write | ✅ Done |
| P27–P30 | <5 ms each | Minimal | 1 INSERT/wk | ✅ Done |
| P15 Divergence | +100 ms | 0 | 0 | ⏳ Backlog |
| Smart Close | 0 | 0 | 0 | ⏳ Backlog |
| Screaming Anchor | 0 | 0 | 0 | ⏳ Backlog |
| P31/P32 | +3 ms | 0 | 0 | 📋 Shelf |

---

### Forbidden Items (Deferred Out of Scope)

| Item | Why Blocked |
|------|-------------|
| Real-time entity-level FII data | No public API. SEBI bulk deals cover <20%. |
| SRF Utilization / G-SIB LCR | Confidential / lagged (RBI monthly). |
| COT Net-Short Positioning | Too large for 10-min GHA timeout. |
| New macro pillars | Architecture closed. No P13. |

### Success Criteria

| Milestone | Deliverable | Exit Criteria |
|-----------|-------------|---------------|
| **v0.5-beta** | GitHub push | 7-message dry-run passes; no `TODO` in working code |
| **v0.6** | P14+P18 wired | Flat-day messages ≤ 2; Guardian YELLOW handles NSE timeout |
| **v0.7** | P17 holdout + P30 live | 12-week rolling paper P&L positive net of friction; adaptive weights ≠ 1.0 |
| **v0.8** | P27+P28+P29 | State journal append-only; Promise Engine flags stale lifecycles; pillar decay active |
| **v0.9** | P15 divergence + P31/P32 | Hollow liquidity fires; AI tokens cut 60% via manifest stubs |
| **v1.0** | Stable 90-day run | Zero silent failures; scorecard calibration (n>30); regime accuracy published |

---

## File Manifest: P14 + P16 + P18

| File | Action | Purpose |
|------|--------|---------|
| `data/manifest.json` | Create | Source of truth for thresholds, buckets, templates |
| `src/manifest.py` | Create | `load() -> dict` with schema validation |
| `src/fingerprint.py` | Create | `compute_raw_fingerprint()`, `should_skip()` |
| `src/guardian.py` | Create | 3-tier triage, replaces `sentinel.py` |
| `src/bot_state.py` | Create | Helpers for `last_fp`, `last_sent_at` read/write |
| `src/telegram_sender.py` | Modify | Append `triage_badge` to regime line |
| `src/formatters.py` | Modify | Suppress options/gex blocks on YELLOW |
| `jobs/market_intel.py` | Modify | Fingerprint gate + guardian check at top |
| `jobs/midday_scan.py` | Modify | Fingerprint gate + guardian check at top |
| `jobs/market_close.py` | Modify | Fingerprint gate + guardian check at top |
| `jobs/sunday_calibration.py` | Modify | Write manifest.json at end of run |

---

## Build Order: P14 + P16-light + P18 (2-3 Days)

**Day 1: Foundation**
1. Create `data/manifest.json` schema with defaults. Modify `sunday_calibration.py` to write it.
2. Create `src/manifest.py` loader. Verify <1ms load.
3. Create `src/bot_state.py` helpers for Supabase `last_fp` / `last_sent_at`.

**Day 2: Guardian + Fingerprint**
1. Implement `src/guardian.py`. Wire into `market_intel.py` and `market_close.py` first.
2. Implement `src/fingerprint.py` with raw-anchor hashing + heartbeat logic.
3. Add skip gate to 3 main jobs (morning, midday, close).
4. Add `triage_badge` append to `telegram_sender.py` and suppression logic to `formatters.py`.

**Day 3: Validation**
1. `DRY_RUN=1` on all 3 jobs twice — second run must skip (or heartbeat if >4h).
2. Verify `bot_state` updated correctly.
3. Simulate YELLOW (mock NSE timeout) — verify options suppressed, AI bypassed, badge appended.

### Files by Phase

| Phase | New Files | Modified Files |
|-------|-----------|----------------|
| P10 | `src/sentinel.py` ✓ | `src/db.py`, `src/regime_arbiter.py`, `src/state.py`, `jobs/market_intel.py`, `jobs/market_close.py` |
| P7 | `src/adaptive_weights.py`, `src/sector_rotation_map.py` | `src/fragility_index.py`, `jobs/sunday_calibration.py`, `src/formatters.py` |
| P8 | `src/value_metrics.py` | `src/data_fetcher.py`, `jobs/sunday_calibration.py`, `src/formatters.py` |
| P9 | `src/scenario_simulator.py`, `src/historical_comparator.py`, `src/agent_query.py` | `src/bot_handler.py`, `.github/workflows/` (new webhook workflow) |
| P11 | `src/scenario_collision.py`, `src/liquidity_freeze.py` | `src/fragility_index.py`, `src/state.py`, `src/formatters.py`, `src/db.py` |
| P12 | — | `src/data_fetcher.py`, `src/transmission_mechanics.py`, `src/scenario_collision.py` |
| P14 | `src/fingerprint.py` | `jobs/market_intel.py`, `jobs/midday_scan.py`, `jobs/market_close.py` |
| P16 | `src/manifest.py`, `data/manifest.json` | `jobs/sunday_calibration.py` |
| P18 | `src/guardian.py` | `src/telegram_sender.py`, `src/formatters.py` (replaces `sentinel.py` conceptually) |

### Data Source Fixes (Q1 2026)

| Fix | File | Change |
|-----|------|--------|
| Sector tickers | `src/symbol_map.py` | `^CNXFINANCE`→`^CNXFIN`, added `^CNXINFRA` + alias + short_map entries |
| SMH/COPX/SOXX thresholds | `src/data_fetcher.py` | `SMH`/`COPX`/`SOXX` bump from 5%→10% daily change; `SMH` range [20,2000], `COPX` range [10,200] |
| Gold baseline | `src/consequence_engine.py` | 252D rolling mean from CSV for gold (static 2800.0 fallback) |
| India 10Y yield | `src/data_fetcher.py` | `get_india_10y_yield()` dual-source: yfinance → 7.0% hardcoded fallback with source label |
| NIFTYGS10YR.NS added | `src/data_fetcher.py` | Added to MACRO_ANCHORS as live Nifty G-Sec index tracker |
| AIEngine midday prompt | `src/ai_engine.py` | `midday_market_prompt()` static method; all prompts guard `consensus_sentiment` with `(cs or "neutral").upper()` |

### EOD Block Assembly (market_close.py)

| Block | Source | Condition |
|-------|--------|-----------|
| Regime headline | `regime_block` | Always |
| Scorecard | `brier_block` | Yesterday data available |
| **Pillars (compact)** | `scenario_block` with CSV fallback | CSV has data → `Active Pillars: ...` |
| Archetype banner | `scenario_collision.py` | Always shown (even "None detected" when pillars active) |
| Fragility/Drawdown | `drawdown_block` | Available only from Supabase |
| **Supplementary** | `sup_parts` | P11 debt stress, P11 liquidity freeze, IN10Y, **SMH/COPX >2%**, P8 ERP decile, P8 India vs EM, P7 adaptive weights |
| Flows (FII/DII) | `flows_block` | `ctx["flow_metrics"]` available |
| DII Capacity | `dii_capacity.py` | Supabase backfill available |
| FII Decomposition | `fii_decomposition.py` | Supabase backfill available |
| Derivatives | `derivs_block` | NSE v3 API available (stub when unavailable) |
| Sector Rotation Map | `rotation_block` | Fragility > 50 |
| Overnight / US Drivers | `overnight_block` | Global indices available |

### Test Strategy (All Phases Complete)

Full suite: `python3 test_all_outputs.py` — 7 sections, 26 scrubber patterns
Supabase tests: `.venv/bin/python3 test_supabase_full.py` (requires `SUPABASE_URL`+`SUPABASE_KEY`)
Full-day dry-run: `DRY_RUN=1 python3 jobs/<job>.py` for each of the 5 daily jobs

**Current status:** 7/7 test sections pass. Full-day dry-run: 8/8 jobs, 0 errors, 7 Telegram messages. P7–P12 locked. P14/P16/P18 modules created and wired into all 3 main jobs (market_intel, midday_scan, market_close). Batch-4 compliance fixes complete. Build phases: P0–P12 ✅, P14/P16/P18 ✅, batch-4 ✅. Next: Phase A (Ship Prep) → Phase B (Validation) → Phase C (Temporal) → Phase D (Utility) → Phase E (AI Econ). See Operational Roadmap above.
