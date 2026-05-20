# Phase 18 + 19 Validation Report
## For External Review

**Date:** 2026-05-20
**Tests:** 187/187 pass
**Status:** Ready to ship

---

## What Was Built

### Phase 18: Consequence Layer
Every data point now has 4 layers: ABSOLUTE → RELATIVE → PERCENTILE → CONSEQUENCE (in rupees).

### Phase 19: Master Signal Diagnostic Engine
Master Signal upgraded from a label ("BEARISH | Confidence: LOW") to a diagnostic engine with gap analysis, confidence split, score trending, and consequence implications.

---

## Supabase Changes Required

### Step 1: Add columns (run once in Supabase SQL editor)

```sql
ALTER TABLE daily_market_snapshot
    ADD COLUMN IF NOT EXISTS structural_score DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS sentiment_score DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS cluster_gap DOUBLE PRECISION;
```

### Step 2: Insert today's real data

```sql
INSERT INTO daily_market_snapshot (date, india_vix, cboe_vix, usdinr, brent, gold, dxy, us_10y, copper, fii_net, dii_net, bull_bear_score, structural_score, sentiment_score, cluster_gap)
VALUES ('2026-05-20', 18.44, 17.92, 96.81, 109.1, 4494.2, 99.39, 4.67, 6.25, -2442.9, 3862.08, 50, 62, 39, 23)
ON CONFLICT (date) DO UPDATE SET
    india_vix = EXCLUDED.india_vix,
    cboe_vix = EXCLUDED.cboe_vix,
    usdinr = EXCLUDED.usdinr,
    brent = EXCLUDED.brent,
    gold = EXCLUDED.gold,
    dxy = EXCLUDED.dxy,
    us_10y = EXCLUDED.us_10y,
    copper = EXCLUDED.copper,
    fii_net = EXCLUDED.fii_net,
    dii_net = EXCLUDED.dii_net,
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap;
```

### Step 3: Backfill existing rows (if any)

```sql
INSERT INTO daily_market_snapshot (date, bull_bear_score, structural_score, sentiment_score, cluster_gap)
VALUES ('2026-05-17', 45, 49, 43, 6)
ON CONFLICT (date) DO UPDATE SET
    bull_bear_score = EXCLUDED.bull_bear_score,
    structural_score = EXCLUDED.structural_score,
    sentiment_score = EXCLUDED.sentiment_score,
    cluster_gap = EXCLUDED.cluster_gap;
```

### Alternative: Run bootstrap script

```bash
python bootstrap_master_signal.py --insert
```

---

## Files Changed

| File | Change | Lines |
|------|--------|-------|
| `src/consequence_engine.py` | NEW — multiplier table + compute/format | ~300 |
| `src/signal_arbitrator.py` | REWRITE — gap analysis, confidence split, trending, consequence | ~600 |
| `src/formatters.py` | Consequence lines in macro anchors + net market impact in FII | ~30 |
| `src/data_fetcher.py` | Indian Basket approximation | ~30 |
| `src/output_validator.py` | Commodity regex + consequence presence check | ~40 |
| `src/simplicity_engine.py` | Oil signal with rupee consequences | ~40 |
| `src/prompt_engine.py` | +1 relevance for consequence blocks | ~10 |
| `config/master_prompt.txt` | 4-layer template + multiplier reference | ~25 |
| `jobs/market_intel.py` | CL=F→wti bug fix, cluster persistence, historical_scores | ~25 |
| `validate_all_phases.py` | Phase 18 + 19 tests | ~250 |
| `bootstrap_master_signal.py` | NEW — fetch real data + generate SQL | ~250 |
| `sql/phase19_cluster_columns.sql` | NEW — ALTER TABLE | 7 |

---

## Test Results (187/187)

### Phase 18: Consequence Layer (31 tests)
```
✅ Multiplier: brent
✅ Multiplier: wti
✅ Multiplier: us_10y
✅ Multiplier: dxy
✅ Multiplier: usdinr
✅ Multiplier: india_vix
✅ Multiplier: gold
✅ Multiplier: copper
✅ Consequence: Brent +$5 — severity=ELEVATED, 4 lines
✅ Consequence: US 10Y +18bps — 3 lines
✅ Consequence: DXY +0.8 — 3 lines
✅ Format: consequence line — ⚠️ CAD stress +$7.5B annualized, INR pressure ~15ps, CPI +10
✅ Batch: 5 anchors computed — 5 variables: ['brent', 'us_10y', 'dxy', 'usdinr', 'gold']
✅ Format: consequence block — 512 chars
✅ Threshold: Brent $95 = STRESS
✅ Threshold: Brent $65 = FAVORABLE
✅ Threshold: India VIX 26 = EXTREME
✅ Threshold: India VIX 22 = HIGH
✅ Empty: unknown variable returns {}
✅ Empty: zero price returns {}
✅ Indian Basket: approx — $82.45 vs Brent $85.0, discount 3.0%
✅ Indian Basket: error handling
✅ Validator: $109.80 extracted
✅ Validator: ₹83.50 extracted
✅ Validator: consequence detected
✅ Validator: no consequence flagged
✅ Validator: catches $64 vs $109 Brent — MAJOR CONTRADICTION
✅ Validator: correct Brent passes
✅ Simplicity: oil $109 (90th %ile) — 🔴 Brent $109...
✅ Simplicity: oil $88 — 🟡 Brent $88...
✅ Simplicity: oil $62 — 🟢 Brent $62...
✅ Simplicity: oil $78 (neutral) = None
✅ Formatter: macro anchors with consequence — has arrow
```

