"""
Signal Arbitrator — Master signal synthesis from competing scores.
Resolves contradictions between structural and sentiment signals.
Produces ONE coherent MASTER SIGNAL for the AI.

Phase 19: Diagnostic Engine upgrade — gap analysis, confidence split,
score trending, consequence layer. Turns the block from a label into
an institutional-grade diagnostic.
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
        # VIX: high = bearish, low = bullish (wider range for crisis differentiation)
        return normalize_to_100(50 - value, 0, 50)
    elif name == "options_flow":
        # Options flow: -1 = bearish, 0 = neutral, +1 = bullish
        return normalize_to_100(value, -1, 1)
    elif name == "sector_rs":
        return normalize_to_100(value, 0, 100)
    return 50


# ═══════════════════════════════════════════════════════════════════════════════
# GAP ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_gap_analysis(structural: float, sentiment: float) -> Dict:
    """
    Analyze the gap between structural and sentiment clusters.
    The gap IS the signal when it's large enough.
    """
    gap = abs(structural - sentiment)

    # Classify gap size
    if gap < 5:
        gap_label = "ALIGNMENT"
        gap_meaning = "Signals agree — direction more reliable"
    elif gap < 10:
        gap_label = "MILD DIVERGENCE"
        gap_meaning = "Minor disagreement — monitor for widening"
    elif gap < 15:
        gap_label = "SIGNIFICANT DIVERGENCE"
        gap_meaning = "Real conflict — regime transition likely"
    else:
        gap_label = "EXTREME DIVERGENCE"
        gap_meaning = "Major dislocation — mean reversion opportunity"

    # Determine direction of gap
    if sentiment < structural:
        direction = "FEAR_EXCEEDING_FUNDAMENTALS"
        direction_text = "Fear exceeding fundamentals"
        contrarian_lean = "bullish"  # sentiment overshot down
    elif sentiment > structural:
        direction = "COMPLACENCY_EXCEEDING_FUNDAMENTALS"
        direction_text = "Complacency exceeding fundamentals"
        contrarian_lean = "bearish"  # sentiment overshot up
    else:
        direction = "ALIGNED"
        direction_text = "Clusters aligned"
        contrarian_lean = "neutral"

    return {
        "gap": round(gap),
        "gap_label": gap_label,
        "gap_meaning": gap_meaning,
        "direction": direction,
        "direction_text": direction_text,
        "contrarian_lean": contrarian_lean,
        "is_significant": gap >= 10,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIDENCE SPLIT
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_confidence_split(contradiction_level: str, active_count: int,
                               gap_analysis: Dict) -> Dict:
    """
    Split confidence into directional vs regime.
    When clusters diverge: direction is LOW, but regime is HIGH.
    """
    # Base directional confidence
    if contradiction_level in ("VERY HIGH", "HIGH"):
        directional = "LOW"
    elif active_count < 3:
        directional = "LOW"
    elif contradiction_level == "MODERATE":
        directional = "MEDIUM"
    else:
        directional = "HIGH"

    # Regime confidence: HIGH when gap is significant (divergence = predictable regime)
    if gap_analysis.get("is_significant"):
        regime = "HIGH"
        regime_text = "divergence = choppy conditions"
    else:
        regime = directional
        regime_text = "aligned signals = trending conditions"

    return {
        "directional": directional,
        "directional_pct": 48 if directional == "LOW" else (65 if directional == "MEDIUM" else 78),
        "regime": regime,
        "regime_text": regime_text,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SCORE TRENDING
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_score_trending(current_score: float, historical_scores: list = None) -> Dict:
    """
    Compute score trending: previous day, 30D avg, percentile.
    Filters by data_quality='real' — suppresses 30D/percentile when <10 real rows.
    Yesterday comparison is always valid (even 1 real row).
    """
    result = {
        "prev_score": None,
        "avg_30d": None,
        "percentile_1y": None,
        "direction": None,
        "change": None,
        "is_historically_weak": False,
        "is_historically_strong": False,
        "real_days": 0,
        "data_sufficient": False,
    }

    if not historical_scores or len(historical_scores) < 1:
        return result

    try:
        # Filter to real data only (exclude estimated_from_prices)
        real_scores = []
        for s in historical_scores:
            if s.get("bull_bear_score") is not None:
                quality = s.get("data_quality", "real")
                if quality == "real":
                    real_scores.append(s["bull_bear_score"])

        # Also include all scores for yesterday comparison (even estimated)
        all_scores = [s.get("bull_bear_score") for s in historical_scores
                      if s.get("bull_bear_score") is not None]

        if len(all_scores) < 1:
            return result

        # Yesterday comparison: always valid (last entry)
        result["prev_score"] = round(all_scores[-1])

        # Direction (uses all scores — yesterday is always valid)
        change = current_score - result["prev_score"]
        result["change"] = round(change)
        if abs(change) >= 3:
            result["direction"] = "↑" if change > 0 else "↓"

        # Real data count
        result["real_days"] = len(real_scores)

        # 30D avg + percentile: only when ≥10 real rows
        if len(real_scores) >= 10:
            result["data_sufficient"] = True
            all_real = real_scores + [current_score]
            last_30 = all_real[-30:] if len(all_real) >= 30 else all_real
            result["avg_30d"] = round(statistics.mean(last_30))

            below = sum(1 for s in real_scores if s < current_score)
            result["percentile_1y"] = round((below / len(real_scores)) * 100)

            result["is_historically_weak"] = result["percentile_1y"] < 20
            result["is_historically_strong"] = result["percentile_1y"] > 80

    except Exception:
        pass

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# CONSEQUENCE LAYER
# ═══════════════════════════════════════════════════════════════════════════════

def _confidence_language(level: str) -> str:
    """Translate confidence level to plain English."""
    mapping = {
        "LOW": "Mixed signals — treat as noise",
        "MEDIUM": "Mild lean — monitor, don't act",
        "HIGH": "Clear pattern — consider positioning",
    }
    return mapping.get(level, level)


def _detect_regime(signals: Dict = None) -> Dict:
    """
    Pre-label the market regime before arbitration.
    This tells the AI WHICH narrative to write, not just the direction.
    """
    if not signals:
        return {"regime": "UNKNOWN", "label": "Insufficient data for regime detection"}

    fii = signals.get("fii_net", 0)
    dxy_change = signals.get("dxy_change", 0)
    vix = signals.get("vix", 15)
    dii_absorption = signals.get("dii_absorption", 0)

    try:
        fii = float(fii) if fii else 0
        dxy_change = float(dxy_change) if dxy_change else 0
        vix = float(vix) if vix else 15
        dii_absorption = float(dii_absorption) if dii_absorption else 0
    except (ValueError, TypeError):
        return {"regime": "UNKNOWN", "label": "Data type error in regime detection"}

    # Regime detection logic
    if fii < -1000 and abs(dxy_change) < 0.3 and vix < 18:
        return {
            "regime": "INDIA_SPECIFIC_SELLING",
            "label": "India-specific selling — not global risk-off",
            "implication": "Domestic factors driving outflow, not EM-wide exit"
        }
    elif fii < -1000 and dxy_change > 0.3 and vix > 18:
        return {
            "regime": "GLOBAL_RISK_OFF",
            "label": "Global risk-off — EM-wide selling pressure",
            "implication": "All EM assets under pressure, not India-specific"
        }
    elif fii < -1000 and dii_absorption > 0.8:
        return {
            "regime": "MANAGED_CORRECTION",
            "label": "Managed correction — DII absorbing most selling",
            "implication": "Floor exists, panic unwarranted"
        }
    elif fii > 500 and vix < 15:
        return {
            "regime": "RISK_ON",
            "label": "Risk-on — foreign buying with low fear",
            "implication": "Momentum supportive"
        }
    elif vix > 25:
        return {
            "regime": "FEAR_REGIME",
            "label": "Fear regime — elevated volatility",
            "implication": "Options expensive, defensive positioning"
        }
    else:
        return {
            "regime": "NEUTRAL",
            "label": "No dominant regime detected",
            "implication": "Mixed signals, no clear directional bias"
        }


def _generate_signal_consequence(arbitration: Dict, signals: Dict = None) -> list:
    """
    Derive actionable implications from the signal configuration.
    Signal strength language only — no position sizing numbers.
    """
    implications = []
    structural = arbitration.get("structural_score", 50)
    sentiment = arbitration.get("sentiment_score", 50)
    gap = abs(structural - sentiment)
    confidence = arbitration.get("confidence", "MEDIUM")

    # Regime detection (pre-labels the narrative)
    regime = _detect_regime(signals)
    if regime.get("regime") != "UNKNOWN":
        implications.append(f"Regime: {regime['label']}")

    # FII context (from signals if available)
    fii_signal = signals.get("fii_streak") if signals else None
    vix_val = signals.get("vix") if signals else None

    # Gap-based implications
    if gap >= 15:
        implications.append("Mean reversion opportunity if timing right")
    elif gap >= 10:
        implications.append("Reduce momentum exposure while divergence persists")

    # Structural implications
    if structural < 40:
        implications.append("Structural weakness — defensive allocation warranted")
    elif structural < 45:
        implications.append("Watch: Structural score falling below 40 → confirmed bearish")
    elif structural > 55:
        implications.append("No structural breakdown yet — floor exists")

    # Sentiment implications
    if sentiment < 30:
        implications.append("Extreme fear — contrarian buy signal if structural holds")
    elif sentiment < 40:
        implications.append("Defensive sectors favored while sentiment remains weak")

    # VIX implications
    if vix_val and vix_val > 20:
        implications.append("Options premium expansion likely")

    # Confidence-based
    if confidence == "LOW" and gap >= 10:
        implications.append("Regime: choppy/rangebound — not trending")

    # Cap at 4 implications
    return implications[:4]


# ═══════════════════════════════════════════════════════════════════════════════
# ARBITRATION LOGIC
# ═══════════════════════════════════════════════════════════════════════════════

def arbitrate_signals(signals: Dict, weights: Dict = None,
                      historical_scores: list = None,
                      nifty_percentile: float = None) -> Dict:
    """
    Master signal arbitration.

    signals: {"bull_bear": 65, "fear_greed": 28, "internals": 72,
              "pcr": 1.3, "factor": -0.5, "vix": 22, "options_flow": -0.3}
    weights: {"bull_bear": 1.2, "fear_greed": 0.8, ...} from signal_accuracy_log
    historical_scores: last 30+ days of {date, bull_bear_score, structural_score, sentiment_score}
    nifty_percentile: optional, for accumulation/distribution detection

    Returns master signal with gap analysis, confidence split, trending, consequence.
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

    # Step 6: Gap analysis (Phase 19)
    gap_analysis = _compute_gap_analysis(structural_avg, sentiment_avg)

    # Step 7: Confidence split (Phase 19)
    active_count = len(normalized)
    confidence_split = _compute_confidence_split(contradiction_level, active_count, gap_analysis)

    # Step 8: Score trending (Phase 19)
    trending = _compute_score_trending(consensus, historical_scores)

    # Step 9: Determine resolution
    resolution = _determine_resolution(structural_avg, sentiment_avg, spread)

    # Step 10: Master label
    master_label = _score_to_label(consensus)

    # Step 11: Consequence layer (Phase 19)
    consequence = _generate_signal_consequence(
        {"structural_score": round(structural_avg), "sentiment_score": round(sentiment_avg),
         "confidence": confidence_split["directional"], "gap_analysis": gap_analysis},
        signals
    )

    return {
        "ok": True,
        "master_score": round(consensus),
        "master_label": master_label,
        "contradiction_level": contradiction_level,
        "structural_score": round(structural_avg),
        "structural_signal": structural_signal,
        "structural_drivers": _get_cluster_drivers(structural_vals, normalized),
        "sentiment_score": round(sentiment_avg),
        "sentiment_signal": sentiment_signal,
        "sentiment_drivers": _get_cluster_drivers(sentiment_vals, normalized),
        "resolution": resolution,
        "confidence": confidence_split["directional"],
        "confidence_split": confidence_split,
        "gap_analysis": gap_analysis,
        "trending": trending,
        "consequence": consequence,
        "active_signals": active_count,
        "spread": round(spread),
        "normalized": normalized,
        "nifty_percentile": nifty_percentile,
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


def _get_cluster_drivers(cluster_vals: Dict, all_normalized: Dict) -> str:
    """Generate human-readable drivers for a cluster."""
    if not cluster_vals:
        return "no data"

    drivers = []
    for name, val in sorted(cluster_vals.items(), key=lambda x: x[1]):
        label = _score_to_label(val)
        if "BEARISH" in label:
            drivers.append(f"{name} bearish")
        elif "BULLISH" in label:
            drivers.append(f"{name} bullish")

    if not drivers:
        return "mixed signals"

    return ", ".join(drivers[:3])


def _determine_resolution(structural: float, sentiment: float, spread: float) -> str:
    """Determine how contradiction is likely to resolve."""
    if spread < 25:
        return "No significant contradiction — signals aligned."

    if structural > sentiment + 20:
        return ("Fundamentals bullish, sentiment bearish — CONTRARIAN signal. "
                "Smart money accumulating while retail fears.")
    elif sentiment > structural + 20:
        return ("Deteriorating fundamentals, complacent sentiment — BEARISH signal. "
                "Retail buying into weakness.")
    elif structural > 60 and sentiment < 40:
        return "Structural strength despite fear — typically resolves bullish within 5-10 days."
    elif structural < 40 and sentiment > 60:
        return "Structural weakness despite greed — typically resolves bearish within 5-10 days."
    else:
        return f"Signals divergent (spread: {spread:.0f}pts) — unclear resolution path."


# ═══════════════════════════════════════════════════════════════════════════════
# FORMATTING — AI PROMPT (Block 0)
# ═══════════════════════════════════════════════════════════════════════════════

def format_master_signal(arbitration: Dict) -> str:
    """
    Format master signal for AI prompt injection (Block 0 replacement).
    Phase 19: Diagnostic engine — gap analysis, confidence split, trending, consequence.
    Max 12-15 lines.
    """
    if not arbitration.get("ok"):
        return ""

    lines = ["[MASTER SIGNAL — Read This First]"]

    # Score with trending (data quality aware)
    score_line = f"Score: {arbitration['master_score']}/100"
    trending = arbitration.get("trending", {})
    if trending.get("direction"):
        score_line += f" {trending['direction']}"
    if trending.get("prev_score") is not None:
        score_line += f" (was {trending['prev_score']}"
        if trending.get("data_sufficient"):
            # Sufficient real data — show full trending
            if trending.get("avg_30d") is not None:
                score_line += f" | 30D avg: {trending['avg_30d']}"
            if trending.get("percentile_1y") is not None:
                pct = trending["percentile_1y"]
                score_line += f" | {pct}th %ile"
                if trending.get("is_historically_weak"):
                    score_line += " — weak"
                elif trending.get("is_historically_strong"):
                    score_line += " — strong"
        else:
            # Insufficient real data — show yesterday only
            real_days = trending.get("real_days", 0)
            score_line += f" | 30D avg: accumulating ({real_days}/30 real days)"
        score_line += ")"
    lines.append(score_line)
    lines.append(f"Lean: {arbitration['master_label']}")

    # Structural cluster (compact)
    lines.append(f"Structural: {arbitration['structural_score']}/100 — {arbitration['structural_signal']}")

    # Sentiment cluster (compact)
    lines.append(f"Sentiment: {arbitration['sentiment_score']}/100 — {arbitration['sentiment_signal']}")

    # Gap analysis (only if significant)
    gap = arbitration.get("gap_analysis", {})
    if gap.get("is_significant"):
        lines.append(f"GAP: {gap['gap']}pts — {gap['direction_text']}, {gap['gap_meaning']}")

    # Composite tension note (when gap >15 and composite is NEUTRAL)
    composite = arbitration.get("master_score", 50)
    if gap.get("gap", 0) > 15 and 45 <= composite <= 55:
        lines.append(f"NOTE: Composite masks extreme internal tension — structural near-bullish, sentiment near-bearish")

    # Accumulation/Distribution signal (when price percentile diverges from composite)
    if arbitration.get("nifty_percentile") is not None:
        nifty_pct = arbitration["nifty_percentile"]
        if nifty_pct < 20 and composite > 55:
            lines.append(f"NOTE: Nifty at {nifty_pct}th %ile while structural bullish = accumulation zone")
        elif nifty_pct > 80 and composite < 45:
            lines.append(f"NOTE: Nifty at {nifty_pct}th %ile while structural bearish = distribution zone")

    # Confidence split (compact)
    conf_split = arbitration.get("confidence_split", {})
    if gap.get("is_significant"):
        lines.append(f"Confidence: {_confidence_language(conf_split.get('directional', 'N/A'))} ({conf_split.get('directional_pct', '?')}%), "
                     f"Regime={conf_split.get('regime', 'N/A')} — {conf_split.get('regime_text', '')}")
    else:
        lines.append(f"Confidence: {_confidence_language(arbitration['confidence'])}")

    # Consequence / Implication
    consequence = arbitration.get("consequence", [])
    if consequence:
        lines.append("Implication:")
        for item in consequence:
            lines.append(f"  • {item}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# FORMATTING — TELEGRAM DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

def format_master_signal_dashboard(arbitration: Dict) -> str:
    """
    Format master signal for Telegram dashboard output.
    Phase 19: Diagnostic engine with gap analysis, confidence split, trending, consequence.
    """
    if not arbitration.get("ok"):
        return ""

    master_score = arbitration["master_score"]
    master_label = arbitration["master_label"]
    confidence = arbitration["confidence"]
    structural = arbitration["structural_score"]
    sentiment = arbitration["sentiment_score"]
    gap = arbitration.get("gap_analysis", {})
    trending = arbitration.get("trending", {})
    conf_split = arbitration.get("confidence_split", {})
    consequence = arbitration.get("consequence", [])

    # Emoji from master score
    if master_score >= 60:
        emoji = "🟢"
    elif master_score <= 40:
        emoji = "🔴"
    else:
        emoji = "⚪"

    lines = [f"{emoji} *MASTER SIGNAL*"]
    lines.append("━" * 26)

    # Score with trending (data quality aware)
    score_line = f"Score: {master_score}/100"
    if trending.get("direction"):
        score_line += f" {trending['direction']}"
    if trending.get("prev_score") is not None:
        score_line += f" (was {trending['prev_score']}"
        if trending.get("data_sufficient"):
            if trending.get("avg_30d") is not None:
                score_line += f" | 30D avg: {trending['avg_30d']}"
            if trending.get("percentile_1y") is not None:
                pct = trending["percentile_1y"]
                score_line += f" | {pct}th %ile"
                if trending.get("is_historically_weak"):
                    score_line += " — historically weak"
                elif trending.get("is_historically_strong"):
                    score_line += " — historically strong"
        else:
            real_days = trending.get("real_days", 0)
            score_line += f" | 30D avg: accumulating ({real_days}/30 real days)"
        score_line += ")"
    lines.append(score_line)
    lines.append(f"Lean: {master_label}")
    lines.append("━" * 26)

    # Cluster scores
    lines.append(f"📊 Structural: {structural}/100 — {arbitration['structural_signal']}")
    drivers = arbitration.get("structural_drivers", "")
    if drivers:
        lines.append(f"   [{drivers}]")

    lines.append(f"📊 Sentiment: {sentiment}/100 — {arbitration['sentiment_signal']}")
    drivers = arbitration.get("sentiment_drivers", "")
    if drivers:
        lines.append(f"   [{drivers}]")

    # Gap analysis
    if gap.get("gap", 0) >= 5:
        lines.append("")
        lines.append(f"📐 *GAP: {gap['gap']}pts — {gap['gap_label']}*")
        lines.append(f"   → {gap['direction_text']}")
        lines.append(f"   → {gap['gap_meaning']}")

    # Confidence split
    lines.append("")
    if gap.get("is_significant"):
        lines.append(f"🎯 *Confidence:*")
        lines.append(f"   Directional: {_confidence_language(conf_split.get('directional', 'N/A'))} ({conf_split.get('directional_pct', '?')}% accuracy)")
        lines.append(f"   Regime: {conf_split.get('regime', 'N/A')} — {conf_split.get('regime_text', '')}")
    else:
        lines.append(f"🎯 Confidence: {_confidence_language(confidence)}")

    # Consequence
    if consequence:
        lines.append("")
        lines.append("💡 *Implication:*")
        for item in consequence:
            lines.append(f"   • {item}")

    lines.append("━" * 26)

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def run_arbitration(signals: Dict, weights: Dict = None,
                    historical_scores: list = None,
                    nifty_percentile: float = None) -> Dict:
    """Full arbitration pipeline."""
    result = arbitrate_signals(signals, weights, historical_scores=historical_scores, nifty_percentile=nifty_percentile)
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
    # Mock historical scores for trending
    test_history = [
        {"date": "2026-05-01", "bull_bear_score": 55},
        {"date": "2026-05-02", "bull_bear_score": 52},
        {"date": "2026-05-03", "bull_bear_score": 48},
        {"date": "2026-05-04", "bull_bear_score": 45},
        {"date": "2026-05-05", "bull_bear_score": 42},
    ]
    result = run_arbitration(test_signals, historical_scores=test_history)
    print(result["formatted"])
