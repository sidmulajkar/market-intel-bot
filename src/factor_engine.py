"""
Factor Attribution Engine — Decompose Nifty returns into style factors.
Tells you WHY the market moved, not just that it moved.

Factors:
  - Momentum (12M return proxy)
  - Value (P/E, P/B inverse)
  - Quality (earnings yield proxy)
  - Size (large vs small cap ratio)

All computation from existing data — zero new API calls.
"""
import statistics
from typing import Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# FACTOR DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

FACTOR_LABELS = {
    "momentum": "MOMENTUM (12M return trend)",
    "value": "VALUE (P/E, P/B inverse)",
    "quality": "QUALITY (earnings yield)",
    "size": "SIZE (large vs small cap)",
}


def compute_momentum_factor(nifty_closes: list, window: int = 252) -> Dict:
    """
    Momentum factor: 12-month return proxy.
    Positive = market trending up (momentum-driven rally).
    Negative = market trending down (momentum collapse).
    """
    if not nifty_closes or len(nifty_closes) < min(window, 60):
        return {"ok": False, "message": "Insufficient price data"}

    current = nifty_closes[-1]
    # 12-month return
    if len(nifty_closes) >= window:
        yoy_return = ((current / nifty_closes[-window]) - 1) * 100
    else:
        yoy_return = ((current / nifty_closes[0]) - 1) * 100

    # 1-month return (short-term momentum)
    month_ago_idx = max(0, len(nifty_closes) - 21)
    month_return = ((current / nifty_closes[month_ago_idx]) - 1) * 100

    # 3-month return
    three_month_idx = max(0, len(nifty_closes) - 63)
    three_month_return = ((current / nifty_closes[three_month_idx]) - 1) * 100

    # Momentum regime
    if yoy_return > 15:
        regime = "STRONG UPTREND"
        contribution = "BULLISH"
    elif yoy_return > 5:
        regime = "MILD UPTREND"
        contribution = "MILDLY BULLISH"
    elif yoy_return > -5:
        regime = "SIDEWAYS"
        contribution = "NEUTRAL"
    elif yoy_return > -15:
        regime = "MILD DOWNTREND"
        contribution = "MILDLY BEARISH"
    else:
        regime = "STRONG DOWNTREND"
        contribution = "BEARISH"

    return {
        "ok": True,
        "factor": "momentum",
        "yoy_return": round(yoy_return, 2),
        "month_return": round(month_return, 2),
        "three_month_return": round(three_month_return, 2),
        "regime": regime,
        "contribution": contribution,
    }


def compute_value_factor(pe: float = None, pb: float = None,
                          pe_history: list = None) -> Dict:
    """
    Value factor: P/E and P/B relative to historical.
    Low P/E = cheap = value factor positive.
    High P/E = expensive = value factor negative.
    """
    if pe is None:
        return {"ok": False, "message": "No P/E data"}

    # Compute P/E percentile if history available
    pe_percentile = None
    if pe_history and len(pe_history) >= 20:
        sorted_pe = sorted(pe_history)
        below = sum(1 for v in sorted_pe if v < pe)
        pe_percentile = round((below / len(sorted_pe)) * 100)

    # Value signal
    if pe_percentile is not None:
        if pe_percentile < 20:
            signal = "DEEP VALUE — historically cheap"
            contribution = "STRONGLY BULLISH"
        elif pe_percentile < 40:
            signal = "BELOW AVERAGE valuation"
            contribution = "BULLISH"
        elif pe_percentile < 60:
            signal = "FAIR VALUE"
            contribution = "NEUTRAL"
        elif pe_percentile < 80:
            signal = "ABOVE AVERAGE valuation"
            contribution = "BEARISH"
        else:
            signal = "EXPENSIVE — limited upside"
            contribution = "STRONGLY BEARISH"
    else:
        signal = "PE = {:.1f}x (no historical context)".format(pe)
        contribution = "NEUTRAL"

    return {
        "ok": True,
        "factor": "value",
        "pe": pe,
        "pb": pb,
        "pe_percentile": pe_percentile,
        "signal": signal,
        "contribution": contribution,
    }


