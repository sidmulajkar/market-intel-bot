"""
Drawdown Anatomy — Nifty 1Y drawdown analysis.
Computes current drawdown %, velocity, and historical recovery time.
Zero AI — purely deterministic Python.
"""
import yfinance as yf
import numpy as np
from typing import Dict, Optional

NIFTY_SYMBOL = "^NSEI"


def _compute_drawdown_series(prices):
    """Compute drawdown series from peak."""
    peak = np.maximum.accumulate(prices)
    dd = (prices - peak) / peak * 100
    return dd


def _find_drawdowns(prices):
    """Find distinct drawdown episodes: each starts at a peak and ends when a new peak is reached.
    Returns list of {"start_idx", "end_idx", "low_idx", "max_dd", "recovery_sessions"}.
    """
    peak_idx = 0
    low_idx = 0
    in_dd = False
    drawdowns = []

    for i in range(1, len(prices)):
        if prices[i] >= prices[peak_idx]:
            if in_dd:
                drawdowns.append({
                    "start_idx": peak_idx,
                    "end_idx": i,
                    "low_idx": low_idx,
                    "max_dd": (prices[low_idx] - prices[peak_idx]) / prices[peak_idx] * 100,
                    "recovery_sessions": i - peak_idx,
                })
                in_dd = False
            peak_idx = i
        else:
            if not in_dd:
                in_dd = True
                low_idx = i
            elif prices[i] < prices[low_idx]:
                low_idx = i

    # If still in drawdown at end, don't count recovery
    if in_dd:
        drawdowns.append({
            "start_idx": peak_idx,
            "end_idx": len(prices) - 1,
            "low_idx": low_idx,
            "max_dd": (prices[low_idx] - prices[peak_idx]) / prices[peak_idx] * 100,
            "recovery_sessions": None,
        })

    return drawdowns


def fetch_nifty_1y() -> Optional[np.ndarray]:
    """Fetch 1 year of Nifty daily close prices."""
    try:
        ticker = yf.Ticker(NIFTY_SYMBOL)
        hist = ticker.history(period="1y")
        if hist.empty or len(hist) < 60:
            return None
        return hist["Close"].values
    except Exception as e:
        print(f"⚠️ Nifty 1y fetch error: {e}")
        return None


def compute_drawdown(prices: np.ndarray, current_price: Optional[float] = None) -> Dict:
    """
    Compute drawdown anatomy from Nifty price series.

    Returns:
        current_dd_pct: Drawdown % from 252D high
        high_252d: Highest price in last year
        velocity_5d: 5-day drawdown rate (%/day)
        recovery_sessions: Median sessions to recover from similar drawdowns
        has_recovery_data: Whether historical recovery data is available
    """
    if prices is None or len(prices) < 60:
        return {"has_data": False}

    high_252d = float(np.max(prices))
    current = current_price if current_price is not None else float(prices[-1])
    current_dd = (current - high_252d) / high_252d * 100

    dd_series = _compute_drawdown_series(prices)
    dd_5d_ago = dd_series[-6] if len(dd_series) > 6 else dd_series[0]
    velocity_5d = (dd_series[-1] - dd_5d_ago) / 5

    drawdowns = _find_drawdowns(prices)
    similar = []
    for dd in drawdowns:
        if dd["recovery_sessions"] is not None and dd["max_dd"] is not None:
            if abs(dd["max_dd"] - current_dd) <= 2.0:
                similar.append(dd["recovery_sessions"])

    recovery_sessions = int(np.median(similar)) if len(similar) >= 2 else None

    return {
        "has_data": True,
        "current_dd_pct": round(current_dd, 1),
        "high_252d": round(high_252d, 2),
        "velocity_5d": round(velocity_5d, 2),
        "recovery_sessions": recovery_sessions,
    }


def format_drawdown_block(result: Dict) -> str:
    """Format drawdown anatomy for Telegram output."""
    if not result.get("has_data"):
        return ""

    dd = result["current_dd_pct"]

    if dd >= 0:
        return ""

    vel = result["velocity_5d"]
    if vel < -0.5:
        vel_label = "RAPID"
    elif vel < -0.2:
        vel_label = "MODERATE"
    else:
        vel_label = "SLOW"

    parts = [f"📉 *DRAWDOWN:* {dd:+.1f}% from 252D high", f"Velocity: {vel:.1f}%/day ({vel_label})"]

    recovery = result.get("recovery_sessions")
    if recovery is not None:
        parts.append(f"Historical recovery: {recovery} sessions (median)")

    return " | ".join(parts)


def run_drawdown_analysis(current_price: Optional[float] = None) -> Dict:
    """
    Full drawdown analysis pipeline.

    Args:
        current_price: Optional override for current Nifty price.
                       If None, uses last price from yfinance.

    Returns:
        Dict with raw results and formatted block.
    """
    prices = fetch_nifty_1y()
    if prices is None:
        return {"ok": False, "message": "No price data available"}

    result = compute_drawdown(prices, current_price)
    if not result.get("has_data"):
        return {"ok": False, "message": "Insufficient price data"}

    formatted = format_drawdown_block(result)

    return {
        "ok": True,
        "drawdown": result,
        "formatted": formatted,
    }
