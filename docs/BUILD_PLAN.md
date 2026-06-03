# Build Plan Reference

## Current State

| Dimension | Score | Status |
|-----------|-------|--------|
| **Deterministic Architecture** | 9 / 10 | Solid. "Python computes, AI narrates" enforced. Scrubber, block validators, no SQL-gen. |
| **Signal Validity** | 6 / 10 | Weakest dimension. Fragility thresholds (65/85) are unvalidated hypotheses. P17 needed. |
| **Operational Efficiency** | 5 / 10 | Every job recomputes everything. ~40% waste. P14 skip gate transforms this. |
| **Data Resilience** | 5 / 10 | Binary halt-or-go. Single NSE timeout = silence. P18 Guardian fixes this. |
| **User Utility** | 6 / 10 | Good at describing smoke. Poor at benign-vs-dangerous distinction. Structurally bearish. |
| **Storage/Economics** | 7 / 10 | 400 MB / 2 GB safe. P16 manifest eliminates unnecessary DB queries. |
| **Overall** | **6.2 / 10** | Smart risk monitor, not yet a regime navigation system. |

---

## Build Phase Inventory

### ✅ Done and Wired (P0–P12)

| Phase | What | Verdict |
|-------|------|---------|
| P0–P3 | Core data, pillars, intraday, stress index | ✅ |
| P4 | Fragility Index + Lifecycle Tracker | ✅ Locked |
| P5 | FII Decomposition + DII Capacity + Sector Flow Match | ✅ Locked |
| P6 | Event Volatility + Pre-Event Positioning + Intraday Pillar Check | ✅ Locked |
| P7 | Adaptive Weights + Sector Rotation Map | ✅ Locked |
| P8 | India vs EM RS + ERP Deciles | ✅ Locked |
| P9 | Scenario Simulator + Historical Comparator + NL Intent Query | ✅ Locked |
| P10 | Preflight Sentinel + Regime Membrane | ✅ Wired |
| P11 | External Debt Stress + Liquidity Freeze + Archetype Collisions | ✅ Locked |
| P12 | SMH/COPX Anchors + Heatflation/AI Displacement narratives | ✅ Locked |
| **P14** | Fingerprint Skip Gate (raw-anchor hash) | 🏗️ **Module exists, needs wiring** |
| **P16** | Lightweight Manifest (data/manifest.json) | 🏗️ **Module exists, needs wiring** |
| **P18** | Guardian 2.0 (3-tier triage) | 🏗️ **Module exists, needs wiring** |

### 🏗️ Wiring Sprint (P14 + P16 + P18 — Next Build Session)

All three modules are **created and tested** in isolation (`src/manifest.py`, `src/fingerprint.py`, `src/guardian.py`, `src/bot_state.py`, `data/manifest.json`). They need to be **wired into jobs**.

**Files to modify:**
| File | Change |
|------|--------|
| `jobs/market_intel.py` | Add fingerprint gate + guardian check at top |
| `jobs/midday_scan.py` | Add fingerprint gate + guardian check at top |
| `jobs/market_close.py` | Add fingerprint gate + guardian check at top |
| `jobs/sunday_calibration.py` | Write manifest.json at end of run |
| `src/telegram_sender.py` | Append `triage_badge` to regime line on YELLOW |
| `src/formatters.py` | Suppress options/GEX blocks on YELLOW |

**Validation checklist:**
- [ ] `DRY_RUN=1` on 3 jobs twice — second run skips via fingerprint (or heartbeat if >4h)
- [ ] `bot_state.last_fingerprint` and `bot_state.last_sent_at` updated correctly
- [ ] Simulate YELLOW (mock NSE timeout) — options suppressed, badge appended, deterministic stub

### 📋 Designed, Not Built (P20–P32)

