"""
Simplicity Engine — Translate complex signals into human-readable one-liners.
Every number → feeling + action. Max 4 lines. No jargon. Emoji-tagged.

This is what separates institutional intelligence from raw data.
New investor reads 4 lines → understands market mood.
Power user reads everything → gets full depth.
"""
from typing import Dict, List


# ═══════════════════════════════════════════════════════════════════════════════
# TRANSLATION RULES
# ═══════════════════════════════════════════════════════════════════════════════

def translate_fii_signal(fii_net: float = None, fii_streak: int = None,
                          fii_avg_duration: float = None,
                          fii_direction: str = None) -> str:
    """Translate FII data into simple line."""
    if fii_net is None:
        return None

    if fii_net < -2000:
        icon = "🔴"
        action = "protect capital"
    elif fii_net < -500:
        icon = "🔴"
        action = "caution"
    elif fii_net > 2000:
        icon = "🟢"
        action = "follow the smart money"
    elif fii_net > 500:
        icon = "🟢"
        action = "support building"
    else:
        return None

    if fii_streak and fii_avg_duration and fii_avg_duration > 0:
        pct_complete = fii_streak / fii_avg_duration
        direction = "selling" if fii_net < 0 else "buying"
        if pct_complete >= 1.2:
            return f"{icon} Foreign {direction} {fii_streak}d — extended (avg {fii_avg_duration:.0f}d), reversal likely"
        elif pct_complete >= 0.7:
            return f"{icon} Foreign {direction} {fii_streak}d — mature (avg {fii_avg_duration:.0f}d), watch for turn"
        else:
            remaining = max(0, fii_avg_duration - fii_streak)
            return f"{icon} Foreign {direction} {fii_streak}d — avg {fii_avg_duration:.0f}d streak, ~{remaining:.0f}d remaining historically"
    elif fii_streak and fii_streak >= 5:
        direction = "selling" if fii_net < 0 else "buying"
        return f"{icon} Foreign {direction} {fii_streak}d straight — streak ongoing"
    else:
        direction = "selling" if fii_net < 0 else "buying"
        amount = f"₹{abs(fii_net):,.0f}Cr"
        return f"{icon} Foreign money {direction} {amount} today"


def translate_contradiction(contradiction_level: str, spread: int = 0) -> str:
    """Translate contradiction into simple line."""
    if contradiction_level in ("VERY HIGH", "HIGH"):
        return f"⚠️ Signals fighting each other — wait and watch"
    elif contradiction_level == "MODERATE":
        return f"🟡 Mixed signals — reduced conviction"
    return None


def translate_internals(internals_score: int = None) -> str:
    """Translate market internals into simple line."""
    if internals_score is None:
        return None

    if internals_score >= 70:
        return f"🟢 Market breadth healthy — not fragile"
    elif internals_score <= 30:
        return f"🔴 Breadth broken — many stocks falling silently"
    elif internals_score <= 40:
        return f"🟡 Market breadth weakening — fewer stocks participating"
    return None


def translate_factor(factor_dominant: str = None) -> str:
    """Translate dominant factor into simple line."""
    if factor_dominant is None:
        return None

    if "BEARISH" in factor_dominant.upper():
        return f"🔴 Expensive stocks getting punished"
    elif "BULLISH" in factor_dominant.upper():
        return f"🟢 Broad-based rally — quality and momentum aligned"
    return None


def translate_confidence(confidence_score: int = None, confidence_level: str = None) -> str:
    """Translate confidence into simple line."""
    if confidence_score is None:
        return None

    if confidence_score < 30:
        return f"🤷 Too confused to predict — sit this one out"
    elif confidence_score < 50:
        return f"🟡 Low conviction — small bets only"
    elif confidence_score >= 80:
        return f"🟢 High conviction — market direction clear"
    return None


def translate_hhi(hhi: int = None) -> str:
    """Translate FII concentration into simple line."""
    if hhi is None:
        return None

    if hhi > 4000:
        return f"⚠️ Few big players dominate — one exit = sharp move"
    elif hhi > 2500:
        return f"🟡 FII activity concentrated — watch for rotation"
    return None


def translate_turnover(turnover_ratio: float = None) -> str:
    """Translate derivative turnover into simple line."""
    if turnover_ratio is None:
        return None

    if turnover_ratio > 3.0:
        return f"🔴 Retail gambling heavy — top likely near"
    elif turnover_ratio > 2.0:
        return f"🟡 Speculation elevated — caution warranted"
    return None


def translate_vix_persistence(vix_regime: str = None, streak_days: int = None,
                               avg_duration: float = None) -> str:
    """Translate VIX persistence into simple line."""
    if vix_regime is None or streak_days is None:
        return None

    if vix_regime == "HIGH" and streak_days > (avg_duration or 12) * 0.8:
        return f"🟡 Volatility {streak_days} days — exhaustion zone, breakout coming"
    elif vix_regime == "LOW" and streak_days > 10:
        return f"🟡 Complacency {streak_days} days — calm before storm"
    elif vix_regime == "HIGH":
        return f"🟡 Volatility elevated — protect positions"
    return None


