"""
Mechanism Mapping Table — Event → India Sector Impact

Maps macro events to transmission chains, affected sectors, and actionable implications.
Used by formatters to add WHY and SO WHAT to every data point.

Design: Static dict, zero computation cost. Just look up triggered mechanisms.
"""

# ═══════════════════════════════════════════════════════════════════════
# MECHANISM MAP: Event → Transmission → Sector Impact → Action
# ═══════════════════════════════════════════════════════════════════════

MECHANISM_MAP = {
    "oil_spike": {
        "trigger": {"symbol": "BZ=F", "threshold_pct": 1.5, "direction": "up"},
        "tiers": [
            {"min": 1.5, "max": 3.0, "severity": "MILD", "label": "Monitor"},
            {"min": 3.0, "max": 5.0, "severity": "MODERATE", "label": "Sector impact likely"},
            {"min": 5.0, "max": 8.0, "severity": "ELEVATED", "label": "Policy response watch"},
            {"min": 8.0, "max": 999, "severity": "SPIKE", "label": "Systemic impact"},
        ],
        "transmission": "CAD widens, inflation rises, RBI hawkish risk, OMC margins compress",
        "bearish": ["OMC (BPCL, HPCL, IOC)", "Oil importers"],
        "bullish": ["Upstream (ONGC, Oil India)", "Reliance (refining)"],
        "caution": ["OMC recovery if de-escalation"],
        "india_impact": "Current account deficit +0.3-0.5% of GDP per $10 oil rise",
        "action": "Sell OMCs, buy upstream if sustained",
    },
    "oil_crash": {
        "trigger": {"symbol": "BZ=F", "threshold_pct": -2.0, "direction": "down"},
        "tiers": [
            {"min": 2.0, "max": 4.0, "severity": "MILD", "label": "OMC margin boost"},
            {"min": 4.0, "max": 8.0, "severity": "MODERATE", "label": "CAD improvement"},
            {"min": 8.0, "max": 999, "severity": "ELEVATED", "label": "Growth stimulus"},
        ],
        "transmission": "CAD improves, inflation eases, OMC margin expansion",
        "bearish": ["Upstream (ONGC, Oil India)"],
        "bullish": ["OMC (BPCL, HPCL, IOC)", "Rate-sensitive (Banks, Auto, Realty)"],
        "india_impact": "CAD improvement, inflation eases, RBI room to cut",
        "action": "Buy OMCs, add rate-sensitive sectors",
    },
    "dxy_strength": {
        "trigger": {"symbol": "DX-Y.NYB", "threshold_pct": 0.8, "direction": "up"},
        "tiers": [
            {"min": 0.8, "max": 1.5, "severity": "MILD", "label": "FII cost rising"},
            {"min": 1.5, "max": 2.5, "severity": "MODERATE", "label": "EM outflow pressure"},
            {"min": 2.5, "max": 999, "severity": "ELEVATED", "label": "Dollar crisis for EM"},
        ],
        "transmission": "FII outflow pressure, INR weakens, IT revenue in INR rises",
        "bearish": ["Import-heavy (Oil marketing, Electronics)", "EM allocation"],
        "bullish": ["IT exporters (TCS, INFY, HCLTECH)", "Pharma exports (DRREDDY, SUNPHARMA)"],
        "caution": ["IT (medium-term US slowdown risk if sustained)"],
        "india_impact": "FII cost of capital rises, EM allocation shrinks",
        "action": "Rotate into IT exporters, avoid import-heavy",
    },
    "dxy_weakness": {
        "trigger": {"symbol": "DX-Y.NYB", "threshold_pct": -0.8, "direction": "down"},
        "transmission": "FII inflow tailwind, INR strengthens, IT revenue headwind",
        "bearish": ["IT exporters (weaker USD revenue)"],
        "bullish": ["FII favorites (HDFCBANK, ICICIBANK, RELIANCE)", "Importers"],
        "india_impact": "EM allocation increases, carry trade attractive",
        "action": "Add FII favorites, reduce IT overweight",
    },
    "china_pmi_miss": {
        "trigger": {"keyword": "china pmi", "threshold": "miss"},
        "transmission": "Metal demand slows, copper/iron ore fall, export slowdown",
        "bearish": ["Metal (TATASTEEL, JSWSTEEL, HINDALCO, VEDL)", "Mining (COALINDIA)"],
        "bullish": [],
        "india_impact": "Export revenue hit for metal companies, 10-15% of Nifty metal earnings",
        "action": "Sell metal stocks, wait for China stimulus",
    },
    "china_stimulus": {
        "trigger": {"keyword": "china stimulus"},
        "transmission": "Metal demand recovery, copper/iron ore rally, infrastructure spending",
        "bearish": [],
        "bullish": ["Metal (TATASTEEL, JSWSTEEL, HINDALCO, VEDL)", "Mining (COALINDIA)"],
        "india_impact": "Metal export revenue recovery, commodity cycle turn",
        "action": "Buy metal stocks on confirmation",
    },
    "us_yield_rise": {
        "trigger": {"symbol": "^TNX", "threshold_pct": 3.0, "direction": "up"},
        "tiers": [
            {"min": 3.0, "max": 5.0, "severity": "MILD", "label": "Carry pressure"},
            {"min": 5.0, "max": 8.0, "severity": "MODERATE", "label": "FII outflow likely"},
            {"min": 8.0, "max": 999, "severity": "ELEVATED", "label": "EM crisis risk"},
        ],
        "transmission": "FII outflow, USDINR pressure, bank NIM compression, rate-sensitive hit",
        "bearish": ["Rate-sensitive (Banks, Realty, Auto)", "Small caps"],
        "bullish": ["IT (short-term weaker INR)"],
        "caution": ["IT (medium-term US recession risk)"],
        "india_impact": "FII carry trade unwinds, 10Y spread narrows",
        "action": "Reduce rate-sensitive, add IT on dips with stoploss",
    },
    "us_yield_fall": {
        "trigger": {"symbol": "^TNX", "threshold_pct": -3.0, "direction": "down"},
        "transmission": "FII inflow, USDINR stable, bank NIM expansion, rate-sensitive rally",
        "bearish": ["IT (stronger INR headwind)"],
        "bullish": ["Banks (NIM expansion)", "Realty", "Auto", "NBFCs"],
        "india_impact": "Carry trade attractive, FII allocation to EM rises",
        "action": "Buy rate-sensitive sectors, reduce IT overweight",
    },
    "gold_rally": {
        "trigger": {"symbol": "GC=F", "threshold_pct": 1.5, "direction": "up"},
        "transmission": "Safe haven bid, inflation hedge, INR gold price rises",
        "bearish": [],
        "bullish": ["Jewelers (TITAN)", "Gold loan NBFCs (MUTHOOTFIN, MANAPPURAM)"],
        "india_impact": "Import bill rises if sustained, CAD pressure",
        "action": "Add TITAN on dips, watch CAD",
    },
    "vix_spike": {
        "trigger": {"symbol": "^INDIAVIX", "threshold_pct": 15.0, "direction": "up"},
        "transmission": "Option premium expansion, hedging demand, retail panic",
        "bearish": ["High-beta (Small caps, Leveraged)", "Momentum stocks"],
        "bullish": ["Insurance (SBILIFE, HDFCLIFE)", "Put sellers (if mean reversion)"],
        "india_impact": "Volatility premium rises, mean reversion likely if >25",
        "action": "Buy insurance, sell small caps, wait for VIX mean reversion",
    },
    "vix_collapse": {
        "trigger": {"symbol": "^INDIAVIX", "threshold_pct": -15.0, "direction": "down"},
        "transmission": "Complacency building, option premium compression, retail FOMO",
        "bearish": ["Insurance (premium compression)"],
        "bullish": ["High-beta (Small caps)", "Momentum stocks"],
        "india_impact": "Complacency zone — contrarian risk if sustained <12",
        "action": "Add small caps cautiously, watch for complacency signal",
    },
    "fed_hawkish": {
        "trigger": {"keyword": "fed rate hike", "keyword2": "fed hawkish"},
        "transmission": "Rate differential narrows, FII exits EM, USDINR pressure",
        "bearish": ["All EM assets", "Rate-sensitive (Banks, Realty)"],
        "bullish": ["IT (short-term USD/INR boost)"],
        "caution": ["IT (medium-term US slowdown risk)"],
        "india_impact": "FII outflow risk, INR depreciation, risk-off globally",
        "action": "Reduce rate-sensitive, add IT on dips with stoploss",
    },
    "fed_dovish": {
        "trigger": {"keyword": "fed rate cut", "keyword2": "fed dovish"},
        "transmission": "Rate differential widens, FII inflows to EM, USDINR stable",
        "bearish": ["IT (stronger INR headwind)"],
        "bullish": ["FII favorites (HDFCBANK, RELIANCE)", "Rate-sensitive"],
        "india_impact": "EM allocation increases, liquidity support",
        "action": "Add FII favorites, buy rate-sensitive",
    },
    "boj_hike": {
        "trigger": {"keyword": "boj", "keyword2": "jpy strength"},
        "transmission": "Carry unwind — JPY funding currency exits EM, global risk-off",
        "bearish": ["All EM assets", "Small caps", "High-beta"],
        "bullish": ["Defensive (FMCG, Pharma)"],
        "india_impact": "Global EM selling pressure, FII outflows",
        "action": "Defensive positioning, reduce high-beta",
    },
    "rbi_rate_cut": {
        "trigger": {"keyword": "rbi cut", "keyword2": "rbi rate"},
        "transmission": "Bank NIM compression short-term, credit growth long-term",
        "bearish": ["Banks (short-term NIM hit)"],
        "bullish": ["Rate-sensitive (Realty, Auto, NBFC)", "Banks (long-term credit growth)"],
        "india_impact": "Easing cycle = liquidity support for equities",
        "action": "Buy rate-sensitive sectors, add banks on dip",
    },
    "rbi_rate_hike": {
        "trigger": {"keyword": "rbi rate hike"},
        "transmission": "Bank NIM expansion short-term, credit slowdown long-term",
        "bearish": ["Rate-sensitive (Realty, Auto, NBFC)", "Leveraged companies"],
        "bullish": ["Banks (NIM expansion short-term)"],
        "india_impact": "Tightening cycle = headwind for equities",
        "action": "Sell rate-sensitive, add banks for NIM play",
    },
    "inr_depreciation": {
        "trigger": {"symbol": "USDINR=X", "threshold_pct": 0.5, "direction": "up"},
        "transmission": "IT revenue boost, gold INR price rise, FII exit cost rise",
        "bearish": ["Importers (Oil, Electronics)"],
        "bullish": ["IT (TCS, INFY, HCLTECH)", "Pharma exports"],
        "india_impact": "Mixed — IT benefits, oil import bill rises",
        "action": "Buy IT exporters, watch oil-INR composite",
    },
    "inr_appreciation": {
        "trigger": {"symbol": "USDINR=X", "threshold_pct": -0.5, "direction": "down"},
        "transmission": "IT revenue headwind, FII entry cost falls, gold INR price falls",
        "bearish": ["IT exporters (weaker USD revenue)"],
        "bullish": ["Importers", "FII favorites"],
        "india_impact": "FII inflow tailwind, IT margin pressure",
        "action": "Add importers, reduce IT overweight",
    },
    "copper_rally": {
        "trigger": {"symbol": "HG=F", "threshold_pct": 2.0, "direction": "up"},
        "transmission": "Growth demand signal, infrastructure spending, metal cycle turn",
        "bearish": [],
        "bullish": ["Metal (HINDALCO, VEDL)", "Infrastructure (LT)", "Capital goods"],
        "india_impact": "Growth signal — Dr. Copper bullish for cyclicals",
        "action": "Buy metal and infra stocks",
    },
    "copper_crash": {
        "trigger": {"symbol": "HG=F", "threshold_pct": -2.0, "direction": "down"},
        "transmission": "Growth slowdown signal, recession risk, demand destruction",
        "bearish": ["Metal (TATASTEEL, JSWSTEEL, HINDALCO)", "Cyclicals"],
        "bullish": ["Defensive (FMCG, Pharma)"],
        "india_impact": "Recession signal — rotate to defensives",
        "action": "Sell cyclicals, add defensives",
    },
    "hyg_stress": {
        "trigger": {"symbol": "HYG", "threshold_pct": -1.5, "direction": "down"},
        "transmission": "US credit stress, liquidity tightening, EM outflows",
        "bearish": ["All risk assets", "Small caps", "Leveraged companies"],
        "bullish": ["Gold", "Defensive (FMCG, Pharma)"],
        "india_impact": "Global liquidity tightening — FII outflow risk",
        "action": "Defensive positioning, reduce leverage",
    },
}


