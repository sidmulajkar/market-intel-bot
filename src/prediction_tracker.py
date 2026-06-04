"""
Prediction Tracker — Parse AI output, store predictions, validate against outcomes.
Enables accuracy tracking and weekly reporting.
"""
import re
import os
import math
from datetime import datetime, timedelta
from typing import Dict, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# PARSE: Extract structured fields from AI output
# ═══════════════════════════════════════════════════════════════════════════════

def parse_ai_output(raw_text: str) -> Dict:
    """
    Extract regime, confidence, scenarios from AI output using regex.
    Returns dict with: regime, confidence, dominant_factor, bull_pct, base_pct, bear_pct, headline
    """
    if not raw_text:
        return {"ok": False, "message": "Empty output"}

    result = {
        "ok": True,
        "regime": None,
        "confidence": None,
        "dominant_factor": None,
        "bull_pct": None,
        "base_pct": None,
        "bear_pct": None,
        "headline": None,
    }

    # REGIME: Risk-on / Risk-off / Neutral only — "Transition" is not a regime
    regime_match = re.search(
        r"REGIME[:\s]+(Risk-on|Risk-off|Neutral)",
        raw_text, re.IGNORECASE
    )
    if regime_match:
        raw_regime = regime_match.group(1).strip()
        # Map AI labels to canonical regime set
        regime_map = {"Risk-on": "BULLISH", "Risk-off": "DEFENSIVE", "Neutral": "NEUTRAL"}
        result["regime"] = regime_map.get(raw_regime, raw_regime)

    # Confidence: HIGH / MEDIUM / LOW
    conf_match = re.search(
        r"Confidence[:\s]+(HIGH|MEDIUM|LOW)",
        raw_text, re.IGNORECASE
    )
    if conf_match:
        result["confidence"] = conf_match.group(1).upper()

    # Dominant factor
    dom_match = re.search(
        r"Dominant factor[:\s]+(.+?)(?:\n|$)",
        raw_text, re.IGNORECASE
    )
    if dom_match:
        result["dominant_factor"] = dom_match.group(1).strip()

    # Scenarios: Bull case (X%), Base case (Y%), Bear case (Z%)
    bull_match = re.search(r"Bull case\s*\((\d+)%\)", raw_text)
    base_match = re.search(r"Base case\s*\((\d+)%\)", raw_text)
    bear_match = re.search(r"Bear case\s*\((\d+)%\)", raw_text)

    if bull_match:
        result["bull_pct"] = int(bull_match.group(1))
    if base_match:
        result["base_pct"] = int(base_match.group(1))
    if bear_match:
        result["bear_pct"] = int(bear_match.group(1))

    # HEADLINE (first non-empty line after the headline marker)
    headline_match = re.search(
        r"HEADLINE[:\s]*\n(.+?)(?:\n|$)",
        raw_text, re.IGNORECASE
    )
    if headline_match:
        result["headline"] = headline_match.group(1).strip()

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# STORE: Save prediction to Supabase
# ═══════════════════════════════════════════════════════════════════════════════

def store_prediction(parsed: Dict, nifty_close: float, run_type: str = "morning") -> bool:
    """Store parsed prediction in daily_predictions table."""
    from src.db import get_client, today_str

    db = get_client()
    if not db:
        return False

    try:
        db.table("daily_predictions").upsert({
            "date":            today_str(),
            "run_type":        run_type,
            "regime":          parsed.get("regime"),
            "confidence":      parsed.get("confidence"),
            "dominant_factor": parsed.get("dominant_factor"),
            "bull_pct":        parsed.get("bull_pct"),
            "base_pct":        parsed.get("base_pct"),
            "bear_pct":        parsed.get("bear_pct"),
            "headline":        parsed.get("headline"),
            "nifty_close":     nifty_close,
            "raw_output":      None,  # Don't store full text (too large)
        }).execute()
        return True
    except Exception as e:
        print(f"⚠️ store_prediction: {e}")
        return False


def parse_and_store_prediction(raw_text: str, nifty_close: float, run_type: str = "morning") -> Dict:
    """Parse AI output and store prediction. Called from market_intel.py."""
    parsed = parse_ai_output(raw_text)

    if not parsed.get("regime"):
        print(f"⚠️ Could not parse regime from AI output")
        return parsed

    stored = store_prediction(parsed, nifty_close, run_type)
    if stored:
        print(f"📊 Prediction stored: {parsed['regime']} | "
              f"Bull {parsed.get('bull_pct')}% / Base {parsed.get('base_pct')}% / Bear {parsed.get('bear_pct')}%")

    return parsed


# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATE: Compare prediction against actual outcome
# ═══════════════════════════════════════════════════════════════════════════════

def compute_brier_score(predicted_probs: Dict[str, float], actual_outcome: str) -> float:
    """
    Compute Brier score for a single prediction.
    Lower is better. 0 = perfect, 0.25 = random baseline.

    predicted_probs: {"bull": 0.3, "base": 0.5, "bear": 0.2}
    actual_outcome: "bull" or "bear" (base is not a directional outcome)
    """
    # Convert to binary outcomes
    outcomes = {"bull": 0, "base": 0, "bear": 0}
    if actual_outcome in outcomes:
        outcomes[actual_outcome] = 1

    score = 0
    for key in ["bull", "base", "bear"]:
        p = predicted_probs.get(key, 0) / 100  # Convert from percentage
        o = outcomes[key]
        score += (p - o) ** 2

    return round(score, 4)


def determine_actual_outcome(nifty_change_pct: float) -> str:
    """
    Determine if market was bull, base, or bear based on actual change.
    Bull: > +0.5%, Bear: < -0.5%, Base: between
    """
    if nifty_change_pct > 0.5:
        return "bull"
    elif nifty_change_pct < -0.5:
        return "bear"
    else:
        return "base"


def determine_actual_regime(nifty_change_pct: float) -> str:
    """
    Determine actual regime based on market move.
    Risk-on: > +0.5%, Risk-off: < -0.5%, Neutral: between
    """
    if nifty_change_pct > 0.5:
        return "Risk-on"
    elif nifty_change_pct < -0.5:
        return "Risk-off"
    else:
        return "Neutral"


def validate_yesterday_prediction(nifty_closes: list = None) -> Dict:
    """
    Fetch yesterday's prediction, compare against today's Nifty close.
    Stores result in prediction_outcomes table.
    """
    from src.db import get_client

    db = get_client()
    if not db:
        return {"ok": False, "message": "DB unavailable"}

    try:
        # Get yesterday's prediction
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        result = (
            db.table("daily_predictions")
            .select("*")
            .eq("date", yesterday)
            .limit(1)
            .execute()
        )

        if not result.data:
            return {"ok": False, "message": f"No prediction found for {yesterday}"}

        prediction = result.data[0]
        pred_close = prediction.get("nifty_close")

        if not pred_close:
            return {"ok": False, "message": "No Nifty close in prediction"}

        # Get today's Nifty close
        if nifty_closes and len(nifty_closes) >= 1:
            today_close = nifty_closes[-1]
        else:
            import yfinance as yf
            hist = yf.Ticker("^NSEI").history(period="2d")["Close"].dropna()
            if len(hist) < 1:
                return {"ok": False, "message": "Cannot fetch Nifty close"}
            today_close = float(hist.iloc[-1])

        # Compute outcomes
        change_pct = round((today_close - pred_close) / pred_close * 100, 2)
        actual_outcome = determine_actual_outcome(change_pct)
        actual_regime = determine_actual_regime(change_pct)

        # Override check: if arbiter override was active yesterday,
        # use the arbiter's final_regime as actual (not Nifty-change proxy)
        try:
            from src.db import get_market_state
            ms = get_market_state(yesterday)
            if ms and ms.get("final_override_reason"):
                actual_regime = ms.get("final_regime", actual_regime)
        except Exception:
            pass

        # Check regime accuracy
        pred_regime = prediction.get("regime", "")
        # Fallback to arbiter's final_regime if AI prediction is empty or invalid
        if not pred_regime or pred_regime not in ("BULLISH", "NEUTRAL", "DEFENSIVE"):
            try:
                from src.db import get_market_state
                arbiter_state = get_market_state(yesterday)
                if arbiter_state and arbiter_state.get("final_regime"):
                    pred_regime = arbiter_state["final_regime"]
            except Exception:
                pass
        regime_correct = False
        if pred_regime:
            # Map predicted regime to direction
            pred_direction = "Risk-on" if "on" in pred_regime.lower() else \
                            "Risk-off" if "off" in pred_regime.lower() else "Neutral"
            regime_correct = (pred_direction == actual_regime)

        # Compute Brier score
        predicted_probs = {
            "bull": prediction.get("bull_pct", 33) or 33,
            "base": prediction.get("base_pct", 34) or 34,
            "bear": prediction.get("bear_pct", 33) or 33,
        }
        brier = compute_brier_score(predicted_probs, actual_outcome)

        # Store outcome
        db.table("prediction_outcomes").upsert({
            "prediction_date":     yesterday,
            "actual_nifty_close":  round(today_close, 2),
            "actual_nifty_change": change_pct,
            "regime_correct":      regime_correct,
            "bull_accuracy":       predicted_probs["bull"],
            "bear_accuracy":       predicted_probs["bear"],
            "brier_score":         brier,
        }).execute()

        result_str = "✅ CORRECT" if regime_correct else "❌ WRONG"
        print(f"📊 Validation: {yesterday} | Predicted: {pred_regime} | Actual: {actual_regime} ({change_pct:+.2f}%) | {result_str}")
        print(f"   Brier: {brier:.4f} (random=0.25, lower=better)")

        return {
            "ok": True,
            "prediction_date": yesterday,
            "predicted_regime": pred_regime,
            "actual_regime": actual_regime,
            "change_pct": change_pct,
            "regime_correct": regime_correct,
            "brier_score": brier,
        }

    except Exception as e:
        print(f"⚠️ validate_yesterday_prediction: {e}")
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# REPORT: Weekly accuracy statistics
# ═══════════════════════════════════════════════════════════════════════════════

