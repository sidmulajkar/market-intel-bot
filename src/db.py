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


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 8: MACRO ANCHOR SNAPSHOTS — For historical percentile + cross-asset
# ═══════════════════════════════════════════════════════════════════════════════

def save_macro_snapshot(date_str: str, symbol: str, name: str, price: float,
                        change_pct: float = None, weekly_change_pct: float = None) -> bool:
    """Save daily macro anchor value to Supabase for historical tracking."""
    db = get_client()
    if not db:
        return False
    try:
        db.table("macro_anchor_snapshots").upsert({
            "date":              date_str,
            "symbol":            symbol,
            "name":              name,
            "price":             price,
            "change_pct":        change_pct,
            "weekly_change_pct": weekly_change_pct,
            "created_at":        datetime.now().isoformat(),
        }).execute()
        return True
    except Exception as e:
        print(f"⚠️ save_macro_snapshot error: {e}")
        return False


def save_macro_snapshots_batch(anchor_data: list, date_str: str = None) -> int:
    """Save all macro anchor snapshots in batch. Returns count saved."""
    if not date_str:
        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")
    saved = 0
    for a in anchor_data:
        if a.get("ok") and a.get("price") is not None:
            if save_macro_snapshot(
                date_str, a["symbol"], a["name"], a["price"],
                a.get("change_pct"), a.get("weekly_change_pct")
            ):
                saved += 1
    return saved


