"""
Single data access layer for all compute modules.

Read path priority:
  1. CSV (immutable, 5Y, instant)          — covers everything up to last Sunday
  2. Supabase gap (last 7 days)           — current week rows not yet in CSV
  3. Live DataFrame (today's prices)      — passed by caller, wins on overlap

All compute modules (clone_engine, stress_index, drawdown_anatomy, pillar_classifier,
transmission_mechanics) MUST use these functions instead of raw csv_data or
direct Supabase queries.

Bootstrap: if CSV has < 252 rows, pull older Supabase data to supplement
(handles the first 6 months while CSV is being built up).
"""
import os
import sys
from datetime import datetime, timedelta
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from src.db import get_client

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# ─────────────────────────────────────────────────────────────────────────────
# CSV MAP — one CSV per logical dataset
# ─────────────────────────────────────────────────────────────────────────────

CSV_MAP = {
    "anchors":  os.path.join(DATA_DIR, "anchor_history.csv"),
    "nifty":    os.path.join(DATA_DIR, "nifty_history.csv"),
    "fii_dii":  os.path.join(DATA_DIR, "fii_dii_history.csv"),
    "stress":   os.path.join(DATA_DIR, "stress_history.csv"),
}

# Supabase table that holds the "current week" gap for each dataset
TABLE_GAP_MAP = {
    "anchors":  "macro_anchor_snapshots",
    "nifty":    "daily_market_snapshot",
    "fii_dii":  "fii_dii_flows",
    "stress":   "stress_history",
}

# Column used as date key in each table
DATE_COL_MAP = {
    "anchors":  "trade_date",
    "nifty":    "trade_date",
    "fii_dii":  "date",
    "stress":   "trade_date",
}


