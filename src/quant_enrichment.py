"""
Quant Enrichment Layer — Pre-compute intelligence from raw data
Adds historical context, percentiles, cross-signal correlations, and regime detection.
All computation in Python — zero extra API calls.
"""
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════
# HISTORICAL PERCENTILES — "Where does this value sit vs history?"
# ═══════════════════════════════════════════════════════════════════════

def compute_percentile(current: float, history: List[float]) -> Dict:
    """
    Compute where current value sits vs historical distribution.
    Returns: percentile (0-100), label, context string.
    """
    if not history or len(history) < 3:
        return {"percentile": None, "label": "insufficient data", "context": ""}

    sorted_h = sorted(history)
    n = len(sorted_h)

    # Count how many historical values are below current
    below = sum(1 for v in sorted_h if v < current)
    percentile = round((below / n) * 100)

    # Find highest/lowest and when
    max_val = max(sorted_h)
    min_val = min(sorted_h)

    # Determine label
    if percentile >= 90:
        label = "extremely elevated"
    elif percentile >= 75:
        label = "elevated"
    elif percentile >= 60:
        label = "above average"
    elif percentile >= 40:
        label = "average"
    elif percentile >= 25:
        label = "below average"
    elif percentile >= 10:
        label = "depressed"
    else:
        label = "extremely depressed"

    # Build context string
    context_parts = [f"{percentile}th percentile"]

    if current >= max_val * 0.99:
        context_parts.append("at period high")
    elif current <= min_val * 1.01:
        context_parts.append("at period low")

    return {
        "percentile": percentile,
        "label": label,
        "max": max_val,
        "min": min_val,
        "context": " | ".join(context_parts),
    }


def compute_historical_context(current: float, history: List[float],
                                dates: List[str] = None, window_label: str = "90D") -> str:
    """
    Build a human-readable historical context string.
    Example: "65th percentile of 90D | highest in 14 days"
    """
    if not history or len(history) < 3:
        return ""

    pct = compute_percentile(current, history)
    parts = [f"{pct['percentile']}th percentile of {window_label}"]

    # Find how many days since we last saw this level
    if dates and len(dates) == len(history):
        days_at_level = 0
        for i in range(len(history) - 1, -1, -1):
            if history[i] >= current:
                days_at_level = (len(history) - 1) - i
                break
        if days_at_level > 0:
            parts.append(f"highest in {days_at_level} periods")
    elif current >= pct.get("max", 0) * 0.99:
        parts.append("at period high")

    return " | ".join(parts)


# ═══════════════════════════════════════════════════════════════════════
# CROSS-ASSET SIGNAL CORRELATIONS — "What does this combination mean?"
# ═══════════════════════════════════════════════════════════════════════

# Pre-defined correlation patterns with estimated win rates
# NOTE: Win rates are estimated from market theory, not backtested.
# Use backtest_cross_signals() to compute actual rates from stored data.
CROSS_SIGNAL_PATTERNS = [
    {
        "id": "fii_sell_dxy_rise",
        "name": "FII Selling + Dollar Strength",
        "description": "FII outflows coinciding with DXY strength — bearish for EM",
        "conditions": lambda fii, macro: (
            fii.get("fii_z_score", 0) < -1.0 and
            macro.get("dxy", {}).get("direction") == "RISING"
        ),
        "estimated_nifty_decline_pct": 68,
        "avg_nifty_decline": -1.8,
        "signal_type": "bearish",
    },
    {
        "id": "fii_buy_vix_low",
        "name": "FII Buying + Low VIX",
        "description": "FII inflows in low-volatility environment — strong risk-on signal",
        "conditions": lambda fii, macro: (
            fii.get("fii_z_score", 0) > 1.0 and
            macro.get("vix_regime") == "LOW"
        ),
        "estimated_nifty_rally_pct": 72,
        "avg_nifty_rally": 2.1,
        "signal_type": "bullish",
    },
    {
        "id": "dii_absorb_high",
        "name": "DII Strong Absorption",
        "description": "DII absorbing >80% of FII selling — floor exists",
        "conditions": lambda fii, macro: (
            fii.get("dii_absorbed", 0) >= 0.8 and
            fii.get("fii_z_score", 0) < -0.5
        ),
        "estimated_floor_pct": 78,
        "avg_max_drawdown": -0.8,
        "signal_type": "supportive",
    },
    {
        "id": "triple_threat",
        "name": "Triple Threat Bear",
        "description": "FII sharp sell + streak + HIGH VIX — rare, severe",
        "conditions": lambda fii, macro: (
            fii.get("fii_z_score", 0) < -1.5 and
            fii.get("fii_streak", 0) >= 3 and
            macro.get("vix_regime") == "HIGH"
        ),
        "estimated_nifty_decline_pct": 82,
        "avg_nifty_decline": -3.2,
        "signal_type": "critical_bear",
    },
    {
        "id": "dxy_tailwind",
        "name": "Dollar Weakness Tailwind",
        "description": "DXY falling + DII support — expect accelerated FII inflows",
        "conditions": lambda fii, macro: (
            macro.get("dxy", {}).get("direction") == "FALLING" and
            fii.get("dii_absorbed", 0) >= 0.8
        ),
        "estimated_inflow_acceleration_pct": 65,
        "avg_nifty_rally": 1.5,
        "signal_type": "bullish",
    },
    {
        "id": "india_specific",
        "name": "India-Specific Event",
        "description": "FII selling but DXY flat — not global EM, local factors at play",
        "conditions": lambda fii, macro: (
            macro.get("dxy", {}).get("direction") == "FLAT" and
            fii.get("fii_z_score", 0) < -0.5
        ),
        "signal_type": "neutral",
        "note": "Watch domestic catalysts — not driven by dollar",
    },
    {
        "id": "buy_the_fear",
        "name": "Buy the Fear (Contrarian)",
        "description": "FII buying into HIGH VIX — smart money contrarian signal",
        "conditions": lambda fii, macro: (
            fii.get("fii_z_score", 0) > 0.5 and
            macro.get("vix_regime") == "HIGH"
        ),
        "estimated_rally_pct": 70,
        "avg_nifty_rally": 2.8,
        "signal_type": "contrarian_bull",
    },
]


