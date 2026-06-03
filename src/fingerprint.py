"""Raw-anchor fingerprint skip gate.

Hashes bucketed raw anchors (NOT computed state) so the skip gate runs in
<100ms before any heavy module loads. Pair with manifest.json for bucket sizes.

Heartbeat logic prevents radio silence on unchanged days.
"""

import hashlib
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple


def compute_raw_fingerprint(anchors: Dict[str, float], manifest: dict) -> str:
    """Hash ONLY cheap raw inputs. NEVER computed state.

    Bucket sizes from manifest prevent tiny ticks from busting cache.
    Manifest version invalidates cache when thresholds change.
    """
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


def should_skip(
    current_fp: str,
    last_fp: Optional[str],
    last_sent_at: Optional[datetime],
    heartbeat_min: int = 240,
) -> Tuple[bool, str]:
    """Decide whether to skip full compute.

    Returns (skip, reason).
    - Skip if fingerprint unchanged AND heartbeat window hasn't elapsed.
    - Force send on heartbeat even if fingerprint unchanged (prevents radio silence).
    """
    now = datetime.now(timezone.utc)

    if last_fp is None:
        return False, "No prior fingerprint — first run"

    if last_fp != current_fp:
        return False, f"Fingerprint changed ({last_fp[:8]} → {current_fp[:8]})"

    if last_sent_at is None:
        return True, "Steady state. Fingerprint unchanged (no prior send time)."

    elapsed = (now - last_sent_at).total_seconds()
    if elapsed < heartbeat_min * 60:
        return True, f"Steady state. Fingerprint unchanged ({int(elapsed / 60)}min since last send, heartbeat={heartbeat_min}min)."

    return False, f"Heartbeat due ({int(elapsed / 60)}min > {heartbeat_min}min threshold). Sending keepalive."
