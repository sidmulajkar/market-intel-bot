"""
Database Layer — Complete CRUD for dynamic watchlist
All operations use Supabase free tier
"""
import os
import json
from datetime import datetime
from typing import Optional, Dict, List

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

_client = None

def get_client():
    """Lazy initialise Supabase client"""
    global _client
    if _client is not None:
        return _client
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("⚠️  Supabase env vars not set — DB features disabled")
        return None
    try:
        from supabase import create_client
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
        return _client
    except Exception as e:
        print(f"⚠️  Supabase init failed: {e}")
        return None

def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")

# ══════════════════════════════════════════════════════════════
# WATCHLIST CRUD
# ══════════════════════════════════════════════════════════════

def get_watchlist() -> List[str]:
    """
    Get watchlist symbols from Supabase.
    Falls back to config/watchlist.json if DB unavailable or empty.
    """
    db = get_client()
    if db:
        try:
            result = (
                db.table("watchlist")
                .select("symbol")
                .order("added_at")
                .execute()
            )
            if result.data:
                return [row["symbol"] for row in result.data]
        except Exception as e:
            print(f"⚠️  DB get_watchlist error: {e}")

    # Fallback to config file
    print("📋 Using config/watchlist.json fallback")
    try:
        with open("config/watchlist.json") as f:
            config = json.load(f)
        return config.get("stocks", [])
    except Exception:
        return []

def add_to_watchlist(
    symbol: str,
    company_name: str = "",
    exchange: str = "",
) -> Dict:
    """
    Add a stock symbol to the watchlist.
    Returns: {"success": True/False, "message": str}
    """
    db = get_client()
    if not db:
        return {"success": False, "message": "Database unavailable"}
    try:
        # Check if already exists
        existing = (
            db.table("watchlist")
            .select("symbol")
            .eq("symbol", symbol)
            .execute()
        )
        if existing.data:
            return {
                "success": False,
                "message": f"⚠️ {symbol} is already in your watchlist"
            }

        db.table("watchlist").insert({
            "symbol":       symbol,
            "company_name": company_name,
            "exchange":     exchange,
            "added_by":     "telegram",
        }).execute()

        return {
            "success": True,
            "message": f"✅ *{symbol}* added to watchlist!"
                       + (f"\n_{company_name}_" if company_name else "")
        }
    except Exception as e:
        return {"success": False, "message": f"❌ Error: {str(e)}"}

def remove_from_watchlist(symbol: str) -> Dict:
    """Remove a stock symbol from watchlist"""
    db = get_client()
    if not db:
        return {"success": False, "message": "Database unavailable"}
    try:
        result = (
            db.table("watchlist")
            .delete()
            .eq("symbol", symbol)
            .execute()
        )
        if result.data:
            return {
                "success": True,
                "message": f"🗑️ *{symbol}* removed from watchlist"
            }
        else:
            return {
                "success": False,
                "message": f"⚠️ {symbol} was not in your watchlist"
            }
    except Exception as e:
        return {"success": False, "message": f"❌ Error: {str(e)}"}

def list_watchlist() -> str:
    """Return formatted watchlist for Telegram"""
    db = get_client()
    if not db:
        return "❌ Database unavailable"
    try:
        result = (
            db.table("watchlist")
            .select("symbol, company_name, exchange, added_at")
            .order("added_at")
            .execute()
        )
        if not result.data:
            return "📋 Your watchlist is empty\n_Use /add SYMBOL to add stocks_"

        lines = ["📋 *YOUR WATCHLIST*\n━━━━━━━━━━━━━━━━━━━━━━━━\n"]
        for i, row in enumerate(result.data, 1):
            sym  = row["symbol"]
            name = row.get("company_name", "")
            exch = row.get("exchange", "")
            name_str = f" — _{name}_" if name else ""
            exch_str = f" `{exch}`"   if exch else ""
            lines.append(f"{i}. *{sym}*{name_str}{exch_str}")

        lines.append(
            f"\n_Total: {len(result.data)} stocks_\n"
            "_/add SYMBOL | /remove SYMBOL_"
        )
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error: {str(e)}"

# ══════════════════════════════════════════════════════════════
# MF WATCHLIST CRUD
# ══════════════════════════════════════════════════════════════

