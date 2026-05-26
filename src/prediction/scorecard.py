"""
Scorecard — Brier scoring for AI forecasts.

Grades yesterday's forecast against actual NIFTY close.
Brier score = mean((forecast_prob - actual_outcome)²)
  - 0.0 = perfect prediction
  - 0.25 = random (50/50)
  - 1.0 = perfectly wrong

Stores results to Supabase for dynamic signal reweighting.

Usage:
    from src.prediction.scorecard import grade_yesterday, get_signal_penalties
    grade_yesterday()  # scores and stores
    penalties = get_signal_penalties()  # {"signal_name": penalty_multiplier}
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from src.state import Forecast


def compute_brier_score(probability_up: float, actual_outcome: bool) -> float:
    """
    Compute single-event Brier score.
    probability_up: 0.1-0.9 (forecast probability of UP)
    actual_outcome: True if NIFTY went up, False otherwise
    Returns: 0.0 (perfect) to 1.0 (perfectly wrong)
    """
    outcome = 1.0 if actual_outcome else 0.0
    return (probability_up - outcome) ** 2


def grade_forecast(forecast: Forecast, nifty_return_1d: float) -> Dict:
    """
    Grade a single forecast against actual return.
    Returns scoring result dict.
    """
    actual_up = nifty_return_1d > 0
    brier = compute_brier_score(forecast.probability_up, actual_up)

    # Determine if forecast was directionally correct
    direction_correct = False
    if forecast.direction == "BULLISH" and actual_up:
        direction_correct = True
    elif forecast.direction == "BEARISH" and not actual_up:
        direction_correct = True
    elif forecast.direction == "NEUTRAL":
        direction_correct = True  # Neutral is never "wrong"

    # Label
    if brier < 0.1:
        label = "EXCELLENT"
    elif brier < 0.25:
        label = "GOOD"
    elif brier < 0.5:
        label = "POOR"
    else:
        label = "TERRIBLE"

    return {
        "brier_score": round(brier, 4),
        "direction_correct": direction_correct,
        "actual_return": round(nifty_return_1d, 2),
        "actual_up": actual_up,
        "forecast_direction": forecast.direction,
        "forecast_prob": forecast.probability_up,
        "forecast_confidence": forecast.confidence,
        "label": label,
        "primary_signals": forecast.primary_signals,
    }


def grade_yesterday() -> Optional[Dict]:
    """
    Fetch yesterday's forecast from Supabase, grade against actual NIFTY return.
    Returns scoring result or None if no forecast found.
    """
    from src.db import get_client

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    try:
        client = get_client()
        if client is None:
            print("  ⚠️  Scorecard: Supabase not available")
            return None

        # Fetch yesterday's forecast
        result = client.table("daily_predictions").select("*").eq("date", yesterday).limit(1).execute()
        if not result.data:
            print(f"  ⚠️  Scorecard: No forecast found for {yesterday}")
            return None

        pred = result.data[0]

        # Get actual NIFTY close for yesterday and day before
        snap_result = client.table("daily_market_snapshot").select("nifty_close", "date").eq("date", yesterday).order("date", desc=True).limit(2).execute()
        if not snap_result.data or len(snap_result.data) < 2:
            print(f"  ⚠️  Scorecard: Insufficient NIFTY data for {yesterday}")
            return None

        closes = [r.get("nifty_close") for r in snap_result.data if r.get("nifty_close") is not None]
        if len(closes) < 2:
            return None

        nifty_return = ((closes[-1] / closes[-2]) - 1) * 100

        # Reconstruct Forecast object
        forecast_data = pred.get("prediction", {})
        if isinstance(forecast_data, str):
            try:
                forecast_data = json.loads(forecast_data)
            except json.JSONDecodeError:
                return None

        forecast = Forecast(
            direction=forecast_data.get("direction", "NEUTRAL"),
            probability_up=forecast_data.get("probability_up", 0.5),
            confidence=forecast_data.get("confidence", 50),
            primary_signals=forecast_data.get("primary_signals", []),
        )

        # Grade
        score = grade_forecast(forecast, nifty_return)

        # Store outcome
        outcome_data = {
            "date": yesterday,
            "brier_score": score["brier_score"],
            "direction_correct": score["direction_correct"],
            "actual_return": score["actual_return"],
            "label": score["label"],
            "forecast_id": pred.get("id"),
        }

        try:
            client.table("prediction_outcomes").insert(outcome_data).execute()
            print(f"  ✅ Scorecard: {score['label']} — Brier {score['brier_score']:.3f} (forecast: {forecast.direction}, actual: {score['actual_return']:+.2f}%)")
        except Exception as e:
            print(f"  ⚠️  Scorecard: Failed to store outcome: {e}")

        return score

    except Exception as e:
        print(f"  ⚠️  Scorecard error: {e}")
        return None


def get_signal_penalties(days: int = 90) -> Dict[str, float]:
    """
    Get penalty multipliers for signals based on recent Brier performance.
    If a signal appears in forecasts with avg Brier > 0.25, penalize it.
    If avg Brier < 0.15, boost it.

    Returns: {"signal_name": multiplier} where multiplier < 1.0 = penalty, > 1.0 = boost
    """
    from src.db import get_client

    try:
        client = get_client()
        if client is None:
            return {}

        # Fetch recent outcomes with associated predictions
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        outcome_result = client.table("prediction_outcomes").select("*").gte("date", cutoff).execute()

        if not outcome_result.data:
            return {}

        # Aggregate by signal
        signal_scores: Dict[str, List[float]] = {}
        for outcome in outcome_result.data:
            brier = outcome.get("brier_score")
            if brier is None:
                continue

            # Get the associated forecast's signals
            # Signals are stored in daily_predictions, linked by forecast_id
            forecast_id = outcome.get("forecast_id")
            if forecast_id is None:
                continue

            pred_result = client.table("daily_predictions").select("*").eq("id", forecast_id).limit(1).execute()
            if not pred_result.data:
                continue

            pred = pred_result.data[0]
            pred_data = pred.get("prediction", {})
            if isinstance(pred_data, str):
                try:
                    pred_data = json.loads(pred_data)
                except json.JSONDecodeError:
                    continue

            signals = pred_data.get("primary_signals", [])
            for signal in signals:
                signal_scores.setdefault(signal, []).append(brier)

        # Compute penalties
        penalties = {}
        for signal, scores in signal_scores.items():
            avg_brier = sum(scores) / len(scores)
            if avg_brier > 0.25:
                # Poor signal — penalize
                penalties[signal] = round(max(0.5, 1.0 - (avg_brier - 0.25)), 2)
            elif avg_brier < 0.15:
                # Good signal — boost
                penalties[signal] = round(min(1.3, 1.0 + (0.15 - avg_brier)), 2)
            else:
                penalties[signal] = 1.0

        return penalties

    except Exception as e:
        print(f"  ⚠️  Signal penalties error: {e}")
        return {}
