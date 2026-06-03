"""Helpers for reading/writing fingerprint skip gate metadata in bot_state.

Usage:
    last_fp, last_sent_at = get_skip_meta()
    update_skip_meta("a1b2c3d...", "2026-06-03T08:00:00Z")
"""

from datetime import datetime
from typing import Optional, Tuple

try:
    from supabase import create_client
    _SUPABASE_AVAILABLE = True
except ImportError:
    _SUPABASE_AVAILABLE = False


def _get_client():
    """Lazy-init Supabase client. Returns None if env vars missing."""
    import os
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


def get_skip_meta() -> Tuple[Optional[str], Optional[datetime]]:
    """Read last_fingerprint and last_sent_at from bot_state.

    Returns:
        (last_fingerprint: str or None, last_sent_at: datetime or None)
        Both None if row doesn't exist or Supabase unavailable.
    """
    if not _SUPABASE_AVAILABLE:
        return None, None

    try:
        client = _get_client()
        if client is None:
            return None, None
        row = client.table("bot_state").select("last_fingerprint", "last_sent_at").limit(1).execute()
        if row.data and len(row.data) > 0:
            fp = row.data[0].get("last_fingerprint")
            sent_raw = row.data[0].get("last_sent_at")
            sent = None
            if sent_raw:
                try:
                    sent = datetime.fromisoformat(str(sent_raw).replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    sent = None
            return fp, sent
        return None, None
    except Exception:
        return None, None


def update_skip_meta(fingerprint: str, sent_at_iso: str) -> bool:
    """Write current fingerprint and send timestamp to bot_state.

    Upserts into id=1 (single-row config table).

    Args:
        fingerprint: Current raw-anchor fingerprint (16 hex chars)
        sent_at_iso: ISO timestamp of last message send

    Returns:
        True if write succeeded, False otherwise
    """
    if not _SUPABASE_AVAILABLE:
        return False

    try:
        client = _get_client()
        if client is None:
            return False
        data = {
            "last_fingerprint": fingerprint,
            "last_sent_at": sent_at_iso,
        }
        client.table("bot_state").upsert(data, on_conflict="id").execute()
        return True
    except Exception:
        return False
