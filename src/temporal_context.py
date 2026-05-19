"""
Temporal Context Layer — Duration and direction of signals.
Adds "WHEN" to existing "WHAT" intelligence.

"How long has FII been outflowing?" matters as much as "FII is outflowing."
Duration + rate of change = temporal context.
"""
import statistics
from typing import Dict, List, Optional


def compute_temporal_context(snapshots: List[Dict]) -> Dict:
    """
    Compute temporal context for key metrics from daily_market_snapshot.
    For each metric: duration in regime, rate of change, historical comparison.
    """
    if not snapshots or len(snapshots) < 10:
        return {"ok": False, "message": "Need 10+ snapshots for temporal context"}

    metrics = {
        "fii_net": {"label": "FII Flow", "lookback": 20, "threshold": 0},
        "india_vix": {"label": "India VIX", "lookback": 20, "threshold": 15},
        "bull_bear_score": {"label": "Bull/Bear Score", "lookback": 20, "threshold": 50},
        "pcr": {"label": "PCR", "lookback": 20, "threshold": 1.0},
        "advance_decline_ratio": {"label": "A/D Ratio", "lookback": 10, "threshold": 1.0},
    }

    results = {}

    for metric, config in metrics.items():
        values = [(s.get("date"), s.get(metric)) for s in snapshots
                  if s.get(metric) is not None]

        if len(values) < 10:
            continue

        current_val = values[-1][1]
        threshold = config["threshold"]

        # Determine current regime
        if metric == "india_vix":
            regime = "HIGH" if current_val > 20 else "ELEVATED" if current_val > 15 else "NORMAL" if current_val > 12 else "LOW"
        elif metric == "bull_bear_score":
            regime = "BULLISH" if current_val > 60 else "BEARISH" if current_val < 40 else "NEUTRAL"
        elif metric == "pcr":
            regime = "BEARISH" if current_val > 1.3 else "BULLISH" if current_val < 0.7 else "NEUTRAL"
        elif metric == "fii_net":
            regime = "BUYING" if current_val > 200 else "SELLING" if current_val < -200 else "NEUTRAL"
        elif metric == "advance_decline_ratio":
            regime = "BROAD" if current_val > 1.5 else "NARROW" if current_val < 0.7 else "NORMAL"
        else:
            regime = "UNKNOWN"

        # Count consecutive days in current regime
        streak = 0
        for _, val in reversed(values):
            if metric == "india_vix":
                in_regime = (val > 20) if regime == "HIGH" else (val > 15 and val <= 20) if regime == "ELEVATED" else (val <= 15 and val > 12) if regime == "NORMAL" else (val <= 12)
            elif metric == "bull_bear_score":
                in_regime = (val > 60) if regime == "BULLISH" else (val < 40) if regime == "BEARISH" else (40 <= val <= 60)
            elif metric == "pcr":
                in_regime = (val > 1.3) if regime == "BEARISH" else (val < 0.7) if regime == "BULLISH" else (0.7 <= val <= 1.3)
            elif metric == "fii_net":
                in_regime = (val > 200) if regime == "BUYING" else (val < -200) if regime == "SELLING" else (-200 <= val <= 200)
            elif metric == "advance_decline_ratio":
                in_regime = (val > 1.5) if regime == "BROAD" else (val < 0.7) if regime == "NARROW" else (0.7 <= val <= 1.5)
            else:
                in_regime = True

            if in_regime:
                streak += 1
            else:
                break

        # Rate of change (5-day)
        recent_5 = [v for _, v in values[-5:]]
        older_5 = [v for _, v in values[-10:-5]] if len(values) >= 10 else recent_5
        recent_avg = statistics.mean(recent_5)
        older_avg = statistics.mean(older_5)
        if older_avg != 0:
            rate_of_change = ((recent_avg / older_avg) - 1) * 100
        else:
            rate_of_change = 0

        if rate_of_change > 10:
            change_direction = "ACCELERATING"
        elif rate_of_change < -10:
            change_direction = "DECELERATING"
        else:
            change_direction = "STABLE"

        # Historical average duration (completed streaks only — exclude current)
        streak_lengths = []
        current_len = 0
        for _, val in values:
            if metric == "fii_net":
                in_r = (val > 200) if regime == "BUYING" else (val < -200) if regime == "SELLING" else False
            elif metric == "india_vix":
                in_r = (val > 20) if regime == "HIGH" else (val > 15 and val <= 20) if regime == "ELEVATED" else (val <= 15 and val > 12) if regime == "NORMAL" else (val <= 12)
            elif metric == "bull_bear_score":
                in_r = (val > 60) if regime == "BULLISH" else (val < 40) if regime == "BEARISH" else False
            elif metric == "pcr":
                in_r = (val > 1.3) if regime == "BEARISH" else (val < 0.7) if regime == "BULLISH" else False
            else:
                in_r = False

            if in_r:
                current_len += 1
            else:
                if current_len > 0:
                    streak_lengths.append(current_len)
                current_len = 0
        # Do NOT append current_len — it's the active streak (circular if included)

        avg_duration = statistics.mean(streak_lengths) if streak_lengths else 0

        # Per-signal baseline defaults (from historical observation)
        if avg_duration == 0:
            BASELINE_AVG = {
                "fii_net": 9,              # FII streak avg ~8-11 days
                "india_vix": 12,           # VIX HIGH regime ~12-15 days
                "bull_bear_score": 16,     # Bull/Bear regime ~15-20 days
                "pcr": 6,                  # PCR extreme ~5-7 days
                "advance_decline_ratio": 7,
            }
            avg_duration = BASELINE_AVG.get(metric, 9)

        # Temporal label
        if streak > avg_duration * 1.2 and avg_duration > 0:
            temporal_label = f"EXTENDED — {streak}d vs {avg_duration:.0f}d avg. Mean reversion overdue."
        elif streak > avg_duration * 0.7 and avg_duration > 0:
            temporal_label = f"MATURE — {streak}d vs {avg_duration:.0f}d avg. Watch for reversal."
        elif avg_duration > 0:
            temporal_label = f"EARLY — {streak}d vs {avg_duration:.0f}d avg. Regime has room to run."
        else:
            temporal_label = f"CURRENT — {streak}d in {regime} regime."

        results[metric] = {
            "label": config["label"],
            "current_value": current_val,
            "regime": regime,
            "streak_days": streak,
            "avg_historical_duration": round(avg_duration, 1),
            "rate_of_change": round(rate_of_change, 1),
            "change_direction": change_direction,
            "temporal_label": temporal_label,
        }

    return {"ok": bool(results), "metrics": results}


