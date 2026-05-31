"""
One-time CSV generation: Supabase (validated) + yfinance (gap fill).
Output: data/anchor_history.csv, data/nifty_history.csv, data/fii_dii_history.csv
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Core macro anchors (21 tickers — 19 market + 2 clone engine)
ANCHORS = [
    "USDINR=X", "BZ=F", "GC=F", "^INDIAVIX", "DX-Y.NYB", "^TNX",
    "^VIX", "HYG", "CL=F", "JPY=X", "EURUSD=X", "SI=F", "HG=F",
    "2YY=F", "ES=F", "NQ=F", "^N225", "LQD", "SOXX",
    "SPY", "EEM",
]

ANCHOR_RENAME = {
    "USDINR=X": "USDINR", "BZ=F": "Brent", "GC=F": "Gold",
    "^INDIAVIX": "IndiaVIX", "DX-Y.NYB": "DXY", "^TNX": "US10Y",
    "^VIX": "CBOE_VIX", "HYG": "HYG", "CL=F": "WTI",
    "JPY=X": "USDJPY", "EURUSD=X": "EURUSD", "SI=F": "Silver",
    "HG=F": "Copper", "2YY=F": "US2Y", "ES=F": "SP500",
    "NQ=F": "NASDAQ", "^N225": "Nikkei", "LQD": "LQD", "SOXX": "SOXX",
    "SPY": "SPY", "EEM": "EEM",
}


def batch_download(symbols: list, period: str = "5y") -> pd.DataFrame:
    """Download Close prices in groups to avoid yfinance ticker limits."""
    all_data = []
    chunk_size = 7
    for i in range(0, len(symbols), chunk_size):
        chunk = symbols[i:i+chunk_size]
        try:
            df = yf.download(chunk, period=period, interval="1d",
                             auto_adjust=True, progress=False, actions=True)
            if df.empty:
                continue
            # Extract Close prices only
            if isinstance(df.columns, pd.MultiIndex):
                if "Close" in df.columns.get_level_values(0):
                    close = df.xs("Close", axis=1, level=0, drop_level=True)
                    all_data.append(close)
                else:
                    # Fallback: use first level
                    df.columns = df.columns.get_level_values(0)
                    all_data.append(df)
            else:
                all_data.append(df)
        except Exception as e:
            print(f"  Batch {chunk} failed: {e}")
    if not all_data:
        return pd.DataFrame()
    combined = pd.concat(all_data, axis=1, join="outer")
    combined = combined.sort_index()
    combined = combined.dropna(axis=1, how="all")
    return combined


def generate_anchor_csv():
    """anchor_history.csv: 19 macro anchors, 5Y daily."""
    print("Fetching macro anchors (yfinance, 5Y)...")
    df = batch_download(ANCHORS, period="5y")
    if df.empty:
        print("FATAL: No anchor data from yfinance")
        return

    # Rename columns
    df.rename(columns=ANCHOR_RENAME, inplace=True)
    df.index.name = "date"
    df.index = pd.to_datetime(df.index)

    # Drop any unmapped columns (raw tickers that weren't renamed)
    for col in list(df.columns):
        if "=" in col or col.startswith("^"):
            df.drop(columns=[col], inplace=True)

    # Derive Cu/Au ratio
    if "Copper" in df.columns and "Gold" in df.columns:
        # Avoid divide-by-zero
        df["Cu_Au_Ratio"] = np.where(df["Gold"] > 0,
                                      df["Copper"] / df["Gold"] * 100,
                                      np.nan)

    df_out = df.reset_index()
    path = os.path.join(DATA_DIR, "anchor_history.csv")
    df_out.to_csv(path, index=False)
    print(f"✅ anchor_history.csv: {len(df_out)} rows x {len(df_out.columns)} cols "
          f"({os.path.getsize(path)/1024:.1f} KB)")
    print(f"   Date range: {df_out.date.min()} to {df_out.date.max()}")
    # Count rows where core columns are present
    core = ["USDINR", "Brent", "DXY", "IndiaVIX", "Gold"]
    present = df_out[core].notna().all(axis=1).sum()
    print(f"   Rows with all 5 core columns: {present}")


def generate_nifty_csv():
    """nifty_history.csv: Nifty OHLCV, 5Y daily."""
    print("\nFetching Nifty (yfinance, 5Y)...")
    t = yf.Ticker("^NSEI")
    h = t.history(period="5y", auto_adjust=True)
    if h.empty:
        print("FATAL: No Nifty data")
        return
    h.index.name = "date"
    h.index = pd.to_datetime(h.index)

    path = os.path.join(DATA_DIR, "nifty_history.csv")
    h.to_csv(path)
    print(f"✅ nifty_history.csv: {len(h)} rows x {len(h.columns)} cols "
          f"({os.path.getsize(path)/1024:.1f} KB)")
    print(f"   Date range: {h.index.min()} to {h.index.max()}")


def generate_fii_dii_csv():
    """fii_dii_history.csv: FII/DII net flows from Supabase + yfinance gap."""
    print("\nFetching FII/DII from Supabase...")
    from src.db import get_client
    db = get_client()
    if not db:
        print("  No Supabase connection")
        return

    try:
        result = db.table("fii_dii_flows").select("date, fiinet_cr, diinet_cr").order("date").execute()
        rows = result.data or []
        if rows:
            df = pd.DataFrame(rows)
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")
            # Rename to standard columns
            df.rename(columns={"fiinet_cr": "FII_Net_Cr", "diinet_cr": "DII_Net_Cr"}, inplace=True)
            path = os.path.join(DATA_DIR, "fii_dii_history.csv")
            df.to_csv(path, index=False)
            print(f"✅ fii_dii_history.csv: {len(df)} rows ({os.path.getsize(path)/1024:.1f} KB)")
            print(f"   Date range: {df.date.min()} to {df.date.max()}")
        else:
            print("  Empty result")
    except Exception as e:
        print(f"  Supabase error: {e}")


def main():
    generate_anchor_csv()
    generate_nifty_csv()
    generate_fii_dii_csv()
    print("\nDone. CSVs ready in data/")


if __name__ == "__main__":
    main()
