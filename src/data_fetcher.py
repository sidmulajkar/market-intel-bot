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
    "Switzerland": {"symbol": "^SSMI",      "region": "Europe",   "flag": "🇨🇭", "iso": "CH",  "index_name": " SMI"},
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
    if not FINNHUB_KEY:
        return []
    url = f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_KEY}"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if isinstance(data, list):
            return [{"headline": a.get("headline", ""),
                     "source":   a.get("source",   ""),
                     "url":      a.get("url",       "")}
                    for a in data[:8]]
    except Exception as e:
        print(f"⚠️  General news: {e}")
    return []