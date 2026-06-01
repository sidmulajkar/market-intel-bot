"""
Pillar Classifier — 6 structural macro pillars for India market regime.
Replaces 5 legacy naive-scenario thresholds with percentile-based scoring.

Core principle: threshold-gated, weight-normalized scoring.
Dimensions contribute only when past their activation threshold.
Normalized by total weight (not active weight) → requires breadth.

Data sources (8/12 from CSV, 4/12 bootstrap):
  CSV stable: DXY, US10Y, Credit(HYG/LQD), Brent, Cu/Au, Gold, USDINR, IndiaVIX
  Bootstrap:  FII 5D, Carry(IND-US), PCR, Skew (added as data accumulates)
"""

import numpy as np
from typing import Dict, List, Optional, Tuple

# ── Pillar Dimension Weights ──
# Each dimension: (weight, direction, threshold_0_100)
# direction="stress": scores when percentile > threshold
# direction="relief": scores when percentile < threshold

PILLAR_DEFINITIONS = {
    "STAGFLATION_SUPPLY": {
        "label": "Stagflation & Supply Shock",
        "emoji": "🏭",
        "dimensions": {
            "Brent":         (0.25, "stress", 55),
            "USDINR":        (0.20, "stress", 60),
            "Cu_Au_Ratio":   (0.15, "relief", 30),
            "US10Y":         (0.15, "stress", 65),
            "Gold":          (0.10, "stress", 50),
            "IndiaVIX":      (0.15, "stress", 55),
        },
    },
    "WEST_ASIA": {
        "label": "West Asia Energy Crisis",
        "emoji": "🛢️",
        "dimensions": {
            "Brent":         (0.30, "stress", 65),
            "CBOE_VIX":      (0.25, "stress", 60),
            "Gold":          (0.20, "stress", 75),
            "USDINR":        (0.15, "stress", 70),
            "DXY":           (0.10, "stress", 50),
        },
    },
    "EM_CONTAGION": {
        "label": "EM Contagion & Carry Unwind",
        "emoji": "🌊",
        "dimensions": {
            "DXY":           (0.25, "stress", 70),
            "USDINR":        (0.20, "stress", 70),
            "Cu_Au_Ratio":   (0.15, "relief", 40),
            "Gold":          (0.15, "stress", 60),
            "IndiaVIX":      (0.15, "stress", 60),
            "Credit_Ratio":  (0.10, "relief", 40),
        },
    },
    "CARRY_UNWIND": {
        "label": "Carry Trade Unwind",
        "emoji": "💱",
        "dimensions": {
            "DXY":           (0.30, "stress", 80),
            "USDINR":        (0.25, "stress", 70),
            "Gold":          (0.20, "stress", 70),
            "US10Y":         (0.15, "stress", 80),
            "IndiaVIX":      (0.10, "stress", 70),
        },
    },
    "DE_DOLLARIZATION": {
        "label": "De-Dollarization & Fragmentation",
        "emoji": "🌐",
        "dimensions": {
            "DXY":           (0.25, "relief", 40),
            "Gold":          (0.25, "stress", 80),
            "USDINR":        (0.20, "relief", 40),
            "US10Y":         (0.15, "relief", 40),
            "Brent":         (0.15, "stress", 55),
        },
    },
    "TECH_CYCLE_BURST": {
        "label": "Tech Cycle & Credit Lock",
        "emoji": "💻",
        "dimensions": {
            "SOXX_NQ_Ratio": (0.25, "relief", 40),
            "IndiaVIX":      (0.25, "stress", 70),
            "Gold":          (0.15, "stress", 65),
            "Credit_Ratio":  (0.20, "relief", 40),
            "DXY":           (0.15, "stress", 50),
        },
    },
}

# 12D vector column names (for CSV column lookup + percentile computation)
VECTOR_FIELDS = [
    "DXY", "US10Y", "Brent", "Gold", "USDINR", "IndiaVIX",
    "CBOE_VIX", "Credit_Ratio", "Cu_Au_Ratio", "SOXX_NQ_Ratio",
]

# Bootstrap dims (added as data accumulates)
BOOTSTRAP_FIELDS = ["FII_5D", "Carry", "PCR", "Skew"]


def compute_pillar_score(
    current_pctiles: Dict[str, float],
    dimensions: Dict[str, Tuple[float, str, float]],
) -> Tuple[float, List[Dict]]:
    """Score a single pillar on 0-100 scale.

    Args:
        current_pctiles: {dim_name: percentile_0_100} for current market state
        dimensions: {dim_name: (weight, direction, threshold)}

    Returns:
        (score_0_100, active_dimensions_list)
    """
    total_weighted = 0.0
    total_weight = 0.0
    active_dims = []

    for dim_name, (weight, direction, threshold) in dimensions.items():
        current_val = current_pctiles.get(dim_name)
        total_weight += weight

        if current_val is None:
            continue

        if direction == "stress" and current_val >= threshold:
            intensity = min(1.0, (current_val - threshold) / (100.0 - threshold))
            contribution = intensity * weight
            total_weighted += contribution
            active_dims.append({
                "name": dim_name,
                "value_pctile": current_val,
                "contribution": round(contribution, 4),
                "direction": direction,
            })

        elif direction == "relief" and current_val <= threshold:
            intensity = (threshold - current_val) / threshold
            contribution = intensity * weight
            total_weighted += contribution
            active_dims.append({
                "name": dim_name,
                "value_pctile": current_val,
                "contribution": round(contribution, 4),
                "direction": direction,
            })

    score = min(100.0, (total_weighted / max(total_weight, 0.001)) * 100)
    return score, active_dims