def _get_severity(abs_change: float, tiers: list) -> tuple:
    """Determine severity tier from absolute change percentage."""
    for tier in tiers:
        if tier["min"] <= abs_change < tier["max"]:
            return tier["severity"], tier["label"]
    return "MILD", "Monitor"


def detect_triggered_mechanisms(anchor_data: list) -> list:
    """
    Check macro anchors against mechanism triggers.
    Returns list of triggered mechanism keys with details.

    Args:
        anchor_data: list of dicts with symbol, price, change_pct, name
    Returns:
        list of dicts: {"key": "oil_spike", "trigger_value": 2.3, "details": {...}}
    """
    if not anchor_data:
        return []

    triggered = []

    # Build lookup by symbol
    anchor_by_symbol = {}
    for a in anchor_data:
        sym = a.get("symbol", "")
        anchor_by_symbol[sym] = a

    for key, mechanism in MECHANISM_MAP.items():
        trigger = mechanism.get("trigger", {})

        # Symbol-based triggers
        if "symbol" in trigger:
            sym = trigger["symbol"]
            anchor = anchor_by_symbol.get(sym)
            if not anchor:
                continue

            change = anchor.get("change_pct", 0)
            threshold = trigger.get("threshold_pct", 0)
            direction = trigger.get("direction", "up")

            if direction == "up" and change >= threshold:
                severity, label = _get_severity(change, mechanism.get("tiers", []))
                triggered.append({
                    "key": key,
                    "trigger_value": change,
                    "severity": severity,
                    "label": label,
                    "details": mechanism,
                    "anchor": anchor,
                })
            elif direction == "down" and change <= threshold:
                severity, label = _get_severity(abs(change), mechanism.get("tiers", []))
                triggered.append({
                    "key": key,
                    "trigger_value": change,
                    "severity": severity,
                    "label": label,
                    "details": mechanism,
                    "anchor": anchor,
                })

    return triggered