def translate_pcr(pcr: float = None) -> str:
    """Translate PCR into simple line."""
    if pcr is None:
        return None

    if pcr > 1.4:
        return f"🔴 Heavy put buying — options traders bracing for drop"
    elif pcr < 0.6:
        return f"🔴 Heavy call buying — everyone bullish = contrarian warning"
    elif pcr > 1.2:
        return f"🟡 Put activity elevated — hedging demand rising"
    elif pcr < 0.8:
        return f"🟢 Call buying dominant — options traders bullish"
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN SIMPLICITY ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def generate_simple_lines(arbitration: Dict = None, temporal: Dict = None,
                           internals_score: int = None, factor_dominant: str = None,
                           confidence_score: int = None, hhi: int = None,
                           turnover_ratio: float = None, pcr: float = None,
                           vix_regime: str = None, vix_streak: int = None,
                           vix_avg_duration: float = None) -> List[str]:
    """
    Generate simple human-readable lines from complex signals.
    Max 4 lines. No jargon. Action-oriented.
    """
    lines = []

    # Priority 1: Contradictions (most actionable)
    if arbitration:
        contradiction = translate_contradiction(
            arbitration.get("contradiction_level"),
            arbitration.get("spread")
        )
        if contradiction:
            lines.append(contradiction)

    # Priority 2: FII (most watched by Indian investors)
    if temporal:
        fii_data = temporal.get("metrics", {}).get("fii_net", {})
        if fii_data:
            fii_line = translate_fii_signal(
                fii_net=fii_data.get("current_value"),
                fii_streak=fii_data.get("streak_days"),
                fii_avg_duration=fii_data.get("avg_historical_duration"),
            )
            if fii_line:
                lines.append(fii_line)

    # Priority 3: Market health
    internals_line = translate_internals(internals_score)
    if internals_line:
        lines.append(internals_line)

    # Priority 4: Factor direction
    factor_line = translate_factor(factor_dominant)
    if factor_line:
        lines.append(factor_line)

    # Priority 5: Confidence
    confidence_line = translate_confidence(confidence_score)
    if confidence_line:
        lines.append(confidence_line)

    # Priority 6: Options (if not already covered)
    if not lines or len(lines) < 3:
        pcr_line = translate_pcr(pcr)
        if pcr_line:
            lines.append(pcr_line)

    # Priority 7: Concentration risk
    if hhi and hhi > 4000:
        hhi_line = translate_hhi(hhi)
        if hhi_line:
            lines.append(hhi_line)

    # Priority 8: Turnover
    if turnover_ratio and turnover_ratio > 2.0:
        turnover_line = translate_turnover(turnover_ratio)
        if turnover_line:
            lines.append(turnover_line)

    # Priority 9: VIX persistence
    if vix_regime and vix_streak:
        vol_line = translate_vix_persistence(vix_regime, vix_streak, vix_avg_duration)
        if vol_line:
            lines.append(vol_line)

    # Priority 10: All bullish edge case
    if not lines:
        lines.append("🟢 No major red flags — steady as she goes")

    # Cap at 4 lines
    return lines[:4]


def format_simple_lines(lines: List[str]) -> str:
    """Format simple lines for prompt injection."""
    if not lines:
        return ""

    return "\n".join(lines)


def format_simple_block(lines: List[str]) -> str:
    """Format simple lines as a prompt block (Block -1)."""
    if not lines:
        return ""

    block = ["[SIMPLE SUMMARY — Weave these into your narrative]"]
    for line in lines:
        block.append(f"  {line}")

    return "\n".join(block)


# ═══════════════════════════════════════════════════════════════════════════════
# EDGE CASE HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

def handle_all_signals_missing() -> List[str]:
    """When no data is available."""
    return [
        "🤷 Market data unavailable — cannot form opinion",
        "⚠️ Sit out until data sources恢复",
    ]


def handle_all_bullish() -> List[str]:
    """When everything is bullish — contrarian warning."""
    return [
        "🟢 Everything green — market firing on all cylinders",
        "⚠️ But check if too crowded — everyone bullish = late cycle",
    ]


def handle_all_bearish() -> List[str]:
    """When everything is bearish — capital protection."""
    return [
        "🔴 All red — protect capital first",
        "⚠️ But extremes often reverse — watch for capitulation",
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Test with contradictory scenario
    lines = generate_simple_lines(
        arbitration={"contradiction_level": "VERY HIGH", "spread": 45},
        temporal={"metrics": {"fii_net": {"current_value": -2100, "streak_days": 8, "avg_historical_duration": 11}}},
        internals_score=72,
        factor_dominant="BEARISH",
        confidence_score=38,
        pcr=1.4,
    )
    print("Simple lines:")
    for line in lines:
        print(f"  {line}")

    # Test all bullish
    print("\nAll bullish:")
    for line in handle_all_bullish():
        print(f"  {line}")
