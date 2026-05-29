"""
Consequence Engine — India Impact Multiplier Table

Computes rupee-denominated and percentage consequences for every macro variable.
Every data point needs 4 layers: ABSOLUTE → RELATIVE → PERCENTILE → CONSEQUENCE.

Design: Static lookup table, zero DB dependency, lightweight arithmetic.
Returns empty dict on any failure (consistent with project pattern).
"""
from src.formatters import _ordinal

# ── Sanity bounds for consequence engine (secondary guard after data_fetcher)
#    Wide absurdity bounds — data_fetcher's daily-change check is the primary guard.
_CONSEQUENCE_RANGES = {
    "brent":     (20, 300),
    "wti":       (10, 300),
    "usdinr":    (60, 200),
    "gold":      (500, 10000),
    "india_vix": (3, 150),
    "dxy":       (50, 200),
    "us_10y":    (0.1, 20.0),
    "copper":    (1, 20),
    "cboe_vix":  (5, 150),
    "hyg":       (20, 120),
}

# ═══════════════════════════════════════════════════════════════════════
# CONSEQUENCE MULTIPLIERS — India Impact Reference
# All multipliers are per-unit changes (per $1, per bps, per %, per ₹1)
# Ranges are used where historical estimates vary
# ═══════════════════════════════════════════════════════════════════════

CONSEQUENCE_MULTIPLIERS = {
    "brent": {
        "unit": "$/bbl",
        "description": "Brent Crude oil price",
        "per_unit": {
            "cad_usd_bn": {"value": 1.5, "label": "CAD stress", "format": "CAD impact ${:+.1f}B annualized"},
            "inr_ps": {"value": 3, "label": "INR pressure", "format": "INR pressure {:+.0f}ps"},
            "inflation_bps": {"value": 2, "label": "CPI impact", "format": "CPI {:+.0f}bps"},
            "omc_margin_pct": {"value": -0.5, "label": "OMC margins", "format": "OMC margins {:+.1f}%"},
        },
        "thresholds": {
            "stress": 90,    # above this = current account stress
            "elevated": 80,  # above this = watch zone
            "favorable": 70, # below this = tailwind
        },
        "sectors_bearish": ["OMC (BPCL, HPCL, IOC)", "Oil importers"],
        "sectors_bullish": ["Upstream (ONGC, Oil India)", "Reliance (refining)"],
    },
    "wti": {
        "unit": "$/bbl",
        "description": "WTI Crude oil price",
        "per_unit": {
            "cad_usd_bn": {"value": 1.2, "label": "CAD stress", "format": "CAD impact ${:+.1f}B annualized"},
            "inr_ps": {"value": 2.5, "label": "INR pressure", "format": "INR pressure {:+.0f}ps"},
        },
        "sectors_bearish": ["OMC (BPCL, HPCL, IOC)"],
        "sectors_bullish": ["Upstream (ONGC, Oil India)"],
    },
    "us_10y": {
        "unit": "%",
        "description": "US 10-Year Treasury Yield",
        "per_unit": {
            "fii_outflow_cr_per_bps": {"value": 17.5, "label": "FII outflow", "format": "FII outflow ~₹{:.0f}Cr per +50bps"},
            "bfsi_impact_pct": {"value": -0.3, "label": "BFSI impact", "format": "BFSI weight impact {:+.1f}%"},
        },
        "per_50bps": {
            "fii_outflow_cr": {"value": 875, "label": "FII outflow per 50bps", "format": "FII outflow pressure ~₹{:.0f}Cr per +50bps"},
        },
        "sectors_bearish": ["Rate-sensitive (Banks, Realty, Auto)", "Growth stocks"],
        "sectors_bullish": ["Banking NIM (if short-end stable)"],
    },
    "dxy": {
        "unit": "index",
        "description": "Dollar Index (DXY)",
        "per_unit": {
            "it_revenue_pct": {"value": 0.5, "label": "IT revenue", "format": "IT revenue {:+.1f}%"},
            "fii_exit_cr": {"value": 650, "label": "FII exit risk", "format": "FII exit risk ~₹{:.0f}Cr per +1%"},
            "pharma_export_pct": {"value": 0.3, "label": "Pharma exports", "format": "Pharma export {:+.1f}%"},
        },
        "sectors_bearish": ["EM assets broadly", "Metal (USD-denominated costs)"],
        "sectors_bullish": ["IT (TCS, INFY, WIPRO)", "Pharma exporters"],
    },
    "usdinr": {
        "unit": "₹/$",
        "description": "USD/INR exchange rate",
        "per_unit": {
            "it_revenue_pct": {"value": 0.8, "label": "IT revenue", "format": "IT revenue {:+.1f}%"},
            "oil_bill_cr": {"value": 14000, "label": "Oil import bill", "format": "Oil bill ₹{:+.0f}Cr/yr"},
            "gold_inr_pct": {"value": 1.0, "label": "Gold INR price", "format": "Gold INR {:+.0f}%"},
        },
        "sectors_bearish": ["Oil importers", "Companies with USD debt"],
        "sectors_bullish": ["IT exporters", "Pharma exporters", "Textile exporters"],
    },
    "india_vix": {
        "unit": "index",
        "description": "India VIX (fear gauge)",
        "per_unit": {
            "option_premium_pct": {"value": 2.0, "label": "Option premium", "format": "Option premium {:+.0f}%"},
        },
        "thresholds": {
            "high": 20,
            "extreme": 25,
            "low": 12,
        },
        "impact_high": "Retail SIP pause risk, hedging costs spike",
        "impact_low": "Complacency — contrarian caution",
    },
    "gold": {
        "unit": "$/oz",
        "description": "Gold futures",
        "per_100": {
            "import_bill_usd_bn": {"value": 3.0, "label": "Import bill", "format": "Import bill +${:.1f}B/yr per +$100"},
        },
        "sectors_bearish": ["Gold importers (CAD pressure)"],
        "sectors_bullish": ["Gold NBFCs (MUTHOOT, MANAPPURAM)", "TITAN (jewelry)"],
    },
    "copper": {
        "unit": "$/lb",
        "description": "Copper futures (Dr. Copper)",
        "interpretation": {
            "rising": "Growth demand signal, infrastructure spending, metal cycle turn",
            "falling": "Growth slowdown signal, demand destruction",
        },
        "sectors_bearish": ["Metal consumers if sustained high"],
        "sectors_bullish": ["Metal (HINDALCO, VEDL)", "Infrastructure (LT)", "Capital goods"],
    },
    "cboe_vix": {
        "unit": "index",
        "description": "CBOE VIX (global fear gauge)",
        "thresholds": {
            "high": 20,
            "extreme": 30,
            "low": 12,
        },
        "impact_high": "Global risk-off, EM selling pressure",
        "impact_extreme": "Panic mode — historical buying opportunity if fundamentals intact",
    },
    "hyg": {
        "unit": "$",
        "description": "US High Yield Bond ETF (credit stress proxy)",
        "interpretation": {
            "falling": "Credit stress rising, risk-off, liquidity tightening",
            "rising": "Risk appetite returning, credit spreads narrowing",
        },
    },
}


