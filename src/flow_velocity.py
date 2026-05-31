"""
Flow Velocity Module (T2.1)
Compares short-term (5D) vs medium-term (21D) FII/DII rolling averages.
Detects acceleration/deceleration via Z-score analysis.
"""
from typing import Dict, Optional, List
from statistics import stdev, mean


def compute_flow_velocity(days: int = 25) -> Dict:
    """Compute FII/DII flow velocity metrics."""
    from src.db import get_fii_dii_flows

    rows = get_fii_dii_flows(days=days)
    if not rows or len(rows) < 10:
        return {"ok": False, "message": f"Only {len(rows)} flow rows (need 10)"}

    fii_vals = [r.get("fiinet_cr", 0) or 0 for r in rows]
    dii_vals = [r.get("diinet_cr", 0) or 0 for r in rows]

    # Rolling averages
    fii_5d = _rolling_avg(fii_vals, 5)
    fii_21d = _rolling_avg(fii_vals, 21)
    dii_5d = _rolling_avg(dii_vals, 5)
    dii_21d = _rolling_avg(dii_vals, 21)

    # Latest values (most recent = last in list)
    fii_5d_val = round(fii_5d[-1], 0) if len(fii_5d) >= 1 else 0
    fii_21d_val = round(fii_21d[-1], 0) if len(fii_21d) >= 1 else 0
    dii_5d_val = round(dii_5d[-1], 0) if len(dii_5d) >= 1 else 0
    dii_21d_val = round(dii_21d[-1], 0) if len(dii_21d) >= 1 else 0

    # Z-score: (5D - 21D) / std(21D)
    fii_z = _z_score(fii_vals[-21:], fii_5d_val) if len(fii_vals) >= 21 else 0
    dii_z = _z_score(dii_vals[-21:], dii_5d_val) if len(dii_vals) >= 21 else 0

    # Labels
    fii_label = _velocity_label(fii_z)
    dii_label = _velocity_label(dii_z)

    # DII floor ratio: DII 21D avg / |FII 21D avg|
    dii_floor_ratio = None
    if abs(fii_21d_val) > 50:
        dii_floor_ratio = round(abs(dii_21d_val / fii_21d_val), 2)

    return {
        "ok": True,
        "fii_5d": fii_5d_val,
        "fii_21d": fii_21d_val,
        "fii_z": round(fii_z, 2),
        "fii_velocity": fii_label,
        "dii_5d": dii_5d_val,
        "dii_21d": dii_21d_val,
        "dii_z": round(dii_z, 2),
        "dii_velocity": dii_label,
        "dii_floor_ratio": dii_floor_ratio,
    }


def _rolling_avg(values: List[float], window: int) -> List[float]:
    if len(values) < window:
        return []
    return [mean(values[i - window:i]) for i in range(window, len(values) + 1)]


def _z_score(population: List[float], value: float) -> float:
    if len(population) < 3:
        return 0.0
    mu = mean(population)
    sd = stdev(population)
    if sd == 0:
        return 0.0
    return (value - mu) / sd


def _velocity_label(z: float) -> str:
    if z > 1.5:
        return "ACCEL"
    if z < -1.5:
        return "DECEL"
    return "NEUTRAL"


def format_flow_velocity(velocity: Dict) -> str:
    """Format flow velocity into a dense one-liner."""
    if not velocity.get("ok"):
        return ""

    parts = []
    fii_5d = velocity["fii_5d"]
    fii_21d = velocity["fii_21d"]
    fii_v = velocity["fii_velocity"]
    dii_5d = velocity["dii_5d"]
    dii_21d = velocity["dii_21d"]
    dii_v = velocity["dii_velocity"]

    fii_line = f"FII ₹{fii_21d:,.0f}Cr (5D: ₹{fii_5d:,.0f}Cr"
    if fii_v != "NEUTRAL":
        fii_line += f" ⚡{fii_v}"
    fii_line += ")"
    parts.append(fii_line)

    dii_line = f"DII ₹{dii_21d:,.0f}Cr (5D: ₹{dii_5d:,.0f}Cr"
    if dii_v != "NEUTRAL":
        dii_line += f" ⚡{dii_v}"
    dii_line += ")"
    parts.append(dii_line)

    ratio = velocity.get("dii_floor_ratio")
    if ratio is not None:
        parts.append(f"Floor: {ratio}x")

    return "📊 Flow Velocity: " + " | ".join(parts)
