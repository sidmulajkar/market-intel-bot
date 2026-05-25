"""
Insider Activity Tracker
Primary: NSE Bulk & Block Deals API (no auth required)
Secondary: NSE PIT (SAST) filings (requires session)
Data: market-wide, no watchlist dependency
"""
import math
import re
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional


# ── Symbol validation ─────────────────────────────────────────────
def _is_valid_indian_symbol(symbol: str) -> bool:
    """
    Filter out non-Indian instruments from NSE data.
    Valid Indian equity symbols: 1-20 chars, alphanumeric, may contain & - .
    Rejects: ETFs, indices, commodity tickers, short US-style tickers.
    """
    if not symbol or len(symbol) > 20:
        return False
    # Must be alphanumeric (allow &, -, ., space)
    if not re.match(r'^[A-Z0-9&\-\. ]+$', symbol):
        return False

    symbol_upper = symbol.upper().strip()

    # Reject very short all-alpha symbols (likely US tickers: AAPL, MSFT, TSLA, NVDA)
    # Indian symbols like TCS, WIPRO, INFY are valid — but single-word US tickers
    # are typically 4 chars. Reject 4-char all-alpha that don't look Indian.
    # Allow 3-char (TCS, INFY) and 5+ char (WIPRO, RELIANCE) symbols.
    if len(symbol_upper) == 4 and symbol_upper.isalpha():
        # 4-char all-alpha: could be AAPL, MSFT, TSLA, NVDA (US) or INFY, SBIN (Indian)
        # Check against known Indian 4-char symbols
        known_indian_4char = {'INFY', 'SBIN', 'HCLT', 'LTIM', 'CIPL', 'DRRE', 'SUNP',
                              'BAJA', 'MARU', 'TITN', 'ASPN', 'BHRI', 'COAL', 'NMDC',
                              'NHPC', 'SJVN', 'IRFC', 'IREDA', 'HAL', 'BEL', 'BDL'}
        if symbol_upper not in known_indian_4char:
            return False

    # Reject known non-equity patterns (exact match or prefix with -)
    skip_exact = {'ETF', 'BEES', 'NIFTY', 'SENSEX', 'BANKNIFTY',
                  'GOLD', 'SILVER', 'CRUDE', 'NIFTYBEES', 'JUNIORBEES'}
    if symbol_upper in skip_exact:
        return False

    skip_prefixes = ['ETF-', 'BEES-', 'NIFTY-', 'GOLD-', 'SILVER-']
    for prefix in skip_prefixes:
        if symbol_upper.startswith(prefix):
            return False

    return True


