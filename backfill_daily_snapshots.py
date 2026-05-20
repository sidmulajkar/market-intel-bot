#!/usr/bin/env python3
"""
Backfill 30 days of daily_market_snapshot with REAL price data.
One yfinance batch call → 22-23 trading days → compute approximate scores → insert to Supabase.

Usage:
    source venv/bin/activate
    python backfill_daily_snapshots.py              # fetch + compute + insert
    python backfill_daily_snapshots.py --sql-only   # generate SQL only
    python backfill_daily_snapshots.py --dry-run    # fetch + compute, don't insert
"""
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def fetch_historical_prices():
    """Fetch 30 days of real price data in one yfinance batch call."""
    import yfinance as yf

    print("📡 Fetching 30 days of real price data (one batch call)...")

    # Only columns that exist in daily_market_snapshot table
    tickers = {
        '^NSEI': 'nifty_close',
        '^INDIAVIX': 'india_vix',
        '^VIX': 'cboe_vix',
        'BZ=F': 'brent',
        'GC=F': 'gold',
        'DX-Y.NYB': 'dxy',
        '^TNX': 'us_10y',
        'USDINR=X': 'usdinr',
        'HG=F': 'copper',
    }

    data = yf.download(list(tickers.keys()), period='1y', interval='1d', progress=False)

    if data.empty:
        print("❌ No data returned from yfinance")
        return None

    # Build daily snapshots
    snapshots = []
    dates = data.index.tolist()

    for i, date in enumerate(dates):
        date_str = date.strftime('%Y-%m-%d')

        row = {'date': date_str}

        for ticker, col_name in tickers.items():
            try:
                val = data['Close'][ticker].iloc[i]
                if val == val:  # not NaN
                    row[col_name] = round(float(val), 2)
            except (KeyError, IndexError):
                pass

        # Compute Nifty return
        if i > 0 and 'nifty_close' in row:
            try:
                prev_close = data['Close']['^NSEI'].iloc[i-1]
                if prev_close == prev_close and prev_close > 0:
                    row['nifty_return_1d'] = round((row['nifty_close'] / float(prev_close) - 1) * 100, 2)
            except (KeyError, IndexError):
                pass

        snapshots.append(row)

    print(f"  ✅ {len(snapshots)} days fetched ({snapshots[0]['date']} to {snapshots[-1]['date']})")
    return snapshots


def compute_approximate_scores(snapshots):
    """
    Compute approximate bull_bear/structural/sentiment from price data.
    This is a FAST approximation — no API calls, just math on prices.
    The daily cron will replace these with real computed scores over time.
    """
    print("🧮 Computing approximate scores from price data...")

    from datetime import datetime, timedelta
    cutoff_30d = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    for snap in snapshots:
        vix = snap.get('india_vix', 15)
        nifty_return = snap.get('nifty_return_1d', 0)
        dxy = snap.get('dxy', 100)
        brent = snap.get('brent', 80)
        hyg = snap.get('hyg', 80)

        # VIX factor: low VIX = bullish, high VIX = bearish
        vix_factor = max(0, min(100, (30 - vix) / 30 * 100))

        # Momentum factor: positive return = bullish
        momentum_factor = max(0, min(100, nifty_return * 10 + 50))

        # DXY factor: weak dollar = bullish for EM
        dxy_factor = max(0, min(100, (105 - dxy) / 10 * 100))

        # Oil factor: low oil = bullish for India
        oil_factor = max(0, min(100, (100 - brent) / 30 * 100 + 50))

        # Credit factor: HYG rising = risk-on
        credit_factor = 50  # neutral default (no intraday HYG return)

        # Compute scores
        bull_bear = round(vix_factor * 0.35 + momentum_factor * 0.25 + dxy_factor * 0.2 + oil_factor * 0.2)
        structural = round(vix_factor * 0.4 + momentum_factor * 0.3 + dxy_factor * 0.15 + oil_factor * 0.15)
        sentiment = round(vix_factor * 0.5 + momentum_factor * 0.2 + credit_factor * 0.15 + oil_factor * 0.15)

        # Clamp
        bull_bear = max(15, min(85, bull_bear))
        structural = max(15, min(85, structural))
        sentiment = max(15, min(85, sentiment))

        snap['bull_bear_score'] = bull_bear
        snap['structural_score'] = structural
        snap['sentiment_score'] = sentiment
        snap['cluster_gap'] = abs(structural - sentiment)
        # Older rows are less reliable (price-only estimation)
        snap['data_quality'] = 'estimated_from_prices' if snap['date'] >= cutoff_30d else 'historical_price_based'

    print(f"  ✅ Scores computed for {len(snapshots)} days")
    return snapshots