# ─────────────────────────────────────────────────────────────────────────────
# CORE READ FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def get_series(dataset: str, live_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """
    Return full time-series from CSV + Supabase gap + live.

    Args:
        dataset: one of "anchors", "nifty", "fii_dii", "stress"
        live_df: DataFrame with today's prices (cols: date, other cols).
                 If provided, wins on date overlap with CSV/Supabase.

    Returns:
        DataFrame sorted by date, no duplicate dates, no NaN index.
        Columns depend on dataset. Always has "date" column.
    """
    csv_path = CSV_MAP.get(dataset)
    if csv_path is None:
        raise ValueError(f"Unknown dataset: {dataset}. Valid: {list(CSV_MAP.keys())}")

    # ── Layer 1: CSV ──────────────────────────────────────────────────────────
    try:
        hist = pd.read_csv(csv_path, parse_dates=["date"])
    except (FileNotFoundError, pd.errors.EmptyDataError):
        hist = pd.DataFrame()

    # ── Bootstrap: if CSV is too short, supplement from Supabase ─────────────
    if len(hist) < 252:
        older = _read_supabase_all(dataset)
        if older is not None and not older.empty:
            hist = pd.concat([older, hist], ignore_index=True)
            hist = hist.drop_duplicates(subset=["date"], keep="last")
            hist = hist.sort_values("date").reset_index(drop=True)

    # ── Layer 2: Supabase gap (current week, not yet in CSV) ─────────────────
    if not hist.empty:
        supabase_gap = _read_supabase_gap(dataset, hist["date"].max())
    else:
        supabase_gap = _read_supabase_all(dataset)

    frames = []
    if not hist.empty:
        frames.append(hist)
    if supabase_gap is not None and not supabase_gap.empty:
        frames.append(supabase_gap)
    if live_df is not None and not live_df.empty:
        frames.append(live_df)

    if not frames:
        return pd.DataFrame()

    merged = pd.concat(frames, ignore_index=True)
    merged = merged.drop_duplicates(subset=["date"], keep="last")
    merged = merged.sort_values("date").reset_index(drop=True)

    return merged


def get_baselines(dataset: str = "anchors", lookback: int = 252) -> dict:
    """
    Compute lookback-day baseline (mean) for all numeric columns.

    Used by consequence_engine for "above/below baseline" comparisons.

    Returns: {"USDINR": 83.2, "Brent": 78.5, "VIX": 14.1, ...}
    """
    full = get_series(dataset)
    if full.empty:
        return {}

    # Ensure date column doesn't get included in numeric cols
    numeric = full.select_dtypes(include="number").columns.tolist()

    if len(full) <= lookback:
        recent = full[numeric]
    else:
        recent = full.tail(lookback)[numeric]

    baselines = {}
    for col in numeric:
        vals = pd.to_numeric(recent[col], errors="coerce").dropna()
        if not vals.empty:
            baselines[col] = round(vals.mean(), 4)

    return baselines


def get_current_percentiles(dataset: str = "anchors") -> dict:
    """
    Compute expanding percentiles for the current row.
    Used by pillar_classifier for threshold detection.

    Returns: dict of column_name_pctile: value (0.0 – 1.0)
    """
    full = get_series(dataset)
    if full.empty:
        return {}

    numeric = full.select_dtypes(include="number").columns.tolist()
    pctiles = {}

    for col in numeric:
        if col == "date":
            continue
        vals = pd.to_numeric(full[col], errors="coerce")
        # expanding percentile rank: fraction of values <= current
        pct = vals.expanding().apply(lambda x: (x <= x[-1]).mean(), include_end=True)
        if not pct.empty:
            pctiles[f"{col}_pctile"] = round(float(pct.iloc[-1]), 4)

    return pctiles


def get_nifty_close_series(live_df: Optional[pd.DataFrame] = None) -> pd.Series:
    """
    Convenience wrapper: get Nifty close series for clone engine / drawdown anatomy.

    Returns: Series with date index and close values.
    """
    nifty = get_series("nifty", live_df)
    if nifty.empty or "close" not in nifty.columns:
        return pd.Series(dtype=float)
    nifty = nifty.set_index("date")["close"].sort_index()
    return nifty


def get_fii_dii_series(live_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """
    Convenience wrapper: get FII/DII series for flow velocity.

    Returns: DataFrame with date, fii_net, dii_net columns.
    """
    df = get_series("fii_dii", live_df)
    for col in ["fii_net", "dii_net"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def get_stress_series(live_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """
    Convenience wrapper: get stress history for stress_index.

    Returns: DataFrame with date, stress_score columns.
    """
    df = get_series("stress", live_df)
    if "stress_score" in df.columns:
        df["stress_score"] = pd.to_numeric(df["stress_score"], errors="coerce")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _read_supabase_gap(dataset: str, last_csv_date) -> pd.DataFrame:
    """
    Read rows from Supabase that are NEWER than the last CSV date.
    These are rows from the current week that haven't been archived yet.
    """
    table = TABLE_GAP_MAP.get(dataset)
    date_col = DATE_COL_MAP.get(dataset)
    if not table:
        return pd.DataFrame()

    # If last_csv_date is a Timestamp, convert to date string
    if hasattr(last_csv_date, "date"):
        last_csv_date = str(last_csv_date.date())
    else:
        last_csv_date = str(last_csv_date)

    db = get_client()
    if not db:
        return pd.DataFrame()

    try:
        result = db.table(table).select("*").gt(date_col, last_csv_date).execute()
        if not result.data:
            return pd.DataFrame()

        df = pd.DataFrame(result.data)
        df = df.rename(columns={date_col: "date"})
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        return df
    except Exception:
        return pd.DataFrame()


def _read_supabase_all(dataset: str) -> pd.DataFrame:
    """
    Read ALL available rows from Supabase for this dataset.
    Used during bootstrap (CSV < 252 rows) and when CSV is missing.
    """
    table = TABLE_GAP_MAP.get(dataset)
    date_col = DATE_COL_MAP.get(dataset)
    if not table:
        return pd.DataFrame()

    db = get_client()
    if not db:
        return pd.DataFrame()

    try:
        # Order by date descending, limit to 5 years max
        cutoff = (datetime.utcnow() - timedelta(days=365 * 5)).strftime("%Y-%m-%d")
        result = (
            db.table(table)
            .select("*")
            .gte(date_col, cutoff)
            .order(date_col)
            .execute()
        )
        if not result.data:
            return pd.DataFrame()

        df = pd.DataFrame(result.data)
        df = df.rename(columns={date_col: "date"})
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        return df
    except Exception:
        return pd.DataFrame()


def csv_freshness(dataset: str) -> dict:
    """
    Check if the CSV for a dataset is fresh enough to use without Supabase gap.

    Returns: {"fresh": bool, "latest_date": str|None, "days_old": int}
    """
    csv_path = CSV_MAP.get(dataset)
    if not csv_path:
        return {"fresh": False, "latest_date": None, "days_old": 999}

    try:
        df = pd.read_csv(csv_path, parse_dates=["date"])
        if df.empty:
            return {"fresh": False, "latest_date": None, "days_old": 999}
        latest = df["date"].max()
        days_old = (datetime.utcnow() - latest).days
        return {"fresh": days_old <= 14, "latest_date": str(latest.date()), "days_old": days_old}
    except Exception:
        return {"fresh": False, "latest_date": None, "days_old": 999}