def get_mf_watchlist() -> List[Dict]:
    """
    Get MF scheme list from Supabase.
    Falls back to config/mf_watchlist.json if empty.
    """
    db = get_client()
    if db:
        try:
            result = (
                db.table("mf_watchlist")
                .select("scheme_code, scheme_name, fund_house, category")
                .order("added_at")
                .execute()
            )
            if result.data:
                return result.data
        except Exception as e:
            print(f"⚠️  DB get_mf_watchlist error: {e}")

    # Fallback to config file
    print("📋 Using config/mf_watchlist.json fallback")
    try:
        with open("config/mf_watchlist.json") as f:
            config = json.load(f)
        codes = config.get("scheme_codes", [])
        names = config.get("scheme_names", {})
        return [
            {"scheme_code": c, "scheme_name": names.get(c, c),
             "fund_house": "", "category": ""}
            for c in codes
        ]
    except Exception:
        return []

def get_mf_scheme_codes() -> List[str]:
    """Returns just the list of scheme codes"""
    return [s["scheme_code"] for s in get_mf_watchlist()]

def add_mf_scheme(
    scheme_code: str,
    scheme_name: str,
    fund_house:  str = "",
    category:    str = "",
) -> Dict:
    """Add MF scheme to watchlist"""
    db = get_client()
    if not db:
        return {"success": False, "message": "Database unavailable"}
    try:
        existing = (
            db.table("mf_watchlist")
            .select("scheme_code")
            .eq("scheme_code", scheme_code)
            .execute()
        )
        if existing.data:
            return {
                "success": False,
                "message": (
                    f"⚠️ Scheme {scheme_code} already in MF watchlist\n"
                    f"_{scheme_name}_"
                )
            }

        db.table("mf_watchlist").insert({
            "scheme_code": scheme_code,
            "scheme_name": scheme_name,
            "fund_house":  fund_house,
            "category":    category,
        }).execute()

        return {
            "success": True,
            "message": (
                f"✅ MF scheme added!\n"
                f"*{scheme_name}*\n"
                f"Code: `{scheme_code}`"
                + (f" | {fund_house}" if fund_house else "")
                + (f" | _{category}_" if category else "")
            )
        }
    except Exception as e:
        return {"success": False, "message": f"❌ Error: {str(e)}"}

def remove_mf_scheme(scheme_code: str) -> Dict:
    """Remove MF scheme from watchlist"""
    db = get_client()
    if not db:
        return {"success": False, "message": "Database unavailable"}
    try:
        result = (
            db.table("mf_watchlist")
            .delete()
            .eq("scheme_code", scheme_code)
            .execute()
        )
        if result.data:
            name = result.data[0].get("scheme_name", scheme_code)
            return {
                "success": True,
                "message": f"🗑️ *{name}* removed from MF watchlist"
            }
        else:
            return {
                "success": False,
                "message": f"⚠️ Scheme `{scheme_code}` not in MF watchlist"
            }
    except Exception as e:
        return {"success": False, "message": f"❌ Error: {str(e)}"}

def list_mf_watchlist() -> str:
    """Return formatted MF watchlist for Telegram"""
    schemes = get_mf_watchlist()
    if not schemes:
        return (
            "💹 Your MF watchlist is empty\n"
            "_Use /addmf CODE to add schemes_\n"
            "_Use /searchmf NAME to find schemes_"
        )

    lines = ["💹 *YOUR MF WATCHLIST*\n━━━━━━━━━━━━━━━━━━━━━━━━\n"]
    for i, s in enumerate(schemes, 1):
        cat  = f" _{s.get('category', '')}_"   if s.get("category") else ""
        house = f" | {s.get('fund_house', '')}" if s.get("fund_house") else ""
        lines.append(
            f"{i}. *{s['scheme_name'][:40]}*\n"
            f"   Code: `{s['scheme_code']}`{house}{cat}"
        )

    lines.append(
        f"\n_Total: {len(schemes)} schemes_\n"
        "_/addmf CODE | /removemf CODE | /searchmf NAME_"
    )
    return "\n".join(lines)

# ══════════════════════════════════════════════════════════════
# BOT STATE (tracks last processed Telegram update_id)
# ══════════════════════════════════════════════════════════════

def get_last_update_id() -> int:
    """Get last processed Telegram update_id from Supabase"""
    db = get_client()
    if not db:
        return 0
    try:
        result = (
            db.table("bot_state")
            .select("value")
            .eq("key", "last_update_id")
            .single()
            .execute()
        )
        if result.data:
            return int(result.data["value"])
    except Exception as e:
        print(f"⚠️  get_last_update_id error: {e}")
    return 0

