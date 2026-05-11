"""
Bulk & Block Deals Tracker
Sources: NSE API (primary) + BSE CSV (secondary)
NSE requires specific session headers — implemented below.
Rate limit: 3 requests per second — respected with delays.
"""
import os
import time
import random
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# ── NSE SESSION HEADERS (Required — NSE blocks plain requests) ────
NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/",
    "Connection": "keep-alive",
}

class NSESession:
    """
    NSE requires a valid session cookie obtained by visiting
    the main page first. This class handles that handshake.
    All requests through NSE are rate limited to 3 requests per second.
    """
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(NSE_HEADERS)
        self._init_session()

    def _init_session(self):
        """Visit NSE homepage to get cookies"""
        try:
            self.session.get(
                "https://www.nseindia.com",
                timeout=15
            )
            time.sleep(1)  # Polite delay after handshake
        except Exception as e:
            print(f"⚠️  NSE session init failed: {e}")

    def get(self, url: str, params: dict = None) -> Optional[dict]:
        """Make GET request to NSE API with rate limit respect"""
        time.sleep(random.uniform(0.4, 0.8))  # Stay under 3 req/s
        try:
            resp = self.session.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                print("⏳ NSE rate limited — waiting 60s...")
                time.sleep(60)
                return self.get(url, params)
            else:
                print(f"⚠️  NSE HTTP {resp.status_code}: {url}")
                return None
        except Exception as e:
            print(f"⚠️  NSE request failed: {e}")
            return None

def fetch_nse_bulk_deals(date_str: str = None) -> List[Dict]:
    """
    Fetch bulk deals from NSE.
    date_str format: "15-08-2023"
    If None, fetches today's data.
    """
    nse = NSESession()
    today = date_str or datetime.now().strftime("%d-%m-%Y")

    # Real-time endpoint (today)
    url = "https://www.nseindia.com/api/snapshot-capital-market-largedeal"
    params = {"bandtype": "bulk_deals", "view": "mode"}

    data = nse.get(url, params)
    if not data:
        return []

    deals = []
    raw_list = data if isinstance(data, list) else data.get("data", [])
    for item in raw_list:
        try:
            qty   = int(str(item.get("tdQty", "0")).replace(",", ""))
            price = float(str(item.get("tdVal", "0")).replace(",", ""))
            deals.append({
                "symbol":       item.get("symbol", ""),
                "company":      item.get("companyName", ""),
                "client":       item.get("clientName", ""),
                "buy_sell":     item.get("buySell", ""),
                "quantity":     qty,
                "price":        price,
                "deal_value":   round((qty * price) / 1e7, 2),  # In Crores
                "deal_type":    "BULK",
                "exchange":     "NSE",
                "date":         today,
            })
        except Exception:
            continue

    return deals

def fetch_nse_block_deals(date_str: str = None) -> List[Dict]:
    """Fetch block deals from NSE"""
    nse  = NSESession()
    today = date_str or datetime.now().strftime("%d-%m-%Y")
    url   = "https://www.nseindia.com/api/snapshot-capital-market-largedeal"
    params = {"bandtype": "block_deals", "view": "mode"}

    data = nse.get(url, params)
    if not data:
        return []

    deals = []
    raw_list = data if isinstance(data, list) else data.get("data", [])
    for item in raw_list:
        try:
            qty   = int(str(item.get("tdQty", "0")).replace(",", ""))
            price = float(str(item.get("tdVal", "0")).replace(",", ""))
            deals.append({
                "symbol":    item.get("symbol", ""),
                "company":   item.get("companyName", ""),
                "client":    item.get("clientName", ""),
                "buy_sell":  item.get("buySell", ""),
                "quantity":  qty,
                "price":     price,
                "deal_value": round((qty * price) / 1e7, 2),
                "deal_type": "BLOCK",
                "exchange":  "NSE",
                "date":      today,
            })
        except Exception:
            continue

    return deals

