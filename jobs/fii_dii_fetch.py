import sys
import os
import requests
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db              import save_fii_dii_flow
from src.telegram_sender import send_text

NSE_HEADERS = {
    "User-Agent":  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer":      "https://www.nseindia.com/",
    "Accept":       "application/json, text/plain, */*",
}

# ── Date helpers ─────────────────────────────────────────────────
def _trading_date() -> datetime:
    """Return the trading date to fetch. Mon-Fri → today. Sat-Sun → last Friday."""
    today = datetime.now()
    if today.weekday() == 5:
        return today - timedelta(days=1)
    elif today.weekday() == 6:
        return today - timedelta(days=2)
    return today


def _fallback_dates() -> list:
    """Dates to try in order: trading date, then prev trading days (skip weekends)."""
    dates = [_trading_date()]
    for _ in range(5):
        prev = dates[-1] - timedelta(days=1)
        if prev.weekday() < 5:
            dates.append(prev)
    return dates


def _parse_cr(val: str) -> float:
    """Parse Indian number string like '16,809.34' → 16809.34"""
    try:
        return float(val.replace(",", "").strip())
    except Exception:
        return 0.0


# ── Fetch ───────────────────────────────────────────────────────
def fetch_fii_dii() -> list:
    """
    Fetch FII + DII from NSE JSON API.
    API: GET https://www.nseindia.com/api/fiidiiTradeNse
    Returns: [{date, fiinet_cr, diinet_cr}]
    """
    for dt in _fallback_dates():
        # Try date param — fall back to no-param (latest available)
        url = f"https://www.nseindia.com/api/fiidiiTradeNse"
        try:
            resp = requests.get(url, headers=NSE_HEADERS, timeout=15)
            if resp.status_code != 200:
                print(f"⚠️  {url} → {resp.status_code}")
                continue

            data = resp.json()
            if not data:
                continue

            # Parse JSON response
            fiinet_cr = None
            diinet_cr = None
            iso_date  = None

            for row in data:
                cat  = (row.get("category") or "").strip()
                date_val = row.get("date") or ""
                net_val  = row.get("netValue") or "0"

                # Parse date: "14-May-2026" → "2026-05-14"
                if not iso_date and date_val:
                    try:
                        iso_date = datetime.strptime(date_val.strip(), "%d-%b-%Y").strftime("%Y-%m-%d")
                    except Exception:
                        pass

                net = _parse_cr(net_val)
                if "FII" in cat.upper() or "FPI" in cat.upper():
                    fiinet_cr = net
                elif "DII" in cat.upper():
                    diinet_cr = net

            if iso_date and fiinet_cr is not None and diinet_cr is not None:
                return [{"date": iso_date, "fiinet_cr": fiinet_cr, "diinet_cr": diinet_cr}]

        except Exception as e:
            print(f"⚠️  API attempt: {e}")
            continue

    print("⚠️  No FII/DII data from NSE")
    return []


# ── Main ──────────────────────────────────────────────────────────
def main():
    print("=" * 50)
    print("📊 FII/DII FETCH STARTING")
    print("=" * 50)

    rows = fetch_fii_dii()
    if not rows:
        print("⚠️  FII/DII fetch failed — no data returned")
        send_text("⚠️  *FII/DII Fetch Failed*\nNo data from NSE.")
        return

    saved = 0
    for row in rows:
        if save_fii_dii_flow(row["date"], row["fiinet_cr"], row["diinet_cr"]):
            saved += 1

    print(f"✅  FII/DII: {saved}/{len(rows)} rows upserted")
    print(f"   FII:  ₹{rows[0]['fiinet_cr']:,.2f} Cr")
    print(f"   DII:  ₹{rows[0]['diinet_cr']:,.2f} Cr")
    print("=" * 50)


if __name__ == "__main__":
    main()