def get_weekly_accuracy(days: int = 7) -> Dict:
    """
    Compute accuracy stats for the last N days.
    Returns: hit_rate, avg_brier, best_prediction, worst_prediction, trend
    """
    from src.db import get_client

    db = get_client()
    if not db:
        return {"ok": False}

    try:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        result = (
            db.table("prediction_outcomes")
            .select("*")
            .gte("prediction_date", cutoff)
            .order("prediction_date")
            .execute()
        )

        if not result.data or len(result.data) < 2:
            return {"ok": False, "message": f"Need at least 2 outcomes, have {len(result.data) if result.data else 0}"}

        outcomes = result.data
        total = len(outcomes)
        correct = sum(1 for o in outcomes if o.get("regime_correct"))
        hit_rate = round(correct / total * 100, 1)
        avg_brier = round(sum(o.get("brier_score", 0.25) for o in outcomes) / total, 4)

        # Best and worst
        best = max(outcomes, key=lambda o: 1 if o.get("regime_correct") else 0)
        worst = min(outcomes, key=lambda o: 1 if o.get("regime_correct") else 0)

        # Trend (first half vs second half)
        mid = total // 2
        first_half = sum(1 for o in outcomes[:mid] if o.get("regime_correct"))
        second_half = sum(1 for o in outcomes[mid:] if o.get("regime_correct"))
        if second_half > first_half:
            trend = "IMPROVING"
        elif second_half < first_half:
            trend = "DECLINING"
        else:
            trend = "STABLE"

        return {
            "ok": True,
            "total": total,
            "correct": correct,
            "hit_rate": hit_rate,
            "avg_brier": avg_brier,
            "best": {
                "date": best.get("prediction_date"),
                "correct": best.get("regime_correct"),
                "change": best.get("actual_nifty_change"),
            },
            "worst": {
                "date": worst.get("prediction_date"),
                "correct": worst.get("regime_correct"),
                "change": worst.get("actual_nifty_change"),
            },
            "trend": trend,
        }

    except Exception as e:
        print(f"⚠️ get_weekly_accuracy: {e}")
        return {"ok": False, "error": str(e)}