def save_last_update_id(update_id: int) -> None:
    """Save last processed update_id to prevent duplicate processing"""
    db = get_client()
    if not db:
        return
    try:
        db.table("bot_state").upsert({
            "key":        "last_update_id",
            "value":      str(update_id),
            "updated_at": datetime.now().isoformat(),
        }).execute()
    except Exception as e:
        print(f"⚠️  save_last_update_id error: {e}")

# ══════════════════════════════════════════════════════════════
# ALERT DEDUPLICATION (existing functions — unchanged)
# ══════════════════════════════════════════════════════════════

def was_alert_sent(symbol: str, alert_type: str) -> bool:
    db = get_client()
    if not db:
        return False
    try:
        result = (
            db.table("sent_alerts")
            .select("id")
            .eq("symbol",     symbol)
            .eq("alert_type", alert_type)
            .eq("date",       today_str())
            .execute()
        )
        return len(result.data) > 0
    except Exception as e:
        print(f"⚠️  was_alert_sent error: {e}")
        return False

def log_alert_sent(
    symbol: str,
    alert_type: str,
    message: str = "",
) -> None:
    db = get_client()
    if not db:
        return
    try:
        db.table("sent_alerts").insert({
            "symbol":     symbol,
            "alert_type": alert_type,
            "date":       today_str(),
            "message":    message[:500],
        }).execute()
    except Exception as e:
        print(f"⚠️  log_alert_sent error: {e}")

# ══════════════════════════════════════════════════════════════
# MARKET SNAPSHOTS (existing — unchanged)
# ══════════════════════════════════════════════════════════════

def save_daily_snapshot(data: dict) -> None:
    db = get_client()
    if not db:
        return
    try:
        safe_data = {
            k: {
                "price":      v.get("price"),
                "change_pct": v.get("change_pct"),
                "status":     v.get("status"),
                "region":     v.get("region"),
            }
            for k, v in data.items() if v.get("ok")
        }
        db.table("market_snapshots").insert({
            "date": today_str(),
            "data": safe_data,
        }).execute()
        print("✅ Snapshot saved to Supabase")
    except Exception as e:
        print(f"⚠️  save_daily_snapshot error: {e}")

def get_yesterday_snapshot() -> Optional[Dict]:
    db = get_client()
    if not db:
        return None
    try:
        from datetime import timedelta
        yesterday = (
            datetime.now() - timedelta(days=1)
        ).strftime("%Y-%m-%d")
        result = (
            db.table("market_snapshots")
            .select("data")
            .eq("date", yesterday)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]["data"]
    except Exception as e:
        print(f"⚠️  get_yesterday_snapshot error: {e}")
    return None

# ══════════════════════════════════════════════════════════════
# FII/DII FLOWS (Daily NSE data)
# ══════════════════════════════════════════════════════════════

def save_fii_dii_flow(date: str, fiinet_cr: float, diinet_cr: float, source: str = "NSE") -> bool:
    """
    Save daily FII/DII flow data.
    date: YYYY-MM-DD (trading day)
    """
    from datetime import timedelta
    
    db = get_client()
    if not db:
        return False
    try:
        net_cr = fiinet_cr + diinet_cr
        # Upsert by date (replace if exists)
        db.table("fii_dii_flows").upsert({
            "date":       date,
            "fiinet_cr":  fiinet_cr,
            "diinet_cr":  diinet_cr,
            "net_cr":     net_cr,
            "source":     source,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(days=90)).isoformat(),
        }).execute()
        return True
    except Exception as e:
        print(f"⚠️ save_fii_dii_flow error: {e}")
        return False


def get_fii_dii_flows(days: int = 45) -> list:
    """
    Get recent FII/DII flows for formatter.
    Returns list of dicts with date, fiinet_cr, diinet_cr, net_cr.
    """
    db = get_client()
    if not db:
        return []
    try:
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        result = (
            db.table("fii_dii_flows")
            .select("date, fiinet_cr, diinet_cr, net_cr")
            .gte("date", cutoff)
            .order("date")
            .execute()
        )
        return result.data if result.data else []
    except Exception as e:
        print(f"⚠️ get_fii_dii_flows error: {e}")
        return []


