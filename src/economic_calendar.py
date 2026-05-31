"""
Economic Calendar Module (T3.1)
Loads curated CSV of Indian/global economic events.
Provides upcoming events, high-impact alerts, and formatted calendar blocks.
"""
import csv
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "econ_calendar_india_2026_27.csv")

IMPACT_EMOJI = {"H": "🔴", "M": "🟡", "L": "⚪"}
CATEGORY_EMOJI = {
    "RBI": "🏦",
    "CPI/WPI": "📈",
    "GDP": "📊",
    "Fiscal": "💰",
    "Global": "🌐",
    "Macro": "📋",
}


def load_calendar(csv_path: str = CSV_PATH) -> List[Dict]:
    """Load economic calendar from CSV."""
    if not os.path.exists(csv_path):
        print(f"⚠️ Calendar CSV not found: {csv_path}")
        return []
    events = []
    try:
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["date"] = row["date"].strip()
                row["event"] = row["event"].strip()
                row["category"] = row["category"].strip()
                row["impact"] = row["impact"].strip().upper()
                events.append(row)
        events.sort(key=lambda x: x["date"])
        return events
    except Exception as e:
        print(f"⚠️ Calendar load error: {e}")
        return []


def get_upcoming_events(days: int = 7, events: Optional[List[Dict]] = None) -> List[Dict]:
    """Filter events within the next N days, sorted by date then impact."""
    if events is None:
        events = load_calendar()
    if not events:
        return []
    today = datetime.now().strftime("%Y-%m-%d")
    cutoff = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    upcoming = [e for e in events if today <= e["date"] <= cutoff]
    impact_order = {"H": 0, "M": 1, "L": 2}
    upcoming.sort(key=lambda x: (x["date"], impact_order.get(x["impact"], 99)))
    return upcoming


def format_calendar(events: List[Dict], days: int = 7) -> str:
    """Format upcoming events into a compact calendar block."""
    if not events:
        return ""
    lines = [f"📅 Risk Calendar (Next {days}D)"]
    for e in events:
        emoji = IMPACT_EMOJI.get(e["impact"], "⚪")
        cat_emoji = CATEGORY_EMOJI.get(e["category"], "")
        lines.append(f"{emoji} {e['date'][5:]}: {cat_emoji} {e['event']}")
    return "\n".join(lines)


def get_high_impact_today(events: Optional[List[Dict]] = None) -> Optional[str]:
    """Return the first high-impact event happening today, or None."""
    if events is None:
        events = load_calendar()
    today = datetime.now().strftime("%Y-%m-%d")
    for e in events:
        if e["date"] == today and e["impact"] == "H":
            return e["event"]
    return None


def get_high_impact_tomorrow(events: Optional[List[Dict]] = None) -> Optional[str]:
    """Return the first high-impact event happening tomorrow, or None."""
    if events is None:
        events = load_calendar()
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    for e in events:
        if e["date"] == tomorrow and e["impact"] == "H":
            return e["event"]
    return None


def get_high_impact_soon(days: int = 2, events: Optional[List[Dict]] = None) -> Optional[str]:
    """Return the next high-impact event within N days, or None."""
    if events is None:
        events = load_calendar()
    upcoming = get_upcoming_events(days, events)
    for e in upcoming:
        if e["impact"] == "H":
            return e["event"]
    return None


def check_calendar_staleness(csv_path: str = CSV_PATH, max_age_days: int = 30) -> Optional[str]:
    """Check if calendar CSV needs updating — warning if last event is > N days from today."""
    if not os.path.exists(csv_path):
        return "⚠️ Calendar CSV not found"
    events = load_calendar(csv_path)
    if not events:
        return "⚠️ Calendar CSV empty"
    last = events[-1]
    last_date = last.get("date", "")
    if not last_date:
        return None
    try:
        dt = datetime.strptime(last_date, "%Y-%m-%d")
        days_until = (dt - datetime.now()).days
        if days_until < max_age_days:
            return f"⚠️ Calendar expires in {days_until}d — update CSV ({last_date})"
        return None
    except ValueError:
        return None
