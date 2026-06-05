"""
Fragility Index (Phase 4.1)
3-component composite score measuring breadth of structural stress.

Replaces the binary concurrent_breach override with a continuous score.
Wired into regime arbiter as Layer 2: Fragility > 65 cap NEUTRAL, > 85 force DEFENSIVE.

Fix (Analyst 1):
- Breadth normalized to 0-100 BEFORE weight: (active_pillars / 6) * 100.
- Max Fragility = 40.0 (base) + 30.0 (breadth) + 30.0 (intensity) = 100.0.
- Lifecycle multipliers applied to intensity scores:
  EMERGING × 0.6, ESCALATING × 1.3, SUSTAINED × 1.0, DE-ESCALATING × 0.7.
"""
from typing import Dict, List, Optional
import math

# Component weights
BASE_WEIGHT = 0.40         # Existing Stress Index
BREADTH_WEIGHT = 0.30      # Active pillars (≥40), normalized 0-100, × weight
INTENSITY_WEIGHT = 0.30    # Max pillar score × lifecycle multiplier, clamped to 100

PILLAR_ACTIVE_THRESHOLD = 40
MAX_PILLARS = 6

# Lifecycle multipliers (from pillar_lifecycle states)
LIFECYCLE_MULTIPLIERS = {
    "EMERGING": 0.6,
    "ESCALATING": 1.3,
    "SUSTAINED": 1.0,
    "DE-ESCALATING": 0.7,
}

SEVERITY_LABELS = [
    (85, "CRITICAL"),
    (65, "ELEVATED"),
    (50, "MODERATE"),
    (35, "LOW"),
    (0,  "QUIET"),
]


def _get_lifecycle_multiplier(pillar: Dict) -> float:
    """Extract lifecycle multiplier from a pillar dict.

    Expects an optional "lifecycle_state" key (set by pillar_lifecycle).
    Defaults to EMERGING (×0.6) if unknown.
    """
    state = pillar.get("lifecycle_state", "EMERGING")
    return LIFECYCLE_MULTIPLIERS.get(state, 0.6)


def compute_fragility_index(stress_score: float, pillars: List[Dict]) -> Dict:
    """Compute the 3-component Fragility Index.

    Args:
        stress_score: 0-100 from stress_index.compute_stress_index()
        pillars: List of pillar dicts from pillar_classifier.classify_pillars()
                 Each may include "lifecycle_state" from pillar_lifecycle.

    Returns:
        Dict with ok, fragility_score, components dict, severity, drivers, message
    """
    if stress_score is None or pillars is None:
        return {"ok": False, "fragility_score": 50.0, "message": "No data"}

    # ── Base (0.40) — Stress Index ──
    base = min(100.0, max(0.0, stress_score))

    # ── Breadth (0.30) — normalized 0-100 ──
    active_count = sum(1 for p in pillars if p.get("score", 0) >= PILLAR_ACTIVE_THRESHOLD)
    breadth_normalized = (active_count / MAX_PILLARS) * 100.0
    breadth = min(100.0, max(0.0, breadth_normalized))

    # ── P11.1: External Debt Stress multiplier on Carry Unwind ──
    debt_mult = _get_external_debt_stress_multiplier()

    # ── Intensity (0.30) — max pillar score × lifecycle × dynamic weight × debt stress ──
    try:
        from src.adaptive_weights import get_dynamic_weights
        dynamic_weights = get_dynamic_weights()
    except Exception:
        dynamic_weights = {}
    scores = []
    raw_scores = []
    for p in pillars:
        raw = p.get("score", 0)
        raw_scores.append(raw)
        mult = _get_lifecycle_multiplier(p)
        dyn = dynamic_weights.get(p.get("id", p.get("name", "")), 1.0)
        p_id = p.get("id", p.get("name", ""))
        # P29: pillar decay — age vs half-life reduces intensity contribution
        decay = _get_pillar_decay(p_id, p.get("age_days", 0), p.get("lifecycle_state", "EMERGING"))
        adjusted = raw * mult * dyn * decay
        # Apply debt stress multiplier to Carry_Unwind pillar
        if debt_mult > 1.0 and "carry" in p_id.lower().replace(" ", "_"):
            adjusted *= debt_mult
        scores.append(adjusted)
    intensity = max(scores) if scores else 0.0
    intensity = min(100.0, max(0.0, intensity))
    raw_peak = max(raw_scores) if raw_scores else 0.0

    # ── Composite ──
    fragility = (base * BASE_WEIGHT) + (breadth * BREADTH_WEIGHT) + (intensity * INTENSITY_WEIGHT)
    fragility = round(min(100.0, max(0.0, fragility)), 1)

    severity = _score_to_severity(fragility)

    drivers = []
    if active_count >= 2:
        drivers.append(f"{active_count} active pillars")
    if intensity >= 60:
        drivers.append(f"Peak {intensity:.0f}")
    if base >= 60:
        drivers.append(f"Stress {base:.0f}")

    return {
        "ok": True,
        "fragility_score": fragility,
        "severity": severity,
        "components": {
            "base": round(base, 1),
            "breadth": round(breadth, 1),
            "intensity": round(intensity, 1),
            "raw_peak": round(raw_peak, 1),
        },
        "active_pillar_count": active_count,
        "drivers": drivers[:3],
        "message": _build_message(fragility, severity, drivers),
    }