# ══════════════════════════════════════════════════════════════
# VALUATION HISTORY (Daily P/E, P/B, DY for percentile)
# ══════════════════════════════════════════════════════════════

def save_valuation_snapshot(date_str: str, index_name: str, pe: float,
                             pb: float = None, div_yield: float = None,
                             earnings_yield: float = None) -> bool:
    """Save daily valuation snapshot to Supabase."""
    db = get_client()
    if not db:
        return False
    try:
        db.table("valuation_history").upsert({
            "date":           date_str,
            "index_name":     index_name,
            "pe":             pe,
            "pb":             pb,
            "div_yield":      div_yield,
            "earnings_yield": earnings_yield,
            "created_at":     datetime.now().isoformat(),
        }).execute()
        return True
    except Exception as e:
        print(f"⚠️ save_valuation_snapshot error: {e}")
        return False


def get_valuation_history(index_name: str = "NIFTY 50", days: int = 1095) -> list:
    """Get historical valuation data for percentile computation. Default 3 years."""
    db = get_client()
    if not db:
        return []
    try:
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        result = (
            db.table("valuation_history")
            .select("date, pe, pb, div_yield, earnings_yield")
            .eq("index_name", index_name)
            .gte("date", cutoff)
            .order("date")
            .execute()
        )
        return result.data if result.data else []
    except Exception as e:
        print(f"⚠️ get_valuation_history error: {e}")
        return []


# ══════════════════════════════════════════════════════════════
# MARKET BREADTH HISTORY (Daily A/D ratios for percentile)
# ══════════════════════════════════════════════════════════════

def save_breadth_snapshot(date_str: str, advances: int, declines: int, ratio: float) -> bool:
    """Save daily market breadth snapshot to Supabase."""
    db = get_client()
    if not db:
        return False
    try:
        db.table("market_breadth_history").upsert({
            "date":      date_str,
            "advances":  advances,
            "declines":  declines,
            "ratio":     ratio,
            "created_at": datetime.now().isoformat(),
        }).execute()
        return True
    except Exception as e:
        print(f"⚠️ save_breadth_snapshot error: {e}")
        return False


def get_breadth_history(days: int = 90) -> list:
    """Get historical breadth ratios for percentile computation."""
    db = get_client()
    if not db:
        return []
    try:
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        result = (
            db.table("market_breadth_history")
            .select("date, ratio")
            .gte("date", cutoff)
            .order("date")
            .execute()
        )
        return result.data if result.data else []
    except Exception as e:
        print(f"⚠️ get_breadth_history error: {e}")
        return []


# ══════════════════════════════════════════════════════════════
# MF FLOWS (Monthly AMFI category data)
# ══════════════════════════════════════════════════════════════

def save_mf_flows(month: str, category: str, amount_cr: float, sip_amount_cr: float = None) -> bool:
    """
    Save monthly MF category flow data.
    month: YYYY-MM-01 (first day of month)
    """
    from datetime import timedelta
    
    db = get_client()
    if not db:
        return False
    try:
        db.table("mf_flows").upsert({
            "month":         month,
            "category":      category,
            "amount_cr":     amount_cr,
            "sip_amount_cr": sip_amount_cr,
            "source":        "AMFI",
            "created_at":    datetime.now().isoformat(),
            "expires_at":    (datetime.now() + timedelta(days=70)).isoformat(),
        }).execute()
        return True
    except Exception as e:
        print(f"⚠️ save_mf_flows error: {e}")
        return False


def get_mf_flows(months: int = 4) -> list:
    """
    Get recent MF flows for formatter.
    Returns list of dicts with month, category, amount_cr, sip_amount_cr.
    """
    db = get_client()
    if not db:
        return []
    try:
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=months * 35)).strftime("%Y-%m-%d")
        result = (
            db.table("mf_flows")
            .select("month, category, amount_cr, sip_amount_cr")
            .gte("month", cutoff)
            .order("month")
            .execute()
        )
        return result.data if result.data else []
    except Exception as e:
        print(f"⚠️ get_mf_flows error: {e}")
        return []


def get_mf_flows_dict(months: int = 4) -> dict:
    """
    Get MF flows grouped by month.
    Returns: {"2026-04-01": [{category, amount_cr}, ...], ...}
    """
    rows = get_mf_flows(months=months)
    grouped = {}
    for row in rows:
        month = row.get("month", "")[:10]
        if month:
            grouped.setdefault(month, []).append(row)
    return grouped


