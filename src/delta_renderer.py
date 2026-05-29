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
    """Format rupee value with sign before symbol: -₹655Cr instead of ₹-655Cr."""
    sign = "-" if value < 0 else "+"
    return f"{sign}₹{abs(value):,.0f}Cr"


# ── Regime card renderer ────────────────────────────────────────────────────


def render_regime_card(
    state,
    delta: Dict,
    forecast=None,
    job_time: str = "08:00",
    key_levels: Optional[Dict] = None,
) -> str:
    """Render a single unified regime card from MarketState.

    Replaces: Market State Dashboard + Master Signal + MF Intelligence.

    Structure:
      🎯 REGIME: NEUTRAL (Confidence: MEDIUM)
      ━━━━━━━━━━━━━━━━━━━━━━
      Evidence: 4/7 signals agree
        🟢 FII: ₹+705Cr (buying)
        🟢 DII: ₹+3,718Cr (accumulating)
        🟡 VIX: 16.1 (normal)
      📐 Forecast: NEUTRAL | confidence=50
      🎯 Tomorrow's Bias: Neutral unless Brent breaches $98
      Key levels: Support 23,435 | Resistance 24,178

    Args:
        state: MarketState with populated fields.
        delta: Output from compute_delta().
        forecast: Optional Forecast object.
        job_time: IST time for context (e.g., "08:00").
        key_levels: Optional dict with support/resistance/max_pain.

    Returns:
        Formatted Telegram text.
    """
    lines = []

    # ── Evidence bullets FIRST — needed for quorum check ────────────────────
    evidence = _build_evidence(state, delta)
    total_count = evidence["total_count"] if evidence else 0

    # ── Quorum check — need at least 3 signals ─────────────────────────────
    if total_count < 3:
        # Incomplete regime — show data-quality warning
        lines.append(f"⚠️ *REGIME: INCOMPLETE ({total_count}/8 signals available)*")
        lines.append("Confidence: INSUFFICIENT DATA")
        lines.append("━" * 26)
        if evidence and evidence["bullets"]:
            lines.append("📊 *Available signals:*")
            for bullet in evidence["bullets"]:
                lines.append(f"  {bullet}")
        lines.append("  Insufficient data for regime determination.")
        lines.append("━" * 26)
        return "\n".join(lines)

    # ── Regime header ──────────────────────────────────────────────────────
    regime_label = _resolve_regime_label(state)
    confidence = _resolve_confidence(state)
    emoji = _regime_emoji(regime_label)

    lines.append(f"{emoji} *{regime_label}*")
    lines.append(f"Confidence: {confidence}")
    lines.append("━" * 26)

    # ── Evidence bullets ──────────────────────────────────────────────────
    override_reason = getattr(state, "final_override_reason", None) or ""
    dominant_driver = getattr(state, "final_dominant_driver", "") or ""
    if evidence:
        if override_reason:
            lines.append(f"📊 *Override Active:* {dominant_driver} → {regime_label}")
            for bullet in evidence["bullets"]:
                lines.append(f"  {bullet}")
        else:
            lines.append(f"📊 *Evidence:* {evidence['agree_count']}/{evidence['total_count']} signals agree")
            for bullet in evidence["bullets"]:
                lines.append(f"  {bullet}")

    # ── Transition protocol (if gap is significant) ────────────────────────
    transition = _check_transition(state)
    if transition:
        lines.append("")
        lines.append(f"🟡 *{transition['label']}*")
        for line in transition["actions"]:
            lines.append(f"  {line}")

    # ── Forecast (if available) ────────────────────────────────────────────
    if forecast and forecast.direction:
        lines.append("")
        prob = f"prob_up={forecast.probability_up:.2f}" if forecast.probability_up else "no prob"
        conf = f"confidence={forecast.confidence}" if forecast.confidence is not None else "no conf"
        lines.append(f"📐 *Forecast:* {forecast.direction} | {prob} | {conf}")
        if forecast.primary_signals:
            sigs = ", ".join(forecast.primary_signals[:3])
            lines.append(f"  Signals: {sigs}")
        if forecast.contradiction_warnings:
            warns = ", ".join(forecast.contradiction_warnings[:2])
            lines.append(f"  ⚠️ Risks: {warns}")

    # ── Actionable bias ────────────────────────────────────────────────────
    bias = _build_actionable_bias(state, forecast, key_levels)
    if bias:
        lines.append("")
        lines.append(f"🎯 *Bias:* {bias}")

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


