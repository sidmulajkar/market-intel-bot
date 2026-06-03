"""
liquidity_freeze.py — P11.2 Liquidity Freeze Detection
Welford streaming Z-score for HYG/LQD ratio spread.
In-memory only — no DB writes. Computed on-demand from yfinance batch data.

Decoupled from P5.2 DII Capacity — runs independently.
"""
from typing import Dict, Optional


HYG_SYMBOL = "HYG"
LQD_SYMBOL = "LQD"


def compute_liquidity_velocity() -> Dict:
    """Compute HYG/LQD ratio spread velocity via Welford streaming Z-score.

    Fetches last 60 days of HYG/LQD data, computes ratio, then
    Welford Z-score of the ratio's 5D change velocity.

    Returns:
        Dict with z_score, velocity, ok, or {"ok": False} on failure.
    """
    try:
        import yfinance as yf
        import numpy as np
        from datetime import datetime, timedelta

        end = datetime.now()
        start = end - timedelta(days=90)

        data = yf.download([HYG_SYMBOL, LQD_SYMBOL], start=start, end=end,
                           auto_adjust=True, progress=False)
        if data.empty:
            return {"ok": False}

        closes = data.get("Close", data)
        hyg = _get_series(closes, HYG_SYMBOL)
        lqd = _get_series(closes, LQD_SYMBOL)

        if hyg is None or lqd is None or len(hyg) < 20 or len(lqd) < 20:
            return {"ok": False}

        # Align series
        combined = hyg.to_frame("hyg").join(lqd.to_frame("lqd"), how="inner")
        combined["ratio"] = combined["hyg"] / combined["lqd"]

        if len(combined) < 20:
            return {"ok": False}

        # Compute 5D change in ratio
        combined["ratio_5d_change"] = combined["ratio"].diff(5)

        # Welford streaming (incremental mean + variance)
        changes = combined["ratio_5d_change"].dropna().values
        n = len(changes)
        if n < 10:
            return {"ok": False}

        mean = 0.0
        m2 = 0.0
        for i, x in enumerate(changes):
            delta = x - mean
            mean += delta / (i + 1)
            delta2 = x - mean
            m2 += delta * delta2

        variance = m2 / (n - 1) if n > 1 else 0
        std = np.sqrt(variance) if variance > 0 else 1e-10

        latest_velocity = float(changes[-1])
        z_score = (latest_velocity - mean) / std

        return {
            "ok": True,
            "z_score": round(float(z_score), 2),
            "velocity": round(float(latest_velocity), 6),
            "mean": round(float(mean), 6),
            "std": round(float(std), 6),
            "samples": n,
            "freeze_active": z_score > 3.0,
        }
    except Exception as e:
        print(f"⚠️ compute_liquidity_velocity: {e}")
        return {"ok": False}


def check_liquidity_freeze(macro_attrs: Dict = None) -> bool:
    """Check if liquidity freeze is active.

    Returns True if either:
      1. HYG/LQD Z-score > 3.0 (credit market panic)
      2. HYG < 72 (credit spread blowout)
    """
    vel = compute_liquidity_velocity()
    if vel.get("ok") and vel.get("freeze_active"):
        return True

    if macro_attrs:
        hyg = macro_attrs.get("HYG")
        if hyg is not None:
            try:
                if float(hyg) < 72:
                    return True
            except (ValueError, TypeError):
                pass

    return False


def _get_series(data, symbol: str):
    """Extract a single series from multi-index yfinance DataFrame."""
    try:
        if hasattr(data, 'columns') and isinstance(data.columns, type(data.columns)):
            if symbol in data.columns.get_level_values(0):
                series = data[symbol]
                if hasattr(series, 'iloc') and series.ndim > 1:
                    price_col = "Close" if "Close" in series.columns else series.columns[0]
                    return series[price_col].dropna()
                return series.dropna()
        if symbol in data:
            series = data[symbol]
            if hasattr(series, 'dropna'):
                return series.dropna()
    except Exception:
        pass
    return None
