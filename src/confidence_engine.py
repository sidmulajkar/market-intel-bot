"""
Confidence Engine — Uncertainty quantification.
Bot knows when NOT to predict. Outputs confidence intervals.

LOW CONFIDENCE conditions:
  - Contradiction level HIGH
  - Active signal count < 3
  - Key data source failed
  - Historical scenario match < 5 comparable periods
  - Upcoming event within 2 days
"""
import statistics
from typing import Dict, List, Optional


def compute_confidence(arbitration: Dict = None, scenario: Dict = None,
                        active_signals: int = 0, data_failures: List[str] = None,
                        upcoming_events: List[Dict] = None) -> Dict:
    """
    Compute prediction confidence based on multiple factors.
    Returns confidence level and reasoning.
    """
    reasons = []
    confidence_score = 100  # Start perfect, deduct for issues

    # 1. Contradiction level
    if arbitration:
        contradiction = arbitration.get("contradiction_level", "LOW")
        if contradiction in ("VERY HIGH", "HIGH"):
            confidence_score -= 30
            reasons.append(f"Signal contradiction: {contradiction} (spread: {arbitration.get('spread', 0)}pts)")
        elif contradiction == "MODERATE":
            confidence_score -= 15
            reasons.append(f"Moderate signal contradiction")

    # 2. Active signal count
    if active_signals < 3:
        confidence_score -= 25
        reasons.append(f"Insufficient signals: only {active_signals} active")
    elif active_signals < 5:
        confidence_score -= 10
        reasons.append(f"Limited signals: {active_signals} active")

    # 3. Data failures
    if data_failures:
        penalty = min(20, len(data_failures) * 10)
        confidence_score -= penalty
        reasons.append(f"Data failures: {', '.join(data_failures)}")

    # 4. Scenario match quality
    if scenario:
        matches = scenario.get("matches", 0)
        if matches < 5:
            confidence_score -= 20
            reasons.append(f"Limited historical matches: {matches} periods")
        elif matches < 10:
            confidence_score -= 5
            reasons.append(f"Moderate historical matches: {matches} periods")

    # 5. Upcoming events
    if upcoming_events:
        near_events = [e for e in upcoming_events if e.get("days_until", 99) <= 2]
        if near_events:
            confidence_score -= 20
            event_names = [e.get("event", "unknown") for e in near_events]
            reasons.append(f"Pre-event uncertainty: {', '.join(event_names)}")

    # Clamp to 0-100
    confidence_score = max(0, min(100, confidence_score))

    # Classify
    if confidence_score >= 75:
        level = "HIGH"
        recommendation = "Full conviction in signal."
    elif confidence_score >= 50:
        level = "MEDIUM"
        recommendation = "Moderate conviction. Consider position sizing."
    elif confidence_score >= 30:
        level = "LOW"
        recommendation = "Low conviction. Reduce position sizing. Wait for clarity."
    else:
        level = "VERY LOW"
        recommendation = "DO NOT TRADE. Insufficient confidence. Wait for signal convergence."

    return {
        "ok": True,
        "confidence_score": confidence_score,
        "level": level,
        "recommendation": recommendation,
        "reasons": reasons,
    }


def compute_confidence_interval(scenario: Dict, volatility: float = None) -> Dict:
    """
    Compute confidence interval on predicted move from scenario matching.
    Uses matched historical outcomes to compute 70% CI.
    """
    if not scenario or not scenario.get("ok"):
        return {"ok": False, "message": "No scenario data"}

    match_details = scenario.get("match_details", [])
    if not match_details:
        return {"ok": False, "message": "No match details"}

    # Extract forward returns from matches
    returns_5d = []
    returns_10d = []
    returns_20d = []

    for m in match_details:
        fwd = m.get("fwd_returns", {})
        if fwd.get("5d") is not None:
            returns_5d.append(fwd["5d"])
        if fwd.get("10d") is not None:
            returns_10d.append(fwd["10d"])
        if fwd.get("20d") is not None:
            returns_20d.append(fwd["20d"])

    intervals = {}
    for period, returns in [("5d", returns_5d), ("10d", returns_10d), ("20d", returns_20d)]:
        if len(returns) >= 3:
            sorted_returns = sorted(returns)
            n = len(sorted_returns)
            # 70% CI: trim 15% from each end
            lower_idx = max(0, int(n * 0.15))
            upper_idx = min(n - 1, int(n * 0.85))
            intervals[period] = {
                "expected": round(statistics.mean(returns), 2),
                "ci_lower": round(sorted_returns[lower_idx], 2),
                "ci_upper": round(sorted_returns[upper_idx], 2),
                "worst": round(min(returns), 2),
                "best": round(max(returns), 2),
                "n_matches": len(returns),
            }

    return {"ok": bool(intervals), "intervals": intervals}


def format_confidence(confidence: Dict, intervals: Dict = None) -> str:
    """Format confidence for AI prompt."""
    if not confidence.get("ok"):
        return ""

    lines = [f"[Confidence Assessment: {confidence['confidence_score']}/100 — {confidence['level']}]"]
    lines.append(f"  {confidence['recommendation']}")

    if confidence.get("reasons"):
        lines.append("  Reasons:")
        for r in confidence["reasons"]:
            lines.append(f"    - {r}")

    if intervals and intervals.get("ok"):
        lines.append("\n  Confidence Intervals (historical):")
        for period, data in intervals.get("intervals", {}).items():
            lines.append(f"    {period}: Expected {data['expected']:+.1f}% | "
                        f"70% CI [{data['ci_lower']:+.1f}%, {data['ci_upper']:+.1f}%] | "
                        f"Range [{data['worst']:+.1f}%, {data['best']:+.1f}%]")

    return "\n".join(lines)


if __name__ == "__main__":
    # Test high confidence
    conf = compute_confidence(
        arbitration={"contradiction_level": "LOW", "spread": 15},
        active_signals=6,
    )
    print("High confidence:", conf["level"], f"({conf['confidence_score']}/100)")

    # Test low confidence
    conf2 = compute_confidence(
        arbitration={"contradiction_level": "HIGH", "spread": 55},
        active_signals=2,
        data_failures=["NSE Options"],
        upcoming_events=[{"event": "RBI Policy", "days_until": 1}],
    )
    print("Low confidence:", conf2["level"], f"({conf2['confidence_score']}/100)")
    for r in conf2["reasons"]:
        print(f"  - {r}")
