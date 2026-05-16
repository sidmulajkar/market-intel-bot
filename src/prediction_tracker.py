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

    # REGIME: Risk-on / Risk-off / Neutral / Transition
    regime_match = re.search(
        r"REGIME[:\s]+(Risk-on|Risk-off|Neutral|Transition)",
        raw_text, re.IGNORECASE
    )
    if regime_match:
        result["regime"] = regime_match.group(1).strip()

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

        # Check regime accuracy
        pred_regime = prediction.get("regime", "")
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
