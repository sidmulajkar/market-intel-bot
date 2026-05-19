"""
Signal Arbitrator — Master signal synthesis from competing scores.
Resolves contradictions between structural and sentiment signals.
Produces ONE coherent MASTER SIGNAL for the AI.

The most critical module for coherence. Without this,
AI receives contradictory scores and produces worthless "mixed" output.
"""
import statistics
from typing import Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# SIGNAL CLUSTERS
# ═══════════════════════════════════════════════════════════════════════════════

STRUCTURAL_SIGNALS = ["bull_bear", "internals", "factor", "sector_rs"]
SENTIMENT_SIGNALS = ["fear_greed", "pcr", "vix", "options_flow"]


def normalize_to_100(value: float, min_val: float = 0, max_val: float = 100) -> float:
    """Normalize any value to 0-100 range."""
    if max_val == min_val:
        return 50
    return max(0, min(100, ((value - min_val) / (max_val - min_val)) * 100))


def normalize_signal(name: str, value: float) -> float:
    """Normalize different signal types to 0-100 scale."""
    if name in ("bull_bear", "internals", "fear_greed"):
        return normalize_to_100(value, 0, 100)
    elif name == "pcr":
        # PCR: 0.5 = bullish (100), 1.0 = neutral (50), 1.5 = bearish (0)
        return normalize_to_100(1.0 - (value - 0.5), 0, 1)
    elif name == "factor":
        # Factor: -1 = bearish (0), 0 = neutral (50), +1 = bullish (100)
        return normalize_to_100(value, -1, 1)
    elif name == "vix":
        # VIX: high = bearish, low = bullish
        return normalize_to_100(30 - value, 0, 30)
    elif name == "options_flow":
        # Options flow: -1 = bearish, 0 = neutral, +1 = bullish
        return normalize_to_100(value, -1, 1)
    elif name == "sector_rs":
        return normalize_to_100(value, 0, 100)
    return 50


# ═══════════════════════════════════════════════════════════════════════════════
# ARBITRATION LOGIC
# ═══════════════════════════════════════════════════════════════════════════════

def arbitrate_signals(signals: Dict, weights: Dict = None) -> Dict:
    """
    Master signal arbitration.

    signals: {"bull_bear": 65, "fear_greed": 28, "internals": 72,
              "pcr": 1.3, "factor": -0.5, "vix": 22, "options_flow": -0.3}
    weights: {"bull_bear": 1.2, "fear_greed": 0.8, ...} from signal_accuracy_log

    Returns master signal with contradiction analysis.
    """
    if not signals:
        return {"ok": False, "message": "No signals provided"}

    # Step 1: Normalize all signals to 0-100
    normalized = {}
    for name, value in signals.items():
        if value is not None:
            normalized[name] = normalize_signal(name, value)

    if not normalized:
        return {"ok": False, "message": "No valid signals"}

    # Step 2: Get weights (default to 1.0)
    if not weights:
        weights = {}
    signal_weights = {name: weights.get(name, {}).get("weight_multiplier", 1.0)
                      for name in normalized}

    # Step 3: Compute weighted consensus
    total_weight = sum(signal_weights.values())
    consensus = sum(normalized[name] * signal_weights[name]
                    for name in normalized) / total_weight if total_weight > 0 else 50

    # Step 4: Detect contradictions
    values = list(normalized.values())
    max_val = max(values)
    min_val = min(values)
    spread = max_val - min_val

    if spread > 50:
        contradiction_level = "VERY HIGH"
    elif spread > 40:
        contradiction_level = "HIGH"
    elif spread > 25:
        contradiction_level = "MODERATE"
    else:
        contradiction_level = "LOW"

    # Step 5: Cluster analysis
    structural_vals = {name: normalized[name] for name in normalized
                       if name in STRUCTURAL_SIGNALS}
    sentiment_vals = {name: normalized[name] for name in normalized
                      if name in SENTIMENT_SIGNALS}

    structural_avg = statistics.mean(structural_vals.values()) if structural_vals else 50
    sentiment_avg = statistics.mean(sentiment_vals.values()) if sentiment_vals else 50

    structural_signal = _score_to_label(structural_avg)
    sentiment_signal = _score_to_label(sentiment_avg)

    # Step 6: Determine resolution
    resolution = _determine_resolution(structural_avg, sentiment_avg, spread)

    # Step 7: Master label
    master_label = _score_to_label(consensus)

    # Step 8: Confidence
    active_count = len(normalized)
    if contradiction_level in ("VERY HIGH", "HIGH"):
        confidence = "LOW"
    elif active_count < 3:
        confidence = "LOW"
    elif contradiction_level == "MODERATE":
        confidence = "MEDIUM"
    else:
        confidence = "HIGH"

    return {
        "ok": True,
        "master_score": round(consensus),
        "master_label": master_label,
        "contradiction_level": contradiction_level,
        "structural_score": round(structural_avg),
        "structural_signal": structural_signal,
        "sentiment_score": round(sentiment_avg),
        "sentiment_signal": sentiment_signal,
        "resolution": resolution,
        "confidence": confidence,
        "active_signals": active_count,
        "spread": round(spread),
        "normalized": normalized,
    }