def get_macro_history(symbol: str, days: int = 90) -> list:
    """Get historical macro anchor values for percentile computation."""
    db = get_client()
    if not db:
        return []
    try:
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        result = (
            db.table("macro_anchor_snapshots")
            .select("date, price, change_pct")
            .eq("symbol", symbol)
            .gte("date", cutoff)
            .order("date")
            .execute()
        )
        return result.data if result.data else []
    except Exception as e:
        print(f"⚠️ get_macro_history error: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 8: FII INSTITUTION TRACKER — SWF/Pension Fund Activity
# ═══════════════════════════════════════════════════════════════════════════════

def save_fii_institution(date_str: str, institution_name: str, institution_type: str,
                         country: str, signal_type: str, amount_cr: float = None,
                         details: str = None, source: str = None) -> bool:
    """Save FII institution activity to Supabase."""
    db = get_client()
    if not db:
        return False
    try:
        db.table("fii_institution_tracker").insert({
            "date":              date_str,
            "institution_name":  institution_name,
            "institution_type":  institution_type,
            "country":           country,
            "signal_type":       signal_type,
            "amount_cr":         amount_cr,
            "details":           details,
            "source":            source,
            "created_at":        datetime.now().isoformat(),
        }).execute()
        return True
    except Exception as e:
        print(f"⚠️ save_fii_institution error: {e}")
        return False


def get_fii_institutions(days: int = 180) -> list:
    """Get recent FII institution activity."""
    db = get_client()
    if not db:
        return []
    try:
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        result = (
            db.table("fii_institution_tracker")
            .select("*")
            .gte("date", cutoff)
            .order("date", desc=True)
            .execute()
        )
        return result.data if result.data else []
    except Exception as e:
        print(f"⚠️ get_fii_institutions error: {e}")
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
            "expires_at":    (datetime.now() + timedelta(days=124)).isoformat(),
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
        "predictions": 0, "outcomes": 0, "shareholding": 0,
        "errors": []
    }
    cutoff_alert    = (datetime.now() - timedelta(days=days_alert)).strftime("%Y-%m-%d")
    cutoff_snapshot = (datetime.now() - timedelta(days=days_snapshot)).strftime("%Y-%m-%d")
    cutoff_mf       = (datetime.now() - timedelta(days=124)).strftime("%Y-%m-%d")  # 4 months

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

    # ── MF flows: 4 months rolling (124 days) ──
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

    # ── Daily predictions: 90 days ──
    try:
        cutoff_predictions = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        resp = db.table("daily_predictions").delete().lt("date", cutoff_predictions).execute()
        results["predictions"] = len(resp.data) if resp.data else 0
    except Exception as e:
        results["errors"].append(f"daily_predictions: {e}")

    # ── Prediction outcomes: 90 days ──
    try:
        cutoff_outcomes = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        resp = db.table("prediction_outcomes").delete().lt("prediction_date", cutoff_outcomes).execute()
        results["outcomes"] = len(resp.data) if resp.data else 0
    except Exception as e:
        results["errors"].append(f"prediction_outcomes: {e}")

    # ── Macro anchor snapshots: 90 days ──
    try:
        cutoff_macro = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        resp = db.table("macro_anchor_snapshots").delete().lt("date", cutoff_macro).execute()
        results["macro_snapshots"] = len(resp.data) if resp.data else 0
    except Exception as e:
        results["errors"].append(f"macro_anchor_snapshots: {e}")

    # ── FII institution tracker: 180 days ──
    try:
        cutoff_fii_tracker = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
        resp = db.table("fii_institution_tracker").delete().lt("date", cutoff_fii_tracker).execute()
        results["fii_tracker"] = len(resp.data) if resp.data else 0
    except Exception as e:
        results["errors"].append(f"fii_institution_tracker: {e}")

    # ── Shareholding snapshots: 90 days ──
    try:
        cutoff_sh = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        resp = db.table("shareholding_snapshots").delete().lt("date", cutoff_sh).execute()
        results["shareholding"] = len(resp.data) if resp.data else 0
    except Exception as e:
        results["errors"].append(f"shareholding_snapshots: {e}")

    # ── Options snapshots: 7 days ──
    try:
        cutoff_options = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        resp = db.table("options_snapshots").delete().lt("date", cutoff_options).execute()
        results["options_snapshots"] = len(resp.data) if resp.data else 0
    except Exception as e:
        results["errors"].append(f"options_snapshots: {e}")

    # ── Daily market snapshot: 3 years ──
    try:
        cutoff_snapshot = (datetime.now() - timedelta(days=1095)).strftime("%Y-%m-%d")
        resp = db.table("daily_market_snapshot").delete().lt("date", cutoff_snapshot).execute()
        results["daily_snapshot"] = len(resp.data) if resp.data else 0
    except Exception as e:
        results["errors"].append(f"daily_market_snapshot: {e}")

    # ── Correlation matrix: 1 year ──
    try:
        cutoff_corr = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        resp = db.table("correlation_matrix").delete().lt("date", cutoff_corr).execute()
        results["correlation"] = len(resp.data) if resp.data else 0
    except Exception as e:
        results["errors"].append(f"correlation_matrix: {e}")

    # ── Signal accuracy log: 1 year ──
    try:
        cutoff_signal = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        resp = db.table("signal_accuracy_log").delete().lt("date", cutoff_signal).execute()
        results["signal_accuracy"] = len(resp.data) if resp.data else 0
    except Exception as e:
        results["errors"].append(f"signal_accuracy_log: {e}")

    # ── Divergence log: 90 days ──
    try:
        cutoff_div = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        resp = db.table("divergence_log").delete().lt("date", cutoff_div).execute()
        results["divergence"] = len(resp.data) if resp.data else 0
    except Exception as e:
        results["errors"].append(f"divergence_log: {e}")

    print(f"🧹 Purged: {results['sent_alerts']} alerts, {results['snapshots']} snapshots, "
          f"{results['analysis_cache']} cache, {results['fii_dii']} fii_dii, {results['mf_flows']} mf_flows, "
          f"{results.get('breadth', 0)} breadth, {results.get('valuation', 0)} valuation, "
          f"{results.get('predictions', 0)} predictions, {results.get('outcomes', 0)} outcomes, "
          f"{results.get('macro_snapshots', 0)} macro, {results.get('fii_tracker', 0)} fii_tracker, "
          f"{results.get('shareholding', 0)} shareholding, {results.get('daily_snapshot', 0)} daily_snapshot")
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 11: DAILY MARKET SNAPSHOT — Rolling Statistical Memory
# ═══════════════════════════════════════════════════════════════════════════════

