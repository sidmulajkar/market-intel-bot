"""
value_metrics.py — P8 Relative Value
P8.1: India vs EM Basket (30D rolling RS spread)
P8.2: ERP Decile Boundaries (Sunday pre-compute)
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional


NIFTY_SYMBOL = "^NSEI"
EM_SYMBOL = "EEM"


def compute_india_vs_em_rs() -> Dict:
    """Compute 30D rolling relative strength of Nifty vs EEM.

    Returns:
        Dict with spread, india_return_30d, em_return_30d, ok
    """
    try:
        import yfinance as yf
        end = datetime.now()
        start = end - timedelta(days=90)

        data = yf.download([NIFTY_SYMBOL, EM_SYMBOL], start=start, end=end,
                           auto_adjust=True, progress=False)
        if data.empty:
            return {"ok": False}

        closes = data.get("Close", data)
        if hasattr(closes, 'columns') and closes.ndim >= 2:
            pass
        else:
            return {"ok": False}

        nifty_close = _get_series(closes, NIFTY_SYMBOL)
        em_close = _get_series(closes, EM_SYMBOL)

        if nifty_close is None or em_close is None or len(nifty_close) < 30:
            return {"ok": False}

        nifty_30d = (nifty_close.iloc[-1] / nifty_close.iloc[-30] - 1) * 100
        em_30d = (em_close.iloc[-1] / em_close.iloc[-30] - 1) * 100
        spread = round(nifty_30d - em_30d, 2)

        return {
            "ok": True,
            "spread": spread,
            "india_return_30d": round(nifty_30d, 2),
            "em_return_30d": round(em_30d, 2),
            "date": datetime.now().strftime("%Y-%m-%d"),
        }
    except Exception as e:
        print(f"⚠️ compute_india_vs_em_rs: {e}")
        return {"ok": False}


def compute_erp_deciles(supabase=None) -> Dict:
    """Sunday pre-compute: bin anchor_history.csv into ERP decile boundaries.

    ERP = (1 / Nifty PE) - India 10Y Yield
    Uses 5Y of anchor_history.csv to compute decile boundaries.

    Stores boundaries as JSONB in market_state for instant weekday lookup.
    """
    try:
        csv_path = "data/anchor_history.csv"
        df = pd.read_csv(csv_path)
        if df.empty:
            print("⚠️ ERP deciles: anchor_history.csv empty")
            return {"ok": False}

        date_col = None
        for c in ["date", "Date", "DATE", "timestamp"]:
            if c in df.columns:
                date_col = c
                break
        if not date_col:
            print("⚠️ ERP deciles: no date column found")
            return {"ok": False}

        df[date_col] = pd.to_datetime(df[date_col])
        cutoff = datetime.now() - timedelta(days=1825)
        df = df[df[date_col] >= cutoff]

        nifty_col = None
        for c in ["nifty_close", "Nifty", "^NSEI", "close"]:
            if c in df.columns:
                nifty_col = c
                break
        us10y_col = None
        for c in ["us_10y", "US10Y", "^TNX", "tnx"]:
            if c in df.columns:
                us10y_col = c
                break

        if not nifty_col or not us10y_col:
            # Try to use a PE ratio or estimate
            print("⚠️ ERP deciles: missing required columns")
            return {"ok": False}

        df["erp"] = (1 / df[nifty_col]) - df[us10y_col]
        df = df.dropna(subset=["erp"])

        if len(df) < 20:
            print(f"⚠️ ERP deciles: insufficient data ({len(df)} rows)")
            return {"ok": False}

        # Compute decile boundaries
        deciles = np.percentile(df["erp"], np.arange(10, 101, 10))
        boundaries = [round(float(v), 4) for v in deciles]

        # Compute forward return stats per decile
        df["erp_decile"] = pd.cut(df["erp"], bins=10, labels=False, duplicates="drop")
        win_rates = {}
        nifty_series = df[nifty_col].values

        for decile in range(10):
            mask = df["erp_decile"] == decile
            decile_data = df[mask]
            if len(decile_data) < 5:
                continue
            # Count positive forward 30D returns at this decile
            positive = 0
            total = 0
            for idx in decile_data.index:
                pos = df.index.get_loc(idx)
                if pos + 20 < len(nifty_series):
                    fwd = (nifty_series[pos + 20] / nifty_series[pos] - 1) * 100
                    if fwd > 0:
                        positive += 1
                    total += 1
            if total >= 5:
                win_rates[str(decile)] = {
                    "win_rate": round(positive / total, 3),
                    "samples": total,
                }

        result = {
            "ok": True,
            "decile_boundaries": boundaries,
            "win_rates": win_rates,
            "samples": len(df),
        }

        # Persist to market_state
        _persist_erp_deciles(result)

        return result
    except Exception as e:
        print(f"⚠️ compute_erp_deciles: {e}")
        return {"ok": False}


def get_current_erp_decile(current_erp: float) -> Dict:
    """Weekday lookup: find which decile current ERP falls into.

    Args:
        current_erp: (1/Nifty PE) - India 10Y Yield

    Returns:
        Dict with decile, win_rate, samples, or empty dict on failure.
    """
    try:
        from src.db import get_client
        db = get_client()
        if not db:
            return {}

        today = datetime.now().strftime("%Y-%m-%d")
        result = (
            db.table("market_state")
            .select("state")
            .eq("trade_date", today)
            .limit(1)
            .execute()
        )
        if not result.data:
            return {}

        state = result.data[0].get("state", {})
        if not isinstance(state, dict):
            return {}

        erp_data = state.get("erp_deciles", {})
        boundaries = erp_data.get("decile_boundaries", [])
        if not boundaries:
            return {}

        # Find which decile current ERP falls into
        for i, bound in enumerate(boundaries):
            if current_erp <= bound:
                win_rates = erp_data.get("win_rates", {})
                win = win_rates.get(str(i), {})
                return {
                    "decile": i,
                    "boundary": bound,
                    "win_rate": win.get("win_rate"),
                    "samples": win.get("samples"),
                }

        # Above top decile
        return {
            "decile": 9,
            "boundary": boundaries[-1],
            "win_rate": erp_data.get("win_rates", {}).get("9", {}).get("win_rate"),
            "samples": erp_data.get("win_rates", {}).get("9", {}).get("samples"),
        }
    except Exception as e:
        print(f"⚠️ get_current_erp_decile: {e}")
        return {}


def format_erp_decile(erp_value: float) -> str:
    """Format ERP decile block for Telegram output."""
    info = get_current_erp_decile(erp_value)
    if not info:
        return ""

    decile = info.get("decile")
    win_rate = info.get("win_rate")
    samples = info.get("samples")

    if decile is None:
        return ""

    label = "bottom" if decile <= 1 else ("top" if decile >= 8 else f"decile {decile}")
    parts = [f"ERP: {erp_value:.2f}% ({label})"]

    if win_rate is not None and samples:
        pct = win_rate * 100
        parts.append(f"Historical prob of positive Nifty 30D: {pct:.0f}% ({samples} samples)")

    return "📊 " + " | ".join(parts)


def compute_erp(nifty_pe: float, india_10y_yield: float) -> float:
    """Compute Equity Risk Premium: (1 / Nifty PE) - India 10Y Yield."""
    if not nifty_pe or nifty_pe <= 0:
        return 0.0
    earnings_yield = 100.0 / nifty_pe
    return round(earnings_yield - india_10y_yield, 4)


def _get_series(data, symbol: str):
    """Extract a single series from multi-index yfinance DataFrame."""
    try:
        if hasattr(data, 'columns') and isinstance(data.columns, pd.MultiIndex):
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


def _persist_erp_deciles(result: Dict, supabase=None) -> bool:
    """Store ERP decile data in market_state."""
    try:
        from src.db import get_client
        db = supabase or get_client()
        if not db:
            return False

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

        state["erp_deciles"] = {
            "decile_boundaries": result.get("decile_boundaries", []),
            "win_rates": result.get("win_rates", {}),
            "samples": result.get("samples", 0),
        }
        db.table("market_state").upsert({
            "trade_date": today,
            "state": state,
        }).execute()
        print("✅ Persisted ERP deciles to market_state")
        return True
    except Exception as e:
        print(f"⚠️ _persist_erp_deciles: {e}")
        return False
