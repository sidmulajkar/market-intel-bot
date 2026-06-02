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

    # ── Intensity (0.30) — max pillar score × lifecycle multiplier ──
    scores = []
    for p in pillars:
        raw = p.get("score", 0)
        mult = _get_lifecycle_multiplier(p)
        adjusted = raw * mult
        scores.append(adjusted)
    intensity = max(scores) if scores else 0.0
    intensity = min(100.0, max(0.0, intensity))

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


def format_fragility_banner(fragility: Dict) -> str:
    """Compact one-line banner for Telegram output."""
    if not fragility.get("ok"):
        return ""
    score = fragility["fragility_score"]
    severity = fragility["severity"]
    drivers = fragility.get("drivers", [])
    driver_str = ", ".join(drivers) if drivers else "none"
    emoji = "🚨" if score >= 85 else "⚠️" if score >= 65 else "📌"
    return f"{emoji} Fragility: {severity} ({score:.0f}/100) | Drivers: {driver_str}"