def compute_cross_signals(fii_context: Dict, macro_context: Dict) -> List[Dict]:
    """
    Evaluate all cross-signal patterns against current data.
    Returns list of active signals with historical context.
    """
    active_signals = []

    for pattern in CROSS_SIGNAL_PATTERNS:
        try:
            if pattern["conditions"](fii_context, macro_context):
                signal = {
                    "id": pattern["id"],
                    "name": pattern["name"],
                    "description": pattern["description"],
                    "type": pattern["signal_type"],
                }
                # Add estimated stats if available
                if "estimated_nifty_decline_pct" in pattern:
                    signal["est_prob"] = pattern["estimated_nifty_decline_pct"]
                    signal["avg_move"] = pattern["avg_nifty_decline"]
                elif "estimated_nifty_rally_pct" in pattern:
                    signal["est_prob"] = pattern["estimated_nifty_rally_pct"]
                    signal["avg_move"] = pattern["avg_nifty_rally"]
                elif "estimated_floor_pct" in pattern:
                    signal["est_prob"] = pattern["estimated_floor_pct"]
                    signal["avg_move"] = pattern["avg_max_drawdown"]
                elif "estimated_inflow_acceleration_pct" in pattern:
                    signal["est_prob"] = pattern["estimated_inflow_acceleration_pct"]
                    signal["avg_move"] = pattern["avg_nifty_rally"]
                elif "estimated_rally_pct" in pattern:
                    signal["est_prob"] = pattern["estimated_rally_pct"]
                    signal["avg_move"] = pattern["avg_nifty_rally"]

                if "note" in pattern:
                    signal["note"] = pattern["note"]

                active_signals.append(signal)
        except Exception:
            continue

    return active_signals


def backtest_cross_signals(nifty_closes: List[float], fii_flows: List[Dict],
                            vix_history: List[float] = None) -> Dict:
    """
    Backtest cross-signal patterns against historical data.
    Uses stored FII/DII flows + Nifty returns to compute actual hit rates.

    Args:
        nifty_closes: List of Nifty close prices (chronological)
        fii_flows: List of dicts from Supabase fii_dii_flows table
                   Each: {date, fiinet_cr, diinet_cr}
        vix_history: Optional list of VIX values (same length as nifty_closes)

    Returns:
        {pattern_id: {"win_rate": float, "avg_move": float, "sample_size": int}}
    """
    import statistics

    if not nifty_closes or not fii_flows or len(nifty_closes) < 20 or len(fii_flows) < 10:
        return {"ok": False, "message": "Insufficient data for backtesting"}

    # Compute FII z-scores from flow data
    fii_values = [f.get("fiinet_cr", 0) for f in fii_flows]
    fii_mean = statistics.mean(fii_values)
    fii_std = statistics.stdev(fii_values) if len(fii_values) > 1 else 1

    # Build date-aligned dataset
    # Assume fii_flows and nifty_closes are roughly aligned (both daily)
    results = {}
    for pattern in CROSS_SIGNAL_PATTERNS:
        pattern_id = pattern["id"]
        wins = 0
        total = 0
        moves = []

        for i in range(len(fii_flows) - 5):  # Need 5 days forward
            # Build synthetic contexts for this day
            fii_val = fii_flows[i].get("fiinet_cr", 0)
            fii_z = (fii_val - fii_mean) / fii_std if fii_std > 0 else 0

            dii_val = fii_flows[i].get("diinet_cr", 0)
            # Float ratio: what fraction of |FII| does DII cover? Cap at 200%
            ratio = abs(dii_val) / abs(fii_val) if fii_val != 0 else 0
            dii_absorbed = min(ratio, 2.0)

            # Compute streak
            streak = 0
            direction = "positive" if fii_val > 0 else "negative"
            for j in range(i, max(i - 10, -1), -1):
                f = fii_flows[j].get("fiinet_cr", 0)
                if (f > 0 and direction == "positive") or (f < 0 and direction == "negative"):
                    streak += 1
                else:
                    break

            # VIX regime (if available)
            vix_regime = "NORMAL"
            if vix_history and i < len(vix_history):
                vix = vix_history[i]
                if vix > 20:
                    vix_regime = "HIGH"
                elif vix < 15:
                    vix_regime = "LOW"

            # DXY not available from stored data — use FLAT as default
            dxy_dir = "FLAT"

            fii_context = {
                "fii_z_score": fii_z,
                "fii_streak": streak,
                "fii_streak_direction": direction,
                "dii_absorbed": dii_absorbed,
            }
            macro_context = {
                "vix_regime": vix_regime,
                "dxy": {"direction": dxy_dir},
            }

            # Check if pattern conditions are met
            try:
                if not pattern["conditions"](fii_context, macro_context):
                    continue
            except Exception:
                continue

            # Pattern activated — measure forward 5-day return
            if i + 5 < len(nifty_closes):
                forward_return = (nifty_closes[i + 5] / nifty_closes[i] - 1) * 100
                total += 1

                # Win = move in expected direction
                if pattern["signal_type"] in ("bearish", "critical_bear"):
                    if forward_return < 0:
                        wins += 1
                elif pattern["signal_type"] in ("bullish", "contrarian_bull", "supportive"):
                    if forward_return > 0:
                        wins += 1
                # neutral patterns don't have win/loss

                moves.append(forward_return)

        if total >= 3:
            results[pattern_id] = {
                "win_rate": round((wins / total) * 100, 1),
                "avg_move": round(statistics.mean(moves), 2),
                "sample_size": total,
                "pattern_name": pattern["name"],
            }

    return {"ok": True, "results": results}


# ═══════════════════════════════════════════════════════════════════════════════
# CONTRARIAN INDICATORS
# ═══════════════════════════════════════════════════════════════════════════════

