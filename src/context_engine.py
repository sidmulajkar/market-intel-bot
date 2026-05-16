"""
Context Engine — Pre-compute all reasoning inside single job execution
AI receives scored conclusions only. AI writes narrative only.

Layer 1: DATA → Layer 2: CONTEXT → Layer 3: CAUSE → Layer 4: IMPLICATION → Layer 5: SYNTHESIS
"""
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Supabase imports
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 2: CONTEXTUALIZATION — Add historical comparison to raw data
# ═══════════════════════════════════════════════════════════════════════════════

def get_fii_dii_context(days: int = 30) -> Dict:
    """
    Compute FII/DII context: vs 4W avg, streak detection, significance score.
    All computation in Python — zero extra API calls.
    """
    from src.db import get_fii_dii_flows

    rows = get_fii_dii_flows(days=days)
    row_count = len(rows) if rows else 0
    
    # Sparse data handling
    if row_count < 3:
        return {"ok": False, "message": "Insufficient FII/DII data (<3 rows)", "confidence": "LOW"}
    if row_count < 10:
        # Low confidence but still usable
        pass  # Continue with reduced confidence

    # Build time series
    import pandas as pd
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    # 4-week rolling average
    df["fii_4w_avg"] = df["fiinet_cr"].rolling(20, min_periods=5).mean()
    df["dii_4w_avg"] = df["diinet_cr"].rolling(20, min_periods=5).mean()

    # Latest values
    latest = df.iloc[-1]
    prev_avg_fii = df["fii_4w_avg"].iloc[-1] if pd.notna(df["fii_4w_avg"].iloc[-1]) else 0
    prev_avg_dii = df["dii_4w_avg"].iloc[-1] if pd.notna(df["dii_4w_avg"].iloc[-1]) else 0

    # Z-score vs 4W avg
    fii_current = latest["fiinet_cr"]
    fii_std = df["fiinet_cr"].tail(20).std()
    fii_z_score = (fii_current - prev_avg_fii) / fii_std if fii_std > 0 else 0

    # Streak detection
    fii_streak = 0
    fii_direction = None
    for i in range(len(df) - 1, -1, -1):
        if fii_direction is None:
            fii_direction = "positive" if df.iloc[i]["fiinet_cr"] > 0 else "negative"
            fii_streak = 1
        elif (df.iloc[i]["fiinet_cr"] > 0 and fii_direction == "positive") or \
             (df.iloc[i]["fiinet_cr"] < 0 and fii_direction == "negative"):
            fii_streak += 1
        else:
            break

    # DII absorption (how much DII offset FII)
    dii_current = latest["diinet_cr"]
    net_current = fii_current + dii_current
    dii_absorbed = "High" if abs(dii_current) > abs(fii_current) * 0.8 else \
                   "Medium" if abs(dii_current) > abs(fii_current) * 0.4 else "Low"

    # Determine confidence based on data quality
    confidence = "HIGH" if row_count >= 20 else "MEDIUM" if row_count >= 10 else "LOW"
    
    return {
        "ok": True,
        "fii_net": fii_current,
        "dii_net": dii_current,
        "net": net_current,
        "fii_4w_avg": round(prev_avg_fii, 1),
        "dii_4w_avg": round(prev_avg_dii, 1),
        "fii_z_score": round(fii_z_score, 2),
        "data_points": row_count,
        "confidence": confidence,
        "fii_streak": fii_streak,
        "fii_streak_direction": fii_direction,
        "dii_absorbed": dii_absorbed,
        "date": latest["date"].strftime("%Y-%m-%d"),
    }


def get_vix_regime(vix_price: float = None) -> str:
    """
    Classify VIX into regime for Bull/Bear scoring.
    Returns UNKNOWN if VIX data unavailable.
    """
    if vix_price is None or vix_price <= 0:
        return "UNKNOWN"
    if vix_price > 20:
        return "HIGH"  # High volatility regime — risk-off
    elif vix_price < 15:
        return "LOW"   # Low volatility regime — risk-on, complacency
    else:
        return "NORMAL"


