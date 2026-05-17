"""
Market Internals Composite Score — Unified 0-100 market health indicator.
Combines multiple internal signals into one number.

Components:
  - A/D Ratio (advance/decline)
  - New High / New Low ratio
  - Volume of advancing vs declining stocks
  - % stocks above 20MA, 50MA, 200MA
  - McClellan Oscillator

Score < 30 = rally on weak internals (unsustainable)
Score > 70 = healthy broad rally
"""
import statistics
from typing import Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# COMPONENT SCORERS (each returns 0-100)
# ═══════════════════════════════════════════════════════════════════════════════

def score_ad_ratio(advance: int, decline: int) -> Dict:
    """
    A/D Ratio score: 0-100.
    A/D > 2.0 = 90+ (extremely broad rally)
    A/D = 1.0 = 50 (balanced)
    A/D < 0.5 = 10 (broad selling)
    """
    if decline == 0:
        ratio = advance if advance > 0 else 1
    else:
        ratio = advance / decline

    # Map to 0-100
    score = max(0, min(100, round(50 + (ratio - 1) * 40)))

    if ratio > 2.0:
        label = "EXTREMELY BROAD rally"
    elif ratio > 1.5:
        label = "BROAD rally"
    elif ratio > 1.0:
        label = "MILDLY POSITIVE"
    elif ratio > 0.7:
        label = "MILDLY NEGATIVE"
    elif ratio > 0.5:
        label = "BROAD selling"
    else:
        label = "EXTREME selling"

    return {"score": score, "ratio": round(ratio, 2), "label": label}


def score_high_low(highs: int, lows: int) -> Dict:
    """
    New High/New Low ratio score: 0-100.
    NH/NL > 3.0 = 90+ (strong uptrend)
    NH/NL = 1.0 = 50 (balanced)
    NH/NL < 0.3 = 10 (strong downtrend)
    """
    if lows == 0:
        ratio = highs if highs > 0 else 1
    else:
        ratio = highs / lows

    score = max(0, min(100, round(50 + (ratio - 1) * 20)))

    if ratio > 3.0:
        label = "STRONG UPTREND — expanding new highs"
    elif ratio > 1.5:
        label = "UPTREND — healthy"
    elif ratio > 0.7:
        label = "NEUTRAL"
    elif ratio > 0.3:
        label = "DOWNTREND — expanding new lows"
    else:
        label = "STRONG DOWNTREND"

    return {"score": score, "ratio": round(ratio, 2), "label": label}


def score_volume_breadth(adv_volume: float, dec_volume: float) -> Dict:
    """
    Volume breadth score: 0-100.
    Volume ratio > 2.0 = 90+ (strong buying pressure)
    Volume ratio = 1.0 = 50 (balanced)
    Volume ratio < 0.5 = 10 (selling pressure)
    """
    if dec_volume == 0:
        ratio = adv_volume if adv_volume > 0 else 1
    else:
        ratio = adv_volume / dec_volume

    score = max(0, min(100, round(50 + (ratio - 1) * 30)))

    if ratio > 2.0:
        label = "STRONG buying pressure"
    elif ratio > 1.2:
        label = "Moderate buying"
    elif ratio > 0.8:
        label = "BALANCED"
    elif ratio > 0.5:
        label = "Moderate selling"
    else:
        label = "STRONG selling pressure"

    return {"score": score, "ratio": round(ratio, 2), "label": label}


def score_ma_breadth(pct_above_20ma: float, pct_above_50ma: float,
                      pct_above_200ma: float) -> Dict:
    """
    % stocks above moving averages score: 0-100.
    Weighted: 20MA (20%), 50MA (40%), 200MA (40%)
    All > 70% = 80+ (broad strength)
    All < 30% = 20- (broad weakness)
    """
    # Each MA contributes to overall score
    score_20ma = pct_above_20ma  # Already 0-100
    score_50ma = pct_above_50ma
    score_200ma = pct_above_200ma

    # Weighted average
    score = round(score_20ma * 0.2 + score_50ma * 0.4 + score_200ma * 0.4)

    avg = (pct_above_20ma + pct_above_50ma + pct_above_200ma) / 3
    if avg > 70:
        label = "BROAD STRENGTH — majority above all MAs"
    elif avg > 50:
        label = "HEALTHY — majority above key MAs"
    elif avg > 30:
        label = "WEAKENING — fewer stocks participating"
    else:
        label = "BROAD WEAKNESS — majority below MAs"

    return {
        "score": score,
        "pct_above_20ma": round(pct_above_20ma, 1),
        "pct_above_50ma": round(pct_above_50ma, 1),
        "pct_above_200ma": round(pct_above_200ma, 1),
        "label": label,
    }


def score_mcclellan(oscillator: float) -> Dict:
    """
    McClellan Oscillator score: 0-100.
    > +100 = 90+ (strong breadth thrust)
    > 0 = 50-80 (positive breadth)
    < 0 = 20-50 (negative breadth)
    < -100 = 10- (strong selling breadth)
    """
    # Map oscillator range (-200 to +200) to 0-100
    score = max(0, min(100, round(50 + oscillator / 4)))

    if oscillator > 100:
        label = "STRONG BREADTH THRUST — powerful rally"
    elif oscillator > 30:
        label = "POSITIVE breadth — rally supported"
    elif oscillator > -30:
        label = "NEUTRAL breadth"
    elif oscillator > -100:
        label = "NEGATIVE breadth — rally unsupported"
    else:
        label = "STRONG SELLING BREADTH"

    return {"score": score, "oscillator": round(oscillator, 1), "label": label}


# ═══════════════════════════════════════════════════════════════════════════════
# COMPOSITE SCORE
# ═══════════════════════════════════════════════════════════════════════════════

