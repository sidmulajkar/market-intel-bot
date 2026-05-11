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
BASE    = f"https://api.telegram.org/bot{TOKEN}"

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
    """Send text message — auto-splits if over 4000 chars"""
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
    """Send PIL-generated image to Telegram"""
    image_buf.seek(0)
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
        "breakout":     "🚀",
        "crash":        "🔴",
        "volume_spike": "📊",
        "news":         "📰",
        "sentiment":    "🎯",
        "earnings":     "💰",
        "general":      "⚡",
    }
    emoji = emoji_map.get(alert_type, "⚡")
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