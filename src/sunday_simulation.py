"""
Sunday Simulation — Pre-computes pillar_metrics + clone cache.
Runs 02:15 UTC Sunday after CSV consolidation (02:00 UTC).

CSV-First architecture: reads from CSV (stable 8 dims), computes pillar scores
for last 7 days, persists derived metrics to Supabase pillar_metrics table.
Pre-computes 2-tier clone distances and writes to clone_history as JSONB.

No AI. No yfinance on Sunday. Pure compute on committed CSV data.
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional


def get_last_7_trade_dates(df: pd.DataFrame) -> List[str]:
    """Get last 7 unique trade dates from a DataFrame with DatetimeIndex."""
    if df.empty:
        return []
    dates = sorted(df.index.unique())[-7:]
    return [str(d.date()) if hasattr(d, 'date') else str(d) for d in dates]


def derive_pillar_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived columns to anchor DataFrame (HYG/LQD, Cu/Au, SOXX/NQ).

    Returns None if all derived columns already exist (idempotent).
    """
    if "HYG" in df.columns and "LQD" in df.columns:
        if "Credit_Ratio" not in df.columns or df["Credit_Ratio"].isna().all():
            df["Credit_Ratio"] = df["HYG"] / df["LQD"]
    if "COPPER" in df.columns and "GOLD" in df.columns:
        if "Cu_Au_Ratio" not in df.columns or df["Cu_Au_Ratio"].isna().all():
            df["Cu_Au_Ratio"] = df["COPPER"] / df["GOLD"]
    if "SOXX" in df.columns and "NASDAQ" in df.columns:
        if "SOXX_NQ_Ratio" not in df.columns or df["SOXX_NQ_Ratio"].isna().all():
            df["SOXX_NQ_Ratio"] = df["SOXX"] / df["NASDAQ"]

    # Swap Cu_Au for COPPER/GOLD if ratio not computable
    if "Cu_Au_Ratio" not in df.columns:
        if "COPPER" in df.columns:
            df["Cu_Au_Ratio"] = df["COPPER"]
    if "SOXX_NQ_Ratio" not in df.columns:
        if "SOXX" in df.columns:
            df["SOXX_NQ_Ratio"] = df["SOXX"]

    return df


def compute_pillar_scores_for_dates(
    df: pd.DataFrame,
    trade_dates: List[str],
) -> List[Dict]:
    """Compute pillar scores for each trade date.

    Returns list of {trade_date, pillar_name, pillar_score, pillar_tier, dims}.
    """
    from src.pillar_classifier import classify_pillars

    all_dims = [
        "DXY", "US10Y", "Brent", "Gold", "USDINR", "IndiaVIX",
        "Credit_Ratio", "Cu_Au_Ratio", "SOXX_NQ_Ratio",
    ]

    for col in all_dims:
        if col in df.columns and df[col].notna().sum() > 10:
            df[f"{col}_pctile"] = df[col].expanding().rank(pct=True)

    results = []
    for td in trade_dates:
        try:
            row = df.loc[td]
        except (KeyError, TypeError):
            continue

        pctiles = {}
        for col in all_dims:
            pcol = f"{col}_pctile"
            if pcol in df.columns:
                val = row.get(pcol)
                if val is not None and not (isinstance(val, float) and np.isnan(val)):
                    pctiles[col] = val * 100

        if len(pctiles) < 3:
            continue

        pillars = classify_pillars(pctiles)
        for p in pillars:
            results.append({
                "trade_date": td,
                "pillar_name": p["name"],
                "pillar_score": p["score"],
                "pillar_tier": p["tier"],
                "active_dims": json.dumps(p["active_dims"]),
            })

    return results


def save_pillar_metrics(supabase, records: List[Dict]) -> bool:
    """Upsert pillar scores to Supabase pillar_metrics table."""
    if not records:
        return True
    try:
        supabase.table("pillar_metrics").upsert(
            records, on_conflict=["trade_date", "pillar_name"]
        ).execute()
        return True
    except Exception as e:
        print(f"⚠️ Failed to save pillar_metrics: {e}")
        return False


def compute_and_save_clone_cache(supabase) -> bool:
    """Pre-compute top-3 clones for current state, write to clone_history as JSONB.

    Uses CSV data. Writes to clone_history with clone_data: {top3: [...]} JSONB.
    """
    from src.clone_engine import find_clones, save_clones
    from src.csv_data import load_history

    df = load_history("anchors")
    if df.empty:
        return False

    # Get most recent row
    latest_idx = df["USDINR"].last_valid_index()
    if latest_idx is None:
        return False
    latest = df.loc[latest_idx]

    # Build current values
    current = {}
    for k, yf_key in [("vix", "^INDIAVIX"), ("usdinr", "USDINR=X"),
                       ("brent", "BZ=F"), ("dxy", "DX-Y.NYB"),
                       ("fii_5d", None), ("pcr", None)]:
        val = latest.get(yf_key) if yf_key else None
        if val is not None and not (isinstance(val, float) and np.isnan(val)):
            current[k] = float(val)

    if not all(current.get(k) for k in ["vix", "usdinr", "brent", "dxy"]):
        return False

    # Compute clones with No-AI extended pctile method
    clone_data = find_clones(
        current_vix=current["vix"],
        current_usdinr=current["usdinr"],
        current_brent=current["brent"],
        current_dxy=current["dxy"],
        current_fii_5d=current.get("fii_5d"),
        current_pcr=current.get("pcr"),
    )

    if clone_data.get("status") != "ok":
        return False

    return save_clones(supabase, clone_data, latest_idx.strftime("%Y-%m-%d"))


def run_sunday_simulation(supabase) -> Dict:
    """Main entry point for Sunday simulation workflow.

    1. Load CSV, compute derived metrics
    2. Score last 7 trade dates against 6 pillars
    3. Save pillar_metrics to Supabase
    4. Pre-compute clone cache and save

    Returns summary dict.
    """
    from src.csv_data import load_history

    df = load_history("anchors")
    if df.empty:
        return {"ok": False, "error": "Empty anchor CSV"}

    # 1. Derive metrics
    df = derive_pillar_metrics(df)
    trade_dates = get_last_7_trade_dates(df)
    print(f"📅 Computing pillar scores for {len(trade_dates)} trade dates")

    # 2. Score pillars
    records = compute_pillar_scores_for_dates(df, trade_dates)
    print(f"🏛️ {len(records)} pillar-day records computed")

    # 3. Save to Supabase
    if supabase and records:
        ok = save_pillar_metrics(supabase, records)
        if ok:
            print(f"✅ Pillar metrics saved to Supabase ({len(records)} rows)")
        else:
            print("⚠️ Pillar metrics save failed")

    # 4. Clone cache
    if supabase:
        clone_ok = compute_and_save_clone_cache(supabase)
        if clone_ok:
            print("✅ Clone cache saved")
        else:
            print("⚠️ Clone cache skipped (insufficient data)")

    return {
        "ok": True,
        "trade_dates": len(trade_dates),
        "pillar_records": len(records),
    }


if __name__ == "__main__":
    print("Sunday Simulation — Standalone execution")
    print("=" * 50)

    from src.db import get_client
    sb = get_client()
    if not sb:
        print("❌ Supabase connection failed")
        sys.exit(1)

    result = run_sunday_simulation(sb)
    print(f"\nResult: {json.dumps(result, indent=2)}")
