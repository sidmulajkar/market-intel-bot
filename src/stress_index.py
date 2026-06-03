"""
Composite Stress Index (T4.1)
Z-score weighted composite of VIX, FII velocity, USDINR, Brent, Put-Call Skew, A/D.
Output: 0-100 stress score → top banner line in 07:00/12:30/18:00 reports.
"""
from typing import Dict, Optional, List, Tuple
from statistics import mean, stdev
from datetime import datetime, timedelta

WEIGHTS = {
    "vix": 0.25,
    "fii": 0.25,
    "usdinr": 0.15,
    "brent": 0.15,
    "skew": 0.10,
    "breadth": 0.10,
}

Z_TO_SCORE_MULTIPLIER = 12
Z_TO_SCORE_OFFSET = 50

SEVERITY_LABELS = [
    (80, "EXTREME"),
    (65, "ELEVATED"),
    (50, "MODERATE"),
    (35, "LOW"),
    (0,  "QUIET"),
]


def compute_stress_index(days: int = 252) -> Dict:
    """Compute composite stress index from 252-day historical Z-scores."""
    z_scores = {}
    contributions = {}

    vix_z = _compute_macro_z("^INDIAVIX", days, invert=False)
    if vix_z is not None:
        z_scores["vix"] = vix_z
        contributions["vix"] = vix_z * WEIGHTS["vix"]

    fii_z = _compute_fii_z(days)
    if fii_z is not None:
        z_scores["fii"] = fii_z
        contributions["fii"] = fii_z * WEIGHTS["fii"]

    usdinr_z = _compute_macro_z("USDINR=X", days, invert=False)
    if usdinr_z is not None:
        z_scores["usdinr"] = usdinr_z
        contributions["usdinr"] = usdinr_z * WEIGHTS["usdinr"]

    brent_z = _compute_macro_z("BZ=F", days, invert=False)
    if brent_z is not None:
        z_scores["brent"] = brent_z
        contributions["brent"] = brent_z * WEIGHTS["brent"]

    skew_z = _compute_skew_z(days)
    if skew_z is not None:
        z_scores["skew"] = skew_z
        contributions["skew"] = skew_z * WEIGHTS["skew"]

    breadth_z = _compute_breadth_z(days)
    if breadth_z is not None:
        z_scores["breadth"] = breadth_z
        contributions["breadth"] = breadth_z * WEIGHTS["breadth"]

    if not z_scores:
        return {"ok": False, "message": "No data for any stress component"}

    raw_stress = sum(contributions.values())
    effective_weight = sum(WEIGHTS[k] for k in z_scores)
    if effective_weight > 0:
        raw_stress = raw_stress * (1.0 / effective_weight)

    stress_score = max(0, min(100, (raw_stress * Z_TO_SCORE_MULTIPLIER) + Z_TO_SCORE_OFFSET))

    sorted_drivers = sorted(contributions.items(), key=lambda x: x[1], reverse=True)
    top_drivers = [k for k, v in sorted_drivers if v > 0][:2]

    severity = _score_to_severity(stress_score)

    return {
        "ok": True,
        "stress_score": round(stress_score, 1),
        "raw_stress": round(raw_stress, 3),
        "severity": severity,
        "top_drivers": top_drivers,
        "components": {k: round(v, 2) for k, v in z_scores.items()},
        "contributions": {k: round(v, 3) for k, v in contributions.items()},
    }


def _compute_macro_z(symbol: str, days: int, invert: bool = False) -> Optional[float]:
    """Compute Z-score for a macro anchor. invert=True flips sign (e.g. A/D)."""
    try:
        from src.csv_data import get_anchor_history
        rows = get_anchor_history(symbol, days=days)
        prices = [r["price"] for r in rows if r.get("price") is not None]
        if len(prices) < 20:
            return None
        mu = mean(prices)
        sd = stdev(prices)
        if sd == 0:
            return None
        z = (prices[-1] - mu) / sd
        return -z if invert else z
    except Exception:
        return None