def compute_sip_concentration(mf_flows: list) -> Dict:
    """
    Compute Herfindahl-Hirschman Index (HHI) of MF flow concentration.
    High HHI = flows concentrated in few sectors (contrarian sell signal).
    Low HHI = flows diversified (healthy).
    """
    if not mf_flows or len(mf_flows) < 3:
        return {"ok": False}

    total = sum(abs(f.get("amount_cr", 0)) for f in mf_flows)
    if total == 0:
        return {"ok": False}

    shares = [abs(f.get("amount_cr", 0)) / total for f in mf_flows]
    hhi = round(sum(s ** 2 for s in shares), 4)

    if hhi > 0.25:
        label = "EXTREMELY CONCENTRATED — contrarian sell signal"
    elif hhi > 0.15:
        label = "CONCENTRATED — watch for crowding"
    elif hhi > 0.10:
        label = "MODERATELY DIVERSIFIED"
    else:
        label = "WELL DIVERSIFIED — healthy"

    return {
        "ok": True,
        "hhi": hhi,
        "label": label,
        "num_categories": len(mf_flows),
        "total_cr": round(total, 0),
    }


def compute_sentiment_extreme(articles: list) -> Dict:
    """
    Analyze FinBERT sentiment distribution for contrarian signals.
    Extreme negative sentiment = contrarian buy signal.
    Extreme positive sentiment = contrarian sell signal.
    """
    if not articles or len(articles) < 3:
        return {"ok": False}

    neg_scores = []
    pos_scores = []

    for a in articles:
        sent = a.get("sentiment", {})
        if sent:
            neg_scores.append(sent.get("negative", 0))
            pos_scores.append(sent.get("positive", 0))

    if not neg_scores:
        return {"ok": False}

    avg_neg = sum(neg_scores) / len(neg_scores)
    avg_pos = sum(pos_scores) / len(pos_scores)
    pct_very_neg = sum(1 for s in neg_scores if s > 0.7) / len(neg_scores) * 100
    pct_very_pos = sum(1 for s in pos_scores if s > 0.7) / len(pos_scores) * 100

    if pct_very_neg > 70:
        signal = "EXTREME FEAR — contrarian buy signal"
        direction = "contrarian_bull"
    elif pct_very_neg > 50:
        signal = "HIGH FEAR — potential contrarian opportunity"
        direction = "mild_bull"
    elif pct_very_pos > 70:
        signal = "EXTREME GREED — contrarian sell signal"
        direction = "contrarian_bear"
    elif pct_very_pos > 50:
        signal = "HIGH GREED — watch for complacency"
        direction = "mild_bear"
    else:
        signal = "BALANCED sentiment"
        direction = "neutral"

    return {
        "ok": True,
        "avg_negative": round(avg_neg, 3),
        "avg_positive": round(avg_pos, 3),
        "pct_very_negative": round(pct_very_neg, 1),
        "pct_very_positive": round(pct_very_pos, 1),
        "signal": signal,
        "direction": direction,
        "sample_size": len(neg_scores),
    }