def _score_to_severity(score: float) -> str:
    for threshold, label in SEVERITY_LABELS:
        if score >= threshold:
            return label
    return "QUIET"


def _build_message(fragility: float, severity: str, drivers: List[str]) -> str:
    if fragility >= 85:
        return f"Critical: {severity} ({fragility:.0f}/100) — forcing defensive posture"
    if fragility >= 65:
        return f"Elevated: {severity} ({fragility:.0f}/100) — capping upside regime"
    if fragility >= 50:
        return f"Moderate: {severity} ({fragility:.0f}/100) — monitoring"
    return f"Low: {severity} ({fragility:.0f}/100) — no structural constraint"


def _get_pillar_decay(pillar_id: str, age_days: int, lifecycle_state: str) -> float:
    """P29: Compute pillar decay multiplier based on age vs half-life.

    A pillar beyond its half-life loses predictive power exponentially.
    Only applies to ESCALATING/SUSTAINED/DE-ESCALATING states.

    decay = exp(-0.1 * max(0, age_days - half_life))

    Returns multiplier in (0, 1].
    """
    if age_days <= 0 or lifecycle_state in ("EMERGING", "INACTIVE"):
        return 1.0

    try:
        from src.manifest import load as _load_manifest
        m = _load_manifest()
        half_lives = m.get("pillar_half_lives", {})
        decay_rate = m.get("pillar_decay", {}).get("decay_rate", 0.1)
        half_life = half_lives.get(pillar_id, m.get("pillar_decay", {}).get("half_life_default", 14))
    except Exception:
        half_life = 14
        decay_rate = 0.1

    excess = max(0, age_days - half_life)
    if excess <= 0:
        return 1.0

    return math.exp(-decay_rate * excess)


def _get_external_debt_stress_multiplier() -> float:
    """P11.1: Check external debt stress conditions.

    IF US10Y > 4.5% AND USDINR > 84.0 AND FII_5D_Net < -10000 Cr
    THEN return 1.5 (multiply Carry_Unwind fragility contribution)
    ELSE return 1.0 (no multiplier)
    """
    try:
        from datetime import datetime, timedelta
        from src.db import get_market_state, get_fii_dii_flows

        today = datetime.now().strftime("%Y-%m-%d")
        state = get_market_state(today) if today else None
        if not state:
            return 1.0

        macro = state.get("macro", {})
        us10y = None
        usdinr = None

        # Extract from macro dict (handles both nested and flat formats)
        us10y_entry = macro.get("^TNX") or macro.get("us_10y") or {}
        if isinstance(us10y_entry, dict):
            us10y = us10y_entry.get("price")
        else:
            us10y = us10y_entry

        usdinr_entry = macro.get("USDINR=X") or macro.get("usdinr") or {}
        if isinstance(usdinr_entry, dict):
            usdinr = usdinr_entry.get("price")
        else:
            usdinr = usdinr_entry

        if us10y is None or usdinr is None:
            return 1.0

        us10y = float(us10y)
        usdinr = float(usdinr)

        # FII 5D net
        flows = get_fii_dii_flows(days=7)
        if not flows:
            return 1.0

        recent = flows[-5:]
        fii_5d = sum(r.get("fiinet_cr", 0) or 0 for r in recent)

        if us10y > 4.5 and usdinr > 84.0 and fii_5d < -10000:
            print(f"   ⚠️ External debt stress: US10Y={us10y}%, USDINR={usdinr}, FII_5D=₹{fii_5d:+,.0f}Cr")
            return 1.5

        return 1.0
    except Exception as e:
        print(f"   ⚠️ _get_external_debt_stress_multiplier: {e}")
        return 1.0


def format_fragility_banner(fragility: Dict) -> str:
    """Decomposed fragility banner with Base/Breadth/Raw Peak components."""
    if not fragility.get("ok"):
        return ""
    score = fragility["fragility_score"]
    severity = fragility["severity"]
    comps = fragility.get("components", {})
    base = comps.get("base", 0)
    breadth = comps.get("breadth", 0)
    raw_peak = comps.get("raw_peak", comps.get("intensity", 0))
    emoji = "🚨" if score >= 85 else "⚠️" if score >= 65 else "📌"
    return f"{emoji} Fragility: {severity} ({score:.0f}/100) Base:{base:.0f} Breadth:{breadth:.0f} Peak:{raw_peak:.0f}"