def _compute_fii_z(days: int) -> Optional[float]:
    """Compute Z-score for FII net flow (5D cumulative). Negative FII = stress."""
    try:
        from src.csv_data import get_fii_dii_history
        df = get_fii_dii_history(days=days)
        if "FII_Net_Cr" not in df.columns:
            return None
        vals = df["FII_Net_Cr"].dropna().tolist()
        if len(vals) < 20:
            return None
        mu = mean(vals)
        sd = stdev(vals)
        if sd == 0:
            return None
        z = (vals[-1] - mu) / sd
        return -z
    except Exception:
        return None


def _compute_skew_z(days: int) -> Optional[float]:
    """Compute Z-score for put-call skew from options snapshots."""
    try:
        from src.db import get_client
        db = get_client()
        if not db:
            return None
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        result = db.table("options_snapshots").select("snapshot_date, skew_25d").gte("snapshot_date", cutoff).order("snapshot_date").execute()
        rows = result.data or []
        vals = [r["skew_25d"] for r in rows if r.get("skew_25d") is not None]
        if len(vals) < 20:
            return None
        mu = mean(vals)
        sd = stdev(vals)
        if sd == 0:
            return None
        return (vals[-1] - mu) / sd
    except Exception:
        return None


def _compute_breadth_z(days: int) -> Optional[float]:
    """Compute Z-score for A/D ratio. Low A/D = stress so invert=True."""
    try:
        from src.db import get_breadth_history
        rows = get_breadth_history(days=days)
        ratios = [r["ratio"] for r in rows if r.get("ratio") is not None]
        if len(ratios) < 20:
            return None
        mu = mean(ratios)
        sd = stdev(ratios)
        if sd == 0:
            return None
        z = (ratios[-1] - mu) / sd
        return -z
    except Exception:
        return None


def _score_to_severity(score: float) -> str:
    """Map 0-100 score to severity label."""
    for threshold, label in SEVERITY_LABELS:
        if score >= threshold:
            return label
    return "QUIET"


def format_stress_banner(stress: Dict) -> str:
    """Format stress index as compact one-line banner."""
    if not stress.get("ok"):
        return ""
    score = stress["stress_score"]
    severity = stress["severity"]
    drivers = stress.get("top_drivers", [])
    driver_labels = {
        "vix": "VIX", "fii": "FII Velocity", "usdinr": "USDINR",
        "brent": "Brent", "skew": "Put-Call Skew", "breadth": "A/D Breadth",
    }
    driver_str = ", ".join(driver_labels.get(d, d) for d in drivers) if drivers else "none"
    return f"⚡ Stress Index: {severity} ({score:.0f}/100) | Drivers: {driver_str}"


def save_stress_index(stress: Dict, trade_date: Optional[str] = None) -> bool:
    """Persist stress index to Supabase stress_history table."""
    if not stress.get("ok"):
        return False
    try:
        from supabase import create_client
        from src.db import get_client
        db = get_client()
        if not db:
            return False
        td = trade_date or datetime.now().strftime("%Y-%m-%d")
        record = {
            "trade_date": td,
            "stress_score": stress["stress_score"],
            "raw_stress": stress.get("raw_stress"),
            "top_driver_1": stress["top_drivers"][0] if stress.get("top_drivers") else None,
            "top_driver_2": stress["top_drivers"][1] if len(stress.get("top_drivers", [])) > 1 else None,
        }
        db.table("stress_history").upsert(record, on_conflict="trade_date").execute()
        return True
    except Exception as e:
        print(f"⚠️ Save stress: {e}")
        return False


def get_stress_history(days: int = 5) -> list:
    """Get recent stress scores for regime arbiter 2-day check."""
    try:
        from src.db import get_client
        db = get_client()
        if not db:
            return []
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        result = db.table("stress_history").select("trade_date, stress_score").gte("trade_date", cutoff).order("trade_date").execute()
        return result.data or []
    except Exception:
        return []
