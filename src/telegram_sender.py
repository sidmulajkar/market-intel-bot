"""
Telegram Delivery Layer
All communication via direct HTTP calls to Telegram Bot API
No telegram library needed — just requests
"""
import os
import requests
from io import BytesIO
from datetime import datetime
import pytz

TOKEN   = os.environ.get('TELEGRAM_TOKEN',  '')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
DRY_RUN = os.environ.get('DRY_RUN', '').lower() in ('1', 'true', 'yes')
BASE    = f"https://api.telegram.org/bot{TOKEN}"

# Allowed emoji set (9 classes). Everything else maps to one of these or is stripped.
_ALLOWED_EMOJI = set("🟢🔴🟡📈📉➡️⚠️🚨📌")


class InfrastructureLeakageError(Exception):
    """Raised when message content contains infrastructure/debug strings."""
    def __init__(self, text: str, matched_pattern: str):
        self.matched_pattern = matched_pattern
        super().__init__(f"Infrastructure leakage detected: '{matched_pattern}'")

# Semantic mapping: unauthorized emoji → allowed equivalent (or "" to strip)
_EMOJI_MAP = {
    # Informational → neutral marker
    "📊": "📌",
    "🤖": "📌",
    "📅": "📌",
    "🏭": "📌",
    "💰": "📌",
    # Pointer/label → neutral marker
    "🎯": "📌",
    "📐": "📌",
    "📍": "📌",
    "🔔": "📌",
    "📦": "📌",
    "📡": "📌",
    "📋": "📌",
    "📝": "📌",
    "📏": "📌",
    "📶": "📌",
    "🔗": "📌",
    "🏦": "📌",
    "🔍": "📌",
    # Intensity → warning
    "🔥": "⚠️",
    "⚡": "⚠️",
    "🚀": "⚠️",
    "💥": "⚠️",
    "🔻": "📉",
    # Decorative → strip
    "💭": "",
    "🌍": "",
    "⚪": "",
    "💵": "",
    "🛢️": "",
    "💹": "",
    "🌃": "",
    "🌅": "",
    "🌙": "",
    "↑": "",
    "↓": "",
}

def _scrub_emoji(text: str) -> str:
    """Replace unauthorized emoji with allowed equivalents. Preserves the 9 allowed emoji."""
    for bad, repl in _EMOJI_MAP.items():
        if bad in text:
            text = text.replace(bad, repl)
    return text

def _post(endpoint: str, **kwargs) -> dict:
    """Generic POST with error logging"""
    try:
        resp   = requests.post(f"{BASE}/{endpoint}", timeout=60, **kwargs)
        result = resp.json()
        if not result.get("ok"):
            print(f"⚠️  Telegram {endpoint} failed: {result.get('description')}")
        return result
    except Exception as e:
        print(f"⚠️  Telegram {endpoint} exception: {e}")
        return {"ok": False}

def send_text(text: str, parse_mode: str = "Markdown") -> bool:
    """Send text message — auto-splits if over 4000 chars. Scrubs emoji to allowed set. Final-pass leakage scrubber. Dry-run prints both original and scrubbed."""
    scrubbed = _scrub_emoji(text)

    # Final-pass leakage scrubber (import here to avoid circular dependency)
    from src.validation_helper import output_scrubber
    scrubbed = output_scrubber(scrubbed)

    # Verify no leakage patterns remain — raise if they do
    lower = scrubbed.lower()
    from src.validation_helper import _LEAKAGE_PATTERNS
    for pattern in _LEAKAGE_PATTERNS:
        if pattern in lower:
            raise InfrastructureLeakageError(scrubbed, pattern)

    if DRY_RUN:
        print("\n" + "=" * 60)
        print("📨 [DRY RUN] Telegram message would be sent:")
        if scrubbed != text:
            print("--- ORIGINAL (emoji will be scrubbed) ---")
            print(text[:4000])
            print("--- SCRUBBED (will be sent) ---")
        print("=" * 60)
        print(scrubbed[:4000])
        if len(scrubbed) > 4000:
            print(f"\n... ({len(scrubbed) - 4000} more chars)")
        print("=" * 60)
        return True
    text = scrubbed
    max_len = 4000
    if len(text) > max_len:
        chunks  = [text[i:i+max_len] for i in range(0, len(text), max_len)]
        success = True
        for chunk in chunks:
            r = _post("sendMessage", json={
                "chat_id":                  CHAT_ID,
                "text":                     chunk,
                "parse_mode":               parse_mode,
                "disable_web_page_preview": True,
            })
            success = success and r.get("ok", False)
        return success

    r = _post("sendMessage", json={
        "chat_id":                  CHAT_ID,
        "text":                     text,
        "parse_mode":               parse_mode,
        "disable_web_page_preview": True,
    })
    return r.get("ok", False)

def send_image(image_buf: BytesIO, caption: str = "") -> bool:
    """Send PIL-generated image to Telegram. Caption is emoji-scrubbed."""
    image_buf.seek(0)
    caption = _scrub_emoji(caption)
    r = _post("sendPhoto",
        files={"photo": (
            getattr(image_buf, 'name', 'image.png'),
            image_buf,
            "image/png"
        )},
        data={
            "chat_id":    CHAT_ID,
            "caption":    caption[:1024] if caption else "",
            "parse_mode": "Markdown",
        }
    )
    return r.get("ok", False)

