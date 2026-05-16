"""
Market Data Fetcher — Fixed yfinance batch column handling
BUG FIX: Single-ticker batch download has different column structure
"""
import os
import time
import random
import pytz
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional

FINNHUB_KEY = os.environ.get('FINNHUB_KEY', '')

GLOBAL_INDICES = {
    "US":          {"symbol": "^GSPC",      "region": "Americas", "flag": "🇺🇸", "iso": "US",  "index_name": "S&P 500"},
    "Brazil":      {"symbol": "^BVSP",      "region": "Americas", "flag": "🇧🇷", "iso": "BR",  "index_name": "Bovespa"},
    "Canada":      {"symbol": "^GSPTSE",    "region": "Americas", "flag": "🇨🇦", "iso": "CA",  "index_name": "S&P/TSX"},
    "Mexico":      {"symbol": "^MXX",       "region": "Americas", "flag": "🇲🇽", "iso": "MX",  "index_name": "IPC"},
    "Chile":       {"symbol": "^IPSA",      "region": "Americas", "flag": "🇨🇱", "iso": "CL",  "index_name": "IPSA"},
    "South Korea": {"symbol": "^KS11",      "region": "Asia",     "flag": "🇰🇷", "iso": "KR",  "index_name": "KOSPI"},
    "Singapore":   {"symbol": "^STI",       "region": "Asia",     "flag": "🇸🇬", "iso": "SG",  "index_name": "STI"},
    "Taiwan":      {"symbol": "^TWII",      "region": "Asia",     "flag": "🇹🇼", "iso": "TW",  "index_name": "TWII"},
    "Hong Kong":   {"symbol": "^HSI",       "region": "Asia",     "flag": "🇭🇰", "iso": "HK",  "index_name": "HSI"},
    "Japan":       {"symbol": "^N225",      "region": "Asia",     "flag": "🇯🇵", "iso": "JP",  "index_name": "Nikkei 225"},
    "China":       {"symbol": "000001.SS",  "region": "Asia",     "flag": "🇨🇳", "iso": "CN",  "index_name": "SSE Composite"},
    "Australia":   {"symbol": "^AXJO",      "region": "Asia",     "flag": "🇦🇺", "iso": "AU",  "index_name": "ASX 200"},
    "India":       {"symbol": "^NSEI",      "region": "Asia",     "flag": "🇮🇳", "iso": "IN",  "index_name": "Nifty 50"},
    "Italy":       {"symbol": "FTSEMIB.MI", "region": "Europe",   "flag": "🇮🇹", "iso": "IT",  "index_name": "FTSE MIB"},
    "UK":          {"symbol": "^FTSE",      "region": "Europe",   "flag": "🇬🇧", "iso": "GB",  "index_name": "FTSE 100"},
    "Germany":     {"symbol": "^GDAXI",     "region": "Europe",   "flag": "🇩🇪", "iso": "DE",  "index_name": "DAX"},
    "Switzerland": {"symbol": "^SSMI",      "region": "Europe",   "flag": "🇨🇭", "iso": "CH",  "index_name": "SMI"},
    "France":      {"symbol": "^FCHI",      "region": "Europe",   "flag": "🇫🇷", "iso": "FR",  "index_name": "CAC 40"},
}

MARKET_HOURS = {
    "India":       ("Asia/Kolkata",          9, 15, 15, 30),
    "Japan":       ("Asia/Tokyo",            9,  0, 15,  0),
    "Hong Kong":   ("Asia/Hong_Kong",        9, 30, 16,  0),
    "China":       ("Asia/Shanghai",         9, 30, 15,  0),
    "Singapore":   ("Asia/Singapore",        9,  0, 17,  0),
    "South Korea": ("Asia/Seoul",            9,  0, 15, 30),
    "Taiwan":      ("Asia/Taipei",           9,  0, 13, 30),
    "Australia":   ("Australia/Sydney",     10,  0, 16,  0),
    "UK":          ("Europe/London",         8,  0, 16, 30),
    "Germany":     ("Europe/Berlin",         9,  0, 17, 30),
    "France":      ("Europe/Paris",          9,  0, 17, 30),
    "Italy":       ("Europe/Rome",           9,  0, 17, 30),
    "Switzerland": ("Europe/Zurich",         9,  0, 17, 30),
    "US":          ("America/New_York",      9, 30, 16,  0),
    "Brazil":      ("America/Sao_Paulo",    10,  0, 17,  0),
    "Canada":      ("America/Toronto",       9, 30, 16,  0),
    "Mexico":      ("America/Mexico_City",   8, 30, 15,  0),
    "Chile":       ("America/Santiago",      9, 30, 16,  0),
}

