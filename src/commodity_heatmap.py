"""
Commodity Heatmap Generator
3-column layout: USD/INR, Brent Crude, Gold
"""
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from datetime import datetime
import pytz


BG       = (0, 0, 0)
HDR_GOLD = (218, 165, 32)
WHITE    = (255, 255, 255)
GREY     = (160, 160, 160)


def _cell_bg(pct: float) -> tuple:
    """Commodity-specific color scale."""
    if   pct >=  3.0: return (0,   120,   0)
    elif pct >=  1.5: return (0,   180,   0)
    elif pct >=  0.5: return (100, 210, 100)
    elif pct >   0.0: return (190, 240, 190)
    elif pct == 0.0:  return (220, 220, 220)
    elif pct > -0.5:  return (255, 210, 210)
    elif pct > -1.5:  return (255, 160, 160)
    elif pct > -3.0:  return (220,  80,  80)
    else:             return (139,   0,   0)


def _text_color(pct: float) -> tuple:
    return WHITE if abs(pct) >= 1.5 else (20, 20, 20)


def _load_fonts() -> dict:
    base = "/usr/share/fonts/truetype/dejavu/"
    bold = base + "DejaVuSans-Bold.ttf"
    reg  = base + "DejaVuSans.ttf"
    def tf(path, size):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            return ImageFont.load_default()
    return {
        "title":   tf(bold, 26),
        "sub":     tf(reg,  16),
        "label":   tf(bold, 16),
        "name":    tf(bold, 14),
        "price":   tf(bold, 18),
        "change":  tf(bold, 14),
        "weekly":  tf(reg,  11),
        "ts":      tf(reg,  12),
    }


def generate_commodity_heatmap(anchor_data: list) -> BytesIO:
    """
    Generate commodity heatmap for USDINR, Brent, Gold.
    anchor_data: list from fetch_macro_anchors()
    Returns BytesIO for Telegram.
    """
    if not anchor_data:
        return None

    IMG_W    = 600
    CARD_W   = 170
    CARD_H   = 130
    CARD_PAD = 15

    F = _load_fonts()
    draw = ImageDraw.Draw(Image.new("RGB", (IMG_W, 200), BG))

    # Calculate image height
    IMG_H = 30 + 36 + 20 + 24 + 20 + CARD_H + 30

    img  = Image.new("RGB", (IMG_W, IMG_H), BG)
    draw = ImageDraw.Draw(img)

    # ── Header ──
    y = 15
    draw.text((IMG_W // 2, y), "Commodity Heatmap",
              fill=WHITE, font=F["title"], anchor="mt")
    y += 36
    draw.text((IMG_W // 2, y), "USD/INR · Brent Crude · Gold",
              fill=GREY, font=F["sub"], anchor="mt")
    y += 24
    ist = datetime.now(pytz.timezone("Asia/Kolkata"))
    draw.text((IMG_W // 2, y),
              ist.strftime("As of %d-%b-%Y %H:%M IST"),
              fill=GREY, font=F["ts"], anchor="mt")
    y += 40

    # ── Cards ──
    items = [a for a in anchor_data if a.get("ok")]
    n = len(items)
    if n == 0:
        return None

    tot_w = n * CARD_W + (n - 1) * CARD_PAD
    x0 = (IMG_W - tot_w) // 2

    for i, item in enumerate(items):
        x = x0 + i * (CARD_W + CARD_PAD)

        name   = item.get("name", "")
        price  = item.get("price")
        change = item.get("change_pct")
        weekly = item.get("weekly_change_pct")
        status = item.get("status", "flat")

        pct = change if change else 0
        bg  = _cell_bg(pct)
        tc  = _text_color(pct)

        draw.rounded_rectangle(
            [(x, y), (x + CARD_W, y + CARD_H)],
            radius=10, fill=bg)

        # Emoji icon
        if "USD" in name:
            icon = "💵"
        elif "Brent" in name:
            icon = "🛢️"
        elif "Gold" in name:
            icon = "🥇"
        else:
            icon = "📊"

        # Name
        draw.text((x + CARD_W // 2, y + 10),
                  icon, font=F["name"], anchor="mt")
        draw.text((x + CARD_W // 2, y + 28),
                  name, fill=tc, font=F["name"], anchor="mt")

        # Price
        if price:
            price_str = f"₹{price:,.2f}" if "USD" in name else f"${price:,.2f}"
        else:
            price_str = "N/A"
        draw.text((x + CARD_W // 2, y + 52),
                  price_str, fill=tc, font=F["price"], anchor="mt")

        # Day change
        sign = "+" if pct >= 0 else ""
        change_str = f"{sign}{pct:.2f}%"
        status_icon = "📈" if status == "up" else ("📉" if status == "down" else "➡️")
        draw.text((x + CARD_W // 2, y + 80),
                  f"{change_str} {status_icon}", fill=tc, font=F["change"], anchor="mt")

        # Weekly change
        if weekly:
            w_sign = "+" if weekly >= 0 else ""
            w_str = f"5D: {w_sign}{weekly:.2f}%"
        else:
            w_str = "5D: N/A"
        draw.text((x + CARD_W // 2, y + 105),
                  w_str, fill=tc, font=F["weekly"], anchor="mt")

    img = img.crop((0, 0, IMG_W, y + CARD_H + 15))
    buf = BytesIO()
    buf.name = "commodity_heatmap.png"
    img.save(buf, "PNG", optimize=True)
    buf.seek(0)
    return buf