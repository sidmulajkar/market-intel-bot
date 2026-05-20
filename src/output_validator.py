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
    numbers += re.findall(r'\$\d{1,4}(?:,\d{3})*\.\d{1,2}\b', ai_text)  # Dollar amounts ($64.41, $109.8, $2,300.50)
    numbers += re.findall(r'₹\d{1,3}\.\d{1,2}\b', ai_text)  # USDINR (₹83.50)

    # Consequence indicators
    consequence_keywords = ["cad", "current account", "fii outflow", "inr pressure",
                            "annualized", "import bill", "margin", "subsidy",
                            "inflation", "depreciation", "appreciation"]
    has_consequence = any(kw in text_lower for kw in consequence_keywords)

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
        "has_consequence": has_consequence,
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

    # 4. Commodity price validation (Brent, Gold, USDINR)
    brent_actual = ground_truth.get("brent")
    if brent_actual:
        for num_str in claims.get("numbers", []):
            try:
                if num_str.startswith("$"):
                    num = float(num_str[1:])
                    if abs(num - brent_actual) / brent_actual > 0.15:  # >15% deviation
                        issues.append(f"COMMODITY MISMATCH: AI says {num_str} but Brent is ${brent_actual:.2f}")
                        severity = "MAJOR"
            except ValueError:
                pass

    gold_actual = ground_truth.get("gold")
    if gold_actual:
        for num_str in claims.get("numbers", []):
            try:
                if num_str.startswith("$"):
                    num = float(num_str[1:])
                    # Gold is typically 1500-3000 range
                    if 1000 < num < 5000 and abs(num - gold_actual) / gold_actual > 0.10:
                        issues.append(f"COMMODITY MISMATCH: AI says {num_str} but Gold is ${gold_actual:.2f}")
                        severity = "MAJOR"
            except ValueError:
                pass

    usdinr_actual = ground_truth.get("usdinr")
    if usdinr_actual:
        for num_str in claims.get("numbers", []):
            try:
                if num_str.startswith("₹"):
                    num = float(num_str[1:])
                    if abs(num - usdinr_actual) / usdinr_actual > 0.05:  # >5% deviation
                        issues.append(f"FX MISMATCH: AI says {num_str} but USDINR is ₹{usdinr_actual:.2f}")
                        severity = "MAJOR"
            except ValueError:
                pass

    # 5. Consequence presence check (soft warning)
    if not claims.get("has_consequence"):
        issues.append("CONSEQUENCE ABSENT: No India-impact consequence indicators found")
        if severity == "OK":
            severity = "MINOR"

    # Consistency check
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

    # Additional checks that need raw ai_text
    extra_issues = []
    extra_severity = "OK"
    text_lower = ai_text.lower()

    # Trade recommendation check
    advice_keywords = [
        'go long', 'go short', 'buy ', 'sell ', 'long on', 'short on',
        'enter position', 'exit position', 'take profit', 'stop loss',
        'long position', 'short position', 'short the',
        'consider adding', 'should outperform', 'recommend',
        'investors should', 'expect nifty to', 'expect market to'
    ]
    for kw in advice_keywords:
        if kw in text_lower:
            extra_issues.append(f"ADVICE VIOLATION: '{kw}' detected — trade recommendation prohibited")
            extra_severity = "MAJOR"
            break

    # Hallucinated percentage check
    hallucinated_pct = re.findall(
        r'\d+\s*(?:%|percent)\s*(?:bull|bear|bullish|bearish|probability|chance|likely|upside|downside)'
        r'|(?:bull|bear|bullish|bearish|probability|chance).*\d+\s*(?:%|percent)',
        text_lower
    )
    if hallucinated_pct:
        extra_issues.append(f"HALLUCINATED %: {hallucinated_pct[0]} — probabilities must be Python-computed")
        extra_severity = "MAJOR"

    # Hallucinated confidence check (unsubstantiated probability language)
    confidence_phrases = ['high probability', 'likely to', 'very likely', 'unlikely to',
                          'expected to rise', 'expected to fall', 'will rise', 'will fall']
    for phrase in confidence_phrases:
        if phrase in text_lower:
            extra_issues.append(f"HALLUCINATED CONFIDENCE: '{phrase}' — predictions must be conditional (If X → Y)")
            extra_severity = "MAJOR"
            break

    # Stale price level check
    nifty = ground_truth.get("nifty_close")
    sensex = ground_truth.get("sensex_close")
    if nifty or sensex:
        for num_str in claims.get("numbers", []):
            try:
                num = int(num_str.replace(",", ""))
                if nifty and 15000 < num < 30000:
                    if abs(num - nifty) / nifty > 0.15:
                        extra_issues.append(f"STALE LEVEL: {num} is {abs(num-nifty)/nifty*100:.0f}% from Nifty {nifty}")
                        extra_severity = "MAJOR"
                if sensex and 60000 < num < 90000:
                    if abs(num - sensex) / sensex > 0.15:
                        extra_issues.append(f"STALE LEVEL: {num} is {abs(num-sensex)/sensex*100:.0f}% from Sensex {sensex}")
                        extra_severity = "MAJOR"
            except ValueError:
                pass

    # Cross-block consistency checks
    consistency_issues = []
    fii_net = ground_truth.get("fii_net", 0) or 0
    nifty = ground_truth.get("nifty_close", 0) or 0
    dii_net = ground_truth.get("dii_net", 0) or 0
    absorption_pct = ground_truth.get("absorption_pct") or 0

    # Q1: Net impact direction vs Nifty direction
    if fii_net < 0 and dii_net > 0:
        effective = fii_net + dii_net
        if effective > 0 and claims.get("tone") == "BEARISH":
            consistency_issues.append("CONSISTENCY: Net FII+DII is positive but narrative is bearish")
        elif effective < 0 and claims.get("tone") == "BULLISH":
            consistency_issues.append("CONSISTENCY: Net FII+DII is negative but narrative is bullish")

    # Q2: Absorption vs regime label
    if absorption_pct > 100 and "weak" in text_lower:
        consistency_issues.append("CONSISTENCY: DII absorption >100% but narrative calls it 'weak'")
    elif absorption_pct < 50 and "strong floor" in text_lower:
        consistency_issues.append("CONSISTENCY: DII absorption <50% but narrative calls it 'strong floor'")

    # Q3: VIX vs volatility tone
    vix = ground_truth.get("india_vix", 0) or 0
    vix_percentile = ground_truth.get("vix_percentile") or 0
    if vix > 25 and "complacent" in text_lower:
        consistency_issues.append("CONSISTENCY: VIX >25 but narrative calls market 'complacent'")
    elif vix_percentile >= 70 and "complacent" in text_lower:
        consistency_issues.append(f"CONSISTENCY: VIX at {vix_percentile:.0f}th percentile but narrative calls market 'complacent'")
    elif vix < 15 and "fear" in text_lower and "no fear" not in text_lower:
        consistency_issues.append("CONSISTENCY: VIX <15 but narrative mentions 'fear'")

    if consistency_issues:
        extra_issues.extend(consistency_issues)
        if extra_severity != "MAJOR":  # Don't downgrade from MAJOR
            extra_severity = "MINOR"

    # Merge extra issues into validation result
    if extra_issues:
        validation["issues"] = validation.get("issues", []) + extra_issues
        if extra_severity == "MAJOR":
            validation["status"] = "MAJOR CONTRADICTION"

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

    brent = ground_truth.get("brent")
    if brent:
        lines.append(f"  Brent: ${brent:.2f}")

    gold = ground_truth.get("gold")
    if gold:
        lines.append(f"  Gold: ${gold:.2f}")

    usdinr = ground_truth.get("usdinr")
    if usdinr:
        lines.append(f"  USDINR: ₹{usdinr:.2f}")

    # Regime context — makes fallback actionable
    regime = ground_truth.get("cross_asset_regime")
    if regime:
        lines.append(f"  Regime: {regime}")

    absorption = ground_truth.get("absorption_pct")
    if absorption:
        try:
            absorption = float(absorption)
            lines.append(f"  Key: DII absorbing {absorption:.0f}% of FII outflow")
        except (ValueError, TypeError):
            pass

    bb = ground_truth.get("bull_bear_score")
    if bb is not None:
        if bb >= 60:
            lines.append("  Signal: Bullish lean — AI output rejected for data contradictions")
        elif bb <= 40:
            lines.append("  Signal: Bearish lean — AI output rejected for data contradictions")
        else:
            lines.append("  Signal: Mixed — no directional call")

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
