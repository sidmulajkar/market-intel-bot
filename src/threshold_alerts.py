"""
Smart Threshold Alerts — Event-driven triggers for extraordinary market events.
Detects threshold breaches inside regular job runs and triggers additional alerts.
Still uses GitHub Actions — workflow_dispatch via API call.
"""
import os
import json
from datetime import datetime
from typing import Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# THRESHOLD DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

THRESHOLDS = {
    # Market Structure Events
    "nifty_crash": {
        "metric": "nifty_return_1d",
        "condition": "lt",
        "value": -1.5,
        "label": "NIFTY CRASH",
        "description": "Nifty fell >1.5% in one day",
        "severity": "HIGH",
    },
    "nifty_surge": {
        "metric": "nifty_return_1d",
        "condition": "gt",
        "value": 2.0,
        "label": "NIFTY SURGE",
        "description": "Nifty surged >2% in one day",
        "severity": "MEDIUM",
    },
    "vix_spike": {
        "metric": "vix_change_pct",
        "condition": "gt",
        "value": 20,
        "label": "VIX SPIKE",
        "description": "VIX spiked >20% in one day",
        "severity": "HIGH",
    },
    "fii_outflow_extreme": {
        "metric": "fii_net",
        "condition": "lt",
        "value": -3000,
        "label": "FII EXTREME OUTFLOW",
        "description": "FII single-day outflow >₹3,000Cr",
        "severity": "HIGH",
    },
    "pcr_extreme_high": {
        "metric": "pcr",
        "condition": "gt",
        "value": 1.5,
        "label": "PCR EXTREME HIGH",
        "description": "PCR crossed 1.5 — extreme put buying",
        "severity": "MEDIUM",
    },
    "pcr_extreme_low": {
        "metric": "pcr",
        "condition": "lt",
        "value": 0.6,
        "label": "PCR EXTREME LOW",
        "description": "PCR fell below 0.6 — extreme call buying / complacency",
        "severity": "MEDIUM",
    },
    "bull_bear_extreme_bear": {
        "metric": "bull_bear_score",
        "condition": "lt",
        "value": 20,
        "label": "BEARISH EXTREME",
        "description": "Bull/Bear score crossed below 20 — extreme bearish",
        "severity": "HIGH",
    },
    "bull_bear_extreme_bull": {
        "metric": "bull_bear_score",
        "condition": "gt",
        "value": 80,
        "label": "BULLISH EXTREME",
        "description": "Bull/Bear score crossed above 80 — extreme bullish",
        "severity": "MEDIUM",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# THRESHOLD CHECKER
# ═══════════════════════════════════════════════════════════════════════════════

def check_thresholds(current_values: Dict) -> List[Dict]:
    """
    Check current values against all thresholds.
    Returns list of breached thresholds with details.

    current_values: dict with metric names as keys (e.g., nifty_return_1d, fii_net, pcr, etc.)
    """
    breaches = []

    for name, threshold in THRESHOLDS.items():
        metric = threshold["metric"]
        value = current_values.get(metric)

        if value is None:
            continue

        condition = threshold["condition"]
        limit = threshold["value"]

        triggered = False
        if condition == "gt" and value > limit:
            triggered = True
        elif condition == "lt" and value < limit:
            triggered = True

        if triggered:
            breaches.append({
                "name": name,
                "label": threshold["label"],
                "description": threshold["description"],
                "severity": threshold["severity"],
                "metric": metric,
                "current_value": value,
                "threshold": limit,
                "condition": condition,
            })

    return breaches


def format_threshold_alerts(breaches: List[Dict], bull_bear: Dict = None,
                             fii_context: Dict = None, macro_context: Dict = None) -> str:
    """
    Format threshold breaches as a special alert message.
    This gets sent as an ADDITIONAL Telegram message (not replacing normal brief).
    """
    if not breaches:
        return ""

    lines = ["🚨 *THRESHOLD ALERT*"]
    lines.append("━" * 30)

    for b in breaches:
        icon = "🔴" if b["severity"] == "HIGH" else "🟡"
        lines.append(f"\n{icon} *{b['label']}*")
        lines.append(f"  {b['description']}")
        lines.append(f"  Current: {b['current_value']:.2f} | Threshold: {b['threshold']}")

    # Add context from bull/bear if available
    if bull_bear:
        lines.append(f"\n📊 *Context:*")
        lines.append(f"  Bull/Bear: {bull_bear.get('normalized_score', '?')}/100 ({bull_bear.get('label', '?')})")
        lines.append(f"  Confidence: {bull_bear.get('confidence', '?')}")

    if fii_context and fii_context.get("ok"):
        lines.append(f"  FII: ₹{fii_context.get('fii_net', 0):+,.0f}Cr (z={fii_context.get('fii_z_score', 0):+.2f})")

    if macro_context:
        vix = macro_context.get("vix_price", "?")
        lines.append(f"  VIX: {vix} ({macro_context.get('vix_regime', '?')})")

    # Action context from rule matrix
    lines.append(f"\n⚡ *Action Context:*")
    for b in breaches:
        if b["name"] == "nifty_crash":
            lines.append("  • Historical: Nifty >1.5% drop → average recovery 3-5 days")
            lines.append("  • Watch: DII absorption, VIX spike continuation, global risk")
        elif b["name"] == "vix_spike":
            lines.append("  • VIX spikes historically precede 2-3% additional downside")
            lines.append("  • Watch: PCR for hedging activity, FII for institutional response")
        elif b["name"] == "fii_outflow_extreme":
            lines.append("  • Extreme FII outflows → historically mark near-term bottoms (30D)")
            lines.append("  • Watch: DII absorption capacity, USD/INR stability, RBI intervention")
        elif b["name"] == "pcr_extreme_high":
            lines.append("  • Extreme put buying → contrarian bullish (squeeze fuel)")
            lines.append("  • Watch: OI changes at support levels, VIX for fear capitulation")
        elif b["name"] == "pcr_extreme_low":
            lines.append("  • Extreme call buying → complacency, correction risk")
            lines.append("  • Watch: OI changes at resistance, breadth for distribution signals")
        elif b["name"] == "bull_bear_extreme_bear":
            lines.append("  • Extreme bearish → contrarian buy zone historically")
            lines.append("  • Watch: breadth, FII reversal, DII accumulation")
        elif b["name"] == "bull_bear_extreme_bull":
            lines.append("  • Extreme bullish → late cycle, tight stops")
            lines.append("  • Watch: breadth divergence, FII distribution, VIX compression")

    lines.append("\n" + "━" * 30)
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN: Check and format threshold alerts
# ═══════════════════════════════════════════════════════════════════════════════

def run_threshold_check(snapshot: dict, bull_bear: Dict = None,
                        fii_context: Dict = None, macro_context: Dict = None) -> Dict:
    """
    Run threshold check against daily market snapshot.
    Returns breaches and formatted alert message.
    """
    # Build current values dict from snapshot
    current_values = {
        "nifty_return_1d": snapshot.get("nifty_return_1d"),
        "fii_net": snapshot.get("fii_net"),
        "pcr": snapshot.get("pcr"),
        "bull_bear_score": snapshot.get("bull_bear_score"),
    }

    # Compute VIX change if we have previous snapshot
    if snapshot.get("india_vix") and snapshot.get("_prev_vix"):
        prev_vix = snapshot["_prev_vix"]
        if prev_vix > 0:
            current_values["vix_change_pct"] = round(
                ((snapshot["india_vix"] / prev_vix) - 1) * 100, 1
            )

    breaches = check_thresholds(current_values)
    alert_text = format_threshold_alerts(breaches, bull_bear, fii_context, macro_context)

    return {
        "breaches": breaches,
        "alert_text": alert_text,
        "has_alerts": len(breaches) > 0,
    }
