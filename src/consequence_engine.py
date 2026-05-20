"""
Consequence Engine — India Impact Multiplier Table

Computes rupee-denominated and percentage consequences for every macro variable.
Every data point needs 4 layers: ABSOLUTE → RELATIVE → PERCENTILE → CONSEQUENCE.

Design: Static lookup table, zero DB dependency, lightweight arithmetic.
Returns empty dict on any failure (consistent with project pattern).
"""

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
            "it_revenue_pct": {"value": 0.5, "label": "IT revenue", "format": "IT revenue boost +{:.1f}%"},
            "fii_exit_cr": {"value": 650, "label": "FII exit risk", "format": "FII exit risk ~₹{:.0f}Cr per +1%"},
            "pharma_export_pct": {"value": 0.3, "label": "Pharma exports", "format": "Pharma export boost +{:.1f}%"},
        },
        "sectors_bearish": ["EM assets broadly", "Metal (USD-denominated costs)"],
        "sectors_bullish": ["IT (TCS, INFY, WIPRO)", "Pharma exporters"],
    },
    "usdinr": {
        "unit": "₹/$",
        "description": "USD/INR exchange rate",
        "per_unit": {
            "it_revenue_pct": {"value": 0.8, "label": "IT revenue", "format": "IT revenue +{:.1f}% per ₹1"},
            "oil_bill_cr": {"value": 14000, "label": "Oil import bill", "format": "Oil bill +₹{:.0f}Cr/yr per ₹1"},
            "gold_inr_pct": {"value": 1.0, "label": "Gold INR price", "format": "Gold INR +{:.0f}% per ₹1"},
        },
        "sectors_bearish": ["Oil importers", "Companies with USD debt"],
        "sectors_bullish": ["IT exporters", "Pharma exporters", "Textile exporters"],
    },
    "india_vix": {
        "unit": "index",
        "description": "India VIX (fear gauge)",
        "per_unit": {
            "option_premium_pct": {"value": 2.0, "label": "Option premium", "format": "Option premium +{:.0f}%"},
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

        # Per-50bps multipliers (for yields)
        per_50bps = spec.get("per_50bps", {})
        for key, mult in per_50bps.items():
            # change_value for yields is in % (e.g., +0.18 = +18bps)
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

        # Per-$100 multipliers (for gold)
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
        }

    except Exception:
        return {}


def format_consequence_line(variable: str, consequence: dict) -> str:
    """
    Format a consequence dict into a single human-readable line.

    Returns: "→ CAD stress +$3.5B annualized, INR pressure ~7-15ps, OMC margins compress"
    Or "" if consequence is empty.
    """
    try:
        if not consequence or not consequence.get("summary"):
            return ""

        summary = consequence["summary"]
        severity = consequence.get("severity", "NEUTRAL")

        prefix = "→"
        if severity in ("STRESS", "EXTREME"):
            prefix = "🚨"
        elif severity in ("ELEVATED", "HIGH"):
            prefix = "⚠️"

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
                        f"⚠️ COMPOUNDED: Rupee at {usdinr_pct:.0f}th %ile (₹{usdinr_price:.1f}) "
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
                            f"⚠️ Gold at {gold_pct:.0f}th %ile in USD → even higher in INR "
                            f"due to rupee weakness"
                        )
                    break

        return lines

    except Exception:
        return []


def format_consequence_block(consequences: dict) -> str:
    """
    Format all consequences into a single block for the AI prompt.
    Shows only variables that have meaningful consequences.
    """
    try:
        lines = []
        for var, cons in consequences.items():
            line = format_consequence_line(var, cons)
            if line:
                spec = CONSEQUENCE_MULTIPLIERS.get(var, {})
                desc = spec.get("description", var.upper())
                lines.append(f"{desc}: {line}")

        if not lines:
            return ""

        header = "[CONSEQUENCE LAYER — India Impact]"
        return header + "\n" + "\n".join(lines)

    except Exception:
        return ""
