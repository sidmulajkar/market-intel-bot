"""
Bulk & Block Deals Tracker
Sources: NSE API (direct HTTP session) + BSE HTML table
Dependencies: requests, pandas — both already in requirements.txt
No nsefin library needed — calls NSE endpoints directly
"""
import time
import random
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# ── NSE HEADERS (required — NSE blocks plain requests) ────────────
NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept":          "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer":         "https://www.nseindia.com/",
    "Connection":      "keep-alive",
}

BSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bseindia.com/",
}


# ── NSE SESSION ───────────────────────────────────────────────────

class NSESession:
    """
    NSE requires a valid session cookie from the homepage first.
    This class handles the cookie handshake automatically.
    Rate limit: max 3 requests per second — respected with delays.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(NSE_HEADERS)
        self._initialised = False

    def _init(self):
        """Visit NSE homepage to obtain session cookies"""
        if self._initialised:
            return
        try:
            self.session.get(
                "https://www.nseindia.com",
                timeout=15,
            )
            time.sleep(1.5)
            self._initialised = True
            print("  ✅ NSE session initialised")
        except Exception as e:
            print(f"  ⚠️  NSE session init failed: {e}")

    def get(self, url: str, params: dict = None) -> Optional[dict]:
        """
        GET request to NSE API.
        Handles rate limiting (429) with automatic retry.
        """
        self._init()
        # Polite delay between requests
        time.sleep(random.uniform(0.5, 1.0))
        try:
            resp = self.session.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 401:
                # Session expired — reinitialise and retry once
                print("  ⚠️  NSE session expired — reinitialising...")
                self._initialised = False
                self._init()
                resp = self.session.get(url, params=params, timeout=15)
                if resp.status_code == 200:
                    return resp.json()
            elif resp.status_code == 429:
                print("  ⏳ NSE rate limited — waiting 60s...")
                time.sleep(60)
                return self.get(url, params)
            else:
                print(f"  ⚠️  NSE HTTP {resp.status_code}: {url}")
                return None
        except Exception as e:
            print(f"  ⚠️  NSE request failed: {e}")
            return None


# ── NSE BULK DEALS ────────────────────────────────────────────────

def fetch_nse_bulk_deals() -> List[Dict]:
    """
    Fetch today's bulk deals from NSE free API.
    Bulk deal = transaction > 0.5% of total equity shares.
    """
    print("  📋 Fetching NSE bulk deals...")
    nse  = NSESession()
    url  = "https://www.nseindia.com/api/snapshot-capital-market-largedeal"
    data = nse.get(url, params={"bandtype": "bulk_deals", "view": "mode"})

    if not data:
        print("  ⚠️  NSE bulk deals: no data returned")
        return []

    raw_list = data if isinstance(data, list) else data.get("data", [])
    deals    = []

    for item in raw_list:
        try:
            qty   = _safe_int(item.get("tdQty",  "0"))
            price = _safe_float(item.get("tdVal", "0"))
            deals.append({
                "symbol":     str(item.get("symbol",      "")),
                "company":    str(item.get("companyName", "")),
                "client":     str(item.get("clientName",  "")),
                "buy_sell":   str(item.get("buySell",     "")),
                "quantity":   qty,
                "price":      price,
                "deal_value": round((qty * price) / 1e7, 2),  # In Crores
                "deal_type":  "BULK",
                "exchange":   "NSE",
                "date":       datetime.now().strftime("%d-%m-%Y"),
            })
        except Exception:
            continue

    print(f"  ✅ NSE bulk deals: {len(deals)} found")
    return deals


# ── NSE BLOCK DEALS ───────────────────────────────────────────────

def fetch_nse_block_deals() -> List[Dict]:
    """
    Fetch today's block deals from NSE.
    Block deal = min 500,000 shares OR min Rs 5 crore value.
    """
    print("  📋 Fetching NSE block deals...")
    nse  = NSESession()
    url  = "https://www.nseindia.com/api/snapshot-capital-market-largedeal"
    data = nse.get(url, params={"bandtype": "block_deals", "view": "mode"})

    if not data:
        print("  ⚠️  NSE block deals: no data returned")
        return []

    raw_list = data if isinstance(data, list) else data.get("data", [])
    deals    = []

    for item in raw_list:
        try:
            qty   = _safe_int(item.get("tdQty",  "0"))
            price = _safe_float(item.get("tdVal", "0"))
            deals.append({
                "symbol":     str(item.get("symbol",      "")),
                "company":    str(item.get("companyName", "")),
                "client":     str(item.get("clientName",  "")),
                "buy_sell":   str(item.get("buySell",     "")),
                "quantity":   qty,
                "price":      price,
                "deal_value": round((qty * price) / 1e7, 2),
                "deal_type":  "BLOCK",
                "exchange":   "NSE",
                "date":       datetime.now().strftime("%d-%m-%Y"),
            })
        except Exception:
            continue

    print(f"  ✅ NSE block deals: {len(deals)} found")
    return deals


# ── BSE BULK DEALS ────────────────────────────────────────────────

def fetch_bse_bulk_deals() -> List[Dict]:
    """
    Fetch bulk deals from BSE.
    BSE publishes these as an HTML table — no auth required.
    """
    print("  📋 Fetching BSE bulk deals...")
    today = datetime.now().strftime("%Y%m%d")
    url   = (
        "https://www.bseindia.com/markets/equity/"
        f"EQReports/BulkDealDetails.aspx?expandable=0&strDate={today}"
    )
    try:
        resp = requests.get(url, headers=BSE_HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"  ⚠️  BSE HTTP {resp.status_code}")
            return []

        tables = pd.read_html(resp.text)
        if not tables:
            print("  ⚠️  BSE: no tables found in response")
            return []

        df      = tables[0]
        df.columns = [str(c).strip() for c in df.columns]
        deals   = []

        for _, row in df.iterrows():
            try:
                qty = _safe_int(
                    str(row.get("Quantity Traded",
                        row.get("Quantity", "0")))
                )
                price = _safe_float(
                    str(row.get("Trade Price / Wt. Avg. Price",
                        row.get("Price", "0")))
                )
                deals.append({
                    "symbol":     str(row.get("Scrip Code", "")),
                    "company":    str(row.get("Scrip Name",
                                   row.get("Company", ""))),
                    "client":     str(row.get("Client Name", "")),
                    "buy_sell":   str(row.get("Buy / Sell",
                                   row.get("Buy/Sell", ""))),
                    "quantity":   qty,
                    "price":      price,
                    "deal_value": round((qty * price) / 1e7, 2),
                    "deal_type":  "BULK",
                    "exchange":   "BSE",
                    "date":       datetime.now().strftime("%d-%m-%Y"),
                })
            except Exception:
                continue

        print(f"  ✅ BSE bulk deals: {len(deals)} found")
        return deals

    except Exception as e:
        print(f"  ⚠️  BSE bulk deals error: {e}")
        return []


# ── MAIN AGGREGATOR ───────────────────────────────────────────────

def get_all_deals(watchlist: List[str] = None) -> Dict:
    """
    Fetch and combine NSE bulk + NSE block + BSE bulk deals.
    Optionally filter to watchlist symbols only.
    Returns categorised dict for Telegram formatting.
    """
    print("📋 Starting deals fetch...")
    bulk  = fetch_nse_bulk_deals()
    block = fetch_nse_block_deals()
    bse   = fetch_bse_bulk_deals()

    all_deals = bulk + block + bse

    # Filter to watchlist if provided
    if watchlist:
        wl_clean  = {
            s.replace(".NS", "").replace(".BO", "").upper()
            for s in watchlist
        }
        all_deals = [
            d for d in all_deals
            if d["symbol"].upper() in wl_clean
        ] or all_deals  # Fall back to all if no matches

    # Sort by deal value — biggest first
    all_deals.sort(
        key=lambda x: x.get("deal_value", 0),
        reverse=True,
    )

    result = {
        "bulk":  [d for d in all_deals if d["deal_type"] == "BULK"],
        "block": [d for d in all_deals if d["deal_type"] == "BLOCK"],
        "all":   all_deals,
        "total": len(all_deals),
        "date":  datetime.now().strftime("%d %b %Y"),
    }

    print(f"✅ Total deals: {len(all_deals)} "
          f"({len(result['block'])} block, {len(result['bulk'])} bulk)")
    return result


# ── TELEGRAM FORMATTER ────────────────────────────────────────────

def format_deals_message(deals_data: Dict) -> str:
    """Format deals into a clean Telegram message"""
    msg  = "📋 *BULK & BLOCK DEALS*\n"
    msg += f"_{deals_data.get('date', 'Today')}_\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    if not deals_data["all"]:
        msg += (
            "_No significant deals reported today_\n\n"
            "_Note: NSE publishes deals after 4:30 PM IST "
            "on trading days_"
        )
        return msg

    # Block deals first — bigger, more significant
    if deals_data["block"]:
        msg += "🔷 *BLOCK DEALS:*\n"
        for d in deals_data["block"][:5]:
            emoji = "🟢" if "BUY" in d["buy_sell"].upper() else "🔴"
            msg += (
                f"{emoji} *{d['symbol']}*\n"
                f"   _{d['client'][:30]}_\n"
                f"   {d['buy_sell']} | Qty: {d['quantity']:,} "
                f"@ ₹{d['price']} | 💰 ₹{d['deal_value']}Cr\n\n"
            )

    # Bulk deals
    if deals_data["bulk"]:
        msg += "📦 *BULK DEALS:*\n"
        for d in deals_data["bulk"][:5]:
            emoji = "🟢" if "BUY" in d["buy_sell"].upper() else "🔴"
            msg += (
                f"{emoji} *{d['symbol']}*\n"
                f"   _{d['client'][:30]}_\n"
                f"   {d['buy_sell']} "
                f"@ ₹{d['price']} | 💰 ₹{d['deal_value']}Cr\n\n"
            )

    msg += f"_Total: {deals_data['total']} deals today_"
    return msg


# ── HELPERS ───────────────────────────────────────────────────────

def _safe_int(value: str) -> int:
    """Safely parse integer from string with commas"""
    try:
        return int(str(value).replace(",", "").replace(" ", "").split(".")[0])
    except Exception:
        return 0

def _safe_float(value: str) -> float:
    """Safely parse float from string with commas"""
    try:
        return float(str(value).replace(",", "").replace(" ", ""))
    except Exception:
        return 0.0