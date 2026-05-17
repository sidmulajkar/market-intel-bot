"""
Derivative Turnover Ratio — F&O volume / Cash market volume.
High ratio = speculation dominant (retail FOMO).
Rising ratio = top signal. Falling = smart money in cash.
"""
from typing import Dict, List, Optional


def compute_turnover_ratio(fno_volume: float, cash_volume: float) -> Dict:
    """
    Compute derivative turnover ratio.
    ratio > 3x = bubble territory (extreme speculation)
    ratio > 2x = high speculation
    ratio 1-2x = normal
    ratio < 1x = cash dominant
    """
    if cash_volume <= 0:
        return {"ok": False, "message": "No cash volume data"}

    ratio = fno_volume / cash_volume

    if ratio > 3.0:
        signal = "EXTREME SPECULATION — bubble territory"
    elif ratio > 2.0:
        signal = "HIGH SPECULATION — retail FOMO likely"
    elif ratio > 1.5:
        signal = "ABOVE AVERAGE — elevated speculation"
    elif ratio > 1.0:
        signal = "NORMAL — balanced"
    elif ratio > 0.5:
        signal = "CASH DOMINANT — institutional preference"
    else:
        signal = "VERY LOW — derivatives inactive"

    return {
        "ok": True,
        "ratio": round(ratio, 2),
        "fno_volume": round(fno_volume),
        "cash_volume": round(cash_volume),
        "signal": signal,
    }


def format_turnover(turnover: Dict) -> str:
    """Format turnover ratio for AI prompt."""
    if not turnover.get("ok"):
        return ""

    lines = [f"[Derivative Turnover Ratio]"]
    lines.append(f"  F&O / Cash: {turnover['ratio']:.2f}x — {turnover['signal']}")
    lines.append(f"  F&O Volume: {turnover['fno_volume']:,} | Cash: {turnover['cash_volume']:,}")

    if turnover["ratio"] > 2.5:
        lines.append(f"\n  ⚠️ Derivative turnover elevated — speculation dominant.")
        lines.append(f"  Historically, ratios >3x precede corrections.")

    return "\n".join(lines)


if __name__ == "__main__":
    result = compute_turnover_ratio(1500000, 800000)
    print(format_turnover(result))
