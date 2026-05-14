import sys
import os
import csv
import io
import requests
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db              import save_fii_dii_flow
from src.telegram_sender import send_text


# ── CSV URL Pattern ────────────────────────────────────────────────
def _csv_url() -> str:
    """Build NSE FII/DII CSV URL for today."""
    today = datetime.now().strftime("%d%m%Y")
    return f"https://www.nseindia.com/archives/nsccl/fii_dii/FII_DII_CM_{today}.csv"


# ── NSE Session ─────────────────────────────────────────────────────
def _nse_session():
    """Browser-like session for NSE."""
    session = requests.Session()
    session.headers.update({
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer":         "https://www.nseindia.com/",
    })
    try:
        session.get("https://www.nseindia.com", timeout=10)
    except Exception:
        pass
    return session


# ── Parse Indian number format ────────────────────────────────────
def _parse_cr(val: str) -> float:
    """Parse Indian comma number like '16,809.34' → 16809.34"""
    try:
        return float(val.replace(",", "").strip())
    except Exception:
        return 0.0


# ── Fetch CSV ─────────────────────────────────────────────────────
def fetch_fii_dii() -> list:
    """
    Fetch FII + DII daily net from NSE CSV.
    Returns list of dicts: [{date, fiinet_cr, diinet_cr}, ...]
    """
    session = _nse_session()

    # Try today's CSV first, then yesterday's
    dates_to_try = [
        datetime.now().strftime("%d%m%Y"),
        (datetime.now() - timedelta(days=1)).strftime("%d%m%Y"),
    ]

    for date_str in dates_to_try:
        url = f"https://www.nseindia.com/archives/nsccl/fii_dii/FII_DII_CM_{date_str}.csv"
        try:
            resp = session.get(url, timeout=15)
            if resp.status_code != 200:
                continue
            text = resp.text.strip()
            if not text:
                continue

            # Parse CSV
            reader = csv.DictReader(io.StringIO(text))
            rows = list(reader)

            if not rows:
                continue

            # First table: Capital Market Segment (NSE only)
            # Columns: Category, Date, Buy Value(₹ Crores), Sell Value (₹ Crores), Net Value (₹ Crores)
            fiinet_cr = None
            diinet_cr = None
            iso_date  = None

            for row in rows:
                cat = (row.get("Category") or row.get("category") or "").strip()
                if not cat:
                    continue

                # Date: "14-May-2026" → "2026-05-14"
                date_val = row.get("Date") or row.get("date") or ""
                if not iso_date and date_val:
                    try:
                        dt = datetime.strptime(date_val.strip(), "%d-%b-%Y")
                        iso_date = dt.strftime("%Y-%m-%d")
                    except Exception:
                        pass

                if "FII" in cat.upper() or "FPI" in cat.upper():
                    net = _parse_cr(row.get("Net Value(₹ Crores)") or
                                    row.get("Net Value") or "0")
                    fiinet_cr = net
                elif "DII" in cat.upper():
                    net = _parse_cr(row.get("Net Value(₹ Crores)") or
                                    row.get("Net Value") or "0")
                    diinet_cr = net

            if iso_date and fiinet_cr is not None and diinet_cr is not None:
                return [{"date": iso_date, "fiinet_cr": fiinet_cr, "diinet_cr": diinet_cr}]

        except Exception as e:
            print(f"⚠️ CSV fetch attempt ({url}): {e}")
            continue

    print("⚠️ No FII/DII CSV found for today or yesterday")
    return []


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
    print(f"   FII:  ₹{rows[0]['fiinet_cr']:,.2f} Cr")
    print(f"   DII:  ₹{rows[0]['diinet_cr']:,.2f} Cr")
    print("=" * 50)


if __name__ == "__main__":
    main()