# ══════════════════════════════════════════════════════════════
# DATA PURGE (cleanup old data to prevent DB bloat)
# ══════════════════════════════════════════════════════════════

def purge_old_data(days_alert: int = 30, days_snapshot: int = 90) -> dict:
    """
    Delete old data from tables to prevent unbounded growth.
    Called once per trading day from morning_brief.py
    Returns: {"sent_alerts": X, "snapshots": Y, "analysis_cache": Z, "fii_dii": A, "mf_flows": B, "errors": []}
    """
    from datetime import timedelta
    import pandas as pd

    db = get_client()
    if not db:
        return {"sent_alerts": 0, "snapshots": 0, "analysis_cache": 0,
                "fii_dii": 0, "mf_flows": 0, "errors": ["DB unavailable"]}

    results = {
        "sent_alerts": 0, "snapshots": 0, "analysis_cache": 0,
        "fii_dii": 0, "mf_flows": 0, "breadth": 0, "valuation": 0,
        "errors": []
    }
    cutoff_alert    = (datetime.now() - timedelta(days=days_alert)).strftime("%Y-%m-%d")
    cutoff_snapshot = (datetime.now() - timedelta(days=days_snapshot)).strftime("%Y-%m-%d")
    cutoff_mf       = (datetime.now() - timedelta(days=62)).strftime("%Y-%m-%d")  # 2 months

    # Delete old sent_alerts
    try:
        resp = db.table("sent_alerts").delete().lt("date", cutoff_alert).execute()
        results["sent_alerts"] = len(resp.data) if resp.data else 0
    except Exception as e:
        results["errors"].append(f"sent_alerts: {e}")

    # Delete old market_snapshots
    try:
        resp = db.table("market_snapshots").delete().lt("date", cutoff_snapshot).execute()
        results["snapshots"] = len(resp.data) if resp.data else 0
    except Exception as e:
        results["errors"].append(f"snapshots: {e}")

    # Delete expired analysis_cache
    try:
        resp = db.table("analysis_cache").delete().lt("expires_at", datetime.now().isoformat()).execute()
        results["analysis_cache"] = len(resp.data) if resp.data else 0
    except Exception as e:
        results["errors"].append(f"analysis_cache: {e}")

    # ── FII/DII flows: trading-day-aware purge (61 trading days) ──
    try:
        if datetime.now().weekday() >= 5:
            pass  # Weekend — skip purge
        else:
            # Get all dates in fii_dii_flows sorted ascending
            result = db.table("fii_dii_flows").select("date").order("date").execute()
            if result.data and len(result.data) >= 62:
                dates = [r["date"] for r in result.data]
                cutoff_date = dates[-61]  # 61st trading day from oldest
                resp = db.table("fii_dii_flows").delete().lt("date", cutoff_date).execute()
                results["fii_dii"] = len(resp.data) if resp.data else 0
    except Exception as e:
        results["errors"].append(f"fii_dii_flows: {e}")

    # ── MF flows: 2 months rolling ──
    try:
        resp = db.table("mf_flows").delete().lt("month", cutoff_mf).execute()
        results["mf_flows"] = len(resp.data) if resp.data else 0
    except Exception as e:
        results["errors"].append(f"mf_flows: {e}")

    # ── Market breadth history: 90 days ──
    try:
        cutoff_breadth = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        resp = db.table("market_breadth_history").delete().lt("date", cutoff_breadth).execute()
        results["breadth"] = len(resp.data) if resp.data else 0
    except Exception as e:
        results["errors"].append(f"breadth_history: {e}")

    # ── Valuation history: 3 years (1095 days) ──
    try:
        cutoff_valuation = (datetime.now() - timedelta(days=1095)).strftime("%Y-%m-%d")
        resp = db.table("valuation_history").delete().lt("date", cutoff_valuation).execute()
        results["valuation"] = len(resp.data) if resp.data else 0
    except Exception as e:
        results["errors"].append(f"valuation_history: {e}")

    print(f"🧹 Purged: {results['sent_alerts']} alerts, {results['snapshots']} snapshots, "
          f"{results['analysis_cache']} cache, {results['fii_dii']} fii_dii, {results['mf_flows']} mf_flows, "
          f"{results.get('breadth', 0)} breadth, {results.get('valuation', 0)} valuation")
    return results