def compute_quality_factor(earnings_yield: float = None,
                           us_10y: float = None,
                           erp: float = None) -> Dict:
    """
    Quality factor: Earnings yield vs risk-free rate (ERP).
    High ERP = equities offering good risk premium = quality factor positive.
    Low ERP = equities expensive vs bonds = quality factor negative.
    """
    if earnings_yield is None:
        return {"ok": False, "message": "No earnings yield data"}

    # Compute ERP if not provided
    if erp is None and us_10y is not None:
        india_gsec = 7.1  # Approximate
        erp = earnings_yield - india_gsec

    if erp is not None:
        if erp > 4:
            signal = "HIGH risk premium — equities attractive vs bonds"
            contribution = "BULLISH"
        elif erp > 2:
            signal = "MODERATE risk premium — fair compensation"
            contribution = "NEUTRAL"
        elif erp > 0:
            signal = "LOW risk premium — limited margin of safety"
            contribution = "BEARISH"
        else:
            signal = "NEGATIVE risk premium — bonds better than equities"
            contribution = "STRONGLY BEARISH"
    else:
        signal = f"EY={earnings_yield:.1f}% (no risk-free rate for ERP)"
        contribution = "NEUTRAL"

    return {
        "ok": True,
        "factor": "quality",
        "earnings_yield": earnings_yield,
        "erp": erp,
        "signal": signal,
        "contribution": contribution,
    }