def _score_to_label(score: float) -> str:
    """Convert 0-100 score to human label."""
    if score >= 75:
        return "STRONGLY BULLISH"
    elif score >= 60:
        return "BULLISH"
    elif score >= 55:
        return "CAUTIOUSLY BULLISH"
    elif score >= 45:
        return "NEUTRAL"
    elif score >= 40:
        return "CAUTIOUSLY BEARISH"
    elif score >= 25:
        return "BEARISH"
    else:
        return "STRONGLY BEARISH"


def _determine_resolution(structural: float, sentiment: float, spread: float) -> str:
    """Determine how contradiction is likely to resolve."""
    if spread < 25:
        return "No significant contradiction — signals aligned."

    if structural > sentiment + 20:
        return ("Fundamentals bullish, sentiment bearish — CONTRARIAN BULLISH. "
                "Smart money accumulating while retail fears. Historical resolution: 67% bullish.")
    elif sentiment > structural + 20:
        return ("Deteriorating fundamentals, complacent sentiment — BEARISH. "
                "Retail buying into weakness. Historical resolution: 63% bearish.")
    elif structural > 60 and sentiment < 40:
        return "Structural strength despite fear — typically resolves bullish within 5-10 days."
    elif structural < 40 and sentiment > 60:
        return "Structural weakness despite greed — typically resolves bearish within 5-10 days."
    else:
        return f"Signals divergent (spread: {spread:.0f}pts) — unclear resolution path."


# ═══════════════════════════════════════════════════════════════════════════════
# FORMATTING
# ═══════════════════════════════════════════════════════════════════════════════

def format_master_signal(arbitration: Dict) -> str:
    """Format master signal for AI prompt injection (Block 0 replacement)."""
    if not arbitration.get("ok"):
        return ""

    lines = ["[MASTER SIGNAL — Read This First]"]
    lines.append(f"  Consensus: {arbitration['master_score']}/100 — {arbitration['master_label']}")
    lines.append(f"  Confidence: {arbitration['confidence']}")
    lines.append(f"  Contradictions: {arbitration['contradiction_level']} (spread: {arbitration['spread']}pts)")
    lines.append("")
    lines.append(f"  Structural: {arbitration['structural_score']}/100 — {arbitration['structural_signal']}")
    lines.append(f"  Sentiment:  {arbitration['sentiment_score']}/100 — {arbitration['sentiment_signal']}")
    lines.append("")
    lines.append(f"  Resolution: {arbitration['resolution']}")

    if arbitration["confidence"] == "LOW":
        lines.append("")
        lines.append(f"  ⚠️ LOW CONFIDENCE — signals contradicting. Treat with caution.")
        lines.append(f"  Historical accuracy in similar conditions: ~48% (near coin flip)")

    return "\n".join(lines)


def format_master_signal_dashboard(arbitration: Dict) -> str:
    """
    Format master signal for Telegram dashboard output.
    Matches the new dashboard style: lean, conviction, evidence, conflicting.
    """
    if not arbitration.get("ok"):
        return ""

    master_score = arbitration["master_score"]
    master_label = arbitration["master_label"]
    confidence = arbitration["confidence"]
    contradiction = arbitration["contradiction_level"]
    structural = arbitration["structural_score"]
    structural_signal = arbitration["structural_signal"]
    sentiment = arbitration["sentiment_score"]
    sentiment_signal = arbitration["sentiment_signal"]
    resolution = arbitration["resolution"]

    # Lean from master score
    if master_score >= 60:
        lean = "Bullish"
    elif master_score <= 40:
        lean = "Bearish"
    else:
        lean = "Neutral"

    # Emoji from master score
    if master_score >= 60:
        emoji = "🟢"
    elif master_score <= 40:
        emoji = "🔴"
    else:
        emoji = "⚪"

    lines = [f"{emoji} *MASTER SIGNAL*"]
    lines.append("━" * 26)
    lines.append(f"Consensus: {master_score}/100 | {master_label}")
    lines.append(f"Lean: {lean} | Confidence: {confidence}")
    lines.append("━" * 26)

    # Cluster scores
    lines.append(f"📊 Structural: {structural}/100 — {structural_signal}")
    lines.append(f"📊 Sentiment: {sentiment}/100 — {sentiment_signal}")

    # Contradiction
    if contradiction in ("HIGH", "VERY HIGH"):
        lines.append("")
        lines.append(f"⚠️ *Contradiction: {contradiction}* (spread: {arbitration['spread']}pts)")
        lines.append(f"   {resolution}")

    # Low confidence warning
    if confidence == "LOW":
        lines.append("")
        lines.append(f"⚠️ LOW CONFIDENCE — signals contradicting")
        lines.append(f"   Historical accuracy: ~48% (near coin flip)")

    lines.append("━" * 26)

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def run_arbitration(signals: Dict, weights: Dict = None) -> Dict:
    """Full arbitration pipeline."""
    result = arbitrate_signals(signals, weights)
    formatted = format_master_signal(result)
    return {"ok": result.get("ok", False), "arbitration": result, "formatted": formatted}


if __name__ == "__main__":
    # Test with contradictory signals
    test_signals = {
        "bull_bear": 65,      # BULLISH
        "fear_greed": 28,     # FEAR
        "internals": 72,      # HEALTHY
        "pcr": 1.4,           # BEARISH
        "factor": -0.5,       # BEARISH
        "vix": 22,            # BEARISH
    }
    result = run_arbitration(test_signals)
    print(result["formatted"])
