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


def get_macro_context(anchor_data: List[Dict] = None) -> Dict:
    """
    Extract VIX regime and DXY signal from anchor data.
    """
    if anchor_data is None:
        anchor_data = []
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

def compute_bull_bear_score(fii_context: Dict, macro_context: Dict,
                             extra_signals: Dict = None,
                             anchor_data: List[Dict] = None) -> Dict:
    """
    Compute weighted Bull/Bear composite score (-55 to +55 range).
    All computed in Python — zero API calls.

    extra_signals: optional dict with additional signal inputs:
        - breadth_ratio: float (A/D ratio, >1 = more advances)
        - nifty_vs_ma200_pct: float (% above/below 200-DMA)
        - pcr: float (put-call ratio)
        - fii_fno_net: float (FII F&O net position, positive = long)
        - carry_trade_regime: str (CARRY-ON, CARRY-STRESS, etc.)
        - recession_level: str (LOW, ELEVATED, HIGH)
        - commodity_regime: str (REFLATION, FLIGHT TO SAFETY, etc.)
        - stagflation_regime: str (STAGFLATION RISK, FLIGHT TO SAFETY, etc.)
        - liquidity_regime: str (MELT-UP, LIQUIDITY DRIVEN, etc.)
    """
    score = 0
    signals = []
    extra = extra_signals or {}

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

    # Market breadth bearish (weak breadth)
    breadth = extra.get("breadth_ratio")
    if breadth is not None and breadth < 0.7:
        score -= 5
        signals.append(f"Weak breadth: A/D ratio {breadth:.2f}")

    # Nifty below 200-DMA (bearish trend)
    ma200_dist = extra.get("nifty_vs_ma200_pct")
    if ma200_dist is not None and ma200_dist < -3:
        score -= 5
        signals.append(f"Nifty {abs(ma200_dist):.1f}% below 200-DMA (bearish trend)")

    # PCR > 1.3 (contrarian bear — call building)
    pcr = extra.get("pcr")
    if pcr is not None and pcr > 1.3:
        score -= 5
        signals.append(f"PCR {pcr:.2f} — CALL building (resistance)")

    # FII net short in F&O
    fii_fno = extra.get("fii_fno_net")
    if fii_fno is not None and fii_fno < -50000:
        score -= 5
        signals.append(f"FII F&O net short: {fii_fno:+,.0f}")

    # Phase 8: Carry trade stress (from extra_signals or computed)
    carry_regime = extra.get("carry_trade_regime")
    if carry_regime == "CARRY-STRESS":
        score -= 10
        signals.append("Carry trade STRESSED — JPY strengthening, EM outflow risk")
    elif carry_regime == "CARRY-ON":
        score += 5
        signals.append("Carry trade ON — JPY weakening, EM inflows favorable")

    # Phase 8: Recession proxy
    recession_level = extra.get("recession_level")
    if recession_level == "HIGH":
        score -= 5
        signals.append("Recession risk HIGH — Copper/Gold + curve inversion")
    elif recession_level == "LOW":
        score += 3
        signals.append("Recession risk LOW — growth healthy")

    # Phase 8: Commodity reflation
    commodity_regime = extra.get("commodity_regime")
    if commodity_regime == "REFLATION":
        score += 5
        signals.append("Commodity reflation — Copper up, Gold down (bullish EM)")
    elif commodity_regime == "FLIGHT TO SAFETY":
        score -= 5
        signals.append("Flight to safety — Gold up, Copper down (bearish)")

    # Phase 9: Stagflation regime (worst outcome for equities)
    stagflation_regime = extra.get("stagflation_regime")
    if stagflation_regime == "STAGFLATION RISK":
        score -= 10
        signals.append("STAGFLATION — rising inflation + slowing growth (worst regime)")
    elif stagflation_regime == "INFLATIONARY PRESSURE":
        score -= 5
        signals.append("Inflationary pressure — Gold + Oil rising with elevated CPI")

    # Phase 9: Liquidity regime
    liquidity_regime = extra.get("liquidity_regime")
    if liquidity_regime == "MELT-UP":
        score -= 5
        signals.append("MELT-UP — everything rising together (late cycle, crash risk)")
    elif liquidity_regime == "LIQUIDITY DRIVEN":
        score += 5
        signals.append("Liquidity driven — central bank liquidity lifting all assets")
    elif liquidity_regime == "LIQUIDITY TIGHTENING":
        score -= 5
        signals.append("Liquidity tightening — rising yields + strong dollar")

    # Institutional signal (SWF/pension fund activity)
    inst_regime = extra.get("inst_regime")
    if inst_regime == "STRONG ACCUMULATION":
        score += 5
        signals.append("Institutional STRONG ACCUMULATION — SWFs actively buying")
    elif inst_regime == "ACCUMULATION":
        score += 3
        signals.append("Institutional accumulation — SWFs net buyers")
    elif inst_regime == "STRONG DISTRIBUTION":
        score -= 5
        signals.append("Institutional STRONG DISTRIBUTION — SWFs actively selling")
    elif inst_regime == "DISTRIBUTION":
        score -= 3
        signals.append("Institutional distribution — SWFs net sellers")

    # US Employment recession signal
    us_recession = extra.get("us_recession_level")
    if us_recession == "HIGH":
        score -= 10
        signals.append("US employment recession signal HIGH — unemployment rising + NFP slowing")
    elif us_recession == "ELEVATED":
        score -= 5
        signals.append("US employment recession signal ELEVATED — labor market weakening")
    elif us_recession == "LOW":
        score += 3
        signals.append("US employment healthy — tight labor market")

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

    # Market breadth bullish (strong breadth)
    if breadth is not None and breadth > 1.5:
        score += 5
        signals.append(f"Strong breadth: A/D ratio {breadth:.2f}")

    # Nifty above 200-DMA (bullish trend)
    if ma200_dist is not None and ma200_dist > 3:
        score += 5
        signals.append(f"Nifty {ma200_dist:.1f}% above 200-DMA (bullish trend)")

    # PCR < 0.7 (contrarian bull — put building / support)
    if pcr is not None and pcr < 0.7:
        score += 5
        signals.append(f"PCR {pcr:.2f} — PUT building (support)")

    # FII net long in F&O
    if fii_fno is not None and fii_fno > 50000:
        score += 5
        signals.append(f"FII F&O net long: {fii_fno:+,.0f}")

    # Normalize to 0-100 scale (expanded range: -55 to +55 with new signals)
    normalized_score = (score + 55) * (100 / 110)  # -55 → 0, +55 → 100

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


def format_context_for_ai(fii_context: Dict, macro_context: Dict, bull_bear: Dict,
                           extra_signals: Dict = None) -> str:
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

    # Extra signals (breadth, 200-DMA, PCR, F&O)
    if extra_signals:
        parts = []
        if "breadth_ratio" in extra_signals:
            parts.append(f"A/D: {extra_signals['breadth_ratio']:.2f}")
        if "nifty_vs_ma200_pct" in extra_signals:
            d = extra_signals["nifty_vs_ma200_pct"]
            parts.append(f"vs 200-DMA: {d:+.1f}%")
        if "pcr" in extra_signals:
            parts.append(f"PCR: {extra_signals['pcr']:.2f}")
        if "fii_fno_net" in extra_signals:
            parts.append(f"FII F&O: {extra_signals['fii_fno_net']:+,.0f}")
        if parts:
            lines.append("┌─ Technical/Positioning ──────────────")
            lines.append(f"│ {' | '.join(parts)}")
    
    # Cross-signal narrative
    if fii_context.get("ok") and macro_context:
        narrative = get_market_narrative(fii_context, macro_context, bull_bear)
        lines.append("┌─ Market Narrative ──────────────────")
        lines.append(f"│ {narrative}")

    lines.append("└" + "─" * 35)
    return "\n".join(lines)


