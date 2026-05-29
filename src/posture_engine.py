"""
Posture Engine — Deterministic THEREFORE Clause

Derives actionable trading posture from MarketState data.
No AI needed. Called by fallback paths and appended to AI output.

Posture = f(Macro extremes, FII flows, VIX regime, Breadth, DXY, Brent)

Three tiers:
  DEFENSIVE   — reduce beta, hedge, watch for breakdowns
  CONSTRUCTIVE — range-trade, buy support, sell resistance
  NO EDGE     — stay light, wait for catalyst

Usage:
    from src.posture_engine import compute_posture
    result = compute_posture(macro, flows, derivatives, features)
    # result.posture, result.rationale, result.triggers, result.therefore
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


def _fmt_rupee_local(value: float) -> str:
    """Format rupee value with sign before symbol: -₹655Cr instead of ₹-655Cr."""
    sign = "-" if value < 0 else "+"
    return f"{sign}₹{abs(value):,.0f}Cr"


@dataclass
class PostureResult:
    posture: str          # "DEFENSIVE", "CONSTRUCTIVE", "NO EDGE"
    confidence: str       # "HIGH", "MEDIUM", "LOW"
    rationale: str        # 1-sentence WHY
    therefore: str        # actionable posture line
    triggers: list[str]   # 2-3 specific levels that would change posture


def reconcile_regime(statistical_regime: str, posture_result: "PostureResult") -> tuple[str, str]:
    """Reconcile statistical regime with posture-driven regime.

    If posture confidence is MEDIUM+, the macro-extreme signal overrides
    the statistical composite. Returns (final_regime, confidence).

    Rule: There can be only one regime per trade date.
    """
    posture = posture_result.posture
    confidence = posture_result.confidence

    # Mapping: posture tier → regime label
    posture_to_regime = {
        "DEFENSIVE": "DEFENSIVE",
        "CONSTRUCTIVE": "BULLISH",
        "NO EDGE": "NEUTRAL",
    }
    posture_regime = posture_to_regime.get(posture, "NEUTRAL")

    # If posture is MEDIUM+ confidence and differs from statistical, override
    if confidence in ("MEDIUM", "HIGH") and posture_regime != statistical_regime:
        return posture_regime, confidence

    return statistical_regime, confidence


def _safe(val, default=0.0) -> float:
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def compute_posture(
    vix: Optional[float] = None,
    vix_regime: Optional[str] = None,
    usdinr: Optional[float] = None,
    brent: Optional[float] = None,
    dxy: Optional[float] = None,
    dxy_signal: Optional[str] = None,
    fii_net: Optional[float] = None,
    fii_streak: Optional[int] = None,
    dii_net: Optional[float] = None,
    absorption_ratio: Optional[float] = None,
    pcr: Optional[float] = None,
    breadth_score: Optional[float] = None,
    gold: Optional[float] = None,
    market_phase: Optional[str] = None,
    bull_bear_normalized: Optional[float] = None,
    forced_regime: Optional[str] = None,  # arbiter override: "DEFENSIVE", "BULLISH", etc.
) -> PostureResult:
    """Compute deterministic posture from available state.

    Works with partial data — degrades gracefully when signals are missing.
    If forced_regime is set (from arbiter), posture aligns to that regime.
    """
    vix = _safe(vix)
    usdinr = _safe(usdinr)
    brent = _safe(brent)
    dxy = _safe(dxy)
    fii_net = _safe(fii_net)
    dii_net = _safe(dii_net)
    absorption = _safe(absorption_ratio)
    pcr = _safe(pcr)
    breadth = _safe(breadth_score)
    gold = _safe(gold)
    bb_norm = _safe(bull_bear_normalized)

    # ── Score each signal: +1 (bullish), 0 (neutral), -1 (bearish) ────
    scores = []
    rationales = []

    # VIX
    if vix > 0:
        if vix < 12:
            scores.append(1)
            rationales.append("VIX very low (complacency)")
        elif vix < 20:
            scores.append(0)
            rationales.append("VIX normal")
        else:
            scores.append(-1)
            rationales.append(f"VIX elevated at {vix:.0f}")

    # USDINR — rupee weakness is bearish for India
    if usdinr > 0:
        if usdinr >= 95:
            scores.append(-1)
            rationales.append(f"INR extreme weakness at ₹{usdinr:.0f}")
        elif usdinr >= 90:
            scores.append(-1)
            rationales.append(f"INR elevated at ₹{usdinr:.0f}")
        elif usdinr >= 85:
            scores.append(0)
            rationales.append(f"INR neutral at ₹{usdinr:.0f}")
        else:
            scores.append(1)
            rationales.append(f"INR strong at ₹{usdinr:.0f}")

    # Brent — high oil is bearish for India (importer)
    if brent > 0:
        if brent >= 100:
            scores.append(-1)
            rationales.append(f"Brent extreme at ${brent:.0f}")
        elif brent >= 90:
            scores.append(-1)
            rationales.append(f"Brent stress at ${brent:.0f}")
        elif brent >= 80:
            scores.append(0)
            rationales.append(f"Brent elevated at ${brent:.0f}")
        else:
            scores.append(1)
            rationales.append(f"Brent favorable at ${brent:.0f}")

    # FII flows
    if fii_net is not None:
        if fii_net > 500:
            scores.append(1)
            rationales.append(f"FII buying {_fmt_rupee_local(fii_net)}")
        elif fii_net > 0:
            scores.append(0)
            rationales.append(f"FII mild buying {_fmt_rupee_local(fii_net)}")
        elif fii_net > -500:
            scores.append(0)
            rationales.append(f"FII mild selling {_fmt_rupee_local(fii_net)}")
        else:
            scores.append(-1)
            rationales.append(f"FII heavy selling {_fmt_rupee_local(fii_net)}")

    # FII streak
    if fii_streak is not None:
        if fii_streak >= 5:
            scores.append(-1)
            rationales.append(f"FII {fii_streak}-day selling streak")
        elif fii_streak <= -5:
            scores.append(1)
            rationales.append(f"FII {-fii_streak}-day buying streak")

    # DII absorption
    if dii_net is not None:
        if dii_net > 1000:
            scores.append(1)
            rationales.append(f"DII strong absorption {_fmt_rupee_local(dii_net)}")
        elif dii_net < -500:
            scores.append(-1)
            rationales.append(f"DII distributing {_fmt_rupee_local(dii_net)}")

    # PCR
    if pcr > 0:
        if pcr > 1.4:
            scores.append(1)
            rationales.append(f"PCR oversold at {pcr:.2f}")
        elif pcr < 0.6:
            scores.append(-1)
            rationales.append(f"PCR overbought at {pcr:.2f}")

    # Breadth
    if breadth_score is not None:
        if breadth > 0.3:
            scores.append(1)
            rationales.append(f"Breadth strong ({breadth:+.2f})")
        elif breadth > 0:
            scores.append(0)
            rationales.append(f"Breadth positive ({breadth:+.2f})")
        elif breadth > -0.3:
            scores.append(0)
            rationales.append(f"Breadth weak ({breadth:+.2f})")
        else:
            scores.append(-1)
            rationales.append(f"Breadth poor ({breadth:+.2f})")

    # Bull/Bear normalized score
    if bb_norm > 0:
        if bb_norm >= 65:
            scores.append(1)
            rationales.append(f"Bull/Bear bullish ({bb_norm:.0f})")
        elif bb_norm >= 55:
            scores.append(0)
            rationales.append(f"Bull/Bear cautious bull ({bb_norm:.0f})")
        elif bb_norm >= 45:
            scores.append(0)
            rationales.append(f"Bull/Bear neutral ({bb_norm:.0f})")
        elif bb_norm >= 35:
            scores.append(0)
            rationales.append(f"Bull/Bear cautious bear ({bb_norm:.0f})")
        else:
            scores.append(-1)
            rationales.append(f"Bull/Bear bearish ({bb_norm:.0f})")

    if not scores:
        return PostureResult(
            posture="NO EDGE",
            confidence="LOW",
            rationale="Insufficient data to determine posture.",
            therefore="No edge. Wait for more signals before taking positions.",
            triggers=["VIX moves >2 points", "FII net exceeds ±₹500Cr", "Brent breaks $96 or $80"],
        )

    # ── Aggregate score ─────────────────────────────────────────────
    total = sum(scores)
    count = len(scores)
    avg = total / count

    # Count extremes for conviction
    bull_count = sum(1 for s in scores if s > 0)
    bear_count = sum(1 for s in scores if s < 0)
    neutral_count = sum(1 for s in scores if s == 0)

    # ── Determine posture ──────────────────────────────────────────
    # Track top bearish and bullish rationales for the "tension" line
    top_bear = [r for s, r in zip(scores, rationales) if s < 0][:3]
    top_bull = [r for s, r in zip(scores, rationales) if s > 0][:3]

    if avg <= -0.5 or bear_count >= 3:
        posture = "DEFENSIVE"
        confidence = "HIGH" if bear_count >= 4 else "MEDIUM"
        rationale = "; ".join(top_bear[:2])
        therefore = _defensive_therefore(usdinr, brent, vix, fii_net)
        triggers = _defensive_triggers(usdinr, brent, vix, current_regime="DEFENSIVE")
    elif avg >= 0.5 or bull_count >= 3:
        posture = "CONSTRUCTIVE"
        confidence = "HIGH" if bull_count >= 4 else "MEDIUM"
        rationale = "; ".join(top_bull[:2])
        therefore = _constructive_therefore(vix, fii_net, breadth)
        triggers = _constructive_triggers(vix, usdinr, brent)
    else:
        posture = "NO EDGE"
        confidence = "LOW" if neutral_count >= count // 2 else "MEDIUM"
        # Show tension between opposing forces
        if top_bear and top_bull:
            rationale = f"Tension: {top_bull[0]} vs {top_bear[0]}"
        elif top_bear:
            rationale = "; ".join(top_bear[:2])
        elif top_bull:
            rationale = "; ".join(top_bull[:2])
        else:
            rationale = "All signals neutral."
        therefore = _no_edge_therefore(usdinr, brent, vix)
        triggers = _no_edge_triggers(usdinr, brent, vix, fii_net)

    # ── Apply forced regime from arbiter (aligns posture with verdict) ─
    if forced_regime:
        regime_to_posture = {
            "DEFENSIVE": "DEFENSIVE",
            "BULLISH": "CONSTRUCTIVE",
            "BEARISH": "DEFENSIVE",
            "NEUTRAL": "NO EDGE",
        }
        forced_posture = regime_to_posture.get(forced_regime, posture)
        if forced_posture != posture:
            posture = forced_posture
            if posture == "DEFENSIVE":
                _drivers = []
                if usdinr >= 95:
                    _drivers.append(f"INR ₹{usdinr:.0f}")
                if brent >= 90:
                    _drivers.append(f"Brent ${brent:.0f}")
                if vix >= 20:
                    _drivers.append(f"VIX {vix:.0f}")
                _driver_str = " + ".join(_drivers) if _drivers else "macro stress"
                rationale = f"Macro driver: {_driver_str} — forces {forced_regime.lower()} posture."
                therefore = _defensive_therefore(usdinr, brent, vix, fii_net)
                triggers = _defensive_triggers(usdinr, brent, vix, current_regime="DEFENSIVE")
            elif posture == "CONSTRUCTIVE":
                rationale = f"Arbiter verdict: {forced_regime} regime → constructive posture."
                therefore = _constructive_therefore(vix, fii_net, breadth)
                triggers = _constructive_triggers(vix, usdinr, brent)

    return PostureResult(
        posture=posture,
        confidence=confidence,
        rationale=rationale,
        therefore=therefore,
        triggers=triggers,
    )


def _defensive_therefore(usdinr: float, brent: float, vix: float, fii_net: float) -> str:
    """DEFENSIVE = Cut beta. No new longs. Hedge existing. Reduce, do not add."""
    parts = ["Cut beta, hedge, raise cash"]
    if brent >= 90:
        parts.append("reduce OMCs and oil importers")
    if vix >= 20:
        parts.append("hedge with Nifty PE; reduce position size")
    if fii_net < -500:
        parts.append("avoid chasing momentum — FII liquidity drain")
    return "; ".join(parts[:3]) + "."


def _defensive_triggers(usdinr: float, brent: float, vix: float, current_regime: str = None) -> list[str]:
    """Price levels that would confirm or reverse defensive posture.

    When current_regime is DEFENSIVE, shows next-step escalation AND
    de-escalation thresholds. Skips redundant current-state triggers.
    """
    triggers = []
    if brent > 0:
        if brent >= 96:
            triggers.append(f"Brent >${brent:.0f} confirms stress")
        elif current_regime == "DEFENSIVE":
            triggers.append(f"Brent >$96 → escalation; Brent <$85 → de-escalation")
        else:
            triggers.append(f"Brent $96: monitor — exceeds override threshold")
    if usdinr > 0:
        if usdinr >= 96:
            triggers.append(f"INR ₹{usdinr:.0f}+ → extreme import pain")
        elif current_regime == "DEFENSIVE":
            triggers.append(f"INR ₹97+ escalates; INR <₹94 → possible downgrade")
        else:
            triggers.append(f"INR ₹96: monitor — at override threshold")
    if vix > 0:
        if vix < 20:
            triggers.append(f"VIX >20: monitor volatility spike")
        else:
            triggers.append(f"VIX <{vix - 5:.0f}: watch for de-escalation")
    return triggers[:3]


def _constructive_therefore(vix: float, fii_net: float, breadth: float) -> str:
    """Generate THEREFORE clause for constructive posture."""
    parts = []

    if vix < 15:
        parts.append("range-trading environment — buy support, sell resistance")
    if fii_net > 0:
        parts.append("FII inflows support upside")
    if breadth is not None and breadth > 0.3:
        parts.append("broad market participation confirms trend")

    if not parts:
        parts.append("constructive but not aggressive — selective longs")

    return "Constructive. " + ". ".join(parts[:2]) + "."


def _constructive_triggers(vix: float, usdinr: float, brent: float) -> list[str]:
    """Price levels that would invalidate constructive posture."""
    triggers = []
    if vix > 0:
        triggers.append(f"VIX spikes above {vix + 5:.0f} → reduce exposure")
    if usdinr > 0:
        triggers.append(f"INR breaks ₹{usdinr + 1:.0f} → reassess IT longs")
    if brent > 0:
        triggers.append(f"Brent breaks ${brent + 3:.0f} → defensive tilt")
    return triggers[:3]


def _no_edge_therefore(usdinr: float, brent: float, vix: float) -> str:
    """Generate THEREFORE clause for no-edge posture."""
    levels = []
    if usdinr > 0:
        if usdinr >= 90:
            levels.append(f"INR ₹{usdinr + 1:.0f} (breakout to extreme)")
        elif usdinr <= 85:
            levels.append(f"INR ₹{usdinr - 1:.0f} (breakdown to weak)")
        else:
            levels.append(f"INR ₹96 (extreme weakness)")
    if brent > 0:
        if brent >= 80:
            levels.append(f"Brent ${brent + 5:.0f} (stress zone)")
        elif brent <= 80:
            levels.append(f"Brent ${brent - 5:.0f} (favorable)")
        else:
            levels.append("Brent $96 (stress)")
    if vix > 0:
        if vix >= 15:
            levels.append(f"VIX {vix + 5:.0f} (fear spike)")
        elif vix <= 15:
            levels.append(f"VIX {max(vix - 5, 5):.0f} (complacency)")
        else:
            levels.append("VIX 20 (high)")

    if not levels:
        levels = ["VIX spikes >20", "Brent breaks $96", "FII streak >5 days"]

    return f"No edge. Stay light until one of these breaks: {'; '.join(levels[:3])}."


def _no_edge_triggers(usdinr: float, brent: float, vix: float, fii_net: float) -> list[str]:
    """Price levels that would create edge from neutral state."""
    triggers = []
    if brent > 0:
        triggers.append(f"Brent ${brent + 5:.0f} (stress) or ${brent - 5:.0f} (relief)")
    if usdinr > 0:
        triggers.append(f"INR ₹{usdinr + 1:.0f} (weakness) or ₹{usdinr - 1:.0f} (strength)")
    if vix > 0:
        triggers.append(f"VIX {vix + 5:.0f} (fear) or {max(vix - 5, 5):.0f} (calm)")
    if fii_net is not None:
        direction = "continues" if fii_net < 0 else "reverses"
        triggers.append(f"FII selling {direction} for 5+ days")
    return triggers[:3] if triggers else ["Macro shift", "FII regime change", "Earnings surprise"]


def format_posture_card(result: PostureResult, prefix: str = "") -> str:
    """Format a posture result as a Telegram-ready block."""
    lines = []
    label = prefix if prefix else "Posture"

    lines.append(f"📌 *{label}: {result.posture}*")
    lines.append(f"Confidence: {result.confidence}")
    lines.append(f"  Why: {result.rationale}")
    lines.append(f"  Action: {result.therefore}")
    lines.append(f"  Watch: {' | '.join(t for t in result.triggers[:3])}")

    return "\n".join(lines)
