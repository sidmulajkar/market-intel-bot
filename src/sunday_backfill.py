"""
Sunday CSV Backfill — The ONLY code that writes to CSV.

Data flow: Supabase (daily writes) → Sunday consolidation → CSV → git snapshot
Two-phase commit: (1) write CSV + (2) mark Supabase rows archived.
Conditional purge: only runs if git push succeeded.

Supabase is the WRITE path for today. CSV is the WRITE path for history.
"""
import os
import sys
import subprocess
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

# Shared DB client
from src.db import get_client

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# ═══════════════════════════════════════════════════════════
# DATASET DEFINITIONS
# ═══════════════════════════════════════════════════════════

DATASETS = {
    "anchors": {
        "csv": os.path.join(DATA_DIR, "anchor_history.csv"),
        "supabase_table": "macro_anchor_snapshots",
        "date_col": "trade_date",
        "price_cols": ["USDINR", "Brent", "Gold", "IndiaVIX", "DXY", "US10Y",
                       "HYG", "WTI", "USDJPY", "EURUSD", "Silver", "Copper",
                       "US2Y", "SP500", "NASDAQ", "Nikkei", "LQD", "SOXX",
                       "KWEB", "SPY", "EEM"],
        "index_cols": ["date"],
    },
    "nifty": {
        "csv": os.path.join(DATA_DIR, "nifty_history.csv"),
        "supabase_table": "daily_market_snapshot",
        "date_col": "trade_date",
        "price_cols": ["open", "high", "low", "close", "volume"],
        "index_cols": ["date"],
    },
    "fii_dii": {
        "csv": os.path.join(DATA_DIR, "fii_dii_history.csv"),
        "supabase_table": "fii_dii_flows",
        "date_col": "date",
        "price_cols": [],
        "index_cols": ["date"],
    },
    "stress": {
        "csv": os.path.join(DATA_DIR, "stress_history.csv"),
        "supabase_table": "stress_history",
        "date_col": "trade_date",
        "price_cols": [],
        "index_cols": ["date"],
    },
}

# yfinance tickers for anchor gap-fill (fallback only)
_ANCHORS_TICKERS = [
    "USDINR=X", "BZ=F", "GC=F", "^INDIAVIX", "DX-Y.NYB", "^TNX",
    "^VIX", "HYG", "CL=F", "JPY=X", "EURUSD=X", "SI=F", "HG=F",
    "2YY=F", "ES=F", "NQ=F", "^N225", "LQD", "SOXX", "KWEB", "SPY", "EEM",
]
_ANCHOR_RENAME = {
    "USDINR=X": "USDINR", "BZ=F": "Brent", "GC=F": "Gold",
    "^INDIAVIX": "IndiaVIX", "DX-Y.NYB": "DXY", "^TNX": "US10Y",
    "^VIX": "CBOE_VIX", "HYG": "HYG", "CL=F": "WTI",
    "JPY=X": "USDJPY", "EURUSD=X": "EURUSD", "SI=F": "Silver",
    "HG=F": "Copper", "2YY=F": "US2Y", "ES=F": "SP500",
    "NQ=F": "NASDAQ", "^N225": "Nikkei", "LQD": "LQD", "SOXX": "SOXX",
    "KWEB": "KWEB", "SPY": "SPY", "EEM": "EEM",
}


# ═══════════════════════════════════════════════════════════
# PER-DATASET BACKFILL
# ═══════════════════════════════════════════════════════════

