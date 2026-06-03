"""
Delta Renderer — Unified Regime Card Output.

Merges MarketState + signal_arbitrator + forecast into a single user-facing
regime card. No raw gap scores. No conflicting frameworks. One card per send.

Usage:
    from src.delta_renderer import render_regime_card
    text = render_regime_card(state, delta, forecast, job_time)
"""
from __future__ import annotations

from typing import Optional, Dict


def _fmt_rupee_local(value: float) -> str:
    """Format rupee value with sign after ₹ symbol: ₹-655Cr (Bloomberg-standard)."""
    sign = "-" if value < 0 else "+"
    return f"₹{sign}{abs(value):,.0f}Cr"


# ── Regime card renderer ────────────────────────────────────────────────────


def render_regime_card(
    state,
    delta: Dict,
    forecast=None,
    job_time: str = "08:00",
    key_levels: Optional[Dict] = None,
) -> str:
    """Render a compact P4-compliant regime card.

    Structure:
      🟡 Regime: NEUTRAL | Fragility: 60/100
      Active: Stagflation (63, EMERGING Day 1), Carry Unwind (47, EMERGING Day 1)
      Drivers: Brent $98 (stress), USDINR ₹95.7 (extreme)
      Transmission (Stagflation): Heatflation — real yield 6.3

    No evidence checklist, no confidence, no bias — Fragility bridges pillars to regime.
    """
    lines = []

    # ── Resolve regime ─────────────────────────────────────────────────────
    regime_label = _resolve_regime_label(state)
    emoji = _regime_emoji(regime_label)
    override_reason = getattr(state, "final_override_reason", None) or ""
    dominant_driver = getattr(state, "final_dominant_driver", "") or ""

    # ── Fragility + pillars (from state or compute inline) ─────────────────
    fragility_score = getattr(state, "fragility_score", None)
    fragility_components = getattr(state, "fragility_components", {})
    pillars = getattr(state, "pillar_metrics", None)

    _computed = False
    if fragility_score is None or not pillars:
        try:
            from src.pillar_classifier import get_percentiles_from_csv, classify_pillars
            from src.fragility_index import compute_fragility_index
            from src.stress_index import compute_stress_index
            _pcts = get_percentiles_from_csv()
            if _pcts:
                _plls = classify_pillars(_pcts)
                if _plls:
                    pillars = _plls
                    _stress = compute_stress_index()
                    if _stress.get("ok"):
                        _frag = compute_fragility_index(_stress["stress_score"], _plls)
                        if _frag.get("ok"):
                            fragility_score = _frag.get("fragility_score")
                            fragility_components = _frag.get("components", {})
                            _computed = True
        except Exception:
            pass

    comps = fragility_components or {}
    base = comps.get("base", 0) if comps else 0
    breadth = comps.get("breadth", 0) if comps else 0
    raw_peak = comps.get("raw_peak", comps.get("intensity", 0)) if comps else 0

    # ── Line 1: Regime + Fragility ─────────────────────────────────────────
    if override_reason:
        lines.append(f"{emoji} *{regime_label}* (Override: {dominant_driver})")
    else:
        lines.append(f"{emoji} *Regime: {regime_label}*")
    if fragility_score is not None:
        cap = " (<65 cap)" if 65 < fragility_score <= 85 else (" (>85 — force DEFENSIVE)" if fragility_score > 85 else "")
        lines[-1] += f" | Fragility: {fragility_score:.0f}/100{cap}"

    # ── Line 2: Active pillars ─────────────────────────────────────────────
    active_parts = []
    if pillars and isinstance(pillars, dict):
        _sorted = sorted(pillars.items(), key=lambda x: x[1], reverse=True)
        for p_name, p_score in _sorted:
            if p_score >= 40:
                display = p_name.replace("_", " ").title()
                lc_state = getattr(state, "pillar_lifecycle", {}).get(p_name, {})
                lc_suffix = ""
                if lc_state:
                    lc_suffix = f", {lc_state.get('state', 'EMERGING')} Day {lc_state.get('age_days', 1)}"
                active_parts.append(f"{display} ({p_score:.0f}{lc_suffix})")
    if active_parts:
        lines.append(f"Active: {', '.join(active_parts[:3])}")

    # ── Line 3: Drivers from macro extremes ────────────────────────────────
    drivers = _build_extreme_drivers(state)
    if drivers:
        lines.append(f"Drivers: {drivers}")

    # ── Line 4+: Transmission for top active pillar ────────────────────────
    if active_parts and pillars:
        top_key = sorted(pillars.items(), key=lambda x: x[1], reverse=True)[0][0]
        try:
            from src.consequence_engine import get_baselines
            from src.transmission_mechanics import compute_transmission, format_transmission
            _m = getattr(state, "macro", {})
            _dxy = getattr(_m, "dxy_signal", None) if hasattr(_m, "dxy_signal") else None
            current = {
                "brent": getattr(_m, "brent", None) if hasattr(_m, "brent") else None,
                "usdinr": getattr(_m, "usdinr", None) if hasattr(_m, "usdinr") else None,
                "vix": getattr(_m, "vix", None) if hasattr(_m, "vix") else None,
                "dxy_signal": _dxy,
            }
            current = {k: v for k, v in current.items() if v is not None}
            if current:
                _bl = get_baselines()
                tx = compute_transmission(top_key, current, _bl)
                if tx:
                    tx_str = format_transmission(top_key, tx)
                    if tx_str:
                        lines.append(tx_str)
        except Exception:
            pass

    # ── Key levels ─────────────────────────────────────────────────────────
    if key_levels:
        level_parts = []
        if key_levels.get("support"):
            level_parts.append(f"Support {key_levels['support']:,.0f}")
        if key_levels.get("resistance"):
            level_parts.append(f"Resistance {key_levels['resistance']:,.0f}")
        if key_levels.get("max_pain"):
            level_parts.append(f"Max Pain {key_levels['max_pain']:,.0f}")
        if level_parts:
            lines.append(f"  Levels: {' | '.join(level_parts)}")

    lines.append("━" * 26)
    return "\n".join(lines)