def _safe_float(val) -> float:
    """Safely convert to float, return 0 on failure."""
    try:
        if val is None:
            return 0.0
        return float(val)
    except (ValueError, TypeError):
        return 0.0


# Magnitude gate thresholds for consequence engine
# Suppress impacts below these levels (noise), flag above as material
_MAGNITUDE_FLOOR_CR = 500      # ₹500 Cr/yr minimum to show
_MAGNITUDE_MATERIAL_CR = 10_000  # ₹10,000 Cr/yr = material impact
_MAGNITUDE_FLOOR_USD_B = 0.5   # $0.5B minimum to show


def _apply_magnitude_gate(lines: list, details: list) -> tuple[list, list]:
    """Filter consequence lines by magnitude. Suppress negligible, flag material.

    Returns (filtered_lines, filtered_details).
    - Suppresses ₹ Cr impacts < ₹500 Cr
    - Suppresses $B impacts < $0.5B
    - Appends [MATERIAL] tag to impacts > ₹10,000 Cr
    """
    if not lines:
        return lines, details

    filtered_lines = []
    filtered_details = []

    for line, detail in zip(lines, details):
        suppressed = False

        # Check for ₹ Cr impacts
        if "Cr" in line:
            # Extract numeric value before "Cr" (handles negative signs)
            import re
            cr_matches = re.findall(r'₹\s*-?([0-9,]+(?:\.\d+)?)\s*Cr', line)
            for val_str in cr_matches:
                val = float(val_str.replace(",", ""))
                if val < _MAGNITUDE_FLOOR_CR:
                    suppressed = True
                    break
                # Flag material impacts
                if val > _MAGNITUDE_MATERIAL_CR and "[MATERIAL]" not in line:
                    line = line + " [MATERIAL]"

        # Check for $B impacts
        elif "B" in line and "$" in line:
            import re
            b_matches = re.findall(r'\$\s*([0-9,]+(?:\.\d+)?)\s*[Bb]', line)
            for val_str in b_matches:
                val = float(val_str.replace(",", ""))
                if val < _MAGNITUDE_FLOOR_USD_B:
                    suppressed = True
                    break

        if not suppressed:
            filtered_lines.append(line)
            filtered_details.append(detail)

    return filtered_lines, filtered_details