def get_dxy_signal(dxy_change_pct: float) -> Dict:
    """
    Interpret DXY move direction and implication.
    """
    if dxy_change_pct > 0.5:
        direction = "RISING"
        implication = "FII likely to sell (strong dollar)"
    elif dxy_change_pct < -0.5:
        direction = "FALLING"
        implication = "FII likely to buy (weak dollar)"
    else:
        direction = "FLAT"
        implication = "Neutral currency impact"

    return {
        "direction": direction,
        "change_pct": dxy_change_pct,
        "implication": implication,
    }


def get_macro_context(anchor_data: List[Dict]) -> Dict:
    """
    Extract VIX regime and DXY signal from anchor data.
    """
    vix_data = next((a for a in anchor_data if "VIX" in a.get("name", "")), None)
    dxy_data = next((a for a in anchor_data if "DXY" in a.get("name", "") or "Dollar" in a.get("name", "")), None)
    usd_data = next((a for a in anchor_data if "USD" in a.get("name", "")), None)

    context = {}

    if vix_data and vix_data.get("ok"):
        vix_price = vix_data.get("price", 0)
        context["vix_price"] = vix_price
        context["vix_regime"] = get_vix_regime(vix_price)
        context["vix_change"] = vix_data.get("change_pct", 0)

    if dxy_data and dxy_data.get("ok"):
        dxy_change = dxy_data.get("change_pct", 0)
        dxy_signal = get_dxy_signal(dxy_change)
        context["dxy"] = dxy_signal

    if usd_data and usd_data.get("ok"):
        context["usd_inr"] = {
            "price": usd_data.get("price"),
            "change_pct": usd_data.get("change_pct"),
        }

    return context


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 5: SYNTHESIS — Bull/Bear Composite Score
# ═══════════════════════════════════════════════════════════════════════════════