def generate_sql(snapshots):
    """Generate SQL INSERT statements."""
    lines = []
    lines.append("-- Backfill: 30 days of daily_market_snapshot with REAL price data")
    lines.append(f"-- Generated: {datetime.now().isoformat()}")
    lines.append(f"-- {len(snapshots)} days, all data from yfinance")
    lines.append("-- Scores are APPROXIMATE (from prices only) — daily cron will replace with real")
    lines.append("")

    # Ensure columns exist
    lines.append("ALTER TABLE daily_market_snapshot")
    lines.append("    ADD COLUMN IF NOT EXISTS structural_score DOUBLE PRECISION,")
    lines.append("    ADD COLUMN IF NOT EXISTS sentiment_score DOUBLE PRECISION,")
    lines.append("    ADD COLUMN IF NOT EXISTS cluster_gap DOUBLE PRECISION,")
    lines.append("    ADD COLUMN IF NOT EXISTS data_quality TEXT DEFAULT 'real';")
    lines.append("")

    for snap in snapshots:
        cols = []
        vals = []
        for k, v in snap.items():
            if v is not None:
                cols.append(k)
                if k == 'date':
                    vals.append(f"'{v}'")
                elif k == 'data_quality':
                    vals.append(f"'{v}'")
                elif isinstance(v, str):
                    vals.append(f"'{v}'")
                else:
                    vals.append(str(v))

        if not cols:
            continue

        lines.append(f"INSERT INTO daily_market_snapshot ({', '.join(cols)})")
        lines.append(f"VALUES ({', '.join(vals)})")
        lines.append("ON CONFLICT (date) DO UPDATE SET")
        update_cols = [f"    {c} = EXCLUDED.{c}" for c in cols if c != 'date']
        lines.append(",\n".join(update_cols) + ";")

    lines.append("")
    lines.append("-- Verify")
    lines.append("SELECT date, nifty_close, india_vix, bull_bear_score, structural_score, sentiment_score, cluster_gap, data_quality")
    lines.append("FROM daily_market_snapshot ORDER BY date DESC LIMIT 35;")

    return "\n".join(lines)


def insert_to_supabase(snapshots):
    """Insert snapshots directly to Supabase. Skips rows with real data."""
    from src.db import get_client

    client = get_client()
    if not client:
        print("  ❌ Supabase not available")
        return

    print(f"\n📤 Inserting {len(snapshots)} days to Supabase...")
    ok_count = 0
    skipped = 0

    for snap in snapshots:
        # Check if row exists with real data — don't overwrite
        try:
            existing = client.table('daily_market_snapshot')\
                .select('data_quality')\
                .eq('date', snap['date'])\
                .execute()

            if existing.data and existing.data[0].get('data_quality') == 'real':
                skipped += 1
                continue
        except Exception:
            pass  # Table might not have data_quality column yet

        # Upsert (insert or update)
        try:
            client.table('daily_market_snapshot').upsert(snap).execute()
            ok_count += 1
        except Exception as e:
            print(f"  ❌ Failed {snap['date']}: {e}")

    print(f"  ✅ Inserted/updated {ok_count} days")
    if skipped:
        print(f"  ⏭️ Skipped {skipped} days (already has real data)")


def main():
    args = sys.argv[1:]
    sql_only = '--sql-only' in args
    dry_run = '--dry-run' in args

    # Step 1: Fetch real prices
    snapshots = fetch_historical_prices()
    if not snapshots:
        print("❌ No data fetched. Exiting.")
        return

    # Step 2: Compute approximate scores
    snapshots = compute_approximate_scores(snapshots)

    # Step 3: Show summary
    print(f"\n📊 Summary:")
    for snap in snapshots[-5:]:  # last 5 days
        print(f"  {snap['date']}: Nifty={snap.get('nifty_close', 'N/A')}, "
              f"VIX={snap.get('india_vix', 'N/A')}, "
              f"BB={snap.get('bull_bear_score', 'N/A')}, "
              f"Struct={snap.get('structural_score', 'N/A')}, "
              f"Sent={snap.get('sentiment_score', 'N/A')}, "
              f"Gap={snap.get('cluster_gap', 'N/A')}")

    # Step 4: Generate SQL
    sql = generate_sql(snapshots)
    sql_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sql', 'backfill_snapshots_30d.sql')
    with open(sql_path, 'w') as f:
        f.write(sql)
    print(f"\n📄 SQL written to: {sql_path}")

    # Step 5: Insert to Supabase
    if not sql_only and not dry_run:
        insert_to_supabase(snapshots)

    print(f"\n{'='*60}")
    print("DONE")
    print(f"{'='*60}")
    print(f"  Days: {len(snapshots)}")
    print(f"  Date range: {snapshots[0]['date']} to {snapshots[-1]['date']}")
    print(f"  Data quality: estimated_from_prices")
    print(f"  Daily cron will replace with real scores over time")


if __name__ == '__main__':
    main()