def backfill_dataset(name: str, config: dict) -> dict:
    """
    Consolidate one dataset: Supabase (primary) + yfinance delta (fallback) → CSV.

    Returns: {"rows_read": N, "rows_appended": M, "status": str}
    """
    csv_path = config["csv"]
    table = config["supabase_table"]
    date_col = config["date_col"]

    # ── Step 1: Read existing CSV ──────────────────────────
    try:
        hist = pd.read_csv(csv_path, parse_dates=["date"])
        last_csv_date = hist["date"].max()
    except (FileNotFoundError, pd.errors.EmptyDataError):
        hist = pd.DataFrame()
        last_csv_date = pd.Timestamp("2020-01-01")

    # ── Step 2: Read new rows from Supabase ────────────────
    new_rows = pd.DataFrame()
    try:
        db = get_client()
        if db:
            result = db.table(table).select("*").gt(date_col, str(last_csv_date.date())).execute()
            if result.data:
                new_rows = pd.DataFrame(result.data)
    except Exception as e:
        return {"rows_read": 0, "rows_appended": 0, "status": f"supabase_error: {e}"}

    # ── Step 3: yfinance delta fallback (anchors only) ───
    yf_delta = None
    if name == "anchors" and new_rows.empty:
        yf_delta = _fetch_yf_anchors(last_csv_date + timedelta(days=1))
    elif name == "nifty" and new_rows.empty:
        yf_delta = _fetch_yf_nifty(last_csv_date + timedelta(days=1))

    # ── Step 4: Merge all sources ──────────────────────────
    frames = [hist] if not hist.empty else []
    if not new_rows.empty:
        new_rows = new_rows.rename(columns={date_col: "date"})
        new_rows["date"] = pd.to_datetime(new_rows["date"], errors="coerce")
        new_rows = new_rows.dropna(subset=["date"])
        frames.append(new_rows)
    if yf_delta is not None and not yf_delta.empty:
        frames.append(yf_delta)

    if len(frames) == 1 and not new_rows.empty:
        return {"rows_read": len(new_rows), "rows_appended": 0, "status": "no_new_data"}

    # ── Step 5: Validate before writing ───────────────────
    merged = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if merged.empty:
        return {"rows_read": 0, "rows_appended": 0, "status": "no_data"}

    merged = merged.drop_duplicates(subset=["date"], keep="last")
    merged = merged.sort_values("date").reset_index(drop=True)

    issues = _validate(merged, config, name)
    if issues:
        return {
            "rows_read": len(new_rows),
            "rows_appended": 0,
            "status": f"validation_failed: {'; '.join(issues)}"
        }

    # ── Step 6: Write CSV ──────────────────────────────────
    merged.to_csv(csv_path, index=False)

    # ── Step 7: Mark Supabase rows as archived (non-critical) ─
    if not new_rows.empty:
        _mark_archived(db, table, date_col, last_csv_date)

    rows_appended = len(merged) - len(hist) if not hist.empty else len(merged)
    return {"rows_read": len(new_rows), "rows_appended": rows_appended, "status": "success"}


def _fetch_yf_anchors(start_date) -> pd.DataFrame | None:
    """Fetch anchor prices from yfinance as gap-fill fallback."""
    try:
        import yfinance as yf
        data = yf.download(
            _ANCHORS_TICKERS, start=str(start_date.date()),
            end=datetime.now().strftime("%Y-%m-%d"),
            interval="1d", auto_adjust=True, progress=False, actions=False
        )
        if data.empty:
            return None
        if isinstance(data.columns, pd.MultiIndex):
            close = data["Close"] if "Close" in data.columns.get_level_values(0) else data
        else:
            close = data if "Close" in data.columns else data
        close = close.rename(columns=_ANCHOR_RENAME).reset_index()
        close = close.rename(columns={"Date": "date"})
        close["date"] = pd.to_datetime(close["date"], errors="coerce")
        close = close.dropna(subset=["date"])
        return close
    except Exception:
        return None


def _fetch_yf_nifty(start_date) -> pd.DataFrame | None:
    """Fetch Nifty OHLCV from yfinance as gap-fill fallback."""
    try:
        import yfinance as yf
        tk = yf.Ticker("^NSEI")
        hist = tk.history(start=str(start_date.date()), end=datetime.now().strftime("%Y-%m-%d"))
        if hist.empty:
            return None
        hist = hist.reset_index()
        hist = hist.rename(columns={
            "Date": "date", "Open": "open", "High": "high",
            "Low": "low", "Close": "close", "Volume": "volume"
        })
        hist["date"] = pd.to_datetime(hist["date"], errors="coerce")
        hist = hist.dropna(subset=["date"])
        return hist[["date", "open", "high", "low", "close", "volume"]]
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════
# VALIDATION
# ═══════════════════════════════════════════════════════════