def format_mechanism_triggers(triggered: list) -> str:
    """
    Format triggered mechanisms into a readable block.
    Shows WHAT triggered, WHY it matters, and SO WHAT for India.
    """
    if not triggered:
        return ""

    lines = ["🌍 *MACRO TRIGGERS:*"]

    for t in triggered:
        key = t["key"]
        details = t["details"]
        value = t["trigger_value"]
        anchor = t.get("anchor", {})
        anchor_name = anchor.get("name", key)

        # Trigger line with severity
        direction = "↑" if value > 0 else "↓"
        severity = t.get("severity", "MILD")
        label = t.get("label", "Monitor")
        lines.append(f"⦿ {anchor_name} {direction}{abs(value):.1f}% ({severity} — {label})")

        # Transmission
        lines.append(f"   {details['transmission']}")

        # Sector impact
        bearish = details.get("bearish", [])
        bullish = details.get("bullish", [])
        caution = details.get("caution", [])
        if bearish:
            lines.append(f"   BEARISH: {', '.join(bearish)}")
        if bullish:
            lines.append(f"   BULLISH: {', '.join(bullish)}")
        if caution:
            lines.append(f"   CAUTION: {', '.join(caution)}")

        # India impact
        india = details.get("india_impact", "")
        if india:
            lines.append(f"   India: {india}")

    return "\n".join(lines)


