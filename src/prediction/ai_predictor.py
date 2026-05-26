"""
AI Predictor — Structured JSON Forecast from MarketState.

Takes a populated MarketState, assembles a feature-rich prompt,
forces JSON output with direction, probability_up, confidence, signals.
Output is machine-readable and Brier-scoreable.

Usage:
    from src.prediction.ai_predictor import generate_forecast
    forecast = generate_forecast(state)
    state.forecast = forecast
"""
from __future__ import annotations

import json
from typing import Dict, Optional

from src.state import MarketState, Forecast


def _assemble_prompt(state: MarketState) -> str:
    """Build the AI forecast prompt from MarketState fields."""
    lines = [
        "You are a quantitative market analyst forecasting NIFTY 50 direction for the next trading day.",
        "",
        "=== CURRENT MARKET STATE ===",
        f"Date: {state.trade_date}",
        "",
        "--- Macro ---",
    ]

    m = state.macro
    if m.vix is not None:
        lines.append(f"India VIX: {m.vix} (regime: {m.vix_regime or 'N/A'})")
    if m.usdinr is not None:
        lines.append(f"USD/INR: {m.usdinr}")
    if m.brent is not None:
        lines.append(f"Brent Crude: ${m.brent:.2f}")
    if m.gold is not None:
        lines.append(f"Gold: ${m.gold:.2f}")
    if m.dxy is not None:
        lines.append(f"DXY: {m.dxy} (signal: {m.dxy_signal or 'N/A'})")
    if m.us_10y is not None:
        lines.append(f"US 10Y Yield: {m.us_10y}%")
    if m.cboe_vix is not None:
        lines.append(f"CBOE VIX: {m.cboe_vix}")
    if m.hyg is not None:
        lines.append(f"High Yield ETF (HYG): ${m.hyg:.2f}")

    lines.append("")
    lines.append("--- Flows ---")
    f = state.flows
    if f.fii_net is not None:
        lines.append(f"FII Net: {f.fii_net:+.0f} INR cr (streak: {f.fii_streak_days}d)")
    if f.dii_net is not None:
        lines.append(f"DII Net: {f.dii_net:+.0f} INR cr")
    if f.absorption_ratio is not None:
        lines.append(f"DII Absorption Ratio: {f.absorption_ratio:.2f}")

    lines.append("")
    lines.append("--- Derivatives ---")
    d = state.derivatives
    if d.pcr is not None:
        lines.append(f"PCR: {d.pcr:.2f} (signal: {d.pcr_signal or 'N/A'})")
    if d.max_pain is not None:
        lines.append(f"Max Pain: {d.max_pain}")
    if d.spot_price is not None:
        lines.append(f"Spot: {d.spot_price}")
    if d.gex is not None:
        lines.append(f"Net GEX: {d.gex:.0f}")

    lines.append("")
    lines.append("--- Market Context ---")
    if state.bull_bear_score is not None:
        lines.append(f"Bull/Bear Score: {state.bull_bear_score:+.1f}")
    if state.bull_bear_normalized is not None:
        lines.append(f"Bull/Bear Normalized: {state.bull_bear_normalized:.0f}/100")
    if state.market_phase:
        lines.append(f"Market Phase: {state.market_phase}")
    if state.cross_asset_regime:
        lines.append(f"Cross-Asset Regime: {state.cross_asset_regime}")
    if state.dominant_factor:
        lines.append(f"Dominant Factor: {state.dominant_factor}")

    if state.features.breadth_score is not None:
        lines.append(f"Breadth Score: {state.features.breadth_score:+.3f}")

    lines.append("")
    lines.append("--- Narratives ---")
    for key, text in state.narratives.items():
        if text:
            lines.append(f"{key}: {text[:200]}")

    lines.append("")
    lines.append("--- Missing Data ---")
    if state.missing_sources:
        for src in state.missing_sources:
            lines.append(f"  MISSING: {src}")
    else:
        lines.append("  All data sources healthy")

    lines.append("")
    lines.append("=== INSTRUCTIONS ===")
    lines.append("Based on the data above, produce a structured forecast for NIFTY 50.")
    lines.append("Rules:")
    lines.append("  - direction: BULLISH / BEARISH / NEUTRAL (pick ONE)")
    lines.append("  - probability_up: float between 0.1 and 0.9 (NO 0.0, 0.5, or 1.0)")
    lines.append("  - confidence: 0-100 integer")
    lines.append("  - primary_signals: 2-4 signals from the data that drove your forecast")
    lines.append("  - contradiction_warnings: 0-2 contradictions or risks in the data")
    lines.append("  - If data is sparse or contradictory, lower confidence accordingly")
    lines.append("")
    lines.append("Respond ONLY with valid JSON in this exact format:")
    lines.append('{')
    lines.append('  "direction": "BULLISH",')
    lines.append('  "probability_up": 0.62,')
    lines.append('  "confidence": 55,')
    lines.append('  "target_horizon": "1D",')
    lines.append('  "primary_signals": ["signal1", "signal2"],')
    lines.append('  "contradiction_warnings": ["warning1"]')
    lines.append('}')

    return "\n".join(lines)


def generate_forecast(state: MarketState) -> Optional[Forecast]:
    """
    Generate a structured AI forecast from MarketState.
    Returns Forecast object or None if generation fails.
    """
    from src.ai_engine import AIEngine

    prompt = _assemble_prompt(state)

    try:
        ai = AIEngine()
        response = ai.analyze("fast", prompt)

        # Parse JSON from AI response
        text = response.strip()

        # Remove code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            json_lines = []
            in_json = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_json = not in_json
                    continue
                if in_json:
                    json_lines.append(line)
            text = "\n".join(json_lines)

        # Strip any leading non-JSON characters (emojis, etc.)
        first_brace = text.find("{")
        if first_brace < 0:
            raise ValueError("No JSON object found in AI response")
        text = text[first_brace:]

        # Extract just the top-level JSON object (handle trailing content)
        # Find matching closing brace
        depth = 0
        in_string = False
        escape_next = False
        end_idx = len(text)
        for i, ch in enumerate(text):
            if escape_next:
                escape_next = False
                continue
            if ch == '\\' and in_string:
                escape_next = True
                continue
            if ch == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end_idx = i + 1
                    break

        text = text[:end_idx]

        data = json.loads(text)

        # Validate and clamp
        direction = data.get("direction", "NEUTRAL").upper()
        if direction not in ("BULLISH", "BEARISH", "NEUTRAL"):
            direction = "NEUTRAL"

        prob_up = data.get("probability_up", 0.5)
        prob_up = max(0.1, min(0.9, float(prob_up)))

        confidence = data.get("confidence", 50)
        confidence = max(0, min(100, int(confidence)))

        forecast = Forecast(
            direction=direction,
            probability_up=prob_up,
            confidence=confidence,
            target_horizon=data.get("target_horizon", "1D"),
            primary_signals=data.get("primary_signals", [])[:4],
            contradiction_warnings=data.get("contradiction_warnings", [])[:2],
        )

        return forecast

    except Exception as e:
        print(f"  ⚠️  Forecast generation failed: {e}")
        return None