def compute_internals_composite(breadth: dict, nifty_closes: list = None) -> Dict:
    """
    Compute unified market internals composite score.
    breadth: dict with advance, decline, highs_52w, lows_52w, adv_volume, dec_volume
    nifty_closes: optional price history for McClellan + MA breadth
    """
    components = {}

    # 1. A/D Ratio
    advance = breadth.get("advance", 0)
    decline = breadth.get("decline", 0)
    if advance > 0 or decline > 0:
        components["ad_ratio"] = score_ad_ratio(advance, decline)

    # 2. New High / New Low
    highs = breadth.get("highs_52w", 0)
    lows = breadth.get("lows_52w", 0)
    if highs > 0 or lows > 0:
        components["high_low"] = score_high_low(highs, lows)

    # 3. Volume Breadth
    adv_vol = breadth.get("adv_volume", 0)
    dec_vol = breadth.get("dec_volume", 0)
    if adv_vol > 0 or dec_vol > 0:
        components["volume_breadth"] = score_volume_breadth(adv_vol, dec_vol)

    # 4. MA Breadth (if available)
    pct_20ma = breadth.get("pct_above_20ma", 50)  # Default to neutral
    pct_50ma = breadth.get("pct_above_50ma", 50)
    pct_200ma = breadth.get("pct_above_200ma", 50)
    if any(v != 50 for v in [pct_20ma, pct_50ma, pct_200ma]):
        components["ma_breadth"] = score_ma_breadth(pct_20ma, pct_50ma, pct_200ma)

    # 5. McClellan (compute from nifty_closes if available)
    if nifty_closes and len(nifty_closes) >= 40:
        # Simple McClellan approximation using A/D
        # Real McClellan uses advancing - declining volume
        # Approximation: use breadth ratio trend
        recent_ad = []
        for i in range(max(0, len(nifty_closes) - 39), len(nifty_closes)):
            # Use price change as proxy for breadth
            if i > 0:
                chg = nifty_closes[i] - nifty_closes[i-1]
                recent_ad.append(chg)

        if len(recent_ad) >= 20:
            ema19 = statistics.mean(recent_ad[:19]) if len(recent_ad) >= 19 else 0
            ema39 = statistics.mean(recent_ad) if recent_ad else 0
            oscillator = (ema19 - ema39) * 100  # Scale up
            components["mcclellan"] = score_mcclellan(oscillator)

    if not components:
        return {"ok": False, "message": "No internal data available"}

    # Composite: weighted average
    weights = {
        "ad_ratio": 0.25,
        "high_low": 0.15,
        "volume_breadth": 0.20,
        "ma_breadth": 0.25,
        "mcclellan": 0.15,
    }

    total_weight = 0
    weighted_score = 0
    for name, data in components.items():
        w = weights.get(name, 0.1)
        weighted_score += data["score"] * w
        total_weight += w

    composite_score = round(weighted_score / total_weight) if total_weight > 0 else 50

    # Classification
    if composite_score >= 80:
        classification = "VERY HEALTHY — broad rally, sustainable"
    elif composite_score >= 60:
        classification = "HEALTHY — rally with decent breadth"
    elif composite_score >= 40:
        classification = "NEUTRAL — mixed signals"
    elif composite_score >= 20:
        classification = "WEAK — narrow rally, fragile"
    else:
        classification = "VERY WEAK — broad selling, caution"

    return {
        "ok": True,
        "composite_score": composite_score,
        "classification": classification,
        "components": components,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# FORMATTING
# ═══════════════════════════════════════════════════════════════════════════════

def format_internals(composite: Dict) -> str:
    """Format market internals for AI prompt injection."""
    if not composite.get("ok"):
        return ""

    lines = ["[Market Internals Composite Score — Market Health]"]
    score = composite["composite_score"]
    lines.append(f"  COMPOSITE SCORE: {score}/100 — {composite['classification']}")
    lines.append("")

    for name, data in composite.get("components", {}).items():
        label = {
            "ad_ratio": "A/D Ratio",
            "high_low": "New High/Low",
            "volume_breadth": "Volume Breadth",
            "ma_breadth": "MA Breadth",
            "mcclellan": "McClellan",
        }.get(name, name)

        s = data["score"]
        icon = "🟢" if s > 60 else "🔴" if s < 40 else "⚪"
        lines.append(f"  {icon} {label}: {s}/100 — {data['label']}")

    # Key insight
    lines.append("")
    if score < 30:
        lines.append("  ⚠️ Internals suggest rally is unsustainable — breadth deteriorating.")
        lines.append("  Fewer stocks participating. Risk of sharp reversal.")
    elif score > 70:
        lines.append("  ✅ Strong internals — broad participation supports the rally.")
        lines.append("  Multiple confirmations across breadth, volume, and momentum.")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def run_internals_analysis(breadth: dict, nifty_closes: list = None) -> Dict:
    """Full market internals analysis pipeline."""
    composite = compute_internals_composite(breadth, nifty_closes)
    formatted = format_internals(composite)

    return {
        "ok": composite.get("ok", False),
        "composite": composite,
        "formatted": formatted,
    }


if __name__ == "__main__":
    # Test with dummy data
    test_breadth = {
        "advance": 1200, "decline": 800,
        "highs_52w": 150, "lows_52w": 30,
        "adv_volume": 50000000, "dec_volume": 30000000,
        "pct_above_20ma": 65, "pct_above_50ma": 55, "pct_above_200ma": 45,
    }
    test_closes = [20000 + i * 30 + (-1)**i * 20 for i in range(200)]

    result = run_internals_analysis(test_breadth, test_closes)
    if result["ok"]:
        print(result["formatted"])
    else:
        print(f"No data: {result.get('message')}")
