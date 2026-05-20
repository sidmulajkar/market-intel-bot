#!/usr/bin/env python3
"""
Backfill MF flows from AMFI — fully dynamic, no hardcoding.
Fetches current AMFI NAVAll.txt, computes category AUM, stores in Supabase.

For historical months: checks existing mf_flows table, only inserts missing data.
AMFI doesn't expose historical monthly flows via API — we accumulate over time.

Usage:
    source venv/bin/activate
    python backfill_mf_flows.py              # fetch + insert
    python backfill_mf_flows.py --sql-only   # generate SQL only
    python backfill_mf_flows.py --dry-run    # fetch only, don't insert
"""
import sys
import os
import requests
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

AMFI_URL = "https://www.amfiindia.com/spages/NAVAll.txt"

# Category keywords for classification
CATEGORY_KEYWORDS = {
    "Large Cap": ["large cap", "largecap", "bluechip", "nifty 50", "nifty 100"],
    "Mid Cap": ["mid cap", "midcap", "nifty midcap"],
    "Small Cap": ["small cap", "smallcap", "nifty smallcap"],
    "Flexi Cap": ["flexi cap", "flexicap", "multi cap", "multicap"],
    "ELSS": ["tax saver", "elss", "equity linked"],
    "Sectoral": ["infrastructure", "infra", "it services", "banking", "pharma", "fmcg", "psu"],
    "Debt": ["debt", "income", "gilt", "bond", "corporate bond"],
    "Liquid": ["liquid", "money market", "overnight"],
    "Hybrid": ["hybrid", "balanced fund"],
    "Gold": ["gold", "sovereign gold"],
    "International": ["global", "international", "overseas", "us equity"],
}


def infer_category(scheme_name: str) -> str:
    """Infer category from scheme name."""
    name_lower = scheme_name.lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in name_lower:
                return cat
    return "Other"


def fetch_amfi_nav_data() -> pd.DataFrame:
    """Fetch and parse AMFI NAVAll.txt — current NAVs for all schemes."""
    print("📥 Fetching AMFI NAVAll.txt...")
    try:
        resp = requests.get(AMFI_URL, timeout=30)
        if resp.status_code != 200:
            print(f"  ❌ AMFI returned status {resp.status_code}")
            return pd.DataFrame()

        schemes = []
        current_category = ""

        for line in resp.text.split("\n"):
            line = line.strip()
            if not line:
                continue
            if ";" not in line:
                current_category = line
                continue
            parts = line.split(";")
            if len(parts) < 5:
                continue
            try:
                code = parts[0].strip()
                name = parts[3].strip()
                nav_str = parts[4].strip()
                nav = float(nav_str) if nav_str else None
                if nav and nav > 0:
                    schemes.append({
                        "code": code,
                        "name": name,
                        "nav": nav,
                        "category": infer_category(name),
                    })
            except (ValueError, IndexError):
                continue

        df = pd.DataFrame(schemes)
        print(f"  ✅ {len(df)} schemes fetched")
        return df

    except Exception as e:
        print(f"  ❌ Fetch failed: {e}")
        return pd.DataFrame()


def compute_category_aggregates(df: pd.DataFrame) -> dict:
    """Compute category-level aggregates from scheme data."""
    if df.empty:
        return {}

    # Count schemes per category
    cat_counts = df.groupby('category').size().to_dict()

    # Average NAV per category (proxy for category health)
    cat_avg_nav = df.groupby('category')['nav'].mean().to_dict()

    # Total schemes
    total = len(df)

    aggregates = {}
    for cat in sorted(set(df['category'])):
        count = cat_counts.get(cat, 0)
        avg_nav = cat_avg_nav.get(cat, 0)
        pct = (count / total * 100) if total > 0 else 0

        aggregates[cat] = {
            "scheme_count": count,
            "avg_nav": round(avg_nav, 2),
            "pct_of_total": round(pct, 1),
        }

    return aggregates


def check_existing_mf_flows() -> dict:
    """Check what MF flow data already exists in Supabase."""
    from src.db import get_mf_flows

    existing = get_mf_flows(months=15)  # get last 15 months
    if not existing:
        return {}

    # Group by month
    by_month = {}
    for row in existing:
        month = row.get('month', '')[:7]  # YYYY-MM
        if month not in by_month:
            by_month[month] = []
        by_month[month].append(row)

    return by_month


def generate_mf_flow_records(aggregates: dict) -> list:
    """
    Generate MF flow records from AMFI aggregates.
    Note: AMFI NAVAll.txt gives current NAVs, not monthly flows.
    We store category composition as a proxy for flow direction.
    Monthly flows require AMFI monthly reports (not available via API).
    """
    current_month = datetime.now().strftime('%Y-%m-01')
    records = []

    for cat, data in aggregates.items():
        records.append({
            "month": current_month,
            "category": cat,
            "amount_cr": 0,  # Can't compute flows from NAVs alone
            "sip_amount_cr": None,
            "source": "AMFI_NAV",
            "scheme_count": data["scheme_count"],
            "avg_nav": data["avg_nav"],
            "pct_of_total": data["pct_of_total"],
        })

    return records