# Baseline estimates for regime impact — approximate 252-day averages
# Updated periodically as market regimes shift
_BASELINE = {
    "usdinr": 88.0,    # ~2024-2025 average, below current ~95
    "brent": 82.0,     # multi-year average
    "gold": 2800.0,    # 2024 average vs current ~4500
    "dxy": 104.0,      # typical range
    "us_10y": 4.2,     # post-2022 normal
    "wti": 75.0,
    "india_vix": 15.0,
    "copper": 4.5,
}


def _compute_regime_impact(variable: str, current_value: float) -> list:
    """
    Compute impact vs baseline when price is at extreme level.

    This fixes the "±0.0%" problem: when daily change is tiny but the price
    level is historically extreme, the regime impact matters more than the delta.

    Returns list of formatted impact lines (may be empty if not extreme).
    """
    baseline = _BASELINE.get(variable)
    if baseline is None or baseline == 0:
        return []

    deviation_pct = (current_value - baseline) / baseline * 100
    abs_deviation = abs(deviation_pct)

    # Threshold for regime impact escalation
    # DXY at 4% — dollar index rarely moves >4% from mean in a year
    threshold = 3.0 if variable == "india_vix" else 4.0 if variable == "dxy" else 5.0
    if abs_deviation < threshold:
        return []

    # VARIANCE CAP: If deviation > 30%, baseline/unit mismatch likely.
    # Suppress the line entirely — emitting 62% gold deviation destroys trust.
    if abs_deviation > 30.0:
        print(f"⚠️  Consequence engine: {variable} deviation {abs_deviation:.0f}% exceeds 30% cap — suppressing (likely baseline/unit mismatch)")
        return []

    spec = CONSEQUENCE_MULTIPLIERS.get(variable, {})
    direction = "above" if deviation_pct > 0 else "below"
    lines = []

    if variable == "usdinr":
        # Rupee depreciation vs baseline — directional only (no hedge model for exact numbers)
        if deviation_pct > 0:
            lines.append(f"INR ₹{current_value:.1f} vs ₹{baseline:.0f} baseline ({abs_deviation:.0f}% deviation): material tailwind to IT margins, elevated CAD pressure")
        else:
            lines.append(f"INR ₹{current_value:.1f} vs ₹{baseline:.0f} baseline ({abs_deviation:.0f}% deviation): IT margin headwind, CAD relief")

    elif variable == "brent":
        lines.append(f"Brent ${current_value:.0f} {direction} baseline ({abs(deviation_pct):.0f}%): elevated import costs, CPI pressure, OMC margin squeeze")

    elif variable == "wti":
        lines.append(f"WTI ${current_value:.0f} {direction} baseline ({abs(deviation_pct):.0f}%): CAD pressure, INR impact")

    elif variable == "gold":
        lines.append(f"Gold ${current_value:,.0f} {direction} baseline (${baseline:.0f}, {abs(deviation_pct):.0f}% deviation): import cost pressure")

    elif variable == "dxy":
        lines.append(f"DXY {direction} baseline by {abs(deviation_pct):.1f}% ({baseline:.1f} → {current_value:.1f})")

    elif variable == "us_10y":
        bps_diff = (current_value - baseline) * 100
        fii_dir = "outflow" if deviation_pct > 0 else "inflow"
        lines.append(f"US10Y {direction} baseline by {abs(bps_diff):.0f}bps: FII {fii_dir} pressure")

    elif variable == "india_vix":
        lines.append(f"VIX {direction} baseline by {abs(deviation_pct):.0f}% ({baseline:.1f} → {current_value:.1f})")

    elif variable == "copper":
        lines.append(f"Copper {direction} baseline by {abs(deviation_pct):.0f}% ({baseline:.2f} → {current_value:.2f})")

    return lines


