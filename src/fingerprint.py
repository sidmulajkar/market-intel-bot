"""Raw-anchor fingerprint skip gate.

Hashes bucketed raw anchors (NOT computed state) so the skip gate runs in
<100ms before any heavy module loads. Pair with manifest.json for bucket sizes.

No hard-skip-with-silence. Fingerprint match always sends a deterministic stub.
"""

import hashlib
from datetime import datetime, timezone
from typing import Dict, Optional


FP_ANCHOR_MAP = {
    "^NSEI": "NIFTY",
    "^INDIAVIX": "VIX",
    "USDINR=X": "USDINR",
    "BZ=F": "BRENT",
    "DX-Y.NYB": "DXY",
}


def build_anchor_dict(
    anchor_data: list,
    index_data: dict = None,
    fii_net: float = None
) -> Dict[str, float]:
    """Extract fingerprint-relevant values from anchor list + global indices."""
    result = {}

    for a in (anchor_data or []):
        sym = a.get("symbol", "")
        if sym in FP_ANCHOR_MAP and a.get("ok") and a.get("price") is not None:
            result[FP_ANCHOR_MAP[sym]] = a["price"]

    if index_data:
        india = index_data.get("India", {})
        if india.get("ok") and india.get("price"):
            result["NIFTY"] = india["price"]
        vix_entry = index_data.get("India VIX", {})
        if vix_entry.get("ok") and vix_entry.get("price"):
            result["VIX"] = vix_entry["price"]

    if fii_net is not None:
        result["FII_NET"] = fii_net

    return result


def compute_raw_fingerprint(anchors: Dict[str, float], manifest: dict) -> str:
    """Hash ONLY cheap raw inputs. NEVER computed state."""
    buckets = manifest.get("fingerprint_buckets", {})
    version = manifest.get("version", "0000000")

    nifty = anchors.get("NIFTY", 0) or 0
    vix = anchors.get("VIX", 0) or 0
    usdinr = anchors.get("USDINR", 0) or 0
    brent = anchors.get("BRENT", 0) or 0
    dxy = anchors.get("DXY", 0) or 0
    fii_net = anchors.get("FII_NET", 0) or 0

    fii_bucket = 0
    if fii_net > 500:
        fii_bucket = 1
    elif fii_net < -500:
        fii_bucket = -1

    canon = (
        f"N:{round(nifty / buckets.get('nifty', 100))}|"
        f"V:{round(vix / buckets.get('vix', 1))}|"
        f"U:{round(usdinr / buckets.get('usdinr', 0.1))}|"
        f"B:{round(brent / buckets.get('brent', 1.0))}|"
        f"D:{round(dxy / buckets.get('dxy', 0.5))}|"
        f"F:{fii_bucket}|"
        f"M:{version}"
    )
    return hashlib.blake2b(canon.encode(), digest_size=8).hexdigest()


def hours_since(dt: Optional[datetime]) -> float:
    """Compute hours elapsed since a datetime. Returns large if dt is None."""
    if dt is None:
        return 9999.0
    return (datetime.now(timezone.utc) - dt).total_seconds() / 3600


def fmt_time_since(dt: Optional[datetime]) -> str:
    """Human-readable time since last send."""
    if dt is None:
        return "never"
    h = hours_since(dt)
    if h < 1:
        return f"{int(h * 60)}m ago"
    return f"{int(h)}h ago"