def get_market_status(country: str) -> str:
    if country not in MARKET_HOURS:
        return "CLOSED"
    tz_name, oh, om, ch, cm = MARKET_HOURS[country]
    try:
        local_now = datetime.now(pytz.timezone(tz_name))
    except Exception:
        return "CLOSED"
    if local_now.weekday() >= 5:
        return "CLOSED"
    open_t  = local_now.replace(hour=oh, minute=om, second=0, microsecond=0)
    close_t = local_now.replace(hour=ch, minute=cm, second=0, microsecond=0)
    return "OPEN" if open_t <= local_now <= close_t else "CLOSED"

def _safe_series(raw: pd.DataFrame, symbol: str,
                 symbols_list: list, col: str = "Close") -> pd.Series:
    """
    BUG FIX: yfinance batch download returns different structures
    depending on number of tickers:
      - Multiple tickers: MultiIndex columns (symbol, field)
      - Single ticker:    Simple columns (field only)
    This function handles both cases safely.
    """
    try:
        if isinstance(raw.columns, pd.MultiIndex):
            # Multiple tickers — access as raw[symbol][col]
            if symbol in raw.columns.get_level_values(0):
                series = raw[symbol][col].dropna()
                return series
            else:
                return pd.Series(dtype=float)
        else:
            # Single ticker — access as raw[col]
            if col in raw.columns:
                return raw[col].dropna()
            else:
                return pd.Series(dtype=float)
    except Exception as e:
        print(f"  ⚠️  Column access error ({symbol}): {e}")
        return pd.Series(dtype=float)

def _fallback_entry(country: str, info: dict, error: str) -> dict:
    return {
        "symbol":     info["symbol"],
        "region":     info["region"],
        "flag":       info["flag"],
        "iso":        info.get("iso", ""),
        "index_name": info.get("index_name", country),
        "price":      0.0,
        "change_pct": 0.0,
        "status":     get_market_status(country),
        "ok":         False,
        "error":      error,
    }

def fetch_global_indices() -> Dict:
    """Fetch all 18 global indices — batch with individual fallback"""
    print("📡 Fetching all 18 global indices (batch mode)...")
    symbols_list = [info["symbol"] for info in GLOBAL_INDICES.values()]
    results      = {}

    try:
        raw = yf.download(
            tickers=symbols_list,
            period="5d",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True,
        )

        for country, info in GLOBAL_INDICES.items():
            sym = info["symbol"]
            try:
                # BUG FIX: Use _safe_series helper
                sym_data = _safe_series(raw, sym, symbols_list, "Close")

                if len(sym_data) >= 2:
                    prev    = float(sym_data.iloc[-2])
                    current = float(sym_data.iloc[-1])
                    change  = ((current - prev) / prev) * 100
                elif len(sym_data) == 1:
                    current = float(sym_data.iloc[-1])
                    change  = 0.0
                else:
                    raise ValueError("No data")

                results[country] = {
                    "symbol":     sym,
                    "region":     info["region"],
                    "flag":       info["flag"],
                    "iso":        info.get("iso", ""),
                    "index_name": info.get("index_name", country),
                    "price":      round(current, 2),
                    "change_pct": round(change,  2),
                    "status":     get_market_status(country),
                    "ok":         True,
                }
            except Exception as e:
                print(f"  ⚠️  {country}: {e}")
                results[country] = _fallback_entry(country, info, str(e))

    except Exception as e:
        print(f"⚠️  Batch failed: {e} — using individual fallback")
        results = _fetch_individual_fallback()

    ok_count = sum(1 for v in results.values() if v.get("ok"))
    print(f"✅ Global indices: {ok_count}/18 fetched")
    return results

