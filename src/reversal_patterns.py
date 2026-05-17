"""
Reversal Pattern Detector — Statistical signatures of price reversals.
Not visual patterns — statistical signatures:
  - V-Bottom: 3-day down >1% each + sharp reversal
  - Failed Breakout: New 20D high → close below within 3 days
  - Exhaustion Gap: Gap >1% + volume >2x avg → reversal next day
  - VWAP Mean Reversion: Close >3% above VWAP → revert within 5 days
"""
from typing import Dict, List, Optional
import statistics


def detect_v_bottom(prices: List[float], threshold: float = -1.0) -> Dict:
    """
    V-Bottom: 3+ consecutive days of >threshold% decline,
    followed by a sharp reversal (>1.5% up in 1 day).
    """
    if len(prices) < 5:
        return {"detected": False}

    returns = [(prices[i] / prices[i-1] - 1) * 100 for i in range(1, len(prices))]

    # Find consecutive down days
    consecutive_down = 0
    for r in reversed(returns[:-1]):
        if r < threshold:
            consecutive_down += 1
        else:
            break

    # Check for sharp reversal
    if consecutive_down >= 3 and returns[-1] > 1.5:
        return {
            "detected": True,
            "type": "V-BOTTOM",
            "description": f"{consecutive_down} consecutive down days (>1% each) + sharp reversal (+{returns[-1]:.1f}%)",
            "signal": "CONTRARIAN BULLISH — capitulation followed by recovery",
        }

    return {"detected": False}


def detect_failed_breakout(prices: List[float], lookback: int = 20) -> Dict:
    """
    Failed Breakout: Price makes new 20D high, then closes below
    the breakout level within 3 days.
    """
    if len(prices) < lookback + 1:
        return {"detected": False}

    # Find 20D high BEFORE the last 3 days (the pre-breakout high)
    pre_breakout = prices[:-3]
    high_20d = max(pre_breakout[-lookback:]) if len(pre_breakout) >= lookback else max(pre_breakout)
    latest_price = prices[-1]

    # Check if recent price exceeded 20D high then fell back
    recent_high = max(prices[-3:])
    if recent_high > high_20d and latest_price < high_20d:
        return {
            "detected": True,
            "type": "FAILED BREAKOUT",
            "description": f"New 20D high ({recent_high:.0f}) → closed back below ({latest_price:.0f})",
            "signal": "BEARISH — breakout failed, sellers took control",
        }

    return {"detected": False}


def detect_exhaustion_gap(prices: List[float], volumes: List[float] = None) -> Dict:
    """
    Exhaustion Gap: Gap >1% in direction of trend + volume spike.
    Usually followed by reversal.
    """
    if len(prices) < 5:
        return {"detected": False}

    # Check for gap
    gap_pct = (prices[-2] / prices[-3] - 1) * 100

    if abs(gap_pct) < 1.0:
        return {"detected": False}

    # Check volume spike
    vol_spike = False
    if volumes and len(volumes) >= 5:
        avg_vol = statistics.mean(volumes[-10:-1]) if len(volumes) >= 10 else statistics.mean(volumes[:-1])
        if avg_vol > 0 and volumes[-2] > avg_vol * 2:
            vol_spike = True

    if vol_spike or abs(gap_pct) > 2.0:
        direction = "UP" if gap_pct > 0 else "DOWN"
        return {
            "detected": True,
            "type": "EXHAUSTION GAP",
            "description": f"Gap {gap_pct:+.1f}% {'up' if gap_pct > 0 else 'down'} with volume spike",
            "signal": f"REVERSAL LIKELY — exhaustion gap {'bullish' if gap_pct < 0 else 'bearish'} (contrarian {'bearish' if gap_pct < 0 else 'bullish'})",
        }

    return {"detected": False}


def detect_mean_reversion(prices: List[float], vwap: float = None,
                           threshold: float = 3.0) -> Dict:
    """
    VWAP Mean Reversion: Close >threshold% above VWAP → likely to revert.
    If no VWAP, use 20-day moving average as proxy.
    """
    if not prices or len(prices) < 20:
        return {"detected": False}

    current = prices[-1]

    # Use 20MA as VWAP proxy
    if vwap is None:
        vwap = statistics.mean(prices[-20:])

    deviation = ((current / vwap) - 1) * 100

    if deviation > threshold:
        return {
            "detected": True,
            "type": "MEAN REVERSION",
            "description": f"Price {deviation:.1f}% above 20MA ({current:.0f} vs {vwap:.0f})",
            "signal": f"BEARISH — price extended, mean reversion likely (expect pullback to {vwap:.0f})",
        }
    elif deviation < -threshold:
        return {
            "detected": True,
            "type": "MEAN REVERSION",
            "description": f"Price {abs(deviation):.1f}% below 20MA ({current:.0f} vs {vwap:.0f})",
            "signal": f"BULLISH — price oversold, mean reversion likely (expect bounce to {vwap:.0f})",
        }

    return {"detected": False}


def detect_all_patterns(prices: List[float], volumes: List[float] = None) -> Dict:
    """Detect all reversal patterns from price/volume data."""
    patterns = []

    for detector in [detect_v_bottom, detect_failed_breakout, detect_exhaustion_gap, detect_mean_reversion]:
        if detector == detect_exhaustion_gap:
            result = detector(prices, volumes)
        else:
            result = detector(prices)
        if result.get("detected"):
            patterns.append(result)

    return {
        "ok": True,
        "patterns": patterns,
        "count": len(patterns),
    }


def format_patterns(patterns: Dict) -> str:
    """Format reversal patterns for AI prompt."""
    if not patterns.get("ok") or not patterns.get("patterns"):
        return ""

    lines = ["[Reversal Pattern Detection]"]
    for p in patterns["patterns"]:
        lines.append(f"  🔍 {p['type']}: {p['description']}")
        lines.append(f"    → {p['signal']}")

    return "\n".join(lines)


if __name__ == "__main__":
    # Test V-bottom
    prices = [100, 99, 97, 95, 93, 91, 89, 92]  # Down 6 days + reversal
    print("V-bottom:", detect_v_bottom(prices))

    # Test mean reversion
    prices2 = [100 + i * 0.5 for i in range(25)]
    print("Mean reversion:", detect_mean_reversion(prices2))