def compute_size_factor(nifty_close: float = None,
                        smallcap_index: float = None,
                        smallcap_history: list = None) -> Dict:
    """
    Size factor: Large cap vs Small cap relative performance.
    Small caps outperforming = risk-on, broad rally.
    Large caps outperforming = defensive, narrow rally.
    """
    if nifty_close is None or smallcap_index is None:
        return {"ok": False, "message": "No index data for size factor"}

    # Small cap / Nifty ratio
    ratio = smallcap_index / nifty_close if nifty_close > 0 else 0

    # Compute ratio percentile if history available
    ratio_percentile = None
    if smallcap_history and len(smallcap_history) >= 20:
        ratios = [s / nifty_close for s, n in smallcap_history
                  if n > 0] if isinstance(smallcap_history[0], (list, tuple)) else smallcap_history
        if len(ratios) >= 20:
            sorted_ratios = sorted(ratios)
            below = sum(1 for v in sorted_ratios if v < ratio)
            ratio_percentile = round((below / len(sorted_ratios)) * 100)

    # Size signal
    if ratio_percentile is not None:
        if ratio_percentile > 80:
            signal = "SMALL CAPS outperforming — risk-on, broad rally"
            contribution = "BULLISH (breadth)"
        elif ratio_percentile > 50:
            signal = "Small caps performing — healthy market"
            contribution = "MILDLY BULLISH"
        elif ratio_percentile > 20:
            signal = "Large caps outperforming — defensive rotation"
            contribution = "NEUTRAL"
        else:
            signal = "Large caps dominating — narrow rally, fragility"
            contribution = "BEARISH (breadth)"
    else:
        signal = f"Small/Nifty ratio: {ratio:.4f}"
        contribution = "NEUTRAL"

    return {
        "ok": True,
        "factor": "size",
        "ratio": round(ratio, 4),
        "ratio_percentile": ratio_percentile,
        "signal": signal,
        "contribution": contribution,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# FULL FACTOR ATTRIBUTION
# ═══════════════════════════════════════════════════════════════════════════════

def compute_factor_attribution(snapshot: dict, nifty_closes: list = None,
                                pe_history: list = None) -> Dict:
    """
    Compute all 4 factors and determine which is driving the market.
    Returns structured analysis for AI prompt injection.
    """
    factors = {}

    # 1. Momentum
    momentum = compute_momentum_factor(nifty_closes)
    if momentum.get("ok"):
        factors["momentum"] = momentum

    # 2. Value
    pe = snapshot.get("nifty_pe")
    pb = snapshot.get("nifty_pb")
    value = compute_value_factor(pe, pb, pe_history)
    if value.get("ok"):
        factors["value"] = value

    # 3. Quality
    earnings_yield = 100 / pe if pe and pe > 0 else None
    us_10y = snapshot.get("us_10y")
    quality = compute_quality_factor(earnings_yield, us_10y)
    if quality.get("ok"):
        factors["quality"] = quality

    # 4. Size (need smallcap data — use Nifty 50 as proxy for large cap)
    nifty_close = snapshot.get("nifty_close")
    # Smallcap index not always available — use breadth as proxy
    ad_ratio = snapshot.get("advance_decline_ratio")
    if ad_ratio is not None:
        # A/D ratio as size factor proxy (broad = small caps participating)
        if ad_ratio > 1.5:
            size_signal = "BROAD rally — small caps participating"
            size_contribution = "BULLISH (breadth)"
        elif ad_ratio > 1.0:
            size_signal = "NORMAL breadth — balanced"
            size_contribution = "NEUTRAL"
        elif ad_ratio > 0.7:
            size_signal = "NARROW rally — large caps only"
            size_contribution = "BEARISH (breadth)"
        else:
            size_signal = "VERY NARROW — only few stocks driving index"
            size_contribution = "STRONGLY BEARISH (breadth)"
        factors["size"] = {
            "ok": True, "factor": "size",
            "signal": size_signal, "contribution": size_contribution,
        }

    # Determine dominant factor
    bullish_count = sum(1 for f in factors.values() if "BULLISH" in f.get("contribution", ""))
    bearish_count = sum(1 for f in factors.values() if "BEARISH" in f.get("contribution", ""))

    if bullish_count > bearish_count:
        dominant = "BULLISH factors dominant"
    elif bearish_count > bullish_count:
        dominant = "BEARISH factors dominant"
    else:
        dominant = "FACTORS MIXED — no clear direction"

    return {
        "ok": bool(factors),
        "factors": factors,
        "dominant": dominant,
        "bullish_count": bullish_count,
        "bearish_count": bearish_count,
    }


def format_factor_attribution(attribution: Dict) -> str:
    """Format factor attribution for AI prompt injection."""
    if not attribution.get("ok"):
        return ""

    lines = ["[Factor Attribution — Why Did the Market Move?]"]

    for name, data in attribution.get("factors", {}).items():
        label = FACTOR_LABELS.get(name, name.upper())
        contrib = data.get("contribution", "UNKNOWN")
        icon = "🟢" if "BULLISH" in contrib else "🔴" if "BEARISH" in contrib else "⚪"
        lines.append(f"  {icon} {label}")
        lines.append(f"    → {data.get('signal', 'N/A')}")
        lines.append(f"    Contribution: {contrib}")

    lines.append(f"\n  Overall: {attribution.get('dominant', 'UNKNOWN')}")
    lines.append(f"  Bullish factors: {attribution.get('bullish_count', 0)} | Bearish: {attribution.get('bearish_count', 0)}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def run_factor_analysis(snapshot: dict, nifty_closes: list = None,
                        pe_history: list = None) -> Dict:
    """Full factor analysis pipeline."""
    attribution = compute_factor_attribution(snapshot, nifty_closes, pe_history)
    formatted = format_factor_attribution(attribution)

    return {
        "ok": attribution.get("ok", False),
        "attribution": attribution,
        "formatted": formatted,
    }


if __name__ == "__main__":
    # Test with dummy data
    test_snapshot = {"nifty_pe": 22.4, "nifty_pb": 3.8, "us_10y": 4.5,
                     "nifty_close": 25400, "advance_decline_ratio": 0.9}
    test_closes = [20000 + i * 50 for i in range(252)]
    test_pe = [18 + i * 0.02 for i in range(252)]

    result = run_factor_analysis(test_snapshot, test_closes, test_pe)
    if result["ok"]:
        print(result["formatted"])
    else:
        print("No factor data available")
