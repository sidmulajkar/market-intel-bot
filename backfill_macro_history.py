"""
Backfill 1 year of macro anchor history into macro_anchor_snapshots.
Uses yfinance batch download for all 19 anchors.

Usage:
    source .venv/bin/activate
    python backfill_macro_history.py              # fetch + insert
    python backfill_macro_history.py --dry-run    # fetch + print, don't insert
"""
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


ANCHORS = [
    {"name": "USD/INR",         "symbol": "USDINR=X"},
    {"name": "Brent Crude",     "symbol": "BZ=F"},
    {"name": "Gold",            "symbol": "GC=F"},
    {"name": "India VIX",       "symbol": "^INDIAVIX"},
    {"name": "Dollar Index",    "symbol": "DX-Y.NYB"},
    {"name": "US 10Y Yield",    "symbol": "^TNX"},
    {"name": "CBOE VIX",        "symbol": "^VIX"},
    {"name": "US High Yield",   "symbol": "HYG"},
    {"name": "WTI Crude",       "symbol": "CL=F"},
    {"name": "USD/JPY",         "symbol": "JPY=X"},
    {"name": "EUR/USD",         "symbol": "EURUSD=X"},
    {"name": "Silver",          "symbol": "SI=F"},
    {"name": "Copper",          "symbol": "HG=F"},
    {"name": "US 2Y Yield",     "symbol": "2YY=F"},
    {"name": "India 10Y Yield", "symbol": "INDIA10Y=X"},
    {"name": "S&P 500 Futures", "symbol": "ES=F"},
    {"name": "Nasdaq Futures",  "symbol": "NQ=F"},
    {"name": "Nikkei 225",      "symbol": "^N225"},
    {"name": "IG Corp Bonds",   "symbol": "LQD"},
    {"name": "Semiconductors",  "symbol": "SOXX"},
]

SYMBOLS = [a["symbol"] for a in ANCHORS]
NAME_MAP = {a["symbol"]: a["name"] for a in ANCHORS}


def fetch_history():
    """Fetch 1 year of daily close data for all anchors."""
    import yfinance as yf
    print("📡 Fetching 1 year of macro anchor history (19 symbols, batch)...")
    raw = yf.download(SYMBOLS, period="1y", interval="1d",
                      auto_adjust=True, progress=False, group_by="ticker")
    if raw.empty:
        print("❌ No data returned from yfinance")
        return None
    return raw


def main():
    dry_run = "--dry-run" in sys.argv

    raw = fetch_history()
    if raw is None:
        sys.exit(1)

    if not dry_run:
        from src.db import save_macro_snapshot

    total = 0
    saved = 0
    errors = []

    for sym in SYMBOLS:
        name = NAME_MAP[sym]
        try:
            # Multi-ticker download: raw[sym] is a DataFrame with 'Close' column
            if sym in raw.columns.get_level_values(0):
                close_s = raw[sym]["Close"].dropna()
            else:
                # Single-ticker or different structure
                close_s = raw["Close"].dropna() if "Close" in raw.columns else None

            if close_s is None or len(close_s) < 2:
                print(f"  ⚠️  {name} ({sym}): insufficient data ({len(close_s) if close_s is not None else 0} points)")
                continue

            dates = close_s.index.tolist()
            vals  = close_s.values.tolist()
            count = 0

            for i, (dt, price) in enumerate(zip(dates, vals)):
                date_str = dt.strftime("%Y-%m-%d")
                price_f = float(price)

                # Compute daily change
                change_pct = None
                if i > 0:
                    prev = float(vals[i - 1])
                    if prev != 0:
                        change_pct = round(((price_f - prev) / prev) * 100, 2)

                if dry_run:
                    if count < 3:
                        print(f"    {date_str}: {price_f} (chg: {change_pct}%)")
                    count += 1
                    total += 1
                    continue

                ok = save_macro_snapshot(
                    date_str=date_str,
                    symbol=sym,
                    name=name,
                    price=round(price_f, 2),
                    change_pct=change_pct,
                    weekly_change_pct=None,
                )
                if ok:
                    saved += 1
                else:
                    errors.append(f"{sym} {date_str}: save returned False")
                total += 1
                count += 1

            print(f"  ✓ {name} ({sym}): {count} dates")

        except Exception as e:
            print(f"  ✗ {name} ({sym}): {e}")
            errors.append(f"{sym}: {e}")

    print(f"\n{'='*50}")
    if dry_run:
        print(f"Total points: {total} | Errors: {len(errors)}")
    else:
        print(f"Total: {total} | Saved: {saved} | Errors: {len(errors)}")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors[:10]:
            print(f"  • {e}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")

    print(f"Done at {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    main()
