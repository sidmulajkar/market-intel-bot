import sys
import os
import time
import requests
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db       import save_fii_dii_flow
from src.telegram_sender import send_text


# ── NSE Session Setup ─────────────────────────────────────────────
def _nse_session():
    """
    Create a requests session with browser-like headers.
    NSE requires cookies set via homepage hit before data endpoints respond.
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept":          "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer":         "https://www.nseindia.com/",
    })
    # Step 1: Get cookies from homepage
    try:
        session.get("https://www.nseindia.com", timeout=10)
    except Exception:
        pass
    return session


# ── NSE FII/DII Fetcher ────────────────────────────────────────────
def fetch_fii_dii() -> list:
    """
    Fetch FII + DII daily net flows from NSE India.
    Returns list of dicts: {date, fiinet_cr, diinet_cr}
    Returns empty list on any failure.
    """
    session = _nse_session()
    results = {}

    # Combined endpoint (preferred)
    endpoints = [
        ("https://www.nseindia.com/api/fii-dii-data", None),
        ("https://www.nseindia.com/api/fiidiitraderehab?type=fii", "fii"),
        ("https://www.nseindia.com/api/fiidiitraderehab?type=dii", "dii"),
    ]

    for url, target in endpoints:
        try:
            resp = session.get(url, timeout=15)
            if resp.status_code != 200:
                continue
            data = resp.json()
            if not data:
                continue

            # Parse based on endpoint structure
            if target is None:
                # Combined: usually has "fii" and "dii" keys
                for key in ["fii", "dii"]:
                    if key in data:
                        _parse_fii_dii_block(data[key], results, key)
            elif target == "fii":
                _parse_fii_dii_block(data, results, "fii")
            elif target == "dii":
                _parse_fii_dii_block(data, results, "dii")

        except Exception as e:
            print(f"⚠️ NSE endpoint {url}: {e}")
            continue

    if not results:
        return []

    # Convert to list, keep last 5 trading days
    cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    rows = []
    for date_str, vals in results.items():
        if date_str >= cutoff:
            rows.append({
                "date":       date_str,
                "fiinet_cr":  vals.get("fii", 0),
                "diinet_cr":  vals.get("dii", 0),
            })
    return rows


def _parse_fii_dii_block(data, results: dict, key: str):
    """
    Parse FII or DII block from NSE JSON.
    NSE date format: "03-Jan-2025" → "2025-01-03"
    """
    if not isinstance(data, list):
        return
    for item in data:
        date_str = item.get("date") or item.get("tradingDate") or item.get("DATE")
        if not date_str:
            continue
        iso_date = _parse_nse_date(date_str)
        if not iso_date:
            continue
        net_val = float(item.get("netValue") or item.get("netvalue") or 0)
        if iso_date not in results:
            results[iso_date] = {}
        results[iso_date][key] = net_val


def _parse_nse_date(date_str: str) -> str:
    """Convert NSE date '03-Jan-2025' → '2025-01-03'"""
    try:
        dt = datetime.strptime(date_str.strip(), "%d-%b-%Y")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return ""


# ── Main ───────────────────────────────────────────────────────────
def main():
    print("=" * 50)
    print("📊 FII/DII FETCH STARTING")
    print("=" * 50)

    if datetime.now().weekday() >= 5:
        print("⏭ Weekend — skipping FII/DII fetch")
        return

    rows = fetch_fii_dii()
    if not rows:
        print("⚠️ FII/DII fetch failed — no data returned")
        send_text("⚠️ *FII/DII Fetch Failed*\nNo data from NSE.")
        return

    saved = 0
    for row in rows:
        if save_fii_dii_flow(row["date"], row["fiinet_cr"], row["diinet_cr"]):
            saved += 1

    print(f"✅ FII/DII: {saved}/{len(rows)} rows upserted")
    print("=" * 50)


if __name__ == "__main__":
    main()