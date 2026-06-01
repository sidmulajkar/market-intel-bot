"""
One-time script: Add KWEB + derived columns to existing anchor_history.csv.
Runs once locally, not in CI. Does NOT refetch 5Y for existing tickers.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import yfinance as yf
import numpy as np

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CSV_PATH = os.path.join(DATA_DIR, "anchor_history.csv")

# Read existing CSV
df = pd.read_csv(CSV_PATH, parse_dates=["date"])
print(f"Existing CSV: {len(df)} rows, {len(df.columns)} cols")
print(f"Date range: {df.date.min()} to {df.date.max()}")
print(f"Existing columns: {list(df.columns)}")

# List of new tickers to add (only the ones not already in CSV)
NEW_TICKERS = {"KWEB": "KWEB"}
EXISTING_COLS = set(df.columns)
TO_FETCH = {k: v for k, v in NEW_TICKERS.items() if v not in EXISTING_COLS}

if not TO_FETCH:
    print("All new tickers already in CSV. Checking derived columns...")
else:
    print(f"\nFetching {len(TO_FETCH)} new ticker(s): {list(TO_FETCH.keys())}")
    ticker_symbols = list(TO_FETCH.keys())
    
    # Fetch 5Y history for new tickers
    t = yf.download(ticker_symbols, period="5y", interval="1d",
                    auto_adjust=True, progress=False)
    print(f"  Downloaded: shape={t.shape}")
    
    if t.empty:
        print("  ERROR: No data returned")
        sys.exit(1)
    
    # Extract close prices
    if isinstance(t.columns, pd.MultiIndex):
        close = t.xs("Close", axis=1, level=0, drop_level=True)
    else:
        close = t[["Close"]] if "Close" in t.columns else t
    
    close.index = pd.to_datetime(close.index)
    close.index.name = "date"
    close = close.reset_index()
    
    # Rename columns
    close.rename(columns=TO_FETCH, inplace=True)
    
    # Merge on date (left join preserves existing rows)
    df = df.merge(close, on="date", how="left")
    print(f"  After merge: {len(df)} rows, {len(df.columns)} cols")

# Compute any missing derived columns
DERIVED = {
    "Cu_Au_Ratio": lambda r: np.nan if r.get("Gold", 0) == 0 else r["Copper"] / r["Gold"] * 100,
}

for col_name, func in DERIVED.items():
    if col_name not in df.columns and all(c in df.columns for c in ["Copper", "Gold"]):
        df[col_name] = df.apply(func, axis=1)
        print(f"  Derived column added: {col_name}")

# Save
df.to_csv(CSV_PATH, index=False)
print(f"\n✅ CSV updated: {len(df)} rows, {len(df.columns)} cols")
print(f"   New columns: {[c for c in df.columns if c not in EXISTING_COLS]}")
print(f"   KWEB valid: {df['KWEB'].notna().sum()}/{len(df)}")

# Verify quality
core = ["USDINR", "Brent", "DXY", "IndiaVIX", "Gold", "KWEB"]
for c in core:
    if c in df.columns:
        v = df[c].notna().sum()
        print(f"   {c:15s}: {v:5d} valid ({v/len(df):.0%})")
