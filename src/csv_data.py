"""
CSV-First Data Architecture (Phase 1)
Merges immutable historical data (CSV) with live data (Supabase + yfinance).
Every compute module calls get_full_series() instead of batch_download(period="5y").
"""
import os
import pandas as pd
import numpy as np
from typing import Optional, Dict, List

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

CSV_PATHS = {
    "anchors": os.path.join(DATA_DIR, "anchor_history.csv"),
    "nifty": os.path.join(DATA_DIR, "nifty_history.csv"),
    "fii_dii": os.path.join(DATA_DIR, "fii_dii_history.csv"),
    "econ_calendar": os.path.join(DATA_DIR, "econ_calendar_india_2026_27.csv"),
}

# 12D macro columns used by clone engine + pillar classifier
MACRO_12D = [
    "DXY", "US10Y", "HYG", "Gold", "Copper", "USDJPY",
    "IndiaVIX", "USDINR", "Brent", "CBOE_VIX", "SP500", "NASDAQ",
    "LQD", "SOXX", "KWEB", "Nikkei", "WTI", "Silver", "US2Y", "EURUSD",
]

# Core subset needed for clone engine distance computation
CLONE_CORE = ["IndiaVIX", "USDINR", "Brent", "DXY", "Gold", "Copper", "US10Y", "HYG", "USDJPY"]

# Minimum valid rows per dataset — reject corrupt/truncated CSVs
_MIN_ROWS = {"anchors": 100, "nifty": 100, "fii_dii": 5}
# Core columns that must have non-NaN data in >=30% of rows
_CORE_COLS = {
    "anchors": ["USDINR", "Brent", "DXY", "IndiaVIX", "Gold"],
    "nifty": ["Close"],
}

_CACHE: Dict[str, pd.DataFrame] = {}
_BOOTSTRAPPED: bool = False


def _generate_on_demand():
    """Generate CSVs from yfinance/Supabase if they don't exist. Runs once per session."""
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return
    _BOOTSTRAPPED = True

    missing = [ds for ds, p in CSV_PATHS.items()
               if ds != "econ_calendar" and not os.path.exists(p)]
    if not missing:
        return

    print(f"📥 CSV bootstrap: generating {len(missing)} missing dataset(s)...")
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from scripts.generate_csvs import main as gen_csvs
        gen_csvs()
        _CACHE.clear()
        print("✅ CSV bootstrap complete")
    except Exception as e:
        print(f"⚠️ CSV bootstrap failed: {e} (will fall back to yfinance)")


def _is_csv_usable(dataset: str, df: pd.DataFrame) -> bool:
    """Check CSV data quality. Returns False if data is too sparse/corrupt."""
    min_rows = _MIN_ROWS.get(dataset, 10)
    if len(df) < min_rows:
        return False
    core = _CORE_COLS.get(dataset, [])
    if not core:
        return True
    present = [c for c in core if c in df.columns]
    if not present:
        return False
    valid_ratio = df[present].notna().mean().mean()
    return valid_ratio >= 0.3


def _load_csv(dataset: str) -> pd.DataFrame:
    """Load CSV, cache in memory. Auto-bootstraps if missing. Rejects corrupt data."""
    if dataset != "econ_calendar":
        _generate_on_demand()
    if dataset in _CACHE:
        return _CACHE[dataset]
    path = CSV_PATHS.get(dataset)
    if path is None or not os.path.exists(path):
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, parse_dates=["date"])
        if "date" in df.columns:
            df = df.set_index("date").sort_index()
        if not _is_csv_usable(dataset, df):
            print(f"⚠️ CSV {dataset} fails quality check ({len(df)} rows, "
                  f"{df.notna().mean().mean():.0%} valid) — treating as empty")
            return pd.DataFrame()
        _CACHE[dataset] = df
        return df
    except Exception as e:
        print(f"⚠️ CSV {dataset} read error: {e} — treating as empty")
        return pd.DataFrame()


def clear_cache():
    """Clear in-memory cache (call if CSV is updated mid-session)."""
    _CACHE.clear()


def load_history(dataset: str) -> pd.DataFrame:
    """Load immutable historical data from CSV. Zero API calls. Cached."""
    return _load_csv(dataset).copy()


def merge_with_live(hist: pd.DataFrame, live: pd.DataFrame) -> pd.DataFrame:
    """Merge CSV history with live DataFrame. Live takes priority for overlapping dates."""
    if live.empty:
        return hist
    combined = pd.concat([hist, live])
    combined = combined[~combined.index.duplicated(keep="last")]
    combined = combined.sort_index()
    return combined


