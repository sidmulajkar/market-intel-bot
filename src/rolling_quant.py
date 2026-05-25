"""
Rolling Quant Engine — Statistical intelligence from stored daily snapshots.
Powers: percentile ranking, divergence detection, scenario matching,
correlation engine, seasonal patterns, relative value, mean reversion.

All computation in Python — zero extra API calls.
Reads from daily_market_snapshot, macro_anchor_snapshots, fii_dii_flows tables.
"""
import statistics
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from src.formatters import _ordinal


# ═══════════════════════════════════════════════════════════════════════════════
# 1. PERCENTILE RANKING ENGINE
# "Where does this value sit vs 1Y/2Y/3Y history?"
# ═══════════════════════════════════════════════════════════════════════════════

def percentile_rank(current: float, history: List[float]) -> Dict:
    """
    Compute percentile rank of current value vs historical distribution.
    Returns percentile (0-100), range, and label.
    """
    if not history or len(history) < 3:
        return {"percentile": None, "label": "insufficient data", "range": ""}

    sorted_h = sorted(history)
    n = len(sorted_h)
    # Clamp percentile to 0-100
    if current <= sorted_h[0]:
        percentile = 0
    elif current >= sorted_h[-1]:
        percentile = 100
    else:
        below = sum(1 for v in sorted_h if v < current)
        at_value = sum(1 for v in sorted_h if abs(v - current) < 1e-10)
        percentile = round(((below + 0.5 * at_value) / n) * 100)

    min_val = min(sorted_h)
    max_val = max(sorted_h)

    if percentile >= 95:
        label = "EXTREMELY ELEVATED"
    elif percentile >= 85:
        label = "ELEVATED"
    elif percentile >= 70:
        label = "ABOVE AVERAGE"
    elif percentile >= 40:
        label = "AVERAGE"
    elif percentile >= 20:
        label = "BELOW AVERAGE"
    elif percentile >= 10:
        label = "DEPRESSED"
    else:
        label = "EXTREMELY DEPRESSED"

    range_str = f"{min_val:.2f}-{max_val:.2f}"
    if current >= max_val * 0.99:
        range_str += " (at period high)"
    elif current <= min_val * 1.01:
        range_str += " (at period low)"

    return {
        "percentile": percentile,
        "label": label,
        "min": round(min_val, 4),
        "max": round(max_val, 4),
        "range": range_str,
        "n_samples": n,
    }


def rolling_z_score(current: float, history: List[float]) -> float:
    """
    Compute z-score of current value vs historical distribution.
    > 2.5 = extreme (mean reversion likely)
    < -2.5 = extreme low (mean reversion likely)
    """
    if not history or len(history) < 10:
        return 0.0
    mean = statistics.mean(history)
    std = statistics.stdev(history)
    if std == 0:
        return 0.0
    return round((current - mean) / std, 2)


def compute_all_percentiles(snapshot: dict, snapshots: list) -> Dict:
    """
    Compute percentile rankings for ALL metrics in a snapshot.
    snapshot: today's daily_market_snapshot dict
    snapshots: list of historical daily_market_snapshot dicts (252+ days)
    Returns dict of {metric: percentile_data} for every metric.
    """
    if not snapshots or len(snapshots) < 10:
        return {}

    metrics = [
        "nifty_pe", "nifty_pb", "india_vix", "cboe_vix", "vix_spread",
        "usdinr", "brent", "gold", "dxy", "us_10y", "copper",
        "fii_net", "dii_net", "pcr", "bull_bear_score", "fear_greed_score",
        "advance_decline_ratio", "momentum_12m", "carry_risk_index",
    ]

    results = {}
    for metric in metrics:
        current = snapshot.get(metric)
        if current is None:
            continue
        history = [s.get(metric) for s in snapshots if s.get(metric) is not None]
        if len(history) < 10:
            continue
        results[metric] = percentile_rank(current, history)
        results[metric]["z_score"] = rolling_z_score(current, history)
        results[metric]["current"] = current

    return results


