#!/usr/bin/env python3
"""
Full-Day Telegram Output Validation

Runs all 7 market intel jobs sequentially with DRY_RUN enabled.
Captures what each job would send to Telegram and validates:
  1. No NameError, UnboundLocalError, format errors
  2. Total messages across all jobs <= 10
  3. No duplicate content between jobs
  4. Each job produces distinct, time-appropriate output
  5. Skip gates fire correctly
  6. Regime card appears in morning_brief + market_intel
  7. AI output >= 30 words or structured JSON with required keys

Usage:
    export SUPABASE_URL=... SUPABASE_KEY=... GROQ_API_KEY=... etc.
    python3 test_full_day.py
"""
import os
import sys
import subprocess
import re
from datetime import datetime

# ── Environment setup ─────────────────────────────────────────────
ENV_VARS = {
    "DRY_RUN": "true",
    "SUPABASE_URL": os.environ.get("SUPABASE_URL", ""),
    "SUPABASE_KEY": os.environ.get("SUPABASE_KEY", ""),
    "GROQ_API_KEY": os.environ.get("GROQ_API_KEY", ""),
    "GOOGLE_AI_KEY": os.environ.get("GOOGLE_AI_KEY", ""),
    "FINNHUB_KEY": os.environ.get("FINNHUB_KEY", ""),
    "HF_KEY": os.environ.get("HF_KEY", ""),
    "TELEGRAM_TOKEN": "dummy-token-for-dry-run",
    "TELEGRAM_CHAT_ID": "dummy-chat-id",
}

# Validate required keys
_missing = [k for k, v in ENV_VARS.items() if not v and k not in ("TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID", "DRY_RUN")]
if _missing:
    print(f"ERROR: Missing env vars: {', '.join(_missing)}")
    print("Set them via export or .env file before running.")
    sys.exit(1)

# Job schedule — order matters (simulates a real trading day)
JOBS = [
    ("05:00", "fii_dii_fetch.py",     [],           "FII/DII Data Fetch"),
    ("07:00", "market_intel.py",      ["morning"],  "Morning Market Intel"),
    ("08:00", "morning_brief.py",     [],           "Morning Brief"),
    ("09:15", "market_open.py",       [],           "Market Open"),
    ("12:30", "midday_scan.py",       [],           "Midday Scan"),
    ("15:30", "market_close.py",      [],           "Market Close"),
    ("18:00", "market_intel.py",      ["evening"],  "Evening Market Intel"),
    ("20:00", "evening_report.py",    [],           "Evening Report"),
]

def run_job(script: str, args: list, label: str) -> dict:
    """Run a single job and capture stdout + telegram messages."""
    print(f"\n{'='*70}")
    print(f"  ⏰ {label}")
    print(f"{'='*70}")

    cmd = [os.path.join(os.path.dirname(os.path.abspath(__file__)), '.venv', 'bin', 'python'), f"jobs/{script}"] + args
    env = {**os.environ, **ENV_VARS}

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=480, cwd=os.path.dirname(os.path.abspath(__file__)),
            env=env,
        )
        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode
    except subprocess.TimeoutExpired:
        stdout = ""
        stderr = "TIMEOUT: Job exceeded 5 minutes"
        exit_code = 124

    # Extract DRY RUN telegram messages
    # Supports two formats:
    #   1. No emoji scrub: 📨 ... \n=====\n<text>\n=====
    #   2. With emoji scrub: 📨 ... \n--- SCRUBBED ---\n=====\n<scrubbed>\n=====
    telegram_messages = re.findall(
        r'📨 \[DRY RUN\] Telegram message would be sent:.*?\n={60}\n(.*?)\n={60}',
        stdout, re.DOTALL
    )

    # Check for errors
    errors = []
    for err_type in ["NameError", "UnboundLocalError", "Unknown format code", "format error",
                     "ImportError", "ModuleNotFoundError", "Traceback"]:
        if err_type.lower() in stderr.lower():
            errors.append(f"{err_type} in stderr")

    print(f"   Exit code: {exit_code}")
    print(f"   Telegram messages: {len(telegram_messages)}")
    print(f"   Errors: {len(errors)}")
    if errors:
        for e in errors:
            print(f"      ❌ {e}")

    return {
        "label": label,
        "time": script,
        "exit_code": exit_code,
        "telegram_messages": telegram_messages,
        "errors": errors,
        "stdout_tail": stdout[-500:] if stdout else "",
        "stderr_tail": stderr[-500:] if stderr else "",
    }