| Phase | What | Effort | Priority | Depends On |
|-------|------|--------|----------|------------|
| **P20** | AI Blackout Mode — 12 pre-computed regime transition templates | 0.5 day | Medium | P16 manifest (template storage) |
| **P21** | Silent Monday — weekend gap detection via 3σ check at Monday 7AM | 0.5 day | **High** | P18 guardian (reuses triage flow) |
| **P22** | Clone Confidence — suppress weak (>1.5σ) historical analogs | 0.25 day | Low | None |
| **P23** | FII Staleness — `source_date` field + `(data lag: T-1)` annotation | 0.25 day | Medium | None |
| **P24** | Emergency Model — complexity circuit breaker at <40% 30d accuracy | 1 day | **High** | P17 accuracy tracking |
| **P25** | Event Cascade — link CPI outcome to MPC expectations | 1 day | Medium | P6 event_volatility exists |
| **P26** | Suppressed Volatility — VVIX/ATR override when VIX <15 for 10+ days | 0.5 day | Medium | P4 stress_index exists |
| **P17** | Living Thresholds + Holdout Wall — OOS-validated grid search | 1.5 day | Medium | P16 manifest |
| **P27** | State Journal — append-only `state_journal` table, no replace of `market_state` | 0.5 day | **High** | None |
| **P28** | Promise Engine — temporal coherence, 6 pillar matchers, 2-day gate | 1 day | Medium | P27 (reads journal) |
| **P29** | Pillar Decay — manifest half-lives, Fragility contribution decays by `exp(-0.1 × (age - half_life))` | 0.5 day | Low | P27 (state history for age) |
| **P30** | Paper P&L — position × Nifty return with 0.12% friction on change days, Sunday compute | 1 day | Medium | Sunday calibration exists |
| **P31** | Hollow Liquidity Detector — logic gate: SATURATED + FII <-8000 + A/D <0.7 | 0.5 day | Medium | P5 (DII Capacity exists) |
| **P32** | Containment Mode — extends Guardian: ≥2 source classes fail → lock regime | 0.5 day | Medium | P18 (Guardian exists) |

---

## Build Order (Recommended)

### Sprint 1: Wire P14 + P16 + P18 (Next Session)
1. Wire manifest writing into `sunday_calibration.py`
2. Add fingerprint gate + guardian check to `market_intel.py`, `midday_scan.py`, `market_close.py`
3. Add triage badge to `telegram_sender.py`, suppression logic to `formatters.py`
4. Validate: DRY_RUN 3 jobs twice (second run skips); simulate YELLOW

### Sprint 2: Structural Fixes (H1)
1. **P21 Silent Monday** — weekend gap detection. Prevents stale data on gap-open days. Wires into Guardian triage.
2. **P24 Emergency Model** — complexity circuit breaker. Prevents system from using degraded pillar/fragility complex.
3. **P20 AI Blackout Mode** — pre-computed regime transition templates. Cosmetic but makes double-AI-outage path readable.

### Sprint 3: Correctness & Polish (H2)
1. **P23 FII Staleness** — `(data lag: T-1)` annotation. Quick data-quality gate.
2. **P22 Clone Confidence** — suppress weak analog matches. 10-line change.
3. **P25 Event Cascade** — link CPI → MPC expectations. Requires refactoring prompt engine.
4. **P26 Suppressed Volatility** — VVIX/ATR override for low-VIX regimes.
5. **P17 Living Thresholds + Holdout** — OOS-validated grid search. Non-negotiable gate before trusting threshold outputs.

### Sprint 4: Bridges to 9.0 (Institutional Memory)
All phases <20ms weekday impact combined. See full spec in CLAUDE.md "Bridges to 9.0" section.

1. **P27 State Journal** — create `state_journal` table + `append_journal()` in every job runner. Audit trail + split-brain recovery.
2. **P31 Hollow Liquidity** — pure logic gate in `liquidity_proxy.py`. Appends `⚠️ LIQUIDITY: Hollow. DII Put inactive.` to regime line.
3. **P32 Containment Mode** — extend `guardian.py` `finalize()` with `source_classes` failure tracking.
4. **P28 Promise Engine** — `src/promise_engine.py` with 6 pillar matchers. Reads yesterday's journal, compares drivers.
5. **P29 Pillar Decay** — manifest half-lives + decay multiplier in Fragility Index Intensity component.
6. **P30 Paper P&L** — extend `prediction_tracker.py`. Sunday-only compute of YTD friction-adjusted returns.