def _fetch_individual_fallback() -> Dict:
    results = {}
    for country, info in GLOBAL_INDICES.items():
        time.sleep(random.uniform(1.5, 3.0))
        try:
            t    = yf.Ticker(info["symbol"])
            hist = t.history(period="5d").dropna(subset=["Close"])
            if len(hist) >= 2:
                prev    = float(hist["Close"].iloc[-2])
                current = float(hist["Close"].iloc[-1])
                change  = ((current - prev) / prev) * 100
            elif len(hist) == 1:
                current = float(hist["Close"].iloc[-1])
                change  = 0.0
            else:
                raise ValueError("No data")

            results[country] = {
                "symbol":     info["symbol"],
                "region":     info["region"],
                "flag":       info["flag"],
                "iso":        info.get("iso", ""),
                "index_name": info.get("index_name", country),
                "price":      round(current, 2),
                "change_pct": round(change,  2),
                "status":     get_market_status(country),
                "ok":         True,
            }
        except Exception as e:
            results[country] = _fallback_entry(country, info, str(e))
    return results

def fetch_watchlist_data(symbols: List[str]) -> Dict:
    if not symbols:
        return {}

    print(f"📈 Fetching watchlist: {symbols}")
    results = {}

    try:
        raw = yf.download(
            tickers=symbols,
            period="1mo",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True,
        )

        for symbol in symbols:
            try:
                # BUG FIX: Use _safe_series for each column
                close_s  = _safe_series(raw, symbol, symbols, "Close")
                high_s   = _safe_series(raw, symbol, symbols, "High")
                low_s    = _safe_series(raw, symbol, symbols, "Low")
                vol_s    = _safe_series(raw, symbol, symbols, "Volume")

                if len(close_s) < 1:
                    raise ValueError("Empty close series")

                h7       = close_s.tail(7)
                last_cls = float(close_s.iloc[-1])
                prev_cls = float(close_s.iloc[-2]) if len(close_s) >= 2 else last_cls
                day_chg  = ((last_cls - prev_cls) / prev_cls) * 100 if prev_cls else 0
                last_vol = int(vol_s.iloc[-1])   if len(vol_s)   > 0 else 0
                avg_vol  = int(vol_s.mean())      if len(vol_s)   > 0 else 1
                avg_vol  = max(avg_vol, 1)

                results[symbol] = {
                    "price":        round(last_cls, 2),
                    "day_change":   round(day_chg, 2),
                    "volume":       last_vol,
                    "avg_volume":   avg_vol,
                    "volume_spike": (last_vol / avg_vol) > 2.0,
                    "week_high":    round(float(high_s.tail(7).max()), 2) if len(high_s) >= 7 else 0,
                    "week_low":     round(float(low_s.tail(7).min()),  2) if len(low_s)  >= 7 else 0,
                    "month_high":   round(float(high_s.max()), 2) if len(high_s) > 0 else 0,
                    "month_low":    round(float(low_s.min()),  2) if len(low_s)  > 0 else 0,
                    "close_series": close_s.tolist(),
                    "ok":           True,
                }
            except Exception as e:
                print(f"  ⚠️  {symbol}: {e}")
                results[symbol] = {"ok": False, "error": str(e)}

    except Exception as e:
        print(f"⚠️  Watchlist batch failed: {e}")
        for sym in symbols:
            time.sleep(random.uniform(1.0, 2.0))
            try:
                t        = yf.Ticker(sym)
                fi       = t.fast_info
                h7       = t.history(period="7d")
                h1m      = t.history(period="1mo")
                last_vol = int(fi.get("last_volume", 0) or 0)
                avg_vol  = int(fi.get("three_month_average_volume", 1) or 1)
                results[sym] = {
                    "price":        round(float(fi.get("last_price", 0) or 0), 2),
                    "day_change":   round(float(fi.get("regular_market_change_percent", 0) or 0), 2),
                    "volume":       last_vol,
                    "avg_volume":   max(avg_vol, 1),
                    "volume_spike": (last_vol / max(avg_vol, 1)) > 2.0,
                    "week_high":    round(float(h7["High"].max()),  2) if len(h7)  > 0 else 0,
                    "week_low":     round(float(h7["Low"].min()),   2) if len(h7)  > 0 else 0,
                    "month_high":   round(float(h1m["High"].max()), 2) if len(h1m) > 0 else 0,
                    "month_low":    round(float(h1m["Low"].min()),  2) if len(h1m) > 0 else 0,
                    "close_series": h1m["Close"].tolist() if len(h1m) > 0 else [],
                    "ok":           True,
                }
            except Exception as e2:
                results[sym] = {"ok": False, "error": str(e2)}

    return results