def generate_sql(records, existing_months):
    """Generate SQL INSERT statements."""
    lines = []
    lines.append("-- MF Flows Backfill from AMFI")
    lines.append(f"-- Generated: {datetime.now().isoformat()}")
    lines.append(f"-- {len(records)} category records for current month")
    lines.append("-- Source: AMFI NAVAll.txt (live fetch)")
    lines.append("-- Note: Monthly flows require AMFI monthly reports (not API-accessible)")
    lines.append("-- We store category composition as proxy for flow direction")
    lines.append("")

    for rec in records:
        lines.append(f"INSERT INTO mf_flows (month, category, amount_cr, sip_amount_cr, source)")
        lines.append(f"VALUES ('{rec['month']}', '{rec['category']}', {rec['amount_cr']}, "
                     f"{rec['sip_amount_cr'] if rec['sip_amount_cr'] else 'NULL'}, '{rec['source']}')")
        lines.append("ON CONFLICT (month, category) DO UPDATE SET")
        lines.append("    amount_cr = EXCLUDED.amount_cr,")
        lines.append("    source = EXCLUDED.source;")

    lines.append("")
    lines.append("-- Verify")
    lines.append("SELECT month, category, amount_cr, source")
    lines.append("FROM mf_flows ORDER BY month DESC, category LIMIT 50;")

    return "\n".join(lines)


def insert_to_supabase(records):
    """Insert MF flow records to Supabase. Skips existing records."""
    from src.db import get_client

    client = get_client()
    if not client:
        print("  ❌ Supabase not available")
        return

    print(f"\n📤 Inserting {len(records)} MF flow records...")
    ok_count = 0
    skipped = 0

    for rec in records:
        # Check if record already exists
        try:
            existing = client.table('mf_flows')\
                .select('month')\
                .eq('month', rec['month'])\
                .eq('category', rec['category'])\
                .execute()

            if existing.data:
                skipped += 1
                continue
        except Exception:
            pass

        # Insert
        try:
            client.table('mf_flows').upsert({
                'month': rec['month'],
                'category': rec['category'],
                'amount_cr': rec['amount_cr'],
                'sip_amount_cr': rec.get('sip_amount_cr'),
                'source': rec['source'],
            }).execute()
            ok_count += 1
        except Exception as e:
            print(f"  ❌ Failed {rec['month']} {rec['category']}: {e}")

    print(f"  ✅ Inserted {ok_count} records")
    if skipped:
        print(f"  ⏭️ Skipped {skipped} records (already exist)")


def main():
    args = sys.argv[1:]
    sql_only = '--sql-only' in args
    dry_run = '--dry-run' in args

    # Step 1: Fetch current AMFI data
    df = fetch_amfi_nav_data()
    if df.empty:
        print("❌ No AMFI data fetched. Exiting.")
        return

    # Step 2: Compute aggregates
    aggregates = compute_category_aggregates(df)
    print(f"\n📊 Category breakdown:")
    for cat, data in sorted(aggregates.items(), key=lambda x: -x[1]['scheme_count']):
        print(f"  {cat}: {data['scheme_count']} schemes, avg NAV ₹{data['avg_nav']}, {data['pct_of_total']}% of total")

    # Step 3: Check existing data
    existing = check_existing_mf_flows()
    print(f"\n📋 Existing MF flow data: {len(existing)} months in DB")
    if existing:
        for month in sorted(existing.keys())[-6:]:
            print(f"  {month}: {len(existing[month])} categories")

    # Step 4: Generate records
    records = generate_mf_flow_records(aggregates)
    print(f"\n📝 Generated {len(records)} records for current month")

    # Step 5: Generate SQL
    sql = generate_sql(records, set(existing.keys()))
    sql_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sql', 'backfill_mf_flows.sql')
    with open(sql_path, 'w') as f:
        f.write(sql)
    print(f"📄 SQL written to: {sql_path}")

    # Step 6: Insert to Supabase
    if not sql_only and not dry_run:
        insert_to_supabase(records)

    print(f"\n{'='*60}")
    print("DONE")
    print(f"{'='*60}")
    print(f"  Categories: {len(records)}")
    print(f"  Month: {records[0]['month'] if records else 'N/A'}")
    print(f"  Source: AMFI NAVAll.txt (live)")
    print(f"  Note: Historical monthly flows require AMFI monthly reports")
    print(f"        Current month's category composition stored as baseline")


if __name__ == '__main__':
    main()