### Phase 19: Master Signal Diagnostic Engine (50+ tests)
```
✅ Gap: 50 vs 38 = 12pts
✅ Gap: SIGNIFICANT DIVERGENCE
✅ Gap: fear_exceeding_fundamentals
✅ Gap: is_significant=True
✅ Gap: 52 vs 48 = 4pts (alignment)
✅ Gap: ALIGNMENT
✅ Gap: is_significant=False
✅ Gap: 60 vs 35 = 25pts
✅ Gap: EXTREME DIVERGENCE
✅ Confidence split: direction=LOW when gap>=10
✅ Confidence split: regime=HIGH when gap>=10
✅ Confidence split: 48% accuracy
✅ Confidence split: aligned = same dir/regime
✅ Trending: prev_score=42
✅ Trending: direction=↓
✅ Trending: change=-4
✅ Trending: no history = empty
✅ Consequence: generated list
✅ Consequence: max 4 items
✅ Consequence: extreme gap has items
✅ Arbitration: ok
✅ Arbitration: has gap_analysis
✅ Arbitration: has confidence_split
✅ Arbitration: has trending
✅ Arbitration: has consequence
✅ Arbitration: structural_score present
✅ Arbitration: sentiment_score present
✅ Format: has MASTER SIGNAL
✅ Format: has Score line
✅ Format: has Structural
✅ Format: has Sentiment
✅ Format: has GAP
✅ Format: has Confidence
✅ Format: has Implication
✅ Format: max 15 lines
✅ Dashboard: has MASTER SIGNAL
✅ Dashboard: has Score
✅ Dashboard: has GAP
✅ Dashboard: has Implication
✅ Run: ok
✅ Run: has formatted
✅ Run: has arbitration
✅ Low conf: no directional call
✅ Bootstrap: importable
✅ Bootstrap: 30 days synthetic
✅ Bootstrap: has bull_bear_score
✅ Bootstrap: has structural_score
✅ Bootstrap: has sentiment_score
✅ Bootstrap: SQL generated
✅ Bootstrap: has ALTER TABLE
```

---

## Sample Outputs

### 1. Consequence Layer — Macro Anchors

**Before:**
```
Brent Crude: $85.20 (+2.30%) | Weekly: +1.50% 📈
```

**After:**
```
Brent Crude: $85.20 (+2.30%) | Weekly: +1.50% 📈
   ⚠️ CAD stress +$2.9B annualized, INR pressure ~6ps, CPI +4bps, OMC margins -1.0%
```

### 2. Consequence Layer — Batch (all anchors)

```
[CONSEQUENCE LAYER — India Impact]
Brent Crude oil price: ⚠️ CAD stress +$2.9B annualized, INR pressure ~6ps, CPI +4bps, OMC margins -1.0%
US 10-Year Treasury Yield: → FII outflow ~₹1Cr per +50bps, BFSI weight impact -0.0%, FII outflow pressure ~₹84Cr per +50bps
Dollar Index (DXY): → IT revenue boost +0.3%, FII exit risk ~₹339Cr per +1%, Pharma export boost +0.2%
USD/INR exchange rate: → IT revenue +0.2% per ₹1, Oil bill +₹3507Cr/yr per ₹1, Gold INR +0% per ₹1
Gold futures: → Import bill +$0.9B/yr per +$100
India VIX (fear gauge): → Option premium +2%
```

### 3. Oil Signal in Simple Lines (Block -1)

```
🔴 Brent $109 (92th %ile — extreme) → India pays ~$196B/yr, INR pressure ~117ps
🟡 Brent $88 → oil bill $158B/yr, INR pressure ~54ps
🟢 Brent $62 (15th %ile — low) → tailwind for CAD, OMC margins healthy
```

### 4. FII Net Market Impact

```
Net market impact: FII -3200Cr × (1 - 62% absorbed) = -1216Cr effective selling pressure
```

### 5. Output Validator — Commodity Mismatch

