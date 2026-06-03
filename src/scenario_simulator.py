"""
scenario_simulator.py — P9.1 /simulate command
Overrides a single macro variable, then runs the deterministic pipeline:
  consequence_engine → pillar_classifier → fragility_index → regime_arbiter

No API calls. Pure algebra on current day's market_state.
"""
from typing import Dict, Optional, List


OVERRIDEABLE_VARS = {
    "brent": "BZ=F",
    "wti": "CL=F",
    "usdinr": "USDINR=X",
    "dxy": "DX-Y.NYB",
    "gold": "GC=F",
    "india_vix": "^INDIAVIX",
    "us_10y": "^TNX",
    "cboe_vix": "^VIX",
    "copper": "HG=F",
    "hyg": "HYG",
}


def run_simulation(variable: str, value: float) -> Dict:
    """Run full deterministic pipeline with one variable overridden.

    Steps:
      1. Fetch current day's market_state from Supabase
      2. Build temporary macro_attrs dict with variable overridden
      3. Run consequence_engine with the new value
      4. Run pillar_classifier with overridden macro data
      5. Run fragility_index
      6. Run regime_arbiter
      7. Return result dict with all intermediate values
    """
    try:
        from datetime import datetime
        from src.db import get_market_state

        today = datetime.now().strftime("%Y-%m-%d")
        state = get_market_state(today)
        if not state:
            return {"ok": False, "error": "No market_state for today"}

        macro = state.get("macro", {})
        if not macro:
            return {"ok": False, "error": "No macro data in market_state"}

        # Build macro_attrs from current state
        macro_attrs = _build_macro_attrs(macro)

        # Override the variable
        symbol = OVERRIDEABLE_VARS.get(variable)
        if symbol:
            macro_attrs[symbol] = value
        else:
            macro_attrs[variable.replace("-", "_")] = value

        # Step 1: Consequence Engine
        consequences = _run_consequences(macro_attrs, variable, value)

        # Step 2: Pillar Classifier
        from src.pillar_classifier import classify_pillars
        pillar_scores = classify_pillars(macro_attrs)

        # Step 3: Fragility Index
        from src.fragility_index import compute_fragility
        fragility_result = compute_fragility(macro_attrs, pillar_scores)
        fragility_score = fragility_result.get("fragility_score", 50)

        # Step 4: Regime Arbiter
        from src.regime_arbiter import arbitrate_regime
        regime = arbitrate_regime(
            macro_attrs=macro_attrs,
            pillar_scores=pillar_scores,
            fragility_score=fragility_score,
            override_regime=None,
        )

        return {
            "ok": True,
            "variable": variable,
            "override_value": value,
            "pillar_scores": pillar_scores,
            "fragility_score": fragility_score,
            "regime": regime,
            "consequences": consequences,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _build_macro_attrs(macro: Dict) -> Dict:
    """Convert market_state macro dict to flat attrs dict with symbol keys."""
    attrs = {}
    for key, val in macro.items():
        if isinstance(val, dict):
            price = val.get("price")
            if price is not None:
                attrs[key] = price
        elif val is not None:
            attrs[key] = val
    return attrs


def _run_consequences(macro_attrs: Dict, variable: str, value: float) -> List[str]:
    """Run consequence engine and return impact lines."""
    try:
        from src.consequence_engine import compute_consequence
        result = compute_consequence(variable, value, change_value=value)
        if result:
            return result.get("lines", [])
    except Exception:
        pass
    return []


def format_simulation(result: Dict) -> str:
    """Format simulation result for Telegram."""
    if not result.get("ok"):
        return f"⚠️ Simulation failed: {result.get('error', 'unknown')}"

    var = result.get("variable", "?")
    val = result.get("override_value", 0)
    regime = result.get("regime", "UNKNOWN")
    fragility = result.get("fragility_score", 0)
    pillars = result.get("pillar_scores", {})

    msg = (
        f"🔮 *Scenario: {var} = {val}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Regime: *{regime}*\n"
        f"Fragility: *{fragility:.1f}* / 100\n\n"
    )

    if pillars:
        msg += "*Pillar Scores:*\n"
        active = {k: v for k, v in pillars.items() if isinstance(v, (int, float)) and v >= 30}
        if active:
            for k, v in sorted(active.items(), key=lambda x: x[1], reverse=True):
                label = k.replace("_", " ").title()
                msg += f"  • {label}: {v:.0f}/100\n"

    lines = result.get("consequences", [])
    if lines:
        msg += f"\n*Impact:*\n"
        for line in lines[:5]:
            msg += f"  {line}\n"

    msg += f"\n_Deterministic simulation — no AI_"
    return msg
