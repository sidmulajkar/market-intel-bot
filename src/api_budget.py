"""
API Failure Budget Tracking — Persistent failure rate monitoring per source.
Tracks failures over time, alerts if reliability drops below threshold.
Uses bot_state table for persistence across runs.
"""
import json
from datetime import datetime
from typing import Dict, List, Optional
from src.db import get_bot_state, set_bot_state


def record_api_call(source: str, success: bool, error: str = None) -> bool:
    """
    Record an API call result (success/failure).
    Uses bot_state table for persistence.
    """
    key = f"api_budget_{source}"
    raw = get_bot_state(key)

    data = {"calls": [], "last_updated": datetime.now().isoformat()}
    if raw:
        try:
            data = json.loads(raw)
        except Exception:
            pass

    data["calls"].append({
        "success": success,
        "error": error,
        "timestamp": datetime.now().isoformat(),
    })

    # Keep only last 100 calls per source
    data["calls"] = data["calls"][-100:]

    set_bot_state(key, json.dumps(data))
    return True


def get_api_reliability(source: str, days: int = 7) -> Dict:
    """
    Get API reliability for a source over last N days.
    Returns success rate, total calls, failures.
    """
    key = f"api_budget_{source}"
    raw = get_bot_state(key)

    if not raw:
        return {"ok": True, "source": source, "reliability": None, "message": "No data yet"}

    try:
        data = json.loads(raw)
    except Exception:
        return {"ok": True, "source": source, "reliability": None, "message": "Corrupt data"}

    calls = data.get("calls", [])
    if not calls:
        return {"ok": True, "source": source, "reliability": None, "message": "No calls recorded"}

    # Filter to last N days
    cutoff = datetime.now().timestamp() - (days * 86400)
    recent_calls = []
    for c in calls:
        try:
            ts = datetime.fromisoformat(c["timestamp"]).timestamp()
            if ts >= cutoff:
                recent_calls.append(c)
        except Exception:
            continue

    if not recent_calls:
        return {"ok": True, "source": source, "reliability": None, "message": f"No calls in last {days} days"}

    total = len(recent_calls)
    successes = sum(1 for c in recent_calls if c.get("success"))
    failures = total - successes
    reliability = round((successes / total) * 100, 1)

    # Alert threshold
    if reliability < 80:
        alert = f"🔴 CRITICAL: {source} reliability {reliability}% — below 80% threshold"
    elif reliability < 90:
        alert = f"🟡 WARNING: {source} reliability {reliability}% — below 90% threshold"
    else:
        alert = f"✅ {source} reliability {reliability}% — healthy"

    return {
        "ok": True,
        "source": source,
        "reliability": reliability,
        "total_calls": total,
        "successes": successes,
        "failures": failures,
        "alert": alert,
        "period_days": days,
    }


def get_all_api_reliability(days: int = 7) -> Dict:
    """Get reliability for all tracked API sources."""
    sources = ["NSE_OPTIONS", "NSE_BREADTH", "NSE_FII", "YFINANCE", "GROQ", "GEMINI"]
    results = {}
    for source in sources:
        results[source] = get_api_reliability(source, days)
    return results


def format_api_budget(results: Dict) -> str:
    """Format API reliability for AI prompt."""
    if not results:
        return ""

    alerts = []
    for source, data in results.items():
        if data.get("reliability") is not None and data["reliability"] < 90:
            alerts.append(data.get("alert", ""))

    if not alerts:
        return ""

    lines = ["[API Reliability Alert]"]
    for alert in alerts:
        lines.append(f"  {alert}")

    lines.append(f"\n  Low reliability may indicate rate limiting or IP blocking.")
    lines.append(f"  Consider reducing request frequency or using fallback sources.")

    return "\n".join(lines)


if __name__ == "__main__":
    # Test (requires Supabase)
    record_api_call("NSE_OPTIONS", True)
    record_api_call("NSE_OPTIONS", True)
    record_api_call("NSE_OPTIONS", False, "403 Forbidden")
    result = get_api_reliability("NSE_OPTIONS")
    print(result)
