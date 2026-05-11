"""
Insider Trading Tracker
Sources:
  1. NSE insider trading filings API (free public data)
  2. yfinance insider_transactions (for US/global stocks)
  3. NSE corporate action announcements filtered for SAST/SEBI filings

Tracks: Director/Promoter buy & sell transactions
"""
import time
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict

NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.nseindia.com/",
    "Accept": "*/*",
}

def _nse_session() -> requests.Session:
    """Create NSE session with cookie"""
    s = requests.Session()
    s.headers.update(NSE_HEADERS)
    try:
        s.get("https://www.nseindia.com", timeout=15)
        time.sleep(1)
    except Exception:
        pass
    return s

def fetch_nse_insider_trades(
    symbol: str = None,
    days_back: int = 30,
) -> List[Dict]:
    """
    Fetch insider trades from NSE.
    If symbol is None, fetches all recent insider trades (market-wide).
    NSE endpoint: /api/corporates-pit
    """
    s     = _nse_session()
    to_d  = datetime.now().strftime("%d-%m-%Y")
    from_d = (datetime.now() - timedelta(days=days_back)).strftime("%d-%m-%Y")

    if symbol:
        sym_clean = symbol.replace(".NS", "").replace(".BO", "").upper()
        url = (
            f"https://www.nseindia.com/api/corporates-pit"
            f"?symbol={sym_clean}&from={from_d}&to={to_d}"
        )
    else:
        url = (
            f"https://www.nseindia.com/api/corporates-pit"
            f"?from={from_d}&to={to_d}"
        )

    results = []
    try:
        resp = s.get(url, timeout=15)
        if resp.status_code != 200:
            print(f"⚠️  NSE insider API returned {resp.status_code}")
            return []

        data  = resp.json()
        items = data if isinstance(data, list) else data.get("data", [])

        for item in items:
            try:
                txn_type = str(item.get("acqMode", "")).upper()
                qty      = int(str(item.get("secAcq",  "0")).replace(",", ""))
                val      = float(str(item.get("val", "0")).replace(",", ""))
                after_pct = float(str(item.get("afterAcqSharesPerc", "0")))
                before_pct = float(str(item.get("beforeAcqSharesPerc", "0")))
                delta_pct  = round(after_pct - before_pct, 4)

                results.append({
                    "symbol":       item.get("symbol", ""),
                    "company":      item.get("company", ""),
                    "insider":      item.get("acqName", ""),
                    "designation":  item.get("personCategory", ""),
                    "transaction":  txn_type,
                    "quantity":     qty,
                    "value_cr":     round(val / 1e7, 2),
                    "before_pct":   before_pct,
                    "after_pct":    after_pct,
                    "delta_pct":    delta_pct,
                    "date":         item.get("intimDt", ""),
                    "is_buy":       "BUY" in txn_type or delta_pct > 0,
                })
            except Exception:
                continue

    except Exception as e:
        print(f"⚠️  NSE insider fetch error: {e}")

    return results

def fetch_yfinance_insider(symbol: str) -> List[Dict]:
    """
    Fetch insider transactions from yfinance (works for US stocks,
    and some NSE stocks with good coverage).
    """
    results = []
    try:
        t     = yf.Ticker(symbol)
        txns  = t.insider_transactions

        if txns is None or txns.empty:
            return []

        for _, row in txns.iterrows():
            try:
                results.append({
                    "symbol":      symbol,
                    "company":     "",
                    "insider":     str(row.get("Insider", "")),
                    "designation": str(row.get("Relationship", "")),
                    "transaction": str(row.get("Transaction", "")),
                    "quantity":    int(row.get("#Shares", 0)),
                    "value_cr":    round(float(row.get("Value", 0)) / 1e7, 4),
                    "before_pct":  0.0,
                    "after_pct":   0.0,
                    "delta_pct":   0.0,
                    "date":        str(row.get("Date", "")),
                    "is_buy":      "Purchase" in str(row.get("Transaction", "")),
                })
            except Exception:
                continue

    except Exception as e:
        print(f"⚠️  yfinance insider error ({symbol}): {e}")

    return results

def get_insider_summary(
    symbols: List[str],
    top_n: int = 20,
) -> Dict:
    """
    Get insider activity for watchlist + market-wide top movers.
    Returns sorted by value — biggest transactions first.
    """
    print("🕵️  Fetching insider trades (NSE market-wide)...")
    market_wide = fetch_nse_insider_trades(symbol=None, days_back=14)

    # Filter to watchlist symbols if they appear
    wl_clean = {s.replace(".NS", "").replace(".BO", "").upper()
                for s in symbols}
    watchlist_trades = [t for t in market_wide
                        if t["symbol"].upper() in wl_clean]

    # Also fetch yfinance for US stocks in watchlist
    us_stocks = [s for s in symbols
                 if not s.endswith(".NS") and not s.endswith(".BO")]
    yf_trades = []
    for sym in us_stocks[:3]:  # Max 3 US stocks
        yf_trades.extend(fetch_yfinance_insider(sym))
        time.sleep(1)

    all_trades = market_wide + yf_trades
    all_trades.sort(
        key=lambda x: x.get("value_cr", 0),
        reverse=True
    )

    buys  = [t for t in all_trades if t["is_buy"]][:top_n]
    sells = [t for t in all_trades if not t["is_buy"]][:top_n]

    return {
        "all":             all_trades[:top_n],
        "top_buys":        buys[:10],
        "top_sells":       sells[:10],
        "watchlist_trades": watchlist_trades,
        "total_count":     len(all_trades),
        "buy_count":       len(buys),
        "sell_count":      len(sells),
        "date_range":      "Last 14 days",
    }

def format_insider_message(summary: Dict) -> str:
    """Format insider trading summary for Telegram"""
    msg = "🕵️ *INSIDER TRADING TRACKER*\n"
    msg += f"_{summary.get('date_range', 'Recent')}_\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    # Watchlist alerts first
    wl = summary.get("watchlist_trades", [])
    if wl:
        msg += "⚡ *YOUR WATCHLIST ACTIVITY:*\n"
        for t in wl[:5]:
            emoji = "🟢" if t["is_buy"] else "🔴"
            msg += (
                f"{emoji} *{t['symbol']}* — {t['insider'][:25]}\n"
                f"   {t['transaction']} | {t['quantity']:,} shares"
                f" | ₹{t['value_cr']}Cr\n"
                f"   Before: {t['before_pct']}% → After: {t['after_pct']}%\n\n"
            )

    # Top buys
    if summary["top_buys"]:
        msg += "🟢 *TOP INSIDER BUYS (by value):*\n"
        for t in summary["top_buys"][:5]:
            msg += (
                f"  • *{t['symbol']}* — {t['insider'][:20]}\n"
                f"    {t['quantity']:,} shares | ₹{t['value_cr']}Cr | "
                f"{t['delta_pct']:+.3f}%\n"
            )

    msg += "\n"

    # Top sells
    if summary["top_sells"]:
        msg += "🔴 *TOP INSIDER SELLS (by value):*\n"
        for t in summary["top_sells"][:5]:
            msg += (
                f"  • *{t['symbol']}* — {t['insider'][:20]}\n"
                f"    {t['quantity']:,} shares | ₹{t['value_cr']}Cr | "
                f"{t['delta_pct']:+.3f}%\n"
            )

    msg += (
        f"\n📊 Total: {summary['buy_count']} buys | "
        f"{summary['sell_count']} sells in last 14 days"
    )

    return msg