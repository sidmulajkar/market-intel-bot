"""
Event Volatility Profiler — Map historical market behavior to upcoming calendar events.
Transforms a calendar warning into a statistical fact.

Data flow:
1. Upcoming event (within 7 days) found in economic_calendar CSV
2. Look up historical occurrences by event label in anchor_history.csv
3. Compute Nifty absolute return (T-0, T+1, T+2) and VIX change (T-2 to T+2)
4. Minimum sample size: 3 occurrences. If fewer, suppress.

Output: "RBI MPC (Jun 4): Avg Nifty move ±0.9% (n=8) | VIX typically falls 1.2pts post-decision"
"""

import csv
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple


# Paths
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
CALENDAR_PATH = os.path.join(DATA_DIR, "econ_calendar_india_2026_27.csv")
NIFTY_HISTORY_PATH = os.path.join(DATA_DIR, "nifty_history.csv")
ANCHOR_HISTORY_PATH = os.path.join(DATA_DIR, "anchor_history.csv")


def load_calendar() -> List[Dict]:
    """Load the economic calendar CSV and return all events as dicts."""
    if not os.path.exists(CALENDAR_PATH):
        return []
    try:
        with open(CALENDAR_PATH, "r") as f:
            return list(csv.DictReader(f))
    except Exception as e:
        print(f"⚠️ event_volatility: calendar load error: {e}")
        return []


def load_nifty_history() -> List[Dict]:
    """Load Nifty history CSV for computing returns."""
    if not os.path.exists(NIFTY_HISTORY_PATH):
        return []
    try:
        with open(NIFTY_HISTORY_PATH, "r") as f:
            rows = list(csv.DictReader(f))
        # Normalize date format
        for r in rows:
            r["date"] = r.get("date", "")[:10]
        return rows
    except Exception as e:
        print(f"⚠️ event_volatility: nifty history load error: {e}")
        return []


def load_anchor_history() -> List[Dict]:
    """Load anchor history CSV for VIX data."""
    if not os.path.exists(ANCHOR_HISTORY_PATH):
        return []
    try:
        with open(ANCHOR_HISTORY_PATH, "r") as f:
            rows = list(csv.DictReader(f))
        for r in rows:
            r["date"] = r.get("date", "")[:10]
        return rows
    except Exception as e:
        print(f"⚠️ event_volatility: anchor history load error: {e}")
        return []


# ── Event Date Generators ──────────────────────────────────────────────────────
# Each generator returns a list of historical dates (YYYY-MM-DD) for a given event type.

_EVENT_DATE_CACHE: Dict[str, List[str]] = {}


def _month_number(month_abbr: str) -> int:
    months = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    return months.get(month_abbr.lower()[:3], 0)


def _find_nearest_trade_date(target_date_str: str, nifty_data: List[Dict], lookback: int = 3) -> Optional[str]:
    """Find the nearest trading date to a target date, within lookback days."""
    target = datetime.strptime(target_date_str, "%Y-%m-%d")
    trade_dates = {r["date"] for r in nifty_data if r.get("date")}

    for offset in range(lookback + 1):
        for sign in [1, -1]:
            if offset == 0 and sign == -1:
                continue
            check = (target + timedelta(days=offset * sign)).strftime("%Y-%m-%d")
            if check in trade_dates:
                return check
    return None


def _get_historical_anchor_value(date_str: str, anchor_data: List[Dict], field: str) -> Optional[float]:
    """Get a specific field value from anchor_history for a given date."""
    for r in anchor_data:
        if r.get("date") == date_str:
            try:
                return float(r.get(field, 0) or 0)
            except (ValueError, TypeError):
                return None
    return None


def _get_nifty_close(date_str: str, nifty_data: List[Dict]) -> Optional[float]:
    """Get Nifty close price for a given date."""
    for r in nifty_data:
        if r.get("date") == date_str:
            try:
                return float(r.get("Close", 0) or 0)
            except (ValueError, TypeError):
                return None
    return None


def _generate_rbi_mpc_dates() -> List[str]:
    """RBI MPC decisions: typically every 2 months on Wed/Thu.
    Known historical dates from 2021-2026 cycle."""
    # RBI MPC scheduled bi-monthly: Apr, Jun, Aug, Oct, Dec, Feb
    # Decision usually released on the 2nd day (Friday) of the meeting
    # Known dates from 2021-2026:
    known_dates = [
        "2021-04-07", "2021-06-04", "2021-08-06", "2021-10-08", "2021-12-08",
        "2022-02-10", "2022-04-08", "2022-06-08", "2022-08-05", "2022-09-30",
        "2022-12-07", "2023-02-08", "2023-04-06", "2023-06-08", "2023-08-10",
        "2023-10-06", "2023-12-08", "2024-02-08", "2024-04-05", "2024-06-07",
        "2024-08-08", "2024-10-09", "2024-12-06", "2025-02-07", "2025-04-09",
        "2025-06-06", "2025-08-06", "2025-10-08", "2025-12-05", "2026-02-06",
        "2026-04-08",
    ]
    return known_dates