def format_context_for_ai_full(ctx: Dict) -> str:
    """
    Format full context including global risk, yield spread, momentum.
    Called from formatters.py with the complete run_contextualization output.
    """
    base = format_context_for_ai(
        ctx.get("fii_context", {}),
        ctx.get("macro_context", {}),
        ctx.get("bull_bear", {}),
        extra_signals=ctx.get("extra_signals"),
    )

    lines = [base]

    # Global Risk Composite
    gr = ctx.get("global_risk", {})
    if gr.get("ok"):
        lines.append(f"┌─ Global Risk ──────────────────────")
        lines.append(f"│ {gr['composite']} (score: {gr['score']:+d})")
        for sig in gr.get("signals", []):
            lines.append(f"│ • {sig}")

    # VIX Spread
    vs = ctx.get("vix_spread", {})
    if vs.get("ok"):
        lines.append(f"┌─ VIX Spread ───────────────────────")
        lines.append(f"│ CBOE: {vs['cboe_vix']:.1f} | India: {vs['india_vix']:.1f} | Spread: {vs['spread']:+.1f}")
        lines.append(f"│ {vs['label']}")

    # Credit Stress
    cs = ctx.get("credit_stress", {})
    if cs.get("ok"):
        lines.append(f"┌─ Credit Stress ────────────────────")
        lines.append(f"│ HYG: ${cs['hyg_price']:.2f} ({cs['hyg_weekly_change']:+.1f}% weekly) → {cs['level']}")

    # Yield Spread
    ys = ctx.get("yield_spread", {})
    if ys.get("ok"):
        lines.append(f"┌─ Yield Spread ─────────────────────")
        lines.append(f"│ India-US: {ys['spread']:+.2f}% (US10Y: {ys['us_10y']:.2f}%)")
        lines.append(f"│ {ys['label']}")

    # India Structural
    ind = ctx.get("india_structural", {})
    if ind.get("ok"):
        rr = ind.get("real_rate", {})
        if rr.get("ok"):
            lines.append(f"┌─ India Structural ─────────────────")
            lines.append(f"│ Real Rate: {rr['real_rate']:+.2f}% (repo {rr['repo_rate']}% - CPI {rr['cpi']}%)")
            lines.append(f"│ Oil+INR: {ind['oil_inr_signal']}")
            sc = ind.get("smallcap_ratio", {})
            if sc.get("ok"):
                lines.append(f"│ Smallcap/Largecap: {sc['ratio']:.3f} — {sc['label']}")

    # Momentum Regime
    mom = ctx.get("momentum", {})
    if mom.get("ok"):
        lines.append(f"┌─ Momentum (12M) ───────────────────")
        lines.append(f"│ 12M Return: {mom['momentum_12m']:+.1f}% → {mom['regime']}")

    # Phase 8: Institutional signals
    carry = ctx.get("carry_trade", {})
    if carry.get("ok"):
        lines.append(f"┌─ Carry Trade Signal ───────────────")
        lines.append(f"│ {carry['regime']} — {carry['label']}")
        lines.append(f"│ JPY: {carry['jpy_price']:.2f} ({carry['jpy_change']:+.2f}%)")
        for sig in carry.get("signals", []):
            lines.append(f"│ • {sig}")

    cr = ctx.get("currency_regime", {})
    if cr.get("ok"):
        lines.append(f"┌─ Currency Regime ──────────────────")
        lines.append(f"│ DXY {cr['dollar_direction']} ({cr['dxy_change']:+.2f}%) — {cr['driver']}-driven")
        lines.append(f"│ EM Impact: {cr['em_impact']}")
        for sig in cr.get("signals", []):
            lines.append(f"│ • {sig}")

    rec = ctx.get("recession_proxy", {})
    if rec.get("ok"):
        lines.append(f"┌─ Recession Proxy ──────────────────")
        lines.append(f"│ Risk: {rec['level']} — {rec['label']}")
        if rec.get("copper_gold_ratio"):
            lines.append(f"│ Copper/Gold: {rec['copper_gold_ratio']:.5f}")
        if rec.get("term_spread") is not None:
            lines.append(f"│ Term Spread: {rec['term_spread']:+.2f}%")
        for sig in rec.get("signals", []):
            lines.append(f"│ • {sig}")

    cb = ctx.get("commodity_breadth", {})
    if cb.get("ok"):
        lines.append(f"┌─ Commodity Breadth ────────────────")
        lines.append(f"│ Regime: {cb['regime']}")
        lines.append(f"│ Inflation: {cb['inflation_signal']}")
        for sig in cb.get("signals", []):
            lines.append(f"│ • {sig}")

    rrd = ctx.get("real_rate_diff", {})
    if rrd.get("ok"):
        lines.append(f"┌─ Real Rate Differential ───────────")
        lines.append(f"│ India: {rrd['india_real_rate']:+.2f}% | US: {rrd['us_real_rate']:+.2f}%")
        lines.append(f"│ Differential: {rrd['differential']:+.2f}% — {rrd['label']}")

    cr_idx = ctx.get("carry_risk", {})
    if cr_idx.get("ok"):
        lines.append(f"┌─ Carry Risk Index ─────────────────")
        lines.append(f"│ Index: {cr_idx['index']}/100 → {cr_idx['regime']}")

    # Phase 9: Regime detection signals
    ath = ctx.get("ath_regime", {})
    if ath.get("ok"):
        lines.append(f"┌─ ATH Regime ───────────────────────")
        lines.append(f"│ {ath['regime']} — {ath['label']}")
        if ath.get("strong_assets"):
            lines.append(f"│ Near ATH: {', '.join(ath['strong_assets'])}")

    stag = ctx.get("stagflation", {})
    if stag.get("ok"):
        lines.append(f"┌─ Stagflation Signal ───────────────")
        lines.append(f"│ {stag['regime']} — {stag['label']}")
        for sig in stag.get("signals", []):
            lines.append(f"│ • {sig}")

    war = ctx.get("war_premium", {})
    if war.get("ok"):
        lines.append(f"┌─ War Premium (Oil) ────────────────")
        lines.append(f"│ Brent ${war['brent']:.0f} vs baseline ${war['baseline']:.0f} = +{war['premium_pct']:.0f}% premium")
        lines.append(f"│ Level: {war['level']} — {war['label']}")

    liq = ctx.get("liquidity_regime", {})
    if liq.get("ok"):
        lines.append(f"┌─ Liquidity Regime ─────────────────")
        lines.append(f"│ {liq['regime']} — {liq['label']}")
        for sig in liq.get("signals", []):
            lines.append(f"│ • {sig}")

    gd = ctx.get("gold_dollar", {})
    if gd.get("ok"):
        lines.append(f"┌─ Gold vs Dollar ───────────────────")
        lines.append(f"│ {gd['regime']} — {gd['label']}")
        lines.append(f"│ India Impact: {gd['india_impact']}")

    inst = ctx.get("inst_context", {})
    if inst.get("ok"):
        lines.append(f"┌─ Institutional Signal ─────────────")
        lines.append(f"│ {inst['regime']} (score: {inst['score']:+d})")
        for s in inst.get("signals", []):
            lines.append(f"│ • {s}")

    emp = ctx.get("us_employment", {})
    if emp.get("ok"):
        lines.append(f"┌─ US Employment (BLS) ──────────────")
        lines.append(f"│ Recession risk: {emp.get('recession_level', '?')} (score: {emp.get('recession_score', 0)}/10)")
        for s in emp.get("signals", []):
            lines.append(f"│ • {s}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# MOMENTUM REGIME: 12-month trend filter
# ═══════════════════════════════════════════════════════════════════════════════

def compute_momentum_regime(nifty_closes: list) -> Dict:
    """
    12-month (252 trading days) momentum regime filter.
    Positive return = bull regime, Negative = bear regime.
    The most robust and simplest regime filter in quantitative finance.
    """
    if not nifty_closes or len(nifty_closes) < 252:
        return {"ok": False, "message": f"Need 252 days, have {len(nifty_closes) if nifty_closes else 0}"}

    current = nifty_closes[-1]
    year_ago = nifty_closes[-252]
    momentum = (current / year_ago - 1) * 100

    if momentum > 15:
        regime = "STRONG BULL"
    elif momentum > 5:
        regime = "BULL"
    elif momentum > -5:
        regime = "NEUTRAL"
    elif momentum > -15:
        regime = "BEAR"
    else:
        regime = "STRONG BEAR"

    return {
        "ok": True,
        "momentum_12m": round(momentum, 2),
        "regime": regime,
        "current": round(current, 2),
        "year_ago": round(year_ago, 2),
    }


def compute_yield_spread(anchor_data: list) -> Dict:
    """
    Compute India-US yield spread from macro anchors.
    Spread = India G-Sec yield - US 10Y yield
    Widening spread = FII inflow incentive
    Narrowing spread = FII outflow risk
    """
    if not anchor_data:
        return {"ok": False}

    us_10y = None
    for a in anchor_data:
        if a.get("name") == "US 10Y Yield" and a.get("ok"):
            us_10y = a["price"]
            break

    if us_10y is None:
        return {"ok": False, "message": "US 10Y not available"}

    # India G-Sec approximate (use typical value or try to fetch)
    india_gsec = 7.1  # Approximate — will be replaced with live data when available

    spread = round(india_gsec - us_10y, 2)

    if spread > 3.5:
        label = "WIDE spread — strong FII carry trade incentive"
    elif spread > 2.5:
        label = "NORMAL spread"
    elif spread > 1.5:
        label = "NARROWING — FII outflow risk"
    else:
        label = "TIGHT — FII outflows likely"

    return {
        "ok": True,
        "spread": spread,
        "us_10y": us_10y,
        "india_gsec": india_gsec,
        "label": label,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL RISK SIGNALS — Multipolar World Framework
# ═══════════════════════════════════════════════════════════════════════════════

def compute_vix_spread(anchor_data: List[Dict]) -> Dict:
    """
    CBOE VIX vs India VIX spread.
    Positive spread (CBOE > India) = global fear > local fear → FII selling risk
    Negative spread (India > CBOE) = local event risk (elections, RBI, geopolitics)
    """
    if not anchor_data:
        return {"ok": False}

    cboe_vix = None
    india_vix = None

    for a in anchor_data:
        if a.get("name") == "CBOE VIX" and a.get("ok"):
            cboe_vix = a["price"]
        elif a.get("name") == "India VIX" and a.get("ok"):
            india_vix = a["price"]

    if cboe_vix is None or india_vix is None:
        return {"ok": False}

    spread = round(cboe_vix - india_vix, 2)

    if spread > 5:
        label = "GLOBAL FEAR DOMINANT — FII selling risk high"
    elif spread > 2:
        label = "ELEVATED GLOBAL FEAR"
    elif spread > -2:
        label = "BALANCED — local and global fear aligned"
    elif spread > -5:
        label = "LOCAL FEAR DOMINANT — event-driven risk"
    else:
        label = "EXTREME LOCAL FEAR — domestic crisis signal"

    return {
        "ok": True,
        "cboe_vix": cboe_vix,
        "india_vix": india_vix,
        "spread": spread,
        "label": label,
    }


def compute_credit_stress(anchor_data: List[Dict]) -> Dict:
    """
    US High Yield ETF (HYG) as credit stress indicator.
    HYG falling = credit spreads widening = liquidity stress → EM outflows.
    """
    if not anchor_data:
        return {"ok": False}

    hyg = None
    hyg_weekly = None

    for a in anchor_data:
        if a.get("name") == "US High Yield" and a.get("ok"):
            hyg = a["price"]
            hyg_weekly = a.get("weekly_change_pct")

    if hyg is None:
        return {"ok": False}

    weekly_change = hyg_weekly or 0

    if weekly_change < -5:
        label = "CREDIT CRISIS — severe stress, expect EM outflows"
        level = "CRISIS"
    elif weekly_change < -2:
        label = "CREDIT STRESS RISING — risk-off spreading"
        level = "STRESS"
    elif weekly_change < -1:
        label = "MILD CREDIT WEAKNESS"
        level = "MILD"
    elif weekly_change < 1:
        label = "STABLE credit conditions"
        level = "STABLE"
    else:
        label = "CREDIT RISK-ON — spreads tightening"
        level = "RISK_ON"

    return {
        "ok": True,
        "hyg_price": hyg,
        "hyg_weekly_change": weekly_change,
        "level": level,
        "label": label,
    }


def compute_global_risk_composite(anchor_data: List[Dict]) -> Dict:
    """
    Combine CBOE VIX, S&P 500 trend, HYG credit stress, DXY into
    a single GLOBAL RISK-ON / RISK-OFF / MIXED signal.
    """
    if not anchor_data:
        return {"ok": False}

    signals = []
    score = 0  # Positive = risk-on, negative = risk-off

    # CBOE VIX
    for a in anchor_data:
        if a.get("name") == "CBOE VIX" and a.get("ok"):
            vix = a["price"]
            if vix > 25:
                score -= 2
                signals.append(f"CBOE VIX {vix:.0f} (HIGH FEAR)")
            elif vix > 20:
                score -= 1
                signals.append(f"CBOE VIX {vix:.0f} (elevated)")
            elif vix < 15:
                score += 1
                signals.append(f"CBOE VIX {vix:.0f} (complacent)")
            else:
                signals.append(f"CBOE VIX {vix:.0f} (normal)")

    # S&P 500 (from global indices, not in anchor_data — use DXY as proxy)
    for a in anchor_data:
        if a.get("name") == "Dollar Index" and a.get("ok"):
            dxy_chg = a.get("change_pct", 0) or 0
            if dxy_chg > 1:
                score -= 1
                signals.append(f"DXY +{dxy_chg:.1f}% (dollar strength = EM headwind)")
            elif dxy_chg < -1:
                score += 1
                signals.append(f"DXY {dxy_chg:.1f}% (dollar weakness = EM tailwind)")

    # HYG credit stress
    credit = compute_credit_stress(anchor_data)
    if credit.get("ok"):
        if credit["level"] == "CRISIS":
            score -= 2
        elif credit["level"] == "STRESS":
            score -= 1
        elif credit["level"] == "RISK_ON":
            score += 1
        signals.append(f"HYG {credit['hyg_weekly_change']:+.1f}% ({credit['level']})")

    # Composite
    if score >= 2:
        composite = "GLOBAL RISK-ON"
    elif score >= 1:
        composite = "MILDLY RISK-ON"
    elif score <= -2:
        composite = "GLOBAL RISK-OFF"
    elif score <= -1:
        composite = "MILDLY RISK-OFF"
    else:
        composite = "MIXED"

    return {
        "ok": True,
        "score": score,
        "composite": composite,
        "signals": signals,
    }


def compute_india_structural(anchor_data: List[Dict]) -> Dict:
    """
    India domestic structural indicators:
    - Real rate (repo - CPI)
    - Oil impact (Brent + INR)
    - Credit conditions proxy
    """
    if not anchor_data:
        return {"ok": False}

    # Real rate (from macro_fetcher)
    from src.macro_fetcher import compute_real_rate
    real = compute_real_rate()

    # Oil + INR composite
    brent = None
    inr = None
    for a in anchor_data:
        if a.get("name") == "Brent Crude" and a.get("ok"):
            brent = a["price"]
        elif a.get("name") == "USD/INR" and a.get("ok"):
            inr = a["price"]

    oil_inr_signal = "NEUTRAL"
    if brent and inr:
        if brent > 90 and inr > 85:
            oil_inr_signal = "STRESS — high oil + weak INR = current account risk"
        elif brent > 80 and inr > 83:
            oil_inr_signal = "ELEVATED — watch for INR defense by RBI"
        elif brent < 70:
            oil_inr_signal = "FAVORABLE — low oil supports INR and inflation"

    # Smallcap/Largecap ratio (risk appetite)
    smallcap = {"ok": False}
    try:
        from src.data_fetcher import fetch_smallcap_ratio
        smallcap = fetch_smallcap_ratio()
    except Exception:
        pass

    return {
        "ok": True,
        "real_rate": real,
        "brent": brent,
        "inr": inr,
        "oil_inr_signal": oil_inr_signal,
        "smallcap_ratio": smallcap,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# INSTITUTIONAL MACRO SIGNALS — Phase 8: Pension/SWF-grade intelligence
# ═══════════════════════════════════════════════════════════════════════════════

def compute_carry_trade_signal(anchor_data: List[Dict]) -> Dict:
    """
    Carry trade signal — THE plumbing of global EM capital flows.
    JPY (USD/JPY) is the funding currency. When JPY strengthens (USD/JPY falls),
    carry trades unwind = EM outflows. When JPY weakens = carry expanding = EM inflows.

    Also checks BOJ intervention risk (USD/JPY > 155).
    """
    if not anchor_data:
        return {"ok": False}

    jpy = None
    jpy_change = None
    us_10y = None
    india_vix = None
    dxy_change = None

    for a in anchor_data:
        if a.get("name") == "USD/JPY" and a.get("ok"):
            jpy = a["price"]
            jpy_change = a.get("change_pct", 0) or 0
        elif a.get("name") == "US 10Y Yield" and a.get("ok"):
            us_10y = a["price"]
        elif a.get("name") == "India VIX" and a.get("ok"):
            india_vix = a["price"]
        elif a.get("name") == "Dollar Index" and a.get("ok"):
            dxy_change = a.get("change_pct", 0) or 0

    if jpy is None:
        return {"ok": False, "message": "USD/JPY data unavailable"}

    signals = []
    score = 0  # Positive = carry-on, negative = carry-stress

    # JPY direction (USD/JPY falling = JPY strengthening = carry stress)
    if jpy_change < -0.5:
        score -= 2
        signals.append(f"JPY strengthening ({jpy_change:+.2f}%) — carry unwind risk")
    elif jpy_change < -0.2:
        score -= 1
        signals.append(f"JPY slightly stronger ({jpy_change:+.2f}%)")
    elif jpy_change > 0.5:
        score += 2
        signals.append(f"JPY weakening ({jpy_change:+.2f}%) — carry expanding")
    elif jpy_change > 0.2:
        score += 1
        signals.append(f"JPY slightly weaker ({jpy_change:+.2f}%)")

    # BOJ intervention risk
    if jpy > 155:
        score -= 1
        signals.append(f"USD/JPY {jpy:.1f} — BOJ intervention risk zone (>155)")
    elif jpy > 150:
        signals.append(f"USD/JPY {jpy:.1f} — elevated but below intervention threshold")

    # Yield spread context (wider = more carry incentive)
    ys = compute_yield_spread(anchor_data)
    if ys.get("ok"):
        spread = ys["spread"]
        if spread > 3.5:
            score += 1
            signals.append(f"Yield spread {spread:.1f}% — wide (carry attractive)")
        elif spread < 2.0:
            score -= 1
            signals.append(f"Yield spread {spread:.1f}% — narrow (carry unattractive)")

    # VIX impact on carry appetite
    if india_vix and india_vix > 20:
        score -= 1
        signals.append(f"VIX {india_vix:.1f} — high vol reduces carry appetite")

    # Composite
    if score >= 2:
        regime = "CARRY-ON"
        label = "Carry trade expanding — favorable for EM inflows"
    elif score >= 1:
        regime = "MILDLY CARRY-ON"
        label = "Carry trade conditions mildly favorable"
    elif score <= -2:
        regime = "CARRY-STRESS"
        label = "Carry trade under stress — EM outflow risk"
    elif score <= -1:
        regime = "MILDLY CARRY-OFF"
        label = "Carry conditions tightening"
    else:
        regime = "NEUTRAL"
        label = "Carry trade neutral — no directional signal"

    return {
        "ok": True,
        "regime": regime,
        "score": score,
        "label": label,
        "jpy_price": jpy,
        "jpy_change": jpy_change,
        "signals": signals,
    }


def compute_currency_regime(anchor_data: List[Dict]) -> Dict:
    """
    Decompose DXY movement into EUR vs JPY drivers.
    DXY is 57% EUR, 14% JPY — understanding the driver matters:
    - EUR-driven dollar strength = ECB dovishness (less bearish for EM)
    - JPY-driven dollar strength = carry unwind (more dangerous for EM)
    - Broad dollar weakness = strongest EM tailwind
    """
    if not anchor_data:
        return {"ok": False}

    dxy = None
    dxy_change = None
    eur = None
    eur_change = None
    jpy = None
    jpy_change = None

    for a in anchor_data:
        name = a.get("name", "")
        if name == "Dollar Index" and a.get("ok"):
            dxy = a["price"]
            dxy_change = a.get("change_pct", 0) or 0
        elif name == "EUR/USD" and a.get("ok"):
            eur = a["price"]
            eur_change = a.get("change_pct", 0) or 0
        elif name == "USD/JPY" and a.get("ok"):
            jpy = a["price"]
            jpy_change = a.get("change_pct", 0) or 0

    if dxy is None:
        return {"ok": False, "message": "DXY data unavailable"}

    signals = []

    # Determine dollar direction
    if dxy_change > 0.3:
        dollar_dir = "RISING"
    elif dxy_change < -0.3:
        dollar_dir = "FALLING"
    else:
        dollar_dir = "FLAT"

    # Decompose driver
    eur_driver = abs(eur_change or 0) > 0.3
    jpy_driver = abs(jpy_change or 0) > 0.3

    if dollar_dir == "RISING":
        if eur_change is not None and eur_change < -0.3:
            driver = "EUR-DRIVEN"
            signals.append(f"EUR weakness ({eur_change:+.2f}%) driving DXY up — ECB dovishness")
            em_impact = "MODERATE BEARISH — EUR-driven, not EM-specific"
        elif jpy_change is not None and jpy_change > 0.3:
            driver = "JPY-DRIVEN"
            signals.append(f"JPY weakness ({jpy_change:+.2f}%) driving DXY — carry expansion")
            em_impact = "MILDLY BULLISH — JPY weakening = carry friendly"
        else:
            driver = "BROAD"
            signals.append("Broad dollar strength")
            em_impact = "BEARISH — broad dollar strength = EM headwind"
    elif dollar_dir == "FALLING":
        if eur_change is not None and eur_change > 0.3:
            driver = "EUR-DRIVEN"
            signals.append(f"EUR strength ({eur_change:+.2f}%) driving DXY down")
            em_impact = "BULLISH — dollar weakness = EM tailwind"
        elif jpy_change is not None and jpy_change < -0.3:
            driver = "JPY-DRIVEN"
            signals.append(f"JPY strength ({jpy_change:+.2f}%) driving DXY down — carry stress")
            em_impact = "BEARISH — JPY strength = carry unwind despite DXY falling"
        else:
            driver = "BROAD"
            signals.append("Broad dollar weakness")
            em_impact = "BULLISH — broad dollar weakness = strong EM tailwind"
    else:
        driver = "NONE"
        signals.append("Dollar flat — no directional signal")
        em_impact = "NEUTRAL"

    # Multipolar shift detection
    if eur_change is not None and jpy_change is not None:
        if eur_change > 0.3 and jpy_change < -0.3:
            signals.append("EUR up + JPY down = mixed (EUR strength, carry tightening)")
        elif eur_change > 0.3 and jpy_change > 0.3:
            signals.append("EUR + JPY both up = broad dollar weakness (multipolar shift signal)")

    return {
        "ok": True,
        "dxy": dxy,
        "dxy_change": dxy_change,
        "eur": eur,
        "eur_change": eur_change,
        "jpy": jpy,
        "jpy_change": jpy_change,
        "dollar_direction": dollar_dir,
        "driver": driver,
        "em_impact": em_impact,
        "signals": signals,
    }


def compute_recession_proxy(anchor_data: List[Dict]) -> Dict:
    """
    Recession probability proxy using Copper/Gold ratio and term structure.
    - Copper/Gold ratio falling = growth slowing, flight to safety
    - Copper/Gold ratio rising = reflation, risk-on
    - Term structure (10Y - 2Y) < 0 = yield curve inversion = recession signal
    """
    if not anchor_data:
        return {"ok": False}

    copper = None
    gold = None
    us_10y = None
    us_2y = None

    for a in anchor_data:
        name = a.get("name", "")
        if name == "Copper" and a.get("ok"):
            copper = a["price"]
        elif name == "Gold" and a.get("ok"):
            gold = a["price"]
        elif name == "US 10Y Yield" and a.get("ok"):
            us_10y = a["price"]
        elif name == "US 2Y Yield" and a.get("ok"):
            us_2y = a["price"]

    signals = []
    score = 0  # Positive = growth, negative = recession risk

    # Copper/Gold ratio
    if copper and gold and gold > 0:
        cg_ratio = round(copper / gold, 6)
        # Historical context: ratio typically 0.0015-0.0025
        # Below 0.0012 = recession territory
        # Above 0.0020 = reflation
        if cg_ratio < 0.0012:
            score -= 2
            signals.append(f"Copper/Gold {cg_ratio:.5f} — recession territory (< 0.0012)")
        elif cg_ratio < 0.0015:
            score -= 1
            signals.append(f"Copper/Gold {cg_ratio:.5f} — growth slowing")
        elif cg_ratio > 0.0020:
            score += 2
            signals.append(f"Copper/Gold {cg_ratio:.5f} — reflation (bullish for EM)")
        elif cg_ratio > 0.0017:
            score += 1
            signals.append(f"Copper/Gold {cg_ratio:.5f} — healthy growth")
        else:
            signals.append(f"Copper/Gold {cg_ratio:.5f} — neutral")
    else:
        cg_ratio = None

    # Term structure (10Y - 2Y)
    term_spread = None
    if us_10y is not None and us_2y is not None:
        term_spread = round(us_10y - us_2y, 2)
        if term_spread < 0:
            score -= 2
            signals.append(f"Yield curve INVERTED ({term_spread:+.2f}%) — recession signal (6-12M lead)")
        elif term_spread < 0.5:
            score -= 1
            signals.append(f"Yield curve flat ({term_spread:+.2f}%) — growth slowing")
        elif term_spread > 1.5:
            score += 1
            signals.append(f"Yield curve steep ({term_spread:+.2f}%) — growth expectations healthy")

    # Composite
    if score <= -3:
        level = "HIGH"
        label = "Recession risk ELEVATED — defensive positioning warranted"
    elif score <= -1:
        level = "ELEVATED"
        label = "Growth slowing — monitor closely"
    elif score >= 2:
        level = "LOW"
        label = "Growth healthy — risk-on environment"
    else:
        level = "NORMAL"
        label = "No clear recession signal"

    return {
        "ok": True,
        "copper_gold_ratio": cg_ratio,
        "term_spread": term_spread,
        "score": score,
        "level": level,
        "label": label,
        "signals": signals,
    }


def compute_commodity_breadth(anchor_data: List[Dict]) -> Dict:
    """
    Commodity breadth — what are commodities telling us about global growth and inflation?
    - All rising = inflationary risk-on
    - Gold up + Copper down = flight to safety (recession signal)
    - Oil up + Gold down = growth-driven demand (healthy)
    - Copper up + Gold down = reflation (bullish for EM)
    """
    if not anchor_data:
        return {"ok": False}

    commodities = {}
    for a in anchor_data:
        name = a.get("name", "")
        if name in ("Gold", "Silver", "Brent Crude", "WTI Crude", "Copper") and a.get("ok"):
            commodities[name] = {
                "price": a["price"],
                "change": a.get("change_pct", 0) or 0,
            }

    if len(commodities) < 3:
        return {"ok": False, "message": "Insufficient commodity data"}

    signals = []
    up_count = sum(1 for c in commodities.values() if c["change"] > 0.1)
    down_count = sum(1 for c in commodities.values() if c["change"] < -0.1)

    # Gold vs Copper divergence (most important signal)
    gold_chg = commodities.get("Gold", {}).get("change", 0)
    copper_chg = commodities.get("Copper", {}).get("change", 0)
    oil_chg = commodities.get("Brent Crude", {}).get("change", 0)

    if gold_chg > 0.5 and copper_chg < -0.5:
        regime = "FLIGHT TO SAFETY"
        signals.append(f"Gold up ({gold_chg:+.1f}%) + Copper down ({copper_chg:+.1f}%) — recession signal")
        inflation_signal = "LOW — demand destruction"
    elif copper_chg > 0.5 and gold_chg < -0.5:
        regime = "REFLATION"
        signals.append(f"Copper up ({copper_chg:+.1f}%) + Gold down ({gold_chg:+.1f}%) — reflation (bullish EM)")
        inflation_signal = "MODERATE — growth-driven"
    elif up_count >= 4:
        regime = "INFLATIONARY RISK-ON"
        signals.append(f"{up_count}/5 commodities rising — inflationary pressure")
        inflation_signal = "HIGH — broad commodity rally"
    elif down_count >= 4:
        regime = "DEFLATIONARY RISK-OFF"
        signals.append(f"{down_count}/5 commodities falling — demand destruction")
        inflation_signal = "LOW — deflationary"
    elif oil_chg > 0.5 and gold_chg < -0.3:
        regime = "GROWTH-DRIVEN"
        signals.append(f"Oil up ({oil_chg:+.1f}%) + Gold flat — healthy growth demand")
        inflation_signal = "MODERATE — supply-driven"
    else:
        regime = "MIXED"
        signals.append("Commodity signals mixed — no clear regime")
        inflation_signal = "NEUTRAL"

    return {
        "ok": True,
        "regime": regime,
        "inflation_signal": inflation_signal,
        "commodities": {k: v for k, v in commodities.items()},
        "up_count": up_count,
        "down_count": down_count,
        "signals": signals,
    }


def compute_real_rate_differential(anchor_data: List[Dict]) -> Dict:
    """
    India-US real rate differential — what drives FII allocation decisions.
    Real rate = nominal yield - inflation.
    Wider differential = India more attractive for FII.
    Narrowing = FII outflow risk.
    """
    if not anchor_data:
        return {"ok": False}

    # India real rate (from macro_fetcher)
    from src.macro_fetcher import compute_real_rate
    india_real = compute_real_rate()
    if not india_real.get("ok"):
        return {"ok": False, "message": "India real rate unavailable"}

    india_rr = india_real["real_rate"]

    # US real rate approximation: US 10Y - estimated US CPI
    # US CPI stored in bot_state, fallback to 2.8% (approximate)
    us_10y = None
    for a in anchor_data:
        if a.get("name") == "US 10Y Yield" and a.get("ok"):
            us_10y = a["price"]
            break

    if us_10y is None:
        return {"ok": False, "message": "US 10Y unavailable"}

    # Get US CPI from bot_state or use approximate
    us_cpi = 2.8  # Approximate — will be replaced with stored value
    try:
        from src.db import get_bot_state
        stored_cpi = get_bot_state("us_cpi")
        if stored_cpi:
            us_cpi = float(stored_cpi)
    except Exception:
        pass

    us_real = round(us_10y - us_cpi, 2)
    differential = round(india_rr - us_real, 2)

    if differential > 3:
        label = "VERY ATTRACTIVE — strong FII carry incentive"
    elif differential > 2:
        label = "ATTRACTIVE — India yield advantage exists"
    elif differential > 1:
        label = "MODERATE — mild advantage"
    elif differential > 0:
        label = "NARROW — advantage shrinking"
    else:
        label = "NEGATIVE — US more attractive (FII outflow risk)"

    return {
        "ok": True,
        "india_real_rate": india_rr,
        "us_real_rate": us_real,
        "us_10y": us_10y,
        "us_cpi": us_cpi,
        "differential": differential,
        "label": label,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CARRY TRADE RISK INDEX — Composite institutional signal
# ═══════════════════════════════════════════════════════════════════════════════

def compute_carry_trade_risk(anchor_data: List[Dict]) -> Dict:
    """
    Composite carry trade risk index combining:
    1. JPY momentum (USD/JPY change)
    2. India-US yield spread
    3. India VIX
    4. DXY momentum

    Used by pension/SWF funds to decide EM allocation.
    """
    carry = compute_carry_trade_signal(anchor_data)
    if not carry.get("ok"):
        return {"ok": False}

    # The carry signal already computes a score — use it as the risk index
    score = carry["score"]

    # Add DXY momentum as a modifier
    for a in anchor_data:
        if a.get("name") == "Dollar Index" and a.get("ok"):
            dxy_chg = a.get("change_pct", 0) or 0
            if dxy_chg > 1:
                score -= 1
            elif dxy_chg < -1:
                score += 1

    # Normalize to 0-100 scale (raw range roughly -5 to +5)
    normalized = round((score + 5) * 10, 1)  # -5 → 0, +5 → 100
    normalized = max(0, min(100, normalized))

    if normalized >= 70:
        regime = "CARRY-ON"
    elif normalized >= 40:
        regime = "NEUTRAL"
    else:
        regime = "CARRY-STRESS"

    return {
        "ok": True,
        "raw_score": score,
        "index": normalized,
        "regime": regime,
        "signals": carry.get("signals", []),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 9: REGIME DETECTION — Bubble, Stagflation, War Premium, Multipolar Shift
# ═══════════════════════════════════════════════════════════════════════════════

def compute_ath_regime(anchor_data: List[Dict]) -> Dict:
    """
    Detect when multiple asset classes are simultaneously at or near all-time highs.
    Historically rare — signals either liquidity-driven melt-up or genuine regime shift.
    Stocks ATH + Gold ATH simultaneously is the most dangerous combination.
    """
    if not anchor_data:
        return {"ok": False}

    # We don't have 52-week highs in anchor_data, so we use the current prices
    # and weekly changes as a proxy. If weekly_change is strongly positive for
    # multiple assets, they're likely near ATH.
    assets = {}
    for a in anchor_data:
        if not a.get("ok"):
            continue
        name = a.get("name", "")
        weekly = a.get("weekly_change_pct", 0) or 0
        daily = a.get("change_pct", 0) or 0
        price = a.get("price", 0)

        if name in ("Gold", "Silver", "Brent Crude", "WTI Crude", "Copper"):
            assets[name] = {"price": price, "daily": daily, "weekly": weekly}
        elif name == "USD/INR":
            assets[name] = {"price": price, "daily": daily, "weekly": weekly}

    signals = []
    near_ath_count = 0
    strong_assets = []

    # Gold near ATH: if weekly change > 3% and price > 3000 (current regime)
    gold = assets.get("Gold", {})
    if gold.get("price", 0) > 3000 and gold.get("weekly", 0) > 2:
        near_ath_count += 1
        strong_assets.append("Gold")
        signals.append(f"Gold at ATH territory: ${gold['price']:.0f} ({gold['weekly']:+.1f}% weekly)")

    # Silver near ATH
    silver = assets.get("Silver", {})
    if silver.get("price", 0) > 50 and silver.get("weekly", 0) > 2:
        near_ath_count += 1
        strong_assets.append("Silver")
        signals.append(f"Silver at ATH territory: ${silver['price']:.0f} ({silver['weekly']:+.1f}% weekly)")

    # Oil elevated (not ATH but war-premium territory)
    brent = assets.get("Brent Crude", {})
    if brent.get("price", 0) > 90:
        signals.append(f"Brent elevated: ${brent['price']:.0f} (above $90 threshold)")

    # Dollar weak (DXY < 100)
    for a in anchor_data:
        if a.get("name") == "Dollar Index" and a.get("ok"):
            dxy = a["price"]
            dxy_weekly = a.get("weekly_change_pct", 0) or 0
            if dxy < 100:
                signals.append(f"Dollar weak: DXY {dxy:.1f} (< 100)")
            if dxy_weekly < -1:
                signals.append(f"DXY falling {dxy_weekly:+.1f}% weekly — dollar weakness accelerating")

    # Determine regime
    if near_ath_count >= 3:
        regime = "MULTI-ASSET ATH"
        label = "3+ asset classes at ATH — melt-up risk, tighten stops"
    elif near_ath_count >= 2:
        regime = "ELEVATED ACROSS ASSETS"
        label = "2+ asset classes near ATH — late cycle signals"
    elif near_ath_count >= 1:
        regime = "SINGLE ASSET STRENGTH"
        label = "1 asset class near ATH — normal dispersion"
    else:
        regime = "NORMAL DISPERSION"
        label = "No unusual ATH clustering"

    # Special combination: Stocks + Gold both near ATH
    if near_ath_count >= 2:
        signals.append("Stocks + Gold both elevated = LIQUIDITY MELT-UP signal")

    return {
        "ok": True,
        "regime": regime,
        "label": label,
        "near_ath_count": near_ath_count,
        "strong_assets": strong_assets,
        "signals": signals,
    }


def compute_stagflation_signal(anchor_data: List[Dict]) -> Dict:
    """
    Stagflation = rising inflation + slowing growth.
    Different from flight-to-safety (which is fear-driven, not inflation-driven).
    Key distinction: stagflation has CPI rising, flight-to-safety has stable CPI.
    """
    if not anchor_data:
        return {"ok": False}

    gold_chg = None
    copper_chg = None
    oil_chg = None
    gold_price = None
    copper_price = None

    for a in anchor_data:
        if not a.get("ok"):
            continue
        name = a.get("name", "")
        if name == "Gold":
            gold_chg = a.get("weekly_change_pct", 0) or 0
            gold_price = a["price"]
        elif name == "Copper":
            copper_chg = a.get("weekly_change_pct", 0) or 0
            copper_price = a["price"]
        elif name == "Brent Crude":
            oil_chg = a.get("weekly_change_pct", 0) or 0

    if gold_chg is None or copper_chg is None:
        return {"ok": False, "message": "Insufficient commodity data"}

    # Get CPI from macro_fetcher
    cpi = None
    cpi_rising = False
    try:
        from src.macro_fetcher import get_stored_cpi
        cpi = get_stored_cpi()
        # CPI > 4% = elevated, > 5% = high (India context)
        if cpi > 5:
            cpi_rising = True
        elif cpi > 4:
            cpi_rising = True
    except Exception:
        pass

    signals = []

    # Percentile-based stagflation: high oil + low Nifty (price-level detection)
    # This catches stagflation even when weekly changes are small
    nifty_close = None
    oil_price = None
    for a in anchor_data:
        if not a.get("ok"):
            continue
        name = a.get("name", "")
        if name == "Brent Crude":
            oil_price = a.get("price")
        elif name == "Nifty 50":
            nifty_close = a.get("close") or a.get("price")

    # Nifty not in anchor_data — try extra_signals or snapshot
    if not nifty_close:
        try:
            from src.db import get_daily_market_snapshots
            recent = get_daily_market_snapshots(days=5)
            if recent:
                nifty_close = recent[-1].get("nifty_close")
        except Exception:
            pass

    if nifty_close and oil_price:
        try:
            from src.formatters import get_percentile_value
            nifty_pct = get_percentile_value("nifty_close", nifty_close, "1Y")
            oil_pct = get_percentile_value("brent", oil_price, "1Y")
            if nifty_pct is not None and oil_pct is not None:
                if oil_pct > 80 and nifty_pct < 25:
                    signals.append(f"Percentile stagflation: Oil {oil_pct}th %ile + Nifty {nifty_pct}th %ile")
                    regime = "STAGFLATION PRESSURE"
                    return {"ok": True, "regime": regime, "signals": signals,
                            "label": f"Oil elevated ({oil_pct}th %ile) + Nifty depressed ({nifty_pct}th %ile) = margin compression"}
        except Exception:
            pass

    # Gold up + Copper down = either flight-to-safety or stagflation
    if gold_chg > 2 and copper_chg < -2:
        if cpi_rising:
            regime = "STAGFLATION RISK"
            label = "Rising inflation + slowing growth — worst regime for equities"
            signals.append(f"Gold up {gold_chg:+.1f}% + Copper down {copper_chg:+.1f}% + CPI {cpi}% = stagflation setup")
            signals.append("RBI may be forced to hike even as growth slows")
        else:
            regime = "FLIGHT TO SAFETY"
            label = "Fear-driven — gold bid, growth assets sold"
            signals.append(f"Gold up {gold_chg:+.1f}% + Copper down {copper_chg:+.1f}% + CPI {cpi}% = flight-to-safety")
    elif gold_chg > 2 and oil_chg is not None and oil_chg > 2:
        if cpi_rising:
            regime = "INFLATIONARY PRESSURE"
            label = "Gold + Oil both rising with elevated CPI — inflation is the threat"
            signals.append(f"Gold up {gold_chg:+.1f}% + Oil up {oil_chg:+.1f}% + CPI {cpi}% = inflationary")
        else:
            regime = "COMMODITY RALLY"
            label = "Gold + Oil rising but CPI contained — demand-driven"
            signals.append(f"Gold up {gold_chg:+.1f}% + Oil up {oil_chg:+.1f}% + CPI {cpi}% = demand-driven")
    elif copper_chg > 2 and gold_chg < 0:
        regime = "REFLATION"
        label = "Copper up, gold down — growth accelerating (bullish EM)"
        signals.append(f"Copper up {copper_chg:+.1f}% + Gold down {gold_chg:+.1f}% = reflation")
    elif gold_chg > 2 and copper_chg > 2:
        regime = "INFLATIONARY RISK-ON"
        label = "All commodities rising — inflationary, RBI may tighten"
        signals.append(f"Gold up {gold_chg:+.1f}% + Copper up {copper_chg:+.1f}% = inflationary risk-on")
    else:
        regime = "NORMAL"
        label = "No stagflation or flight-to-safety signal"
        signals.append(f"Gold {gold_chg:+.1f}%, Copper {copper_chg:+.1f}% — normal dispersion")

    return {
        "ok": True,
        "regime": regime,
        "label": label,
        "gold_chg": gold_chg,
        "copper_chg": copper_chg,
        "oil_chg": oil_chg,
        "cpi": cpi,
        "signals": signals,
    }


def compute_war_premium(anchor_data: List[Dict]) -> Dict:
    """
    Quantify the war premium in oil prices above fundamental fair value.
    When there's an active conflict, oil includes a geopolitical premium.
    De-escalation = oil crash (deflationary). Escalation = further spike.
    Uses hybrid approach: auto from macro_anchor_snapshots when available,
    hardcoded fallback (~$85) when not.
    """
    if not anchor_data:
        return {"ok": False}

    brent = None
    wti = None
    for a in anchor_data:
        if not a.get("ok"):
            continue
        if a.get("name") == "Brent Crude":
            brent = a["price"]
        elif a.get("name") == "WTI Crude":
            wti = a["price"]

    if brent is None:
        return {"ok": False, "message": "Brent data unavailable"}

    # Try to get baseline from macro_anchor_snapshots (30-day history)
    baseline = None
    try:
        from src.db import get_macro_history
        history = get_macro_history("BZ=F", days=30)
        if history and len(history) >= 5:
            # Use the earliest available price as baseline
            baseline = history[0].get("price")
    except Exception:
        pass

    # Fallback: hardcoded pre-conflict estimate
    if baseline is None:
        baseline = 85.0  # Approximate pre-conflict Brent

    premium_pct = round((brent - baseline) / baseline * 100, 1)

    signals = []
    if premium_pct > 30:
        level = "EXTREME"
        label = "Extreme war premium — crash risk on de-escalation"
        de_escalation_risk = "HIGH"
        signals.append(f"Brent ${brent:.0f} vs baseline ${baseline:.0f} = +{premium_pct:.0f}% premium")
        signals.append("If conflict de-escalates, oil could crash 20-30%")
    elif premium_pct > 15:
        level = "SIGNIFICANT"
        label = "Significant war premium — priced for continued conflict"
        de_escalation_risk = "MODERATE"
        signals.append(f"Brent ${brent:.0f} vs baseline ${baseline:.0f} = +{premium_pct:.0f}% premium")
        signals.append("Market pricing in continued conflict. Surprise de-escalation = oil correction")
    elif premium_pct > 5:
        level = "MODERATE"
        label = "Moderate premium — conflict partially priced in"
        de_escalation_risk = "LOW"
        signals.append(f"Brent ${brent:.0f} vs baseline ${baseline:.0f} = +{premium_pct:.0f}% premium")
    else:
        level = "MINIMAL"
        label = "Minimal war premium — market pricing in peace"
        de_escalation_risk = "LOW"
        signals.append(f"Brent ${brent:.0f} vs baseline ${baseline:.0f} = +{premium_pct:.0f}% premium — near fundamentals")

    return {
        "ok": True,
        "brent": brent,
        "baseline": baseline,
        "premium_pct": premium_pct,
        "level": level,
        "label": label,
        "de_escalation_risk": de_escalation_risk,
        "signals": signals,
    }


def compute_liquidity_regime(anchor_data: List[Dict]) -> Dict:
    """
    Detect when "everything rises together" — stocks, gold, dollar weak.
    This happens when central banks flood the system with liquidity.
    It's the opposite of "normal" where stocks up = gold down.
    """
    if not anchor_data:
        return {"ok": False}

    gold_chg = None
    silver_chg = None
    dxy_chg = None
    us_10y_chg = None
    brent_chg = None

    for a in anchor_data:
        if not a.get("ok"):
            continue
        name = a.get("name", "")
        chg = a.get("weekly_change_pct", 0) or 0
        if name == "Gold":
            gold_chg = chg
        elif name == "Silver":
            silver_chg = chg
        elif name == "Dollar Index":
            dxy_chg = chg
        elif name == "US 10Y Yield":
            us_10y_chg = chg
        elif name == "Brent Crude":
            brent_chg = chg

    signals = []
    score = 0  # Positive = liquidity abundant, negative = tightening

    # Gold up + Dollar down = liquidity driven (money printing)
    if gold_chg is not None and dxy_chg is not None:
        if gold_chg > 2 and dxy_chg < -1:
            score += 2
            signals.append(f"Gold up {gold_chg:+.1f}% + DXY down {dxy_chg:+.1f}% = LIQUIDITY DRIVEN")
        elif gold_chg > 2 and dxy_chg > 1:
            score -= 1
            signals.append(f"Gold up {gold_chg:+.1f}% + DXY up {dxy_chg:+.1f}% = INFLATION HEDGE (gold rising despite dollar strength)")

    # Silver + Gold both up = precious metals bid (liquidity or fear)
    if gold_chg is not None and silver_chg is not None:
        if gold_chg > 2 and silver_chg > 2:
            score += 1
            signals.append(f"Gold + Silver both up = broad precious metals bid")
        elif silver_chg > 3 and gold_chg < 1:
            signals.append(f"Silver up {silver_chg:+.1f}% + Gold flat = industrial demand (not liquidity)")

    # Oil + Gold both spiking = dual shock (inflationary + growth negative)
    if gold_chg is not None and brent_chg is not None:
        if gold_chg > 2 and brent_chg > 3:
            score -= 1
            signals.append("Gold + Oil both spiking = DUAL SHOCK (inflationary + growth negative)")

    # US yields rising = liquidity tightening
    if us_10y_chg is not None:
        if us_10y_chg > 3:
            score -= 2
            signals.append(f"US 10Y up {us_10y_chg:+.1f}% = BOND ROUT — liquidity tightening")
        elif us_10y_chg > 1:
            score -= 1
            signals.append(f"US 10Y up {us_10y_chg:+.1f}% = yields rising")
        elif us_10y_chg < -2:
            score += 1
            signals.append(f"US 10Y down {us_10y_chg:+.1f}% = yields falling (liquidity easing)")

    # Composite
    if score >= 3:
        regime = "MELT-UP"
        label = "Everything rising together — late cycle, historically ends with 15-30% correction"
    elif score >= 2:
        regime = "LIQUIDITY DRIVEN"
        label = "Central bank liquidity driving all assets — works until liquidity is withdrawn"
    elif score >= 1:
        regime = "MILDLY LIQUID ABUNDANT"
        label = "Liquidity conditions favorable"
    elif score <= -2:
        regime = "LIQUIDITY TIGHTENING"
        label = "Rising yields + strong dollar — worst environment for all assets"
    elif score <= -1:
        regime = "MILDLY TIGHT"
        label = "Liquidity conditions tightening"
    else:
        regime = "NEUTRAL"
        label = "No clear liquidity signal"

    return {
        "ok": True,
        "regime": regime,
        "label": label,
        "score": score,
        "signals": signals,
    }


def compute_gold_dollar_regime(anchor_data: List[Dict]) -> Dict:
    """
    Gold rising + Dollar falling = strongest multipolar shift signal.
    This is what happens when the world loses confidence in the dollar
    as reserve currency. Not a trade — a regime.
    """
    if not anchor_data:
        return {"ok": False}

    gold_chg = None
    gold_price = None
    dxy_chg = None
    dxy_price = None

    for a in anchor_data:
        if not a.get("ok"):
            continue
        name = a.get("name", "")
        if name == "Gold":
            gold_chg = a.get("weekly_change_pct", 0) or 0
            gold_price = a["price"]
        elif name == "Dollar Index":
            dxy_chg = a.get("weekly_change_pct", 0) or 0
            dxy_price = a["price"]

    if gold_chg is None or dxy_chg is None:
        return {"ok": False, "message": "Gold or DXY data unavailable"}

    signals = []

    if gold_chg > 2 and dxy_chg < -1:
        regime = "MULTIPOLAR SHIFT"
        label = "Gold surging + Dollar weakening — structural, not cyclical"
        signals.append(f"Gold up {gold_chg:+.1f}% + DXY down {dxy_chg:+.1f}% = multipolar shift signal")
        signals.append("Gold bid is structural in this scenario — not a trade, a regime")
        signals.append("Weak dollar = EM tailwind (capital flows to higher-yielding assets)")
        india_impact = "BULLISH — weak dollar attracts FII inflows to India"
    elif gold_chg > 2 and dxy_chg > 1:
        regime = "INFLATION HEDGE"
        label = "Gold rising despite dollar strength — pure inflation fear"
        signals.append(f"Gold up {gold_chg:+.1f}% + DXY up {dxy_chg:+.1f}% = inflation hedge bid")
        signals.append("Gold rising alongside dollar = inflation is the primary fear, not dollar weakness")
        india_impact = "NEUTRAL — dollar strength offsets gold's inflation signal"
    elif gold_chg < -1 and dxy_chg > 1:
        regime = "NORMAL"
        label = "Dollar strength pressuring gold — classic inverse relationship"
        signals.append(f"Gold down {gold_chg:+.1f}% + DXY up {dxy_chg:+.1f}% = normal inverse")
        india_impact = "BEARISH — strong dollar = FII outflow risk"
    elif gold_chg < -1 and dxy_chg < -1:
        regime = "UNUSUAL"
        label = "Both gold and dollar weak — liquidity event"
        signals.append(f"Gold down {gold_chg:+.1f}% + DXY down {dxy_chg:+.1f}% = unusual (liquidity event)")
        india_impact = "MIXED — unusual correlation, monitor for contagion"
    else:
        regime = "NEUTRAL"
        label = "No clear gold-dollar signal"
        signals.append(f"Gold {gold_chg:+.1f}%, DXY {dxy_chg:+.1f}% — within normal range")
        india_impact = "NEUTRAL"

    return {
        "ok": True,
        "regime": regime,
        "label": label,
        "gold_price": gold_price,
        "gold_chg": gold_chg,
        "dxy_price": dxy_price,
        "dxy_chg": dxy_chg,
        "india_impact": india_impact,
        "signals": signals,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN: Run all contextualization for a job execution
# ═══════════════════════════════════════════════════════════════════════════════

def compute_market_phase(ctx: Dict, inst_signals: Dict = None,
                         earnings_regime: Dict = None) -> Dict:
    """
    Classify market into 4 phases using weighted composite scoring.
    Each signal contributes a -1.0 to +1.0 score with magnitude.
    Missing signals are excluded (not scored as 0).

    Phases:
    EXPANSION   — composite >= +0.5
    RECOVERY    — composite +0.2 to +0.5
    NEUTRAL     — composite -0.2 to +0.2
    DISTRIBUTION — composite -0.5 to -0.2
    CONTRACTION  — composite <= -0.5
    """
    inst = inst_signals or {}
    er = earnings_regime or {}
    earnings = er.get("regime", "QUIET")

    # ── Step 1: Score each signal -1.0 to +1.0 ────────────────────
    scores = {}  # {name: (score, weight, available)}

    # Bull/Bear score (0-100)
    bb = ctx.get("bull_bear", {})
    if bb.get("ok"):
        bb_score = bb.get("score", 50)
        if bb_score >= 70:    s = 1.0
        elif bb_score >= 60:  s = 0.6
        elif bb_score >= 45:  s = 0.2
        elif bb_score >= 35:  s = -0.2
        elif bb_score >= 25:  s = -0.6
        else:                 s = -1.0
        scores["bull_bear"] = (s, 0.20, True)

    # Cross-asset regime
    car = ctx.get("cross_asset_regime", {})
    if car.get("ok"):
        car_regime = car.get("regime", "CONFUSION")
        car_map = {
            "RISK_ON": 1.0, "LIQUIDITY_DRIVEN": 0.7, "FLIGHT_TO_SAFETY": -0.7,
            "STAGFLATION": -0.8, "RISK_OFF": -1.0, "CONFUSION": 0.0,
        }
        scores["cross_asset"] = (car_map.get(car_regime, 0.0), 0.15, True)

    # Sector regime
    sr = inst.get("sector_regime", {})
    if sr.get("ok"):
        sr_regime = sr.get("regime", "NEUTRAL")
        sr_map = {
            "OFFENSIVE": 0.8, "MILDLY_OFFENSIVE": 0.4, "NEUTRAL": 0.0,
            "MILDLY_DEFENSIVE": -0.4, "DEFENSIVE": -0.8,
        }
        scores["sector"] = (sr_map.get(sr_regime, 0.0), 0.05, True)

    # Breadth thrust
    bt = inst.get("breadth_thrust", {})
    if bt.get("ok"):
        bt_signal = bt.get("signal", "NO_THRUST")
        bt_map = {"STRONG_THRUST": 1.0, "SINGLE_THRUST": 0.5, "NO_THRUST": -0.2}
        scores["breadth"] = (bt_map.get(bt_signal, 0.0), 0.15, True)

    # FII footprint
    fi = inst.get("fii_footprint", {})
    if fi.get("ok"):
        fi_signal = fi.get("signal", "MIXED")
        fi_map = {
            "CONSENSUS_BUY": 1.0, "STEALTH_ACCUMULATION": 0.6,
            "MIXED": 0.0, "DISTRIBUTION": -0.6, "CONSENSUS_SELL": -1.0,
        }
        scores["fii_footprint"] = (fi_map.get(fi_signal, 0.0), 0.20, True)

    # Volatility setup
    vs = inst.get("volatility_setup", {})
    if vs.get("ok"):
        vs_setup = vs.get("setup", "NORMAL")
        vs_map = {
            "COMPRESSION": 0.3, "NORMAL": 0.0, "ELEVATED": -0.4, "PANIC": -0.8,
        }
        scores["volatility"] = (vs_map.get(vs_setup, 0.0), 0.05, True)

    # Fear/Greed (from ctx or inst)
    fg = ctx.get("fear_greed", {}) or inst.get("fear_greed", {})
    if fg.get("ok") or fg.get("score") is not None:
        fg_score = fg.get("score", 50)
        if fg_score >= 75:    s = 0.8
        elif fg_score >= 60:  s = 0.4
        elif fg_score >= 40:  s = 0.0
        elif fg_score >= 25:  s = -0.4
        else:                 s = -0.8
        scores["fear_greed"] = (s, 0.10, True)

    # Credit stress
    cs = ctx.get("credit_stress", {})
    if cs.get("ok"):
        cs_level = cs.get("level", "STABLE")
        cs_map = {
            "RISK_ON": 0.5, "STABLE": 0.0, "MILD": -0.3,
            "STRESS": -0.7, "CRISIS": -1.0,
        }
        scores["credit"] = (cs_map.get(cs_level, 0.0), 0.10, True)

    # ── Step 2: Weighted composite ─────────────────────────────────
    total_weight = 0.0
    weighted_sum = 0.0
    for name, (score, weight, available) in scores.items():
        if available:
            weighted_sum += score * weight
            total_weight += weight

    composite = weighted_sum / total_weight if total_weight > 0 else 0.0

    # ── Step 3: Phase classification ───────────────────────────────
    if composite >= 0.5:
        phase = "EXPANSION"
        label = "Strong breadth, flows, macro aligned"
    elif composite >= 0.2:
        phase = "RECOVERY"
        label = "Improving but not fully confirmed"
    elif composite > -0.2:
        phase = "NEUTRAL"
        label = "Mixed signals, no directional edge"
    elif composite > -0.5:
        phase = "DISTRIBUTION"
        label = "Cracks forming, smart money exiting"
    else:
        phase = "CONTRACTION"
        label = "Broad deterioration across all signals"

    # ── Step 4: Stance = phase × confidence cross-reference ────────
    # Confidence: coverage × agreement
    coverage = total_weight / 1.0  # max possible weight = 1.0

    # Agreement: how many signals point same direction as composite
    agree_weight = 0.0
    for name, (score, weight, available) in scores.items():
        if available:
            if (composite >= 0 and score >= 0) or (composite < 0 and score < 0):
                agree_weight += weight
    agreement = agree_weight / total_weight if total_weight > 0 else 0.0

    confidence = round(coverage * agreement * 100)

    # Stance logic: phase × confidence
    if confidence < 30:
        stance = "WAIT"
        exposure = "Hold cash"
        focus = "No new positions — signal quality insufficient"
        avoid = "All directional trades"
    elif phase == "EXPANSION":
        if confidence >= 70:
            stance = "AGGRESSIVE"
            exposure = "70-80%"
            focus = "Cyclicals, high-beta, financials"
            avoid = "Cash drag, excessive hedging"
        else:
            stance = "MODERATE"
            exposure = "55-65%"
            focus = "Quality cyclicals, diversified"
            avoid = "Leverage, concentrated bets"
    elif phase == "RECOVERY":
        if confidence >= 60:
            stance = "MODERATE"
            exposure = "55-65%"
            focus = "Beaten-down quality, early cyclicals"
            avoid = "Chasing gaps, leveraged trades"
        else:
            stance = "SELECTIVE"
            exposure = "45-55%"
            focus = "Quality stocks only"
            avoid = "Speculative positions"
    elif phase == "NEUTRAL":
        stance = "BALANCED"
        exposure = "40-55%"
        focus = "Quality stocks, sector rotation"
        avoid = "Concentrated bets, leverage"
    elif phase == "DISTRIBUTION":
        if confidence >= 60:
            stance = "DEFENSIVE"
            exposure = "30-45%"
            focus = "Cash, bonds, low-beta quality"
            avoid = "Momentum, leverage, new longs"
        else:
            stance = "REDUCE"
            exposure = "45-55%"
            focus = "Quality large-caps, dividend stocks"
            avoid = "Small-caps, crowded longs"
    elif phase == "CONTRACTION":
        if confidence >= 70:
            stance = "CAPITAL_PRESERVATION"
            exposure = "20-30%"
            focus = "Cash, Gold, Pharma, defensive"
            avoid = "All cyclicals, all leverage"
        else:
            stance = "DEFENSIVE"
            exposure = "30-40%"
            focus = "Pharma, FMCG, Gold, cash"
            avoid = "High-beta, momentum trades"

    # ── Step 5: Risk watch — specific pattern detection ────────────
    risk_actions = []

    # Contradiction: smart money vs sentiment
    fi_score = scores.get("fii_footprint", (0, 0, False))[0]
    fg_score_val = scores.get("fear_greed", (0, 0, False))[0]
    if scores.get("fii_footprint", (0, 0, False))[2] and scores.get("fear_greed", (0, 0, False))[2]:
        if (fi_score < -0.3 and fg_score_val > 0.3) or (fi_score > 0.3 and fg_score_val < -0.3):
            risk_actions.append("Smart money and sentiment diverging — watch for reversal")

    # Vol compression in distribution/contraction
    if scores.get("volatility", (0, 0, False))[2]:
        vs_score = scores["volatility"][0]
        if vs_score > 0.2 and phase in ("DISTRIBUTION", "CONTRACTION"):
            risk_actions.append("Volatility compressed in bear phase — sharp selloff risk")

    # FII selling + retail absorbing
    if scores.get("fii_footprint", (0, 0, False))[2] and fi_score < -0.5:
        risk_actions.append("FII distributing — retail absorbing supply")

    # Contrarian setup: extreme fear + positive composite
    if scores.get("fear_greed", (0, 0, False))[2] and fg_score_val < -0.5 and composite > 0:
        risk_actions.append("Contrarian setup — extreme fear at positive composite")

    # Earnings noise
    if earnings == "PEAK_WEEK":
        risk_actions.append("Earnings peak week — stock-specific noise overrides index signals")
    elif earnings == "ACTIVE":
        risk_actions.append("Earnings active — sector RS signals may be noisy")

    # Low confidence
    if confidence < 35 and len(risk_actions) < 3:
        risk_actions.append("Insufficient signal quality — no directional conviction")

    # Cap at 3
    risk_actions = risk_actions[:3]

    # ── Return ─────────────────────────────────────────────────────
    return {
        "ok": True,
        "phase": phase,
        "phase_label": label,
        "stance": stance,
        "exposure_range": exposure,
        "focus": focus,
        "avoid": avoid,
        "risk_actions": risk_actions,
        "confidence": confidence,
        "composite": round(composite, 2),
        "coverage": round(coverage * 100),
        "signals_available": len([1 for _, _, a in scores.values() if a]),
        "signals_total": len(scores),
        "bull_bear_score": ctx.get("bull_bear", {}).get("score", 50),
        "cross_asset_regime": ctx.get("cross_asset_regime", {}).get("regime", "N/A"),
        "earnings_regime": earnings,
        "scores": {k: round(v[0], 2) for k, v in scores.items()},
    }


def compute_cross_asset_regime(ctx: Dict) -> Dict:
    """
    Synthesize all regime detectors into a single cross-asset regime label.
    Counts how many independent detectors confirm each regime.

    Args:
        ctx: output from run_contextualization() individual signals
    Returns:
        Dict with regime label, confirmation score, transition signal.
    """
    votes = {
        "RISK_ON": 0,
        "RISK_OFF": 0,
        "STAGFLATION": 0,
        "LIQUIDITY_DRIVEN": 0,
        "FLIGHT_TO_SAFETY": 0,
    }
    total_signals = 0
    reasons = []

    # Global risk composite (direct mapping)
    gr = ctx.get("global_risk", {})
    if gr.get("ok"):
        total_signals += 1
        r = gr.get("regime", "")
        if "RISK_ON" in r:
            votes["RISK_ON"] += 1
            reasons.append(f"Global risk: {r}")
        elif "RISK_OFF" in r:
            votes["RISK_OFF"] += 1
            reasons.append(f"Global risk: {r}")

    # Commodity breadth (flight to safety vs reflation)
    cb = ctx.get("commodity_breadth", {})
    if cb.get("ok"):
        total_signals += 1
        r = cb.get("regime", "")
        if "FLIGHT" in r:
            votes["FLIGHT_TO_SAFETY"] += 1
            reasons.append(f"Commodities: {r}")
        elif "REFLATION" in r or "RISK_ON" in r:
            votes["RISK_ON"] += 1
            reasons.append(f"Commodities: {r}")
        elif "DEFLATIONARY" in r:
            votes["RISK_OFF"] += 1
            reasons.append(f"Commodities: {r}")

    # Stagflation
    sf = ctx.get("stagflation", {})
    if sf.get("ok"):
        total_signals += 1
        r = sf.get("regime", "")
        if "STAGFLATION" in r:
            votes["STAGFLATION"] += 1
            reasons.append(f"Stagflation: {r}")
        elif "FLIGHT" in r:
            votes["FLIGHT_TO_SAFETY"] += 1
            reasons.append(f"Stagflation: {r}")
        elif "RISK_ON" in r or "REFLATION" in r:
            votes["RISK_ON"] += 1

    # Liquidity regime
    lr = ctx.get("liquidity_regime", {})
    if lr.get("ok"):
        total_signals += 1
        r = lr.get("regime", "")
        if "MELT" in r or "LIQUIDITY DRIVEN" in r:
            votes["LIQUIDITY_DRIVEN"] += 1
            reasons.append(f"Liquidity: {r}")
        elif "TIGHTENING" in r or "TIGHT" in r:
            votes["RISK_OFF"] += 1
            reasons.append(f"Liquidity: {r}")

    # Credit stress
    cs = ctx.get("credit_stress", {})
    if cs.get("ok"):
        total_signals += 1
        level = cs.get("level", "")
        if level in ("CRISIS", "STRESS"):
            votes["RISK_OFF"] += 1
            reasons.append(f"Credit: {level}")
        elif level == "RISK_ON":
            votes["RISK_ON"] += 1

    # VIX spread
    vs = ctx.get("vix_spread", {})
    if vs.get("ok"):
        total_signals += 1
        r = vs.get("regime", "")
        if "GLOBAL FEAR" in r:
            votes["RISK_OFF"] += 1
            reasons.append(f"VIX spread: {r}")
        elif "LOCAL FEAR" in r:
            # India-specific, not global contagion
            pass

    # Carry trade
    ct = ctx.get("carry_trade", {})
    if ct.get("ok"):
        total_signals += 1
        r = ct.get("regime", "")
        if "STRESS" in r:
            votes["RISK_OFF"] += 1
            reasons.append(f"Carry: {r}")
        elif "CARRY_ON" in r:
            votes["RISK_ON"] += 1

    # Gold-dollar regime
    gd = ctx.get("gold_dollar", {})
    if gd.get("ok"):
        total_signals += 1
        r = gd.get("regime", "")
        if "MULTIPOLAR" in r:
            votes["FLIGHT_TO_SAFETY"] += 1
            reasons.append(f"Gold/Dollar: {r}")
        elif "INFLATION HEDGE" in r:
            votes["STAGFLATION"] += 1

    # Bull/bear score (final arbiter)
    bb = ctx.get("bull_bear", {})
    if bb.get("ok"):
        score = bb.get("score", 50)
        if score >= 65:
            votes["RISK_ON"] += 1
        elif score <= 35:
            votes["RISK_OFF"] += 1

    # Determine winner
    if total_signals < 3:
        return {"ok": False, "message": "Insufficient signals"}

    max_votes = max(votes.values())
    winners = [k for k, v in votes.items() if v == max_votes]

    if len(winners) > 1 or max_votes < 2:
        regime = "CONFUSION"
        label  = "Mixed signals — no clear cross-asset consensus"
    else:
        regime = winners[0]
        labels = {
            "RISK_ON": "Risk-on: equities + cyclicals leading, credit stable",
            "RISK_OFF": "Risk-off: defensives + gold leading, credit widening",
            "STAGFLATION": "Stagflation: rising commodities + slowing growth",
            "LIQUIDITY_DRIVEN": "Liquidity-driven: all assets rising together (melt-up risk)",
            "FLIGHT_TO_SAFETY": "Flight to safety: gold + bonds rallying, equities weak",
        }
        label = labels.get(regime, regime)

    confirmation = round((max_votes / total_signals) * 100)

    return {
        "ok": True,
        "regime": regime,
        "label": label,
        "confirmation_pct": confirmation,
        "votes": votes,
        "total_signals": total_signals,
        "reasons": reasons[:5],
    }


def run_contextualization(anchor_data: List[Dict], extra_signals: Dict = None) -> Dict:
    """
    Full contextualization pipeline — runs inside single job execution.
    Returns all computed context for prompt injection.

    extra_signals: optional dict with breadth_ratio, nifty_vs_ma200_pct, pcr, fii_fno_net
    """
    # Get FII/DII context from DB
    fii_context = get_fii_dii_context(days=30)

    # Get macro context (VIX, DXY) from fetched anchors
    macro_context = get_macro_context(anchor_data)

    # Compute yield spread from anchors
    yield_spread = compute_yield_spread(anchor_data)

    # Compute momentum regime (if Nifty closes available from extra_signals)
    momentum = {"ok": False}
    nifty_closes = (extra_signals or {}).get("nifty_closes")
    if nifty_closes:
        momentum = compute_momentum_regime(nifty_closes)

    # Global risk signals (multipolar world framework)
    vix_spread = compute_vix_spread(anchor_data)
    credit_stress = compute_credit_stress(anchor_data)
    global_risk = compute_global_risk_composite(anchor_data)
    india_structural = compute_india_structural(anchor_data)

    # Phase 8: Institutional macro signals (computed BEFORE bull_bear so they feed into it)
    carry_trade = compute_carry_trade_signal(anchor_data)
    currency_regime = compute_currency_regime(anchor_data)
    recession_proxy = compute_recession_proxy(anchor_data)
    commodity_breadth = compute_commodity_breadth(anchor_data)
    real_rate_diff = compute_real_rate_differential(anchor_data)
    carry_risk = compute_carry_trade_risk(anchor_data)

    # Phase 9: Regime detection signals
    ath_regime = compute_ath_regime(anchor_data)
    stagflation = compute_stagflation_signal(anchor_data)
    war_premium = compute_war_premium(anchor_data)
    liquidity_regime = compute_liquidity_regime(anchor_data)
    gold_dollar = compute_gold_dollar_regime(anchor_data)

    # Institutional context (SWF/pension fund activity from stored data)
    try:
        from src.fii_tracker import get_institutional_context
        inst_context = get_institutional_context()
    except Exception:
        inst_context = {"ok": False}

    # US Employment data (BLS public API, no key needed)
    try:
        from src.data_fetcher import fetch_us_employment
        us_employment = fetch_us_employment()
    except Exception:
        us_employment = {"ok": False}

    # Enrich extra_signals with institutional + regime signals for bull_bear score
    enriched_extra = dict(extra_signals) if extra_signals else {}
    if carry_trade.get("ok"):
        enriched_extra["carry_trade_regime"] = carry_trade["regime"]
    if recession_proxy.get("ok"):
        enriched_extra["recession_level"] = recession_proxy["level"]
    if commodity_breadth.get("ok"):
        enriched_extra["commodity_regime"] = commodity_breadth["regime"]
    if stagflation.get("ok"):
        enriched_extra["stagflation_regime"] = stagflation["regime"]
    if liquidity_regime.get("ok"):
        enriched_extra["liquidity_regime"] = liquidity_regime["regime"]
    if inst_context.get("ok"):
        enriched_extra["inst_regime"] = inst_context["regime"]
    if us_employment.get("ok"):
        enriched_extra["us_recession_level"] = us_employment.get("recession_level")

    # Compute Bull/Bear score with enriched signals
    bull_bear = compute_bull_bear_score(fii_context, macro_context, extra_signals=enriched_extra)

    # Cross-asset regime synthesis (needs all signals computed first)
    cross_asset_regime = compute_cross_asset_regime({
        "global_risk": global_risk,
        "commodity_breadth": commodity_breadth,
        "stagflation": stagflation,
        "liquidity_regime": liquidity_regime,
        "credit_stress": credit_stress,
        "vix_spread": vix_spread,
        "carry_trade": carry_trade,
        "gold_dollar": gold_dollar,
        "bull_bear": bull_bear,
    })

    return {
        "fii_context": fii_context,
        "macro_context": macro_context,
        "bull_bear": bull_bear,
        "yield_spread": yield_spread,
        "momentum": momentum,
        "vix_spread": vix_spread,
        "credit_stress": credit_stress,
        "global_risk": global_risk,
        "india_structural": india_structural,
        # Phase 8 additions
        "carry_trade": carry_trade,
        "currency_regime": currency_regime,
        "recession_proxy": recession_proxy,
        "commodity_breadth": commodity_breadth,
        "real_rate_diff": real_rate_diff,
        "carry_risk": carry_risk,
        # Phase 9 additions
        "ath_regime": ath_regime,
        "stagflation": stagflation,
        "war_premium": war_premium,
        "liquidity_regime": liquidity_regime,
        "gold_dollar": gold_dollar,
        "inst_context": inst_context,
        "us_employment": us_employment,
        "cross_asset_regime": cross_asset_regime,
    }


if __name__ == "__main__":
    # Test
    print("Testing context engine...")
    # Would need actual anchor_data to test fully
    print("Context engine loaded successfully.")