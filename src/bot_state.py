"""Helpers for reading/writing fingerprint skip gate metadata.

Primary storage: data/skip_state.json (local file, GHA-cacheable).
Fallback: Supabase bot_state table (if file unavailable).
"""

import json, os
from datetime import datetime
from typing import NamedTuple, Optional

_SKIP_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "skip_state.json")


class SkipMeta(NamedTuple):
    last_fingerprint: Optional[str]
    last_sent_at: Optional[datetime]
    last_regime: str
    last_fragility: float


def _read_file() -> Optional[dict]:
    try:
        if not os.path.exists(_SKIP_FILE):
            return None
        with open(_SKIP_FILE) as f:
            return json.load(f)
    except Exception:
        return None


def _write_file(d: dict) -> bool:
    try:
        os.makedirs(os.path.dirname(_SKIP_FILE), exist_ok=True)
        with open(_SKIP_FILE, "w") as f:
            json.dump(d, f, default=str)
        return True
    except Exception:
        return False


def _read_supabase() -> Optional[dict]:
    try:
        from supabase import create_client
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if not url or not key:
            return None
        client = create_client(url, key)
        row = client.table("bot_state").select("value").eq("key", "skip_meta").limit(1).execute()
        if row.data and len(row.data) > 0:
            val = row.data[0].get("value")
            if val:
                return json.loads(val) if isinstance(val, str) else val
    except Exception:
        pass
    return None


def _write_supabase(d: dict) -> bool:
    try:
        from supabase import create_client
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if not url or not key:
            return False
        client = create_client(url, key)
        client.table("bot_state").upsert(
            {"key": "skip_meta", "value": json.dumps(d, default=str)},
            on_conflict="key",
        ).execute()
        return True
    except Exception:
        return False


def get_skip_meta() -> SkipMeta:
    """Read skip metadata: try local file first, then Supabase, then defaults."""
    defaults = SkipMeta(None, None, "NEUTRAL", 50.0)

    d = _read_file()
    if d is None:
        d = _read_supabase()
    if d is None:
        return defaults

    fp = d.get("last_fingerprint")
    sent_raw = d.get("last_sent_at")
    sent = None
    if sent_raw:
        try:
            sent = datetime.fromisoformat(str(sent_raw).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            sent = None
    regime = d.get("last_regime", "NEUTRAL") or "NEUTRAL"
    fragility = d.get("last_fragility", 50.0) or 50.0
    return SkipMeta(fp, sent, str(regime), float(fragility))


def update_skip_meta(
    fingerprint: str,
    sent_at_iso: str,
    regime: str = "NEUTRAL",
    fragility: float = 50.0,
) -> bool:
    """Write fingerprint + send timestamp to local file AND Supabase (best-effort)."""
    value = {
        "last_fingerprint": fingerprint,
        "last_sent_at": sent_at_iso,
        "last_regime": regime,
        "last_fragility": fragility,
    }
    ok = _write_file(value)
    _write_supabase(value)  # best-effort
    return ok
