"""
World Equity Heatmap Generator
Fixed: Pilmoji CDN fallback if Twemoji unavailable on runner
"""
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from datetime import datetime
import pytz

BG        = (0,   0,   0)
HDR_GREEN = (0, 153,  51)
WHITE     = (255, 255, 255)
GREY      = (160, 160, 160)

# BUG FIX: Check if pilmoji + network works, fall back to plain PIL
try:
    from pilmoji import Pilmoji
    PILMOJI_AVAILABLE = True
except ImportError:
    PILMOJI_AVAILABLE = False
    print("⚠️  pilmoji not available — using plain text flags")

def _cell_bg(pct: float) -> tuple:
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

def _status_color(status: str) -> tuple:
    return (0, 160, 0) if status == "OPEN" else (160, 0, 0)

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
        "section": tf(bold, 18),
        "region":  tf(reg,  13),
        "country": tf(bold, 13),
        "pct":     tf(bold, 17),
        "status":  tf(reg,  10),
        "ts":      tf(reg,  12),
    }

def _draw_cards_plain(img, draw, F, countries, y, CARD_W, CARD_H, CARD_PAD, IMG_W):
    """
    BUG FIX: Plain PIL drawing without pilmoji
    Used as fallback when pilmoji/CDN unavailable
    Replaces flag emoji with ISO country code text
    """
    n_rows = (len(countries) + 4) // 5
    for row_i in range(n_rows):
        row   = countries[row_i * 5: (row_i + 1) * 5]
        tot_w = len(row) * CARD_W + (len(row) - 1) * CARD_PAD
        x0    = (IMG_W - tot_w) // 2

        for col_i, (country, data) in enumerate(row):
            x        = x0 + col_i * (CARD_W + CARD_PAD)
            pct      = data.get("change_pct", 0.0)
            status   = data.get("status",     "CLOSED")
            iso      = data.get("iso",         "")
            index_nm = data.get("index_name", "")
            bg       = _cell_bg(pct)
            tc       = _text_color(pct)

            draw.rounded_rectangle(
                [(x, y), (x + CARD_W, y + CARD_H)],
                radius=8, fill=bg,
            )
            # Use ISO code instead of emoji flag
            draw.text((x + CARD_W // 2, y + 8),  iso,
                      fill=tc, font=F["status"], anchor="mt")
            draw.text((x + CARD_W // 2, y + 24), country,
                      fill=tc, font=F["country"], anchor="mt")
            if index_nm:
                draw.text((x + CARD_W // 2, y + 40), index_nm,
                          fill=tc, font=F["status"], anchor="mt")
            sign = "+" if pct >= 0 else ""
            draw.text((x + CARD_W // 2, y + 56),
                      f"{sign}{pct:.2f}%",
                      fill=tc, font=F["pct"], anchor="mt")

            sc  = _status_color(status)
            bx1 = x + CARD_W // 2 - 28
            by1 = y + CARD_H - 22
            bx2 = x + CARD_W // 2 + 28
            by2 = y + CARD_H - 6
            draw.rounded_rectangle([(bx1, by1), (bx2, by2)],
                                   radius=4, fill=sc)
            draw.text((x + CARD_W // 2, (by1 + by2) // 2),
                      status, fill=WHITE, font=F["status"], anchor="mm")

        y += CARD_H + CARD_PAD + 4
    return y

def generate_heatmap(index_data: dict) -> BytesIO:
    """
    Generate FinXray-style world equity heatmap PNG.
    Returns BytesIO ready for Telegram sendPhoto.
    """
    REGION_ORDER   = ["Americas", "Asia", "Europe"]
    SECTION_LABELS = {
        "Americas": "Overnight Action",
        "Asia":     "Today's Action",
        "Europe":   "Today's Action",
    }

    grouped = {r: [] for r in REGION_ORDER}
    for country, data in index_data.items():
        r = data.get("region", "Other")
        if r in grouped:
            grouped[r].append((country, data))

    IMG_W    = 900
    CARD_W   = 148
    CARD_H   = 115
    CARD_PAD = 11

    total_rows = sum((len(grouped[r]) + 4) // 5
                     for r in REGION_ORDER if grouped[r])
    n_sections = len([r for r in REGION_ORDER if grouped[r]])
    IMG_H = 130 + n_sections * 100 + total_rows * (CARD_H + CARD_PAD + 4) + 30

    img  = Image.new("RGB", (IMG_W, IMG_H), BG)
    F    = _load_fonts()
    draw = ImageDraw.Draw(img)

    y = 15
    draw.text((IMG_W // 2, y), "World Equity Heatmap",
              fill=WHITE, font=F["title"], anchor="mt")
    y += 36
    draw.text((IMG_W // 2, y), "Today",
              fill=WHITE, font=F["sub"], anchor="mt")
    y += 24
    ist = datetime.now(pytz.timezone("Asia/Kolkata"))
    draw.text((IMG_W // 2, y),
              ist.strftime("As of %d-%b-%Y %H:%M IST"),
              fill=GREY, font=F["ts"], anchor="mt")
    y += 28

    drawn_sections = set()

    for region_name in REGION_ORDER:
        countries = grouped[region_name]
        if not countries:
            continue

        section = SECTION_LABELS[region_name]
        if section not in drawn_sections:
            y += 8
            draw.rectangle([(0, y), (IMG_W, y + 38)], fill=HDR_GREEN)
            draw.text((IMG_W // 2, y + 19), section,
                      fill=WHITE, font=F["section"], anchor="mm")
            y += 48
            drawn_sections.add(section)

        draw.text((IMG_W // 2, y), region_name,
                  fill=GREY, font=F["region"], anchor="mt")
        y += 22

        # BUG FIX: Try pilmoji, fall back to plain PIL
        if PILMOJI_AVAILABLE:
            try:
                n_rows = (len(countries) + 4) // 5
                with Pilmoji(img) as pilmoji:
                    for row_i in range(n_rows):
                        row   = countries[row_i * 5: (row_i + 1) * 5]
                        tot_w = len(row) * CARD_W + (len(row) - 1) * CARD_PAD
                        x0    = (IMG_W - tot_w) // 2

                        for col_i, (country, data) in enumerate(row):
                            x         = x0 + col_i * (CARD_W + CARD_PAD)
                            pct       = data.get("change_pct", 0.0)
                            status    = data.get("status",     "CLOSED")
                            flag      = data.get("flag",        "")
                            index_nm  = data.get("index_name", "")
                            bg        = _cell_bg(pct)
                            tc        = _text_color(pct)

                            draw.rounded_rectangle(
                                [(x, y), (x + CARD_W, y + CARD_H)],
                                radius=8, fill=bg)

                            pilmoji.text(
                                (x + CARD_W // 2 - 12, y + 6),
                                flag, fill=tc, font=F["country"],
                                emoji_scale_factor=1.4)

                            draw.text((x + CARD_W // 2, y + 28),
                                      country, fill=tc,
                                      font=F["country"], anchor="mt")

                            if index_nm:
                                draw.text((x + CARD_W // 2, y + 44),
                                          index_nm, fill=tc,
                                          font=F["status"], anchor="mt")

                            sign = "+" if pct >= 0 else ""
                            draw.text((x + CARD_W // 2, y + 62),
                                      f"{sign}{pct:.2f}%",
                                      fill=tc, font=F["pct"], anchor="mt")

                            sc   = _status_color(status)
                            bx1  = x + CARD_W // 2 - 28
                            by1  = y + CARD_H - 22
                            bx2  = x + CARD_W // 2 + 28
                            by2  = y + CARD_H - 6
                            draw.rounded_rectangle(
                                [(bx1, by1), (bx2, by2)],
                                radius=4, fill=sc)
                            draw.text((x + CARD_W // 2, (by1 + by2) // 2),
                                      status, fill=WHITE,
                                      font=F["status"], anchor="mm")

                        y += CARD_H + CARD_PAD + 4
                y += 10
                continue
            except Exception as e:
                print(f"⚠️  Pilmoji failed ({e}), using plain PIL")

        # Fallback: plain PIL without emoji
        y = _draw_cards_plain(
            img, draw, F, countries, y,
            CARD_W, CARD_H, CARD_PAD, IMG_W
        )
        y += 10

    img = img.crop((0, 0, IMG_W, y + 15))
    buf = BytesIO()
    buf.name = "heatmap.png"
    img.save(buf, "PNG", optimize=True)
    buf.seek(0)
    return buf