def format_weekly_accuracy() -> str:
    """Format weekly accuracy report for Telegram."""
    stats = get_weekly_accuracy(days=7)

    if not stats.get("ok"):
        return ""

    lines = ["📊 WEEKLY ACCURACY REPORT"]
    lines.append("━" * 25)
    lines.append(f"Regime Predictions: {stats['correct']}/{stats['total']} correct ({stats['hit_rate']}%)")
    lines.append(f"Brier Score: {stats['avg_brier']:.4f} ({'good' if stats['avg_brier'] < 0.25 else 'needs improvement'} — random=0.25)")

    best = stats.get("best", {})
    worst = stats.get("worst", {})

    if best.get("date"):
        emoji = "✅" if best.get("correct") else "❌"
        lines.append(f"Best: {best['date']} {emoji} (Nifty {best.get('change', 0):+.2f}%)")

    if worst.get("date"):
        emoji = "✅" if worst.get("correct") else "❌"
        lines.append(f"Worst: {worst['date']} {emoji} (Nifty {worst.get('change', 0):+.2f}%)")

    lines.append(f"Trend: {stats['trend']}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# SIGNAL ACCURACY TRACKING — Dynamic Weight Adjustment
# Track which signals are actually predictive. Adjust bull/bear weights by hit rate.
# ═══════════════════════════════════════════════════════════════════════════════

def record_signals_that_fired(fii_context: Dict, macro_context: Dict,
                                extra_signals: Dict = None, actual_direction: str = None,
                                nifty_return: float = None) -> bool:
    """
    Record which signals fired today and whether they were correct.
    Called AFTER we know the actual market outcome.

    Tracks these signal types:
      - fii_streak_bearish: FII selling streak >= 3 days
      - fii_streak_bullish: FII buying streak >= 3 days
      - fii_extreme_selling: FII z-score < -1.5
      - fii_extreme_buying: FII z-score > 1.5
      - vix_high: VIX > 20 (regime HIGH)
      - vix_low: VIX < 15 (regime LOW)
      - dxy_rising: DXY direction RISING
      - dxy_falling: DXY direction FALLING
      - dii_absorbing: DII absorption High
      - pcr_contrarian_bull: PCR < 0.7
      - pcr_bearish: PCR > 1.3
      - breadth_weak: A/D ratio < 0.7
      - breadth_strong: A/D ratio > 1.5
      - carry_stress: Carry trade STRESSED
      - carry_on: Carry trade ON
      - stagflation: Stagflation risk
      - triple_threat_bear: FII sell + streak + HIGH VIX
    """
    from src.db import log_signal_accuracy, today_str

    if actual_direction is None:
        return False

    date_str = today_str()
    signals_fired = []

    # FII signals
    fii_z = fii_context.get("fii_z_score", 0)
    fii_streak = fii_context.get("fii_streak", 0)
    fii_dir = fii_context.get("fii_streak_direction", "")

    if fii_streak >= 3 and fii_dir == "negative":
        signals_fired.append(("fii_streak_bearish", fii_streak))
    if fii_streak >= 3 and fii_dir == "positive":
        signals_fired.append(("fii_streak_bullish", fii_streak))
    if fii_z < -1.5:
        signals_fired.append(("fii_extreme_selling", fii_z))
    if fii_z > 1.5:
        signals_fired.append(("fii_extreme_buying", fii_z))

    # VIX signals
    vix_regime = macro_context.get("vix_regime", "UNKNOWN")
    if vix_regime == "HIGH":
        signals_fired.append(("vix_high", macro_context.get("vix_price", 0)))
    if vix_regime == "LOW":
        signals_fired.append(("vix_low", macro_context.get("vix_price", 0)))

    # DXY signals
    dxy_dir = macro_context.get("dxy", {}).get("direction", "FLAT")
    if dxy_dir == "RISING":
        signals_fired.append(("dxy_rising", macro_context.get("dxy", {}).get("change_pct", 0)))
    if dxy_dir == "FALLING":
        signals_fired.append(("dxy_falling", macro_context.get("dxy", {}).get("change_pct", 0)))

    # DII absorption
    if fii_context.get("dii_absorbed", 0) >= 0.8:
        signals_fired.append(("dii_absorbing", 1))

    # PCR signals
    extra = extra_signals or {}
    pcr = extra.get("pcr")
    if pcr is not None:
        if pcr < 0.7:
            signals_fired.append(("pcr_contrarian_bull", pcr))
        if pcr > 1.3:
            signals_fired.append(("pcr_bearish", pcr))

    # Breadth signals
    breadth = extra.get("breadth_ratio")
    if breadth is not None:
        if breadth < 0.7:
            signals_fired.append(("breadth_weak", breadth))
        if breadth > 1.5:
            signals_fired.append(("breadth_strong", breadth))

    # Carry trade
    carry = extra.get("carry_trade_regime", "")
    if carry == "CARRY-STRESS":
        signals_fired.append(("carry_stress", 1))
    if carry == "CARRY-ON":
        signals_fired.append(("carry_on", 1))

    # Stagflation
    stag = extra.get("stagflation_regime", "")
    if "STAGFLATION" in stag:
        signals_fired.append(("stagflation", 1))

    # Triple threat (rare but critical)
    if fii_z < -1.5 and fii_streak >= 3 and vix_regime == "HIGH":
        signals_fired.append(("triple_threat_bear", fii_z))

    # Log each signal
    recorded = 0
    for signal_name, signal_value in signals_fired:
        # Predicted direction for this signal type
        bearish_signals = {
            "fii_streak_bearish", "fii_extreme_selling", "vix_high",
            "dxy_rising", "pcr_bearish", "breadth_weak", "carry_stress",
            "stagflation", "triple_threat_bear"
        }
        predicted = "DOWN" if signal_name in bearish_signals else "UP"

        # Check if prediction was correct
        hit = (predicted == actual_direction) if actual_direction in ("UP", "DOWN") else None

        if hit is not None:
            log_signal_accuracy(
                date_str=date_str,
                signal_name=signal_name,
                signal_value=signal_value,
                predicted_direction=predicted,
                actual_direction=actual_direction,
                hit=hit,
                nifty_return=nifty_return,
            )
            recorded += 1

    if recorded > 0:
        print(f"📊 Recorded {recorded} signal accuracy logs for {date_str}")

    return recorded > 0


def get_dynamic_signal_weights(days: int = 90) -> Dict:
    """
    Compute dynamic signal weights based on historical hit rates.
    Signals with hit rate > 65% get weight × 1.3 (amplified)
    Signals with hit rate < 45% get weight × 0.7 (penalized)
    Signals with insufficient data (< 10 occurrences) get weight × 1.0

    Dampening: weight changes limited to ±10% per week to prevent oscillation.
    Returns: {signal_name: {"weight_multiplier": float, "hit_rate": float, "occurrences": int}}
    """
    from src.db import get_signal_accuracy, get_bot_state, set_bot_state
    import json

    accuracy = get_signal_accuracy(days=days)
    if not accuracy:
        return {}

    # Load previous weights for dampening
    prev_weights_raw = get_bot_state("signal_weights")
    prev_weights = {}
    if prev_weights_raw:
        try:
            prev_weights = json.loads(prev_weights_raw)
        except Exception:
            pass

    weights = {}
    for signal_name, stats in accuracy.items():
        hit_rate = stats["hit_rate"]
        total = stats["total"]

        if total < 10:
            multiplier = 1.0
        elif hit_rate > 65:
            multiplier = 1.3
        elif hit_rate < 45:
            multiplier = 0.7
        else:
            multiplier = 1.0

        # Dampening: limit ±10% change from previous weight
        prev = prev_weights.get(signal_name, 1.0)
        max_change = 0.10
        if multiplier > prev + max_change:
            multiplier = prev + max_change
        elif multiplier < prev - max_change:
            multiplier = prev - max_change

        weights[signal_name] = {
            "weight_multiplier": round(multiplier, 2),
            "hit_rate": hit_rate,
            "occurrences": total,
            "hits": stats["hits"],
            "misses": stats["misses"],
        }

    # Save current weights for next week's dampening
    weights_to_save = {k: v["weight_multiplier"] for k, v in weights.items()}
    set_bot_state("signal_weights", json.dumps(weights_to_save))

    return weights


def format_signal_weights(weights: Dict) -> str:
    """Format signal weights for AI prompt."""
    if not weights:
        return ""

    lines = ["[Signal Accuracy & Dynamic Weights]"]
    for name, data in sorted(weights.items(), key=lambda x: abs(x[1]["weight_multiplier"] - 1), reverse=True):
        mult = data["weight_multiplier"]
        rate = data["hit_rate"]
        occ = data["occurrences"]

        if mult > 1:
            icon = "🟢"
            adj = f"AMPLIFIED ×{mult:.1f}"
        elif mult < 1:
            icon = "🔴"
            adj = f"PENALIZED ×{mult:.1f}"
        else:
            icon = "⚪"
            adj = "neutral"

        lines.append(f"  {icon} {name}: {rate}% hit rate ({occ} occ) → {adj}")

    return "\n".join(lines)
