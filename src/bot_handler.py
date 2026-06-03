"""
Telegram Bot Command Processor
Polls Telegram getUpdates API for new commands.
Processes commands and updates Supabase watchlists.
Uses offset stored in Supabase to avoid duplicate processing.

SUPPORTED COMMANDS:
  /start          — Welcome message + help
  /help           — Full command list
  /add SYMBOL     — Add stock to watchlist
  /remove SYMBOL  — Remove stock from watchlist
  /list           — Show current watchlist
  /addmf CODE     — Add MF scheme by AMFI code
  /removemf CODE  — Remove MF scheme
  /listmf         — Show MF watchlist
  /searchmf NAME  — Search AMFI for MF scheme by name
  /status         — Show bot status + DB health
"""
import os
import time
import requests
import yfinance as yf
from typing import List, Dict, Optional, Tuple

from src.db import (
    get_last_update_id,
    save_last_update_id,
    add_to_watchlist,
    remove_from_watchlist,
    list_watchlist,
    add_mf_scheme,
    remove_mf_scheme,
    list_mf_watchlist,
    get_watchlist,
    get_mf_watchlist,
    get_fii_dii_flows,
    get_sector_rs_history,
    get_client,
)
from src.stress_index import compute_stress_index, get_stress_history
from src.consequence_engine import compute_consequence, CONSEQUENCE_MULTIPLIERS
from src.options_engine import get_latest_snapshot

TOKEN   = os.environ.get("TELEGRAM_TOKEN",  "")
CHAT_ID = str(os.environ.get("TELEGRAM_CHAT_ID", ""))
BASE    = f"https://api.telegram.org/bot{TOKEN}"

# ── HELP TEXT ─────────────────────────────────────────────────────
HELP_TEXT = """
🤖 *Market Intel Bot — Commands*
━━━━━━━━━━━━━━━━━━━━━━━━

📈 *STOCK WATCHLIST:*
`/add RELIANCE.NS` — Add NSE stock
`/add AAPL` — Add US stock
`/remove RELIANCE.NS` — Remove stock
`/list` — Show all watchlist stocks

💹 *MUTUAL FUND WATCHLIST:*
`/addmf 119598` — Add MF by AMFI code
`/removemf 119598` — Remove MF scheme
`/listmf` — Show all MF schemes
`/searchmf bluechip` — Search MF by name

📊 *MARKET INTEL:*
`/stress` — Composite stress index + top drivers
`/clone` — Historical macro clones + forward returns
`/flows` — FII/DII net flows + velocity
`/gex` — Options GEX levels + max pain + PCR
`/sectors` — Sector RS leaders + laggards
`/whatif brent 100` — Consequence simulation for any variable
`/simulate brent 120` — Full pipeline simulation (pillars + fragility + regime)
`/compare 2013-08-15` — Side-by-side macro comparison with any date
`/query what is FII doing?` — Natural language query against deterministic data

ℹ️ *INFO:*
`/status` — Bot health check
`/help` — This message

📌 *SYMBOL FORMATS:*
NSE stocks: Add `.NS` → `TCS.NS`
BSE stocks: Add `.BO` → `TCS.BO`
US stocks: Use ticker → `AAPL`, `MSFT`
Indices: `^NSEI` (Nifty), `^GSPC` (S&P500)
"""

WELCOME_TEXT = """
👋 *Welcome to Market Intel Bot!*
━━━━━━━━━━━━━━━━━━━━━━━━

I deliver AI-powered market intelligence 
directly to your Telegram every day:

🌅 *8:00 AM* — Morning Brief + 3 Heatmaps
📈 *9:15 AM* — Market Open Alert
📊 *12:30 PM* — Midday Watchlist Scan
🔔 *3:45 PM* — End of Day Summary
📋 *4:30 PM* — Bulk & Block Deals
🕵️ *5:00 PM* — Insider Trading Tracker
🏦 *6:00 PM* — Credit Rating Monitor
🌃 *7:00 PM* — Evening Global Report

Type /help to see all commands.
"""