def get_mechanism_for_news(headline: str) -> dict:
    """
    Check if a news headline triggers any mechanism.
    Returns mechanism details or None.
    Uses word-boundary matching to avoid false positives (e.g. "fed" in "federal").
    """
    import re
    if not headline:
        return None

    headline_lower = headline.lower()

    for key, mechanism in MECHANISM_MAP.items():
        trigger = mechanism.get("trigger", {})
        keyword = trigger.get("keyword", "")
        keyword2 = trigger.get("keyword2", "")

        # Word-boundary match: all words in keyword must appear as whole words
        if keyword:
            words = keyword.split()
            if all(re.search(r'\b' + re.escape(w) + r'\b', headline_lower) for w in words):
                return {"key": key, "details": mechanism}
        if keyword2:
            words = keyword2.split()
            if all(re.search(r'\b' + re.escape(w) + r'\b', headline_lower) for w in words):
                return {"key": key, "details": mechanism}

    return None


def get_india_linkage_for_event(event_key: str) -> str:
    """
    Get a concise India linkage string for a mechanism event.
    Used in news formatting to add SO WHAT.
    """
    mechanism = MECHANISM_MAP.get(event_key)
    if not mechanism:
        return ""

    india = mechanism.get("india_impact", "")
    bearish = mechanism.get("bearish", [])
    bullish = mechanism.get("bullish", [])

    parts = []
    if india:
        parts.append(india)
    if bearish:
        parts.append(f"BEARISH: {', '.join(bearish[:2])}")
    if bullish:
        parts.append(f"BULLISH: {', '.join(bullish[:2])}")

    return " | ".join(parts)
