"""
Transmission Mechanics — Deterministic impact functions for each structural pillar.
Maps global macro breaks → India-specific financial impact.
Zero AI. Pure math on historical relationships. No div-by-zero. No NaN outputs.
"""

import numpy as np
from typing import Dict, Optional

_TYPICAL_IMPORT_BILL_BPS = 0.15  # ~15% of crude price pass-through to CPI
_INR_IMPORT_PASS_THROUGH = 0.08  # ~8% of INR depreciation passes to CPI
_FX_RESERVES_USD_BN = 650  # India forex reserves ~$650B
_MONTHLY_IMPORT_USD_BN = 50  # Monthly imports ~$50B


def _safe(val, default=0.0):
    """Safely coerce a value to float, returning default on failure."""
    if val is None:
        return default
    try:
        f = float(val)
        if np.isnan(f) or np.isinf(f):
            return default
        return f
    except (ValueError, TypeError, OverflowError):
        return default


def rbi_dilemma(current: Dict, baseline: Dict) -> Dict:
    """STAGFLATION: Real yield constraint from commodity + INR pressure.

    When CPI is elevated AND growth is slowing, RBI faces a dual mandate
    conflict. Computes the real yield and fiscal deficit impact.
    """
    brent_c = _safe(current.get("brent"), 75)
    brent_b = _safe(baseline.get("brent"), 75)
    usdinr_c = _safe(current.get("usdinr"), 83)
    usdinr_b = _safe(baseline.get("usdinr"), 83)

    freight_cpi_bps = max(0, (brent_c - brent_b) / max(brent_b, 1)) * 150
    inr_cpi_bps = max(0, (usdinr_c - usdinr_b) / max(usdinr_b, 1)) * 80
    cpi_est_bps = round(freight_cpi_bps + inr_cpi_bps, 1)

    india10y = _safe(current.get("india10y", 6.8), 6.8)
    real_yield = round(india10y - (cpi_est_bps / 100), 2)

    import_bill = round((brent_c * usdinr_c - brent_b * usdinr_b) * 0.15, 0)
    cad_increase_cr = round(import_bill * 0.03, 0)

    return {
        "cpi_impact_bps": cpi_est_bps,
        "real_yield": real_yield,
        "real_yield_status": "NEGATIVE" if real_yield < 0 else "CONSTRAINED" if real_yield < 1.5 else "POSITIVE",
        "rbi_constraint": "CANT_EASE_INFLATION" if real_yield < 1.0 else "LIMITED_ROOM" if real_yield < 2.0 else "ROOM_TO_EASE",
        "cad_increase_cr": cad_increase_cr,
        "fiscal_pressure": "ELEVATED" if cad_increase_cr > 5000 else "MODERATE" if cad_increase_cr > 2000 else "NORMAL",
    }


def second_order_cpi(current: Dict, baseline: Dict) -> Dict:
    """WEST ASIA: Freight premium cascade through CPI → RBI forced hike.

    Physical shortage from West Asia disruption cascades:
    Brent → freight premium → WPI/CPI → RBI forced hike despite slowing GDP.
    """
    brent_c = _safe(current.get("brent"), 75)
    brent_b = _safe(baseline.get("brent"), 75)
    usdinr_c = _safe(current.get("usdinr"), 83)

    freight_pct = max(0, (brent_c - brent_b) / max(brent_b, 1)) * 30
    cpi_impact = round(freight_pct * 15, 1)
    rbi_hike_forced = cpi_impact > 50

    import_bill = round((brent_c - brent_b) * usdinr_c * _TYPICAL_IMPORT_BILL_BPS, 0)

    return {
        "freight_premium_pct": round(freight_pct, 1),
        "cpi_impact_bps": cpi_impact,
        "rbi_hike_forced": rbi_hike_forced,
        "import_bill_increase_cr": import_bill,
    }


def balance_sheet_mismatch(current: Dict, baseline: Dict) -> Dict:
    """EM CONTAGION: USD debt servicing + RBI intervention calculus.

    When DXY crushes EM + USDJPY carry unwinds, Indian corporates with
    USD debt face surging costs. RBI intervention depends on reserve cover.
    """
    usdinr_c = _safe(current.get("usdinr"), 83)
    usdinr_b = _safe(baseline.get("usdinr"), 83)
    depreciation_pct = max(0, (usdinr_c - usdinr_b) / max(usdinr_b, 1)) * 100

    corporate_cost_pct = round(depreciation_pct * 0.85, 1)
    reserves_months = round(_FX_RESERVES_USD_BN / _MONTHLY_IMPORT_USD_BN, 1)
    intervention_likely = reserves_months < 8

    return {
        "usdinr_depreciation_pct": round(depreciation_pct, 1),
        "corporate_usd_cost_increase_pct": corporate_cost_pct,
        "reserves_months_cover": reserves_months,
        "intervention_likely": intervention_likely,
        "capital_controls_risk": reserves_months < 6,
    }


