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