"""
FII Cash vs Derivatives Cross-Reference — 4 regime matrix.
Cross-references FII cash flows with FII derivatives positioning.
Currently these two modules never talk to each other.

Four regime matrix:
  FII Cash | FII Derivatives | Signal
  Buying   | Long            | STRONG CONVICTION
  Selling  | Short           | FULL BEAR MODE
  Buying   | Short           | HEDGED BUYING (cautious bull)
  Selling  | Long            | HEDGE SELLING (weak bear)
"""
from typing import Dict, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# REGIME MATRIX
# ═══════════════════════════════════════════════════════════════════════════════

REGIME_MATRIX = {
    ("buying", "long"): {
        "signal": "STRONG CONVICTION",
        "direction": "BULLISH",
        "description": "FII buying cash + long derivatives = strong institutional conviction. Both equity and derivatives markets aligned.",
        "confidence": "HIGH",
    },
    ("selling", "short"): {
        "signal": "FULL BEAR MODE",
        "direction": "BEARISH",
        "description": "FII selling cash + short derivatives = full institutional exit. Both equity and derivatives markets aligned bearish.",
        "confidence": "HIGH",
    },
    ("buying", "short"): {
        "signal": "HEDGED BUYING",
        "direction": "CAUTIOUSLY BULLISH",
        "description": "FII buying cash but short derivatives = hedged positioning. Bullish on equity but protecting against downside.",
        "confidence": "MEDIUM",
    },
    ("selling", "long"): {
        "signal": "HEDGE SELLING",
        "direction": "WEAK BEARISH",
        "description": "FII selling cash but long derivatives = hedging existing positions. Not full exit, but reducing cash exposure.",
        "confidence": "MEDIUM",
    },
}


def classify_fii_cash(fii_net: float, threshold: float = 200) -> str:
    """Classify FII cash flow direction."""
    if fii_net > threshold:
        return "buying"
    elif fii_net < -threshold:
        return "selling"
    return "neutral"


def classify_fii_derivatives(fno_net: float = None, pcr: float = None,
                              gex: float = None) -> str:
    """
    Classify FII derivatives positioning.
    Uses FII F&O net if available, else PCR + GEX signals.
    """
    if fno_net is not None:
        if fno_net > 500:
            return "long"
        elif fno_net < -500:
            return "short"
        return "neutral"

    # Fallback: use PCR + GEX
    signals = []
    if pcr is not None:
        if pcr > 1.2:
            signals.append("short")  # High PCR = put buying = bearish
        elif pcr < 0.8:
            signals.append("long")   # Low PCR = call buying = bullish
    if gex is not None:
        if gex > 0:
            signals.append("long")   # Positive GEX = dealers long gamma
        elif gex < 0:
            signals.append("short")  # Negative GEX = dealers short gamma

    if not signals:
        return "neutral"

    # Majority vote
    long_count = signals.count("long")
    short_count = signals.count("short")
    if long_count > short_count:
        return "long"
    elif short_count > long_count:
        return "short"
    return "neutral"


def cross_reference_fii(fii_net: float = None, fno_net: float = None,
                         pcr: float = None, gex: float = None) -> Dict:
    """
    Cross-reference FII cash and derivatives positioning.
    Returns combined institutional signal.
    """
    cash_dir = classify_fii_cash(fii_net) if fii_net is not None else "neutral"
    deriv_dir = classify_fii_derivatives(fno_net, pcr, gex)

    # Look up regime
    regime_key = (cash_dir, deriv_dir)
    regime = REGIME_MATRIX.get(regime_key)

    if regime is None:
        # Neutral on one or both sides
        if cash_dir == "neutral" and deriv_dir == "neutral":
            signal = "NO CLEAR SIGNAL"
            direction = "NEUTRAL"
            description = "FII positioning neutral on both cash and derivatives."
            confidence = "LOW"
        elif cash_dir == "neutral":
            signal = f"DERIVATIVES ONLY: {deriv_dir.upper()}"
            direction = "BULLISH" if deriv_dir == "long" else "BEARISH"
            description = f"FII cash neutral but derivatives {deriv_dir}."
            confidence = "LOW"
        else:
            signal = f"CASH ONLY: {cash_dir.upper()}"
            direction = "BULLISH" if cash_dir == "buying" else "BEARISH"
            description = f"FII cash {cash_dir} but derivatives neutral."
            confidence = "LOW"
    else:
        signal = regime["signal"]
        direction = regime["direction"]
        description = regime["description"]
        confidence = regime["confidence"]

    return {
        "ok": True,
        "cash_direction": cash_dir,
        "derivatives_direction": deriv_dir,
        "signal": signal,
        "direction": direction,
        "description": description,
        "confidence": confidence,
        "fii_net": fii_net,
        "fno_net": fno_net,
    }


def format_fii_cross_reference(result: Dict) -> str:
    """Format FII cross-reference for AI prompt."""
    if not result.get("ok"):
        return ""

    lines = ["[FII Institutional Signal — Cash × Derivatives]"]
    lines.append(f"  Cash: {result['cash_direction'].upper()} | Derivatives: {result['derivatives_direction'].upper()}")
    lines.append(f"  Signal: {result['signal']} — {result['direction']}")
    lines.append(f"  {result['description']}")
    lines.append(f"  Confidence: {result['confidence']}")

    if result.get("fii_net") is not None:
        lines.append(f"  FII Net (Cash): ₹{result['fii_net']:+,.0f}Cr")
    if result.get("fno_net") is not None:
        lines.append(f"  FII F&O Net (Derivatives OI): ₹{result['fno_net']:+,.0f}Cr (notional, not cash)")

    return "\n".join(lines)


if __name__ == "__main__":
    # Test all 4 regimes
    print("=== REGIME TESTS ===")
    for cash, deriv, expected in [
        ("buying", "long", "STRONG CONVICTION"),
        ("selling", "short", "FULL BEAR MODE"),
        ("buying", "short", "HEDGED BUYING"),
        ("selling", "long", "HEDGE SELLING"),
    ]:
        result = cross_reference_fii(
            fii_net=1000 if cash == "buying" else -1000,
            pcr=0.7 if deriv == "long" else 1.4,
        )
        status = "✅" if result["signal"] == expected else "❌"
        print(f"  {status} {cash}+{deriv}: {result['signal']}")

    # Test with real-ish data
    result = cross_reference_fii(fii_net=-1500, pcr=1.3, gex=-50000)
    print(f"\n{format_fii_cross_reference(result)}")
