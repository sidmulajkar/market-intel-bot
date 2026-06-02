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

- **Regime Arbiter:** Single compute 08:00 → `market_state.final_regime`. Downstream read-only. Global Arbiter Layer 1b (STAGFLATION/LIQUIDITY→FORCE DEFENSIVE, RISK_OFF→cap NEUTRAL). Pillar Layer (Fragility hook). `_defensive_triggers()` shows escalation/de-escalation thresholds.
- **Arbiter override hierarchy:** Only Layer 1b (Global Arbiter) + Layer 2 (Fragility Index) remain. Hard-coded price thresholds (USDINR > 94.5, Brent > 90) deleted. Fragility > 65 caps NEUTRAL, > 85 forces DEFENSIVE.
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

**P0-36:** 58+ modules, 270+ functions, 14 cron jobs, 31 tables, 15 workflows. Full-day dry-run: 8 jobs, 7 messages, 0 errors. Calibration 94% pass rate (7/10 episodes testable).

**P39 A0–A4:** Stock prompt sanitized, GEX magnetic levels, drawdown anatomy, sector phases, 6 Telegram commands, pinned glossary.

**P40-49:** LQD+SOXX anchors, global arbiter (4-state, 4-episode backtest), 2-tier global clone engine, cross-border transmission matrix, codebase health (calendar staleness, self-audit, purge entries).

**P1 (CSV):** `anchor_history.csv` (1,304×24), `nifty_history.csv` (1,235), `fii_dii_history.csv` (58). Backfill → purge pipeline. SHAP+EEM for clone fwd returns.

**P2 (Pillars):** `pillar_classifier.py` — 6 pillars (Stagflation, West Asia, EM Contagion, Carry Unwind, De-dollarization, Tech Cycle). Threshold-gated weight-normalized. ↑↓ arrows. `transmission_mechanics.py` — 6 deterministic chains. Wired into `format_scenario_block()` + market_intel. `sunday_simulation` pre-computes. Calibration: 94% pass (7 testable).

**P3 (Intraday):** `intraday_pulse.py` — 30-min Nifty+VIX, CALM/WATCH/ALERT, state-change-only. GHA `*/30 4-9 * * 1-5`.

**P4 (Fragility+Lifecycle):** ✅ Locked. `fragility_index.py` — 3-component composite (Base 40%/Breadth 30%/Intensity 30%). Arbiter Layer 2 replaces hard-coded thresholds. `pillar_lifecycle.py` — EMERGING/ESCALATING/SUSTAINED/DE-ESCALATING states, EMERGING×0.6 multiplier. Full-day validation: Fragility=60 leaves regime NEUTRAL (below 65 cap).

**P5 (Institutional Micro):** ✅ Locked. `fii_decomposition.py` — Dual-path entity/SEBI fallback, graceful `(entity data pending)` when SEBI lags. `dii_capacity.py` — 1-line compact gauge: `99.8% deployed | SATURATED | MF ₹+11Cr/d (insufficient) | FII 5D ₹26,742Cr`. `sectoral_drag.py` — T-1 cache to Supabase bot_state for sector flow fallback.

**P6 (Event Dynamics):** ✅ Locked. `event_volatility.py` — `scan_upcoming_events()` appends `Avg Nifty move ±0.8% (n=60)` to risk calendar. `detect_pre_event_positioning()` — PCR/Skew shift with stale snapshot fallback, fires within 2d of high-impact events. `check_intraday_pillar_confirmation()` — directional tick counting validates/refutes pillars in 12:30 scan (e.g., `STAGFLATION: CONFIRMED 5c/1d`).

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

## Phase 7: Adaptive Calibration & Regime Rotation

**Concept:** The system uses static equal-weight logic for pillars. Empirical hit rates vary: EM Contagion might be a weak predictor (20%), Stagflation a strong one (80%). Phase 7 makes the system learn its own accuracy and maps historical sector behavior to pillar configurations.

### 7.1: Dynamic Pillar Weighting
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

**Module:** `src/adaptive_weights.py` (new). Reads `signal_accuracy_log`, writes `dynamic_weights` JSON.

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

**Output placement:** Below `Pillar-Flow Match` block in 15:30 EOD, only when Fragility > 50.

**Module:** `src/sector_rotation_map.py` (new). Reads `sector_rs` + `pillar_metrics`. Binning: pillar score ±10 buckets.

---

## Phase 8: Relative Value & Cross-Border Arbitrage (Horizon)

**Concept:** The bot currently treats India in glorious isolation, with global data only serving as "triggers" for the local framework. But capital flows are a zero-sum game between geographies. When a global fund decides to reduce EM exposure, it doesn't just sell India — it reallocates to DM bonds, US tech, or Japan value. India's underperformance relative to its EM peers is a signal in itself.

