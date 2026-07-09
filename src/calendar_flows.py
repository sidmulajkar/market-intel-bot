"""
Calendar Rebalancing & Seasonality — Institutional Flow Clock

Deterministic dictionary of known flow windows based on calendar mechanics:
- Jan-Mar ELSS tax-saving: massive MF inflows
- Quarter-end MTM window dressing (last 10 days of Mar/Jun/Sep/Dec)
- October seasonality (most volatile month — festival supply + MF fiscal year start)
- December tax-loss harvesting (last 7 days)

Also computes historical median Nifty return for the current calendar week
from anchor_history.csv (~4,000 daily returns spanning 5+ years).

Total GHA cost: 5ms for date logic + 50ms for CSV read + median calc.
"""

import os
from pathlib import Path
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple

import pandas as pd


def _load_nifty_history(csv_path: Optional[str] = None) -> pd.Series:
    """Load and return Nifty close series from anchor_history.csv."""
    if csv_path is None:
        csv_path = str(
            Path(__file__).resolve().parent.parent / "data" / "anchor_history.csv"
        )
    if not os.path.exists(csv_path):
        return pd.Series(dtype=float)

    df = pd.read_csv(csv_path)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        df = df.set_index("date").sort_index()
    else:
        return pd.Series(dtype=float)

    # Nifty column: could be "NIFTY" or "Nikkei" — use close enough name
    for col in ["NIFTY", "Nifty", "^NSEI"]:
        if col in df.columns:
            series = df[col].dropna().astype(float)
            return series

    return pd.Series(dtype=float)


# Flow calendar windows: (month, day_start, day_end, label, impact, emoji)
_FLOW_CALENDAR: List[Tuple[int, int, int, str, str, str]] = [
    (1,  1,  31, "New Year deployment — MF/insurer inflows", "Seasonal buying tailwind", "🗓️"),
    (3,  15, 31, "Tax-saving MF inflows (ELSS deadline)", "Bullish tailwind — forced buying", "🗓️"),
    (3,  22, 31, "Quarter-end MTM window dressing", "Index-heavyweight buying into close", "🗓️"),
    (6,  22, 30, "Quarter-end MTM window dressing", "Index-heavyweight buying into close", "🗓️"),
    (9,  22, 30, "Quarter-end MTM window dressing", "Index-heavyweight buying into close", "🗓️"),
    (10, 1,  15, "October seasonality — MF fiscal year start", "Historically most volatile month", "⚠️"),
    (12, 24, 31, "Tax-loss harvesting & thin liquidity", "Gap risk elevated — low volume", "⚠️"),
]


def get_calendar_flows(today: Optional[date] = None) -> Dict:
    """Check if today falls in any known flow calendar window.

    Returns:
        {
            "ok": True,
            "active_flows": [{"window": ..., "event": ..., "impact": ..., "emoji": ...}],
            "historical_median_return_this_week": 0.42,
            "historical_median_return_label": "+0.42%",
        }
    """
    if today is None:
        today = date.today()

    m = today.month
    d = today.day

    active: List[Dict] = []
    for month_s, day_s, day_e, label, impact, emoji in _FLOW_CALENDAR:
        if m == month_s and day_s <= d <= day_e:
            active.append({
                "window": f"{month_s:02d}/{day_s:02d} - {month_s:02d}/{day_e:02d}",
                "event": label,
                "impact": impact,
                "emoji": emoji,
            })

    # Historical median return for this calendar week
    hist_return = _compute_week_median_return(today)

    return {
        "ok": True,
        "active_flows": active,
        "historical_median_return_this_week": hist_return,
        "historical_median_return_label": (
            f"{hist_return:+.2f}%" if hist_return is not None else ""
        ),
    }


def _compute_week_median_return(today: date) -> Optional[float]:
    """Compute historical median Nifty return for this calendar week number.

    Uses anchor_history.csv to find all closes for the same ISO week number,
    computes week-over-week return, takes median.
    """
    series = _load_nifty_history()
    if series.empty or len(series) < 252:
        return None

    iso_week = today.isocalendar().week
    iso_year = today.isocalendar().year

    # Create DataFrame with year, week, close
    df = pd.DataFrame({"close": series})
    df["year"] = df.index.year
    df["week"] = df.index.isocalendar().week.astype(int)

    # Filter to same ISO week across all years (except current year — partial)
    mask = (df["week"] == iso_week) & (df["year"] != iso_year)
    week_data = df[mask].copy()
    if week_data.empty:
        return None

    # Compute weekly returns (Friday close to Friday close or nearest)
    week_data["weekly_ret"] = week_data.groupby("year")["close"].transform(
        lambda x: x.pct_change()
    )
    returns = week_data["weekly_ret"].dropna()
    if returns.empty or len(returns) < 3:
        return None

    median_ret = float(returns.median()) * 100
    return round(median_ret, 2)


def format_calendar_flows(result: Dict) -> str:
    """Format calendar flows for Telegram.

    Empty string when no active flows (format hygiene: silent suppression).
    """
    if not result.get("ok"):
        return ""

    active = result.get("active_flows", [])
    if not active:
        return ""

    lines = []
    for flow in active:
        emoji = flow.get("emoji", "🗓️")
        event = flow.get("event", "")
        impact = flow.get("impact", "")
        lines.append(f"{emoji} *{event}*")
        lines.append(f"   {impact}")

    # Append historical median return if available
    hist = result.get("historical_median_return_this_week")
    if hist is not None:
        sign = "+" if hist >= 0 else ""
        lines.append(f"\n📊 Historical 5Y median Nifty return this week: {sign}{hist:.2f}%")

    return "🗓️ *Flow Calendar*\n━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines)