def fetch_bse_bulk_deals() -> List[Dict]:
    """
    Fetch bulk deals from BSE CSV endpoint.
    BSE publishes this daily — no session cookie required.
    """
    today    = datetime.now().strftime("%Y%m%d")
    url      = (
        f"https://www.bseindia.com/markets/equity/"
        f"EQReports/BulkDealDetails.aspx?"
        f"expandable=0&strDate={today}"
    )
    headers = {
        "User-Agent": NSE_HEADERS["User-Agent"],
        "Referer": "https://www.bseindia.com/",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return []
        # BSE returns HTML table — parse with pandas
        tables = pd.read_html(resp.text)
        if not tables:
            return []
        df = tables[0]
        df.columns = [str(c).strip() for c in df.columns]
        deals = []
        for _, row in df.iterrows():
            try:
                deals.append({
                    "symbol":    str(row.get("Scrip Code", "")),
                    "company":   str(row.get("Scrip Name", row.get("Company", ""))),
                    "client":    str(row.get("Client Name", "")),
                    "buy_sell":  str(row.get("Buy/Sell", "")),
                    "quantity":  int(str(row.get("Quantity", "0")).replace(",", "")),
                    "price":     float(str(row.get("Price", "0")).replace(",", "")),
                    "deal_type": "BULK",
                    "exchange":  "BSE",
                    "date":      datetime.now().strftime("%d-%m-%Y"),
                })
            except Exception:
                continue
        return deals
    except Exception as e:
        print(f"⚠️  BSE bulk deals error: {e}")
        return []

def get_all_deals(watchlist: List[str] = None) -> Dict:
    """
    Fetch and combine NSE bulk + block deals.
    Optionally filter by watchlist symbols.
    Returns categorised dict for easy display.
    """
    print("📋 Fetching bulk deals from NSE...")
    bulk  = fetch_nse_bulk_deals()
    print("📋 Fetching block deals from NSE...")
    block = fetch_nse_block_deals()
    print("📋 Fetching bulk deals from BSE...")
    bse   = fetch_bse_bulk_deals()

    all_deals = bulk + block + bse

    # Filter to watchlist if provided
    if watchlist:
        wl_clean = [s.replace(".NS", "").replace(".BO", "").upper()
                    for s in watchlist]
        all_deals = [d for d in all_deals
                     if d["symbol"].upper() in wl_clean or not watchlist]

    # Sort by deal value descending
    all_deals.sort(key=lambda x: x.get("deal_value", 0), reverse=True)

    return {
        "bulk":  [d for d in all_deals if d["deal_type"] == "BULK"],
        "block": [d for d in all_deals if d["deal_type"] == "BLOCK"],
        "all":   all_deals,
        "total": len(all_deals),
        "date":  datetime.now().strftime("%d %b %Y"),
    }

def format_deals_message(deals_data: Dict) -> str:
    """Format deals into Telegram-ready message"""
    msg = "📋 *BULK & BLOCK DEALS*\n"
    msg += f"_{deals_data.get('date', 'Today')}_\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    if not deals_data["all"]:
        msg += "_No significant deals reported today_"
        return msg

    # Block deals first (bigger / more significant)
    if deals_data["block"]:
        msg += "🔷 *BLOCK DEALS*\n"
        for d in deals_data["block"][:5]:
            emoji = "🟢" if "BUY" in d["buy_sell"].upper() else "🔴"
            msg += (
                f"{emoji} *{d['symbol']}*\n"
                f"   {d['client'][:30]}\n"
                f"   {d['buy_sell']} | Qty: {d['quantity']:,} "
                f"| ₹{d['price']} | 💰₹{d['deal_value']}Cr\n\n"
            )

    if deals_data["bulk"]:
        msg += "📦 *BULK DEALS*\n"
        for d in deals_data["bulk"][:5]:
            emoji = "🟢" if "BUY" in d["buy_sell"].upper() else "🔴"
            msg += (
                f"{emoji} *{d['symbol']}*\n"
                f"   {d['client'][:30]}\n"
                f"   {d['buy_sell']} | ₹{d['price']} "
                f"| 💰₹{d['deal_value']}Cr\n\n"
            )

    return msg