### 8.1: India vs EM Basket
- Track Nifty's relative strength against MSCI Emerging Markets ETF (EEM) over a rolling 30-day window.
- If India underperforms EEM by > 5% during this window, AND the EM Contagion pillar is concurrently ACTIVE → this signals a structural reallocation *out of India specifically*, not just a general EM exit.
- Implication: Nifty is losing its premium status within EM. The "India decoupling" narrative is failing in real-time.

**Module:** `src/cross_border_flow.py` (new). Reads yfinance data for `EEM` and `^NSEI`. Compares 30D rolling RS.

### 8.2: Bond/Equity Switch
- Track the Equity Risk Premium (ERP): `(1 / Nifty PE) - India 10Y Yield`.
- When ERP drops below 0 (currently at -2.12% as of June 2026), compute the historical probability of Nifty generating positive 30-day forward returns at this ERP level.
- Use 5 years of `anchor_history.csv` to bin ERP into deciles and calculate the forward return distributions.
- **If ERP is deeply negative AND in the bottom decile historically** → mathematically justifies a defensive tilt toward bonds over equities without any AI speculation.

**Output:** `ERP: -2.12% (bottom decile) | Historical prob of positive Nifty 30D: 22% (18/82 occurrences)`. Pure descriptive statistics.

**Module:** `src/bond_equity_switch.py` (new). Reads CSV + current Nifty PE from market_state.

---

## Phase 9: Autonomous Agent Interactivity (Horizon)

**Concept:** Phase A3 gave us basic Telegram commands (`/stress`, `/flows`, `/gex`, `/sectors`, `/whatif`, `/clone`). Phase 9 expands this into a full conversational query layer where the bot acts as an autonomous agent against its own deterministic data store. The critical constraint: zero AI number generation. AI is used only for natural language-to-SQL translation and result summarization. All numbers come from deterministic engines.

### 9.1: Scenario Simulator
- `/simulate brent 120`: Runs the Consequence Engine + Pillar Classifier + Fragility Index with `Brent` hardcoded to 120 for the current session.
- Returns: Theoretical regime shift ("Stagflation → 78/100 ELEVATED, Fragility → 81, Regime → force DEFENSIVE"), impact multipliers (import bill increase ₹X Cr), and transmission chain output.
- No AI involved — purely deterministic with one parameter overridden.

**Module:** `src/scenario_simulator.py` (new). Creates a temporary `macro_attrs` dict with the overridden value, then calls the same pipeline: `consequence_engine → pillar_classifier → fragility_index → regime_arbiter`.

### 9.2: Historical Comparator
- `/compare 2013-08-15`: Pulls the exact 12D macro vector (all 24 columns) from `anchor_history.csv` for that date.
- Side-by-side comparison with today's vector: same metrics, color-coded differences.
- If the Taper Tantrum is identified as a "clone" by the Clone Engine, this gives the user direct access to the raw data behind the clone match.

**Module:** `src/historical_comparator.py` (reuses or extends `clone_engine` data access patterns).

### 9.3: Natural Language Query Layer
- Natural language queries like "what's driving FII selling this week?" are parsed by LLM into deterministic DB reads against known tables.
- The LLM never generates numbers. It generates SQL-like queries (or structured data access patterns) that the bot executes against Supabase.
- Result is formatted and returned as a Telegram message.
- **Scope:** Read-only queries. No state mutation. No trade suggestions.

**Module:** `src/agent_query.py` (new). Uses LLM for intent parsing → query construction → deterministic execution → result formatting.

---

## Phase Priority & Sequencing

| Phase | Effort | Risk | Value | Depends On | Start |
|-------|--------|------|-------|------------|-------|
| P4 (Fragility+Lifecycle) | 4 hr | Low | High — closes pillar-arbiter gap | P2 (Pillars), P3 (Stress Index) | **✅ Locked** |
| P5 (Institutional Micro) | 5 hr | Medium | High — grounds pillars in cash flows | P4 (Fragility provides the regime context) | **✅ Locked** |
| P6 (Event Dynamics) | 3 hr | Low | Medium — transforms calendar into stats | P0 (Economic Calendar), Anchor History CSV | **✅ Locked** |
| P7 (Adaptive Weights) | 3 hr | Medium | Medium — system learns its own accuracy | P4 (needs Fragility Index as target), Signal Accuracy Log | After P6 |
| P8 (Relative Value) | 4 hr | High | Medium — cross-border context | P4 (needs regime context to interpret RS divergence) | After P7 |
| P9 (Agent Interactivity) | 5 hr | High | High — conversational deterministic query | All prior phases (max data surface for queries) | After P8 |

**Summary rationale (completed):** P4 closed the pillar-arbiter gap with a continuous Fragility Index (no hard-coded thresholds). P5 grounded theoretical pillars in actual FII/DII cash flows. P6 transformed the risk calendar into statistical facts and validated pillars in real-time via intraday ticks. P7-P9 represent the adaptive and interactive frontier — Phase 7 makes the system learn its own accuracy via dynamic weights; Phase 8 adds cross-border relative value context; Phase 9 expands Telegram into a conversational deterministic query layer.