# ── TELEGRAM API HELPERS ──────────────────────────────────────────

def _send(chat_id: str, text: str) -> bool:
    """Send message back to user"""
    # Split if too long
    if len(text) > 4000:
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        return all(_send(chat_id, c) for c in chunks)
    try:
        resp = requests.post(
            f"{BASE}/sendMessage",
            json={
                "chat_id":                  chat_id,
                "text":                     text,
                "parse_mode":               "Markdown",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        return resp.json().get("ok", False)
    except Exception as e:
        print(f"⚠️  Send error: {e}")
        return False

def get_updates(offset: int = 0) -> List[Dict]:
    """
    Poll Telegram for new updates using offset.
    offset = last_update_id + 1 means only NEW messages.
    All updates with update_id <= offset are confirmed/discarded.
    """
    try:
        resp = requests.get(
            f"{BASE}/getUpdates",
            params={
                "offset":          offset,
                "limit":           100,
                "timeout":         0,        # Non-blocking
                "allowed_updates": ["message"],
            },
            timeout=20,
        )
        data = resp.json()
        if data.get("ok"):
            return data.get("result", [])
    except Exception as e:
        print(f"⚠️  getUpdates error: {e}")
    return []

# ── SYMBOL VALIDATION ─────────────────────────────────────────────

def validate_stock_symbol(symbol: str) -> Tuple[bool, str, str]:
    """
    Validate a stock symbol exists via yfinance.
    Returns: (is_valid, company_name, exchange)
    """
    try:
        t    = yf.Ticker(symbol)
        info = t.fast_info

        # Check if we get a valid price back
        price = info.get("last_price", None)
        if price is None or price == 0:
            # Try getting basic info
            full_info = t.info
            name = full_info.get("longName", "")
            exch = full_info.get("exchange", "")
            if name:
                return True, name, exch
            return False, "", ""

        # Get company name
        full_info    = t.info
        company_name = full_info.get("longName", "")  \
                    or full_info.get("shortName", "") \
                    or symbol
        exchange     = full_info.get("exchange", "")  \
                    or full_info.get("market", "")

        return True, company_name, exchange

    except Exception as e:
        print(f"⚠️  Symbol validation error ({symbol}): {e}")
        return False, "", ""

def validate_mf_code(scheme_code: str) -> Tuple[bool, str, str, str]:
    """
    Validate MF scheme code against mfapi.in
    Returns: (is_valid, scheme_name, fund_house, category)
    """
    try:
        resp = requests.get(
            f"https://api.mfapi.in/mf/{scheme_code}",
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            meta = data.get("meta", {})
            name      = meta.get("scheme_name",     "")
            fund_house = meta.get("fund_house",      "")
            category  = meta.get("scheme_category", "")
            if name:
                return True, name, fund_house, category
    except Exception as e:
        print(f"⚠️  MF code validation error: {e}")
    return False, "", "", ""

def search_mf_by_name(query: str) -> List[Dict]:
    """
    Search AMFI NAVAll.txt for MF schemes matching query.
    Returns top 5 matches.
    """
    try:
        resp = requests.get(
            "https://www.amfiindia.com/spages/NAVAll.txt",
            timeout=30
        )
        if resp.status_code != 200:
            return []

        results = []
        query_upper = query.upper()

        for line in resp.text.split("\n"):
            line = line.strip()
            if ";" not in line or not line:
                continue
            parts = line.split(";")
            if len(parts) < 4:
                continue
            code = parts[0].strip()
            name = parts[3].strip()
            if query_upper in name.upper() and code.isdigit():
                results.append({
                    "scheme_code": code,
                    "scheme_name": name,
                })
            if len(results) >= 8:
                break

        return results

    except Exception as e:
        print(f"⚠️  MF search error: {e}")
        return []

# ── SECURITY CHECK ────────────────────────────────────────────────

def is_authorised(chat_id: str) -> bool:
    """
    Only allow YOUR chat ID to control the bot.
    Prevents anyone else from modifying your watchlist.
    """
    return str(chat_id) == str(CHAT_ID)

# ── COMMAND HANDLERS ──────────────────────────────────────────────

def handle_start(chat_id: str) -> None:
    _send(chat_id, WELCOME_TEXT)

def handle_help(chat_id: str) -> None:
    _send(chat_id, HELP_TEXT)

def handle_add(chat_id: str, args: str) -> None:
    """Add stock to watchlist with validation"""
    if not args:
        _send(
            chat_id,
            "❌ Please provide a symbol\n"
            "Example: `/add RELIANCE.NS`"
        )
        return

    symbol = args.strip().upper()
    _send(chat_id, f"🔍 Validating *{symbol}*...")

    valid, company, exchange = validate_stock_symbol(symbol)
    if not valid:
        _send(
            chat_id,
            f"❌ *{symbol}* not found\n\n"
            f"💡 Make sure to use correct format:\n"
            f"  • NSE: `RELIANCE.NS`\n"
            f"  • BSE: `RELIANCE.BO`\n"
            f"  • US: `AAPL`"
        )
        return

    result = add_to_watchlist(symbol, company, exchange)
    _send(chat_id, result["message"])

def handle_remove(chat_id: str, args: str) -> None:
    """Remove stock from watchlist"""
    if not args:
        _send(
            chat_id,
            "❌ Please provide a symbol\n"
            "Example: `/remove RELIANCE.NS`"
        )
        return

    symbol = args.strip().upper()
    result = remove_from_watchlist(symbol)
    _send(chat_id, result["message"])

def handle_list(chat_id: str) -> None:
    """Show current watchlist"""
    msg = list_watchlist()
    _send(chat_id, msg)

def handle_addmf(chat_id: str, args: str) -> None:
    """Add MF scheme by AMFI code"""
    if not args:
        _send(
            chat_id,
            "❌ Please provide a scheme code\n"
            "Example: `/addmf 119598`\n\n"
            "💡 Don't know the code? Use:\n"
            "`/searchmf SBI bluechip`"
        )
        return

    code = args.strip()
    if not code.isdigit():
        _send(
            chat_id,
            f"❌ `{code}` is not a valid AMFI code\n"
            f"AMFI codes are numbers only\n"
            f"Use `/searchmf NAME` to find codes"
        )
        return

    _send(chat_id, f"🔍 Validating scheme code `{code}`...")
    valid, name, fund_house, category = validate_mf_code(code)

    if not valid:
        _send(
            chat_id,
            f"❌ Scheme code `{code}` not found on mfapi.in\n"
            f"Use `/searchmf NAME` to find valid codes"
        )
        return

    result = add_mf_scheme(code, name, fund_house, category)
    _send(chat_id, result["message"])

def handle_removemf(chat_id: str, args: str) -> None:
    """Remove MF scheme"""
    if not args:
        _send(
            chat_id,
            "❌ Please provide a scheme code\n"
            "Example: `/removemf 119598`\n"
            "Use `/listmf` to see your codes"
        )
        return

    code   = args.strip()
    result = remove_mf_scheme(code)
    _send(chat_id, result["message"])

def handle_listmf(chat_id: str) -> None:
    """Show MF watchlist"""
    msg = list_mf_watchlist()
    _send(chat_id, msg)

def handle_searchmf(chat_id: str, args: str) -> None:
    """Search for MF scheme by name"""
    if not args or len(args.strip()) < 3:
        _send(
            chat_id,
            "❌ Please provide at least 3 characters\n"
            "Example: `/searchmf SBI bluechip`"
        )
        return

    query = args.strip()
    _send(chat_id, f"🔍 Searching for *{query}*...")

    results = search_mf_by_name(query)
    if not results:
        _send(
            chat_id,
            f"❌ No schemes found for *{query}*\n"
            "Try a different search term"
        )
        return

    msg = f"🔍 *Search results for '{query}':*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for r in results[:8]:
        msg += (
            f"• *{r['scheme_name'][:50]}*\n"
            f"  Code: `{r['scheme_code']}`\n"
            f"  → `/addmf {r['scheme_code']}`\n\n"
        )
    msg += "_Tap a code above or type /addmf CODE_"
    _send(chat_id, msg)

def handle_status(chat_id: str) -> None:
    """Show bot status and DB health"""
    stocks  = get_watchlist()
    schemes = get_mf_watchlist()
    last_id = get_last_update_id()

    msg = (
        "✅ *Bot Status — All Systems Operational*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📈 Watchlist stocks: *{len(stocks)}*\n"
        f"💹 MF schemes: *{len(schemes)}*\n"
        f"🔄 Last processed update ID: `{last_id}`\n"
        f"🗄️ Database: ✅ Connected\n"
        f"🤖 AI Providers: Groq + Google AI\n\n"
        f"_Bot checks for commands every 5 minutes_"
    )
    _send(chat_id, msg)

# ── MARKET INTEL COMMANDS ──────────────────────────────────────────

def handle_stress(chat_id: str) -> None:
    """Show composite stress index from latest snapshot."""
    try:
        history = get_stress_history(days=5)
        if not history:
            _send(chat_id, "⚠️ No stress data available (may be weekend or market holiday)")
            return
        latest = history[-1]
        score = latest.get("stress_score", 0)
        date = latest.get("trade_date", "?")
        # Levels
        if score >= 80:
            level = "🚨 EXTREME"
        elif score >= 60:
            level = "🔴 HIGH"
        elif score >= 40:
            level = "🟡 ELEVATED"
        elif score >= 20:
            level = "🟢 MODERATE"
        else:
            level = "✅ LOW"
        msg = (
            f"📊 *Composite Stress Index*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Score: *{score:.1f}* / 100 ({level})\n"
            f"Date: {date}\n\n"
        )
        # Show trend
        if len(history) >= 2:
            prev = history[-2].get("stress_score", 0)
            delta = score - prev
            arrow = "↑" if delta > 1 else "↓" if delta < -1 else "→"
            msg += f"Trend: {arrow} {delta:+.1f} vs prev day\n"
        # Component breakdown via live compute
        try:
            current = compute_stress_index()
            if current.get("ok"):
                comps = current.get("components", {})
                msg += f"\n*Top drivers:*\n"
                for k, v in sorted(comps.items(), key=lambda x: abs(x[1]), reverse=True)[:4]:
                    label = k.replace("_", " ").title()
                    msg += f"  • {label}: {v:+.1f}\n"
        except Exception:
            pass
        _send(chat_id, msg)
    except Exception as e:
        _send(chat_id, f"⚠️ Error fetching stress index: {e}")


def handle_clone(chat_id: str) -> None:
    """Show latest historical macro clones."""
    try:
        db = get_client()
        if not db:
            _send(chat_id, "⚠️ Database not connected")
            return
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
        result = (
            db.table("clone_history")
            .select("*")
            .gte("trade_date", cutoff)
            .order("trade_date", desc=True)
            .limit(9)
            .execute()
        )
        rows = result.data if result.data else []
        if not rows:
            _send(chat_id, "⚠️ No clone data available (computed during market hours)")
            return
        # Group by trade_date, show latest group
        latest_group = rows[0]["trade_date"]
        clones = [r for r in rows if r["trade_date"] == latest_group][:3]
        msg = (
            f"🔬 *Historical Clones (Macro State)*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        for c in clones:
            fwd = c.get("nifty_30d_fwd")
            dd = c.get("max_dd")
            fwd_str = f"{fwd:+.1f}%" if fwd is not None else "N/A"
            dd_str = f"{dd:+.1f}%" if dd is not None else "N/A"
            msg += (
                f"📅 {c['clone_date']} | Dist: {c['distance']:.2f}\n"
                f"   30D Fwd: {fwd_str} | Max DD: {dd_str}\n\n"
            )
        # Summary line
        valid_fwds = [c.get("nifty_30d_fwd") for c in clones if c.get("nifty_30d_fwd") is not None]
        if valid_fwds:
            median = sorted(valid_fwds)[len(valid_fwds)//2]
            msg += f"Median 30D Fwd: {median:+.1f}%\n"
        msg += f"\n_Last computed: {latest_group}_"
        _send(chat_id, msg)
    except Exception as e:
        _send(chat_id, f"⚠️ Error fetching clones: {e}")


def handle_flows(chat_id: str) -> None:
    """Show latest FII/DII flows and velocity."""
    try:
        flows = get_fii_dii_flows(days=10)
        if not flows:
            _send(chat_id, "⚠️ No flow data available")
            return
        # Latest day
        latest = flows[-1]
        msg = (
            f"🏦 *FII / DII Flows*\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"Latest: {latest['date']}\n"
            f"FII Net: *₹{latest.get('fiinet_cr', 0):+,.0f} cr*\n"
            f"DII Net: *₹{latest.get('diinet_cr', 0):+,.0f} cr*\n"
            f"Net: *₹{latest.get('net_cr', 0):+,.0f} cr*\n\n"
        )
        # 5D cumulative
        recent = flows[-5:]
        if recent:
            fii_5d = sum(r.get("fiinet_cr", 0) or 0 for r in recent)
            dii_5d = sum(r.get("diinet_cr", 0) or 0 for r in recent)
            msg += f"*5D Cumulative:*\n"
            msg += f"FII: ₹{fii_5d:+,.0f} cr | DII: ₹{dii_5d:+,.0f} cr\n"
            # Velocity label
            if fii_5d < -5000:
                msg += f"🔄 FII: Accelerating selling\n"
            elif fii_5d < -2000:
                msg += f"🔁 FII: Sustained selling\n"
            elif fii_5d > 5000:
                msg += f"🔄 FII: Strong buying\n"
            else:
                msg += f"➡️ FII: Mixed / neutral\n"
        # Streak detection (simplified)
        streaks = []
        for r in reversed(flows):
            net = r.get("net_cr", 0) or 0
            if net > 0:
                streaks.append("B")
            elif net < 0:
                streaks.append("S")
            else:
                break
        if len(streaks) >= 3:
            direction = "buying 📈" if streaks[0] == "B" else "selling 📉"
            msg += f"\n*Streak:* {len(streaks)}d of {direction}"
        _send(chat_id, msg)
    except Exception as e:
        _send(chat_id, f"⚠️ Error fetching flows: {e}")


def handle_gex(chat_id: str) -> None:
    """Show latest options GEX levels, max pain, PCR."""
    try:
        snap = get_latest_snapshot("NIFTY", "morning")
        if not snap:
            snap = get_latest_snapshot("NIFTY", "evening")
        if not snap:
            _send(chat_id, "⚠️ No options snapshot available (traded during market hours)")
            return
        msg = (
            f"🧲 *Options Snapshot (NIFTY)*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        if snap.get("spot_price"):
            msg += f"Spot: *{snap['spot_price']:,.0f}*\n"
        if snap.get("max_pain"):
            msg += f"Max Pain: *{snap['max_pain']:,.0f}*\n"
        if snap.get("pcr"):
            msg += f"PCR: *{snap['pcr']:.2f}*"
            sig = snap.get("pcr_signal", "")
            if sig:
                msg += f" ({sig})"
            msg += "\n"
        if snap.get("gex") is not None:
            gex = snap["gex"]
            msg += f"GEX: *₹{gex:+,.0f} cr*"
            if gex > 500:
                msg += " (positive gamma — volatility dampening)"
            elif gex < -500:
                msg += " (negative gamma — volatility amplifying)"
            msg += "\n"
        if snap.get("skew_25d") is not None:
            msg += f"Skew (25d): *{snap['skew_25d']:.2f}*\n"
        # Support/resistance zones if stored
        sz = snap.get("support_zone", [])
        if sz and isinstance(sz, list) and len(sz) >= 2:
            msg += f"Support zone: {sz[0]:,.0f}–{sz[1]:,.0f}\n"
        rz = snap.get("resistance_zone", [])
        if rz and isinstance(rz, list) and len(rz) >= 2:
            msg += f"Resistance zone: {rz[0]:,.0f}–{rz[1]:,.0f}\n"
        msg += f"\n_Run: {snap.get('run', '?')} | {snap.get('date', '?')}_"
        _send(chat_id, msg)
    except Exception as e:
        _send(chat_id, f"⚠️ Error fetching options data: {e}")


def handle_sectors(chat_id: str) -> None:
    """Show latest sector RS leaders and laggards."""
    try:
        rows = get_sector_rs_history(days=3)
        if not rows:
            _send(chat_id, "⚠️ No sector RS data available")
            return
        # Group by date, get latest
        dates = sorted(set(r["date"] for r in rows), reverse=True)
        latest_date = dates[0]
        latest = [r for r in rows if r["date"] == latest_date]
        if not latest:
            _send(chat_id, "⚠️ No sector data for latest date")
            return
        # Sort by rs_score
        sorted_sectors = sorted(latest, key=lambda x: abs(x.get("rs_score", 0) or 0), reverse=True)
        msg = (
            f"📊 *Sector Relative Strength*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Date: {latest_date}\n\n"
        )
        leaders = [s for s in sorted_sectors if (s.get("rs_score", 0) or 0) > 0][:5]
        laggards = [s for s in sorted_sectors if (s.get("rs_score", 0) or 0) < 0][:5]
        if leaders:
            msg += "*Leaders:*\n"
            for s in leaders:
                rs = s.get("rs_score", 0) or 0
                mom = s.get("momentum_1m", 0) or 0
                arrow = "↑" if mom > 0 else "↓"
                msg += f"  🟢 {s.get('sector_name', '?')}: {rs:+.2f}σ {arrow}\n"
        if laggards:
            msg += f"\n*Laggards:*\n"
            for s in laggards:
                rs = s.get("rs_score", 0) or 0
                mom = s.get("momentum_1m", 0) or 0
                arrow = "↑" if mom > 0 else "↓"
                msg += f"  🔴 {s.get('sector_name', '?')}: {rs:+.2f}σ {arrow}\n"
        # Turnover ratio if available
        trs = [s.get("turnover_ratio") for s in latest if s.get("turnover_ratio") is not None]
        if trs:
            avg_tr = sum(trs) / len(trs)
            msg += f"\nAvg turnover ratio: {avg_tr:.2f}\n"
        _send(chat_id, msg)
    except Exception as e:
        _send(chat_id, f"⚠️ Error fetching sector data: {e}")


def handle_simulate(chat_id: str, args: str) -> None:
    """Simulate a scenario with overridden macro variable."""
    if not args:
        vars_list = ", ".join(["brent", "wti", "usdinr", "dxy", "gold", "india_vix", "us_10y", "copper", "hyg"])
        _send(
            chat_id,
            f"❌ Usage: `/simulate <variable> <value>`\n\n"
            f"Available: {vars_list}\n\n"
            f"Examples:\n"
            f"  `/simulate brent 120` — Oil at $120\n"
            f"  `/simulate usdinr 90` — Rupee at ₹90\n"
            f"  `/simulate india_vix 25` — VIX at 25"
        )
        return
    parts = args.strip().split(None, 1)
    if len(parts) < 2:
        _send(chat_id, "❌ Provide both variable and value\nExample: `/simulate brent 120`")
        return
    variable = parts[0].lower().strip()
    try:
        value = float(parts[1])
    except ValueError:
        _send(chat_id, "❌ Value must be a number")
        return
    try:
        from src.scenario_simulator import run_simulation, format_simulation
        result = run_simulation(variable, value)
        msg = format_simulation(result)
        _send(chat_id, msg)
    except Exception as e:
        _send(chat_id, f"⚠️ Simulation error: {e}")


def handle_compare(chat_id: str, args: str) -> None:
    """Compare current macro state with a historical date."""
    if not args:
        _send(
            chat_id,
            "❌ Usage: `/compare YYYY-MM-DD`\n\n"
            "Examples:\n"
            "  `/compare 2020-03-23` — COVID crash bottom\n"
            "  `/compare 2013-08-15` — Taper Tantrum\n"
            "  `/compare 2008-10-27` — GFC low"
        )
        return
    target_date = args.strip()
    try:
        from src.historical_comparator import format_comparison
        msg = format_comparison(target_date)
        _send(chat_id, msg)
    except Exception as e:
        _send(chat_id, f"⚠️ Comparison error: {e}")


def handle_query(chat_id: str, args: str) -> None:
    """Natural language query against deterministic data store."""
    if not args or len(args.strip()) < 3:
        _send(
            chat_id,
            "❌ Ask me something specific.\n\n"
            "Examples:\n"
            "  `what is FII doing?`\n"
            "  `show me sector RS`\n"
            "  `active pillars?`\n"
            "  `current regime?`\n"
            "  `how stressed is the market?`"
        )
        return
    try:
        from src.agent_query import format_query_response
        msg = format_query_response(args.strip())
        _send(chat_id, msg)
    except Exception as e:
        _send(chat_id, f"⚠️ Query error: {e}")


def handle_whatif(chat_id: str, args: str) -> None:
    """Simulate consequence of a macro variable change."""
    if not args:
        vars_list = ", ".join(sorted(CONSEQUENCE_MULTIPLIERS.keys()))
        _send(
            chat_id,
            f"❌ Usage: `/whatif <variable> <value>`\n\n"
            f"Available variables: {vars_list}\n\n"
            f"Examples:\n"
            f"  `/whatif brent 100` — Oil at $100\n"
            f"  `/whatif usdinr 90` — Rupee at ₹90\n"
            f"  `/whatif india_vix 25` — VIX at 25\n"
            f"  `/whatif gold 5000` — Gold at ₹5000/bbl"
        )
        return
    parts = args.strip().split(None, 1)
    if len(parts) < 2:
        _send(
            chat_id,
            f"❌ Please provide both variable and value\n"
            f"Example: `/whatif brent 100`"
        )
        return
    variable = parts[0].lower().strip()
    try:
        current_value = float(parts[1])
    except ValueError:
        _send(chat_id, "❌ Value must be a number")
        return
    # Validate variable (with common aliases)
    ALIASES = {
        "vix": "india_vix",
        "usd": "usdinr",
        "dollar": "usdinr",
        "rupee": "usdinr",
        "inr": "usdinr",
        "oil": "brent",
        "crude": "brent",
        "10y": "us_10y",
        "us10y": "us_10y",
        "dxy": "dxy",
        "dollar_index": "dxy",
        "gold": "gold",
        "copper": "copper",
        "hyg": "hyg",
        "wti": "wti",
    }
    canonical = ALIASES.get(variable, variable.replace("-", "_").replace("/", "_"))
    if canonical not in CONSEQUENCE_MULTIPLIERS:
        vars_list = ", ".join(sorted(CONSEQUENCE_MULTIPLIERS.keys()))
        _send(
            chat_id,
            f"❌ Unknown variable: `{variable}`\n\n"
            f"Available: {vars_list}\n\n"
            f"Examples:\n"
            f"  `/whatif brent 100` — Oil at $100\n"
            f"  `/whatif usdinr 90` — Rupee at ₹90\n"
            f"  `/whatif india_vix 25` — VIX at 25\n"
            f"  `/whatif gold 5000` — Gold at ₹5000\n"
            f"  `/whatif us_10y 5` — US 10Y at 5%"
        )
        return
    result = compute_consequence(canonical, current_value, change_value=current_value)
    if not result:
        _send(chat_id, f"⚠️ No consequence mapping for `{variable}` at that level")
        return
    msg = (
        f"🔮 *What If: {variable} = {current_value}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    lines = result.get("lines", [])
    for line in lines[:5]:
        msg += f"  • {line}\n"
    severity = result.get("severity", "")
    if severity:
        sev_map = {"neutral": "⚪", "elevated": "🟡", "high": "🔴", "extreme": "🚨", "stress": "🔴"}
        emoji = sev_map.get(severity.lower(), "⚪")
        msg += f"\nSeverity: {emoji} {severity}\n"
    _send(chat_id, msg)


def handle_unknown(chat_id: str, text: str) -> None:
    """Handle unrecognised commands"""
    _send(
        chat_id,
        f"❓ Unknown command: `{text}`\n\n"
        "Type /help to see all available commands"
    )

# ── MAIN COMMAND DISPATCHER ───────────────────────────────────────

def process_update(update: Dict) -> None:
    """
    Process a single Telegram update.
    Dispatches to correct handler based on command.
    """
    message = update.get("message", {})
    if not message:
        return

    chat_id = str(message.get("chat", {}).get("id", ""))
    text    = message.get("text", "").strip()

    if not text or not chat_id:
        return

    print(f"📨 Message from {chat_id}: {text[:80]}")

    # ── Security: only YOUR chat ID allowed ────────────────────
    if not is_authorised(chat_id):
        print(f"🚫 Unauthorised access attempt from chat_id: {chat_id}")
        _send(
            chat_id,
            "🚫 Unauthorised\n"
            "This bot is privately configured"
        )
        return

    # ── Parse command and args ──────────────────────────────────
    parts   = text.split(None, 1)           # Split on first whitespace
    command = parts[0].lower().strip()
    args    = parts[1].strip() if len(parts) > 1 else ""

    # Remove bot username if present (e.g. /add@mybotname)
    if "@" in command:
        command = command.split("@")[0]

    # ── Dispatch ────────────────────────────────────────────────
    dispatch = {
        "/start":     lambda: handle_start(chat_id),
        "/help":      lambda: handle_help(chat_id),
        "/add":       lambda: handle_add(chat_id, args),
        "/remove":    lambda: handle_remove(chat_id, args),
        "/list":      lambda: handle_list(chat_id),
        "/addmf":     lambda: handle_addmf(chat_id, args),
        "/removemf":  lambda: handle_removemf(chat_id, args),
        "/listmf":    lambda: handle_listmf(chat_id),
        "/searchmf":  lambda: handle_searchmf(chat_id, args),
        "/status":    lambda: handle_status(chat_id),
        "/stress":    lambda: handle_stress(chat_id),
        "/clone":     lambda: handle_clone(chat_id),
        "/flows":     lambda: handle_flows(chat_id),
        "/gex":       lambda: handle_gex(chat_id),
        "/sectors":   lambda: handle_sectors(chat_id),
        "/whatif":    lambda: handle_whatif(chat_id, args),
        "/simulate":  lambda: handle_simulate(chat_id, args),
        "/compare":   lambda: handle_compare(chat_id, args),
        "/query":     lambda: handle_query(chat_id, args),
    }

    handler = dispatch.get(command)
    if handler:
        handler()
    else:
        handle_unknown(chat_id, text)


# ── MAIN POLLING LOOP (called by GitHub Actions) ──────────────────

def run_bot_handler() -> None:
    """
    Main entry point — called every 5 minutes by GitHub Actions.
    Gets new updates since last run using offset from Supabase.
    Processes all new commands.
    Saves new offset back to Supabase.
    """
    print("=" * 50)
    print("🤖 BOT HANDLER — CHECKING FOR COMMANDS")
    print("=" * 50)

    # Get last processed update_id from Supabase
    last_id = get_last_update_id()
    offset  = last_id + 1 if last_id > 0 else 0
    print(f"📋 Last update_id: {last_id} | Fetching from offset: {offset}")

    # Get new updates
    updates = get_updates(offset=offset)
    print(f"📨 New updates: {len(updates)}")

    if not updates:
        print("✅ No new commands — all caught up")
        return

    # Process each update
    new_max_id = last_id
    for update in updates:
        update_id = update.get("update_id", 0)
        try:
            process_update(update)
        except Exception as e:
            print(f"⚠️  Error processing update {update_id}: {e}")

        # Track highest update_id seen
        if update_id > new_max_id:
            new_max_id = update_id

    # Save new offset — prevents re-processing on next run
    if new_max_id > last_id:
        save_last_update_id(new_max_id)
        print(f"✅ Saved new last_update_id: {new_max_id}")

    print(f"✅ Processed {len(updates)} update(s)")