def compute_consequence(variable: str, current_value: float, change_value: float = 0, change_pct: float = 0) -> dict:
    """
    Compute India-impact consequences for a macro variable.

    Args:
        variable: Key in CONSEQUENCE_MULTIPLIERS (e.g., "brent", "us_10y", "dxy")
        current_value: Current price/yield/rate
        change_value: Absolute change (e.g., +$5.20 for Brent)
        change_pct: Percentage change (e.g., +2.3%)

    Returns:
        dict with consequence labels and formatted lines, or {} on failure.
        Keys: "lines" (list[str]), "summary" (str), "severity" (str)
    """
    try:
        variable = variable.lower().replace("-", "_").replace("/", "_")
        spec = CONSEQUENCE_MULTIPLIERS.get(variable)
        if not spec:
            return {}

        current_value = _safe_float(current_value)
        change_value = _safe_float(change_value)
        change_pct = _safe_float(change_pct)

        if current_value == 0:
            return {}

        lines = []
        details = []

        # Per-unit multipliers (preserves direction)
        per_unit = spec.get("per_unit", {})
        for key, mult in per_unit.items():
            val = mult["value"]
            raw_impact = val * change_value if change_value != 0 else val * (current_value * change_pct / 100)
            if abs(raw_impact) > 0.01:  # only show meaningful impacts
                fmt = mult.get("format", f"{key}: {{:.1f}}")
                try:
                    lines.append(fmt.format(raw_impact))
                    details.append(mult["label"])
                except (KeyError, ValueError, IndexError):
                    lines.append(f"{mult['label']}: ~{raw_impact:.1f}")
                    details.append(mult["label"])

        # Regime impact: when price is at extreme level, show baseline deviation
        # instead of per-unit noise. Regime impact replaces ALL per-unit lines.
        regime_lines = _compute_regime_impact(variable, current_value)
        has_regime = bool(regime_lines)
        if has_regime:
            lines = regime_lines
            details = ["regime"] * len(regime_lines)

        # Per-50bps multipliers (for yields) — skip if regime impact active
        if not has_regime:
            per_50bps = spec.get("per_50bps", {})
            for key, mult in per_50bps.items():
                bps_change = abs(change_value) * 100 if abs(change_value) < 10 else abs(change_value)
                units_of_50 = bps_change / 50
                impact = mult["value"] * units_of_50
                if abs(impact) > 1:
                    fmt = mult.get("format", f"{key}: {{:.0f}}")
                    try:
                        lines.append(fmt.format(impact))
                        details.append(mult["label"])
                    except (KeyError, ValueError, IndexError):
                        lines.append(f"{mult['label']}: ~₹{impact:.0f}Cr")
                        details.append(mult["label"])

        # Per-$100 multipliers (for gold) — skip if regime impact active
        if not has_regime:
            per_100 = spec.get("per_100", {})
            for key, mult in per_100.items():
                units_of_100 = abs(change_value) / 100 if change_value != 0 else 0
                impact = mult["value"] * units_of_100
                if abs(impact) > 0.1:
                    fmt = mult.get("format", f"{key}: {{:.1f}}")
                    try:
                        lines.append(fmt.format(impact))
                        details.append(mult["label"])
                    except (KeyError, ValueError, IndexError):
                        lines.append(f"{mult['label']}: ~${impact:.1f}B")
                        details.append(mult["label"])

        # Threshold-based signals (check from most extreme to least)
        thresholds = spec.get("thresholds", {})
        severity = "NEUTRAL"
        if thresholds:
            # Upper thresholds: check from highest to lowest
            if current_value >= thresholds.get("extreme", 999):
                severity = "EXTREME"
            elif current_value >= thresholds.get("stress", 999):
                severity = "STRESS"
            elif current_value >= thresholds.get("high", 999):
                severity = "HIGH"
            elif current_value >= thresholds.get("elevated", 999):
                severity = "ELEVATED"
            # Lower thresholds
            elif current_value <= thresholds.get("favorable", 0):
                severity = "FAVORABLE"
            elif current_value <= thresholds.get("low", 999):
                severity = "LOW"

        # Regime impact overrides severity based on baseline deviation
        if has_regime:
            baseline = _BASELINE.get(variable)
            if baseline:
                dev = abs(current_value - baseline) / baseline * 100
                if dev >= 20:
                    severity = "EXTREME"
                elif dev >= 10:
                    severity = "ELEVATED"
                elif severity == "NEUTRAL":
                    severity = "HIGH"  # regime impact active → at least notable

        # Magnitude gate: filter negligible impacts, flag material ones
        lines, details = _apply_magnitude_gate(lines, details)

        # Build summary
        if lines:
            summary = ", ".join(lines)
        else:
            summary = ""

        return {
            "lines": lines,
            "summary": summary,
            "severity": severity,
            "sectors_bearish": spec.get("sectors_bearish", []),
            "sectors_bullish": spec.get("sectors_bullish", []),
            "details": details,
            "current_price": current_value,
            "change_pct": change_pct,
        }

    except Exception:
        return {}


