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
)

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