"""
sentinel.py — Meta-Cognitive Sentinel (Phase 10)
Pure edge-case defense. Runs at pipeline boot.
1. Preflight Check: Null/Variance HALT (prevents garbage in)
2. Regime Membrane: Circuit Breaker (prevents hallucinated regime leaps)
"""
import logging
import sys
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

REGIME_ORDER = {'BULLISH': 0, 'NEUTRAL': 1, 'DEFENSIVE': 2}
MAX_NULL_PCT = 0.30
MAX_DAILY_VARIANCE = 0.30
VARIANCE_CHECK_ANCHORS = ['BZ=F', 'USDINR=X', 'DX-Y.NYB']

def preflight_check(current_anchors: Dict[str, float], prev_anchors: Dict[str, float]) -> Tuple[bool, str]:
    if not current_anchors:
        return False, "100% macro anchor fetch failure (empty dict)"

    null_count = sum(1 for v in current_anchors.values() if v is None or v == 0.0)
    null_pct = null_count / len(current_anchors)
    if null_pct > MAX_NULL_PCT:
        reason = f"Macro anchor fetch >{int(MAX_NULL_PCT*100)}% null ({null_pct:.0%}). Pipeline halted."
        logger.critical(f"🚨 SENTINEL HALT: {reason}")
        return False, reason

    for anchor in VARIANCE_CHECK_ANCHORS:
        cur = current_anchors.get(anchor)
        prev = prev_anchors.get(anchor)
        if cur and prev and prev > 0:
            daily_change = abs(cur - prev) / prev
            if daily_change > MAX_DAILY_VARIANCE:
                reason = f"{anchor} moved {daily_change:.0%} daily (>{int(MAX_DAILY_VARIANCE*100)}%). Likely API glitch."
                logger.critical(f"🚨 SENTINEL HALT: {reason}")
                return False, reason

    return True, "Pass"


def regime_membrane(current_regime: str, prev_regime: str, current_fragility: float, prev_fragility: float) -> str:
    cur_score = REGIME_ORDER.get(current_regime, 1)
    prev_score = REGIME_ORDER.get(prev_regime, 1)
    step_jump = abs(cur_score - prev_score)

    if step_jump >= 2:
        fragility_delta = prev_fragility - current_fragility

        if cur_score < prev_score and fragility_delta < 20:
            logger.warning(f"⚠️ SENTINEL MEMBRANE: Blocked {prev_regime}->{current_regime} leap. Fragility only dropped {fragility_delta:.1f}pts (needs 20+). Capping at NEUTRAL.")
            return 'NEUTRAL'

        if cur_score > prev_score and fragility_delta > -20:
            logger.warning(f"⚠️ SENTINEL MEMBRANE: Blocked {prev_regime}->{current_regime} leap. Fragility only surged by {abs(fragility_delta):.1f}pts (needs 20+). Capping at NEUTRAL.")
            return 'NEUTRAL'

    return current_regime