def fetch_macro_anchors() -> list:
    """
    Fetch USD/INR, Brent Crude, Gold, India VIX, Dollar Index.
    Returns list of 5 dicts with: name, symbol, price, change_pct, weekly_change_pct, status, ok
    """
    print("📡 Fetching macro anchors (USDINR, Brent, Gold, VIX, DXY)...")
    anchors = [
        {"name": "USD/INR",      "symbol": "USDINR=X"},
        {"name": "Brent Crude",  "symbol": "BZ=F"},
        {"name": "Gold",         "symbol": "GC=F"},
        {"name": "India VIX",   "symbol": "^INDIAVIX"},
        {"name": "Dollar Index", "symbol": "DX-Y.NYB"},
    ]
    results = []
    for anchor in anchors:
        sym  = anchor["symbol"]
        name = anchor["name"]
        try:
            raw = yf.download(sym, period="5d", interval="1d",
                             auto_adjust=True, progress=False)
            close_s = _safe_series(raw, sym, [sym], "Close")

            if len(close_s) >= 2:
                prev    = float(close_s.iloc[-2])
                current = float(close_s.iloc[-1])
                change  = round(((current - prev) / prev) * 100, 3) if prev else 0.0

                # Weekly change: first to last close in 5d range
                week_ago   = float(close_s.iloc[0])
                weekly_chg = round(((current - week_ago) / week_ago) * 100, 3) if week_ago else None

                # Status: pure change_pct direction (24/5 instruments — no market-hours check)
                if change > 0.05:
                    status = "up"
                elif change < -0.05:
                    status = "down"
                else:
                    status = "flat"

                results.append({
                    "name":               name,
                    "symbol":             sym,
                    "price":              round(current, 2),
                    "change_pct":         round(change, 2),
                    "weekly_change_pct":  weekly_chg,
                    "status":             status,
                    "ok":                 True,
                })
            else:
                raise ValueError("Insufficient close data")

        except Exception as e:
            print(f"⚠️  Macro anchor {name} ({sym}): {e}")
            results.append({
                "name":               name,
                "symbol":             sym,
                "price":              None,
                "change_pct":         None,
                "weekly_change_pct":  None,
                "status":             None,
                "ok":                 False,
            })

    ok_count = sum(1 for r in results if r["ok"])
    print(f"✅ Macro anchors: {ok_count}/3 fetched")
    return results


def fetch_news_finnhub(symbol: str, days: int = 7) -> List[Dict]:
    if not FINNHUB_KEY:
        return []
    to_d   = datetime.now().strftime("%Y-%m-%d")
    from_d = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    url    = (f"https://finnhub.io/api/v1/company-news"
              f"?symbol={symbol}&from={from_d}&to={to_d}&token={FINNHUB_KEY}")
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if isinstance(data, list):
            return [{"headline": a.get("headline", ""),
                     "source":   a.get("source",   ""),
                     "url":      a.get("url",       "")}
                    for a in data[:5]]
    except Exception as e:
        print(f"⚠️  Finnhub news ({symbol}): {e}")
    return []

def fetch_general_news() -> List[Dict]:
    """Fetch global financial news from Finnhub (general + forex + crypto categories)."""
    if not FINNHUB_KEY:
        return []
    all_articles = []
    for category in ["general", "forex", "crypto"]:
        url = f"https://finnhub.io/api/v1/news?category={category}&token={FINNHUB_KEY}"
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            if isinstance(data, list):
                for a in data[:5]:
                    all_articles.append({
                        "headline": a.get("headline", ""),
                        "source":   a.get("source",   ""),
                        "url":      a.get("url",       ""),
                        "category": "global",
                    })
        except Exception as e:
            print(f"⚠️  {category} news: {e}")
    return all_articles


