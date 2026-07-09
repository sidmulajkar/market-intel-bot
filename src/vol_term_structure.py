"""
Volatility Term Structure — Jane Street Proxy

Measures the shape of the VIX curve using:
1. CBOE_VIX ('^VIX') — spot implied vol (30-day)
2. Ratio of current VIX to its 10D moving average — term structure proxy

When near-term vol spikes above its own recent average, the curve is
inverting (backwardation) = institutions aggressively pricing short-term risk.

Data source: anchor_history.csv and yfinance live fetch.
Total GHA cost: ~1.5 seconds (single yfinance call).
"""

import os
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import numpy as np


# Columns needed from anchor_history.csv
_VIX_COL = "CBOE_VIX"

# Term structure thresholds
_BACKWARDATION_RATIO = 1.10   # VIX > 110% of its 10D MA = backwardation
_CONTANGO_RATIO = 0.95        # VIX < 95% of its 10D MA = contango
_SHORT_WINDOW = 10            # Moving average window
_EMA_SPAN = 21                # For smoothing trend


def _load_vix_history(csv_path: Optional[str] = None) -> pd.DataFrame:
    """Load CBOE_VIX from anchor_history.csv.

    Returns DataFrame with date index and 'CBOE_VIX' column.
    """
    if csv_path is None:
        csv_path = str(
            Path(__file__).resolve().parent.parent / "data" / "anchor_history.csv"
        )
    if not os.path.exists(csv_path):
        return pd.DataFrame()

    df = pd.read_csv(csv_path)
    if _VIX_COL not in df.columns:
        return pd.DataFrame()

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        df = df.set_index("date").sort_index()

    df = df[[_VIX_COL]].dropna()
    return df.astype(float)


def compute_vol_term_structure(
    csv_path: Optional[str] = None,
) -> Dict:
    """Compute VIX term structure using CSV history + optional live yfinance fetch.

    Strategy:
    1. Load CBOE_VIX history from CSV (has ~5 years of daily data).
    2. Compute 10D SMA of VIX as 'near-term' baseline.
    3. Current VIX / 10D SMA = term structure ratio.
    4. Ratio > 1.10 = backwardation (panic pricing).
       Ratio < 0.95 = contango (complacent).
       In between = flat.

    Also fetches live VIX from yfinance for the most up-to-date print,
    and ^INDIAVIX for India-specific vol context.

    Returns:
        {
            "ok": True,
            "current_vix": 17.06,
            "ma_10_vix": 15.42,
            "ratio": 1.11,
            "state": "BACKWARDATION",
            "vix_change_1d": -0.3,
            "vix_ema_21": 16.80,
            "india_vix": 13.36,
            "india_vix_change_1d": 0.5,
        }
    """
    df = _load_vix_history(csv_path)
    if df.empty or len(df) < _SHORT_WINDOW + 5:
        return {"ok": False, "reason": f"insufficient VIX history ({len(df)} rows)"}

    # Compute moving averages
    vix_series = df[_VIX_COL]
    current_vix = float(vix_series.iloc[-1])
    ma_10 = float(vix_series.tail(_SHORT_WINDOW).mean())
    ema_21 = float(vix_series.tail(_EMA_SPAN).ewm(span=_EMA_SPAN).mean().iloc[-1])
    vix_1d_chg = float(vix_series.iloc[-1] - vix_series.iloc[-2]) if len(vix_series) >= 2 else 0.0

    ratio = current_vix / ma_10 if ma_10 > 0 else 1.0
    spread = current_vix - ma_10

    if ratio >= _BACKWARDATION_RATIO:
        state = "BACKWARDATION"
    elif ratio <= _CONTANGO_RATIO:
        state = "CONTANGO"
    else:
        state = "FLAT"

    # Try live yfinance fetch for India VIX
    india_vix = None
    india_vix_chg = None
    try:
        import yfinance as yf
        indiavix = yf.download("^INDIAVIX", period="5d", progress=False)["Close"]
        if not indiavix.empty:
            india_vix = float(indiavix.iloc[-1])
            india_vix_chg = float(indiavix.iloc[-1] - indiavix.iloc[-2]) if len(indiavix) >= 2 else 0.0
    except Exception:
        pass

    return {
        "ok": True,
        "current_vix": round(current_vix, 2),
        "ma_10_vix": round(ma_10, 2),
        "ratio": round(ratio, 3),
        "state": state,
        "spread": round(spread, 2),
        "vix_change_1d": round(vix_1d_chg, 2),
        "vix_ema_21": round(ema_21, 2),
        "india_vix": round(india_vix, 2) if india_vix is not None else None,
        "india_vix_change_1d": round(india_vix_chg, 2) if india_vix_chg is not None else None,
    }


def format_vol_term_structure(result: Dict) -> str:
    """Format VIX term structure for Telegram.

    Empty string when no data (format hygiene: silent suppression).
    """
    if not result.get("ok"):
        return ""

    state = result["state"]
    vix = result["current_vix"]
    ratio = result["ratio"]
    spread = result["spread"]

    if state == "FLAT" and abs(spread) < 0.5:
        return ""  # Suppress when flat and insignificant

    state_emoji = "📉" if state == "BACKWARDATION" else "📈" if state == "CONTANGO" else "➡️"
    state_label = state.title()

    lines = [
        f"📉 *Vol Term Structure* — US VIX {vix:.1f}",
        f"   {state_emoji} {state_label} | Ratio: {ratio:.2f} vs 10D avg",
    ]

    if state == "BACKWARDATION":
        lines.append("   Short-term protection aggressively priced. Event risk elevated.")
    elif state == "CONTANGO":
        lines.append("   Curve in contango — normal carry environment.")

    # India VIX context
    iv = result.get("india_vix")
    iv_chg = result.get("india_vix_change_1d")
    if iv is not None:
        iv_sign = "+" if iv_chg is not None and iv_chg >= 0 else ""
        iv_part = f"India VIX: {iv:.1f}"
        if iv_chg is not None:
            iv_part += f" ({iv_sign}{iv_chg:.1f})"
        lines.append(f"   {iv_part}")

    return "\n".join(lines)


def check_vol_term_structure_pre_event(result: Dict) -> str:
    """Check if VIX curve is inverted ahead of an upcoming event.

    Combines vol term structure state with upcoming economic calendar
    to produce a pre-event signal line.

    Returns empty string if no inversion or no event (format hygiene).
    """
    if not result.get("ok") or result.get("state") != "BACKWARDATION":
        return ""

    try:
        from src.event_volatility import scan_upcoming_events
        from datetime import datetime

        upcoming = scan_upcoming_events(days_ahead=2)
        if not upcoming:
            return ""

        nearest = upcoming[0]
        evt_date = datetime.strptime(nearest["event_date"], "%Y-%m-%d")
        days_away = (evt_date - datetime.now()).days
        label = nearest["event_label"]
        vix = result.get("current_vix", 0)
        ratio = result.get("ratio", 1.0)

        return (
            f"📡 *Pre-Event Vol Signal:* VIX curve inverted ({vix:.1f}, "
            f"ratio {ratio:.2f}) ahead of {label} (T+{days_away}). "
            f"Short-dated options pricing in tail risk — smart money hedged."
        )
    except Exception:
        return ""