def _safe_float(val, default=0.0) -> float:
    """Convert to float, return default on NaN or error."""
    try:
        f = float(val or 0)
        return default if math.isnan(f) or math.isinf(f) else f
    except (ValueError, TypeError):
        return default

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
            symbol = r.get("BD_SYMBOL", "")
            if not _is_valid_indian_symbol(symbol):
                continue
            qty   = int(r.get("BD_QTY_TRD", 0) or 0)
            price = _safe_float(r.get("BD_TP_WATP", 0))
            val_rs = qty * price
            if val_rs <= 0:
                continue
            results.append({
                "date":        r.get("BD_DT_DATE", ""),
                "symbol":      symbol,
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
            symbol = r.get("BD_SYMBOL", "")
            if not _is_valid_indian_symbol(symbol):
                continue
            qty   = int(r.get("BD_QTY_TRD", 0) or 0)
            price = _safe_float(r.get("BD_TP_WATP", 0))
            val_rs = qty * price
            if val_rs <= 0:
                continue
            results.append({
                "date":        r.get("BD_DT_DATE", ""),
                "symbol":      symbol,
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
        "patterns":     _detect_deal_patterns(unique),
    }


# ── Deal Pattern Detection ──────────────────────────────────────
def _detect_deal_patterns(deals: List[Dict]) -> List[Dict]:
    """
    Detect intelligent patterns in bulk/block deals:
    - Related-party transfer: same symbol, same price (±1%), same day, buy ≈ sell
    - Institutional redistribution: multiple MFs buying what a single entity sold
    - Accumulation: same entity buying same stock across multiple days
    """
    if not deals:
        return []

    patterns = []

    # Group by symbol + date
    from collections import defaultdict
    by_symbol_date = defaultdict(list)
    for d in deals:
        key = (d["symbol"], d["date"])
        by_symbol_date[key].append(d)

    # Pattern 1: Related-party transfer / cross-trade
    # Same symbol, same day, same price (±1%), both buy and sell sides present
    for (symbol, date), day_deals in by_symbol_date.items():
        buys = [d for d in day_deals if d["side"] == "BUY"]
        sells = [d for d in day_deals if d["side"] == "SELL"]
        if not buys or not sells:
            continue

        # Check if buy and sell prices match (±1%)
        buy_prices = set(round(d["price"], 2) for d in buys)
        sell_prices = set(round(d["price"], 2) for d in sells)

        matched_price = None
        for bp in buy_prices:
            for sp in sell_prices:
                if sp > 0 and abs(bp - sp) / sp <= 0.01:
                    matched_price = bp
                    break
            if matched_price:
                break

        if not matched_price:
            continue

        total_buy_qty = sum(d["qty"] for d in buys)
        total_sell_qty = sum(d["qty"] for d in sells)
        total_value = sum(d["value_cr"] for d in buys + sells)

        # Determine if quantities are roughly equal (±25%)
        qty_ratio = total_buy_qty / total_sell_qty if total_sell_qty > 0 else 999
        if 0.75 <= qty_ratio <= 1.25:
            buy_entities = [d["client"] for d in buys]
            sell_entities = [d["client"] for d in sells]

            # Check if any seller is a promoter/promoter group entity
            promoter_keywords = ["promoter", "js w", "family", "trust", "holding", "ventures"]
            is_promoter_selling = any(
                any(kw in s.lower() for kw in promoter_keywords)
                for s in sell_entities
            )

            # Check if buyers are institutional
            inst_keywords = ["gqg", "sbi", "mf", "mutual fund", "hdfc mf", "icici prudential",
                           "axis mf", "nippon", "dsp", "kotak mf", "mirae", "parag parikh",
                           "foreign", "fii", "government"]
            is_inst_buying = any(
                any(kw in b.lower() for kw in inst_keywords)
                for b in buy_entities
            )

            if is_promoter_selling and is_inst_buying:
                pattern_type = "PROMOTER → INSTITUTION TRANSFER"
                insight = (
                    f"Promoter group sold ₹{total_value:.0f}Cr at ₹{matched_price:,.2f} to "
                    f"institutional investors ({', '.join(buy_entities[:3])}) — "
                    f"stake redistribution, not market selling. "
                    f"Watch for further promoter dilution."
                )
            else:
                pattern_type = "CROSS-TRADE (matched price)"
                insight = (
                    f"₹{total_value:.0f}Cr changed hands at ₹{matched_price:,.2f} "
                    f"between {', '.join(sell_entities[:2])} and {', '.join(buy_entities[:2])} — "
                    f"negotiated block deal, not market activity."
                )

            patterns.append({
                "symbol": symbol,
                "company": buys[0].get("company", ""),
                "date": date,
                "type": pattern_type,
                "price": matched_price,
                "total_value_cr": total_value,
                "insight": insight,
            })

    # Pattern 2: Accumulation — same entity buying same stock across 3+ days
    entity_symbol_days = defaultdict(list)
    for d in deals:
        if d["side"] == "BUY":
            key = (d["client"], d["symbol"])
            entity_symbol_days[key].append(d)

    for (entity, symbol), entity_deals in entity_symbol_days.items():
        unique_dates = set(d["date"] for d in entity_deals)
        if len(unique_dates) >= 3:
            total_value = sum(d["value_cr"] for d in entity_deals)
            total_qty = sum(d["qty"] for d in entity_deals)
            avg_price = sum(d["price"] * d["qty"] for d in entity_deals) / total_qty if total_qty > 0 else 0

            patterns.append({
                "symbol": symbol,
                "company": entity_deals[0].get("company", ""),
                "date": f"{min(unique_dates)} to {max(unique_dates)}",
                "type": "ACCUMULATION",
                "price": round(avg_price, 2),
                "total_value_cr": total_value,
                "insight": (
                    f"{entity} accumulated {total_qty:,} shares (₹{total_value:.0f}Cr) "
                    f"across {len(unique_dates)} sessions at avg ₹{avg_price:,.2f} — "
                    f"building position."
                ),
            })

    return patterns


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

    # Detected patterns
    if data.get("patterns"):
        lines.append("\n🔍 *Pattern Analysis:*")
        for p in data["patterns"]:
            lines.append(f"  • {p['symbol']} ({p['type']}): {p['insight']}")

    lines.append(f"\n_Source: NSE Bulk/Block Deals (SEBI data)_")
    return "\n".join(lines)