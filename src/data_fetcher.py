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
    Fetch macro anchors — global risk, dollar, energy, metals, rates, currencies.
    Batch fetch via single yf.download() call for speed.

    Returns list of dicts with: name, symbol, price, change_pct, weekly_change_pct, status, ok

    Anchors (14):
    - USD/INR, Brent Crude, Gold — existing
    - India VIX, Dollar Index, US 10Y — existing
    - CBOE VIX (global fear), HYG (credit stress), WTI Crude — existing
    - JPY (carry trade), EUR (DXY composition), Silver, Copper (growth proxy), US 2Y (Fed expectations) — NEW
    """
    print("📡 Fetching macro anchors (14 tickers, batch)...")
    anchors = [
        {"name": "USD/INR",         "symbol": "USDINR=X"},
        {"name": "Brent Crude",     "symbol": "BZ=F"},
        {"name": "Gold",            "symbol": "GC=F"},
        {"name": "India VIX",       "symbol": "^INDIAVIX"},
        {"name": "Dollar Index",    "symbol": "DX-Y.NYB"},
        {"name": "US 10Y Yield",    "symbol": "^TNX"},
        {"name": "CBOE VIX",        "symbol": "^VIX"},
        {"name": "US High Yield",   "symbol": "HYG"},
        {"name": "WTI Crude",       "symbol": "CL=F"},
        # Phase 8: Institutional macro anchors
        {"name": "USD/JPY",         "symbol": "JPY=X"},       # Carry trade funding currency
        {"name": "EUR/USD",         "symbol": "EURUSD=X"},    # DXY composition (57%)
        {"name": "Silver",          "symbol": "SI=F"},        # Industrial precious metal
        {"name": "Copper",          "symbol": "HG=F"},        # Dr. Copper — growth proxy
        {"name": "US 2Y Yield",     "symbol": "2YY=F"},       # Fed expectations
    ]

    symbols = [a["symbol"] for a in anchors]
    name_map = {a["symbol"]: a["name"] for a in anchors}

    results = []
    try:
        # Batch download all tickers in one call
        raw = yf.download(symbols, period="5d", interval="1d",
                          auto_adjust=True, progress=False, group_by="ticker")

        for sym in symbols:
            name = name_map[sym]
            try:
                # Extract close series — batch download with group_by='ticker'
                # gives Ticker as level 0, Price as level 1
                close_s = raw[sym]["Close"].dropna()

                if len(close_s) >= 2:
                    prev    = float(close_s.iloc[-2])
                    current = float(close_s.iloc[-1])
                    change  = round(((current - prev) / prev) * 100, 3) if prev else 0.0

                    week_ago   = float(close_s.iloc[0])
                    weekly_chg = round(((current - week_ago) / week_ago) * 100, 3) if week_ago else None

                    if change > 0.05:
                        status = "up"
                    elif change < -0.05:
                        status = "down"
                    else:
                        status = "flat"

                    results.append({
                        "name":              name,
                        "symbol":            sym,
                        "price":             round(current, 2),
                        "change_pct":        round(change, 2),
                        "weekly_change_pct": weekly_chg,
                        "status":            status,
                        "ok":                True,
                    })
                else:
                    raise ValueError("Insufficient close data")
            except Exception as e:
                print(f"⚠️  Macro anchor {name} ({sym}): {e}")
                results.append({
                    "name": name, "symbol": sym, "price": None,
                    "change_pct": None, "weekly_change_pct": None,
                    "status": None, "ok": False,
                })

    except Exception as e:
        print(f"⚠️  Batch download failed: {e}")
        # Fallback: individual fetches
        for anchor in anchors:
            sym, name = anchor["symbol"], anchor["name"]
            try:
                raw = yf.download(sym, period="5d", interval="1d",
                                  auto_adjust=True, progress=False)
                close_s = _safe_series(raw, sym, [sym], "Close")
                if len(close_s) >= 2:
                    prev = float(close_s.iloc[-2])
                    current = float(close_s.iloc[-1])
                    change = round(((current - prev) / prev) * 100, 3) if prev else 0.0
                    week_ago = float(close_s.iloc[0])
                    weekly_chg = round(((current - week_ago) / week_ago) * 100, 3) if week_ago else None
                    status = "up" if change > 0.05 else "down" if change < -0.05 else "flat"
                    results.append({"name": name, "symbol": sym, "price": round(current, 2),
                                    "change_pct": round(change, 2), "weekly_change_pct": weekly_chg,
                                    "status": status, "ok": True})
                else:
                    raise ValueError("Insufficient data")
            except Exception as e2:
                print(f"⚠️  {name}: {e2}")
                results.append({"name": name, "symbol": sym, "price": None,
                                "change_pct": None, "weekly_change_pct": None,
                                "status": None, "ok": False})

    ok_count = sum(1 for r in results if r["ok"])
    print(f"✅ Macro anchors: {ok_count}/{len(anchors)} fetched")
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# SMALLCAP / LARGECAPE RATIO — Risk Appetite Indicator
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_smallcap_ratio() -> Dict:
    """
    Fetch Nifty Smallcap 250 / Nifty 50 ratio from NSE allIndices.
    Rising ratio = small-cap outperformance = risk-on / retail euphoria.
    Falling ratio = large-cap flight = risk-off.
    """
    import requests

    NSE_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.nseindia.com/",
        "Accept": "application/json",
    }

    session = requests.Session()
    try:
        session.get("https://www.nseindia.com", headers=NSE_HEADERS, timeout=10)
    except Exception:
        pass

    try:
        resp = session.get("https://www.nseindia.com/api/allIndices", headers=NSE_HEADERS, timeout=15)
        if resp.status_code != 200:
            return {"ok": False}

        indices = resp.json().get("data", [])
        nifty_50 = None
        smallcap_250 = None

        for idx in indices:
            name = idx.get("index", "")
            if name == "NIFTY 50":
                nifty_50 = float(idx.get("last", 0))
            elif name == "NIFTY SMALLCAP 250":
                smallcap_250 = float(idx.get("last", 0))

        if not nifty_50 or not smallcap_250:
            return {"ok": False}

        ratio = round(smallcap_250 / nifty_50, 4)
        # Historical context: ratio typically 0.5-1.0
        # Below 0.6 = smallcaps crushed (risk-off)
        # Above 0.9 = smallcap euphoria (late cycle)

        if ratio > 0.9:
            label = "SMALLCAP EUPHORIA — late cycle, contrarian sell"
        elif ratio > 0.8:
            label = "SMALLCAP OUTPERFORMANCE — risk-on"
        elif ratio > 0.65:
            label = "BALANCED"
        elif ratio > 0.5:
            label = "LARGE-CAP FLIGHT — risk-off"
        else:
            label = "SMALLCAP CRASH — extreme fear, contrarian buy"

        return {
            "ok": True,
            "nifty_50": nifty_50,
            "smallcap_250": smallcap_250,
            "ratio": ratio,
            "label": label,
        }

    except Exception as e:
        print(f"⚠️ Smallcap ratio: {e}")
        return {"ok": False}


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
    """Format market breadth for prompt injection with historical percentile."""
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

    # Add historical percentile context
    try:
        from src.db import get_breadth_history
        from src.quant_enrichment import compute_percentile
        history = get_breadth_history(days=90)
        if history and len(history) >= 5:
            ratios = [h["ratio"] for h in history if h.get("ratio")]
            pct = compute_percentile(ratio, ratios)
            if pct.get("percentile") is not None:
                lines.append(f"Breadth percentile: {pct['percentile']}th of 90D ({pct['label']})")
    except Exception:
        pass  # Non-critical, skip if DB unavailable

    if breadth.get("highs_52w"):
        lines.append(f"52W Highs: {breadth['highs_52w']} | 52W Lows: {breadth['lows_52w']}")

    # McClellan Oscillator
    try:
        mcc = compute_mcclellan()
        if mcc.get("ok"):
            lines.append(f"McClellan: {mcc['oscillator']:+.0f} ({mcc['signal']})")
    except Exception:
        pass

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# BREADTH: McClellan Oscillator
# ═══════════════════════════════════════════════════════════════════════════════

def compute_mcclellan() -> Dict:
    """
    Compute McClellan Oscillator from stored breadth history.
    McClellan = EMA(19) of net advances - EMA(39) of net advances
    Positive = bullish breadth momentum, Negative = bearish.
    """
    try:
        from src.db import get_breadth_history
        history = get_breadth_history(days=60)

        if not history or len(history) < 20:
            return {"ok": False, "message": "Insufficient breadth history"}

        # Compute net advances (advances - declines) for each day
        # We only have ratio, so approximate: net = ratio * declines - declines = declines * (ratio - 1)
        # Simpler: use ratio as the signal itself
        ratios = [h["ratio"] for h in history if h.get("ratio")]

        if len(ratios) < 20:
            return {"ok": False}

        # EMA computation
        def ema(data, period):
            k = 2 / (period + 1)
            result = [data[0]]
            for i in range(1, len(data)):
                result.append(data[i] * k + result[-1] * (1 - k))
            return result

        ema19 = ema(ratios, 19)
        ema39 = ema(ratios, 39)

        oscillator = round((ema19[-1] - ema39[-1]) * 100, 1)  # Scale up

        if oscillator > 20:
            signal = "STRONG BULLISH breadth momentum"
        elif oscillator > 5:
            signal = "BULLISH breadth momentum"
        elif oscillator > -5:
            signal = "NEUTRAL breadth"
        elif oscillator > -20:
            signal = "BEARISH breadth momentum"
        else:
            signal = "STRONG BEARISH breadth momentum"

        return {
            "ok": True,
            "oscillator": oscillator,
            "ema19": round(ema19[-1], 3),
            "ema39": round(ema39[-1], 3),
            "signal": signal,
        }

    except Exception as e:
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# TOP MOVERS — Auto-fetched top gainers/losers from India + US markets
# Replaces static watchlist with dynamic market-wide view
# ═══════════════════════════════════════════════════════════════════════════════

# Nifty 50 constituents (NSE symbols with .NS suffix for yfinance)
NIFTY_50 = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "LT.NS", "AXISBANK.NS", "BAJFINANCE.NS", "ASIANPAINT.NS", "MARUTI.NS",
    "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS", "NESTLEIND.NS", "WIPRO.NS",
    "HCLTECH.NS", "M&M.NS", "NTPC.NS", "TATAMOTORS.NS", "POWERGRID.NS",
    "ONGC.NS", "JSWSTEEL.NS", "TATASTEEL.NS", "ADANIENT.NS", "ADANIPORTS.NS",
    "BAJAJFINSV.NS", "TECHM.NS", "HDFCLIFE.NS", "DIVISLAB.NS", "DRREDDY.NS",
    "CIPLA.NS", "EICHERMOT.NS", "BRITANNIA.NS", "COALINDIA.NS", "GRASIM.NS",
    "HEROMOTOCO.NS", "INDUSINDBK.NS", "TATACONSUM.NS", "APOLLOHOSP.NS",
    "BPCL.NS", "HINDALCO.NS", "SBILIFE.NS", "UPL.NS", "BAJAJ-AUTO.NS",
    "SHRIRAMFIN.NS",
]

# Major US stocks (broad representation across sectors)
US_MAJOR = [
    # Tech mega caps
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO",
    # Semis
    "AMD", "INTC", "QCOM", "MU", "ARM",
    # Finance
    "JPM", "BAC", "GS", "MS", "V", "MA", "BRK-B",
    # Healthcare
    "UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK",
    # Consumer
    "WMT", "PG", "KO", "PEP", "COST", "MCD", "NKE",
    # Energy
    "XOM", "CVX", "COP",
    # Industrial
    "CAT", "BA", "HON", "UPS", "GE",
    # Telecom
    "DIS", "NFLX", "CMCSA",
    # Other
    "PLTR", "COIN", "SQ", "SHOP", "CRWD",
]


def fetch_top_movers(top_n: int = 10) -> Dict:
    """
    Fetch top gainers and losers from Indian (Nifty 50) and US markets.
    Returns top N gainers + losers per market, sorted by daily change%.
    """
    import yfinance as yf
    from concurrent.futures import ThreadPoolExecutor, as_completed

    result = {
        "india": {"gainers": [], "losers": []},
        "us": {"gainers": [], "losers": []},
    }

    def _fetch_batch(symbols, market):
        """Fetch a batch of tickers (chunked to 25 max) and return sorted movers."""
        try:
            all_movers = []
            # Chunk into groups of 25 to avoid yfinance rate limits
            chunk_size = 25
            for i in range(0, len(symbols), chunk_size):
                chunk = symbols[i:i + chunk_size]
                chunk_movers = _fetch_single_chunk(chunk, market)
                all_movers.extend(chunk_movers)
                # Rate limit: sleep between chunks (not after last)
                if i + chunk_size < len(symbols):
                    import time
                    time.sleep(1)
            return all_movers
        except Exception as e:
            print(f"⚠️  {market} batch fetch error: {e}")
            return []

    def _fetch_single_chunk(symbols, market):
        """Fetch a single chunk of tickers."""
        try:
            data = yf.download(symbols, period="5d", interval="1d",
                               group_by="ticker", progress=False, threads=True)
            movers = []
            for sym in symbols:
                try:
                    if len(symbols) > 1:
                        series = _safe_series_movers(data, sym, "Close")
                    else:
                        series = _safe_series_movers(data, symbols[0], "Close")
                    if series is not None and len(series) >= 2:
                        current = float(series.iloc[-1])
                        prev = float(series.iloc[-2])
                        change_pct = round((current - prev) / prev * 100, 2) if prev > 0 else 0
                        # Get weekly change (5-day)
                        if len(series) >= 5:
                            week_ago = float(series.iloc[-5])
                            weekly_pct = round((current - week_ago) / week_ago * 100, 2) if week_ago > 0 else 0
                        else:
                            weekly_pct = change_pct
                        movers.append({
                            "symbol": sym.replace(".NS", ""),
                            "price": current,
                            "change_pct": change_pct,
                            "weekly_pct": weekly_pct,
                            "market": market,
                        })
                except Exception:
                    continue
            return movers
        except Exception as e:
            print(f"⚠️  {market} batch fetch error: {e}")
            return []

    # Fetch India (Nifty 50) and US in parallel
    print("📊 Fetching top movers (India Nifty 50 + US majors)...")
    with ThreadPoolExecutor(max_workers=2) as executor:
        india_future = executor.submit(_fetch_batch, NIFTY_50, "India")
        us_future = executor.submit(_fetch_batch, US_MAJOR, "US")

        india_movers = india_future.result()
        us_movers = us_future.result()

    # Sort and split into gainers/losers
    india_sorted = sorted(india_movers, key=lambda x: x["change_pct"], reverse=True)
    result["india"]["gainers"] = india_sorted[:top_n]
    result["india"]["losers"] = india_sorted[-top_n:][::-1]  # reverse to show worst first
    result["india"]["total"] = len(india_movers)

    us_sorted = sorted(us_movers, key=lambda x: x["change_pct"], reverse=True)
    result["us"]["gainers"] = us_sorted[:top_n]
    result["us"]["losers"] = us_sorted[-top_n:][::-1]
    result["us"]["total"] = len(us_movers)

    print(f"   → India: {len(india_movers)} stocks, US: {len(us_movers)} stocks")
    return result


def _safe_series_movers(data, ticker, col):
    """Safely extract a series from yfinance batch download (top movers variant)."""
    try:
        if hasattr(data, 'columns') and isinstance(data.columns, pd.MultiIndex):
            if col in data.columns.get_level_values(0):
                s = data[col][ticker] if ticker in data[col].columns else None
            elif ticker in data.columns.get_level_values(0):
                s = data[ticker][col] if col in data[ticker].columns else None
            else:
                s = None
        else:
            s = data[col] if col in data.columns else None
        return s.dropna() if s is not None else None
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# US EMPLOYMENT DATA — BLS Public API (no key needed)
# Fetches unemployment rate, nonfarm payrolls, JOLTS job openings
# For recession detection + labor market health + geopolitical impact
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_us_employment() -> Dict:
    """
    Fetch US employment data from BLS public API v2 (no API key).
    Returns unemployment rate, NFP, JOLTS with trend analysis.

    Signals:
    - Unemployment rising > 0.5% from 12M low = recession warning
    - NFP declining for 3+ months = labor market weakening
    - JOLTS falling = demand for workers declining (early recession signal)
    - Unemployment > 4.5% = elevated (recession territory historically)
    """
    import requests as req

    series_map = {
        "unemployment": "LNS14000000",      # Unemployment Rate (SA)
        "nfp": "CES0000000001",              # Nonfarm Payrolls (thousands)
        "jolts": "JTS000000000000000JOL",    # JOLTS Total Job Openings
    }

    result = {}
    headers = {"Content-type": "application/json"}

    for name, series_id in series_map.items():
        try:
            url = f"https://api.bls.gov/publicAPI/v2/timeseries/data/{series_id}"
            resp = req.get(url, headers=headers, timeout=15)
            data = resp.json()

            if data.get("status") != "REQUEST_SUCCEEDED":
                result[name] = {"ok": False}
                continue

            series_data = data.get("Results", {}).get("series", [{}])[0].get("data", [])
            if not series_data:
                result[name] = {"ok": False}
                continue

            # Parse values
            readings = []
            for item in series_data[:12]:  # Last 12 months
                val = item.get("value")
                if val and val != "-":
                    readings.append({
                        "year": item["year"],
                        "month": item.get("periodName", ""),
                        "value": float(val),
                    })

            if len(readings) < 2:
                result[name] = {"ok": False}
                continue

            latest = readings[0]
            prev = readings[1]

            # Compute trend (3-month vs 6-month average)
            recent_3 = [r["value"] for r in readings[:3]]
            recent_6 = [r["value"] for r in readings[:6]]
            avg_3 = sum(recent_3) / len(recent_3)
            avg_6 = sum(recent_6) / len(recent_6)

            # 12-month low and high
            all_vals = [r["value"] for r in readings]
            low_12m = min(all_vals)
            high_12m = max(all_vals)

            result[name] = {
                "ok": True,
                "latest": latest["value"],
                "latest_label": f"{latest['month']} {latest['year']}",
                "prev": prev["value"],
                "prev_label": f"{prev['month']} {prev['year']}",
                "change": round(latest["value"] - prev["value"], 2),
                "avg_3m": round(avg_3, 2),
                "avg_6m": round(avg_6, 2),
                "low_12m": low_12m,
                "high_12m": high_12m,
                "trend": "RISING" if avg_3 > avg_6 else ("FALLING" if avg_3 < avg_6 else "FLAT"),
                "readings": readings,
            }

        except Exception as e:
            print(f"⚠️ BLS {name} fetch error: {e}")
            result[name] = {"ok": False}

    # Compute composite signals
    unemp = result.get("unemployment", {})
    nfp = result.get("nfp", {})
    jolts = result.get("jolts", {})

    signals = []
    recession_score = 0  # 0-10, higher = more recession risk

    # Unemployment analysis
    if unemp.get("ok"):
        rate = unemp["latest"]
        low = unemp["low_12m"]
        rise_from_low = round(rate - low, 1)

        if rate > 5.0:
            recession_score += 3
            signals.append(f"Unemployment {rate}% — ABOVE 5% (recession territory)")
        elif rate > 4.5:
            recession_score += 2
            signals.append(f"Unemployment {rate}% — ELEVATED (above 4.5%)")
        elif rate > 4.0:
            signals.append(f"Unemployment {rate}% — NORMAL range")
        else:
            signals.append(f"Unemployment {rate}% — LOW (tight labor market)")

        if rise_from_low >= 0.5:
            recession_score += 2
            signals.append(f"Unemployment up {rise_from_low}% from 12M low — Sahm Rule proximity")

        if unemp["trend"] == "RISING":
            recession_score += 1
            signals.append(f"Unemployment trend: RISING ({unemp['avg_3m']}% 3M avg vs {unemp['avg_6m']}% 6M avg)")

    # NFP analysis (values in thousands: 158736 = 158.7M total, monthly change in K)
    if nfp.get("ok"):
        latest_nfp = nfp["latest"]
        change = nfp["change"]

        # NFP is total employment in thousands. Monthly job gains = current - previous
        monthly_gain = change  # already computed as latest - prev

        if monthly_gain < 100:
            recession_score += 2
            signals.append(f"NFP monthly gain {monthly_gain:+.0f}K — BELOW 100K (recession signal)")
        elif monthly_gain < 150:
            signals.append(f"NFP monthly gain {monthly_gain:+.0f}K — SLOWING (below trend)")
        else:
            signals.append(f"NFP monthly gain {monthly_gain:+.0f}K — HEALTHY")

        if nfp["trend"] == "FALLING":
            recession_score += 1
            signals.append(f"NFP trend: FALLING — employment growth decelerating")

    # JOLTS analysis (values in thousands: 6866 = 6.866M)
    if jolts.get("ok"):
        openings = jolts["latest"]
        if openings < 6000:
            recession_score += 2
            signals.append(f"JOLTS {openings/1000:.1f}M — BELOW 6M (labor demand weakening)")
        elif openings < 7000:
            signals.append(f"JOLTS {openings/1000:.1f}M — COOLING (was 9M+ in 2022)")
        else:
            signals.append(f"JOLTS {openings/1000:.1f}M — STILL ELEVATED")

        if jolts["trend"] == "FALLING":
            recession_score += 1
            signals.append(f"JOLTS trend: FALLING — demand for workers declining")

    # Composite recession risk
    recession_score = min(10, recession_score)
    if recession_score >= 7:
        recession_level = "HIGH"
    elif recession_score >= 4:
        recession_level = "ELEVATED"
    elif recession_score >= 2:
        recession_level = "MODERATE"
    else:
        recession_level = "LOW"

    return {
        "ok": any(r.get("ok") for r in result.values()),
        "unemployment": unemp,
        "nfp": nfp,
        "jolts": jolts,
        "recession_score": recession_score,
        "recession_level": recession_level,
        "signals": signals,
    }