def _generate_us_fomc_dates() -> List[str]:
    """US FOMC decisions: typically every 6 weeks.
    Known schedule from 2021-2026."""
    known_dates = [
        "2021-01-27", "2021-03-17", "2021-04-28", "2021-06-16", "2021-07-28",
        "2021-09-22", "2021-11-03", "2021-12-15",
        "2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15", "2022-07-27",
        "2022-09-21", "2022-11-02", "2022-12-14",
        "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14", "2023-07-26",
        "2023-09-20", "2023-11-01", "2023-12-13",
        "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12", "2024-07-31",
        "2024-09-18", "2024-11-07", "2024-12-18",
        "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30",
        "2025-09-17", "2025-11-05", "2025-12-17",
        "2026-01-28", "2026-03-18", "2026-05-06",
    ]
    return known_dates


def _generate_us_nfp_dates() -> List[str]:
    """US NFP (Non-Farm Payrolls): First Friday of each month."""
    from calendar import monthrange
    dates = []
    for year in range(2021, 2027):
        for month in range(1, 13):
            # First Friday
            first_day = datetime(year, month, 1)
            # Day of week: Monday=0, Friday=4
            days_to_friday = (4 - first_day.weekday()) % 7
            first_friday = first_day + timedelta(days=days_to_friday)
            dates.append(first_friday.strftime("%Y-%m-%d"))
    return dates


def _generate_monthly_data_event(base_name: str, day_of_month: int) -> List[str]:
    """Generate dates for monthly data releases (CPI, WPI, IIP, etc.) on a specific day."""
    dates = []
    for year in range(2021, 2027):
        for month in range(1, 13):
            try:
                d = datetime(year, month, min(day_of_month, 28))
                dates.append(d.strftime("%Y-%m-%d"))
            except ValueError:
                pass
    return dates


def _get_historical_dates_for_event(base_event: str) -> List[str]:
    """Get historical dates for a given base event name (month suffix stripped)."""
    cache_key = base_event.lower().strip()
    if cache_key in _EVENT_DATE_CACHE:
        return _EVENT_DATE_CACHE[cache_key]

    be = base_event.upper().strip()

    if "RBI MPC" in be:
        dates = _generate_rbi_mpc_dates()
    elif "FOMC" in be:
        dates = _generate_us_fomc_dates()
    elif "NFP" in be or "NON-FARM" in be or "NONFARM" in be:
        dates = _generate_us_nfp_dates()
    elif "CPI" in be:
        # India CPI: 12th of month, US CPI: 10-14th
        if "US" in be:
            dates = _generate_monthly_data_event("CPI", 13)
        else:
            dates = _generate_monthly_data_event("CPI", 12)
    elif "WPI" in be:
        dates = _generate_monthly_data_event("WPI", 14)
    elif "IIP" in be:
        dates = _generate_monthly_data_event("IIP", 10)
    elif "PMI" in be:
        dates = _generate_monthly_data_event("PMI", 1)
    elif "TRADE" in be:
        dates = _generate_monthly_data_event("Trade", 15)
    elif "BUDGET" in be:
        # India Union Budget: Feb 1
        dates = [f"{y}-02-01" for y in range(2021, 2027)]
    elif "GDP" in be:
        # Quarterly GDP release: Feb 28, May 31, Aug 31, Nov 30 (approx)
        months_q = {"Q1": "06-01", "Q2": "09-01", "Q3": "12-01", "Q4": "03-01"}
        dates = []
        for y in range(2021, 2027):
            for q, m in months_q.items():
                if q in be:
                    dates.append(f"{y}-{m}")
    else:
        dates = []

    _EVENT_DATE_CACHE[cache_key] = dates
    return dates


def strip_month_suffix(event_label: str) -> str:
    """Strip month suffix from event label to get base event name.
    E.g., 'India CPI (May)' → 'India CPI'"""
    return re.sub(r"\s*\((Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\)", "", event_label).strip()


