"""
Delta Engine — State Diff, News Fingerprinting, Suppression.

Prevents the bot from repeating stale information. Every job consults this
before rendering a block. If the underlying MarketState value hasn't changed
meaningfully from the previous send, the block is suppressed.

Usage:
    from src.delta import compute_delta, should_suppress_block, news_fingerprint_hash, get_relevant_indices

    delta = compute_delta(current_state, previous_state)
    if should_suppress_block("brent", delta):
        return ""  # skip this block
"""
from __future__ import annotations

import hashlib
from typing import Dict, List, Optional, Any

# ── Field groups for delta comparison ──────────────────────────────────────

_MACRO_FIELDS = [
    "vix", "vix_percentile", "vix_change_pct",
    "usdinr", "usdinr_change_pct",
    "brent", "brent_change_pct",
    "gold", "gold_change_pct",
    "dxy", "dxy_change_pct",
    "us_10y", "us_10y_change_pct",
    "cboe_vix", "cboe_vix_change_pct",
    "hyg", "wti", "copper",
    "vix_regime", "dxy_signal", "credit_stress",
]

_FLOWS_FIELDS = [
    "fii_net", "dii_net", "absorption_ratio",
    "fii_streak_days", "dii_streak_days",
    "fii_mood", "dii_mood",
    "fii_fno_long", "fii_fno_short", "fii_fno_net",
    "dii_fno_long", "dii_fno_short", "dii_fno_net",
]

_DERIVATIVES_FIELDS = [
    "pcr", "pcr_signal", "max_pain", "spot_price",
    "gex", "skew_25d", "call_oi_total", "put_oi_total",
    "iv", "top_call_strikes", "top_put_strikes",
]

_FEATURES_FIELDS = [
    "momentum_12m", "carry_fii", "sentiment_finbert",
    "vix_zscore", "breadth_score", "valuation_zscore",
    "pcr_normalized", "dxy_carry", "skew_signal",
    "smallcap_ratio",
]

_STATE_FIELDS = [
    "bull_bear_score", "bull_bear_normalized", "bull_bear_confidence",
    "market_phase", "cross_asset_regime", "dominant_factor",
]

_FIELD_TO_GROUP = {}
for f in _MACRO_FIELDS:
    _FIELD_TO_GROUP[f] = "macro"
for f in _FLOWS_FIELDS:
    _FIELD_TO_GROUP[f] = "flows"
for f in _DERIVATIVES_FIELDS:
    _FIELD_TO_GROUP[f] = "derivatives"
for f in _FEATURES_FIELDS:
    _FIELD_TO_GROUP[f] = "features"
for f in _STATE_FIELDS:
    _FIELD_TO_GROUP[f] = "state"

# Default thresholds — % change needed to consider "meaningfully different"
_DEFAULT_THRESHOLDS: Dict[str, float] = {
    "vix": 0.05,
    "brent": 0.02,
    "gold": 0.01,
    "dxy": 0.005,
    "us_10y": 0.02,
    "cboe_vix": 0.05,
    "usdinr": 0.002,
    "fii_net": 0.20,
    "dii_net": 0.20,
    "bull_bear_score": 0.10,
    "bull_bear_normalized": 0.05,
    "pcr": 0.05,
    "max_pain": 0.005,
}

# ── Global indices time-awareness ──────────────────────────────────────────

# Each job time maps to which market sessions are LIVE (not stale)
_TIME_RELEVANT_SESSIONS = {
    "06:00": ["asia_close"],           # market_intel morning — Asia just closed
    "07:00": ["asia_close"],           # market_intel morning
    "08:00": ["asia_close", "us_prior_close"],  # morning_brief
    "09:15": ["us_prior_close"],       # market_open — Asia stale, US prior close
    "12:30": [],                       # midday_scan — nothing global is live
    "15:30": ["europe_mid", "us_premarket"],     # market_close
    "18:00": ["us_live", "europe_close"],        # market_intel evening
    "20:00": ["us_live"],             # evening_report
}

# Which country keys belong to which session
_SESSION_COUNTRIES = {
    "asia_close": ["Japan", "South Korea", "Hong Kong", "Singapore",
                    "Australia", "China SSE", "China SZSE", "Taiwan",
                    "Indonesia", "Malaysia", "Thailand"],
    "us_prior_close": ["US"],
    "us_live": ["US"],
    "europe_mid": ["UK", "Germany", "France"],
    "europe_close": ["UK", "Germany", "France"],
}


def get_relevant_indices(job_time: str, valid_index: dict) -> dict:
    """Return only the global indices that are LIVE (not stale) for this job time.

    At 8AM: show Asia close + US prior close.
    At 12:30: show nothing global (Asia closed, US not open).
    At 3:30: show Europe mid-session + US pre-market.
    At 6PM/8PM: show US live.

    Args:
        job_time: IST time in HH:MM format (e.g., "08:00").
        valid_index: Full dict from fetch_global_indices().

    Returns:
        Subset of valid_index containing only relevant entries.
    """
    sessions = _TIME_RELEVANT_SESSIONS.get(job_time, [])
    if not sessions:
        return {}

    relevant_countries = set()
    for session in sessions:
        relevant_countries.update(_SESSION_COUNTRIES.get(session, []))

    return {
        k: v for k, v in valid_index.items()
        if k in relevant_countries and v.get("ok")
    }