def format_consequence_line(variable: str, consequence: dict) -> str:
    """
    Format a consequence dict into a single human-readable line.
    Includes actual price level for geopolitical context (Phase 23).

    Returns: "→ Brent $85 (+2.1%): CAD +$3.5B annualized, INR pressure ~7-15ps"
    Or "" if consequence is empty.
    """
    try:
        if not consequence or not consequence.get("summary"):
            return ""

        summary = consequence["summary"]
        severity = consequence.get("severity", "NEUTRAL")
        price = consequence.get("current_price")
        change_pct = consequence.get("change_pct")

        prefix = "📌"
        if severity in ("STRESS", "EXTREME"):
            prefix = "🚨"
        elif severity in ("ELEVATED", "HIGH"):
            prefix = "⚠️"

        # Inject price level if available (Phase 23: geopolitical price context)
        price_context = ""
        if price is not None:
            if variable == "brent":
                price_context = f"Brent ${price:.0f}"
            elif variable == "gold":
                price_context = f"Gold ${price:.0f}"
            elif variable == "copper":
                price_context = f"Copper ${price:.2f}"
            elif variable == "usdinr":
                price_context = f"USDINR ₹{price:.2f}"
            elif variable == "us_10y":
                price_context = f"US10Y {price:.2f}%"
            elif variable == "dxy":
                price_context = f"DXY {price:.1f}"
            elif variable == "wti":
                price_context = f"WTI ${price:.0f}"
            elif variable == "india_vix":
                price_context = f"India VIX: {price:.1f}"
            elif variable == "cboe_vix":
                price_context = f"CBOE VIX: {price:.1f}"
            else:
                price_context = f"{variable}: {price:.1f}"

            if change_pct is not None and abs(change_pct) > 0.1:
                price_context += f" ({change_pct:+.1f}%)"

        if price_context:
            return f"{prefix} {price_context}: {summary}"
        return f"{prefix} {summary}"

    except Exception:
        return ""


def compute_all_consequences(anchor_data: list, fii_data: dict = None) -> dict:
    """
    Batch compute consequences for all available macro anchor data.

    Args:
        anchor_data: List of anchor dicts from fetch_macro_anchors()
        fii_data: Optional FII context dict

    Returns:
        dict keyed by variable name (e.g., "brent", "us_10y") with consequence dicts.
    """
    results = {}
    try:
        symbol_to_var = {
            "BZ=F": "brent",
            "CL=F": "wti",
            "^TNX": "us_10y",
            "DX-Y.NYB": "dxy",
            "USDINR=X": "usdinr",
            "^INDIAVIX": "india_vix",
            "GC=F": "gold",
            "HG=F": "copper",
            "^VIX": "cboe_vix",
            "HYG": "hyg",
        }

        for anchor in anchor_data:
            if not anchor.get("ok"):
                continue

            symbol = anchor.get("symbol", "")
            variable = symbol_to_var.get(symbol)
            if not variable:
                continue

            price = _safe_float(anchor.get("price"))
            change_pct = _safe_float(anchor.get("change_pct"))

            # Secondary sanity guard — skip if price is outside 3-sigma bounds
            var_ranges = _CONSEQUENCE_RANGES.get(variable)
            if var_ranges:
                lo, hi = var_ranges
                if price < lo or price > hi:
                    print(f"⚠️  Consequence guard: {variable} price={price} outside [{lo}, {hi}] — skipping")
                    continue

            # Compute absolute change from percentage
            change_value = price * change_pct / 100 if price and change_pct else 0

            consequence = compute_consequence(
                variable=variable,
                current_value=price,
                change_value=change_value,
                change_pct=change_pct,
            )

            if consequence:
                results[variable] = consequence

        # WTI/Brent coherence check: if deviation spread > 5%, suppress WTI
        if "brent" in results and "wti" in results:
            brent_price = _safe_float(results["brent"].get("current_price"))
            wti_price = _safe_float(results["wti"].get("current_price"))
            brent_baseline = _BASELINE.get("brent")
            wti_baseline = _BASELINE.get("wti")
            if brent_price and wti_price and brent_baseline and wti_baseline:
                brent_dev = abs((brent_price - brent_baseline) / brent_baseline * 100)
                wti_dev = abs((wti_price - wti_baseline) / wti_baseline * 100)
                if abs(brent_dev - wti_dev) > 5.0:
                    print(f"⚠️  WTI/Brent decoupling: Brent {brent_dev:.0f}% vs WTI {wti_dev:.0f}% — suppressing WTI")
                    del results["wti"]

    except Exception:
        pass

    return results


