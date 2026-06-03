"""
Intraday Pulse — 30-min scanner during Indian market hours (09:15-15:30 IST).

Triggers: */30 3:45-10:00 1-5 (GitHub Actions cron, UTC).
Zero AI. Pure data check. Sends only on state change (CALM→WATCH→ALERT).

Usage: python3 jobs/intraday_pulse.py
"""

import os
import sys

_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _dir not in sys.path:
    sys.path.insert(0, _dir)

# Load API keys
keyfile = os.path.join(_dir, "apikeys.txt") if os.path.exists(
    os.path.join(_dir, "apikeys.txt")
) else os.path.join(os.path.dirname(_dir), "apikeys.txt")
if os.path.exists(keyfile):
    with open(keyfile) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                sep = "=" if "=" in line else ":"
                if sep in line:
                    k, v = line.split(sep, 1)
                    os.environ.setdefault(k.strip(), v.strip())


def main():
    from src.intraday_pulse import run_pulse
    import src.telegram_sender as ts

    dry_run = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")

    # Connect Supabase
    supabase = None
    if not dry_run:
        try:
            from supabase import create_client
            supabase = create_client(
                os.environ.get("SUPABASE_URL", ""),
                os.environ.get("SUPABASE_KEY", ""),
            )
        except Exception as e:
            print(f"⚠️ Supabase: {e}")

    result = run_pulse(supabase)

    if not result.get("ok"):
        reason = result.get("reason", "Unknown")
        print(f"⏭️ Pulse skipped: {reason}")
        # Send Telegram for data failures (not expected boundary skips)
        if reason not in ("Outside market hours",):
            from datetime import datetime
            from src.db import get_bot_state, set_bot_state
            last_fail = get_bot_state("last_pulse_fail_reason")
            if last_fail != reason:
                set_bot_state("last_pulse_fail_reason", reason)
                ts.send_text(f"⏭️ *Intraday Pulse:* {reason}")
        return

    record = result.get("record", {})
    pulse_label = record.get("pulse_label", "CALM")
    label_changed = result.get("label_changed", False)

    print(f"📍 Intraday Pulse: Nifty {record.get('nifty_price')}, VIX {record.get('india_vix')}")
    print(f"   Label: {pulse_label} | Changed: {label_changed}")

    # Only send Telegram if label changed from last scan
    if label_changed and not dry_run:
        formatted = result.get("formatted", "")
        if formatted:
            ts.send_text(formatted)
            print(f"📤 Sent: {formatted}")
    elif dry_run:
        print(f"📋 Dry-run: {result.get('formatted', '(empty)')}")
    else:
        print(f"⏭️ No change from last pulse (still {pulse_label})")


if __name__ == "__main__":
    main()
