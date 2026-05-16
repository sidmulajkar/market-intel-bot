"""
Insider Activity Tracker
Primary: NSE Bulk & Block Deals API (no auth required)
Secondary: NSE PIT (SAST) filings (requires session)
Data: market-wide, no watchlist dependency
"""
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional

NSE_HEADERS = {
    "User-Agent":  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer":      "https://www.nseindia.com/report-detail/display-bulk-and-block-deals",
    "Accept":       "application/json, text/plain, */*",
}


# ── Fetch Bulk Deals ─────────────────────────────────────────────
def fetch_bulk_deals(days: int = 10) -> List[Dict]:
    """
    Fetch NSE bulk deals — large client trades ≥ 0.5% equity.
    Public API, no session/cookie needed.
    Returns: [{date, symbol, company, client, side, qty, price, value_cr}, ...]
    """
    from_d = (datetime.now() - timedelta(days=days)).strftime("%d-%m-%Y")
    to_d   = datetime.now().strftime("%d-%m-%Y")
    url    = (
        f"https://www.nseindia.com/api/historicalOR/bulk-block-short-deals"
        f"?optionType=bulk_deals&segment=NSE&from={from_d}&to={to_d}"
    )
    try:
        resp = requests.get(url, headers=NSE_HEADERS, timeout=20)
        if resp.status_code != 200:
            return []
        data = resp.json()
        rows = data if isinstance(data, list) else data.get("data", [])
        if not rows:
            return []

        results = []
        for r in rows:
            qty   = int(r.get("BD_QTY_TRD", 0) or 0)
            price = float(r.get("BD_TP_WATP", 0) or 0)
            val_rs = qty * price
            results.append({
                "date":        r.get("BD_DT_DATE", ""),
                "symbol":      r.get("BD_SYMBOL", ""),
                "company":     r.get("BD_SCRIP_NAME", ""),
                "client":      r.get("BD_CLIENT_NAME", ""),
                "side":        r.get("BD_BUY_SELL", ""),
                "qty":         qty,
                "price":       price,
                "value_rs":    val_rs,
                "value_cr":    round(val_rs / 1e7, 2),
                "remarks":     r.get("BD_REMARKS", ""),
                "deal_type":   "bulk",
            })
        return results
    except Exception as e:
        print(f"⚠️  bulk_deals fetch: {e}")
        return []


# ── Fetch Block Deals ────────────────────────────────────────────
def fetch_block_deals(days: int = 10) -> List[Dict]:
    """
    Fetch NSE block deals — single price, single buyer/seller, higher value.
    Same endpoint as bulk deals, different optionType.
    """
    from_d = (datetime.now() - timedelta(days=days)).strftime("%d-%m-%Y")
    to_d   = datetime.now().strftime("%d-%m-%Y")
    url    = (
        f"https://www.nseindia.com/api/historicalOR/bulk-block-short-deals"
        f"?optionType=block_deals&segment=NSE&from={from_d}&to={to_d}"
    )
    try:
        resp = requests.get(url, headers=NSE_HEADERS, timeout=20)
        if resp.status_code != 200:
            return []
        data = resp.json()
        rows = data if isinstance(data, list) else data.get("data", [])
        if not rows:
            return []

        results = []
        for r in rows:
            qty   = int(r.get("BD_QTY_TRD", 0) or 0)
            price = float(r.get("BD_TP_WATP", 0) or 0)
            val_rs = qty * price
            results.append({
                "date":        r.get("BD_DT_DATE", ""),
                "symbol":      r.get("BD_SYMBOL", ""),
                "company":     r.get("BD_SCRIP_NAME", ""),
                "client":      r.get("BD_CLIENT_NAME", ""),
                "side":        r.get("BD_BUY_SELL", ""),
                "qty":         qty,
                "price":       price,
                "value_rs":    val_rs,
                "value_cr":    round(val_rs / 1e7, 2),
                "remarks":     r.get("BD_REMARKS", ""),
                "deal_type":   "block",
            })
        return results
    except Exception as e:
        print(f"⚠️  block_deals fetch: {e}")
        return []


