"""
Corporate Actions Tracker (T3.2)
Fetches dividend/bonus/split/buyback for watchlist + Nifty 50.
Uses NSE corporate-info API per symbol, filters for next 5 sessions.
"""
import json
import os
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

# Nifty 50 symbols (static — rarely changes)
NIFTY_50 = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR", "ITC",
    "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "WIPRO", "AXISBANK", "BAJFINANCE",
    "MARUTI", "TITAN", "SUNPHARMA", "TATAMOTORS", "HCLTECH", "ASIANPAINT",
    "NTPC", "ULTRACEMCO", "ONGC", "M&M", "POWERGRID", "NESTLEIND", "JSWSTEEL",
    "BAJAJFINSV", "TATASTEEL", "HDFCLIFE", "TECHM", "SBILIFE", "DRREDDY",
    "CIPLA", "BAJAJ-AUTO", "HAL", "BRITANNIA", "APOLLOHOSP", "COALINDIA",
    "EICHERMOT", "DLF", "GRASIM", "ADANIPORTS", "BPCL", "INDUSINDBK",
    "HEROMOTOCO", "TRENT", "SHRIRAMFIN", "BEL", "ADANIENT",
]


def _load_watchlist_symbols() -> List[str]:
    """Load symbols from watchlist JSON (config/watchlist.json)."""
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "watchlist.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            data = json.load(f)
        stocks = data.get("stocks", [])
        return [s.replace(".NS", "") for s in stocks]
    except Exception:
        return []


def _get_target_symbols() -> List[str]:
    """Combine watchlist + Nifty 50, deduplicate."""
    wl = _load_watchlist_symbols()
    seen = set()
    result = []
    for sym in wl + NIFTY_50:
        s = sym.upper().replace(".NS", "")
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result


def fetch_corporate_actions_nse(symbols: Optional[List[str]] = None) -> Dict:
    """
    Fetch corporate actions for given symbols via NSE corp-info API.
    Returns dict keyed by symbol with list of actions (dividend/bonus/split/buyback).
    """
    if symbols is None:
        symbols = _get_target_symbols()

    import requests

    results = {}
    total = len(symbols)
    session = requests.Session()
    session.get("https://www.nseindia.com", headers=NSE_HEADERS, timeout=10)

    for i, sym in enumerate(symbols):
        if i % 20 == 0 and i > 0:
            print(f"   → Corp actions: {i}/{total}")
        try:
            url = f"https://www.nseindia.com/api/corp-info?symbol={sym}"
            resp = session.get(url, headers=NSE_HEADERS, timeout=15)
            if resp.status_code != 200:
                continue
            data = resp.json()
            actions = _parse_corp_info(sym, data)
            if actions:
                results[sym] = actions
            time.sleep(0.15)
        except Exception:
            continue

    return {"ok": True, "actions": results, "total_symbols": total}


def _parse_corp_info(symbol: str, data: Dict) -> List[Dict]:
    """Parse corporate actions from NSE corp-info response."""
    actions = []
    now = datetime.now()
    cutoff = now + timedelta(days=30)

    corp_info = data.get("corpInfo", []) if isinstance(data, dict) else []
    if not corp_info:
        return actions

    for item in corp_info:
        if not isinstance(item, dict):
            continue
        action_type = (item.get("action") or "").lower()
        ex_date_str = item.get("exDate") or item.get("ex_date") or ""
        if not ex_date_str or not action_type:
            continue
        try:
            ex_date = datetime.strptime(ex_date_str, "%d-%b-%Y")
        except ValueError:
            try:
                ex_date = datetime.strptime(ex_date_str, "%Y-%m-%d")
            except ValueError:
                continue
        if ex_date < now or ex_date > cutoff:
            continue

        purpose = item.get("purpose") or item.get("desc") or ""
        detail = item.get("detail") or item.get("remarks") or ""

        if "dividend" in action_type or "div" in action_type:
            amount = _extract_amount(purpose + " " + detail)
            actions.append({
                "symbol": symbol,
                "ex_date": ex_date_str,
                "action_type": "DIVIDEND",
                "detail": f"₹{amount:.2f}" if amount else purpose,
            })
        elif "bonus" in action_type:
            ratio = _extract_ratio(purpose + " " + detail)
            actions.append({
                "symbol": symbol,
                "ex_date": ex_date_str,
                "action_type": "BONUS",
                "detail": ratio or purpose,
            })
        elif "split" in action_type:
            ratio = _extract_ratio(purpose + " " + detail)
            actions.append({
                "symbol": symbol,
                "ex_date": ex_date_str,
                "action_type": "SPLIT",
                "detail": ratio or purpose,
            })
        elif "buyback" in action_type:
            actions.append({
                "symbol": symbol,
                "ex_date": ex_date_str,
                "action_type": "BUYBACK",
                "detail": purpose,
            })

    return actions