def send_alert(symbol: str, alert_type: str, message: str) -> bool:
    """Send formatted alert"""
    emoji_map = {
        "breakout":     "📈",
        "crash":        "🔴",
        "volume_spike": "📌",
        "news":         "📌",
        "sentiment":    "📌",
        "earnings":     "📌",
        "general":      "⚠️",
    }
    emoji = emoji_map.get(alert_type, "⚠️")
    text  = f"{emoji} *ALERT — {symbol}*\n\n{message}"
    return send_text(text)

# ── MESSAGE FORMATTERS ────────────────────────────────────────────

def fmt_morning_report(analysis: str) -> str:
    ist      = datetime.now(pytz.timezone('Asia/Kolkata'))
    date_str = ist.strftime("%A, %d %b %Y")
    return (
        f"🌅 *MORNING MARKET BRIEF*\n"
        f"_{date_str}_\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{analysis}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"_AI Market Intel Bot_"
    )

def fmt_eod_report(analysis: str) -> str:
    return (
        f"🔔 *END OF DAY SUMMARY*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{analysis}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"_See you tomorrow! 🌙_"
    )

def fmt_weekly_report(analysis: str) -> str:
    return (
        f"📅 *WEEKLY MARKET DIGEST*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{analysis}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"_Have a great weekend!_"
    )

def send_health_check() -> bool:
    return send_text(
        "✅ *Market Intel Bot is Running*\n"
        "_All systems operational_"
    )

# ── BLUF HEADER — Bottom Line Up Front ────────────────────────────

def build_bluf(regime_verdict=None, bull_bear: dict = None, nifty_price: float = None, nifty_change: float = None,
               vix: float = None, fii_net: float = None, dii_net: float = None) -> str:
    """Build a 1-line BLUF narrative driven by regime arbiter verdict.

    If regime_verdict (from arbitrate_regime) is provided, uses template-driven
    narrative. Falls back to empty string — never computes legacy composite.
    """
    if regime_verdict is not None:
        regime = getattr(regime_verdict, 'regime', None) or getattr(regime_verdict, 'get', lambda k, d: d)('regime', None)
        drivers = getattr(regime_verdict, 'dominant_driver', '') or getattr(regime_verdict, 'get', lambda k, d: d)('dominant_driver', '')
        posture = getattr(regime_verdict, 'posture', None) or getattr(regime_verdict, 'get', lambda k, d: d)('posture', None)

        posture_text = ""
        if posture:
            posture_therefore = getattr(posture, 'therefore', '') or posture.get('therefore', '')
            posture_text = posture_therefore

        if regime == "DEFENSIVE":
            template = f"Macro override active: {drivers}. Risk posture: defensive."
            if posture_text:
                template += f" {posture_text}"
            return template
        elif regime == "BEARISH":
            return f"Bearish setup: {drivers}. Reduce exposure."
        elif regime == "BULLISH":
            return f"Constructive setup: {drivers}. Accumulate on dips."
        elif regime == "NEUTRAL":
            return f"No dominant macro driver. Range-bound posture."
        else:
            return f"Regime: {regime}. {drivers}." if drivers else ""

    # No regime verdict — return empty rather than computing legacy composite.
    # Callers should pass the arbiter verdict to get meaningful BLUF text.
    return ""


def pin_message(message_id: int, disable_notification: bool = True) -> bool:
    """Pin a message to the chat. Returns True on success."""
    if DRY_RUN:
        print(f"📌 [DRY RUN] Would pin message {message_id}")
        return True
    r = _post("pinChatMessage", json={
        "chat_id": CHAT_ID,
        "message_id": message_id,
        "disable_notification": disable_notification,
    })
    return r.get("ok", False)


def send_pinned_glossary() -> bool:
    """Send and pin the inline glossary to the group. Zero AI, zero live API calls."""
    from src.formatters import GLOSSARY_TIER1, GLOSSARY_TIER2

    text = (
        "📌 *GLOSSARY*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "*Tier 1 (Confusing terms — explained every session):*\n"
    )
    for term in sorted(GLOSSARY_TIER1):
        text += f"• {term} — {GLOSSARY_TIER1[term]}\n"
    text += "\n*Tier 2 (Common terms — explained once per day):*\n"
    for term in sorted(GLOSSARY_TIER2):
        text += f"• {term} — {GLOSSARY_TIER2[term]}\n"
    text += (
        "\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "_Pinned reference — updated by Market Intel Bot_"
    )

    if DRY_RUN:
        print("\n" + "=" * 60)
        print("📌 [DRY RUN] Pinned Glossary:")
        print(text)
        print("=" * 60)
        return True

    r = _post("sendMessage", json={
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    })

    if not r.get("ok"):
        print(f"⚠️  Failed to send glossary: {r.get('description')}")
        return False

    message_id = r.get("result", {}).get("message_id")
    if message_id:
        return pin_message(message_id)
    return False