def format_percentile_block(percentiles: Dict) -> str:
    """
    Format percentile rankings for AI prompt injection.
    Bloomberg-style: "Nifty PE: 22.4x (67th percentile, range: 18.1-24.8x)"
    """
    if not percentiles:
        return ""

    lines = ["[Percentile Rankings — Historical Context]"]
    metric_labels = {
        "nifty_pe": "Nifty P/E",
        "nifty_pb": "Nifty P/B",
        "india_vix": "India VIX",
        "cboe_vix": "CBOE VIX",
        "vix_spread": "VIX Spread",
        "usdinr": "USD/INR",
        "brent": "Brent Crude",
        "gold": "Gold",
        "dxy": "Dollar Index",
        "us_10y": "US 10Y Yield",
        "copper": "Copper",
        "fii_net": "FII Net Flow",
        "dii_net": "DII Net Flow",
        "pcr": "Put-Call Ratio",
        "bull_bear_score": "Bull/Bear Score",
        "fear_greed_score": "Fear & Greed",
        "advance_decline_ratio": "A/D Ratio",
        "momentum_12m": "12M Momentum",
        "carry_risk_index": "Carry Risk",
    }

    for metric, label in metric_labels.items():
        data = percentiles.get(metric)
        if not data or data.get("percentile") is None:
            continue
        pct = data["percentile"]
        current = data["current"]
        z = data.get("z_score", 0)
        rng = data["range"]

        # Determine z-score significance
        z_note = ""
        if abs(z) > 2.5:
            z_note = " ⚠️MEAN REVERSION ZONE"
        elif abs(z) > 2.0:
            z_note = " (elevated z-score)"

        lines.append(f"  {label}: {current:.2f} ({_ordinal(int(pct))} pct, range: {rng}){z_note}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. DIVERGENCE DETECTOR
# "When things that should move together STOP moving together"
# ═══════════════════════════════════════════════════════════════════════════════

def detect_divergences(snapshot: dict, prev_snapshots: list = None) -> List[Dict]:
    """
    Detect cross-asset divergences that signal hidden risk/opportunity.
    All inputs from daily_market_snapshot — zero API calls.

    Divergences detected:
    1. Gold + Dollar both rising (abnormal — systemic stress)
    2. Nifty up + Breadth down (narrow rally — fragility)
    3. VIX falling + FII selling (complacency trap)
    4. Copper falling + Nifty rising (growth proxy divergence)
    5. India VIX falling + CBOE VIX rising (global-local disconnect)
    """
    divergences = []

    # Helper: get 5-day change from snapshots
    def _get_5d_change(metric: str) -> float:
        if not prev_snapshots or len(prev_snapshots) < 5:
            return 0
        recent = [s.get(metric) for s in prev_snapshots[-5:] if s.get(metric) is not None]
        if len(recent) < 2:
            return 0
        return ((recent[-1] / recent[0]) - 1) * 100 if recent[0] != 0 else 0

    def _get_1d_change(metric: str) -> float:
        if not prev_snapshots or len(prev_snapshots) < 2:
            return 0
        vals = [s.get(metric) for s in prev_snapshots[-2:] if s.get(metric) is not None]
        if len(vals) < 2 or vals[0] == 0:
            return 0
        return ((vals[-1] / vals[0]) - 1) * 100

    # 1. Gold + Dollar both rising (abnormal)
    gold_chg = snapshot.get("gold", 0) or 0
    dxy_chg = snapshot.get("dxy", 0) or 0
    # Use 5-day changes if available from snapshots
    gold_5d = _get_5d_change("gold") if prev_snapshots else 0
    dxy_5d = _get_5d_change("dxy") if prev_snapshots else 0

    if gold_5d > 2 and dxy_5d > 1:
        divergences.append({
            "type": "gold_dollar_both_rising",
            "severity": "HIGH",
            "description": "Gold + Dollar both rising — flight to safety across ALL assets. Something is systemically wrong.",
            "asset_1": "Gold", "asset_1_change": round(gold_5d, 2),
            "asset_2": "DXY", "asset_2_change": round(dxy_5d, 2),
        })
    elif gold_5d > 2 and dxy_5d > 0.5:
        divergences.append({
            "type": "gold_dollar_both_rising",
            "severity": "MEDIUM",
            "description": "Gold rising alongside dollar — unusual. Inflation fear overriding dollar strength.",
            "asset_1": "Gold", "asset_1_change": round(gold_5d, 2),
            "asset_2": "DXY", "asset_2_change": round(dxy_5d, 2),
        })

    # 2. Nifty up + Breadth down (narrow rally)
    ad_ratio = snapshot.get("advance_decline_ratio")
    nifty_5d = _get_5d_change("nifty_close") if prev_snapshots else 0
    if ad_ratio is not None and ad_ratio < 0.7 and nifty_5d > 0.5:
        divergences.append({
            "type": "nifty_up_breadth_down",
            "severity": "MEDIUM",
            "description": f"Nifty rising but A/D ratio {ad_ratio:.2f} — rally driven by few heavy stocks, not broad participation.",
            "asset_1": "Nifty", "asset_1_change": round(nifty_5d, 2),
            "asset_2": "A/D Ratio", "asset_2_change": ad_ratio,
        })

    # 3. VIX falling + FII selling (complacency trap)
    vix_now = snapshot.get("india_vix")
    fii_now = snapshot.get("fii_net")
    if vix_now and fii_now and prev_snapshots and len(prev_snapshots) >= 5:
        vix_5d = _get_5d_change("india_vix")
        fii_recent = [s.get("fii_net", 0) for s in prev_snapshots[-5:] if s.get("fii_net") is not None]
        fii_trend = sum(fii_recent) if fii_recent else 0
        if vix_5d < -10 and fii_trend < -500:
            divergences.append({
                "type": "vix_falling_fii_selling",
                "severity": "MEDIUM",
                "description": f"VIX falling {vix_5d:+.1f}% but FII net ₹{fii_trend:+,.0f}Cr — complacency trap. Smart money leaving while retail is calm.",
                "asset_1": "India VIX", "asset_1_change": round(vix_5d, 2),
                "asset_2": "FII Net 5D", "asset_2_change": round(fii_trend, 0),
            })

    # 4. Copper falling + Nifty rising (Dr. Copper divergence)
    copper_5d = _get_5d_change("copper") if prev_snapshots else 0
    if copper_5d < -2 and nifty_5d > 1:
        divergences.append({
            "type": "copper_nifty_divergence",
            "severity": "MEDIUM",
            "description": f"Copper {copper_5d:+.1f}% (growth proxy falling) but Nifty {nifty_5d:+.1f}% — equities ignoring growth slowdown signal.",
            "asset_1": "Copper", "asset_1_change": round(copper_5d, 2),
            "asset_2": "Nifty", "asset_2_change": round(nifty_5d, 2),
        })

    # 5. India VIX falling + CBOE VIX rising (disconnect)
    cboe_now = snapshot.get("cboe_vix")
    if vix_now and cboe_now and prev_snapshots and len(prev_snapshots) >= 5:
        india_vix_5d = _get_5d_change("india_vix")
        cboe_vix_5d = _get_5d_change("cboe_vix")
        if india_vix_5d < -5 and cboe_vix_5d > 5:
            divergences.append({
                "type": "india_global_vix_disconnect",
                "severity": "HIGH",
                "description": f"India VIX {india_vix_5d:+.1f}% but CBOE VIX {cboe_vix_5d:+.1f}% — India disconnected from global risk. Either safe haven or lagging.",
                "asset_1": "India VIX", "asset_1_change": round(india_vix_5d, 2),
                "asset_2": "CBOE VIX", "asset_2_change": round(cboe_vix_5d, 2),
            })

    # 6. Gold-VIX divergence (price vs fear disconnect)
    gold_now = snapshot.get("gold")
    if gold_now and vix_now and prev_snapshots and len(prev_snapshots) >= 5:
        try:
            from src.formatters import get_percentile_value
            gold_pct = get_percentile_value("gold", gold_now, "1Y")
            vix_pct = get_percentile_value("india_vix", vix_now, "1Y")
            if gold_pct is not None and vix_pct is not None:
                if gold_pct < 55 and vix_pct > 65:
                    divergences.append({
                        "type": "gold_vix_divergence",
                        "severity": "HIGH",
                        "description": f"Gold at {_ordinal(int(gold_pct))} %ile (middle of range) while VIX at {_ordinal(int(vix_pct))} %ile (elevated fear). "
                                       f"Gold not pricing fear — either fear overstated or gold will catch up.",
                        "asset_1": "Gold", "asset_1_pct": round(gold_pct),
                        "asset_2": "India VIX", "asset_2_pct": round(vix_pct),
                    })
                elif gold_pct > 60 and vix_pct < 30:
                    divergences.append({
                        "type": "gold_vix_divergence",
                        "severity": "MEDIUM",
                        "description": f"Gold at {_ordinal(int(gold_pct))} %ile (elevated) while VIX at {_ordinal(int(vix_pct))} %ile (calm). "
                                       f"Gold pricing risk VIX doesn't see — possible hidden stress.",
                        "asset_1": "Gold", "asset_1_pct": round(gold_pct),
                        "asset_2": "India VIX", "asset_2_pct": round(vix_pct),
                    })
        except Exception:
            pass

    return divergences


def format_divergences(divergences: List[Dict]) -> str:
    """Format divergences for AI prompt injection."""
    if not divergences:
        return ""

    lines = ["[Cross-Asset Divergences Detected]"]
    for d in divergences:
        severity_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(d["severity"], "⚪")
        lines.append(f"  {severity_icon} {d['type']}: {d['description']}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. SEASONAL PATTERN ENGINE
# "Markets have known seasonal patterns — encode them as signals"
# ═══════════════════════════════════════════════════════════════════════════════

# Monthly seasonal patterns (hardcoded from market research)
MONTHLY_PATTERNS = {
    1: {"label": "January Effect", "bias": "bullish", "smallcap_outperform": True,
        "note": "Tax-loss selling reversal, small caps outperform, new year portfolio rebalancing"},
    2: {"label": "Pre-Budget Positioning", "bias": "neutral", "smallcap_outperform": False,
        "note": "Budget anticipation, sector rotation based on budget expectations"},
    3: {"label": "Fiscal Year End", "bias": "bearish", "smallcap_outperform": False,
        "note": "FII selling (fiscal year end redemptions), window dressing, tax-related trades"},
    4: {"label": "New FY Start", "bias": "bullish", "smallcap_outperform": True,
        "note": "Fresh allocations, new financial year optimism, FII buying resumes"},
    5: {"label": "Sell in May", "bias": "neutral", "smallcap_outperform": False,
        "note": "Global 'sell in May' effect, pre-monsoon positioning"},
    6: {"label": "Monsoon + Expiry", "bias": "volatile", "smallcap_outperform": False,
        "note": "Monsoon onset uncertainty, F&O monthly expiry + quarter end, higher volatility"},
    7: {"label": "Monsoon Watch", "bias": "neutral", "smallcap_outperform": False,
        "note": "Monsoon progress drives agri/FMCG, Q1 earnings season"},
    8: {"label": "Earnings Season", "bias": "neutral", "smallcap_outperform": False,
        "note": "Q1 results in full swing, stock-specific action"},
    9: {"label": "Quarter End", "bias": "volatile", "smallcap_outperform": False,
        "note": "Quarter end window dressing, derivatives expiry effects"},
    10: {"label": "Post-Summer Rally", "bias": "bullish", "smallcap_outperform": True,
        "note": "FII buying resumes post summer, Q2 earnings, festival season"},
    11: {"label": "Festival Season Rally", "bias": "bullish", "smallcap_outperform": True,
        "note": "Diwali rally, SWF year-end rebalancing, consumer spending"},
    12: {"label": "Santa Rally + Year End", "bias": "bullish", "smallcap_outperform": True,
        "note": "Santa rally, year-end portfolio rebalancing, SWF allocations"},
}

# Weekly patterns
WEEKLY_PATTERNS = {
    0: {"label": "Monday", "note": "Gap risk — weekend news unpriced"},
    1: {"label": "Tuesday", "note": "Direction established post Monday gap"},
    2: {"label": "Wednesday", "note": "Mid-week — often trending day"},
    3: {"label": "Thursday", "note": "Weekly expiry → options pinning, low range day"},
    4: {"label": "Friday", "note": "Position squaring, volume spike, direction bias"},
}


def compute_seasonal_context(snapshot: dict = None) -> Dict:
    """
    Compute seasonal context based on current date.
    Returns monthly pattern, weekly pattern, and event proximity.
    """
    now = datetime.now()
    month = now.month
    weekday = now.weekday()  # 0=Monday, 4=Friday

    monthly = MONTHLY_PATTERNS.get(month, {})
    weekly = WEEKLY_PATTERNS.get(weekday, {})

    # Monthly expiry week detection (last Thursday of month)
    # Find last Thursday of current month
    import calendar
    last_day = calendar.monthrange(now.year, month)[1]
    last_thursday = None
    for day in range(last_day, 0, -1):
        d = datetime(now.year, month, day)
        if d.weekday() == 3:  # Thursday
            last_thursday = d
            break

    is_expiry_week = False
    is_day_before_expiry = False
    if last_thursday:
        days_to_expiry = (last_thursday.date() - now.date()).days
        if 0 <= days_to_expiry <= 4:
            is_expiry_week = True
        if days_to_expiry == 1:
            is_day_before_expiry = True

    result = {
        "month": month,
        "month_name": now.strftime("%B"),
        "monthly_pattern": monthly,
        "weekday": weekday,
        "weekly_pattern": weekly,
        "is_expiry_week": is_expiry_week,
        "is_day_before_expiry": is_day_before_expiry,
    }

    # Add VIX context for expiry
    if is_expiry_week and snapshot:
        vix = snapshot.get("india_vix")
        if vix and vix > 20:
            result["expiry_volatility_note"] = f"VIX {vix:.1f} + expiry week = elevated gamma effects expected"
        max_pain = snapshot.get("max_pain")
        if max_pain:
            result["max_pain_note"] = f"Max pain gravity at {max_pain:.0f} — pinning risk"

    return result


def format_seasonal_context(seasonal: Dict) -> str:
    """Format seasonal context for AI prompt."""
    if not seasonal:
        return ""

    lines = ["[Seasonal Context]"]

    monthly = seasonal.get("monthly_pattern", {})
    if monthly:
        lines.append(f"  Month: {seasonal['month_name']} — {monthly.get('label', 'Unknown')}")
        lines.append(f"  Bias: {monthly.get('bias', 'neutral').upper()}")
        lines.append(f"  Note: {monthly.get('note', '')}")

    weekly = seasonal.get("weekly_pattern", {})
    if weekly:
        lines.append(f"  Day: {weekly.get('label', '')} — {weekly.get('note', '')}")

    if seasonal.get("is_expiry_week"):
        lines.append("  ⚡ EXPIRY WEEK — elevated IV, gamma effects dominant")
    if seasonal.get("is_day_before_expiry"):
        lines.append("  ⚡ DAY BEFORE EXPIRY — max pain gravity strongest")
    if seasonal.get("expiry_volatility_note"):
        lines.append(f"  {seasonal['expiry_volatility_note']}")
    if seasonal.get("max_pain_note"):
        lines.append(f"  {seasonal['max_pain_note']}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. SCENARIO MATCHING ENGINE
# "Find historical periods with similar conditions → what happened next?"
# ═══════════════════════════════════════════════════════════════════════════════

def compute_scenario_match(snapshot: dict, snapshots: list,
                           min_matches: int = 3) -> Dict:
    """
    Find historical dates where similar conditions existed,
    then compute forward returns from those dates.

    Current conditions fingerprint:
      FII z-score, VIX regime, PCR, DXY direction, carry stress, etc.

    Matches if ≥3 of 5 conditions are within thresholds of historical values.
    """
    if not snapshots or len(snapshots) < 60:
        return {"ok": False, "message": f"Need 60+ days of snapshots, have {len(snapshots)}"}

    # Build current fingerprint
    current_fp = {
        "fii_net": snapshot.get("fii_net"),
        "india_vix": snapshot.get("india_vix"),
        "pcr": snapshot.get("pcr"),
        "bull_bear_score": snapshot.get("bull_bear_score"),
        "nifty_pe": snapshot.get("nifty_pe"),
    }

    # Filter out None values
    current_fp = {k: v for k, v in current_fp.items() if v is not None}

    if len(current_fp) < 3:
        return {"ok": False, "message": "Insufficient current data for scenario matching"}

    # Define matching thresholds (how close a historical value must be)
    thresholds = {
        "fii_net": lambda c, h: abs(c - h) < 1500,       # ±1500 Cr
        "india_vix": lambda c, h: abs(c - h) < 4,         # ±4 VIX points
        "pcr": lambda c, h: abs(c - h) < 0.3,             # ±0.3 PCR
        "bull_bear_score": lambda c, h: abs(c - h) < 20,  # ±20 score
        "nifty_pe": lambda c, h: abs(c - h) < 3,          # ±3 PE points
    }

    matches = []

    for i, hist in enumerate(snapshots):
        if i < 10 or i >= len(snapshots) - 5:
            continue  # Skip early days and last 5 days (need forward returns)

        # Count matching conditions
        match_count = 0
        total_conditions = 0
        for metric, current_val in current_fp.items():
            hist_val = hist.get(metric)
            if hist_val is None:
                continue
            total_conditions += 1
            check = thresholds.get(metric)
            if check and check(current_val, hist_val):
                match_count += 1

        if total_conditions < 3:
            continue

        match_ratio = match_count / total_conditions
        if match_ratio >= 0.6:  # ≥60% of conditions matched
            # Compute forward returns
            hist_nifty = hist.get("nifty_close")
            if hist_nifty is None:
                continue

            # Find forward returns at 5D, 10D, 20D
            fwd_returns = {}
            for fwd_days in [5, 10, 20]:
                if i + fwd_days < len(snapshots):
                    fwd_nifty = snapshots[i + fwd_days].get("nifty_close")
                    if fwd_nifty and hist_nifty > 0:
                        fwd_returns[f"{fwd_days}d"] = round(
                            ((fwd_nifty / hist_nifty) - 1) * 100, 2
                        )

            if fwd_returns:
                matches.append({
                    "date": hist.get("date"),
                    "match_ratio": round(match_ratio * 100),
                    "fwd_returns": fwd_returns,
                    "nifty_at_match": hist_nifty,
                })

    if len(matches) < min_matches:
        return {"ok": False, "message": f"Only {len(matches)} matches found, need {min_matches}"}

    # Compute summary statistics
    avg_returns = {}
    worst_returns = {}
    best_returns = {}
    for fwd in ["5d", "10d", "20d"]:
        vals = [m["fwd_returns"].get(fwd) for m in matches if m["fwd_returns"].get(fwd) is not None]
        if vals:
            avg_returns[fwd] = round(statistics.mean(vals), 2)
            worst_returns[fwd] = round(min(vals), 2)
            best_returns[fwd] = round(max(vals), 2)

    # Directional accuracy (bearish if majority of 5D returns negative)
    bearish_count = sum(1 for m in matches if m["fwd_returns"].get("5d", 0) < 0)
    bearish_pct = round((bearish_count / len(matches)) * 100)

    return {
        "ok": True,
        "matches": len(matches),
        "avg_returns": avg_returns,
        "worst_returns": worst_returns,
        "best_returns": best_returns,
        "bearish_base_rate": bearish_pct,
        "match_details": matches[:5],  # Top 5 matches
    }


def format_scenario_match(scenario: Dict) -> str:
    """Format scenario matching for AI prompt."""
    if not scenario.get("ok"):
        return ""

    lines = ["[Historical Scenario Match]"]
    lines.append(f"  Current conditions matched {scenario['matches']} historical periods:")

    avg = scenario.get("avg_returns", {})
    worst = scenario.get("worst_returns", {})
    best = scenario.get("best_returns", {})

    for fwd in ["5d", "10d", "20d"]:
        if fwd in avg:
            lines.append(f"  {fwd.upper()}: avg {avg[fwd]:+.2f}% | worst {worst.get(fwd, 0):+.2f}% | best {best.get(fwd, 0):+.2f}%")

    bear = scenario.get("bearish_base_rate", 50)
    lines.append(f"  Historical base rate bearish: {bear}%")

    if bear > 65:
        lines.append(f"  ⚠️ Conditions historically resolved bearish {bear}% of the time")
    elif bear < 35:
        lines.append(f"  📈 Conditions historically resolved bullish {100-bear}% of the time")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. ROLLING CORRELATION ENGINE
# "What relationships are active between signals?"
# ═══════════════════════════════════════════════════════════════════════════════

def _pearson_correlation(x: List[float], y: List[float]) -> Tuple[float, float]:
    """Compute Pearson correlation coefficient and p-value approximation."""
    n = len(x)
    if n < 10:
        return 0.0, 1.0

    mean_x = statistics.mean(x)
    mean_y = statistics.mean(y)
    std_x = statistics.stdev(x) if n > 1 else 1
    std_y = statistics.stdev(y) if n > 1 else 1

    if std_x == 0 or std_y == 0:
        return 0.0, 1.0

    cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y)) / (n - 1)
    r = cov / (std_x * std_y)

    # Approximate p-value using t-distribution
    if abs(r) >= 1:
        return r, 0.0
    t = r * math.sqrt((n - 2) / (1 - r**2))
    # Rough p-value approximation (2-tailed)
    df = n - 2
    p = 2 * math.exp(-0.717 * abs(t) - 0.416 * t**2) if df > 0 else 1.0
    p = min(1.0, max(0.0, p))

    return round(r, 4), round(p, 4)


def compute_rolling_correlations(snapshots: list, window: int = 90) -> Dict:
    """
    Compute rolling correlations between key signal pairs.
    Uses stored daily_market_snapshot data.
    window: number of days for correlation computation.
    """
    if not snapshots or len(snapshots) < window:
        return {"ok": False, "message": f"Need {window}+ days of snapshots"}

    # Extract metric series
    def _extract(metric: str) -> list:
        return [s.get(metric) for s in snapshots[-window:] if s.get(metric) is not None]

    fii = _extract("fii_net")
    nifty_1d = _extract("nifty_return_1d")
    pcr = _extract("pcr")
    vix = _extract("india_vix")
    dxy = _extract("dxy")
    gold = _extract("gold")
    brent = _extract("brent")

    # Helper: shift series for lead/lag correlations
    def _shift(series: list, lag: int) -> Tuple[list, list]:
        if lag > 0:
            return series[:-lag], series[lag:]
        elif lag < 0:
            return series[-lag:], series[:lag]
        return series, series

    pairs = {}

    # FII vs Next-day Nifty return (is FII a leading indicator?)
    if len(fii) >= 20 and len(nifty_1d) >= 20:
        fii_aligned, nifty_aligned = _shift(fii, -1)
        min_len = min(len(fii_aligned), len(nifty_aligned))
        if min_len >= 10:
            r, p = _pearson_correlation(fii_aligned[:min_len], nifty_aligned[:min_len])
            pairs["fii_vs_nifty_1d"] = {"correlation": r, "p_value": p, "sample_size": min_len,
                                         "interpretation": _interpret_corr(r, "FII flow", "next-day Nifty return")}

    # PCR vs 3-day Nifty return
    if len(pcr) >= 20 and len(nifty_1d) >= 20:
        # Compute 3-day cumulative return
        nifty_3d = []
        for i in range(2, len(nifty_1d)):
            cum = sum(nifty_1d[max(0, i-2):i+1])
            nifty_3d.append(cum)
        pcr_trimmed = pcr[2:]
        min_len = min(len(pcr_trimmed), len(nifty_3d))
        if min_len >= 10:
            r, p = _pearson_correlation(pcr_trimmed[:min_len], nifty_3d[:min_len])
            pairs["pcr_vs_nifty_3d"] = {"correlation": r, "p_value": p, "sample_size": min_len,
                                         "interpretation": _interpret_corr(r, "PCR", "3-day Nifty return")}

    # DXY change vs FII flow (dollar-FII relationship)
    if len(dxy) >= 20 and len(fii) >= 20:
        min_len = min(len(dxy), len(fii))
        if min_len >= 10:
            r, p = _pearson_correlation(dxy[:min_len], fii[:min_len])
            pairs["dxy_vs_fii"] = {"correlation": r, "p_value": p, "sample_size": min_len,
                                    "interpretation": _interpret_corr(r, "DXY", "FII flow")}

    # VIX change vs Nifty return (VIX as hedge signal)
    if len(vix) >= 20 and len(nifty_1d) >= 20:
        min_len = min(len(vix), len(nifty_1d))
        if min_len >= 10:
            r, p = _pearson_correlation(vix[:min_len], nifty_1d[:min_len])
            pairs["vix_vs_nifty"] = {"correlation": r, "p_value": p, "sample_size": min_len,
                                      "interpretation": _interpret_corr(r, "VIX", "Nifty return")}

    # Gold vs Dollar (should be negative — divergence detector)
    if len(gold) >= 20 and len(dxy) >= 20:
        min_len = min(len(gold), len(dxy))
        if min_len >= 10:
            r, p = _pearson_correlation(gold[:min_len], dxy[:min_len])
            pairs["gold_vs_dxy"] = {"correlation": r, "p_value": p, "sample_size": min_len,
                                     "interpretation": _interpret_corr(r, "Gold", "DXY")}

    # Brent vs Nifty (oil impact on India)
    if len(brent) >= 20 and len(nifty_1d) >= 20:
        min_len = min(len(brent), len(nifty_1d))
        if min_len >= 10:
            r, p = _pearson_correlation(brent[:min_len], nifty_1d[:min_len])
            pairs["brent_vs_nifty"] = {"correlation": r, "p_value": p, "sample_size": min_len,
                                        "interpretation": _interpret_corr(r, "Brent", "Nifty return")}

    return {"ok": True, "pairs": pairs, "window": window}


def _interpret_corr(r: float, var1: str, var2: str) -> str:
    """Human-readable interpretation of correlation coefficient."""
    strength = abs(r)
    direction = "positive" if r > 0 else "negative"

    if strength > 0.7:
        strength_label = "STRONG"
    elif strength > 0.4:
        strength_label = "MODERATE"
    elif strength > 0.2:
        strength_label = "WEAK"
    else:
        strength_label = "NO"

    if strength > 0.4:
        return f"{strength_label} {direction} correlation — {var1} is {'predictive of' if r > 0 else 'inversely related to'} {var2}"
    else:
        return f"{strength_label} correlation — {var1} and {var2} are independent"


def format_correlations(correlations: Dict) -> str:
    """Format correlation matrix for AI prompt."""
    if not correlations.get("ok"):
        return ""

    pairs = correlations.get("pairs", {})
    if not pairs:
        return ""

    from datetime import datetime
    lines = [f"[Rolling {correlations.get('window', 90)}-Day Correlations — computed {datetime.now().strftime('%Y-%m-%d')}]"]
    for pair_name, data in pairs.items():
        r = data["correlation"]
        p = data["p_value"]
        sig = "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.1 else ""
        lines.append(f"  {pair_name}: r={r:+.3f}{sig} (p={p:.3f})")
        lines.append(f"    → {data['interpretation']}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. RELATIVE VALUE ENGINE
# "Don't just show Nifty PE — show what it MEANS"
# ═══════════════════════════════════════════════════════════════════════════════

def compute_relative_value(snapshot: dict, snapshots: list,
                           us_snapshots: list = None) -> Dict:
    """
    Compute relative value metrics:
    1. Equity Risk Premium vs historical
    2. ERP vs global (India vs US)
    3. Nifty fair value bands
    4. Cross-asset ratios (Gold/Nifty)
    """
    result = {}

    # 1. Equity Risk Premium (Earnings Yield - Risk Free Rate)
    pe = snapshot.get("nifty_pe")
    us_10y = snapshot.get("us_10y")
    if pe and pe > 0:
        from src.valuation_engine import compute_equity_risk_premium
        earnings_yield = (1 / pe) * 100
        # India G-Sec ~7.1% (approximate; matches valuation_engine default)
        india_gsec = 7.1
        erp_result = compute_equity_risk_premium(earnings_yield, india_gsec)
        result["erp"] = {
            "value": erp_result["premium"],
            "earnings_yield": round(earnings_yield, 2),
            "risk_free_rate": india_gsec,
            "label": erp_result["label"],
        }

        # ERP percentile from stored data
        if snapshots:
            erp_history = []
            for s in snapshots:
                s_pe = s.get("nifty_pe")
                if s_pe and s_pe > 0:
                    erp_history.append(round((1 / s_pe) * 100 - india_gsec, 2))
            if len(erp_history) >= 20:
                result["erp"]["percentile"] = percentile_rank(erp_result["premium"], erp_history)

    # 2. ERP vs Global (India vs US)
    if us_10y and pe and pe > 0:
        # US ERP approximation: S&P 500 earnings yield (~5.5%) - US 10Y
        us_earnings_yield = 5.5  # Approximate S&P 500 earnings yield
        us_erp = round(us_earnings_yield - us_10y, 2)
        india_erp = result.get("erp", {}).get("value", 0)
        if india_erp and us_erp:
            erp_premium = round(india_erp - us_erp, 2)
            result["erp_vs_global"] = {
                "india_erp": india_erp,
                "us_erp": us_erp,
                "premium": erp_premium,
                "label": "ATTRACTIVE" if erp_premium > 1.5 else "MODERATE" if erp_premium > 0.5 else "COMPRESSED",
            }

    # 3. Nifty Fair Value Bands
    if snapshots:
        pe_values = [s.get("nifty_pe") for s in snapshots if s.get("nifty_pe") is not None]
        if pe_values and pe:
            avg_pe = statistics.mean(pe_values)
            # Implied EPS = price / PE
            nifty_close = snapshot.get("nifty_close")
            if nifty_close and pe > 0:
                implied_eps = nifty_close / pe
                result["fair_value"] = {
                    "bear_case_pe": 18.0,
                    "base_case_pe": round(avg_pe, 1),
                    "bull_case_pe": 24.0,
                    "implied_eps": round(implied_eps, 0),
                    "bear_case": round(18.0 * implied_eps, 0),
                    "base_case": round(avg_pe * implied_eps, 0),
                    "bull_case": round(24.0 * implied_eps, 0),
                    "current_price": nifty_close,
                }
                # Position relative to fair value
                base = result["fair_value"]["base_case"]
                if base > 0:
                    pct_from_base = round(((nifty_close / base) - 1) * 100, 1)
                    result["fair_value"]["pct_from_base"] = pct_from_base

    # 4. Cross-asset ratios
    gold = snapshot.get("gold")
    nifty_close = snapshot.get("nifty_close")
    if gold and nifty_close and nifty_close > 0:
        gold_nifty_ratio = round(gold / nifty_close, 6)
        result["gold_nifty_ratio"] = gold_nifty_ratio

        # Percentile of ratio
        if snapshots:
            ratios = []
            for s in snapshots:
                g = s.get("gold")
                n = s.get("nifty_close")
                if g and n and n > 0:
                    ratios.append(g / n)
            if len(ratios) >= 20:
                result["gold_nifty_pctile"] = percentile_rank(gold_nifty_ratio, ratios)

    return result


def format_relative_value(rv: Dict) -> str:
    """Format relative value for AI prompt."""
    if not rv:
        return ""

    lines = ["[Relative Value Analysis]"]

    # ERP
    erp = rv.get("erp", {})
    if erp.get("value") is not None:
        pctile = erp.get("percentile", {})
        pct_str = f" ({_ordinal(int(pctile.get('percentile', 0)))} percentile)" if pctile.get("percentile") else ""
        lines.append(f"  Equity Risk Premium: {erp['value']:+.2f}%{pct_str}")
        lines.append(f"    Earnings yield: {erp['earnings_yield']:.2f}% | Risk-free: {erp['risk_free_rate']:.2f}%")
        if erp["value"] < 2:
            lines.append(f"    ⚠️ ERP compressed — equities pricing in perfection, limited margin of safety")

    # ERP vs Global
    erp_global = rv.get("erp_vs_global", {})
    if erp_global.get("premium") is not None:
        lines.append(f"  India vs US ERP premium: {erp_global['premium']:+.2f}% — {erp_global['label']}")
        if erp_global["premium"] < 0.5:
            lines.append(f"    ⚠️ India's relative value advantage shrinking — FII rotation risk")

    # Fair Value
    fv = rv.get("fair_value", {})
    if fv.get("base_case"):
        pct = fv.get("pct_from_base", 0)
        lines.append(f"  Nifty Fair Value: Bear {fv['bear_case']:.0f} | Base {fv['base_case']:.0f} | Bull {fv['bull_case']:.0f}")
        lines.append(f"    Current: {fv['current_price']:.0f} ({pct:+.1f}% from base)")

    # Gold/Nifty ratio
    if rv.get("gold_nifty_ratio"):
        pctile = rv.get("gold_nifty_pctile", {})
        pct_str = f" ({_ordinal(int(pctile.get('percentile', 0)))} percentile)" if pctile.get("percentile") else ""
        lines.append(f"  Gold/Nifty ratio: {rv['gold_nifty_ratio']:.4f}{pct_str}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. MEAN REVERSION SIGNALS
# "When z-score > 2.5, mean reversion likely"
# ═══════════════════════════════════════════════════════════════════════════════

def compute_mean_reversion_signals(snapshots: list) -> Dict:
    """
    Compute mean reversion signals using 252-day z-scores.
    Z > 2.0 = extreme high (mean reversion DOWN likely)
    Z < -2.0 = extreme low (mean reversion UP likely)
    """
    if not snapshots or len(snapshots) < 60:
        return {"ok": False, "message": "Insufficient data", "signals": []}

    signals = []

    # FII mean reversion
    fii_vals = [s.get("fii_net") for s in snapshots if s.get("fii_net") is not None]
    if len(fii_vals) >= 60:
        current_fii = fii_vals[-1]
        z = rolling_z_score(current_fii, fii_vals)
        if abs(z) > 2.0:
            signals.append({
                "metric": "FII Net",
                "z_score": z,
                "current": current_fii,
                "signal": "EXTREME SELLING — mean reversion likely" if z < -2 else "EXTREME BUYING — mean reversion likely",
            })

    # PCR mean reversion
    pcr_vals = [s.get("pcr") for s in snapshots if s.get("pcr") is not None]
    if len(pcr_vals) >= 60:
        current_pcr = pcr_vals[-1]
        z = rolling_z_score(current_pcr, pcr_vals)
        if abs(z) > 2.0:
            signals.append({
                "metric": "PCR",
                "z_score": z,
                "current": current_pcr,
                "signal": "EXTREME PUT BUYING — squeeze fuel" if z > 2 else "EXTREME CALL BUYING — potential top",
            })

    # VIX mean reversion
    vix_vals = [s.get("india_vix") for s in snapshots if s.get("india_vix") is not None]
    if len(vix_vals) >= 60:
        current_vix = vix_vals[-1]
        z = rolling_z_score(current_vix, vix_vals)
        if abs(z) > 2.0:
            signals.append({
                "metric": "India VIX",
                "z_score": z,
                "current": current_vix,
                "signal": "EXTREME FEAR — contrarian buy" if z > 2 else "EXTREME COMPLACENCY — contrarian sell",
            })

    # Nifty PE mean reversion
    pe_vals = [s.get("nifty_pe") for s in snapshots if s.get("nifty_pe") is not None]
    if len(pe_vals) >= 60:
        current_pe = pe_vals[-1]
        z = rolling_z_score(current_pe, pe_vals)
        if abs(z) > 2.0:
            signals.append({
                "metric": "Nifty PE",
                "z_score": z,
                "current": current_pe,
                "signal": "EXTREMELY EXPENSIVE — valuation correction risk" if z > 2 else "EXTREMELY CHEAP — valuation opportunity",
            })

    return {"ok": True, "signals": signals} if signals else {"ok": False, "message": "No mean reversion signals active", "signals": []}


def format_mean_reversion(mr: Dict) -> str:
    """Format mean reversion signals for AI prompt."""
    if not mr.get("ok"):
        return ""

    lines = ["[Mean Reversion Signals — Z-Score > 2.0]"]
    for s in mr["signals"]:
        icon = "🔴" if s["z_score"] > 2 else "🟢"
        lines.append(f"  {icon} {s['metric']}: {s['current']:.2f} (z={s['z_score']:+.2f}) — {s['signal']}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# 8. REGIME CHANGE DETECTION (Statistical)
# "20D vs 60D rolling averages — change point detection"
# ═══════════════════════════════════════════════════════════════════════════════

def detect_statistical_regime_shifts(snapshots: list) -> List[Dict]:
    """
    Compare 20-day vs 60-day rolling averages to detect regime shifts.
    If 20D avg differs from 60D avg by > 1 std dev → regime shift.
    Multiple simultaneous shifts → structural shift, not noise.
    """
    if not snapshots or len(snapshots) < 60:
        return []

    shifts = []

    metrics = {
        "fii_net": "FII Flow",
        "india_vix": "India VIX",
        "pcr": "PCR",
        "bull_bear_score": "Bull/Bear Score",
        "advance_decline_ratio": "A/D Ratio",
    }

    for metric, label in metrics.items():
        vals = [s.get(metric) for s in snapshots if s.get(metric) is not None]
        if len(vals) < 60:
            continue

        avg_20 = statistics.mean(vals[-20:])
        avg_60 = statistics.mean(vals[-60:])
        std_60 = statistics.stdev(vals[-60:]) if len(vals[-60:]) > 1 else 1

        if std_60 == 0:
            continue

        diff = avg_20 - avg_60
        z_diff = diff / std_60

        if abs(z_diff) > 1.0:
            direction = "BULLISH" if z_diff > 0 and metric != "india_vix" else \
                       "BEARISH" if z_diff < 0 and metric != "india_vix" else \
                       "BEARISH" if z_diff > 0 and metric == "india_vix" else "BULLISH"
            # Adjust for metrics where higher = bearish
            if metric in ("india_vix",):
                direction = "BEARISH" if z_diff > 0 else "BULLISH"

            severity = "HIGH" if abs(z_diff) > 2 else "MEDIUM"
            shifts.append({
                "metric": label,
                "avg_20d": round(avg_20, 2),
                "avg_60d": round(avg_60, 2),
                "z_diff": round(z_diff, 2),
                "direction": direction,
                "severity": severity,
            })

    # If multiple high-severity shifts → structural shift
    high_shifts = [s for s in shifts if s["severity"] == "HIGH"]
    if len(high_shifts) >= 2:
        for s in shifts:
            s["note"] = "STRUCTURAL SHIFT — multiple signals confirming regime change"

    return shifts


def format_regime_shifts(shifts: List[Dict]) -> str:
    """Format regime shifts for AI prompt."""
    if not shifts:
        return ""

    lines = ["[Statistical Regime Change Detection — 20D vs 60D]"]
    for s in shifts:
        icon = "🔴" if s["severity"] == "HIGH" else "🟡"
        note = f" ⚠️{s['note']}" if s.get("note") else ""
        lines.append(f"  {icon} {s['metric']}: 20D avg {s['avg_20d']:.2f} vs 60D avg {s['avg_60d']:.2f} (z={s['z_diff']:+.2f}) → {s['direction']}{note}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN: Compute all rolling quant intelligence
# ═══════════════════════════════════════════════════════════════════════════════

def run_rolling_quant_engine(snapshot: dict, snapshots: list) -> Dict:
    """
    Full rolling quant engine — runs inside evening job.
    Returns all computed intelligence for prompt injection.
    """
    result = {}

    # 1. Percentile rankings
    result["percentiles"] = compute_all_percentiles(snapshot, snapshots)

    # 2. Divergence detection + persist to divergence_log
    result["divergences"] = detect_divergences(snapshot, snapshots)
    try:
        from src.db import log_divergence
        for div in result["divergences"]:
            log_divergence(
                divergence_type=div.get("type", "unknown"),
                asset_1=div.get("asset_1", ""),
                asset_2=div.get("asset_2", ""),
                severity=div.get("severity", "MEDIUM"),
                description=div.get("description", ""),
            )
    except Exception:
        pass  # divergence_log persistence is optional

    # 3. Seasonal context
    result["seasonal"] = compute_seasonal_context(snapshot)

    # 4. Scenario matching (needs 60+ days)
    result["scenario"] = compute_scenario_match(snapshot, snapshots)

    # 5. Mean reversion signals
    result["mean_reversion"] = compute_mean_reversion_signals(snapshots)

    # 6. Statistical regime shifts
    result["regime_shifts"] = detect_statistical_regime_shifts(snapshots)

    # 7. Relative value
    result["relative_value"] = compute_relative_value(snapshot, snapshots)

    # 8. Rolling correlations (computed weekly, not daily — check if needed)
    result["correlations"] = compute_rolling_correlations(snapshots)

    return result


def format_rolling_quant_block(quant_data: Dict) -> str:
    """Format all rolling quant intelligence for AI prompt injection."""
    blocks = []

    pctl = format_percentile_block(quant_data.get("percentiles", {}))
    if pctl:
        blocks.append(pctl)

    divs = format_divergences(quant_data.get("divergences", []))
    if divs:
        blocks.append(divs)

    seasonal = format_seasonal_context(quant_data.get("seasonal", {}))
    if seasonal:
        blocks.append(seasonal)

    scenario = format_scenario_match(quant_data.get("scenario", {}))
    if scenario:
        blocks.append(scenario)

    mr = format_mean_reversion(quant_data.get("mean_reversion", {}))
    if mr:
        blocks.append(mr)

    shifts = format_regime_shifts(quant_data.get("regime_shifts", []))
    if shifts:
        blocks.append(shifts)

    rv = format_relative_value(quant_data.get("relative_value", {}))
    if rv:
        blocks.append(rv)

    corr = format_correlations(quant_data.get("correlations", {}))
    if corr:
        blocks.append(corr)

    return "\n\n".join(blocks)
