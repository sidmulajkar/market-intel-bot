"""Lightweight manifest loader — O(1) weekday reads of Sunday pre-computed values."""

import json
import os
from typing import Any, Dict


_REQUIRED_TOP_LEVEL = {"version", "generated_at", "fingerprint_buckets", "fragility"}
_MANIFEST_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "manifest.json")


def load(path: str = None) -> Dict[str, Any]:
    """Load manifest.json. Validates schema. Aborts if missing required keys."""
    path = path or _MANIFEST_PATH

    if not os.path.exists(path):
        raise FileNotFoundError(f"Manifest not found: {path} — run sunday_calibration first")

    with open(path, "r") as f:
        manifest = json.load(f)

    missing = _REQUIRED_TOP_LEVEL - set(manifest.keys())
    if missing:
        raise KeyError(f"Manifest missing required keys: {missing}")

    version = manifest.get("version", "0000000")
    if version == "0000000" or not version:
        raise ValueError(f"Manifest version is unset or invalid: {version}")

    buckets = manifest.get("fingerprint_buckets", {})
    for key in ("nifty", "vix", "brent", "usdinr", "dxy"):
        val = buckets.get(key)
        if val is None or val <= 0:
            raise ValueError(f"Manifest fingerprint_buckets.{key} is missing or non-positive: {val}")

    fragility = manifest.get("fragility", {})
    for key in ("cap_neutral", "force_defensive"):
        val = fragility.get(key)
        if val is None or not isinstance(val, (int, float)):
            raise ValueError(f"Manifest fragility.{key} is missing or invalid: {val}")

    adaptive = manifest.get("adaptive_weights", {})
    for pillar, weight in adaptive.items():
        if not isinstance(weight, (int, float)) or weight < 0.5 or weight > 2.0:
            raise ValueError(f"Manifest adaptive_weights.{pillar} out of range [0.5, 2.0]: {weight}")

    erp = manifest.get("erp_deciles", [])
    if len(erp) != 10:
        raise ValueError(f"Manifest erp_deciles must have exactly 10 values, got {len(erp)}")

    template = manifest.get("steady_state_template", "")
    if not template:
        raise ValueError("Manifest steady_state_template is empty")

    return manifest
