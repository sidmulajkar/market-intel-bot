"""
Data Staleness Detection — Check if NSE data is fresh.
Flag data older than expected threshold.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional


def check_data_staleness(data_timestamp: str, source: str = "NSE",
                          max_age_minutes: int = 30) -> Dict:
    """
    Check if data is stale based on timestamp.
    Returns staleness status and severity.
    """
    try:
        # Parse various timestamp formats
        for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
            try:
                data_time = datetime.strptime(data_timestamp, fmt)
                break
            except ValueError:
                continue
        else:
            return {"ok": True, "stale": False, "message": "Cannot parse timestamp", "severity": "UNKNOWN"}

        now = datetime.now()
        age_minutes = (now - data_time).total_seconds() / 60

        if age_minutes <= max_age_minutes:
            return {"ok": True, "stale": False, "age_minutes": round(age_minutes), "severity": "FRESH"}
        elif age_minutes <= max_age_minutes * 2:
            return {"ok": True, "stale": True, "age_minutes": round(age_minutes),
                    "severity": "WARNING", "message": f"Data is {age_minutes:.0f}min old (threshold: {max_age_minutes}min)"}
        else:
            return {"ok": True, "stale": True, "age_minutes": round(age_minutes),
                    "severity": "CRITICAL", "message": f"Data is {age_minutes:.0f}min old — possibly stale"}

    except Exception as e:
        return {"ok": False, "message": str(e)}


def check_batch_staleness(data_items: List[Dict]) -> Dict:
    """
    Check staleness for multiple data sources at once.
    data_items: [{"source": "NSE Options", "timestamp": "...", "max_age": 30}, ...]
    """
    results = []
    stale_count = 0

    for item in data_items:
        source = item.get("source", "Unknown")
        timestamp = item.get("timestamp", "")
        max_age = item.get("max_age", 30)

        check = check_data_staleness(timestamp, source, max_age)
        check["source"] = source
        results.append(check)
        if check.get("stale"):
            stale_count += 1

    return {
        "ok": True,
        "total": len(results),
        "stale_count": stale_count,
        "fresh_count": len(results) - stale_count,
        "results": results,
    }


def format_staleness(staleness: Dict) -> str:
    """Format staleness check for AI prompt."""
    if not staleness.get("ok"):
        return ""

    if staleness.get("stale_count", 0) == 0:
        return ""

    lines = ["[Data Staleness Alert]"]
    for r in staleness.get("results", []):
        if r.get("stale"):
            icon = "🔴" if r["severity"] == "CRITICAL" else "🟡"
            lines.append(f"  {icon} {r['source']}: {r['message']}")

    lines.append(f"\n  ⚠️ {staleness['stale_count']} data source(s) may be stale.")
    lines.append(f"  Analysis based on stale data may be inaccurate.")

    return "\n".join(lines)


if __name__ == "__main__":
    from datetime import datetime, timedelta
    now = datetime.now()
    items = [
        {"source": "NSE Options", "timestamp": (now - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S"), "max_age": 30},
        {"source": "FII Data", "timestamp": (now - timedelta(minutes=45)).strftime("%Y-%m-%d %H:%M:%S"), "max_age": 30},
    ]
    result = check_batch_staleness(items)
    print(format_staleness(result))
