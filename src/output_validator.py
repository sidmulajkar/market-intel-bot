"""
Output Consistency Validator — Pre-send contradiction check.
Ensures AI brief doesn't contradict ground truth data.
Catches hallucinations, tone mismatches, factual errors.
"""
import re
from typing import Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# CLAIM EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════════

BULLISH_WORDS = ["bullish", "resilient", "strength", "rally", "uptrend", "accumulate",
                 "buying", "supportive", "positive", "upside", "momentum"]
BEARISH_WORDS = ["bearish", "weakness", "decline", "downtrend", "selling", "pressure",
                 "risk", "cautious", "downside", "fragile", "correction"]
NEUTRAL_WORDS = ["mixed", "sideways", "range-bound", "consolidat", "uncertain"]


def extract_claims(ai_text: str) -> Dict:
    """Extract key claims from AI-generated text."""
    text_lower = ai_text.lower()

    # Directional tone
    bullish_count = sum(1 for w in BULLISH_WORDS if w in text_lower)
    bearish_count = sum(1 for w in BEARISH_WORDS if w in text_lower)
    neutral_count = sum(1 for w in NEUTRAL_WORDS if w in text_lower)

    if bullish_count > bearish_count + 1:
        tone = "BULLISH"
    elif bearish_count > bullish_count + 1:
        tone = "BEARISH"
    elif bullish_count > 0 and bearish_count > 0:
        tone = "MIXED"
    else:
        tone = "NEUTRAL"

    # Numbers mentioned
    numbers = re.findall(r'\b\d{1,3},?\d{3}\b', ai_text)  # Indian number format
    numbers += re.findall(r'\b\d+\.\d+%\b', ai_text)  # Percentages
    numbers += re.findall(r'\b\d{4,5}\b', ai_text)  # 4-5 digit numbers (Nifty levels)

    # Flow direction
    flow_words = re.findall(r'(?:fii|dii|foreign|institutional)\s+(?:buying|selling|accumulating|distributing|inflow|outflow)', text_lower)
    flow_direction = None
    if any("buy" in w or "accumulat" in w or "inflow" in w for w in flow_words):
        flow_direction = "BUYING"
    elif any("sell" in w or "distribut" in w or "outflow" in w for w in flow_words):
        flow_direction = "SELLING"

    return {
        "tone": tone,
        "bullish_count": bullish_count,
        "bearish_count": bearish_count,
        "flow_direction": flow_direction,
        "numbers": numbers,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# GROUND TRUTH COMPARISON
# ═══════════════════════════════════════════════════════════════════════════════

def validate_against_ground_truth(claims: Dict, ground_truth: Dict) -> Dict:
    """
    Compare extracted claims against actual data.

    ground_truth: {
        "bull_bear_score": 35,
        "fii_net": -1500,
        "nifty_close": 25400,
        "pcr": 1.4,
    }
    """
    issues = []
    severity = "OK"

    # 1. Directional tone vs Bull/Bear score
    bull_bear = ground_truth.get("bull_bear_score")
    if bull_bear is not None:
        tone = claims.get("tone", "MIXED")
        if bull_bear < 40 and tone == "BULLISH":
            issues.append(f"TONE MISMATCH: Bull/Bear={bull_bear} (bearish) but AI says bullish")
            severity = "MAJOR"
        elif bull_bear > 60 and tone == "BEARISH":
            issues.append(f"TONE MISMATCH: Bull/Bear={bull_bear} (bullish) but AI says bearish")
            severity = "MAJOR"

    # 2. Flow direction vs FII net
    fii_net = ground_truth.get("fii_net")
    flow_dir = claims.get("flow_direction")
    if fii_net is not None and flow_dir:
        if fii_net < -500 and flow_dir == "BUYING":
            issues.append(f"FLOW MISMATCH: FII net=₹{fii_net:+,.0f}Cr (selling) but AI says buying")
            severity = "MAJOR"
        elif fii_net > 500 and flow_dir == "SELLING":
            issues.append(f"FLOW MISMATCH: FII net=₹{fii_net:+,.0f}Cr (buying) but AI says selling")
            severity = "MAJOR"

    # 3. Number accuracy (Nifty levels)
    nifty = ground_truth.get("nifty_close")
    if nifty:
        for num_str in claims.get("numbers", []):
            try:
                num = int(num_str.replace(",", ""))
                if abs(num - nifty) / nifty > 0.02 and 20000 < num < 30000:
                    issues.append(f"NUMBER MISMATCH: AI mentions {num} but Nifty is {nifty}")
                    severity = max(severity, "MINOR", key=lambda x: ["OK", "MINOR", "MAJOR"].index(x))
            except ValueError:
                pass

    # 4. Consistency check
    if not issues:
        status = "CONSISTENT"
    elif severity == "MAJOR":
        status = "MAJOR CONTRADICTION"
    else:
        status = "MINOR MISMATCH"

    return {
        "status": status,
        "severity": severity,
        "issues": issues,
        "claims": claims,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATION DECISION
# ═══════════════════════════════════════════════════════════════════════════════

def validate_output(ai_text: str, ground_truth: Dict) -> Dict:
    """
    Full validation pipeline.
    Returns: {send: bool, reason: str, issues: list, fallback_text: str}
    """
    claims = extract_claims(ai_text)
    validation = validate_against_ground_truth(claims, ground_truth)

    if validation["status"] == "CONSISTENT":
        return {
            "send": True,
            "reason": "AI output consistent with ground truth",
            "issues": [],
            "fallback_text": None,
        }
    elif validation["status"] == "MINOR MISMATCH":
        return {
            "send": True,
            "reason": f"Minor mismatch — sending with note: {validation['issues'][0]}",
            "issues": validation["issues"],
            "fallback_text": None,
        }
    else:
        # Major contradiction — use fallback
        fallback = _generate_fallback(ground_truth)
        return {
            "send": False,
            "reason": f"Major contradiction detected — using raw data fallback",
            "issues": validation["issues"],
            "fallback_text": fallback,
        }


def _generate_fallback(ground_truth: Dict) -> str:
    """Generate raw data fallback when AI output is contradictory."""
    lines = ["[MARKET DATA — AI output discarded due to contradictions]"]

    bull_bear = ground_truth.get("bull_bear_score")
    if bull_bear is not None:
        lines.append(f"  Bull/Bear Score: {bull_bear}/100")

    fii = ground_truth.get("fii_net")
    if fii is not None:
        lines.append(f"  FII Net: ₹{fii:+,.0f}Cr")

    nifty = ground_truth.get("nifty_close")
    if nifty:
        lines.append(f"  Nifty: {nifty:,.0f}")

    pcr = ground_truth.get("pcr")
    if pcr:
        lines.append(f"  PCR: {pcr:.2f}")

    vix = ground_truth.get("india_vix")
    if vix:
        lines.append(f"  VIX: {vix:.1f}")

    lines.append("")
    lines.append("  Note: AI brief was discarded due to data contradictions.")
    lines.append("  Raw data provided instead. Manual review recommended.")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Test: AI says bullish but data says bearish
    test_ai = "Markets showing resilience with bullish momentum. FII buying supportive."
    test_truth = {"bull_bear_score": 35, "fii_net": -1500, "nifty_close": 25400}

    result = validate_output(test_ai, test_truth)
    print(f"Send: {result['send']}")
    print(f"Reason: {result['reason']}")
    for issue in result["issues"]:
        print(f"  Issue: {issue}")
    if result["fallback_text"]:
        print(f"\nFallback:\n{result['fallback_text']}")