def _get_field_value(state, group: str, field: str) -> Optional[Any]:
    """Extract a field value from the appropriate sub-model of MarketState."""
    sub = getattr(state, group, None)
    if sub is None:
        return None
    if isinstance(sub, dict):
        return sub.get(field)
    return getattr(sub, field, None)


def compute_delta(current, previous) -> Dict:
    """Compute per-field delta between two MarketState objects.

    Compares all numeric and string fields across macro, flows, derivatives,
    features, and top-level state fields.

    Args:
        current: MarketState with today's data.
        previous: MarketState from prior send (can be None on first run).

    Returns:
        Dict with keys:
            changed: list of field names that changed meaningfully
            unchanged: list of field names that are the same
            changed_values: {field: (old_val, new_val, pct_change)}
            previous_exists: bool
    """
    result = {
        "changed": [],
        "unchanged": [],
        "changed_values": {},
        "previous_exists": previous is not None,
    }

    if previous is None:
        # First run — everything is "new"
        result["changed"] = _all_fields()
        return result

    for group, fields in [
        ("macro", _MACRO_FIELDS),
        ("flows", _FLOWS_FIELDS),
        ("derivatives", _DERIVATIVES_FIELDS),
        ("features", _FEATURES_FIELDS),
        ("state", _STATE_FIELDS),
    ]:
        for field in fields:
            old_val = _get_field_value(previous, group, field)
            new_val = _get_field_value(current, group, field)

            if _values_equal(old_val, new_val, field):
                result["unchanged"].append(field)
            else:
                pct = _pct_change(old_val, new_val)
                result["changed"].append(field)
                result["changed_values"][field] = (old_val, new_val, pct)

    return result


def _all_fields() -> List[str]:
    """Return all tracked field names."""
    return (
        _MACRO_FIELDS + _FLOWS_FIELDS + _DERIVATIVES_FIELDS
        + _FEATURES_FIELDS + _STATE_FIELDS
    )


def _values_equal(old, new, field: str) -> bool:
    """Check if two values are meaningfully equal."""
    if old is None and new is None:
        return True
    if old is None or new is None:
        return False
    if isinstance(old, str) and isinstance(new, str):
        return old == new
    if isinstance(old, list) and isinstance(new, list):
        return old == new
    # Numeric comparison with threshold
    threshold = _DEFAULT_THRESHOLDS.get(field, 0.03)
    if old == 0 and new == 0:
        return True
    if old == 0 or new == 0:
        return False
    pct = abs(new - old) / abs(old)
    return pct < threshold


def _pct_change(old, new) -> Optional[float]:
    """Compute percentage change between two values."""
    if old is None or new is None:
        return None
    if isinstance(old, str) or isinstance(new, str):
        return None
    if old == 0:
        return None
    return (new - old) / abs(old)


def should_suppress_block(
    field: str,
    delta: Dict,
    threshold: Optional[float] = None,
) -> bool:
    """Check if a block should be suppressed because its data hasn't changed.

    Args:
        field: The primary field this block depends on (e.g., "brent").
        delta: Output from compute_delta().
        threshold: Override threshold (default from _DEFAULT_THRESHOLDS).

    Returns:
        True if the block should be suppressed (no meaningful change).
    """
    if not delta.get("previous_exists"):
        return False  # first run, never suppress

    if field in delta.get("changed", []):
        return False  # data changed, don't suppress

    if field in delta.get("unchanged", []):
        return True  # explicitly unchanged

    # Unknown field — default: don't suppress
    return False


def news_fingerprint_hash(headlines: List[str], top_n: int = 3) -> str:
    """SHA-256 hash of top N headlines for staleness detection.

    Args:
        headlines: List of headline strings.
        top_n: Number of top headlines to include in hash.

    Returns:
        Hex digest string.
    """
    if not headlines:
        return hashlib.sha256(b"__no_headlines__").hexdigest()[:16]
    selected = headlines[:top_n]
    canonical = "|".join(h.strip().lower() for h in selected)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def check_news_staleness(
    headlines: List[str],
    prev_fingerprint: Optional[str],
    top_n: int = 3,
) -> Dict[str, str]:
    """Check if news has changed since last send.

    Args:
        headlines: Current top headlines.
        prev_fingerprint: Hash from previous send (from bot_state).
        top_n: Number of headlines to compare.

    Returns:
        Dict with keys:
            status: "fresh" | "stale" | "unknown"
            fingerprint: current hash
    """
    current_fp = news_fingerprint_hash(headlines, top_n)
    if prev_fingerprint is None:
        return {"status": "fresh", "fingerprint": current_fp}
    if current_fp == prev_fingerprint:
        return {"status": "stale", "fingerprint": current_fp}
    return {"status": "fresh", "fingerprint": current_fp}