def _resolve_tier(score: float) -> str:
    if score >= 80:
        return "STRESS"
    if score >= 60:
        return "ELEVATED"
    if score >= 40:
        return "ACTIVE"
    if score >= 20:
        return "MONITORED"
    return "INACTIVE"


def classify_pillars(
    current_pctiles: Dict[str, float],
    pillar_overrides: Optional[Dict] = None,
) -> List[Dict]:
    """Classify current market into active structural pillars.

    Args:
        current_pctiles: {dim_name: percentile_0_100} for today
        pillar_overrides: Optional dynamic thresholds (from calibration)

    Returns:
        List of pillar dicts sorted by score descending:
        [{"name", "label", "emoji", "score", "tier", "active_dims"}] 
        Only pillars with score >= 20 (MONITORED+) are returned.
    """
    definitions = PILLAR_DEFINITIONS
    if pillar_overrides:
        for name, overrides in pillar_overrides.items():
            if name in definitions:
                definitions[name]["dimensions"] = overrides

    results = []
    for pillar_name, config in definitions.items():
        score, active_dims = compute_pillar_score(
            current_pctiles, config["dimensions"]
        )
        tier = _resolve_tier(score)
        if tier == "INACTIVE":
            continue

        results.append({
            "name": pillar_name,
            "label": config["label"],
            "emoji": config["emoji"],
            "score": round(score, 1),
            "tier": tier,
            "active_dims": active_dims,
        })

    results.sort(key=lambda x: -x["score"])
    return results


def get_percentiles_from_csv(trade_date: str = None) -> Dict[str, float]:
    """Compute expanding percentiles from CSV data for all pillar dims.

    Falls back to last valid row if trade_date is None or weekend.
    Returns {dim_name: percentile_0_100}.
    """
    import pandas as pd
    from src.csv_data import load_history

    df = load_history("anchors")
    if df.empty:
        return {}

    # Compute derived ratios on the full history
    if "HYG" in df.columns and "LQD" in df.columns:
        df["Credit_Ratio"] = df["HYG"] / df["LQD"]
    if "SOXX" in df.columns and "NASDAQ" in df.columns:
        df["SOXX_NQ_Ratio"] = df["SOXX"] / df["NASDAQ"]

    # All dimensions we can compute
    all_dims = VECTOR_FIELDS + BOOTSTRAP_FIELDS

    # Compute expanding percentiles for available dims
    for col in all_dims:
        if col in df.columns:
            df[f"{col}_pctile"] = df[col].expanding().rank(pct=True)

    # Find target row
    if trade_date:
        matching = df[df.index == trade_date]
        if matching.empty:
            return {}
        row = matching.iloc[0]
    else:
        # Last valid row
        idx = df["USDINR"].last_valid_index()
        if idx is None:
            return {}
        row = df.loc[idx]

    # Extract percentiles
    result = {}
    for col in all_dims:
        pcol = f"{col}_pctile"
        if pcol in df.columns:
            val = row.get(pcol)
            if val is not None and not (isinstance(val, float) and np.isnan(val)):
                result[col] = val * 100  # Convert 0-1 to 0-100

    return result


def format_pillar_output(active_pillars: List[Dict], max_pillars: int = 2) -> str:
    """Format active pillars for Telegram output.
    
    Shows max 2 pillars (top rank) with emoji + score + active dimensions.
    """
    if not active_pillars:
        return ""

    lines = []
    for p in active_pillars[:max_pillars]:
        tier_emoji = {"STRESS": "🔴", "ELEVATED": "🟠", "ACTIVE": "🟡", "MONITORED": "🟢"}
        emoji = tier_emoji.get(p["tier"], "⚪")
        lines.append(f"{p['emoji']} *{p['label']}* — {p['tier']} ({p['score']:.0f}/100)")

        # Show active dimensions that contribute meaningfully
        meaningful = [d for d in p["active_dims"] if d["contribution"] >= 0.01]
        if meaningful:
            dims_str = ", ".join(
                f"{d['name']} {d['value_pctile']:.0f}p{'↑' if d['direction'] == 'stress' else '↓'}"
                for d in meaningful[:5]
            )
            lines.append(f"  🔴 Detection: {dims_str}")

    return "\n".join(lines)


def get_current_pillar_scores() -> Dict:
    """One-shot: returns active pillars + pctile vector for today.
    
    Used by Saturday simulation and ad-hoc diagnostics.
    """
    pctiles = get_percentiles_from_csv()
    if not pctiles:
        return {"ok": False, "pillars": [], "pctiles": {}}

    pillars = classify_pillars(pctiles)
    return {
        "ok": True,
        "pillars": pillars,
        "pctiles": pctiles,
        "fingerprint": " | ".join(
            f"{p['label']}:{p['score']:.0f}" for p in pillars[:3]
        ),
    }
