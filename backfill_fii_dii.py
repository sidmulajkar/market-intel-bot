"""
Backfill FII/DII flow data from sql/fii-dii-data.json into Supabase.
Usage: python backfill_fii_dii.py
Requires: SUPABASE_URL, SUPABASE_KEY env vars (or apikeys.txt)
"""
import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.db import save_fii_dii_flow

DATA_FILE = os.path.join(os.path.dirname(__file__), "sql", "fii-dii-data.json")


def parse_date(date_str: str) -> str:
    """Convert '20 May 2026' → '2026-05-20'"""
    dt = datetime.strptime(date_str.strip(), "%d %b %Y")
    return dt.strftime("%Y-%m-%d")


def main():
    with open(DATA_FILE, "r") as f:
        raw = f.read()

    # Strip markdown code fences if present
    if raw.strip().startswith("```"):
        lines = raw.strip().split("\n")
        # Remove first and last lines (```json and ```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw = "\n".join(lines)

    data = json.loads(raw)

    total = 0
    success = 0
    errors = 0

    for month_name, month_data in data.items():
        records = month_data.get("records", [])
        print(f"\n{month_name}: {len(records)} records")

        for rec in records:
            total += 1
            date_str = rec["date"]
            fii_net = rec["FII"]["net"]
            dii_net = rec["DII"]["net"]

            try:
                date_iso = parse_date(date_str)
                ok = save_fii_dii_flow(date_iso, fii_net, dii_net)
                if ok:
                    success += 1
                    print(f"  ✓ {date_iso}: FII {fii_net:+,.0f} | DII {dii_net:+,.0f}")
                else:
                    errors += 1
                    print(f"  ✗ {date_iso}: save returned False")
            except Exception as e:
                errors += 1
                print(f"  ✗ {date_str}: {e}")

    print(f"\n{'='*40}")
    print(f"Total: {total} | Success: {success} | Errors: {errors}")


if __name__ == "__main__":
    main()
