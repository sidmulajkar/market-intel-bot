"""
adaptive_weights.py — P7.1 Dynamic Pillar Weighting
Sunday: Load signal_accuracy_log (365d), compute hit rate per pillar,
apply clamp [0.70, 1.30], upsert dynamic_weights JSONB to market_state.
"""
from datetime import datetime, timedelta
from typing import Dict, Optional


PILLAR_NAMES = [
    "STAGFLATION_SUPPLY",
    "WEST_ASIA",
    "EM_CONTAGION",
    "CARRY_UNWIND",
    "DE_DOLLARIZATION",
    "TECH_CYCLE_BURST",
]

WEIGHT_MIN = 0.70
WEIGHT_MAX = 1.30
LOOKBACK_DAYS = 365


def compute_pillar_weights(supabase=None) -> Dict[str, float]:
    """Compute dynamic weight multipliers for all 6 pillars.

    For each pillar, hit_rate = % of times pillar signal ≥ 40
    preceded a Nifty 5D drop > 1% within the lookback window.

    weight_multiplier = clamp(1.0 + (hit_rate - 0.50), 0.70, 1.30)
    """
    from src.db import get_client, get_signal_accuracy

    db = supabase or get_client()
    if not db:
        return _default_weights()

    accuracy = get_signal_accuracy(days=LOOKBACK_DAYS)
    if not accuracy:
        print("⚠️ No signal accuracy data — using default weights (1.0)")
        return _default_weights()

    weights = {}
    for pillar in PILLAR_NAMES:
        stats = accuracy.get(pillar)
        if stats and stats.get("total", 0) >= 5:
            hit_rate = stats["hit_rate"] / 100.0
            mult = 1.0 + (hit_rate - 0.50)
            mult = max(WEIGHT_MIN, min(WEIGHT_MAX, mult))
            weights[pillar] = round(mult, 3)
            print(f"  {pillar}: hit_rate={hit_rate:.1%} total={stats['total']} weight={mult:.3f}")
        else:
            weights[pillar] = 1.0
            count = stats["total"] if stats else 0
            print(f"  {pillar}: insufficient data ({count} samples) — weight=1.0")

    _persist_weights(weights, db)
    return weights


def get_dynamic_weights(supabase=None) -> Dict[str, float]:
    """Read dynamic_weights from market_state, returning default 1.0 if absent."""
    db = supabase
    if not db:
        from src.db import get_client
        db = get_client()
    if not db:
        return _default_weights()

    try:
        today = datetime.now().strftime("%Y-%m-%d")
        result = (
            db.table("market_state")
            .select("state")
            .eq("trade_date", today)
            .limit(1)
            .execute()
        )
        if result.data:
            state = result.data[0].get("state", {})
            if isinstance(state, dict):
                weights = state.get("dynamic_weights", {})
                if weights and isinstance(weights, dict):
                    return weights
    except Exception as e:
        print(f"⚠️ get_dynamic_weights error: {e}")

    # Fall back to manifest.json weights
    try:
        from src.manifest import load as _load_manifest
        m = _load_manifest()
        mw = m.get("adaptive_weights", {})
        if mw and isinstance(mw, dict) and any(v != 1.0 for v in mw.values()):
            return mw
    except Exception:
        pass

    return _default_weights()


def _default_weights() -> Dict[str, float]:
    return {p: 1.0 for p in PILLAR_NAMES}


def _persist_weights(weights: Dict[str, float], db) -> bool:
    """Upsert dynamic_weights into today's market_state."""
    if not db:
        return False
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        existing = (
            db.table("market_state")
            .select("state")
            .eq("trade_date", today)
            .limit(1)
            .execute()
        )
        if existing.data:
            state = existing.data[0].get("state", {})
            if not isinstance(state, dict):
                state = {}
        else:
            state = {}

        state["dynamic_weights"] = weights
        db.table("market_state").upsert({
            "trade_date": today,
            "state": state,
        }).execute()
        print(f"✅ Persisted dynamic_weights to market_state ({len(weights)} pillars)")
        return True
    except Exception as e:
        print(f"⚠️ _persist_weights error: {e}")
        return False
