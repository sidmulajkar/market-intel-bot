"""
Regime Arbiter — Single Source of Truth for Market Regime

Consumes MarketState and returns a unified regime verdict.
All formatters read from this arbiter; none recompute regime independently.

Hierarchy:
  1. Deterministic override (macro extremes) → strongest
  2. Statistical composite (bull_bear) → fallback
  3. Posture alignment (THEREFORE clause) → attached to verdict

Usage:
    from src.regime_arbiter import arbitrate_regime
    verdict = arbitrate_regime(state)
    # verdict.regime, verdict.confidence, verdict.dominant_driver, verdict.narrative
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from src.posture_engine import compute_posture, PostureResult


def _fmt_rupee_local(value: float) -> str:
    """Format rupee value with sign after ₹ symbol: ₹-655Cr (Bloomberg-standard)."""
    sign = "-" if value < 0 else "+"
    return f"₹{sign}{abs(value):,.0f}Cr"


# ── No hard-coded price thresholds ──────────────────────────────────
# Phase 4.3: All price-based overrides (USDINR > 94.5, Brent > 90)
# removed. Override paths are:
#   Layer 1b: Global Arbiter (STAGFLATION/LIQUIDITY_DRAWDOWN)
#   Layer 2:  Fragility Index (>65 cap NEUTRAL, >85 force DEFENSIVE)


@dataclass
class RegimeVerdict:
    regime: str              # "BULLISH", "BEARISH", "NEUTRAL", "DEFENSIVE"
    confidence: str          # "HIGH", "MEDIUM", "LOW"
    dominant_driver: str     # e.g., "USDINR ₹95.7 + Brent $93"
    narrative: str           # 1-sentence WHY
    override_reason: str     # "" if no override, else reason code
    posture: Optional[PostureResult] = None  # action posture


def _safe(val, default=0.0) -> float:
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def _build_override_narrative(drivers, usdinr, brent, vix, fii_net) -> str:
    """Build user-facing causal narrative — no system internals."""
    parts = []
    for d in drivers:
        if "Global:" in d:
            parts.append(d.replace("Global: ", ""))
        elif "Fragility" in d:
            parts.append(f"Structural fragility ({d})")
        elif "USDINR" in d:
            parts.append(f"Historic INR weakness (₹{usdinr:.1f})")
        elif "Brent" in d:
            parts.append(f"Brent stress (${brent:.0f})")
        elif "VIX" in d:
            parts.append(f"Volatility spike (VIX {vix:.0f})")
        elif "FII" in d:
            parts.append(f"FII heavy selling ({_fmt_rupee_local(fii_net)})")
        elif "variables stressed" in d:
            parts.append(f"Multi-variable stress detected")
        elif "Stress Index" in d:
            parts.append(f"Sustained broad market stress")
    if parts:
        return " + ".join(parts[:3]) + "."
    return "Macro extremes detected."


def arbitrate_regime(state, flow_metrics: Optional[Dict] = None) -> RegimeVerdict:
    """Single arbiter that determines regime from MarketState.

    Must be called AFTER macro/flows/derivatives are populated.
    Returns RegimeVerdict with regime, confidence, dominant_driver, narrative.
    """
    m = getattr(state, "macro", None)
    f = getattr(state, "flows", None)
    d = getattr(state, "derivatives", None)

    vix = _safe(getattr(m, "vix", None) if m else None)
    usdinr = _safe(getattr(m, "usdinr", None) if m else None)
    brent = _safe(getattr(m, "brent", None) if m else None)
    fii_net = _safe(getattr(f, "fii_net", None) if f else None)
    fii_streak = getattr(f, "fii_streak_days", 0) if f else 0
    dii_net = _safe(getattr(f, "dii_net", None) if f else None)
    pcr = _safe(getattr(d, "pcr", None) if d else None)
    breadth = _safe(getattr(getattr(state, "features", None), "breadth_score", None))
    gold = _safe(getattr(m, "gold", None) if m else None)
    bb_norm = getattr(state, "bull_bear_normalized", None)
    market_phase = getattr(state, "market_phase", None)

    # ── Layer 1: Deterministic override ───────────────────────────
    override_regime = None
    override_confidence = None
    override_reason = ""
    drivers = []

    # ── Layer 1b: Global Regime Override (hard kill switch) ─────────
    # Must run first — if global regime is STAGFLATION or LIQUIDITY_DRAWDOWN,
    # local arbiter must obey regardless of local fragility.
    global_regime = None
    try:
        if getattr(state, "macro", None) and hasattr(state, "macro"):
            m = state.macro
            macro_list = []
            if getattr(m, "usdinr", None) is not None:
                macro_list.append({"name": "USD/INR", "ok": True, "price": m.usdinr, "change_pct": 0})
            if getattr(m, "dxy", None) is not None:
                macro_list.append({"name": "Dollar Index", "ok": True, "price": m.dxy, "change_pct": 0})
            if getattr(m, "vix", None) is not None:
                macro_list.append({"name": "CBOE VIX", "ok": True, "price": m.vix, "change_pct": 0})
            if getattr(m, "brent", None) is not None:
                macro_list.append({"name": "Brent Crude", "ok": True, "price": m.brent, "change_pct": 0})
            if getattr(m, "gold", None) is not None:
                macro_list.append({"name": "Gold", "ok": True, "price": m.gold, "change_pct": 0})
            if getattr(m, "copper", None) is not None:
                macro_list.append({"name": "Copper", "ok": True, "price": m.copper, "change_pct": 0})
            if getattr(m, "us_10y", None) is not None:
                macro_list.append({"name": "US 10Y Yield", "ok": True, "price": m.us_10y, "change_pct": 0})
            if getattr(m, "usd_jpy", None) is not None:
                macro_list.append({"name": "USD/JPY", "ok": True, "price": m.usd_jpy, "change_pct": 0})
            if getattr(m, "hyg", None) is not None:
                macro_list.append({"name": "US High Yield", "ok": True, "price": m.hyg, "change_pct": 0})
            if getattr(m, "lqd", None) is not None:
                macro_list.append({"name": "IG Corp Bonds", "ok": True, "price": m.lqd, "change_pct": 0})
            if getattr(m, "es", None) is not None:
                macro_list.append({"name": "S&P 500 Futures", "ok": True, "price": m.es, "change_pct": 0})
            if getattr(m, "nq", None) is not None:
                macro_list.append({"name": "Nasdaq Futures", "ok": True, "price": m.nq, "change_pct": 0})

            if macro_list:
                from src.global_arbiter import compute_global_regime
                global_regime = compute_global_regime(macro_list)
                gr = global_regime.get("regime", "GLOBAL_NEUTRAL")
                state.global_regime = gr
                if gr in ("GLOBAL_STAGFLATION", "GLOBAL_LIQUIDITY_DRAWDOWN"):
                    override_regime = "DEFENSIVE"
                    override_confidence = "HIGH"
                    override_reason = "global_" + gr.lower()
                    drivers.append(f"Global: {global_regime['label']}")
    except Exception as e:
        print(f"   ⚠️ Global arbiter: {e}")

    # ── Layer 1.6: Fragility Index Override (P4.3) ───────────────
    # Mathematical bridge: Pillars → Fragility → Regime → Narrative.
    # > 85 force DEFENSIVE, > 65 cap BULLISH to NEUTRAL (applied post-statistical).
    # Replaces old hard-coded USDINR/Brent price thresholds.
    if not override_regime:
        fragility_score = getattr(state, "fragility_score", None)
        if fragility_score is None:
            try:
                from src.pillar_classifier import get_percentiles_from_csv, classify_pillars
                from src.fragility_index import compute_fragility_index
                from src.stress_index import compute_stress_index
                pctiles = get_percentiles_from_csv()
                if pctiles:
                    pillars = classify_pillars(pctiles)
                    stress = compute_stress_index()
                    stress_score = stress.get("stress_score", 50.0) if stress.get("ok") else 50.0
                    frag = compute_fragility_index(stress_score, pillars)
                    if frag.get("ok"):
                        fragility_score = frag["fragility_score"]
                        state.fragility_score = fragility_score
            except Exception:
                pass
        if fragility_score is not None and isinstance(fragility_score, (int, float)):
            if fragility_score > 85:
                override_regime = "DEFENSIVE"
                override_confidence = "HIGH"
                override_reason = "fragility_index"
                drivers.append(f"Fragility Index {fragility_score:.0f}/100")

    # ── Build verdict ─────────────────────────────────────────────
    if override_regime:
        regime = override_regime
        confidence = override_confidence
        dominant_driver = " + ".join(drivers[:3])
        narrative = _build_override_narrative(drivers, usdinr, brent, vix, fii_net)
    else:
        # ── Layer 2: Statistical composite ────────────────────────
        regime = _regime_from_bull_bear(bb_norm, market_phase)
        data_count = _count_signals(state)
        confidence = "HIGH" if data_count >= 5 else "MEDIUM" if data_count >= 3 else "LOW"
        dominant_driver = _dominant_driver_from_bb(state)
        narrative = _narrative_from_bb(bb_norm, market_phase, data_count)

        # Global RISK_OFF cap: ban BULL, cap at NEUTRAL
        if global_regime and global_regime.get("regime") == "GLOBAL_RISK_OFF":
            if regime == "BULLISH":
                regime = "NEUTRAL"
                narrative += " (capped at NEUTRAL — global risk-off)"
                if "Global" not in dominant_driver:
                    dominant_driver = "Global risk-off overlay"
            narrative += " Global risk-off overlay active."

        # Fragility > 65 cap: ban BULL, cap at NEUTRAL
        fragility_score = getattr(state, "fragility_score", None)
        if fragility_score is not None and isinstance(fragility_score, (int, float)) and fragility_score > 65:
            if regime == "BULLISH":
                regime = "NEUTRAL"
                narrative += f" (capped at NEUTRAL — Fragility {fragility_score:.0f}/100)"
                if "Fragility" not in dominant_driver:
                    dominant_driver = f"Fragility {fragility_score:.0f}/100"

    # ── Layer 3: Scenario detection (multi-variable patterns) ─────
    try:
        from src.scenario_engine import ScenarioDetector
        detector = ScenarioDetector(state, flow_metrics=flow_metrics)
        scenarios = detector.detect()
        if scenarios:
            state.active_scenarios = scenarios
            names = [s.name for s in scenarios]
            print(f"🔍 Scenarios detected: {', '.join(names)}")
            # Persist to history
            try:
                from src.db import merge_scenario_history
                trade_date = getattr(state, "trade_date", None)
                if trade_date:
                    merge_scenario_history(trade_date, [s.model_dump() for s in scenarios])
            except Exception:
                pass  # Non-blocking — persistence is advisory
    except Exception:
        pass  # Non-blocking — scenarios are advisory

    # ── Layer 4: Posture alignment (THEREFORE) ────────────────────
    posture = compute_posture(
        vix=vix if vix > 0 else None,
        usdinr=usdinr if usdinr > 0 else None,
        brent=brent if brent > 0 else None,
        dxy=None,
        dxy_signal=None,
        fii_net=fii_net if fii_net != 0 else None,
        fii_streak=fii_streak if fii_streak != 0 else None,
        dii_net=dii_net if dii_net != 0 else None,
        pcr=pcr if pcr > 0 else None,
        breadth_score=breadth if breadth is not None else None,
        gold=gold if gold > 0 else None,
        market_phase=market_phase,
        bull_bear_normalized=bb_norm,
        forced_regime=regime,  # align posture with arbitrated regime
    )

    # Align posture confidence with verdict confidence (single source of truth)
    if posture and posture.confidence != confidence:
        from dataclasses import replace
        posture = replace(posture, confidence=confidence)

    return RegimeVerdict(
        regime=regime,
        confidence=confidence,
        dominant_driver=dominant_driver,
        narrative=narrative,
        override_reason=override_reason,
        posture=posture,
    )


def _regime_from_bull_bear(bb_norm: Optional[float], market_phase: Optional[str]) -> str:
    """Map statistical composite to regime label."""
    if market_phase:
        phase_map = {
            "ACCUMULATION": "BULLISH",
            "MARKUP": "BULLISH",
            "DISTRIBUTION": "BEARISH",
            "DECLINE": "BEARISH",
        }
        return phase_map.get(market_phase, "NEUTRAL")

    if bb_norm is not None:
        if bb_norm >= 65:
            return "BULLISH"
        if bb_norm <= 35:
            return "BEARISH"
        return "NEUTRAL"

    return "NEUTRAL"


def _count_signals(state) -> int:
    """Count populated signals for confidence calibration."""
    m = getattr(state, "macro", None)
    f = getattr(state, "flows", None)
    d = getattr(state, "derivatives", None)
    feat = getattr(state, "features", None)

    count = 0
    if m and m.vix is not None:
        count += 1
    if m and m.brent is not None:
        count += 1
    if m and m.dxy is not None:
        count += 1
    if f and f.fii_net is not None:
        count += 1
    if f and f.dii_net is not None:
        count += 1
    if d and d.pcr is not None:
        count += 1
    if feat and feat.breadth_score is not None:
        count += 1
    return count


def _dominant_driver_from_bb(state) -> str:
    """Build dominant driver string from available data."""
    m = getattr(state, "macro", None)
    f = getattr(state, "flows", None)
    drivers = []

    if m:
        if m.vix is not None:
            drivers.append(f"VIX {m.vix:.0f}")
        if m.usdinr is not None:
            drivers.append(f"USDINR ₹{m.usdinr:.1f}")
        if m.brent is not None:
            drivers.append(f"Brent ${m.brent:.0f}")

    if f and f.fii_net is not None:
        direction = "buying" if f.fii_net > 0 else "selling"
        drivers.append(f"FII {direction} {_fmt_rupee_local(f.fii_net)}")

    return " + ".join(drivers[:3]) if drivers else "Mixed signals"


def _narrative_from_bb(bb_norm: Optional[float], market_phase: Optional[str], data_count: int) -> str:
    """Build narrative from statistical composite."""
    if market_phase:
        return f"Market phase: {market_phase}."
    if bb_norm is not None:
        if bb_norm >= 65:
            return f"Composite bullish ({bb_norm:.0f}/100)."
        if bb_norm <= 35:
            return f"Composite bearish ({bb_norm:.0f}/100)."
        return f"Mixed flows; VIX signals unknown. No strong directional signal."
    return f"Insufficient data ({data_count} signals)."
