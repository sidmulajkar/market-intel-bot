"""
Volatility Regime Persistence — Track how long VIX stays in a regime.
Predict persistence: "VIX has been HIGH for 12 days, avg duration is 18 days."
Helps time re-entry after risk-off.
"""
import statistics
from typing import Dict, List, Optional


def compute_regime_persistence(snapshots: List[Dict]) -> Dict:
    """
    Analyze VIX regime persistence from historical snapshots.
    Computes: current regime duration, avg historical duration, expected remaining.
    """
    if not snapshots or len(snapshots) < 30:
        return {"ok": False, "message": "Need 30+ snapshots"}

    # Extract VIX values and classify regimes
    vix_data = [(s.get("date"), s.get("india_vix")) for s in snapshots
                if s.get("india_vix") is not None]

    if len(vix_data) < 30:
        return {"ok": False, "message": "Insufficient VIX data"}

    def _classify(vix):
        if vix > 20:
            return "HIGH"
        elif vix > 15:
            return "ELEVATED"
        elif vix > 12:
            return "NORMAL"
        elif vix > 10:
            return "LOW"
        else:
            return "COMPLACENT"

    # Build regime sequence
    regimes = [_classify(v) for _, v in vix_data]
    current_regime = regimes[-1]
    current_vix = vix_data[-1][1]

    # Compute streaks (consecutive days in same regime)
    streaks = []
    current_streak = 1
    for i in range(len(regimes) - 1, 0, -1):
        if regimes[i] == regimes[i - 1]:
            current_streak += 1
        else:
            streaks.append({"regime": regimes[i], "length": current_streak})
            current_streak = 1
    streaks.append({"regime": regimes[0], "length": current_streak})

    # Current streak length
    current_streak_len = 0
    for s in streaks:
        if s["regime"] == current_regime:
            current_streak_len = s["length"]
            break

    # Historical streak lengths for this regime
    same_regime_streaks = [s["length"] for s in streaks if s["regime"] == current_regime]
    avg_duration = statistics.mean(same_regime_streaks) if same_regime_streaks else 0
    max_duration = max(same_regime_streaks) if same_regime_streaks else 0
    min_duration = min(same_regime_streaks) if same_regime_streaks else 0

    # Persistence prediction
    if current_streak_len > avg_duration * 1.5:
        prediction = f"OVEREXTENDED — {current_streak_len}d vs {avg_duration:.0f}d avg. Regime shift likely."
    elif current_streak_len > avg_duration:
        prediction = f"ABOVE AVERAGE — {current_streak_len}d vs {avg_duration:.0f}d avg. May persist a few more days."
    elif current_streak_len > avg_duration * 0.5:
        prediction = f"NORMAL — {current_streak_len}d vs {avg_duration:.0f}d avg. Expected to continue."
    else:
        prediction = f"EARLY — {current_streak_len}d vs {avg_duration:.0f}d avg. Regime has room to run."

    return {
        "ok": True,
        "current_vix": current_vix,
        "current_regime": current_regime,
        "current_streak_days": current_streak_len,
        "avg_historical_duration": round(avg_duration, 1),
        "max_historical_duration": max_duration,
        "min_historical_duration": min_duration,
        "prediction": prediction,
        "total_days_analyzed": len(regimes),
    }


def format_vol_persistence(persistence: Dict) -> str:
    """Format volatility persistence for AI prompt."""
    if not persistence.get("ok"):
        return ""

    lines = [f"[Volatility Regime Persistence]"]
    lines.append(f"  Current: VIX {persistence['current_vix']:.1f} — {persistence['current_regime']} regime")
    lines.append(f"  Duration: {persistence['current_streak_days']} days (avg: {persistence['avg_historical_duration']:.0f}d, max: {persistence['max_historical_duration']}d)")
    lines.append(f"  {persistence['prediction']}")

    return "\n".join(lines)


if __name__ == "__main__":
    snapshots = [{"date": f"2026-01-{i+1:02d}", "india_vix": 14 + (i % 20) * 0.5} for i in range(60)]
    result = compute_regime_persistence(snapshots)
    print(format_vol_persistence(result))