def compute_event_volatility(event_label: str, event_date: str) -> Dict:
    """
    Compute historical volatility profile for an event.

    Args:
        event_label: Full event label from calendar (e.g., "RBI MPC Decision")
        event_date: Date string (YYYY-MM-DD) of the upcoming event

    Returns:
        Dict with avg_nifty_move, vix_change, sample_size, profile
    """
    nifty_data = load_nifty_history()
    anchor_data = load_anchor_history()

    if not nifty_data:
        return {"ok": False, "message": "No Nifty history data"}

    # Get base event name
    base_event = strip_month_suffix(event_label)

    # Get historical dates for this event type
    hist_dates = _get_historical_dates_for_event(base_event)

    # Filter to dates within our data range
    data_start = nifty_data[0]["date"] if nifty_data else "2020-01-01"
    data_end = nifty_data[-1]["date"] if nifty_data else "2030-01-01"
    hist_dates = [d for d in hist_dates if data_start <= d <= data_end]

    if not hist_dates:
        return {"ok": False, "message": f"No historical dates for '{base_event}'"}

    # Compute statistics for each occurrence
    nifty_abs_returns = []
    vix_changes = []
    sample_count = 0

    # Find nearest trade dates
    trade_dates = sorted({r["date"] for r in nifty_data if r.get("date")})
    trade_date_set = set(trade_dates)

    for hist_date in hist_dates:
        # Find nearest trading day
        t0 = _find_nearest_trade_date(hist_date, nifty_data)
        if not t0:
            continue

        # Get T+1, T+2 trade dates
        t0_idx = -1
        for i, d in enumerate(trade_dates):
            if d == t0:
                t0_idx = i
                break

        if t0_idx < 0:
            continue

        t1 = trade_dates[t0_idx + 1] if t0_idx + 1 < len(trade_dates) else None
        t2 = trade_dates[t0_idx + 2] if t0_idx + 2 < len(trade_dates) else None

        # Get T-2 date (pre-event)
        t_minus2 = trade_dates[t0_idx - 2] if t0_idx >= 2 else None

        if not t1:
            continue

        # Nifty close prices
        close_t0 = _get_nifty_close(t0, nifty_data)
        close_t1 = _get_nifty_close(t1, nifty_data)

        if close_t0 and close_t1 and close_t0 > 0:
            abs_return = abs((close_t1 - close_t0) / close_t0 * 100)
            nifty_abs_returns.append(abs_return)

            # VIX change (T-2 to T+2)
            if t_minus2 and t2 and anchor_data:
                vix_pre = _get_historical_anchor_value(t_minus2, anchor_data, "IndiaVIX")
                vix_post = _get_historical_anchor_value(t2, anchor_data, "IndiaVIX")
                if vix_pre is not None and vix_post is not None:
                    vix_changes.append(vix_post - vix_pre)

            sample_count += 1

    if sample_count < 3:
        return {
            "ok": False,
            "message": f"Insufficient historical data for '{base_event}' (n={sample_count}, min 3)",
            "sample_size": sample_count,
        }

    # Compute statistics
    avg_nifty_move = round(sum(nifty_abs_returns) / len(nifty_abs_returns), 1) if nifty_abs_returns else 0
    max_nifty_move = round(max(nifty_abs_returns), 1) if nifty_abs_returns else 0
    avg_vix_change = round(sum(vix_changes) / len(vix_changes), 1) if vix_changes else 0

    # VIX typically rises/falls
    if avg_vix_change < -0.5:
        vix_profile = f"VIX typically falls {abs(avg_vix_change):.1f}pts post-decision"
    elif avg_vix_change > 0.5:
        vix_profile = f"VIX typically rises {avg_vix_change:.1f}pts post-decision"
    else:
        vix_profile = "VIX typically stable post-decision"

    return {
        "ok": True,
        "event_label": event_label,
        "event_date": event_date,
        "base_event": base_event,
        "sample_size": sample_count,
        "avg_nifty_move_pct": avg_nifty_move,
        "max_nifty_move_pct": max_nifty_move,
        "avg_vix_change_pts": avg_vix_change,
        "vix_profile": vix_profile,
        "profile": f"Avg Nifty move ±{avg_nifty_move}% (n={sample_count}) | {vix_profile}",
    }


def scan_upcoming_events(days_ahead: int = 7) -> List[Dict]:
    """
    Scan economic calendar for upcoming events and compute volatility profiles.

    Returns list of event volatility dicts (only those with sufficient data).
    """
    calendar = load_calendar()
    if not calendar:
        return []

    today = datetime.now().strftime("%Y-%m-%d")
    cutoff = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    # Filter upcoming high-impact events
    upcoming = [
        r for r in calendar
        if today <= r.get("date", "")[:10] <= cutoff
        and r.get("impact", "") in ("H", "M")  # High or Medium impact
    ]

    if not upcoming:
        return []

    results = []
    for event in upcoming:
        label = event.get("event", "")
        date = event.get("date", "")[:10]
        result = compute_event_volatility(label, date)
        if result.get("ok"):
            result["impact"] = event.get("impact", "")
            result["category"] = event.get("category", "")
            results.append(result)
        # Silently skip events without enough data

    return results


def format_event_volatility(profiles: List[Dict]) -> str:
    """Format event volatility profiles for AI prompt injection."""
    if not profiles:
        return ""

    lines = [f"[Upcoming Event Volatility Profiles]"]
    for p in profiles:
        date_display = datetime.strptime(p["event_date"], "%Y-%m-%d").strftime("%b %d")
        lines.append(
            f"  {p['event_label']} ({date_display}): "
            f"{p['profile']}"
        )

    return "\n".join(lines)


if __name__ == "__main__":
    profiles = scan_upcoming_events(days_ahead=7)
    print(format_event_volatility(profiles))