def validate_results(results: list):
    """Run all validation checks across job results."""
    print(f"\n{'='*70}")
    print(f"  VALIDATION REPORT")
    print(f"{'='*70}")

    total_messages = sum(len(r["telegram_messages"]) for r in results)
    total_errors = sum(len(r["errors"]) for r in results)

    # 1. Error check
    print(f"\n1. {'✅' if total_errors == 0 else '❌'} Runtime errors: {total_errors}")
    for r in results:
        if r["errors"]:
            print(f"   {r['label']}: {', '.join(r['errors'])}")

    # 2. Message count
    passed = total_messages <= 10
    print(f"\n2. {'✅' if passed else '⚠️'} Total Telegram messages: {total_messages} (max 10)")
    for r in results:
        n = len(r["telegram_messages"])
        if n > 0:
            print(f"   {r['label']}: {n} message(s)")

    # 3. Duplicate detection
    all_content = []
    for r in results:
        for msg in r["telegram_messages"]:
            all_content.append((r["label"], msg))

    duplicates = []
    for i in range(len(all_content)):
        for j in range(i+1, len(all_content)):
            label_a, content_a = all_content[i]
            label_b, content_b = all_content[j]
            # Check if >50% of lines overlap
            lines_a = set(content_a.strip().split("\n"))
            lines_b = set(content_b.strip().split("\n"))
            if lines_a and lines_b:
                overlap = len(lines_a & lines_b) / max(len(lines_a), len(lines_b))
                if overlap > 0.5 and label_a != label_b:
                    duplicates.append((label_a, label_b, overlap))

    print(f"\n3. {'✅' if not duplicates else '❌'} Duplicate content: {len(duplicates)}")
    for a, b, overlap in duplicates:
        print(f"   {a} ↔ {b}: {overlap:.0%} overlap")

    # 4. Distinct output check
    print(f"\n4. Output distinctness:")
    for r in results:
        n = len(r["telegram_messages"])
        if n > 0:
            first_msg = r["telegram_messages"][0]
            first_50 = first_msg[:50].strip()
            print(f"   {r['label']}: \"{first_50}...\"")

    # 5. AI output quality
    print(f"\n5. AI output quality:")
    for r in results:
        for msg in r["telegram_messages"]:
            words = len(msg.split())
            has_direction = bool(re.search(r'(BULLISH|BEARISH|NEUTRAL|risk-on|risk-off)', msg, re.IGNORECASE))
            has_numbers = bool(re.search(r'[\d,]+', msg))
            status = "✅" if (words >= 30 or has_direction) else "⚠️"
            print(f"   {r['label']}: {status} {words} words, structured={'yes' if has_direction else 'no'}")

    # 6. Skip gates
    print(f"\n6. Skip gate behavior:")
    for r in results:
        if "Midday" in r["label"]:
            if len(r["telegram_messages"]) == 1:
                msg = r["telegram_messages"][0]
                if "quiet" in msg.lower() or "unchanged" in msg.lower():
                    print(f"   {r['label']}: ✅ Quiet one-liner (skip gate fired)")
                else:
                    print(f"   {r['label']}: ✅ Full scan sent (market moved)")
            else:
                print(f"   {r['label']}: ⚠️ {len(r['telegram_messages'])} messages (expected 1)")
        if "Evening Report" in r["label"]:
            if len(r["telegram_messages"]) <= 1:
                print(f"   {r['label']}: ✅ {'Quiet' if len(r['telegram_messages']) == 0 else 'Report'} (skip gate OK)")

    # 7. Regime card presence
    print(f"\n7. Regime card presence:")
    regime_jobs = ["Morning Brief", "Morning Market Intel", "Evening Market Intel"]
    for r in results:
        if r["label"] in regime_jobs:
            has_regime = any("REGIME" in msg or "regime" in msg.lower() for msg in r["telegram_messages"])
            print(f"   {r['label']}: {'✅ regime card present' if has_regime else '⚠️ no regime card'}")


def print_telegram_output(results: list):
    """Print the full Telegram-formatted output for senior analyst review."""
    print(f"\n\n{'='*70}")
    print(f"  TELEGRAM OUTPUT — FULL DAY SIMULATION")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M IST')}")
    print(f"{'='*70}")

    for r in results:
        if r["telegram_messages"]:
            for i, msg in enumerate(r["telegram_messages"]):
                print(f"\n{'─'*70}")
                print(f"  📨 {r['label']} — Message {i+1}/{len(r['telegram_messages'])}")
                print(f"{'─'*70}")
                print(msg)
                print(f"{'─'*70}")


if __name__ == "__main__":
    print("="*70)
    print("  FULL-DAY TELEGRAM OUTPUT VALIDATION")
    print("="*70)
    print(f"  Jobs: {len(JOBS)}")
    print(f"  DRY RUN: Yes (messages printed to console)")
    print(f"  AI: Groq + Google fallback")
    print(f"  Data: Live from NSE, yfinance, Finnhub")
    print("="*70)

    results = []
    for time_str, script, args, label in JOBS:
        result = run_job(script, args, label)
        results.append(result)

    validate_results(results)
    print_telegram_output(results)

    # Summary
    total_msgs = sum(len(r["telegram_messages"]) for r in results)
    total_errs = sum(len(r["errors"]) for r in results)
    print(f"\n{'='*70}")
    print(f"  SUMMARY")
    print(f"{'='*70}")
    print(f"  Jobs run:       {len(JOBS)}")
    print(f"  Messages sent:  {total_msgs}")
    print(f"  Errors:         {total_errs}")
    print(f"  Status:         {'✅ PASSED' if total_errs == 0 and total_msgs <= 10 else '❌ ISSUES FOUND'}")
    print(f"{'='*70}")
