"""
sector_rotation_map.py — P7.2 Regime Rotation Map (GHA Edition)
Sunday pre-compute: load pillar_metrics + sector_rs history, bin pillar scores ±10,
find historical sector tilts, store as JSONB lookup table.

Weekday read: at 15:30 EOD, if Fragility > 50, lookup active pillars' historical tilts.
Output: "Historical Tilt: IT (+0.4σ), Pharma (+0.2σ) | Lagged: O&G (-0.6σ), PSU Banks (-0.5σ)"
"""
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple


PILLAR_NAMES = [
    "STAGFLATION_SUPPLY",
    "WEST_ASIA",
    "EM_CONTAGION",
    "CARRY_UNWIND",
    "DE_DOLLARIZATION",
    "TECH_CYCLE_BURST",
]


def compute_sector_tilt_map(supabase=None) -> Dict[str, Dict]:
    """Pre-compute historical sector tilts for each pillar.

    Reads pillar_metrics history + sector_rs from CSV/Supabase.
    For each pillar score ±10 bin, finds median sector RS.
    Stores as JSONB: {pillar_name: {"bullish": [sector,...], "bearish": [sector,...]}}

    Falls back to empty map if historical data insufficient.
    """
    from src.db import get_client
    db = supabase or get_client()
    if not db:
        return {}

    pillar_history = _load_pillar_history(db)
    sector_history = _load_sector_rs_history(db)

    if pillar_history.empty or sector_history.empty:
        print("⚠️ Insufficient historical data for sector rotation map")
        return {}

    tilt_map = {}
    for pillar in PILLAR_NAMES:
        tilts = _compute_tilts_for_pillar(pillar, pillar_history, sector_history)
        if tilts:
            tilt_map[pillar] = tilts

    _persist_tilt_map(tilt_map, db)
    return tilt_map


def get_sector_tilt_map(supabase=None) -> Dict[str, Dict]:
    """Read sector_tilt_map from today's market_state."""
    from src.db import get_client
    db = supabase or get_client()
    if not db:
        return {}
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
                tilt_map = state.get("sector_tilt_map", {})
                if tilt_map and isinstance(tilt_map, dict):
                    return tilt_map
    except Exception as e:
        print(f"⚠️ get_sector_tilt_map error: {e}")
    return {}


def format_rotation_map(active_pillar_names: List[str], fragility_score: float = None,
                        supabase=None) -> str:
    """Format sector rotation map block for 15:30 EOD.

    Only shown when Fragility > 50.
    """
    if fragility_score is not None and fragility_score <= 50:
        return ""

    tilt_map = get_sector_tilt_map(supabase)
    if not tilt_map:
        return "📈 *SECTOR ROTATION MAP:* Data pending (Sunday backfill required)."

    lines = []
    for name in active_pillar_names:
        if name not in tilt_map:
            continue
        tilts = tilt_map[name]
        bullish = tilts.get("bullish", [])
        bearish = tilts.get("bearish", [])
        if not bullish and not bearish:
            continue

        label = _pillar_label(name)
        parts = []
        if bullish:
            parts.append(f"Outperform: {', '.join(bullish)}")
        if bearish:
            parts.append(f"Lagged: {', '.join(bearish)}")
        if parts:
            lines.append(f"📊 *{label}:* {' | '.join(parts)}")

    if not lines:
        return ""

    header = "📈 *SECTOR ROTATION MAP*"
    return header + "\n" + "\n".join(lines)


def _load_pillar_history(db) -> pd.DataFrame:
    """Load pillar_metrics history from Supabase (last 5 years)."""
    try:
        result = (
            db.table("pillar_metrics")
            .select("date, pillar_name, pillar_score")
            .gte("date", (datetime.now() - pd.Timedelta(days=1825)).strftime("%Y-%m-%d"))
            .execute()
        )
        if result.data:
            df = pd.DataFrame(result.data)
            df["pillar_score"] = pd.to_numeric(df["pillar_score"], errors="coerce")
            return df.dropna(subset=["pillar_score"])
    except Exception as e:
        print(f"⚠️ _load_pillar_history: {e}")
    return pd.DataFrame()


def _load_sector_rs_history(db) -> pd.DataFrame:
    """Load sector_rs history from Supabase (last 5 years)."""
    try:
        result = (
            db.table("sector_rs")
            .select("date, sector_name, rs_score")
            .gte("date", (datetime.now() - pd.Timedelta(days=1825)).strftime("%Y-%m-%d"))
            .execute()
        )
        if result.data:
            df = pd.DataFrame(result.data)
            df["rs_score"] = pd.to_numeric(df["rs_score"], errors="coerce")
            return df.dropna(subset=["rs_score"])
    except Exception as e:
        print(f"⚠️ _load_sector_rs_history: {e}")
    return pd.DataFrame()


def _compute_tilts_for_pillar(pillar: str, pillar_history: pd.DataFrame,
                               sector_history: pd.DataFrame) -> Dict:
    """Compute top/bottom sectors for a single pillar's active regimes."""
    try:
        active = pillar_history[
            (pillar_history["pillar_name"] == pillar) &
            (pillar_history["pillar_score"] >= 40)
        ]
        if active.empty:
            return {}

        active_dates = active["date"].unique()
        sector_on_dates = sector_history[sector_history["date"].isin(active_dates)]

        if sector_on_dates.empty:
            return {}

        sector_means = (
            sector_on_dates.groupby("sector_name")["rs_score"]
            .mean()
            .sort_values(ascending=False)
        )

        if sector_means.empty:
            return {}

        top = sector_means.head(2)
        bottom = sector_means.tail(2)

        bullish = [f"{idx} ({val:+.1f}σ)" for idx, val in top.items()]
        bearish = [f"{idx} ({val:+.1f}σ)" for idx, val in bottom.items()]

        return {"bullish": bullish, "bearish": bearish}
    except Exception as e:
        print(f"⚠️ _compute_tilts_for_pillar: {e}")
        return {}


def _persist_tilt_map(tilt_map: Dict, db) -> bool:
    """Store tilt_map in today's market_state JSONB."""
    if not tilt_map:
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

        state["sector_tilt_map"] = tilt_map
        db.table("market_state").upsert({
            "trade_date": today,
            "state": state,
        }).execute()
        print(f"✅ Persisted sector_tilt_map ({len(tilt_map)} pillars)")
        return True
    except Exception as e:
        print(f"⚠️ _persist_tilt_map: {e}")
        return False


def _pillar_label(name: str) -> str:
    labels = {
        "STAGFLATION_SUPPLY": "Stagflation",
        "WEST_ASIA": "West Asia",
        "EM_CONTAGION": "EM Contagion",
        "CARRY_UNWIND": "Carry Unwind",
        "DE_DOLLARIZATION": "De-dollarization",
        "TECH_CYCLE_BURST": "Tech Cycle",
    }
    return labels.get(name, name)
