"""
Correlation Regime Clamp — Systemic Risk Radar

Detects when rolling correlations between macro anchors converge toward
+1.0 or -1.0, signalling systemic contagion / regime change.

References: Renaissance-style cross-asset correlation analysis.
Bridgewater "all-weather" regime detection using rolling correlation deltas.

Data source: anchor_history.csv (1,304 rows, 24 columns, daily)
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np


# Default pairs to monitor — the systemic risk nodes
_MONITORED_PAIRS: List[Tuple[str, str]] = [
    ("Brent", "DXY"),       # Commodity vs Dollar — decoupling = stress
    ("Brent", "USDINR"),    # Oil vs INR — normal negative, clamp positive = panic
    ("USDINR", "DXY"),      # INR vs Dollar — normally high positive
    ("CBOE_VIX", "DXY"),    # Fear vs Dollar — flight to safety
    ("US10Y", "CBOE_VIX"),  # Bonds vs Vol — risk-off inversion
    ("US10Y", "USDINR"),    # Rates vs INR — EM debt stress
]

# Columns expected in the CSV
_CSV_COLS = ["Brent", "DXY", "USDINR", "IndiaVIX", "US10Y", "CBOE_VIX"]

# Thresholds
_CLAMP_DELTA_MIN = 0.30       # Minimum absolute change in correlation
_CLAMP_ABS_MIN = 0.60         # Minimum absolute current correlation
_BASELINE_WINDOW = 90         # Long window for baseline
_SHORT_WINDOW = 20            # Short window for current readings
_MIN_ROWS = _BASELINE_WINDOW  # Minimum rows needed


def _load_csv(csv_path: Optional[str] = None) -> pd.DataFrame:
    """Load anchor_history.csv and return price DataFrame with date index."""
    if csv_path is None:
        csv_path = str(
            Path(__file__).resolve().parent.parent / "data" / "anchor_history.csv"
        )
    if not os.path.exists(csv_path):
        return pd.DataFrame()

    df = pd.read_csv(csv_path)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        df = df.set_index("date").sort_index()

    # Select only columns we need
    avail = [c for c in _CSV_COLS if c in df.columns]
    if not avail:
        return pd.DataFrame()

    df = df[avail].dropna(how="all")
    return df.astype(float)


def compute_correlation_clamp(
    csv_path: Optional[str] = None,
) -> Dict:
    """Compute rolling 20D vs 90D correlation matrix and detect clamps.

    Returns:
        {"ok": True, "clamps": [...], "matrix_20d": {...}, "matrix_90d": {...}}

    Each clamp entry:
        {"pair": "Brent/DXY", "r20": 0.85, "r90": 0.42,
         "delta": 0.43, "direction": "positive",
         "severity": "MODERATE"|"HIGH"|"CRITICAL"}
    """
    df = _load_csv(csv_path)
    if df.empty or len(df) < _MIN_ROWS:
        return {"ok": False, "reason": f"insufficient data ({len(df)} rows)"}

    prices = df.dropna(how="any")
    if len(prices) < _MIN_ROWS:
        return {"ok": False, "reason": f"insufficient clean rows ({len(prices)})"}

    corr_20 = prices.tail(_SHORT_WINDOW).corr()
    corr_90 = prices.tail(_BASELINE_WINDOW).corr()

    clamps: List[Dict] = []
    for col1, col2 in _MONITORED_PAIRS:
        if col1 not in prices.columns or col2 not in prices.columns:
            continue

        r20 = corr_20.loc[col1, col2]
        r90 = corr_90.loc[col1, col2]
        delta = abs(r20 - r90)

        if delta >= _CLAMP_DELTA_MIN and abs(r20) >= _CLAMP_ABS_MIN:
            direction = "positive" if r20 > 0 else "negative"
            severity = (
                "CRITICAL"
                if delta >= 0.60 and abs(r20) >= 0.85
                else "HIGH"
                if delta >= 0.45
                else "MODERATE"
            )
            clamps.append({
                "pair": f"{col1}/{col2}",
                "r20": round(r20, 3),
                "r90": round(r90, 3),
                "delta": round(delta, 3),
                "direction": direction,
                "severity": severity,
            })

    # Sort by severity
    _ORDER = {"CRITICAL": 0, "HIGH": 1, "MODERATE": 2}
    clamps.sort(key=lambda c: _ORDER.get(c["severity"], 99))

    return {
        "ok": True,
        "clamps": clamps,
        "matrix_20d": corr_20.to_dict(),
        "matrix_90d": corr_90.to_dict(),
    }


def format_correlation_clamp(result: Dict) -> str:
    """Format clamp output for Telegram.

    Empty string when no clamps detected (format hygiene: silent suppression).
    """
    if not result.get("ok") or not result.get("clamps"):
        return ""

    lines = []
    for c in result["clamps"][:2]:  # Top 2 most severe
        pair = c["pair"]
        r20 = c["r20"]
        delta = c["delta"]
        direction = c["direction"]
        severity = c["severity"]

        emoji = "🩻" if severity == "CRITICAL" else "🔬"
        sign = "+" if r20 >= 0 else ""
        norm_label = "Lockstep" if direction == "positive" else "Inverse clamp"

        lines.append(
            f"{emoji} *Correlation Clamp:* {pair}"
            f"\n   20D r={sign}{r20:.2f} | shift of {delta:.2f} vs 90D avg"
            f"\n   {norm_label} ({severity})"
        )

    if lines:
        return "🩻 *Systemic Risk Radar*\n━━━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines)
    return ""