def format_temporal_context(temporal: Dict) -> str:
    """Format temporal context for AI prompt."""
    if not temporal.get("ok"):
        return ""

    lines = ["[Temporal Context — Duration & Direction of Signals]"]

    # Icon based on market implication (bearish=🔴, bullish=🟢, neutral=⚪)
    REGIME_ICON = {
        "BUYING": "🟢", "BULLISH": "🟢", "BROAD": "🟢", "LOW": "🟢",
        "SELLING": "🔴", "BEARISH": "🔴", "NARROW": "🔴", "HIGH": "🔴",
        "ELEVATED": "🔴",  # VIX elevated = bearish market implication
        "NEUTRAL": "⚪", "NORMAL": "⚪",
    }
    for metric, data in temporal.get("metrics", {}).items():
        icon = REGIME_ICON.get(data["regime"], "⚪")
        lines.append(f"  {icon} {data['label']}: {data['regime']} ({data['streak_days']}d)")
        lines.append(f"    → {data['temporal_label']}")
        lines.append(f"    Rate: {data['rate_of_change']:+.1f}% ({data['change_direction']})")

    return "\n".join(lines)


if __name__ == "__main__":
    # Test with dummy data
    import random
    random.seed(42)
    snapshots = []
    for i in range(60):
        snapshots.append({
            "date": f"2026-01-{i+1:02d}",
            "fii_net": -1500 + random.randint(-500, 500),
            "india_vix": 14 + (i % 20) * 0.5,
            "bull_bear_score": 35 + random.randint(-10, 10),
            "pcr": 1.2 + random.uniform(-0.3, 0.3),
            "advance_decline_ratio": 0.9 + random.uniform(-0.3, 0.3),
        })

    result = compute_temporal_context(snapshots)
    print(format_temporal_context(result))