def get_full_series(dataset: str, live_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """
    Primary API for all compute modules.
    Returns full 5Y + today data. 99% from CSV, 1% from live.
    """
    hist = load_history(dataset)
    if live_df is not None and not live_df.empty:
        return merge_with_live(hist, live_df)
    return hist


def get_macro_vector(date_str: str, df: Optional[pd.DataFrame] = None) -> Dict[str, float]:
    """Get the 12D macro vector for a specific date. Returns dict of {col: value}."""
    if df is None:
        df = load_history("anchors")
    if df.empty:
        return {}
    try:
        date_ts = pd.Timestamp(date_str)
        if date_ts not in df.index:
            closest = df.index[df.index.searchsorted(date_ts) - 1] if date_ts > df.index[0] else df.index[0]
            row = df.loc[closest]
        else:
            row = df.loc[date_ts]
        return {col: float(row[col]) for col in MACRO_12D if col in df.columns and pd.notna(row.get(col))}
    except Exception:
        return {}


def get_anchor_history(symbol: str, days: int = 252) -> list:
    """
    Drop-in replacement for db.get_macro_history().
    Returns list of {date, price} dicts for percentile computation.
    Falls back to Supabase if CSV doesn't cover the full window.
    """
    df = load_history("anchors")
    if df.empty:
        return _supabase_fallback(symbol, days)

    col = _map_symbol_to_col(symbol)
    if col is None or col not in df.columns:
        return _supabase_fallback(symbol, days)

    series = df[col].dropna().tail(days)
    # Fall back if less than 25% of requested window has data (< 5 rows absolute minimum)
    if len(series) < max(5, days // 4):
        return _supabase_fallback(symbol, days)
    return [{"date": k.strftime("%Y-%m-%d"), "price": v}
            for k, v in series.items()]


def _map_symbol_to_col(symbol: str) -> Optional[str]:
    """Map yfinance ticker symbol to CSV column name."""
    _CSV_MAP = {
        "USDINR=X": "USDINR", "BZ=F": "Brent", "GC=F": "Gold",
        "^INDIAVIX": "IndiaVIX", "DX-Y.NYB": "DXY", "^TNX": "US10Y",
        "^VIX": "CBOE_VIX", "HYG": "HYG", "CL=F": "WTI",
        "JPY=X": "USDJPY", "EURUSD=X": "EURUSD", "SI=F": "Silver",
        "HG=F": "Copper", "2YY=F": "US2Y", "ES=F": "SP500",
        "NQ=F": "NASDAQ", "^N225": "Nikkei", "LQD": "LQD", "SOXX": "SOXX", "KWEB": "KWEB",
        "SPY": "SPY", "EEM": "EEM",
        "^NSEI": "Close",
    }
    mapping = _CSV_MAP
    return mapping.get(symbol)


def _supabase_fallback(symbol: str, days: int = 252) -> list:
    """Fallback to Supabase when CSV data is insufficient."""
    try:
        from src.db import get_macro_history
        return get_macro_history(symbol, days)
    except Exception:
        return []


def get_nifty_history(days: int = 252) -> pd.DataFrame:
    """Get Nifty close history from CSV. Returns DataFrame with Close column."""
    df = load_history("nifty")
    if df.empty:
        return pd.DataFrame()
    return df.tail(days)


def get_fii_dii_history(days: int = 252) -> pd.DataFrame:
    """Get FII/DII flow history from CSV (limited — only ~58 rows from Supabase)."""
    df = load_history("fii_dii")
    if df.empty:
        return pd.DataFrame()
    return df.tail(days)


def csv_freshness(dataset: str = "nifty", max_age_days: int = 14) -> Dict:
    """Check if CSV data is fresh enough. Returns {ok, last_date, age_days, message}."""
    df = load_history(dataset)
    if df.empty:
        return {"ok": False, "last_date": None, "age_days": None,
                "message": f"CSV {dataset} is empty"}
    last_date = df.index.max()
    age = (pd.Timestamp.now(tz=last_date.tz) - last_date).days if hasattr(last_date, 'tz') and last_date.tz else (pd.Timestamp.now() - last_date).days
    ok = age <= max_age_days
    return {"ok": ok, "last_date": str(last_date.date()), "age_days": age,
            "message": f"CSV {dataset} data is {age}d old{' ✅' if ok else ' ⚠️ stale'}" if age is not None else "Unknown"}


def get_nifty_close_series(days: int = 252) -> pd.Series:
    """Get Nifty close prices from CSV (or yfinance fallback). Never crashes."""
    try:
        df = load_history("nifty")
        if not df.empty and "Close" in df.columns:
            series = df["Close"].dropna().tail(days)
            if len(series) >= 20:
                return series
    except Exception:
        pass
    # Fallback to yfinance
    try:
        import yfinance as yf
        h = yf.Ticker("^NSEI").history(period="1y")
        if not h.empty and "Close" in h.columns:
            return h["Close"].dropna()
    except Exception:
        pass
    return pd.Series()
