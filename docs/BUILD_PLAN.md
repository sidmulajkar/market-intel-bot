# Build Plan: Beta → v1.0

**Rating:** 7.0/10 — ship as beta. Feature-complete, operationally immature.

**Constraint:** Do not start Phase B until Phase A is fully wired. `manifest.json` is the dependency for everything else. No feature is added before the membrane is sealed.

---

## Phase A: Ship Preparation (Week 1)

Push `v0.5-beta` with no hidden state, no `TODO()` in working code, all modules wired to graceful fallback.

### A.1 Manifest Schema Lock (P16)
- [ ] Finalize `data/manifest.json` schema with `fingerprint_buckets`, `fragility` thresholds, `adaptive_weights`, `sector_tilt_map`, `erp_deciles`, `templates` (intel stubs, heartbeat, yellow stub)
- [ ] `src/manifest.py`: `load()` validates schema, returns safe defaults if corrupt. No `KeyError` reaches a job runner
- [ ] `jobs/sunday_calibration.py`: Append all pre-computed variables into this JSON as the single write commit at end of run
- **Test:** `python3 -c "from src.manifest import load; d=load(); assert 'fingerprint_buckets' in d"`

### A.2 P14 Fingerprint Gate Wiring
- [ ] Add skip gate to top of `jobs/market_intel.py`, `jobs/midday_scan.py`, `jobs/market_close.py`:
  - `fp == last_fp ∧ <4h` → `exit 0` (hard skip, no Telegram)
  - `fp == last_fp ∧ ≥4h` → heartbeat template (deterministic, no AI)
  - `fp != last_fp` → full pipeline → update bot_state
- **Test:** `DRY_RUN=1 python3 jobs/market_intel.py` (first run full, second run skip)

### A.3 P18 Guardian Integration (Replace P10 Sentinel)
- [ ] Replace ad-hoc sanity checks with `Guardian.check_source()` per fetcher, `finalize(anchors) → triage`
- [ ] `triage == RED` → `send_alert, sys.exit(1)`
- [ ] `triage == YELLOW` → suppress options_block, bypass AI (use `manifest.templates["yellow_stub"]`), append `⚠️ Delayed/Partial` badge
- [ ] Wire triage into `formatters.py` (suppress GEX/options on YELLOW) and `telegram_sender.py` (append badge to regime line)
- **Test:** Mock NSE timeout → verify options block suppressed, badge present

### A.4 Options Fallback Chain Fix
- [ ] Instrument each tier in `src/options_engine.py`: ① Supabase → ② MarketState → ③ NSE v3 live → ④ file cache
- [ ] Log which tier is the failure point
- [ ] Decision gate: If NSE v3 is structurally unreliable after 1 week production logging → **reclassify derivatives as conditional bonus block** (move to `/gex` command only). Do not let a dead third of the system block the other two layers

---

## Phase B: Validation & Calibration (Week 2–3)

Prove that mathematical thresholds mean something. Replace guesswork with evidence.

### B.1 P17 Living Thresholds with Holdout Wall
- [ ] In `sunday_calibration.py`: Grid search Fragility thresholds [50–90 step 5] on `T-12M` training set
- [ ] Validate on last 90 days holdout. Only validation-approved parameters reach `manifest.json`
- [ ] If holdout accuracy ≤ equal-weights → keep defaults, log warning
- **Forbidden:** No grid search on weekday jobs (10-min timeout)

### B.2 Paper P&L Prototype (P30)
- [ ] `prediction_tracker.py`: `position_today = map_regime_to_position(final_regime)` (+1/0/-1)
- [ ] Daily return = `position_yesterday × Nifty_return_today`
- [ ] Friction: 0.12% STT + 5bps slippage on position-change days
- [ ] Weekly: `Paper Track (YTD): Gross +X% | Net +Y% | Buy-Hold +Z%`
- **Success:** After 30 days of production, check if net paper P&L has positive alpha vs buy-hold. If not, Fragility Index is decorative

---

## Phase C: Temporal Integrity (Week 3–4)

Prevent stale narratives, phantom regimes, silent data rot.

### C.1 P27 State Journal
- [ ] New Supabase table: `state_journal(timestamp, job_tag, fingerprint, regime, fragility, pillars, triage, manifest_version)`
- [ ] Every job on success calls `append(record)`
- [ ] On crash, next run reads last journal row to warm up market_state