def _resolve_regime_label(state) -> str:
    """Resolve a single regime label from MarketState.

    Priority: final_regime (arbiter verdict) > market_phase > bull_bear_normalized > default.
    """
    final = getattr(state, "final_regime", None)
    if final:
        return final

    phase = getattr(state, "market_phase", None)
    bb_norm = getattr(state, "bull_bear_normalized", None)

    if phase:
        phase_map = {
            "ACCUMULATION": "BULLISH",
            "MARKUP": "BULLISH",
            "DISTRIBUTION": "BEARISH",
            "DECLINE": "BEARISH",
        }
        return phase_map.get(phase, "NEUTRAL")

    if bb_norm is not None:
        if bb_norm >= 65:
            return "BULLISH"
        if bb_norm <= 35:
            return "BEARISH"
        return "NEUTRAL"

    return "NEUTRAL"


def _regime_emoji(label: str) -> str:
    if "BULL" in label.upper():
        return "🟢"
    if "BEAR" in label.upper() or "DEFENSIVE" in label.upper():
        return "🔴"
    return "🟡"


def _build_extreme_drivers(state) -> str:
    """Build a compact driver string from macro extremes (used in regime card)."""
    parts = []
    m = getattr(state, "macro", {})

    # Brent
    if m and m.brent is not None:
        b = m.brent
        if b >= 100:
            parts.append(f"Brent ${b:.0f} (extreme)")
        elif b >= 90:
            parts.append(f"Brent ${b:.0f} (stress)")
        elif b >= 80:
            parts.append(f"Brent ${b:.0f} (elevated)")

    # USDINR
    if m and m.usdinr is not None:
        u = m.usdinr
        if u >= 90:
            parts.append(f"USDINR ₹{u:.1f} (extreme)")
        elif u >= 85:
            parts.append(f"USDINR ₹{u:.1f} (elevated)")

    # VIX
    if m and m.vix is not None:
        v = m.vix
        if v >= 20:
            parts.append(f"VIX {v:.1f} (elevated)")

    # DXY
    if m and m.dxy_signal is not None:
        dxy = m.dxy_signal
        if "RIS" in dxy.upper():
            parts.append(f"DXY rising")
        elif "FALL" in dxy.upper():
            parts.append(f"DXY falling")

    # FII (from flows)
    f = getattr(state, "flows", {})
    if f and f.fii_net is not None and abs(f.fii_net) > 1000:
        direction = "selling" if f.fii_net < 0 else "buying"
        parts.append(f"FII ₹{abs(f.fii_net):,.0f}Cr ({direction})")

    return " | ".join(parts[:5]) if parts else ""