def fetch_indian_news() -> List[Dict]:
    """Fetch India-specific news from RSS feeds (Economic Times, MoneyControl, Livemint)."""
    import xml.etree.ElementTree as ET

    RSS_FEEDS = {
        "Economic Times": "https://economictimes.indiatimes.com/rssfeedstopstories.cms",
        "MoneyControl":   "https://www.moneycontrol.com/rss/latestnews.xml",
        "Livemint":       "https://www.livemint.com/rss/markets",
    }

    articles = []
    for source_name, rss_url in RSS_FEEDS.items():
        try:
            resp = requests.get(rss_url, timeout=10, headers={
                "User-Agent": "Mozilla/5.0 (compatible; MarketIntelBot/1.0)"
            })
            if resp.status_code != 200:
                continue
            root = ET.fromstring(resp.content)
            # RSS 2.0 format
            for item in root.findall(".//item")[:5]:
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                desc = item.findtext("description", "").strip()[:200]
                if title:
                    articles.append({
                        "headline": title,
                        "source":   source_name,
                        "url":      link,
                        "summary":  desc,
                        "category": "india",
                    })
        except Exception as e:
            print(f"⚠️  RSS {source_name}: {e}")

    return articles


def fetch_market_breadth() -> Optional[Dict]:
    """
    Fetch NSE market breadth data (advance/decline, 52W highs/lows).
    Uses NSE API for market activity data.
    """
    url = "https://www.nseindia.com/api/marketStatus"
    try:
        session = requests.Session()
        session.get("https://www.nseindia.com", headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }, timeout=10)
        resp = session.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }, timeout=10)

        if resp.status_code != 200:
            return None

        data = resp.json()

        # Extract breadth from market data
        breadth = {
            "ok": True,
            "advances": 0,
            "declines": 0,
            "unchanged": 0,
            "highs_52w": 0,
            "lows_52w": 0,
        }

        # NSE market status endpoint may have different structures
        # Try to extract from available data
        if "marketState" in data:
            for market in data["marketState"]:
                if market.get("market") == "Capital Market - Normal":
                    breadth["advances"] = int(market.get("advances", 0) or 0)
                    breadth["declines"] = int(market.get("declines", 0) or 0)
                    breadth["unchanged"] = int(market.get("unchanged", 0) or 0)

        # Compute A/D ratio
        if breadth["declines"] > 0:
            breadth["ad_ratio"] = round(breadth["advances"] / breadth["declines"], 2)
        elif breadth["advances"] > 0:
            breadth["ad_ratio"] = 99.0  # All advances
        else:
            breadth["ad_ratio"] = 1.0

        # Determine breadth strength
        ratio = breadth["ad_ratio"]
        if ratio > 2.0:
            breadth["strength"] = "STRONG"
        elif ratio > 1.2:
            breadth["strength"] = "MODERATE"
        elif ratio > 0.8:
            breadth["strength"] = "NEUTRAL"
        elif ratio > 0.5:
            breadth["strength"] = "WEAK"
        else:
            breadth["strength"] = "VERY WEAK"

        return breadth

    except Exception as e:
        print(f"⚠️  Market breadth: {e}")
        return None


def format_market_breadth(breadth: Optional[Dict]) -> str:
    """Format market breadth for prompt injection."""
    if not breadth or not breadth.get("ok"):
        return ""

    adv = breadth["advances"]
    dec = breadth["declines"]
    unc = breadth.get("unchanged", 0)
    ratio = breadth["ad_ratio"]
    strength = breadth["strength"]

    lines = [
        f"[Market Breadth]",
        f"A/D: {adv}↑ / {dec}↓ / {unc}→ | Ratio: {ratio} ({strength})",
    ]

    if breadth.get("highs_52w"):
        lines.append(f"52W Highs: {breadth['highs_52w']} | 52W Lows: {breadth['lows_52w']}")

    return "\n".join(lines)