def _resolve_confidence(state) -> str:
    """Resolve confidence from MarketState.

    Priority: final_regime_confidence (arbiter) > bull_bear_confidence > fallback.
    """
    final_conf = getattr(state, "final_regime_confidence", None)
    if final_conf:
        return final_conf

    bb_conf = getattr(state, "bull_bear_confidence", None)

    if bb_conf is not None:
        if bb_conf >= 70:
            return "HIGH"
        if bb_conf >= 40:
            return "MEDIUM"
        return "LOW"

    # Fallback: estimate from data availability
    data_count = _count_populated_signals(state)
    if data_count >= 5:
        return "MEDIUM"
    if data_count >= 3:
        return "LOW"
    return "LOW"


def _count_populated_signals(state) -> int:
    """Count how many key signals have data."""
    count = 0
    m = getattr(state, "macro", None)
    f = getattr(state, "flows", None)
    d = getattr(state, "derivatives", None)
    feat = getattr(state, "features", None)

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


def _regime_emoji(label: str) -> str:
    if "BULL" in label.upper():
        return "🟢"
    if "BEAR" in label.upper() or "DEFENSIVE" in label.upper():
        return "🔴"
    return "⚪"


def _build_evidence(state, delta: Dict) -> Optional[Dict]:
    """Build evidence bullets from MarketState fields.

    Only includes fields that have data. Uses delta to mark changed fields.
    """
    bullets = []
    agree_count = 0
    total_count = 0

    m = getattr(state, "macro", {})
    f = getattr(state, "flows", {})
    d = getattr(state, "derivatives", {})
    feat = getattr(state, "features", {})

    # FII
    if f and f.fii_net is not None:
        total_count += 1
        net = f.fii_net
        if net > 0:
            agree_count += 1
            emoji = "🟢"
            action = "buying"
        else:
            emoji = "🔴"
            action = "selling"
        bullets.append(f"{emoji} FII: {_fmt_rupee_local(net)} ({action})")

    # DII
    if f and f.dii_net is not None:
        total_count += 1
        net = f.dii_net
        if net > 0:
            agree_count += 1
            emoji = "🟢"
            action = "accumulating"
        else:
            emoji = "🔴"
            action = "distributing"
        bullets.append(f"{emoji} DII: {_fmt_rupee_local(net)} ({action})")

    # VIX
    if m and m.vix is not None:
        total_count += 1
        vix = m.vix
        regime = m.vix_regime or _vix_regime_label(vix)
        if regime == "LOW" or regime == "NORMAL":
            agree_count += 1
            emoji = "🟢"
        elif regime == "HIGH":
            emoji = "🔴"
        else:
            emoji = "🟡"
        bullets.append(f"{emoji} VIX: {vix:.1f} ({regime.lower()})")

    # USDINR — rupee strength/weakness signal
    if m and m.usdinr is not None:
        total_count += 1
        usdinr = m.usdinr
        # >90 = extreme weakness (bearish for India), <80 = strong rupee (bullish)
        if usdinr >= 90:
            emoji = "🔴"
            bullets.append(f"{emoji} USDINR: ₹{usdinr:.1f} (extreme weakness)")
        elif usdinr >= 85:
            emoji = "🟡"
            bullets.append(f"{emoji} USDINR: ₹{usdinr:.1f} (elevated)")
        elif usdinr <= 80:
            emoji = "🟢"
            agree_count += 1
            bullets.append(f"{emoji} USDINR: ₹{usdinr:.1f} (strong)")
        else:
            emoji = "🟡"
            bullets.append(f"{emoji} USDINR: ₹{usdinr:.1f} (neutral)")

    # Brent — oil cost signal for India
    if m and m.brent is not None:
        total_count += 1
        brent = m.brent
        if brent >= 100:
            emoji = "🔴"
            bullets.append(f"{emoji} Brent: ${brent:.0f} (extreme)")
        elif brent >= 90:
            emoji = "🔴"
            bullets.append(f"{emoji} Brent: ${brent:.0f} (stress)")
        elif brent >= 80:
            emoji = "🟡"
            bullets.append(f"{emoji} Brent: ${brent:.0f} (elevated)")
        else:
            emoji = "🟢"
            agree_count += 1
            bullets.append(f"{emoji} Brent: ${brent:.0f} (favorable)")

    # DXY — dollar strength = EM headwind
    if m and m.dxy_signal is not None:
        total_count += 1
        dxy_sig = m.dxy_signal
        if "RIS" in dxy_sig.upper():
            emoji = "🔴"
            bullets.append(f"{emoji} DXY: rising (EM headwind)")
        elif "FALL" in dxy_sig.upper():
            emoji = "🟢"
            agree_count += 1
            bullets.append(f"{emoji} DXY: falling (EM tailwind)")
        else:
            emoji = "🟡"
            bullets.append(f"{emoji} DXY: flat")

    # PCR
    if d and d.pcr is not None:
        total_count += 1
        pcr = d.pcr
        signal = d.pcr_signal or _pcr_signal_label(pcr)
        if "BULL" in signal.upper():
            agree_count += 1
            emoji = "🟢"
        elif "BEAR" in signal.upper():
            emoji = "🔴"
        else:
            emoji = "🟡"
            agree_count += 1  # neutral agrees with neutral
        bullets.append(f"{emoji} PCR: {pcr:.2f} ({signal.lower()})")

    # Breadth
    if feat and feat.breadth_score is not None:
        total_count += 1
        bs = feat.breadth_score
        if bs > 0.1:
            agree_count += 1
            emoji = "🟢"
        elif bs < -0.1:
            emoji = "🔴"
        else:
            emoji = "🟡"
            agree_count += 1
        bullets.append(f"{emoji} Breadth: {bs:+.2f}")

    # Momentum
    if feat and feat.momentum_12m is not None:
        total_count += 1
        mom = feat.momentum_12m
        emoji = "🟢" if mom > 0 else ("🔴" if mom < 0 else "🟡")
        if mom >= 0:
            agree_count += 1
        bullets.append(f"{emoji} Momentum: {mom:+.3f}")

    # Cap bullets
    return {
        "agree_count": agree_count,
        "total_count": total_count,
        "bullets": bullets[:6],
    }