# ── Fetch PIT (SAST Filings) for a symbol ───────────────────────
def fetch_pit_for_symbol(symbol: str, days: int = 14) -> List[Dict]:
    """
    Fetch PIT (SAST) insider filings for a specific symbol.
    Requires NSE session. Used for recent director/promoter activity.
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer":    "https://www.nseindia.com/",
    })
    try:
        session.get("https://www.nseindia.com", timeout=10)
    except Exception:
        pass

    from_d = (datetime.now() - timedelta(days=days)).strftime("%d-%m-%Y")
    to_d   = datetime.now().strftime("%d-%m-%Y")
    sym    = symbol.replace(".NS", "").replace(".BO", "").upper()
    url    = f"https://www.nseindia.com/api/corporates-pit?symbol={sym}&from={from_d}&to={to_d}"

    try:
        resp = session.get(url, timeout=15)
        if resp.status_code != 200:
            return []
        d = resp.json()
        rows = d.get("data", [])
        if not rows:
            return []

        results = []
        for r in rows:
            sec_val = float(r.get("secVal", 0) or 0)
            results.append({
                "date":     r.get("intimDt", ""),
                "symbol":   r.get("symbol", ""),
                "person":   r.get("acqName", ""),
                "category": r.get("personCategory", ""),
                "txn_type": r.get("tdpTransactionType", ""),
                "acq_mode": r.get("acqMode", ""),
                "qty":      int(r.get("secAcq", 0) or 0),
                "value_rs": sec_val,
                "value_cr": round(sec_val / 1e7, 2),
                "before_pct": float(r.get("befAcqSharesPer", 0) or 0),
                "after_pct":  float(r.get("afterAcqSharesPer", 0) or 0),
            })
        return results
    except Exception as e:
        print(f"⚠️  PIT fetch ({symbol}): {e}")
        return []


# ── Combine all sources ─────────────────────────────────────────
def get_market_insider_activity(days: int = 10) -> Dict:
    """
    Fetch all market-wide insider/bulk activity.
    Returns aggregated summary with bulk, block, and PIT signals.
    """
    print("🕵️  Fetching market insider activity...")

    # Fetch bulk + block deals (no session needed)
    bulk_deals = fetch_bulk_deals(days=days)
    block_deals = fetch_block_deals(days=days)

    all_deals = bulk_deals + block_deals
    if not all_deals:
        return {"ok": False, "message": "No bulk/block deals data available"}

    # Deduplicate: one entry per (symbol, client, side, date, deal_type)
    seen = set()
    unique = []
    for d in all_deals:
        key = (d["symbol"], d["client"], d["side"], d["date"], d["deal_type"])
        if key not in seen:
            seen.add(key)
            unique.append(d)

    # Sort by value descending
    unique.sort(key=lambda x: x["value_rs"], reverse=True)

    # Aggregate: group by symbol
    symbol_agg = {}
    for d in unique:
        sym = d["symbol"]
        if sym not in symbol_agg:
            symbol_agg[sym] = {"symbol": sym, "company": d["company"],
                                 "total_buy_val": 0, "total_sell_val": 0,
                                 "buy_count": 0, "sell_count": 0,
                                 "top_deal": None}
        agg = symbol_agg[sym]
        if d["side"] == "BUY":
            agg["total_buy_val"] += d["value_rs"]
            agg["buy_count"] += 1
        else:
            agg["total_sell_val"] += d["value_rs"]
            agg["sell_count"] += 1
        if agg["top_deal"] is None or d["value_rs"] > agg["top_deal"]["value_rs"]:
            agg["top_deal"] = d

    # Get date range
    dates = sorted(set(d["date"] for d in unique))
    date_range = f"{dates[0]} to {dates[-1]}" if dates else "unknown"

    # Top deals by value
    top_deals = unique[:20]

    # Top symbols by net flow
    symbol_flows = []
    for sym, agg in symbol_agg.items():
        net = agg["total_buy_val"] - agg["total_sell_val"]
        symbol_flows.append({
            "symbol":       sym,
            "company":      agg["company"],
            "net_val_rs":   net,
            "net_val_cr":   round(net / 1e7, 2),
            "buy_val_cr":   round(agg["total_buy_val"] / 1e7, 2),
            "sell_val_cr":  round(agg["total_sell_val"] / 1e7, 2),
            "buy_count":    agg["buy_count"],
            "sell_count":   agg["sell_count"],
        })
    symbol_flows.sort(key=lambda x: abs(x["net_val_rs"]), reverse=True)

    return {
        "ok":           True,
        "date_range":   date_range,
        "total_deals":  len(unique),
        "bulk_count":   len(bulk_deals),
        "block_count":  len(block_deals),
        "symbols":      list(symbol_agg.keys()),
        "top_deals":    top_deals,
        "symbol_flows": symbol_flows[:15],
    }


# ── Format for Telegram ─────────────────────────────────────────
def format_insider_summary(data: Dict) -> str:
    """Format market insider activity for Telegram."""
    if not data.get("ok"):
        return ""

    lines = []
    lines.append(f"📊 *BULK & BLOCK DEAL ACTIVITY*\n_{data['date_range']}_")
    lines.append(f"Bulk: {data['bulk_count']} | Block: {data['block_count']} | Symbols: {len(data['symbols'])}\n")

    # Top net flows
    if data.get("symbol_flows"):
        lines.append("🔄 *Top Flows by Symbol:*")
        for sf in data["symbol_flows"][:8]:
            net = sf["net_val_cr"]
            sign = "+" if net >= 0 else ""
            emoji = "🟢" if net > 0 else ("🔴" if net < 0 else "⚪")
            lines.append(
                f"{emoji} {sf['symbol']}: {sf['buy_val_cr']:.0f} Cr in | "
                f"{sf['sell_val_cr']:.0f} Cr out | Net: {sign}{net:.0f} Cr"
            )

    # Top deals by value
    if data.get("top_deals"):
        lines.append("\n💰 *Top Deals by Value:*")
        buys  = [d for d in data["top_deals"] if d["side"] == "BUY"][:5]
        sells = [d for d in data["top_deals"] if d["side"] == "SELL"][:5]

        if buys:
            lines.append("🟢 *Top Buys:*")
            for d in buys:
                client_short = d["client"][:30] if len(d["client"]) > 30 else d["client"]
                lines.append(
                    f"  • {d['symbol']}: {d['qty']:,} shares @ ₹{d['price']:,.2f}"
                    f" | ₹{d['value_cr']} Cr | {client_short}"
                )

        if sells:
            lines.append("🔴 *Top Sells:*")
            for d in sells:
                client_short = d["client"][:30] if len(d["client"]) > 30 else d["client"]
                lines.append(
                    f"  • {d['symbol']}: {d['qty']:,} shares @ ₹{d['price']:,.2f}"
                    f" | ₹{d['value_cr']} Cr | {client_short}"
                )

    lines.append(f"\n_Source: NSE Bulk/Block Deals (SEBI data)_")
    return "\n".join(lines)