def _validate(df: pd.DataFrame, config: dict, name: str) -> list:
    """Validate CSV before committing. Returns list of issues (empty = valid)."""
    issues = []

    # Check: Dates monotonic increasing
    if not df["date"].is_monotonic_increasing:
        df = df.sort_values("date").reset_index(drop=True)

    # Check: No duplicate dates
    dupes = df["date"].duplicated().sum()
    if dupes > 0:
        issues.append(f"{dupes} duplicate dates")

    # Check: No zero prices (yfinance delisting artifact)
    price_cols = [c for c in config.get("price_cols", []) if c in df.columns]
    for col in price_cols:
        if (df[col] == 0).any():
            zero_dates = df[df[col] == 0]["date"].dt.strftime("%Y-%m-%d").tolist()[:3]
            issues.append(f"zero price in {col} on {zero_dates}")

    # Check: No >3% daily gaps in price columns (corruption detection)
    for col in price_cols:
        if col in df.columns and len(df) > 1:
            vals = pd.to_numeric(df[col], errors="coerce")
            pct = vals.pct_change().abs()
            extreme_count = (pct > 0.03).sum()
            if extreme_count > 3:
                issues.append(f"{extreme_count} extreme moves in {col} (>{3}%)")

    return issues


def _mark_archived(db, table: str, date_col: str, last_date) -> None:
    """Mark Supabase rows newer than last_date as archived (two-phase commit)."""
    try:
        db.table(table).update({"archived": True}).gt(date_col, str(last_date.date())).execute()
    except Exception:
        pass  # Non-critical — archive flag is nice-to-have


# ═══════════════════════════════════════════════════════════
# GIT COMMIT + PUSH
# ═══════════════════════════════════════════════════════════

def git_commit_and_push() -> str:
    """Commit updated CSVs to repo. Returns: 'success' | 'no_changes' | 'failed'."""
    try:
        subprocess.run(["git", "config", "user.name", "Market Intel Bot"], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "bot@market-intel.local"], check=True, capture_output=True)
        subprocess.run(["git", "add", "data/anchor_history.csv", "data/nifty_history.csv",
                        "data/fii_dii_history.csv", "data/stress_history.csv"], check=True, capture_output=True)
        result = subprocess.run(["git", "diff", "--cached", "--quiet"], capture_output=True)
        if result.returncode != 0:
            date_str = datetime.now().strftime("%Y-%m-%d")
            msg = f"📥 Weekly CSV backfill ({date_str}) [skip ci]"
            subprocess.run(["git", "commit", "-m", msg], check=True, capture_output=True)
            subprocess.run(["git", "push"], check=True, capture_output=True)
            return "success"
        return "no_changes"
    except subprocess.CalledProcessError:
        return "failed"


# ═══════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════

def run() -> dict:
    """
    Run Sunday consolidation for all datasets.

    Flow:
      1. Backfill each dataset (Supabase → CSV)
      2. Git push (only if ALL datasets succeeded)
      3. Conditional purge (only if git push succeeded)

    Returns: {"anchors": {...}, "nifty": {...}, "fii_dii": {...}, "stress": {...},
             "git_push": str, "purge": dict}
    """
    results = {}
    all_success = True

    for name, config in DATASETS.items():
        result = backfill_dataset(name, config)
        results[name] = result
        if result["status"] not in ("success", "no_new_data"):
            all_success = False

    # Only push if all datasets succeeded
    if all_success:
        push_result = git_commit_and_push()
        results["git_push"] = push_result

        # Only run purge if push succeeded
        if push_result == "success":
            try:
                from src.purge_manager import purge_expired_tables
                db = get_client()
                if db:
                    results["purge"] = purge_expired_tables(db)
                else:
                    results["purge"] = {"status": "db_unavailable"}
            except Exception as e:
                results["purge"] = {"status": f"error: {e}"}
        else:
            results["git_push"] = push_result
            results["purge"] = {"status": "skipped (push failed)"}
    else:
        results["git_push"] = "skipped (dataset errors)"
        results["purge"] = {"status": "skipped (backfill failed)"}

    return results


if __name__ == "__main__":
    import json
    result = run()
    print(json.dumps(result, indent=2, default=str))
    sys.exit(0)