### C.2 P28 Promise Engine
- [ ] Define `PILLAR_DRIVERS` mapping in `pillar_lifecycle.py`
- [ ] Before final formatting, compare current drivers to yesterday's `state_journal`
- [ ] If drivers improved >3σ but lifecycle is `ESCALATING` → append `⚠️ REGIME DRIFT: Stagflation drivers eased. Lifecycle stale.`

### C.3 P29 Pillar Decay / Half-Life
- [ ] Add `pillar_half_lives` to manifest. Half-lives: Carry Unwind 5d, West Asia 7d, Stagflation 10d, EM Contagion 12d, Tech Cycle 20d, De-dollarization 25d
- [ ] In `fragility_index.py`: `effective_score = raw_score × lifecycle_mult × exp(-0.1 × max(0, age - half_life))`
- [ ] Age from `state_journal` history

---

## Phase D: User Utility Hardening (Week 4)

### D.1 P15 Divergence Block
- [ ] Three cheap sensors before AI call:
  - Cross-asset divergence (Nifty flat but VIX rising)
  - Sector divergence (>2 sectors moving >1% opposite)
  - Macro-implied vs actual (Consequence Engine implied Nifty move vs actual)
- [ ] No divergence + regime unchanged → `manifest.templates["steady_state"]` (no AI)
- [ ] Only if divergence detected → allow AI

### D.2 P31 Hollow Liquidity + P32 Containment
- [ ] `src/liquidity_proxy.py`: `IF dii_capacity == SATURATED AND fii_5d < -8000 AND advance_decline < 0.7 → ⚠️ HOLLOW LIQUIDITY: DII Put inactive`
- [ ] `src/guardian.py`: If ≥2 source classes fail simultaneously → CONTAINMENT (lock regime, pre-canned alert)

---

## Phase E: AI Economics (Backport to P14)

- [ ] Add `intel_stubs` to manifest per regime (NEUTRAL, BULLISH, DEFENSIVE)
- [ ] If fingerprint unchanged and triage GREEN → bypass AI, return `manifest.intel_stubs[regime].format(...)`
- [ ] Reserve AI for: regime transitions, YELLOW triage, fragility > 80
- **Goal:** AI API calls drop from ~14/week → ~4/week without user-perceived quality loss

---

## Budget

| Addition | GHA Time | DB Storage | Writes/Run |
|----------|----------|------------|------------|
| P27 State Journal | +5 ms | 30 rows/mo | 1 INSERT |
| P28 Promise Engine | +10 ms | 0 | 0 (reads journal) |
| P29 Pillar Decay | 0 | 0 | 0 (manifest math) |
| P30 Paper P&L | Sunday +2 min | 1 JSONB row | 0 (weekday) |
| P31 Hollow Liquidity | +1 ms | 0 | 0 |
| P32 Containment Mode | +2 ms | 0 | 0 |

**Weekday impact:** < 20 ms per job.

---

## Forbidden Items

| Item | Why Blocked |
|------|-------------|
| Real-time entity-level FII data | No public API. SEBI bulk deals cover <20%. |
| SRF Utilization / G-SIB LCR | Confidential / lagged (RBI monthly). |
| COT Net-Short Positioning | Too large for 10-min GHA timeout. |
| New macro pillars | Architecture closed. No P13. |

---

## Success Criteria

| Milestone | Deliverable | Exit Criteria |
|-----------|-------------|---------------|
| **v0.5-beta** | GitHub push | 7-message dry-run passes; no `TODO` in working code |
| **v0.6** | P14+P18 wired | Flat-day messages ≤ 2; Guardian YELLOW handles NSE timeout |
| **v0.7** | P17 holdout + P30 live | 12-week rolling paper P&L positive net of friction; adaptive weights ≠ 1.0 |
| **v0.8** | P27+P28+P29 | State journal append-only; Promise Engine flags stale lifecycles; pillar decay active |
| **v0.9** | P15 divergence + P31/P32 | Hollow liquidity fires; AI tokens cut 60% via manifest stubs |
| **v1.0** | Stable 90-day run | Zero silent failures; scorecard calibration (n>30); regime accuracy published |