def _extract_amount(text: str) -> Optional[float]:
    """Extract rupee amount from text like 'Rs. 21.00 per share'."""
    m = re.search(r'(?:Rs\.?|₹)\s*([\d,]+\.?\d*)', text)
    if m:
        return float(m.group(1).replace(",", ""))
    m = re.search(r'(\d+\.?\d*)\s*(?:per share|%|rs)', text, re.I)
    if m:
        return float(m.group(1))
    return None


def _extract_ratio(text: str) -> Optional[str]:
    """Extract ratio like '1:2' or '10:1' from text."""
    m = re.search(r'(\d+\s*:\s*\d+)', text)
    if m:
        return m.group(1).replace(" ", "")
    return None


def format_corporate_actions(results: Dict) -> str:
    """Format corporate actions for output (next 5 sessions only)."""
    if not results.get("ok") or not results.get("actions"):
        return ""

    today = datetime.now()
    cutoff_5d = today + timedelta(days=7)
    lines = []
    all_actions = []

    for sym, sym_actions in results["actions"].items():
        for act in sym_actions:
            try:
                ex_date = datetime.strptime(act["ex_date"], "%d-%b-%Y")
            except ValueError:
                try:
                    ex_date = datetime.strptime(act["ex_date"], "%Y-%m-%d")
                except ValueError:
                    continue
            if today <= ex_date <= cutoff_5d:
                all_actions.append((ex_date, sym, act))

    if not all_actions:
        return ""

    all_actions.sort(key=lambda x: x[0])
    lines.append("📅 Corporate Actions (Next 7D)")
    for ex_date, sym, act in all_actions:
        label = ex_date.strftime("%d-%b")
        if act["action_type"] == "DIVIDEND":
            lines.append(f"🔵 {label}: {sym} Ex-Dividend ({act['detail']})")
        elif act["action_type"] == "BONUS":
            lines.append(f"🟢 {label}: {sym} Ex-Bonus ({act['detail']})")
        elif act["action_type"] == "SPLIT":
            lines.append(f"🟣 {label}: {sym} Split ({act['detail']})")
        elif act["action_type"] == "BUYBACK":
            lines.append(f"🟠 {label}: {sym} Buyback ({act['detail']})")

    return "\n".join(lines)


def save_corporate_actions(actions: Dict) -> bool:
    """Persist corporate actions to Supabase corporate_actions table."""
    if not actions.get("ok") or not actions.get("actions"):
        return False
    try:
        from supabase import create_client
        supabase_url = os.environ.get("SUPABASE_URL", "")
        supabase_key = os.environ.get("SUPABASE_KEY", "")
        if not supabase_url or not supabase_key:
            return False
        client = create_client(supabase_url, supabase_key)
        now_str = datetime.now().strftime("%Y-%m-%d")
        for sym, sym_actions in actions["actions"].items():
            for act in sym_actions:
                record = {
                    "symbol": sym,
                    "ex_date": act["ex_date"],
                    "action_type": act["action_type"],
                    "detail": act["detail"],
                    "fetched_date": now_str,
                }
                client.table("corporate_actions").upsert(
                    record,
                    on_conflict="symbol,ex_date,action_type",
                ).execute()
        print(f"   → Saved corp actions to Supabase")
        return True
    except Exception as e:
        print(f"   ⚠️ Save corp actions: {e}")
        return False


def fetch_cached_actions(days: int = 7) -> Dict:
    """Read watchlist corporate actions from Supabase cache (populated Sunday)."""
    try:
        from supabase import create_client
        supabase_url = os.environ.get("SUPABASE_URL", "")
        supabase_key = os.environ.get("SUPABASE_KEY", "")
        if not supabase_url or not supabase_key:
            return {"ok": False, "actions": {}}
        client = create_client(supabase_url, supabase_key)
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        resp = client.table("corporate_actions").select("*").gte("fetched_date", cutoff).execute()
        rows = resp.data or []
        if not rows:
            return {"ok": False, "actions": {}}
        actions = {}
        for r in rows:
            sym = r["symbol"]
            if sym not in actions:
                actions[sym] = []
            actions[sym].append({
                "symbol": sym,
                "ex_date": r["ex_date"],
                "action_type": r["action_type"],
                "detail": r.get("detail", ""),
            })
        return {"ok": True, "actions": actions, "source": "cache"}
    except Exception as e:
        print(f"   ⚠️ Cache read: {e}")
        return {"ok": False, "actions": {}}


def merge_corporate_actions(live: Dict, cached: Dict) -> Dict:
    """Merge live Nifty 50 fetch with cached watchlist actions. Live takes precedence."""
    merged = {"ok": True, "actions": dict(live.get("actions", {}))}
    for sym, sym_actions in cached.get("actions", {}).items():
        if sym not in merged["actions"]:
            merged["actions"][sym] = sym_actions
    return merged


if __name__ == "__main__":
    result = fetch_corporate_actions_nse()
    print(format_corporate_actions(result))