def asymmetric_carry(current: Dict, baseline: Dict) -> Dict:
    """CARRY UNWIND: Net carry yield erosion from DXY + INR depreciation.

    When dollar strengthens and INR weakens, the net carry available to
    FIIs shrinks. Below critical threshold (200bps), FIIs exit.
    """
    india10y = _safe(current.get("india10y", 6.8), 6.8)
    us10y = _safe(current.get("us10y", 4.45), 4.45)
    base_carry = round((india10y - us10y) * 100, 1)

    usdinr_c = _safe(current.get("usdinr"), 83)
    usdinr_b = _safe(baseline.get("usdinr"), 83)
    inr_hedge_cost = max(0, (usdinr_c - usdinr_b) / max(usdinr_b, 1)) * 50
    net_carry = round(base_carry - inr_hedge_cost, 1)

    return {
        "base_carry_bps": base_carry,
        "inr_hedge_cost_bps": round(inr_hedge_cost, 1),
        "net_carry_bps": net_carry,
        "fii_break_even_met": net_carry > 200,
    }


def eurodollar_gap(current: Dict, baseline: Dict) -> Dict:
    """DE-DOLLARIZATION: Liquidity fragmentation from DXY-Gold divergence.

    When DXY drops but Gold surges, it signals structural dollar distrust.
    This gap widens EM USD-debt financing costs independent of Fed.
    """
    dxy_c = _safe(current.get("dxy_pctile", 50), 50)
    gold_c = _safe(current.get("gold_pctile", 50), 50)
    divergence = round(gold_c - (100 - dxy_c), 1)
    em_premium_bps = round(max(0, divergence) * 1.5, 1)

    return {
        "dxy_gold_divergence": divergence,
        "em_usd_debt_premium_bps": em_premium_bps,
        "structural_shift": divergence > 40,
    }


def denominator_effect(current: Dict, baseline: Dict) -> Dict:
    """TECH CYCLE: Private markdown → forced public liquidation.

    When tech valuations collapse + credit locks, pension funds face
    denominator effect: illiquid private assets swell as % of portfolio,
    forcing liquidation of liquid public equities.
    """
    pctile_c = _safe(current.get("soxx_nq_pctile", 50), 50)
    tech_stress = max(0, (50 - pctile_c) / 50) * 100
    credit_pct = _safe(current.get("credit_ratio_pctile", 50), 50)
    credit_lock = max(0, (credit_pct - 65) / 35)

    private_markdown = round(tech_stress * 0.15 + credit_lock * 10, 1)
    forced_liquidation = round(private_markdown * 0.08, 2)

    return {
        "tech_stress_index": round(tech_stress, 1),
        "credit_lock": "LOCKED" if credit_lock > 0.7 else "STRESS" if credit_lock > 0.5 else "NORMAL",
        "private_markdown_est_pct": private_markdown,
        "forced_public_liquidation_pct": forced_liquidation,
    }


# Router: pillar_name → transmission function
TRANSMISSION_MAP = {
    "STAGFLATION_SUPPLY": rbi_dilemma,
    "WEST_ASIA": second_order_cpi,
    "EM_CONTAGION": balance_sheet_mismatch,
    "CARRY_UNWIND": asymmetric_carry,
    "DE_DOLLARIZATION": eurodollar_gap,
    "TECH_CYCLE_BURST": denominator_effect,
}


def compute_transmission(
    pillar_name: str,
    current: Dict,
    baselines: Dict,
) -> Optional[Dict]:
    """Route pillar to its transmission function. Returns None on failure."""
    func = TRANSMISSION_MAP.get(pillar_name)
    if not func:
        return None
    try:
        return func(current, baselines)
    except Exception as e:
        return {"error": f"Transmission failed: {e}"}


def format_transmission(pillar_name: str, tx: Dict) -> str:
    """Format transmission result for Telegram output. Max 4 metrics."""
    if not tx or tx.get("error"):
        return ""

    lines = ["  📊 Transmission:"]
    show_keys = {
        "cpi_impact_bps": "CPI impact",
        "real_yield": "Real yield",
        "real_yield_status": "Yield status",
        "cad_increase_cr": "CAD increase",
        "freight_premium_pct": "Freight premium",
        "rbi_hike_forced": "RBI hike forced",
        "import_bill_increase_cr": "Import bill",
        "usdinr_depreciation_pct": "INR depreciation",
        "corporate_usd_cost_increase_pct": "USD debt cost",
        "reserves_months_cover": "Reserve cover",
        "intervention_likely": "RBI intervention likely",
        "capital_controls_risk": "Capital controls risk",
        "net_carry_bps": "Net carry",
        "fii_break_even_met": "FII break-even met",
        "dxy_gold_divergence": "DXY-Gold divergence",
        "em_usd_debt_premium_bps": "EM debt premium",
        "tech_stress_index": "Tech stress",
        "private_markdown_est_pct": "Private markdown est",
        "forced_public_liquidation_pct": "Forced liquidation",
    }

    count = 0
    for key, label in show_keys.items():
        if key in tx and count < 4:
            val = tx[key]
            if isinstance(val, bool):
                val = "Yes" if val else "No"
            elif isinstance(val, float):
                val = f"{val:.1f}"
            lines.append(f"    • {label}: {val}")
            count += 1

    return "\n".join(lines)
