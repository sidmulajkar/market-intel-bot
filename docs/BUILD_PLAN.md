# Build Plan: v0.5-beta → v1.0

**Rating:** 8.1 / 10 — Coherent checkpoint. Determinism membrane sealed, cost under control, temporal integrity wired. Remaining work is epistemological patience.

---

## ✅ v0.5-beta: Complete (Commit 510f5bd)

All Phase A–C code implemented, tested, and committed. Supabase fail-open throughout.

### Phase A: Ship Preparation ✅
| Item | Status |
|------|--------|
| **A.1 P16 Manifest Schema** — `data/manifest.json` with fingerprint_buckets, fragility thresholds, adaptive_weights, templates | ✅ Done. `src/manifest.py` validates, returns safe defaults |
| **A.2 P14 Fingerprint Gate** — Skip gate in market_intel, midday, close. Should-skip logic (fp match + <4h → exit 0, ≥4h → heartbeat) | ✅ Done. `src/fingerprint.py` wired in 3 jobs |
| **A.3 P18 Guardian Triage** — GREEN/YELLOW/RED tiers replacing binary halt. YELLOW suppresses options, bypasses AI, appends badge | ✅ Done. `src/guardian.py` replaces sentinel |
| **A.4 Options Fallback Chain Fix** — 4-tier fallback instrumented | ✅ Done. Tombstones suppressed on failure |

### Phase B: Validation & Calibration ✅
| Item | Status |
|------|--------|
| **B.1 P17 Holdout Wall** — Grid search Fragility thresholds on T-12M, validate on 90d holdout | ✅ Wired in `sunday_calibration.py` |
| **B.2 P30 Paper P&L** — `position_today = map_regime_to_position(final_regime)`, friction 0.12% STT + 5bps slippage, weekly Paper Track line | ✅ Done. `src/prediction_tracker.py` |

### Phase C: Temporal Integrity ✅
| Item | Status |
|------|--------|
| **C.1 P27 State Journal** — Append-only journal per job. On crash, warm up from last row | ✅ Done. `src/state_journal.py`. Deferred in .gitignore pending Supabase key |
| **C.2 P28 Promise Engine** — `detect_stale_lifecycle()` flags regime drift when drivers reverse but lifecycle state hasn't updated | ✅ Done. In `src/pillar_lifecycle.py` |
| **C.3 P29 Pillar Decay / Half-Life** — `pillar_half_lives` in manifest. `effective_score = raw_score × lifecycle_mult × exp(-0.1 × max(0, age - half_life))` | ✅ Done. In `src/fragility_index.py` |

---

## Forward Roadmap

### Option A: The Monk (Recommended)

Do not add features for **14 days**. Run the bot silently and collect:

| Week | What to Watch | Decision Trigger |
|------|---------------|-----------------|
| **Week 1** | First `Paper Track (YTD)` line in Sunday digest | If `Net` is positive vs Buy-Hold, signal has edge |
| **Week 2** | Check adaptive weights in manifest | If weights drift further from 1.0, system is learning |
| **Week 3** | Regime accuracy vs Nifty direction | If regime calls <55% directional, Fragility is decorative |

**If P30 fails (Net alpha negative after 30 days):**
- Raise `Base Fragility` weight from 40% → 60% in `manifest.json` (stress is more predictive than pillars)
- Accept the bot as a brilliant macro monitor, not a decision-support system

### Option B: The Surgeon (If you must code)

Three high-utility, low-risk additions that don't require a P30 verdict:

#### 1. P15 Divergence Block (<100ms, zero new data calls)
Three cheap sensors inside `should_skip()` — if any fire, force full compute even on matching fingerprint:
- **Cross-asset divergence:** Nifty unchanged but VIX changed >10% from last fingerprint
- **Sector divergence:** >2 sectors moved >1% opposite to Nifty
- **Macro-implied vs actual:** Consequence Engine implied Nifty move vs actual — if `|implied - actual| > 0.8%`, market is held up mechanically

**Why now:** Turns skip gate from blunt cost weapon into sharp signal filter.

#### 2. Smart Market Close (middle tier, zero AI cost)
When fingerprint matches but it's the Close job, emit a *minimal deterministic* block instead of full stub:
```
📌 *MARKET CLOSE*
🟡 Steady State: NEUTRAL | Nifty 23,367 (+0.1%)
📌 Flows: FII ₹-1,203Cr | DII ₹+980Cr
💤 No regime shift.
```

**Why:** Users lose daily FII/DII data on quiet days. This gives it back at $0 cost.

#### 3. "Screaming Anchor" Bypass (20 lines in `should_skip()`)
Bypass the skip gate when specific anchors cross crisis thresholds:
- FII 5D flow crosses ±₹10,000 Cr
- VIX spikes >20% in a single session
- War / RBI / SEBI headline with FinBERT sentiment >0.8

**Why:** Prevents the bot from stubbing through a black-swan morning.

### Keep on the Shelf (Crisis-Only, Do Not Build Now)
- **P31 Hollow Liquidity:** `DII_SATURATED + FII_5D < -8000 + advance_decline < 0.7 → ⚠️` alert
- **P32 Containment:** ≥2 source class failures → lock regime, pre-canned alert
- **P9+ Telegram commands:** `/lastchange`, `/regime`, `/alertme` — useful but distracting

---

## Success Criteria

| Milestone | Deliverable | Exit Criteria |
|-----------|-------------|---------------|
| **v0.5-beta** ✅ | `510f5bd` | 8/8 dry-run passes; no `TODO` in working code; all modules wired to graceful fallback |
| **v0.6** | 14-day observation | Paper P&L prints in Sunday digest; skip gate operates silently; zero Supabase errors |
| **v0.7** (if P30 passes) | Signal validation | Net paper alpha > Buy-Hold after 30 days; adaptive weights ≠ 1.0 |
| **v0.8** (if coding) | P15 + Smart Close + Screaming Anchor | Divergence detection wired; Close shows flows on quiet days; crisis anchors bypass gate |
| **v1.0** | Stable 90-day run | Zero silent failures; regime accuracy published; scorecard calibration n>30 |

## Budget

| Addition | GHA Time | DB Storage | Writes/Run | Status |
|----------|----------|------------|------------|--------|
| P14/P16/P18 Skip Gate | -2 min saved | 0 (local file) | 1 write | ✅ Done |
| P27 State Journal | +5 ms | 30 rows/mo | 1 INSERT | ✅ Done (deferred) |
| P28 Promise Engine | +10 ms | 0 | 0 | ✅ Done |
| P29 Pillar Decay | 0 | 0 | 0 | ✅ Done |
| P30 Paper P&L | Sunday +2 min | 1 JSONB row | 0 (weekday) | ✅ Done |
| P15 Divergence | +100 ms | 0 | 0 | ⏳ Backlog |
| Smart Close | 0 | 0 | 0 | ⏳ Backlog |
| Screaming Anchor | 0 | 0 | 0 | ⏳ Backlog |
| P31 Hollow Liquidity | +1 ms | 0 | 0 | 📋 Shelf |
| P32 Containment | +2 ms | 0 | 0 | 📋 Shelf |

## Forbidden Items

| Item | Why Blocked |
|------|-------------|
| Real-time entity-level FII data | No public API. SEBI bulk deals cover <20%. |
| SRF Utilization / G-SIB LCR | Confidential / lagged (RBI monthly). |
| COT Net-Short Positioning | Too large for 10-min GHA timeout. |
| New macro pillars | Architecture closed. No P13. |
| New features before 14-day observation | Signal validity is 6.5/10 — only time and data can raise that score |