---

## Key Constraints

| Constraint | Rule |
|------------|------|
| **GHA timeout** | All jobs <10 min. Sunday calibration pre-computes everything; weekday reads only. |
| **Supabase 2GB** | Time-series in CSV, state in Supabase. 7d purge on high-volume tables. |
| **GHA stateless** | No persistent listeners. `workflow_dispatch` triggers, compute, exit. |
| **AI architecture** | Python computes, AI narrates. Scrubber enforces. No temperature for facts. |
| **No SQL-gen** | Intent Catalog only. LLM classifies intent; Python fills slots and executes. |

---

## Verification Gates

| Gate | When | How |
|------|------|-----|
| Module imports | Every build | `python3 -c "from src.<module> import *"` |
| Scrubber patterns | Every build | `python3 test_all_outputs.py` |
| Supabase CRUD | Weekly | `.venv/bin/python3 test_supabase_full.py` |
| Dry-run | Per job | `DRY_RUN=1 python3 jobs/<job>.py` |
| Holdout validation | P17 only | `train_test_split` by date; only OOS-approved params reach manifest |
| Fingerprint skip | Sprint 1 | Run same job twice; second run must show "skipped" log line |

---

## Audit Gap Closure

| Dimension | Current | After Sprint 1 | After Sprint 2 | After Sprint 3 | After Sprint 4 |
|-----------|---------|----------------|----------------|----------------|----------------|
| Operational Efficiency | 5/10 | **9/10** (skip gate) | 9/10 | 9/10 | **9/10** (still 9) |
| Data Resilience | 5/10 | **8/10** (Guardian YELLOW) | **9/10** (+ Silent Monday) | 9/10 | **9.5/10** (+ Containment Mode, + State Journal) |
| Signal Validity | 6/10 | 6/10 | **7/10** (+ Emergency Model) | **9/10** (+ Holdout Wall) | **9/10** (+ Promise Engine temporal coherence) |
| User Utility | 6/10 | **8/10** (divergence block) | 8/10 | **9/10** (+ Cascade + Clone Confidence) | **9/10** (+ Pillar Decay context) |
| Storage/Economics | 7/10 | **9/10** (manifest) | 9/10 | 9/10 | **9/10** (still 9) |
| Deterministic Arch | 9/10 | 9/10 | 9/10 | 9/10 | **9.5/10** (+ State Journal audit trail, + Paper P&L) |
| **Overall** | **6.2/10** | **8.2/10** | **8.5/10** | **9.2/10** | **9.4/10** |

---

## Reference: Key Module Locations

| Module | Path | Purpose |
|--------|------|---------|
| Fingerprint | `src/fingerprint.py` | Raw-anchor Blake2b hash + heartbeat skip logic |
| Manifest | `src/manifest.py` | `load()` with schema validation |
| Guardian | `src/guardian.py` | 3-tier triage (GREEN/YELLOW/RED) |
| Bot State | `src/bot_state.py` | Supabase helpers for `last_fp` / `last_sent_at` |
| Manifest data | `data/manifest.json` | Bucket sizes, fragility thresholds, templates |
| Sentinel | `src/sentinel.py` | P10 preflight + regime membrane (being replaced by Guardian) |
| State Journal | `src/state_journal.py` | Append-only journal for audit trail & split-brain recovery |
| Promise Engine | `src/promise_engine.py` | Temporal coherence: compares yesterday's drivers to today's anchors |
| Liquidity Proxy | `src/liquidity_proxy.py` | P31 hollow liquidity detector logic gate |
| Paper P&L | built into `src/prediction_tracker.py` | Position × Nifty return with friction |