def compute_compound_consequences(anchor_data: list) -> list:
    """
    Cross-asset compounding: when USDINR is at extreme percentile,
    amplify commodity consequences by rupee weakness factor.

    Returns list of compound consequence lines (empty if no compounding).
    """
    try:
        from src.formatters import get_percentile_value

        # Find USDINR price
        usdinr_price = None
        for a in anchor_data:
            if a.get("ok") and a.get("symbol") == "USDINR=X":
                usdinr_price = _safe_float(a.get("price"))
                break

        if not usdinr_price:
            return []

        # Get USDINR percentile
        usdinr_pct = get_percentile_value("usdinr", usdinr_price, "1Y")
        if usdinr_pct is None or usdinr_pct < 85:
            return []

        # Rupee is at extreme weakness — amplify commodity consequences
        amplifier = 1 + (usdinr_pct - 85) / 100  # 1.0 at 85th, 1.15 at 100th

        lines = []

        # Check Brent (oil)
        for a in anchor_data:
            if a.get("ok") and a.get("symbol") == "BZ=F":
                brent_price = _safe_float(a.get("price"))
                if brent_price:
                    # Effective oil cost in rupee terms
                    # Each $1 of oil = ₹83-97 depending on USDINR
                    # At 100th %ile USDINR, every barrel costs more in INR
                    effective_amplifier_pct = round((amplifier - 1) * 100)
                    lines.append(
                        f"⚠️ COMPOUNDED: Rupee at {_ordinal(int(usdinr_pct))} %ile (₹{usdinr_price:.1f}) "
                        f"amplifies oil import cost by ~{effective_amplifier_pct}%"
                    )
                    break

        # Check Gold
        for a in anchor_data:
            if a.get("ok") and a.get("symbol") == "GC=F":
                gold_price = _safe_float(a.get("price"))
                if gold_price:
                    gold_pct = get_percentile_value("gold", gold_price, "1Y")
                    if gold_pct and gold_pct > 70:
                        lines.append(
                            f"⚠️ Gold at {_ordinal(int(gold_pct))} %ile in USD → even higher in INR "
                            f"due to rupee weakness"
                        )
                    break

        return lines

    except Exception:
        return []


# Severity sort order for headwind/tailwind hierarchy
_SEVERITY_SCORE = {
    "EXTREME": 5,   # worst headwind
    "STRESS": 4,
    "HIGH": 3,
    "ELEVATED": 2,
    "NEUTRAL": 1,
    "LOW": -1,       # mild tailwind
    "FAVORABLE": -2, # strong tailwind
}

# Variables that are headwinds when elevated (positive deviation = bad for India)
_HEADWIND_WHEN_HIGH = {"usdinr", "brent", "wti", "dxy", "us_10y", "india_vix", "cboe_vix", "gold"}
# Variables that are tailwinds when elevated (positive deviation = good for India)
_TAILWIND_WHEN_HIGH = {"copper", "hyg"}  # copper = growth, HYG = risk-on