def compute_bull_bear_score(fii_context: Dict, macro_context: Dict) -> Dict:
    """
    Compute weighted Bull/Bear composite score (-40 to +40 range).
    All computed in Python — zero API calls.
    """
    score = 0
    signals = []

    # BEAR SIGNALS (weight: 60%)
    # FII outflow streak (heavy weight)
    if fii_context.get("fii_streak_direction") == "negative" and fii_context.get("fii_streak", 0) >= 3:
        score -= 15
        signals.append(f"FII outflow streak: {fii_context['fii_streak']} days")

    # FII significant selling (z-score)
    if fii_context.get("fii_z_score", 0) < -1.5:
        score -= 15
        signals.append(f"FII z-score: {fii_context['fii_z_score']} (significant selling)")

    # High VIX regime (skip if UNKNOWN)
    vix_regime = macro_context.get("vix_regime", "UNKNOWN")
    if vix_regime == "HIGH":
        score -= 10
        signals.append(f"VIX regime: HIGH ({macro_context.get('vix_price', 'N/A')})")
    elif vix_regime == "UNKNOWN":
        signals.append("VIX: data unavailable (skipped)")

    # DXY rising (dollar strength)
    dxy_dir = macro_context.get("dxy", {}).get("direction", "FLAT")
    if dxy_dir == "RISING":
        score -= 10
        signals.append(f"DXY rising → FII selling pressure")

    # Global risk-off (would need global indices data)
    # Placeholder — can add later with global indices comparison

    # BULL SIGNALS (weight: 40%)
    # DII high absorption
    if fii_context.get("dii_absorbed") == "High":
        score += 10
        signals.append(f"DII absorption: HIGH (offsetting FII)")

    # Low VIX regime (skip if UNKNOWN)
    if vix_regime == "LOW":
        score += 10
        signals.append(f"VIX regime: LOW (risk-on environment)")

    # DXY falling (dollar weakness)
    if dxy_dir == "FALLING":
        score += 10
        signals.append(f"DXY falling → FII buying opportunity")

    # Normalize to 0-100 scale
    normalized_score = (score + 40) * 1.25  # -40 → 0, +40 → 100

    # Determine label
    if normalized_score >= 65:
        label = "BULLISH"
    elif normalized_score <= 35:
        label = "BEARISH"
    else:
        label = "NEUTRAL"

    # Compute confidence based on signal count and consensus
    active_signal_count = len(signals)
    if active_signal_count >= 4:
        confidence = "HIGH"
    elif active_signal_count >= 2:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"
    
    # Determine dominant factor (biggest single driver)
    dominant_factor = "Insufficient data"
    if signals:
        # Score each signal by magnitude
        signal_weights = {
            "outflow streak": 15,
            "z-score": 15,
            "VIX regime": 10,
            "DXY": 10,
            "absorption": 10,
        }
        max_weight = 0
        for sig in signals:
            for key, weight in signal_weights.items():
                if key in sig.lower() and weight > max_weight:
                    max_weight = weight
                    dominant_factor = sig
            # If no match, take first signal
            if max_weight == 0 and sig:
                dominant_factor = sig

    return {
        "raw_score": score,              # -40 to +40
        "normalized_score": round(normalized_score, 1),  # 0 to 100
        "label": label,
        "signals": signals,
        "key_drivers": signals[:3] if signals else ["Insufficient data"],
        # NEW: Confidence metrics
        "confidence": confidence,
        "active_signal_count": active_signal_count,
        "dominant_factor": dominant_factor,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CROSS-SIGNAL RULE MATRIX — Pre-computed narrative synthesis
# ═══════════════════════════════════════════════════════════════════════════════

def get_market_narrative(fii_context: Dict = None, macro_context: Dict = None, bull_bear: Dict = None) -> str:
    """
    Cross-signal synthesis using rule matrix.
    Returns pre-written narrative based on combination of signals.
    Handles None inputs gracefully.
    """
    # Handle None inputs - return neutral narrative
    if not fii_context or not macro_context:
        return "➡️ *NEUTRAL*: Insufficient data for market narrative. Awaiting more signals."
    
    # Default empty bull_bear if None
    if not bull_bear:
        bull_bear = {"normalized_score": 50, "confidence": "LOW", "label": "NEUTRAL"}
    
    # Extract signal components
    fii_z = fii_context.get("fii_z_score", 0)
    fii_streak = fii_context.get("fii_streak", 0)
    fii_direction = fii_context.get("fii_streak_direction", "neutral")
    dii_absorb = fii_context.get("dii_absorbed", "Low")
    
    vix_regime = macro_context.get("vix_regime", "NORMAL")
    dxy_dir = macro_context.get("dxy", {}).get("direction", "FLAT")
    
    bull_score = bull_bear.get("normalized_score", 50)
    confidence = bull_bear.get("confidence", "LOW")
    dominant = bull_bear.get("dominant_factor", "Insufficient data")
    
    # Rule matrix patterns - key insight combinations
    
    # CRITICAL BEAR CASES
    if fii_z < -1.5 and fii_streak >= 3 and vix_regime == "HIGH":
        return (
            "⚠️ *TRIPLE THREAT BEAR CASE*: FII selling sharply (z={z}), "
            "multi-day streak active, and VIX elevated. Risk-off environment. "
            "DII absorption {dii} but insufficient to offset FII pressure. "
            "Dollar strength (DXY {dxy}) adding headwind. Confidence: {conf}."
        ).format(z=round(fii_z,1), dii=dii_absorb.lower(), dxy=dxy_dir.lower(), conf=confidence)
    
    if fii_z < -1.5 and dxy_dir == "RISING":
        return (
            "📉 *DOLLAR-FII SELL PRESSURE*: Strong FII selling (z={z}) coinciding with "
            "dollar strength. Typically flows reverse when DXY peaks. "
            "VIX {vix}, DII absorption {dii}. Watch for DXY reversal signal. "
            "Confidence: {conf}."
        ).format(z=round(fii_z,1), vix=vix_regime.lower(), dii=dii_absorb.lower(), conf=confidence)
    
    # CRITICAL BULL CASES
    if fii_z > 1.0 and dii_absorb == "High" and vix_regime == "LOW":
        return (
            "🚀 *INSTITUTIONAL ACCUMULATION*: FII buying (z={z}) + strong DII support "
            "in low VIX environment. Rare risk-on alignment. Sustained flow would "
            "confirm structural support. Confidence: {conf}."
        ).format(z=round(fii_z,1), conf=confidence)
    
    if dxy_dir == "FALLING" and dii_absorb == "High":
        return (
            "💰 *DOLLAR TAILWIND*: DXY declining typically triggers FII inflows. "
            "Current DII already absorbing FII outflows. If DXY breaks lower, "
            "expect accelerated inflows. Watch for confirmation. Confidence: {conf}."
        ).format(conf=confidence)
    
    # DXY FLAT + FII SELLING = India-specific event (not global EM)
    if dxy_dir == "FLAT" and (fii_z < -0.5 or fii_direction == "negative"):
        return (
            "🏏 *INDIA-SPECIFIC EVENT*: FII {direction} but DXY FLAT = not global EM outflow. "
            "Dollar not driving this. Local factors (budget, earnings, liquidity) at play. "
            "DII absorption {absorb}%. This is an India-specific signal, "
            "not a global risk-off. Watch domestic catalysts. Confidence: {conf}."
        ).format(
            direction="selling" if fii_z < -0.5 else "net outflow",
            absorb=dii_absorb.lower(),
            conf=confidence
        )
    
    # FII BUYING + VIX HIGH = buy the fear (contrarian)
    if fii_z > 0.5 and vix_regime == "HIGH":
        return (
            "🟢 *BUY THE FEAR*: FII buying (z={z}) amid HIGH VIX ({vix}). "
            "Typically a contrarian bullish signal — smart money buying into fear. "
            "DII absorption {dii}%. This is institutional conviction, not panic. "
            "Historical precedent: such setups often mark near-term bottoms. "
            "Confidence: {conf}."
        ).format(z=round(fii_z,1), vix=vix_regime.lower(), dii=dii_absorb.lower(), conf=confidence)
    
    # DII HIGH ABSORPTION modifies any FII sell
    if dii_absorb == "High" and fii_z < -0.5:
        return (
            "🛡️ *CORRECTION MANAGED*: FII selling (z={z}) but DII absorbing {absorb}%. "
            "Net flows muted. Floor exists. If DII fatigue shows (absorption drops below 40%), "
            "then re-assess. Currently: structural support intact. "
            "Confidence: {conf}."
        ).format(z=round(fii_z,1), absorb=dii_absorb.lower(), conf=confidence)

    # NEUTRAL/MIXED CASES
    if abs(fii_z) < 0.5 and vix_regime == "NORMAL":
        return (
            "➡️ *STATUS QUO*: No strong directional signal. FII/DII balanced, "
            "VIX neutral, DXY flat. Range-bound market likely. "
            "Wait for catalyst. Confidence: {conf}."
        ).format(conf=confidence)
    
    if fii_streak >= 3 and dii_absorb == "High":
        return (
            "⚖️ *DII OFFSET MODE*: FII {direction} streak {streak} days but DII "
            "absorbing {absorb}%. Net effect muted. Watch for streak break "
            "or DII fatigue. Confidence: {conf}."
        ).format(
            direction="selling" if fii_direction == "negative" else "buying",
            streak=fii_streak,
            absorb=dii_absorb.lower(),
            conf=confidence
        )
    
    # DEFAULT - use Bull/Bear score and confidence
    if bull_score >= 65:
        return (
            f"📈 *BULL BIAS*: Score {int(bull_score)}/100 ({bull_bear.get('label', 'NEUTRAL')}). "
            f"Leading: {dominant}. {confidence} confidence in direction."
        )
    elif bull_score <= 35:
        return (
            f"📉 *BEAR BIAS*: Score {int(bull_score)}/100 ({bull_bear.get('label', 'NEUTRAL')}). "
            f"Leading: {dominant}. {confidence} confidence in direction."
        )
    else:
        return (
            f"➡️ *NEUTRAL*: Score {int(bull_score)}/100. Mixed signals, "
            f"no clear regime. Dominant: {dominant}. Low conviction."
        )


def format_context_for_ai(fii_context: Dict, macro_context: Dict, bull_bear: Dict) -> str:
    """
    Pre-format all computed conclusions for AI prompt.
    AI receives scored conclusions only — writes narrative.
    """
    lines = []
    lines.append("📊 *MARKET CONTEXT (Pre-computed)*\n")

    # FII/DII Context
    if fii_context.get("ok"):
        lines.append("┌─ FII/DII Flows ─────────────────────")
        lines.append(f"│ FII: ₹{fii_context.get('fii_net', 0):+.0f}Cr ({fii_context.get('date', '')})")
        lines.append(f"│   vs 4W avg: ₹{fii_context.get('fii_4w_avg', 0):+.0f}Cr")
        lines.append(f"│   z-score: {fii_context.get('fii_z_score', 0):+.2f}")
        lines.append(f"│   streak: {fii_context.get('fii_streak', 0)} days ({fii_context.get('fii_streak_direction', 'N/A')})")
        lines.append(f"│ DII: ₹{fii_context.get('dii_net', 0):+.0f}Cr | Absorption: {fii_context.get('dii_absorbed', 'N/A')}")
        lines.append(f"│ Net: ₹{fii_context.get('net', 0):+.0f}Cr")

    # Macro Context
    if macro_context.get("vix_price"):
        lines.append("┌─ Macro Anchors ─────────────────────")
        lines.append(f"│ VIX: {macro_context.get('vix_price', 'N/A')} ({macro_context.get('vix_regime', 'N/A')})")
        dxy = macro_context.get("dxy", {})
        lines.append(f"│ DXY: {dxy.get('direction', 'N/A')} | {dxy.get('implication', '')}")
        usd = macro_context.get("usd_inr", {})
        if usd.get("price"):
            lines.append(f"│ USD/INR: ₹{usd.get('price', 'N/A')} ({usd.get('change_pct', 0):+.2f}%)")

    # Bull/Bear Score
    if bull_bear:
        lines.append("┌─ Bull/Bear Score ───────────────────")
        lines.append(f"│ Score: {bull_bear.get('normalized_score', 'N/A')}/100 ({bull_bear.get('label', 'N/A')})")
        lines.append(f"│ Confidence: {bull_bear.get('confidence', 'N/A')} ({bull_bear.get('active_signal_count', 0)} signals)")
        lines.append(f"│ Dominant: {bull_bear.get('dominant_factor', 'N/A')}")
        lines.append(f"│ Key: {' | '.join(bull_bear.get('key_drivers', ['N/A']))}")
    
    # Cross-signal narrative
    if fii_context.get("ok") and macro_context:
        narrative = get_market_narrative(fii_context, macro_context, bull_bear)
        lines.append("┌─ Market Narrative ──────────────────")
        lines.append(f"│ {narrative}")

    lines.append("└" + "─" * 35)
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN: Run all contextualization for a job execution
# ═══════════════════════════════════════════════════════════════════════════════

def run_contextualization(anchor_data: List[Dict]) -> Dict:
    """
    Full contextualization pipeline — runs inside single job execution.
    Returns all computed context for prompt injection.
    """
    # Get FII/DII context from DB
    fii_context = get_fii_dii_context(days=30)

    # Get macro context (VIX, DXY) from fetched anchors
    macro_context = get_macro_context(anchor_data)

    # Compute Bull/Bear score
    bull_bear = compute_bull_bear_score(fii_context, macro_context)

    return {
        "fii_context": fii_context,
        "macro_context": macro_context,
        "bull_bear": bull_bear,
    }


if __name__ == "__main__":
    # Test
    print("Testing context engine...")
    # Would need actual anchor_data to test fully
    print("Context engine loaded successfully.")