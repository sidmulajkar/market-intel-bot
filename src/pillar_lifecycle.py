"""
Pillar Lifecycle Tracker (Phase 4.2)
Tracks state transitions of each pillar: EMERGING → ESCALATING → SUSTAINED → DE-ESCALATING.

A pillar's meaning changes based on its age and trend direction.
This module reads pillar_metrics history from Supabase and computes lifecycle state.
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import statistics

# State definitions
EMERGING_DAYS = (1, 3)          # Days 1-3, could be noise
ESCALATING_TREND_DAYS = 3       # Need 3+ consecutive days of upward trend
SUSTAINED_MIN_DAYS = 5          # Day 5+ to be considered sustained
SUSTAINED_STABLE_RANGE = 3.0    # Within ±3 points for 3+ days
DE_ESCALATING_DROP_DAYS = 3     # Dropping for 3+ consecutive days
PEAK_LOOKBACK = 5               # Check last 5 days for peak
ACTIVE_SCORE_THRESHOLD = 40     # Must be >= 40 to be considered active


def compute_pillar_lifecycle(
    pillar_name: str,
    current_score: float,
    history: List[Dict],
) -> Dict:
    """Compute lifecycle state for a single pillar.

    Args:
        pillar_name: e.g., "STAGFLATION_SUPPLY"
        current_score: Current pillar score (0-100)
        history: List of dicts with 'trade_date', 'pillar_name', 'score'
                 from pillar_metrics table, sorted ascending by date.
                 Should include at least the last 30 days.

    Returns:
        Dict with state, age_days, peak_score, peak_date, trend_direction,
        formatted string for output.
    """
    pillar_history = [h for h in history if h.get("pillar_name") == pillar_name]
    pillar_history.sort(key=lambda x: x.get("trade_date", ""))

    age_days = _compute_age_days(pillar_name, pillar_history, current_score)
    peak_score, peak_date = _compute_peak(pillar_history, current_score)
    recent_trend = _compute_trend(pillar_history, PEAK_LOOKBACK)

    state = _classify_state(age_days, current_score, recent_trend, pillar_history)

    formatted = _format_lifecycle(state, age_days, peak_score, current_score)

    return {
        "ok": True,
        "pillar_name": pillar_name,
        "state": state,
        "age_days": age_days,
        "peak_score": round(peak_score, 1) if peak_score else None,
        "peak_date": peak_date,
        "trend_direction": recent_trend,
        "current_score": round(current_score, 1),
        "formatted": formatted,
    }


def _compute_age_days(
    pillar_name: str,
    pillar_history: List[Dict],
    current_score: float,
) -> int:
    """Estimate how many days the pillar has been active (score >= 40).

    If no history, assume Day 1 if currently active.
    """
    if current_score < ACTIVE_SCORE_THRESHOLD:
        return 0

    if not pillar_history:
        return 1

    active_days = 0
    for record in reversed(pillar_history):
        score = record.get("score", 0)
        if isinstance(score, (int, float)) and score >= ACTIVE_SCORE_THRESHOLD:
            active_days += 1
        else:
            break

    return max(1, active_days + 1)


def _compute_peak(
    pillar_history: List[Dict],
    current_score: float,
) -> Tuple[Optional[float], Optional[str]]:
    """Find peak score in recent history (last PEAK_LOOKBACK records + today)."""
    recent = pillar_history[-PEAK_LOOKBACK:] if len(pillar_history) >= PEAK_LOOKBACK else pillar_history
    all_scores = [r.get("score", 0) for r in recent if isinstance(r.get("score"), (int, float))]
    all_scores.append(current_score)

    if not all_scores:
        return None, None

    peak = max(all_scores)
    peak_idx = all_scores.index(peak)

    if peak_idx < len(recent):
        return peak, recent[peak_idx].get("trade_date")
    return peak, "today"


def _compute_trend(pillar_history: List[Dict], lookback: int = 5) -> str:
    """Compute trend direction: 'up', 'down', 'stable' based on recent scores."""
    recent = pillar_history[-lookback:] if len(pillar_history) >= lookback else pillar_history
    scores = [r.get("score", 0) for r in recent if isinstance(r.get("score"), (int, float))]

    if len(scores) < 3:
        return "stable"

    try:
        slope = scores[-1] - scores[0]
        if slope > 3.0:
            return "up"
        if slope < -3.0:
            return "down"
    except (IndexError, TypeError):
        pass

    return "stable"


def _classify_state(
    age_days: int,
    current_score: float,
    trend: str,
    pillar_history: List[Dict],
) -> str:
    """Classify pillar into lifecycle state based on age, score, and trend.

    States: EMERGING -> ESCALATING -> SUSTAINED -> DE-ESCALATING
    """
    if current_score < ACTIVE_SCORE_THRESHOLD:
        return "INACTIVE"

    # DE-ESCALATING: Net 3D drop > ±3, age >= 5
    # Uses net change instead of strict monotonic to avoid noise (Analyst 1 fix)
    if age_days >= SUSTAINED_MIN_DAYS and trend == "down":
        recent_scores = [r.get("score", 0) for r in pillar_history[-DE_ESCALATING_DROP_DAYS:]]
        if len(recent_scores) >= DE_ESCALATING_DROP_DAYS:
            net_change = current_score - recent_scores[0]
            if net_change <= -3.0:
                return "DE-ESCALATING"

    # SUSTAINED: Day 5+, trend stable (net change within ±3 over 3 days)
    if age_days >= SUSTAINED_MIN_DAYS and trend == "stable":
        return "SUSTAINED"

    # ESCALATING: Day 3+, trending up
    if age_days >= EMERGING_DAYS[1] and trend == "up":
        return "ESCALATING"

    # EMERGING: Days 1-3, score >= 40
    if age_days <= EMERGING_DAYS[1] and current_score >= ACTIVE_SCORE_THRESHOLD:
        return "EMERGING"

    # Default for 3+ days but no clear trend
    if age_days >= EMERGING_DAYS[1]:
        return "SUSTAINED"

    return "EMERGING"


def _format_lifecycle(state: str, age_days: int, peak_score: Optional[float], current_score: float) -> str:
    """Format lifecycle state for Telegram output.

    E.g. "ESCALATING (Day 4, Peak: 68)" or "SUSTAINED (Day 8, Peak: 65)"
    """
    if state == "INACTIVE":
        return ""

    parts = [state]
    if age_days > 0:
        parts.append(f"Day {age_days}")
    if peak_score and peak_score > current_score + 1:
        parts.append(f"Peak: {peak_score:.0f}")

    return " | ".join(parts)


def format_pillar_with_lifecycle(pillar: Dict, lifecycle: Dict) -> str:
    """Append lifecycle info to a single pillar's output line."""
    if not lifecycle.get("ok") or not lifecycle.get("formatted"):
        return ""
    lc = lifecycle["formatted"]
    return f"  📊 Lifecycle: {lc}"


def get_pillar_history_from_db(pillar_name: str, days: int = 30) -> List[Dict]:
    """Fetch pillar score history from Supabase pillar_metrics table."""
    try:
        from src.db import get_client
        db = get_client()
        if not db:
            return []
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        result = (
            db.table("pillar_metrics")
            .select("trade_date, pillar_name, score")
            .eq("pillar_name", pillar_name)
            .gte("trade_date", cutoff)
            .order("trade_date")
            .execute()
        )
        return result.data or []
    except Exception:
        return []