def _classify_consequence(variable: str, consequence: dict) -> tuple[str, int]:
    """Classify as 'headwind' or 'tailwind' and return sort score.

    Returns (classification, severity_score).
    Lower score = more urgent to show first.
    """
    severity = consequence.get("severity", "NEUTRAL")
    score = _SEVERITY_SCORE.get(severity, 0)
    price = consequence.get("current_price")
    baseline = _BASELINE.get(variable)

    # Determine if price is above or below baseline
    above_baseline = None
    if price and baseline:
        above_baseline = price > baseline

    # Headwind-when-high variables: bad when above baseline (USDINR, Brent, VIX, DXY, yields)
    if variable in _HEADWIND_WHEN_HIGH:
        if above_baseline is True and severity in ("EXTREME", "STRESS", "HIGH", "ELEVATED"):
            return "headwind", -score
        elif above_baseline is False and severity in ("FAVORABLE", "LOW"):
            return "tailwind", score
    # Tailwind-when-high variables: good when above baseline (copper=growth, HYG=risk-on)
    elif variable in _TAILWIND_WHEN_HIGH:
        if above_baseline is True and severity in ("EXTREME", "STRESS", "HIGH", "ELEVATED"):
            return "tailwind", score
        elif above_baseline is False and severity in ("EXTREME", "STRESS", "HIGH", "ELEVATED"):
            return "headwind", -score

    # Unknown or neutral → neutral bucket
    return "neutral", 0


# India relevance tiers — for India-focused bot, INR/Brent outrank Gold/Copper
_INDIA_RELEVANCE_TIER = {
    # Tier 1: Always show, always on top
    "usdinr": 1, "brent": 1, "india_vix": 1,
    # Tier 2: Show if ELEVATED+ severity
    "dxy": 2, "us_10y": 2, "wti": 2,
    # Tier 3: Suppress unless EXTREME
    "gold": 3, "copper": 3, "hyg": 3, "cboe_vix": 3,
}


def compute_compound_stress_score(consequences: dict) -> int:
    """Count how many variables are at ELEVATED/HIGH/STRESS/EXTREME.

    Used by the regime arbiter to trigger deterministic override.
    """
    return sum(1 for c in consequences.values()
               if c.get("severity") in ("ELEVATED", "HIGH", "STRESS", "EXTREME"))


def _tier_filter(var: str, severity: str) -> bool:
    """Check if a variable should be shown based on its tier and severity."""
    tier = _INDIA_RELEVANCE_TIER.get(var, 2)
    if tier == 1:
        return True
    if tier == 2:
        return severity in ("ELEVATED", "HIGH", "STRESS", "EXTREME")
    if tier == 3:
        return severity == "EXTREME"
    return True


def format_consequence_block(consequences: dict) -> str:
    """
    Format all consequences into a single block for the AI prompt.
    Shows only variables that have meaningful consequences.
    Sorted: India relevance tier → headwinds (worst first) → tailwinds → neutral.

    Tier 1 (always top): USDINR, Brent, VIX
    Tier 2 (show if ELEVATED+): DXY, US10Y, WTI
    Tier 3 (suppress unless EXTREME): Gold, Copper, HYG, CBOE VIX
    """
    try:
        headwinds = []
        tailwinds = []
        neutral = []

        for var, cons in consequences.items():
            line = format_consequence_line(var, cons)
            if not line:
                continue
            spec = CONSEQUENCE_MULTIPLIERS.get(var, {})
            desc = spec.get("description", var.upper())
            full_line = f"{desc}: {line}"

            severity = cons.get("severity", "NEUTRAL")
            tier = _INDIA_RELEVANCE_TIER.get(var, 2)

            # Tier filter: suppress Tier 2 if not elevated, Tier 3 if not extreme
            if not _tier_filter(var, severity):
                continue

            classification, score = _classify_consequence(var, cons)
            # Sort key: (tier, severity_score) so Tier 1 appears before Tier 2
            if classification == "headwind":
                headwinds.append((tier, score, full_line))
            elif classification == "tailwind":
                tailwinds.append((tier, score, full_line))
            else:
                neutral.append((tier, full_line))

        # Sort: tier first (1 before 2 before 3), then severity within tier
        headwinds.sort(key=lambda x: (x[0], x[1]))
        tailwinds.sort(key=lambda x: (x[0], x[1]))
        neutral.sort(key=lambda x: x[0])

        all_lines = [l for _, _, l in headwinds] + [l for _, _, l in tailwinds] + [l for _, l in neutral]

        if not all_lines:
            return ""

        header = "[CONSEQUENCE LAYER — India Impact]"
        return header + "\n" + "\n".join(all_lines)

    except Exception:
        return ""
