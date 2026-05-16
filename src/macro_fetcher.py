"""
Macro Fetcher — Indian macroeconomic indicators and calendar
Sources: RBI (MIBOR, repo rate), config/macro_calendar.json (events)
"""
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# MACRO CALENDAR — Block 9
# ═══════════════════════════════════════════════════════════════════════════════

def load_macro_calendar() -> List[Dict]:
    """Load macro events from config/macro_calendar.json."""
    cal_path = os.path.join(os.path.dirname(__file__), "..", "config", "macro_calendar.json")
    try:
        with open(cal_path, "r") as f:
            data = json.load(f)
        return data.get("events", [])
    except Exception as e:
        print(f"⚠️ load_macro_calendar: {e}")
        return []


def get_upcoming_events(days: int = 7) -> List[Dict]:
    """Get macro events in the next N days."""
    events = load_macro_calendar()
    if not events:
        return []

    today = datetime.now().date()
    cutoff = today + timedelta(days=days)

    upcoming = []
    for e in events:
        try:
            event_date = datetime.strptime(e["date"], "%Y-%m-%d").date()
            if today <= event_date <= cutoff:
                days_away = (event_date - today).days
                e["days_away"] = days_away
                upcoming.append(e)
        except (ValueError, KeyError):
            continue

    # Sort by date
    upcoming.sort(key=lambda x: x["date"])
    return upcoming


def format_macro_calendar(days: int = 7) -> str:
    """Format upcoming macro events for Block 9."""
    events = get_upcoming_events(days)

    if not events:
        return ""

    lines = ["[Macro Calendar — Next 7 Days]"]
    impact_icons = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}

    for e in events:
        icon = impact_icons.get(e.get("impact", "MEDIUM"), "⚪")
        date_str = e["date"]
        event = e["event"]
        prev = e.get("previous", "")
        days_away = e.get("days_away", 0)

        day_label = "today" if days_away == 0 else "tomorrow" if days_away == 1 else f"in {days_away}d"

        line = f"{icon} {date_str}: {event}"
        if prev and prev != "TBD":
            line += f" — prev {prev}"
        line += f" | {e.get('impact', '')} | {day_label}"
        lines.append(line)

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# RBI POLICY — Real Rate Tracker
# ═══════════════════════════════════════════════════════════════════════════════

# Current RBI policy state — update when MPC announces
RBI_POLICY = {
    "repo_rate": 6.00,
    "stance": "ACCOMMODATIVE",
    "last_mpc_date": "2026-04-09",
    "last_action": "CUT 25bps",
    "crr": 4.00,
    "slr": 18.00,
}


def get_stored_cpi() -> float:
    """Get last known CPI from Supabase bot_state, fall back to default."""
    try:
        from src.db import get_client
        db = get_client()
        if db:
            result = db.table("bot_state").select("value").eq("key", "last_cpi").limit(1).execute()
            if result.data:
                return float(result.data[0]["value"])
    except Exception:
        pass
    return 3.34  # Default fallback


def store_cpi(cpi_value: float) -> bool:
    """Store CPI value in Supabase bot_state for future use."""
    try:
        from src.db import get_client
        db = get_client()
        if db:
            db.table("bot_state").upsert({
                "key": "last_cpi",
                "value": str(cpi_value),
                "updated_at": datetime.now().isoformat(),
            }).execute()
            return True
    except Exception:
        pass
    return False


def compute_real_rate(cpi_inflation: float = None) -> Dict:
    """
    Compute real interest rate = repo rate - CPI inflation.
    Positive = restrictive (tight). Negative = loose (accommodative for equities).
    """
    repo = RBI_POLICY["repo_rate"]

    if cpi_inflation is None:
        cpi_inflation = get_stored_cpi()

    real_rate = round(repo - cpi_inflation, 2)

    if real_rate > 2:
        label = "VERY TIGHT — restrictive for equities"
    elif real_rate > 1:
        label = "TIGHT — moderately restrictive"
    elif real_rate > 0:
        label = "MILDLY POSITIVE — neutral"
    elif real_rate > -1:
        label = "NEGATIVE — supportive for equities"
    else:
        label = "VERY NEGATIVE — highly accommodative"

    return {
        "ok": True,
        "repo_rate": repo,
        "cpi": cpi_inflation,
        "real_rate": real_rate,
        "label": label,
        "stance": RBI_POLICY["stance"],
    }


def format_rbi_policy() -> str:
    """Format RBI policy status for prompt injection."""
    real = compute_real_rate()

    lines = ["[RBI Policy]"]
    lines.append(f"Repo Rate: {real['repo_rate']}% | Stance: {real['stance']}")
    lines.append(f"Real Rate: {real['real_rate']:+.2f}% (repo {real['repo_rate']}% - CPI {real['cpi']}%)")
    lines.append(f"→ {real['label']}")
    lines.append(f"Last Action: {RBI_POLICY['last_action']} ({RBI_POLICY['last_mpc_date']})")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# COMBINED MACRO BLOCK
# ═══════════════════════════════════════════════════════════════════════════════

def format_macro_block() -> str:
    """Format complete macro intelligence block (calendar + RBI policy)."""
    parts = []

    # Macro Calendar
    cal = format_macro_calendar(days=7)
    if cal:
        parts.append(cal)

    # RBI Policy
    rbi = format_rbi_policy()
    if rbi:
        parts.append(rbi)

    return "\n\n".join(parts) if parts else ""