def _vix_regime_label(vix: float) -> str:
    if vix < 12:
        return "LOW"
    if vix < 20:
        return "NORMAL"
    return "HIGH"


def _pcr_signal_label(pcr: float) -> str:
    if pcr > 1.3:
        return "BULLISH"
    if pcr < 0.7:
        return "BEARISH"
    return "NEUTRAL"


def _check_transition(state) -> Optional[Dict]:
    """Check if structural vs sentiment gap implies a transition phase.

    Uses signal_arbitrator internally but only returns user-facing protocol.
    """
    try:
        from src.signal_arbitrator import arbitrate_signals

        signals = {}
        bb = getattr(state, "bull_bear_score", None)
        if bb is not None:
            signals["bull_bear"] = bb

        m = getattr(state, "macro", {})
        f = getattr(state, "flows", {})
        d = getattr(state, "derivatives", {})

        if m and m.vix is not None:
            signals["vix"] = m.vix
        if f and f.fii_net is not None:
            # Use streak as proxy for fear_greed direction
            signals["fear_greed"] = max(0, min(100, 50 + f.fii_net / 100))
        if d and d.pcr is not None:
            signals["pcr"] = d.pcr

        if len(signals) < 2:
            return None

        arb = arbitrate_signals(signals)
        gap = arb.get("gap_analysis", {})

        if gap.get("is_significant") and gap.get("gap", 0) >= 10:
            direction = gap.get("direction", "")
            actions = []
            if "COMPLACENCY" in direction:
                actions.append("Action: Hedge longs, reduce size, wait for alignment")
            elif "FEAR" in direction:
                actions.append("Action: Watch for oversold bounce, scale in cautiously")
            else:
                actions.append("Action: Reduce momentum exposure while divergence persists")

            return {
                "label": "Transition Phase",
                "actions": actions,
            }
    except Exception:
        pass

    return None


def _build_actionable_bias(state, forecast, key_levels: Optional[Dict] = None) -> Optional[str]:
    """Build a single actionable bias line.

    Format: '[Direction] unless [specific condition]'
    """
    # Use forecast direction if available
    direction = None
    if forecast and forecast.direction:
        direction = forecast.direction.upper()
    else:
        regime = _resolve_regime_label(state)
        direction = regime.upper()

    if direction == "NEUTRAL":
        # Neutral unless something breaks
        conditions = []
        m = getattr(state, "macro", {})
        if m and m.brent is not None:
            conditions.append(f"Brent breaches ${m.brent + 2:.0f}")
        if m and m.vix is not None and m.vix > 15:
            conditions.append(f"VIX spikes above {m.vix + 3:.0f}")
        if not conditions:
            conditions.append("new catalyst emerges")

        return f"Neutral — waiting for catalyst ({' or '.join(conditions[:2])})"

    if direction == "BULLISH":
        conditions = []
        m = getattr(state, "macro", {})
        if m and m.vix is not None:
            conditions.append(f"VIX spikes above {m.vix + 5:.0f}")
        if key_levels and key_levels.get("support"):
            conditions.append(f"Support {key_levels['support']:,.0f} breaks")
        if not conditions:
            conditions.append("bearish catalyst")

        return f"Bullish tilts unless {' or '.join(conditions[:2])}"

    if direction == "BEARISH":
        conditions = []
        if key_levels and key_levels.get("resistance"):
            conditions.append(f"Resistance {key_levels['resistance']:,.0f} breaks")
        if not conditions:
            conditions.append("risk-on shift")

        return f"Defensive tilts unless {' or '.join(conditions[:2])}"

    return None
