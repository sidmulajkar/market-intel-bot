"""
historical_comparator.py — P9.2 /compare command
Loads anchor_history.csv for a specific date, compares side-by-side with current market_state.
No AI — pure CSV read + formatted output.
"""
from typing import Dict, List, Optional, Tuple
import os


CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "anchor_history.csv")


COMPARISON_METRICS = [
    ("^INDIAVIX", "India VIX"),
    ("BZ=F", "Brent"),
    ("CL=F", "WTI"),
    ("USDINR=X", "USD/INR"),
    ("DX-Y.NYB", "DXY"),
    ("^TNX", "US 10Y"),
    ("GC=F", "Gold"),
    ("HG=F", "Copper"),
    ("^VIX", "CBOE VIX"),
    ("HYG", "HYG"),
]


def load_history_for_date(target_date: str) -> Optional[Dict]:
    """Load anchor_history.csv row matching a specific date."""
    try:
        import pandas as pd
        df = pd.read_csv(CSV_PATH)
        if df.empty:
            return None

        date_col = None
        for c in ["date", "Date", "DATE", "timestamp"]:
            if c in df.columns:
                date_col = c
                break

        if not date_col:
            return None

        df[date_col] = pd.to_datetime(df[date_col]).dt.strftime("%Y-%m-%d")
        row = df[df[date_col] == target_date]
        if row.empty:
            return None

        return row.iloc[0].to_dict()
    except Exception as e:
        print(f"⚠️ load_history_for_date: {e}")
        return None


def get_current_values() -> Dict:
    """Pull current day's macro data from market_state."""
    try:
        from datetime import datetime
        from src.db import get_market_state

        today = datetime.now().strftime("%Y-%m-%d")
        state = get_market_state(today)
        if not state:
            return {}

        macro = state.get("macro", {})
        if not macro:
            return {}

        result = {}
        for symbol, _ in COMPARISON_METRICS:
            entry = macro.get(symbol, {})
            if isinstance(entry, dict):
                price = entry.get("price")
            else:
                price = entry
            if price is not None:
                try:
                    result[symbol] = float(price)
                except (ValueError, TypeError):
                    pass
        return result
    except Exception as e:
        print(f"⚠️ get_current_values: {e}")
        return {}


def format_comparison(target_date: str) -> str:
    """Build side-by-side comparison for Telegram."""
    hist = load_history_for_date(target_date)
    if not hist:
        return f"⚠️ No historical data for *{target_date}*"

    current = get_current_values()

    msg = (
        f"📅 *Historical Comparison*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Date: {target_date} vs Today\n\n"
    )

    rows = []
    for symbol, label in COMPARISON_METRICS:
        hist_val = hist.get(symbol)
        if hist_val is not None:
            try:
                hist_val = float(hist_val)
            except (ValueError, TypeError):
                hist_val = None
        curr_val = current.get(symbol)

        if hist_val is None and curr_val is None:
            continue

        hist_str = f"{hist_val:,.2f}" if hist_val is not None else "N/A"
        curr_str = f"{curr_val:,.2f}" if curr_val is not None else "N/A"

        if hist_val is not None and curr_val is not None:
            diff = ((curr_val - hist_val) / abs(hist_val)) * 100 if hist_val != 0 else 0
            diff_str = f"{diff:+.1f}%" if abs(diff) > 0.1 else ""
            emoji = "🟢" if diff < 0 and symbol in {"USDINR=X", "BZ=F", "^INDIAVIX", "^VIX", "CL=F", "DX-Y.NYB", "^TNX"} else ("🔴" if diff > 0 else "⚪")
        else:
            diff_str = ""
            emoji = "⚪"

        rows.append(f"{emoji} {label}: {hist_str} → {curr_str}  {diff_str}")

    if not rows:
        return f"⚠️ No matching metrics for *{target_date}*"

    msg += "\n".join(rows[:12])
    msg += f"\n\n_Source: anchor_history.csv + current market_state_"
    return msg