def compute_signal_consensus(signals: List[Dict]) -> Dict:
    """
    How many independent signals point the same direction?
    Returns: direction, conviction (HIGH/MEDIUM/LOW), agreement_ratio
    """
    if not signals:
        return {"direction": "NEUTRAL", "conviction": "LOW", "agreement": 0}

    bull_count = sum(1 for s in signals if s.get("type") in ("bullish", "contrarian_bull", "supportive"))
    bear_count = sum(1 for s in signals if s.get("type") in ("bearish", "critical_bear"))
    total = bull_count + bear_count

    if total == 0:
        return {"direction": "NEUTRAL", "conviction": "LOW", "agreement": 0}

    agreement = max(bull_count, bear_count) / total
    direction = "BULLISH" if bull_count > bear_count else "BEARISH" if bear_count > bull_count else "NEUTRAL"
    conviction = "HIGH" if agreement > 0.75 else "MEDIUM" if agreement > 0.5 else "LOW"

    return {
        "direction": direction,
        "conviction": conviction,
        "agreement": round(agreement, 2),
        "bull_signals": bull_count,
        "bear_signals": bear_count,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# VIX vs REALIZED VOLATILITY SPREAD
# ═══════════════════════════════════════════════════════════════════════════════

def compute_vix_rv_spread(vix_current: float, nifty_closes: list, period: int = 20) -> Dict:
    """
    Compare implied volatility (VIX) with realized volatility.
    Realized vol = annualized std dev of daily returns over period.

    Spread > +3 = options EXPENSIVE (sellers favored)
    Spread < -3 = options CHEAP (buyers favored)
    """
    import statistics

    if not nifty_closes or len(nifty_closes) < period + 1:
        return {"ok": False, "message": f"Need {period + 1} closes, have {len(nifty_closes) if nifty_closes else 0}"}

    if not vix_current or vix_current <= 0:
        return {"ok": False}

    returns = [(nifty_closes[-i] / nifty_closes[-i - 1] - 1) for i in range(1, period + 1)]
    daily_std = statistics.stdev(returns)
    realized_vol = round(daily_std * (252 ** 0.5) * 100, 2)  # Annualized, in %

    spread = round(vix_current - realized_vol, 2)

    if spread > 5:
        label = "VERY EXPENSIVE — sell premium aggressively"
    elif spread > 3:
        label = "EXPENSIVE — sellers favored"
    elif spread > -3:
        label = "FAIR — balanced pricing"
    elif spread > -5:
        label = "CHEAP — buyers favored"
    else:
        label = "VERY CHEAP — buy protection"

    return {
        "ok": True,
        "vix": round(vix_current, 2),
        "realized_vol": realized_vol,
        "spread": spread,
        "label": label,
        "period": period,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# FEAR & GREED INDEX (0-100)
# ═══════════════════════════════════════════════════════════════════════════════

def compute_fear_greed_index(vix: float = None, pcr: float = None,
                              breadth_ratio: float = None, fii_z_score: float = None,
                              momentum_12m: float = None, sentiment_score: float = None) -> Dict:
    """
    Composite Fear & Greed Index (0-100).
    0 = Extreme Fear, 50 = Neutral, 100 = Extreme Greed.

    Each component normalized to 0-100, then averaged.
    Missing components are excluded (not defaulted to 50).
    """
    components = []

    # VIX: VIX > 25 = 0 (fear), VIX < 12 = 100 (greed)
    if vix is not None and vix > 0:
        vix_score = max(0, min(100, (25 - vix) / (25 - 12) * 100))
        components.append(("VIX", round(vix_score, 1)))

    # PCR: PCR > 1.4 = 0 (fear), PCR < 0.5 = 100 (greed)
    if pcr is not None and pcr > 0:
        pcr_score = max(0, min(100, (1.4 - pcr) / (1.4 - 0.5) * 100))
        components.append(("PCR", round(pcr_score, 1)))

    # Breadth: ratio < 0.5 = 0 (fear), ratio > 2.0 = 100 (greed)
    if breadth_ratio is not None and breadth_ratio > 0:
        breadth_score = max(0, min(100, (breadth_ratio - 0.5) / (2.0 - 0.5) * 100))
        components.append(("Breadth", round(breadth_score, 1)))

    # FII Flows: z-score < -1.5 = 0 (fear), z-score > 1.5 = 100 (greed)
    if fii_z_score is not None:
        fii_score = max(0, min(100, (fii_z_score + 1.5) / 3.0 * 100))
        components.append(("FII", round(fii_score, 1)))

    # Momentum: 12M return < -15% = 0 (fear), > 15% = 100 (greed)
    if momentum_12m is not None:
        mom_score = max(0, min(100, (momentum_12m + 15) / 30.0 * 100))
        components.append(("Momentum", round(mom_score, 1)))

    # Sentiment: > 70% negative = 0 (fear), > 70% positive = 100 (greed)
    if sentiment_score is not None:
        components.append(("Sentiment", round(max(0, min(100, sentiment_score)), 1)))

    if not components:
        return {"ok": False, "message": "No components available"}

    # Average all available components
    scores = [c[1] for c in components]
    index = round(sum(scores) / len(scores), 1)

    if index < 20:
        label = "EXTREME FEAR"
    elif index < 40:
        label = "FEAR"
    elif index < 60:
        label = "NEUTRAL"
    elif index < 80:
        label = "GREED"
    else:
        label = "EXTREME GREED"

    return {
        "ok": True,
        "index": index,
        "label": label,
        "components": {c[0]: c[1] for c in components},
        "num_components": len(components),
    }


def format_cross_signals(signals: List[Dict]) -> str:
    """Format cross-signal analysis for AI prompt injection."""
    if not signals:
        return ""

    lines = ["[Cross-Signal Analysis]"]
    for s in signals:
        emoji = {"bearish": "🔴", "bullish": "🟢", "supportive": "🛡️",
                 "critical_bear": "🚨", "contrarian_bull": "🔄", "neutral": "⚪"
                 }.get(s["type"], "⚪")
        line = f"{emoji} {s['name']}: {s['description']}"
        if "est_prob" in s:
            line += f" (estimated: {s['est_prob']}% hit rate, avg {s['avg_move']:+.1f}%)"
        if "note" in s:
            line += f" — {s['note']}"
        lines.append(line)

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
# REGIME TRANSITION DETECTION — "Is the market shifting?"
# ═══════════════════════════════════════════════════════════════════════

def detect_regime_transition(fii_context: Dict, macro_context: Dict,
                              prev_fii_context: Dict = None) -> Dict:
    """
    Detect if market is transitioning between regimes.
    Compares current state vs previous state.
    """
    transition = {"transitioning": False}

    if not prev_fii_context:
        return transition

    curr_vix = macro_context.get("vix_regime", "NORMAL")
    prev_vix = prev_fii_context.get("vix_regime", "NORMAL") if prev_fii_context else "NORMAL"

    curr_fii_z = fii_context.get("fii_z_score", 0)
    prev_fii_z = prev_fii_context.get("fii_z_score", 0) if prev_fii_context else 0

    # VIX regime change
    if curr_vix != prev_vix:
        transition["transitioning"] = True
        transition["from"] = prev_vix
        transition["to"] = curr_vix
        transition["trigger"] = f"VIX regime: {prev_vix} → {curr_vix}"
        transition["confidence"] = "HIGH"

    # FII direction flip
    if (prev_fii_z > 0.5 and curr_fii_z < -0.5):
        transition["transitioning"] = True
        transition["from"] = "FII buying"
        transition["to"] = "FII selling"
        transition["trigger"] = f"FII z-score flipped: {prev_fii_z:+.1f} → {curr_fii_z:+.1f}"
        transition["confidence"] = "MEDIUM"
    elif (prev_fii_z < -0.5 and curr_fii_z > 0.5):
        transition["transitioning"] = True
        transition["from"] = "FII selling"
        transition["to"] = "FII buying"
        transition["trigger"] = f"FII z-score flipped: {prev_fii_z:+.1f} → {curr_fii_z:+.1f}"
        transition["confidence"] = "MEDIUM"

    return transition


# ═══════════════════════════════════════════════════════════════════════
# NEWS IMPACT SCORING — "How market-moving is this headline?"
# ═══════════════════════════════════════════════════════════════════════

# Keywords that indicate high market impact
HIGH_IMPACT_KEYWORDS = [
    "tariff", "sanction", "rate cut", "rate hike", "fed", "rbi", "ecb", "boj",
    "gdp", "inflation", "cpi", "ppi", "unemployment", "nonfarm", "payroll",
    "recession", "crisis", "default", "bankruptcy", "war", "conflict",
    "oil", "crude", "opec", "supply cut", "production cut",
    "earnings", "revenue", "guidance", "forecast", "outlook",
    "ipo", "merger", "acquisition", "buyback", "dividend",
    "sebi", "nse", "bse", "fii", "dii", "sensex", "nifty",
    "dollar", "dxy", "treasury", "bond", "yield",
]

MEDIUM_IMPACT_KEYWORDS = [
    "upgrade", "downgrade", "target", "rating", "analyst",
    "sector", "industry", "growth", "decline", "surge", "plunge",
    "record", "high", "low", "breakout", "support", "resistance",
    "policy", "reform", "budget", "fiscal", "monetary",
]

CATEGORY_KEYWORDS = {
    "macro": ["gdp", "inflation", "cpi", "ppi", "unemployment", "payroll", "recession",
              "fed", "rbi", "ecb", "boj", "rate", "monetary", "fiscal", "treasury", "bond", "yield"],
    "geopolitical": ["tariff", "sanction", "war", "conflict", "trade", "embargo", "diplomatic"],
    "earnings": ["earnings", "revenue", "profit", "eps", "guidance", "forecast", "quarterly"],
    "commodity": ["oil", "crude", "gold", "silver", "copper", "opec", "supply", "production"],
    "currency": ["dollar", "dxy", "rupee", "usd", "inr", "forex", "currency"],
    "flows": ["fii", "dii", "inflow", "outflow", "foreign", "institutional"],
    "policy": ["sebi", "rbi", "budget", "reform", "regulation", "tax", "gst"],
}


def score_news_impact(headline: str) -> Dict:
    """
    Score a news headline for market impact beyond sentiment.
    Returns: impact level, category, extracted numbers, affected assets.
    """
    headline_lower = headline.lower()

    # Extract numbers with context
    numbers = re.findall(r'[\$₹€£]?\d+\.?\d*\s*[%$₹€£KkMmBbTt]?|'
                          r'\d+\.?\d*\s*(?:percent|bps|basis points|cr|crore|lakh|billion|million|trillion)',
                          headline)
    number_str = ", ".join(numbers[:3]) if numbers else ""

    # Score impact
    high_hits = sum(1 for kw in HIGH_IMPACT_KEYWORDS if kw in headline_lower)
    medium_hits = sum(1 for kw in MEDIUM_IMPACT_KEYWORDS if kw in headline_lower)

    if high_hits >= 2:
        impact = "HIGH"
        impact_score = 9
    elif high_hits >= 1:
        impact = "HIGH"
        impact_score = 8
    elif medium_hits >= 2:
        impact = "MEDIUM"
        impact_score = 6
    elif medium_hits >= 1:
        impact = "MEDIUM"
        impact_score = 5
    else:
        impact = "LOW"
        impact_score = 3

    # Determine category
    category = "general"
    max_cat_hits = 0
    for cat, keywords in CATEGORY_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in headline_lower)
        if hits > max_cat_hits:
            max_cat_hits = hits
            category = cat

    # Determine affected assets
    affected = []
    asset_keywords = {
        "Nifty": ["nifty", "sensex", "india", "bse", "nse"],
        "USD/INR": ["rupee", "usd", "inr", "forex", "dollar", "currency"],
        "FII/DII": ["fii", "dii", "foreign", "institutional", "inflow", "outflow"],
        "Oil": ["oil", "crude", "opec", "brent"],
        "Gold": ["gold", "bullion"],
        "US Markets": ["s&p", "nasdaq", "dow", "wall street", "fed", "treasury"],
    }
    for asset, keywords in asset_keywords.items():
        if any(kw in headline_lower for kw in keywords):
            affected.append(asset)

    return {
        "impact": impact,
        "impact_score": impact_score,
        "category": category,
        "numbers": number_str,
        "affected_assets": affected,
    }


def enrich_news_articles(articles: List[Dict]) -> List[Dict]:
    """
    Add impact scoring to news articles.
    Returns articles sorted by impact score (highest first).
    """
    for article in articles:
        headline = article.get("headline", "")
        impact = score_news_impact(headline)
        article["impact"] = impact["impact"]
        article["impact_score"] = impact["impact_score"]
        article["category"] = impact["category"]
        article["extracted_numbers"] = impact["numbers"]
        article["affected_assets"] = impact["affected_assets"]

    # Sort by impact score descending
    articles.sort(key=lambda a: a.get("impact_score", 0), reverse=True)
    return articles


# ═══════════════════════════════════════════════════════════════════════
# SIGNIFICANCE LABELS — "How notable is this move?"
# ═══════════════════════════════════════════════════════════════════════

def compute_significance_label(current: float, history: List[float],
                                metric_name: str = "value") -> str:
    """
    Generate a significance label for a metric value vs its history.
    Example: "largest single-day FII sell in 30 days"
    """
    if not history or len(history) < 5:
        return ""

    pct = compute_percentile(current, history)

    if pct["percentile"] is None:
        return ""

    if pct["percentile"] >= 95:
        return f"extreme {metric_name} — top 5% of period"
    elif pct["percentile"] >= 90:
        return f"notably elevated {metric_name}"
    elif pct["percentile"] >= 80:
        return f"above normal {metric_name}"
    elif pct["percentile"] <= 5:
        return f"extreme {metric_name} — bottom 5% of period"
    elif pct["percentile"] <= 10:
        return f"notably depressed {metric_name}"
    elif pct["percentile"] <= 20:
        return f"below normal {metric_name}"

    return ""


# ═══════════════════════════════════════════════════════════════════════
# ENRICHMENT WRAPPER — Add quant context to formatter output
# ═══════════════════════════════════════════════════════════════════════

def enrich_with_percentile(value: float, history: List[float],
                            metric_name: str, window_label: str = "90D") -> str:
    """
    Add percentile context to a formatted metric.
    Returns: "value (65th percentile of 90D | highest in 14 days)"
    """
    if not history or len(history) < 5:
        return ""

    ctx = compute_historical_context(value, history, window_label=window_label)
    return f"{ctx}" if ctx else ""


def enrich_formatter_block(block_type: str, raw_lines: List[str],
                            enrichment_data: Dict) -> List[str]:
    """
    Add quant enrichment lines to a formatter block.
    enrichment_data: {"percentiles": {...}, "cross_signals": [...], "regime": {...}}
    """
    enriched = list(raw_lines)

    # Add percentile annotations
    if enrichment_data.get("percentiles"):
        for metric, pct_data in enrichment_data["percentiles"].items():
            if pct_data.get("context"):
                enriched.append(f"  ↳ {metric}: {pct_data['context']}")

    # Add cross-signal summary
    if enrichment_data.get("cross_signals"):
        signals = enrichment_data["cross_signals"]
        active = [s for s in signals if s.get("est_prob")]
        if active:
            enriched.append(f"\n[Active Cross-Signals: {len(active)}]")
            for s in active[:2]:  # Top 2 only
                enriched.append(f"  • {s['name']}: {s['est_prob']}% estimated hit rate")

    return enriched


# ═══════════════════════════════════════════════════════════════════════
# SCENARIO GENERATION — "What are the possible outcomes?"
# ═══════════════════════════════════════════════════════════════════════

def generate_scenarios(bull_bear_score: float, cross_signals: List[Dict],
                        macro_context: Dict, nifty_price: float = None) -> str:
    """
    Generate probability-weighted scenarios based on current signals.
    Returns formatted string for AI prompt.
    Always includes Bull/Base/Bear with current price anchored in Base range.
    """
    # Base probabilities from bull/bear score
    if bull_bear_score >= 70:
        bull_pct, bear_pct, base_pct = 55, 15, 30
    elif bull_bear_score >= 60:
        bull_pct, bear_pct, base_pct = 45, 20, 35
    elif bull_bear_score >= 40:
        bull_pct, bear_pct, base_pct = 30, 30, 40
    elif bull_bear_score >= 30:
        bull_pct, bear_pct, base_pct = 20, 45, 35
    else:
        bull_pct, bear_pct, base_pct = 15, 55, 30

    # Adjust based on cross-signals
    for signal in cross_signals:
        if signal.get("type") == "critical_bear":
            bear_pct += 10
            bull_pct -= 5
        elif signal.get("type") == "bullish":
            bull_pct += 10
            bear_pct -= 5
        elif signal.get("type") == "contrarian_bull":
            bull_pct += 5

    # Normalize to 100
    total = bull_pct + bear_pct + base_pct
    bull_pct = round((bull_pct / total) * 100)
    bear_pct = round((bear_pct / total) * 100)
    base_pct = 100 - bull_pct - bear_pct

    # Build scenario descriptions
    vix = macro_context.get("vix_regime", "NORMAL")
    dxy = macro_context.get("dxy", {}).get("direction", "FLAT")

    bull_desc = "Continued inflows, VIX compression, range expansion"
    bear_desc = "Accelerated outflows, VIX spike, support break"
    if nifty_price:
        base_desc = f"Range-bound near {nifty_price:,.0f} (±2%), mixed flows, awaiting catalyst"
    else:
        base_desc = "Range-bound, mixed flows, awaiting catalyst"

    # Adjust descriptions based on context
    if vix == "HIGH":
        bear_desc = "VIX remains elevated, risk-off persists, further selling"
        base_desc = "VIX compresses slowly, cautious recovery, stock-specific action"
    elif dxy == "RISING":
        bear_desc = "Dollar strength continues, EM outflows accelerate"
        bull_desc = "Dollar reversal triggers FII return, short-covering rally"

    lines = ["[Scenario Analysis]"]
    lines.append(f"• Bull case ({bull_pct}%): {bull_desc}")
    lines.append(f"• Base case ({base_pct}%): {base_desc}")
    lines.append(f"• Bear case ({bear_pct}%): {bear_desc}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
# INSTITUTIONAL SIGNALS — "What smart money does, not what it says"
# All computed from stored Supabase data. Zero API cost.
# ═══════════════════════════════════════════════════════════════════════

OFFENSIVE_SECTORS = {"BANK", "AUTO", "REALTY", "METAL", "INFRA"}
DEFENSIVE_SECTORS = {"PHARMA", "FMCG", "IT", "MEDIA"}

HIGH_BETA_SECTORS = {"BANK", "AUTO", "METAL", "REALTY"}
LOW_BETA_SECTORS  = {"PHARMA", "FMCG"}


def compute_sector_regime(sector_perf: Dict[str, float]) -> Dict:
    """
    Classify market regime by which sectors are leading.
    Offensive (cyclicals leading) vs Defensive (staples/pharma leading).
    Defensive shift = classic late-cycle warning that AMCs watch.

    Args:
        sector_perf: {sector_name: weekly_change_pct} e.g. {"BANK": 2.1, "PHARMA": -0.5}
    Returns:
        Dict with regime label, offensive/defensive scores, leading sectors.
    """
    if not sector_perf:
        return {"ok": False, "message": "No sector data"}

    off_scores = [sector_perf[s] for s in OFFENSIVE_SECTORS if s in sector_perf]
    def_scores = [sector_perf[s] for s in DEFENSIVE_SECTORS if s in sector_perf]

    off_avg = sum(off_scores) / len(off_scores) if off_scores else 0
    def_avg = sum(def_scores) / len(def_scores) if def_scores else 0
    spread  = off_avg - def_avg

    if spread > 2.0:
        regime = "OFFENSIVE"
        label  = "Risk-on: cyclicals leading (bullish)"
    elif spread > 0.5:
        regime = "MILDLY_OFFENSIVE"
        label  = "Slight risk preference"
    elif spread > -0.5:
        regime = "NEUTRAL"
        label  = "No clear sector preference"
    elif spread > -2.0:
        regime = "MILDLY_DEFENSIVE"
        label  = "Early defensive rotation (caution)"
    else:
        regime = "DEFENSIVE"
        label  = "Risk-off: defensives leading (late-cycle warning)"

    # Top 3 leaders and laggards
    sorted_sectors = sorted(sector_perf.items(), key=lambda x: x[1], reverse=True)
    leaders   = sorted_sectors[:3]
    laggards  = sorted_sectors[-3:]

    return {
        "ok": True,
        "regime": regime,
        "label": label,
        "offensive_avg": round(off_avg, 2),
        "defensive_avg": round(def_avg, 2),
        "spread": round(spread, 2),
        "leaders": leaders,
        "laggards": laggards,
    }


def compute_volatility_setup(vix_history: List[float], vix_current: float) -> Dict:
    """
    Detect volatility compression (coiled spring) or expansion.
    Options desks use this daily. VIX below 20th percentile = breakout imminent.
    Above 80th percentile = panic, mean-reversion likely.

    Args:
        vix_history: list of VIX closing prices over 90 days
        vix_current: today's VIX value
    Returns:
        Dict with percentile, setup label, historical context.
    """
    if not vix_history or len(vix_history) < 10 or vix_current is None:
        return {"ok": False, "message": "Insufficient VIX history"}

    sorted_vix = sorted(vix_history)
    n = len(sorted_vix)

    # Find percentile rank
    rank = sum(1 for v in sorted_vix if v <= vix_current)
    percentile = round((rank / n) * 100)

    # Compute compression/expansion
    recent_5  = vix_history[-5:] if len(vix_history) >= 5 else vix_history
    recent_20 = vix_history[-20:] if len(vix_history) >= 20 else vix_history

    avg_5  = sum(recent_5) / len(recent_5)
    avg_20 = sum(recent_20) / len(recent_20)
    compression = round(((avg_20 - vix_current) / avg_20) * 100, 1) if avg_20 else 0

    if percentile <= 15:
        setup = "EXTREME_COMPRESSION"
        label = "Coiled spring — breakout imminent (options desks buy straddles here)"
    elif percentile <= 30:
        setup = "COMPRESSION"
        label = "Low vol environment — complacency building"
    elif percentile <= 70:
        setup = "NORMAL"
        label = "Volatility in normal range"
    elif percentile <= 85:
        setup = "ELEVATED"
        label = "Elevated fear — hedging activity rising"
    else:
        setup = "PANIC"
        label = "Extreme fear — mean-reversion likely (contrarian buy signal)"

    return {
        "ok": True,
        "vix_current": vix_current,
        "percentile": percentile,
        "setup": setup,
        "label": label,
        "avg_5d": round(avg_5, 2),
        "avg_20d": round(avg_20, 2),
        "compression_pct": compression,
        "90d_range": (round(sorted_vix[0], 2), round(sorted_vix[-1], 2)),
    }


def compute_risk_appetite(sector_perf: Dict[str, float]) -> Dict:
    """
    High-beta (Bank, Auto, Metal) vs Low-beta (Pharma, FMCG) spread.
    Widening = risk-on, narrowing = risk-off.
    Institutional flow direction proxy — funds rotate between these buckets.

    Args:
        sector_perf: {sector_name: weekly_change_pct}
    Returns:
        Dict with spread, appetite label, component scores.
    """
    if not sector_perf:
        return {"ok": False, "message": "No sector data"}

    hb_scores = [sector_perf[s] for s in HIGH_BETA_SECTORS if s in sector_perf]
    lb_scores = [sector_perf[s] for s in LOW_BETA_SECTORS if s in sector_perf]

    hb_avg = sum(hb_scores) / len(hb_scores) if hb_scores else 0
    lb_avg = sum(lb_scores) / len(lb_scores) if lb_scores else 0
    spread = hb_avg - lb_avg

    if spread > 3.0:
        appetite = "STRONG_RISK_ON"
        label    = "Aggressive risk appetite — institutions rotating into cyclicals"
    elif spread > 1.0:
        appetite = "RISK_ON"
        label    = "Moderate risk preference"
    elif spread > -1.0:
        appetite = "NEUTRAL"
        label    = "No clear risk preference"
    elif spread > -3.0:
        appetite = "RISK_OFF"
        label    = "Defensive rotation — institutions reducing beta"
    else:
        appetite = "STRONG_RISK_OFF"
        label    = "Flight to safety — institutions hiding in defensives"

    return {
        "ok": True,
        "appetite": appetite,
        "label": label,
        "high_beta_avg": round(hb_avg, 2),
        "low_beta_avg": round(lb_avg, 2),
        "spread": round(spread, 2),
    }


def compute_breadth_thrust(breadth_history: List[Dict]) -> Dict:
    """
    Count "thrust days" — days where >65% of stocks advanced.
    Rare signal. Historically precedes 10%+ rallies within 3 months.
    Used by tactical AMCs (PMS desks) for entry timing.

    Args:
        breadth_history: list of {date, advances, declines, ratio} from get_breadth_history()
    Returns:
        Dict with thrust count, total days, thrust ratio, signal.
    """
    if not breadth_history or len(breadth_history) < 5:
        return {"ok": False, "message": "Insufficient breadth data"}

    total   = len(breadth_history)
    thrusts = []

    for snap in breadth_history:
        adv = snap.get("advances", 0)
        dec = snap.get("declines", 0)
        total_stocks = adv + dec
        if total_stocks > 0:
            adv_pct = adv / total_stocks
            if adv_pct >= 0.65:
                thrusts.append({
                    "date": snap.get("date", ""),
                    "adv_pct": round(adv_pct * 100, 1),
                    "advances": adv,
                    "declines": dec,
                })

    thrust_count = len(thrusts)
    thrust_ratio = round((thrust_count / total) * 100, 1) if total else 0

    if thrust_count >= 3:
        signal = "STRONG_THRUST"
        label  = f"{thrust_count} thrust days in {total}-day window — rare bullish signal (historically precedes 10%+ rallies)"
    elif thrust_count >= 1:
        signal = "SINGLE_THRUST"
        label  = f"{thrust_count} thrust day — watch for confirmation"
    else:
        signal = "NO_THRUST"
        label  = "No breadth thrust — rally lacks broad participation"

    return {
        "ok": True,
        "thrust_count": thrust_count,
        "total_days": total,
        "thrust_ratio": thrust_ratio,
        "signal": signal,
        "label": label,
        "thrust_days": thrusts[-3:],  # Last 3 thrust days
    }


def compute_fii_institutional_footprint(institutions: List[Dict]) -> Dict:
    """
    Analyze FII institution types: who is accumulating vs distributing.
    Long-only funds buying + hedge funds selling = stealth accumulation.
    Hedge funds buying + long-only selling = short-term trade, likely reversal.

    Args:
        institutions: list from get_fii_institutions() with institution_name, type, buy/sell
    Returns:
        Dict with net flows by type, accumulation/distribution signal.
    """
    if not institutions or len(institutions) < 3:
        return {"ok": False, "message": "Insufficient institutional data"}

    # Group by institution type
    type_flows = {}
    for inst in institutions:
        inst_type = inst.get("institution_type", "Unknown")
        buy_val   = inst.get("buy_value_cr", 0) or 0
        sell_val  = inst.get("sell_value_cr", 0) or 0
        net       = buy_val - sell_val

        if inst_type not in type_flows:
            type_flows[inst_type] = {"buy": 0, "sell": 0, "net": 0, "count": 0}
        type_flows[inst_type]["buy"]  += buy_val
        type_flows[inst_type]["sell"] += sell_val
        type_flows[inst_type]["net"]  += net
        type_flows[inst_type]["count"] += 1

    # Classify each type
    type_signals = {}
    for t, flows in type_flows.items():
        net = flows["net"]
        if net > 500:
            type_signals[t] = "ACCUMULATING"
        elif net > 100:
            type_signals[t] = "MILD_BUYING"
        elif net > -100:
            type_signals[t] = "NEUTRAL"
        elif net > -500:
            type_signals[t] = "MILD_SELLING"
        else:
            type_signals[t] = "DISTRIBUTING"

    # Overall signal
    long_only_net  = type_flows.get("Long Only", {}).get("net", 0)
    hedge_fund_net = type_flows.get("Hedge Fund", {}).get("net", 0)

    if long_only_net > 500 and hedge_fund_net < -200:
        signal = "STEALTH_ACCUMULATION"
        label  = "Long-only funds buying, hedge funds selling — smart money accumulating on dips"
    elif long_only_net < -500 and hedge_fund_net > 200:
        signal = "DISTRIBUTION"
        label  = "Long-only funds exiting, hedge funds buying — institutional distribution phase"
    elif long_only_net > 200 and hedge_fund_net > 200:
        signal = "CONSENSUS_BUY"
        label  = "Both long-only and hedge funds buying — strong institutional conviction"
    elif long_only_net < -200 and hedge_fund_net < -200:
        signal = "CONSENSUS_SELL"
        label  = "Both long-only and hedge funds selling — broad institutional exit"
    else:
        signal = "MIXED"
        label  = "No clear institutional consensus"

    return {
        "ok": True,
        "signal": signal,
        "label": label,
        "type_flows": {t: {"net_cr": round(f["net"]), "count": f["count"]}
                       for t, f in type_flows.items()},
        "type_signals": type_signals,
    }


def format_institutional_signals(signals: Dict) -> str:
    """
    Format all institutional signals into a readable Telegram block.
    """
    lines = ["🏦 *Institutional Signals (Smart Money)*"]
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")

    sr = signals.get("sector_regime", {})
    if sr.get("ok"):
        emoji = "🟢" if "OFFENSIVE" in sr["regime"] else ("🔴" if "DEFENSIVE" in sr["regime"] else "⚪")
        lines.append(f"{emoji} *Sector Regime:* {sr['label']}")
        if sr.get("leaders"):
            ldr = ", ".join(f"{s} {v:+.1f}%" for s, v in sr["leaders"])
            lines.append(f"   Leaders: {ldr}")
        if sr.get("laggards"):
            lag = ", ".join(f"{s} {v:+.1f}%" for s, v in sr["laggards"])
            lines.append(f"   Laggards: {lag}")

    vs = signals.get("volatility_setup", {})
    if vs.get("ok"):
        emoji = "🔥" if vs["percentile"] <= 20 else ("⚠️" if vs["percentile"] >= 80 else "📊")
        lines.append(f"{emoji} *Vol Setup:* VIX {vs['vix_current']:.1f} ({vs['percentile']}th percentile)")
        lines.append(f"   {vs['label']}")

    ra = signals.get("risk_appetite", {})
    if ra.get("ok"):
        emoji = "🟢" if "RISK_ON" in ra["appetite"] else ("🔴" if "RISK_OFF" in ra["appetite"] else "⚪")
        lines.append(f"{emoji} *Risk Appetite:* {ra['label']}")
        lines.append(f"   High-beta avg: {ra['high_beta_avg']:+.1f}% | Low-beta avg: {ra['low_beta_avg']:+.1f}%")

    bt = signals.get("breadth_thrust", {})
    if bt.get("ok"):
        emoji = "🚀" if bt["signal"] == "STRONG_THRUST" else ("📊" if bt["signal"] == "SINGLE_THRUST" else "⚪")
        lines.append(f"{emoji} *Breadth:* {bt['label']}")

    fi = signals.get("fii_footprint", {})
    if fi.get("ok"):
        emoji = "🟢" if "ACCUMULATION" in fi["signal"] else ("🔴" if "DISTRIBUTION" in fi["signal"] else "⚪")
        lines.append(f"{emoji} *FII Footprint:* {fi['label']}")
        for t, sig in fi.get("type_signals", {}).items():
            net = fi.get("type_flows", {}).get(t, {}).get("net_cr", 0)
            lines.append(f"   {t}: {sig} (₹{net:+,} Cr)")

    return "\n".join(lines)
