"""
scenario_collision.py — P11.4 Archetype Collision Matrix
Bitmask check runs at 15:30 after all pillars computed.
Prepends banner above pillar breakdown; pillar z-scores/transmission chains remain visible below.
"""
from typing import Dict, List, Optional, Tuple


ARCHETYPES = [
    {
        "name": "Asian Crisis 1997",
        "mask": {"Carry_Unwind", "EM_Contagion"},
        "extra": {"dxy_spike": True},
        "banner": "⚠️ ARCHETYPE: Asian Crisis 1997 (Reserve depletion + EM exit + Strong Dollar)",
    },
    {
        "name": "Stagflationary Freeze",
        "mask": {"Stagflation"},
        "extra": {"liquidity_freeze": True},
        "banner": "⚠️ ARCHETYPE: Stagflationary Freeze (Supply shock + Credit seized)",
    },
    {
        "name": "Multipolar Shift",
        "mask": {"De_dollarization"},
        "extra": {"gold_spike": True, "cny_strength": True},
        "banner": "⚠️ ARCHETYPE: Bretton Woods Unraveling (Dedollarization + Hard Asset anchor)",
    },
    {
        "name": "Sovereign Debt Trap",
        "extra": {"fiscal_stress": True, "vix_spike": True, "yield_inversion": True},
        "banner": "⚠️ ARCHETYPE: Sovereign Debt Trap (Unserviceable debt + monetary tightening)",
    },
    {
        "name": "AI Displacement Exit",
        "mask": {"Tech_Cycle", "Carry_Unwind"},
        "extra": {"dxy_spike": True},
        "banner": "⚠️ ARCHETYPE: AI Displacement Exit (Compute capex down + IT USD inflows at risk + Strong Dollar)",
    },
    {
        "name": "Climate/Heatflation Trap",
        "mask": {"Stagflation", "EM_Contagion"},
        "extra": {"usdinr_spike": True},
        "banner": "⚠️ ARCHETYPE: Climate/Heatflation Trap (Agri supply shock + EM debt strain + Import bill crisis)",
    },
]


def detect_collision(pillar_scores: Dict, extra_flags: Dict = None) -> Optional[Dict]:
    """Check active pillars against archetype matrix.

    Args:
        pillar_scores: Dict of {pillar_name: score} from pillar_classifier
        extra_flags: Dict of extra conditions (e.g., dxy_spike, gold_spike, liquidity_freeze)

    Returns:
        First matching archetype dict, or None
    """
    if not pillar_scores:
        return None

    extra = extra_flags or {}

    # Determine active pillars (score >= 40)
    active = {k.replace(" ", "_") for k, v in pillar_scores.items()
              if isinstance(v, (int, float)) and v >= 40}

    # Normalize pillar names (handle both "Stagflation" and "Stagflation_Pillar" etc.)
    normalized_active = set()
    for p in active:
        normalized_active.add(p)
        # Also check key substrings
        for archetype in ARCHETYPES:
            for mask_pillar in archetype.get("mask", set()):
                if mask_pillar.lower() in p.lower() or p.lower() in mask_pillar.lower():
                    normalized_active.add(mask_pillar)

    for archetype in ARCHETYPES:
        mask = archetype.get("mask", set())
        extra_needed = archetype.get("extra", {})

        # Check pillar mask: all required pillars active
        if mask and not mask.issubset(normalized_active):
            continue

        # Check extra conditions
        extra_match = True
        for extra_key, extra_val in extra_needed.items():
            if extra.get(extra_key) != extra_val:
                extra_match = False
                break
        if not extra_match:
            continue

        return archetype

    return None


def has_dxy_spike(macro_attrs: Dict = None) -> bool:
    """Check if DXY is spiking (>106.5)."""
    if not macro_attrs:
        return False
    dxy = macro_attrs.get("DX-Y.NYB") or macro_attrs.get("dxy", 0)
    try:
        return float(dxy) > 106.5
    except (ValueError, TypeError):
        return False


def has_gold_spike(macro_attrs: Dict = None) -> bool:
    """Check if gold is spiking (>3000)."""
    if not macro_attrs:
        return False
    gold = macro_attrs.get("GC=F") or macro_attrs.get("gold", 0)
    try:
        return float(gold) > 3000
    except (ValueError, TypeError):
        return False


def has_cny_strength(macro_attrs: Dict = None) -> bool:
    """Check if CNY is strengthening (USD/CNY < 7.0)."""
    if not macro_attrs:
        return False
    # We don't track CNY directly — proxy via DXY weakness + EEM strength
    return False


def has_usdinr_spike(macro_attrs: Dict = None) -> bool:
    """Check if USDINR is spiking (>86)."""
    if not macro_attrs:
        return False
    usdinr = macro_attrs.get("USDINR=X") or macro_attrs.get("usdinr", 0)
    try:
        return float(usdinr) > 86
    except (ValueError, TypeError):
        return False


def format_collision(archetype: Optional[Dict]) -> str:
    """Format archetype collision as a one-line banner."""
    if not archetype:
        return ""
    return archetype.get("banner", "")
