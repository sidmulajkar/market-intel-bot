"""
Market Data Fetcher
Sources: yfinance (batch download) + Finnhub free API
Fixed: Uses yf.download() batch call — avoids 429 rate limits
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

# ── GLOBAL INDICES ────────────────────────────────────────────────
GLOBAL_INDICES = {
    "US":          {"symbol": "^GSPC",      "region": "Americas", "flag": "🇺🇸", "iso": "US"},
    "Brazil":      {"symbol": "^BVSP",      "region": "Americas", "flag": "🇧🇷", "iso": "BR"},
    "Canada":      {"symbol": "^GSPTSE",    "region": "Americas", "flag": "🇨🇦", "iso": "CA"},
    "Mexico":      {"symbol": "^MXX",       "region": "Americas", "flag": "🇲🇽", "iso": "MX"},
    "Chile":       {"symbol": "^IPSA",      "region": "Americas", "flag": "🇨🇱", "iso": "CL"},
    "South Korea": {"symbol": "^KS11",      "region": "Asia",     "flag": "🇰🇷", "iso": "KR"},
    "Singapore":   {"symbol": "^STI",       "region": "Asia",     "flag": "🇸🇬", "iso": "SG"},
    "Taiwan":      {"symbol": "^TWII",      "region": "Asia",     "flag": "🇹🇼", "iso": "TW"},
    "Hong Kong":   {"symbol": "^HSI",       "region": "Asia",     "flag": "🇭🇰", "iso": "HK"},
    "Japan":       {"symbol": "^N225",      "region": "Asia",     "flag": "🇯🇵", "iso": "JP"},
    "China":       {"symbol": "000001.SS",  "region": "Asia",     "flag": "🇨🇳", "iso": "CN"},
    "Australia":   {"symbol": "^AXJO",      "region": "Asia",     "flag": "🇦🇺", "iso": "AU"},
    "India":       {"symbol": "^NSEI",      "region": "Asia",     "flag": "🇮🇳", "iso": "IN"},
    "Italy":       {"symbol": "FTSEMIB.MI", "region": "Europe",   "flag": "🇮🇹", "iso": "IT"},
    "UK":          {"symbol": "^FTSE",      "region": "Europe",   "flag": "🇬🇧", "iso": "GB"},
    "Germany":     {"symbol": "^GDAXI",     "region": "Europe",   "flag": "🇩🇪", "iso": "DE"},
    "Switzerland": {"symbol": "^SSMI",      "region": "Europe",   "flag": "🇨🇭", "iso": "CH"},
    "France":      {"symbol": "^FCHI",      "region": "Europe",   "flag": "🇫🇷", "iso": "FR"},
}

# ── MARKET HOURS ──────────────────────────────────────────────────
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
    """Returns OPEN or CLOSED based on current local time"""
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

def _fallback_entry(country: str, info: dict, error: str) -> dict:
    return {
        "symbol":     info["symbol"],
        "region":     info["region"],
        "flag":       info["flag"],
        "iso":        info.get("iso", ""),
        "price":      0.0,
        "change_pct": 0.0,
        "status":     get_market_status(country),
        "ok":         False,
        "error":      error,
    }

def fetch_global_indices() -> Dict:
    """
    Fetch all 18 global indices using batch yf.download().
    Falls back to individual fetches with delays if batch fails.
    """
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
                if len(symbols_list) > 1:
                    if sym in raw.columns.get_level_values(0):
                        sym_data = raw[sym]["Close"].dropna()
                    else:
                        raise ValueError(f"{sym} not in batch result")
                else:
                    sym_data = raw["Close"].dropna()

                if len(sym_data) >= 2:
                    prev    = float(sym_data.iloc[-2])
                    current = float(sym_data.iloc[-1])
                    change  = ((current - prev) / prev) * 100
                elif len(sym_data) == 1:
                    current = float(sym_data.iloc[-1])
                    change  = 0.0
                else:
                    raise ValueError("No data in series")

                results[country] = {
                    "symbol":     sym,
                    "region":     info["region"],
                    "flag":       info["flag"],
                    "iso":        info.get("iso", ""),
                    "price":      round(current, 2),
                    "change_pct": round(change, 2),
                    "status":     get_market_status(country),
                    "ok":         True,
                }
            except Exception as e:
                print(f"  ⚠️  {country} parse error: {e}")
                results[country] = _fallback_entry(country, info, str(e))

    except Exception as e:
        print(f"⚠️  Batch download failed: {e}")
        print("🔄 Falling back to individual fetches...")
        results = _fetch_individual_fallback()

    ok_count = sum(1 for v in results.values() if v.get("ok"))
    print(f"✅ Global indices: {ok_count}/18 fetched successfully")
    return results

def _fetch_individual_fallback() -> Dict:
    """Fetch one by one with random delays — fallback only"""
    results = {}
    for country, info in GLOBAL_INDICES.items():
        time.sleep(random.uniform(1.5, 3.0))
        try:
            t    = yf.Ticker(info["symbol"])
            hist = t.history(period="5d", interval="1d").dropna(subset=["Close"])
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
                "price":      round(current, 2),
                "change_pct": round(change, 2),
                "status":     get_market_status(country),
                "ok":         True,
            }
        except Exception as e:
            print(f"  ⚠️  {country} individual fetch failed: {e}")
            results[country] = _fallback_entry(country, info, str(e))

    return results

def fetch_watchlist_data(symbols: List[str]) -> Dict:
    """
    Fetch OHLCV data for watchlist stocks using batch download.
    """
    if not symbols:
        return {}

    print(f"📈 Fetching watchlist data: {symbols}")
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
                if len(symbols) > 1:
                    if symbol in raw.columns.get_level_values(0):
                        sym_df = raw[symbol].dropna(subset=["Close"])
                    else:
                        raise ValueError(f"{symbol} not in batch")
                else:
                    sym_df = raw.dropna(subset=["Close"])

                if len(sym_df) < 1:
                    raise ValueError("Empty dataframe")

                h7       = sym_df.tail(7)
                last_cls = float(sym_df["Close"].iloc[-1])
                prev_cls = float(sym_df["Close"].iloc[-2]) if len(sym_df) >= 2 else last_cls
                day_chg  = ((last_cls - prev_cls) / prev_cls) * 100
                last_vol = int(sym_df["Volume"].iloc[-1]) if "Volume" in sym_df.columns else 0
                avg_vol  = int(sym_df["Volume"].mean())   if "Volume" in sym_df.columns else 1
                avg_vol  = max(avg_vol, 1)

                results[symbol] = {
                    "price":        round(last_cls, 2),
                    "day_change":   round(day_chg, 2),
                    "volume":       last_vol,
                    "avg_volume":   avg_vol,
                    "volume_spike": (last_vol / avg_vol) > 2.0,
                    "week_high":    round(float(h7["High"].max()),     2) if "High"  in h7.columns and len(h7) > 0 else 0,
                    "week_low":     round(float(h7["Low"].min()),      2) if "Low"   in h7.columns and len(h7) > 0 else 0,
                    "month_high":   round(float(sym_df["High"].max()), 2) if "High"  in sym_df.columns else 0,
                    "month_low":    round(float(sym_df["Low"].min()),  2) if "Low"   in sym_df.columns else 0,
                    "close_series": sym_df["Close"].tolist(),
                    "ok":           True,
                }
            except Exception as e:
                print(f"  ⚠️  {symbol} parse error: {e}")
                results[symbol] = {"ok": False, "error": str(e)}

    except Exception as e:
        print(f"⚠️  Watchlist batch failed: {e}")
        # Individual fallback
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
                    "price":        round(fi.get("last_price", 0) or 0, 2),
                    "day_change":   round(fi.get("regular_market_change_percent", 0) or 0, 2),
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

def fetch_news_finnhub(symbol: str, days: int = 7) -> List[Dict]:
    """Fetch company news from Finnhub free tier (60 calls/min)"""
    if not FINNHUB_KEY:
        print("⚠️  No FINNHUB_KEY set — skipping news")
        return []
    to_d   = datetime.now().strftime("%Y-%m-%d")
    from_d = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    url    = (
        f"https://finnhub.io/api/v1/company-news"
        f"?symbol={symbol}&from={from_d}&to={to_d}&token={FINNHUB_KEY}"
    )
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if isinstance(data, list):
            return [
                {
                    "headline": a.get("headline", ""),
                    "source":   a.get("source",   ""),
                    "url":      a.get("url",       ""),
                }
                for a in data[:5]
            ]
    except Exception as e:
        print(f"⚠️  Finnhub news error ({symbol}): {e}")
    return []

def fetch_general_news() -> List[Dict]:
    """General market news from Finnhub — no symbol needed"""
    if not FINNHUB_KEY:
        return []
    url = f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_KEY}"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if isinstance(data, list):
            return [
                {
                    "headline": a.get("headline", ""),
                    "source":   a.get("source",   ""),
                    "url":      a.get("url",       ""),
                }
                for a in data[:8]
            ]
    except Exception as e:
        print(f"⚠️  General news error: {e}")
    return []