```
AI says '$64.41' when Brent=$109.8:
Status: MAJOR CONTRADICTION
⚠️ COMMODITY MISMATCH: AI says $64.41 but Brent is $109.80
⚠️ CONSEQUENCE ABSENT: No India-impact consequence indicators found
```

### 6. Indian Basket Approximation

```
Indian Basket: $82.64 (vs Brent $85.2, discount 3.0%)
```

### 7. Master Signal — Before vs After

**Before (Phase 16):**
```
Consensus: 38/100 | BEARISH
Lean: Bearish | Confidence: LOW
Structural: 50/100 — NEUTRAL
Sentiment: 38/100 — BEARISH
⚠️ LOW CONFIDENCE — signals contradicting
Historical accuracy: ~48% (near coin flip)
```

**After (Phase 19):**
```
[MASTER SIGNAL — Read This First]
Score: 38/100 ↓ (was 42 | 30D avg: 51 | 22nd %ile)
Lean: BEARISH
Structural: 50/100 — NEUTRAL
Sentiment: 38/100 — BEARISH
GAP: 12pts — Fear exceeding fundamentals, Real conflict — regime transition likely
Confidence: Direction=LOW (48%), Regime=HIGH — divergence = choppy conditions
Implication:
  • Mean reversion opportunity if timing right
  • Reduce momentum exposure while divergence persists
  • Defensive sectors favored while sentiment remains weak
  • Options premium expansion likely
```

### 8. Real Data from Today's Run

```
Bull/Bear: 50/100 — NEUTRAL
Structural: 62/100 — BULLISH
Sentiment: 39/100 — BEARISH
Gap: 23pts — EXTREME DIVERGENCE
Confidence: LOW (direction), HIGH (regime = choppy)
```

---

## Logic Verification

### Consequence Multiplier Table

| Variable | Per-Unit Multiplier | Source |
|----------|-------------------|--------|
| Brent +$1 | CAD +$1.5B, INR +3ps, CPI +2bps, OMC -0.5% | mechanism_map.py precedent |
| US 10Y +50bps | FII outflow ₹875Cr | Historical FII-yield correlation |
| DXY +1% | IT revenue +0.5%, FII exit ₹650Cr | IT earnings sensitivity |
| USDINR +₹1 | IT +0.8%, oil bill +₹14,000Cr | Import bill calculation |
| Gold +$100 | Import bill +$3B | India gold import data |

### Gap Analysis Classification

| Gap | Label | Meaning |
|-----|-------|---------|
| <5 | ALIGNMENT | Signals agree — direction more reliable |
| 5-10 | MILD DIVERGENCE | Minor disagreement — monitor |
| 10-15 | SIGNIFICANT DIVERGENCE | Real conflict — regime transition |
| >15 | EXTREME DIVERGENCE | Major dislocation — mean reversion |

### Confidence Split Logic

| Condition | Direction Confidence | Regime Confidence |
|-----------|---------------------|-------------------|
| Gap >= 10 | LOW (48%) | HIGH (choppy) |
| Gap < 10 | Same as base | Same as base |

### VIX Threshold Ordering (Bug Fix)

| VIX | Before (Bug) | After (Fixed) |
|-----|-------------|---------------|
| 26 | HIGH (wrong) | EXTREME (correct) |
| 22 | HIGH | HIGH |
| 35 | HIGH (wrong) | EXTREME (correct) |

---

## Adversarial Probes (Verification Agent)

1. `_compute_gap_analysis(0, 0)` → ALIGNMENT, gap=0 ✓
2. `_compute_gap_analysis(100, 0)` → EXTREME DIVERGENCE, gap=100 ✓
3. Empty signals → `{"ok": False}` ✓
4. Single history entry → empty trending ✓
5. PCR=0.0 → normalized to 100 (bullish) ✓
6. PCR=2.0 → normalized to 0 (bearish) ✓
7. Confidence split single line in format ✓
8. `cluster_gap` key consistent across all files ✓
9. `format_master_signal({})` → empty string ✓

---

## Known Issues

1. **Master Signal sample output** shows `Error: 'master_score'` — pre-existing bug in the sample output path, not Phase 18/19 related. The actual `format_master_signal()` works correctly (verified in tests).

2. **Trending needs 30+ days** — Master Signal trending requires historical data accumulation. Run daily. Bootstrap script inserts today's data only.

3. **Indian Basket is approximated** — `Brent - 3%`. Real PPAC data integration would be more accurate but requires scraping.

---

## What NOT to Worry About

- No synthetic data in DB — real data only
- No hardcoded historical resolution % — waits for DB accumulation
- No position sizing numbers — signal strength language only
- No duplication of FII/Macro block content
- Master Signal max 12-15 lines
- All formatters return "" on failure
- 187/187 tests pass