def save_daily_market_snapshot(date_str: str, snapshot: dict) -> bool:
    """
    Save unified daily market snapshot for percentile ranking,
    scenario matching, correlations, and divergence detection.
    snapshot: dict with all metric values (see daily_market_snapshot schema).
    """
    db = get_client()
    if not db:
        return False
    try:
        record = {"date": date_str, "created_at": datetime.now().isoformat()}
        # Only store non-None values
        for key, val in snapshot.items():
            if val is not None:
                record[key] = val
        db.table("daily_market_snapshot").upsert(record).execute()
        return True
    except Exception as e:
        print(f"⚠️ save_daily_market_snapshot error: {e}")
        return False


def get_daily_market_snapshots(days: int = 252) -> list:
    """
    Get historical daily market snapshots for percentile computation.
    Default 252 days (1 trading year). Max 1095 (3 years).
    """
    db = get_client()
    if not db:
        return []
    try:
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        result = (
            db.table("daily_market_snapshot")
            .select("*")
            .gte("date", cutoff)
            .order("date")
            .execute()
        )
        return result.data if result.data else []
    except Exception as e:
        print(f"⚠️ get_daily_market_snapshots error: {e}")
        return []


def get_snapshot_metric_history(metric: str, days: int = 252) -> list:
    """
    Get a single metric's history from daily_market_snapshot.
    Returns list of (date, value) tuples, filtering out None values.
    """
    db = get_client()
    if not db:
        return []
    try:
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        result = (
            db.table("daily_market_snapshot")
            .select(f"date, {metric}")
            .gte("date", cutoff)
            .not_.is_(metric, "null")
            .order("date")
            .execute()
        )
        return [(r["date"], r[metric]) for r in (result.data or []) if r.get(metric) is not None]
    except Exception as e:
        print(f"⚠️ get_snapshot_metric_history({metric}) error: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 11: CORRELATION MATRIX — Rolling signal correlations
# ═══════════════════════════════════════════════════════════════════════════════

def save_correlation(date_str: str, pair_name: str, correlation: float,
                     p_value: float = None, sample_size: int = None,
                     window_days: int = 90) -> bool:
    """Save a computed correlation for weekly digest."""
    db = get_client()
    if not db:
        return False
    try:
        db.table("correlation_matrix").insert({
            "date": date_str,
            "window_days": window_days,
            "pair_name": pair_name,
            "correlation": round(correlation, 4),
            "p_value": round(p_value, 4) if p_value else None,
            "sample_size": sample_size,
            "created_at": datetime.now().isoformat(),
        }).execute()
        return True
    except Exception as e:
        print(f"⚠️ save_correlation error: {e}")
        return False


def get_correlations(date_str: str = None, days_back: int = 30) -> list:
    """Get recent correlation matrix entries."""
    db = get_client()
    if not db:
        return []
    try:
        from datetime import timedelta
        if date_str:
            cutoff = date_str
        else:
            cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        result = (
            db.table("correlation_matrix")
            .select("date, pair_name, correlation, p_value, sample_size")
            .gte("date", cutoff)
            .order("date", desc=True)
            .execute()
        )
        return result.data if result.data else []
    except Exception as e:
        print(f"⚠️ get_correlations error: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 11: SIGNAL ACCURACY LOG — Per-signal hit rates
# ═══════════════════════════════════════════════════════════════════════════════

def log_signal_accuracy(date_str: str, signal_name: str, signal_value: float,
                        predicted_direction: str, actual_direction: str,
                        hit: bool, nifty_return: float = None) -> bool:
    """Log a signal's prediction vs outcome for accuracy tracking."""
    db = get_client()
    if not db:
        return False
    try:
        db.table("signal_accuracy_log").insert({
            "date": date_str,
            "signal_name": signal_name,
            "signal_value": signal_value,
            "predicted_direction": predicted_direction,
            "actual_direction": actual_direction,
            "hit": hit,
            "nifty_return": nifty_return,
            "created_at": datetime.now().isoformat(),
        }).execute()
        return True
    except Exception as e:
        print(f"⚠️ log_signal_accuracy error: {e}")
        return False


def get_signal_accuracy(signal_name: str = None, days: int = 90) -> dict:
    """
    Get signal accuracy stats. If signal_name provided, return that signal's stats.
    Otherwise return all signals' stats.
    Returns: {signal_name: {hit_rate, total, hits, avg_return_when_hit}}
    """
    db = get_client()
    if not db:
        return {}
    try:
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        query = db.table("signal_accuracy_log").select("signal_name, hit, nifty_return, date").gte("date", cutoff)
        if signal_name:
            query = query.eq("signal_name", signal_name)
        result = query.execute()
        if not result.data:
            return {}

        # Group by signal name
        from collections import defaultdict
        stats = defaultdict(lambda: {"hits": 0, "total": 0, "returns_when_hit": []})
        for row in result.data:
            name = row["signal_name"]
            stats[name]["total"] += 1
            if row.get("hit"):
                stats[name]["hits"] += 1
            if row.get("nifty_return") is not None:
                stats[name]["returns_when_hit"].append(row["nifty_return"])

        # Compute hit rates
        output = {}
        for name, s in stats.items():
            output[name] = {
                "hit_rate": round((s["hits"] / s["total"]) * 100, 1) if s["total"] > 0 else 0,
                "total": s["total"],
                "hits": s["hits"],
                "misses": s["total"] - s["hits"],
            }
        return output
    except Exception as e:
        print(f"⚠️ get_signal_accuracy error: {e}")
        return {}


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 11: DIVERGENCE LOG — Active cross-asset divergences
# ═══════════════════════════════════════════════════════════════════════════════

def log_divergence(date_str: str, divergence_type: str, severity: str,
                   description: str, asset_1: str = None, asset_1_change: float = None,
                   asset_2: str = None, asset_2_change: float = None) -> bool:
    """Log a detected divergence for historical tracking."""
    db = get_client()
    if not db:
        return False
    try:
        db.table("divergence_log").insert({
            "date": date_str,
            "divergence_type": divergence_type,
            "severity": severity,
            "description": description,
            "asset_1": asset_1,
            "asset_1_change": asset_1_change,
            "asset_2": asset_2,
            "asset_2_change": asset_2_change,
            "created_at": datetime.now().isoformat(),
        }).execute()
        return True
    except Exception as e:
        print(f"⚠️ log_divergence error: {e}")
        return False


def get_recent_divergences(days: int = 7) -> list:
    """Get recent divergences for context."""
    db = get_client()
    if not db:
        return []
    try:
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        result = (
            db.table("divergence_log")
            .select("date, divergence_type, severity, description")
            .gte("date", cutoff)
            .order("date", desc=True)
            .execute()
        )
        return result.data if result.data else []
    except Exception as e:
        print(f"⚠️ get_recent_divergences error: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# BOT STATE — Generic key-value store for runtime state
# ═══════════════════════════════════════════════════════════════════════════════

def get_bot_state(key: str) -> str:
    """Get a value from bot_state table."""
    db = get_client()
    if not db:
        return None
    try:
        result = (
            db.table("bot_state")
            .select("value")
            .eq("key", key)
            .single()
            .execute()
        )
        return result.data["value"] if result.data else None
    except Exception:
        return None


def set_bot_state(key: str, value: str) -> bool:
    """Set a value in bot_state table."""
    db = get_client()
    if not db:
        return False
    try:
        db.table("bot_state").upsert({
            "key": key,
            "value": value,
            "updated_at": datetime.now().isoformat(),
        }).execute()
        return True
    except Exception as e:
        print(f"⚠️ set_bot_state({key}) error: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 12: STORAGE TABLES — Historical percentile enablement
# ═══════════════════════════════════════════════════════════════════════════════

def save_cftc_positioning(date_str: str, contract_name: str, data: dict) -> bool:
    """Save CFTC positioning data for historical percentile."""
    db = get_client()
    if not db:
        return False
    try:
        db.table("cftc_positioning_history").upsert({
            "date": date_str, "contract_name": contract_name,
            "speculator_net": data.get("speculator_net"),
            "commercial_net": data.get("commercial_net"),
            "open_interest": data.get("open_interest"),
            "speculator_percentile": data.get("speculator_percentile"),
            "trend": data.get("trend"),
            "created_at": datetime.now().isoformat(),
        }).execute()
        return True
    except Exception as e:
        print(f"⚠️ save_cftc_positioning error: {e}")
        return False


def save_factor_scores(date_str: str, scores: dict) -> bool:
    """Save daily factor attribution scores."""
    db = get_client()
    if not db:
        return False
    try:
        db.table("factor_scores_history").upsert({
            "date": date_str,
            "momentum_score": scores.get("momentum"),
            "value_score": scores.get("value"),
            "quality_score": scores.get("quality"),
            "size_score": scores.get("size"),
            "dominant_factor": scores.get("dominant"),
            "created_at": datetime.now().isoformat(),
        }).execute()
        return True
    except Exception as e:
        print(f"⚠️ save_factor_scores error: {e}")
        return False


def save_sector_rs(date_str: str, sectors: list) -> bool:
    """Save daily sector RS rankings."""
    db = get_client()
    if not db:
        return False
    try:
        records = []
        for s in sectors:
            records.append({
                "date": date_str, "sector_name": s.get("name"),
                "rs_score": s.get("rs_score"), "rs_1w": s.get("rs_1w"),
                "rs_1m": s.get("rs_1m"), "rs_3m": s.get("rs_3m"),
                "rank": s.get("rank"), "created_at": datetime.now().isoformat(),
            })
        db.table("sector_rs_history").upsert(records).execute()
        return True
    except Exception as e:
        print(f"⚠️ save_sector_rs error: {e}")
        return False


def save_earnings_surprise(ticker: str, earnings_date: str, data: dict) -> bool:
    """Save earnings surprise data."""
    db = get_client()
    if not db:
        return False
    try:
        db.table("earnings_surprises").upsert({
            "ticker": ticker, "earnings_date": earnings_date,
            "eps_actual": data.get("eps_actual"),
            "eps_estimate": data.get("eps_estimate"),
            "surprise_pct": data.get("surprise_pct"),
            "stock_move_1d": data.get("stock_move_1d"),
            "stock_move_5d": data.get("stock_move_5d"),
            "created_at": datetime.now().isoformat(),
        }).execute()
        return True
    except Exception as e:
        print(f"⚠️ save_earnings_surprise error: {e}")
        return False


def save_internals_snapshot(date_str: str, internals: dict) -> bool:
    """Save daily market internals composite score."""
    db = get_client()
    if not db:
        return False
    try:
        db.table("market_internals_history").upsert({
            "date": date_str,
            "composite_score": internals.get("composite_score"),
            "ad_score": internals.get("components", {}).get("ad_ratio", {}).get("score"),
            "high_low_score": internals.get("components", {}).get("high_low", {}).get("score"),
            "volume_score": internals.get("components", {}).get("volume_breadth", {}).get("score"),
            "ma_score": internals.get("components", {}).get("ma_breadth", {}).get("score"),
            "mcclellan_score": internals.get("components", {}).get("mcclellan", {}).get("score"),
            "classification": internals.get("classification"),
            "created_at": datetime.now().isoformat(),
        }).execute()
        return True
    except Exception as e:
        print(f"⚠️ save_internals_snapshot error: {e}")
        return False


def get_factor_history(days: int = 365) -> list:
    """Get historical factor scores for percentile computation."""
    db = get_client()
    if not db:
        return []
    try:
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        result = db.table("factor_scores_history").select("*").gte("date", cutoff).order("date").execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"⚠️ get_factor_history error: {e}")
        return []


def get_sector_rs_history(sector_name: str = None, days: int = 365) -> list:
    """Get historical sector RS for percentile computation."""
    db = get_client()
    if not db:
        return []
    try:
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        query = db.table("sector_rs_history").select("*").gte("date", cutoff)
        if sector_name:
            query = query.eq("sector_name", sector_name)
        result = query.order("date").execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"⚠️ get_sector_rs_history error: {e}")
        return []


# ── Phase 25: MarketState ──────────────────────────────────────────────────

def save_market_state(trade_date: str, state) -> bool:
    """
    Save MarketState Pydantic model to market_state table (JSONB).
    state: src.state.MarketState instance
    """
    db = get_client()
    if not db:
        return False
    try:
        data = state.to_dict() if hasattr(state, "to_dict") else state
        record = {"trade_date": trade_date, "state": data}
        db.table("market_state").upsert(record).execute()
        return True
    except Exception as e:
        print(f"⚠️ save_market_state error: {e}")
        return False


def get_market_state(trade_date: str):
    """
    Fetch MarketState from Supabase by date.
    Returns dict or None.
    """
    db = get_client()
    if not db:
        return None
    try:
        result = db.table("market_state").select("*").eq("trade_date", trade_date).limit(1).execute()
        if result.data:
            return result.data[0].get("state")
        return None
    except Exception as e:
        print(f"⚠️ get_market_state error: {e}")
        return None


def save_forecast_log(trade_date: str, forecast: dict, outcome: dict = None) -> bool:
    """Save AI forecast to forecast_log table."""
    db = get_client()
    if not db:
        return False
    try:
        record = {"trade_date": trade_date, "forecast": forecast}
        if outcome:
            record["outcome"] = outcome
            record["scored_at"] = datetime.now().isoformat()
        db.table("forecast_log").upsert(record).execute()
        return True
    except Exception as e:
        print(f"⚠️ save_forecast_log error: {e}")
        return False


def save_analytics_ledger(date_str: str, category: str, data: dict) -> bool:
    """Save to consolidated analytics_ledger table."""
    db = get_client()
    if not db:
        return False
    try:
        db.table("analytics_ledger").insert({
            "date": date_str,
            "category": category,
            "data": data,
        }).execute()
        return True
    except Exception as e:
        print(f"⚠️ save_analytics_ledger error: {e}")
        return False


# ── Phase 26: Delta Engine Support ─────────────────────────────────────────

_market_state_checked = False

def check_market_state_table() -> bool:
    """Check if market_state table exists on Supabase. Returns True if present.

    Warns once per session if the table is missing (Phase 26 features disabled).
    """
    global _market_state_checked
    if _market_state_checked:
        return getattr(check_market_state_table, '_result', True)
    _market_state_checked = True
    db = get_client()
    if not db:
        check_market_state_table._result = False
        return False
    try:
        result = db.table("market_state").select("id").limit(1).execute()
        check_market_state_table._result = True
        return True
    except Exception:
        print("⚠️ market_state table missing — delta/regime features disabled")
        print("   Run: sql/phase25_consolidation.sql on Supabase")
        check_market_state_table._result = False
        return False


def get_latest_market_state(before_date: str = None):
    """Fetch the most recent MarketState before a given date.

    Used by delta computation to compare current vs prior send.

    Args:
        before_date: YYYY-MM-DD. Defaults to today (excludes today).

    Returns:
        Dict of MarketState data, or None.
    """
    from datetime import datetime, timedelta
    db = get_client()
    if not db:
        return None
    try:
        if before_date is None:
            before_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        result = (
            db.table("market_state")
            .select("*")
            .lt("trade_date", before_date)
            .order("trade_date", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0].get("state")
        return None
    except Exception as e:
        print(f"⚠️ get_latest_market_state error: {e}")
        return None


def get_bot_state(key: str):
    """Fetch a single value from bot_state table.

    Used for news fingerprint and other persistent state.
    """
    db = get_client()
    if not db:
        return None
    try:
        result = db.table("bot_state").select("value").eq("key", key).limit(1).execute()
        if result.data:
            return result.data[0].get("value")
        return None
    except Exception as e:
        print(f"⚠️ get_bot_state error: {e}")
        return None


def set_bot_state(key: str, value: str) -> bool:
    """Upsert a value into bot_state table.

    Used for news fingerprint persistence.
    """
    db = get_client()
    if not db:
        return False
    try:
        db.table("bot_state").upsert({
            "key": key,
            "value": value,
            "updated_at": datetime.now().isoformat(),
        }).execute()
        return True
    except Exception as e:
        print(f"⚠️ set_bot_state error: {e}")
        return False