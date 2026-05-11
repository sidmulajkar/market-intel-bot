"""
Sector Heatmap Generator
Generates visual heatmaps for:
  1. India Sectors (Nifty sector indices)
  2. Personal Watchlist stocks
  3. Global Countries (existing heatmap_generator.py handles this)
All rendered as PNG images using PIL + pilmoji
"""
import io
import time
import yfinance as yf
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji
from io import BytesIO
from datetime import datetime
import pytz

# ── NIFTY SECTOR INDICES (free via yfinance) ─────────────────────
NIFTY_SECTORS = {
    "IT":           {"symbol": "^CNXIT",   "emoji": "💻"},
    "Bank":         {"symbol": "^NSEBANK", "emoji": "🏦"},
    "Pharma":       {"symbol": "^CNXPHARMA","emoji": "💊"},
    "Auto":         {"symbol": "^CNXAUTO", "emoji": "🚗"},
    "FMCG":         {"symbol": "^CNXFMCG", "emoji": "🛒"},
    "Metal":        {"symbol": "^CNXMETAL","emoji": "⚙️"},
    "Energy":       {"symbol": "^CNXENERGY","emoji": "⚡"},
    "Realty":       {"symbol": "^CNXREALTY","emoji": "🏠"},
    "Media":        {"symbol": "^CNXMEDIA","emoji": "📺"},
    "Financial Svcs":{"symbol": "^CNXFIN",  "emoji": "💰"},
    "PSU Bank":     {"symbol": "^CNXPSUBANK","emoji": "🏛️"},
    "Healthcare":   {"symbol": "^CNXHEALTH","emoji": "🏥"},
}

# ── COLOUR HELPERS (same as heatmap_generator.py) ─────────────────
BG         = (0,   0,   0)
HDR_GREEN  = (0, 153,  51)
WHITE      = (255, 255, 255)
GREY       = (150, 150, 150)

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

def _load_fonts() -> dict:
    base = "/usr/share/fonts/truetype/dejavu/"
    bold = base + "DejaVuSans-Bold.ttf"
    reg  = base + "DejaVuSans.ttf"
    def tf(path, size):
        try: return ImageFont.truetype(path, size)
        except: return ImageFont.load_default()
    return {
        "title":   tf(bold, 24),
        "section": tf(bold, 16),
        "label":   tf(bold, 13),
        "pct":     tf(bold, 16),
        "small":   tf(reg,  11),
        "emoji":   tf(reg,  18),
    }

def _fetch_sector_data() -> dict:
    """Batch fetch all Nifty sector indices"""
    symbols = [v["symbol"] for v in NIFTY_SECTORS.values()]
    results = {}

    try:
        raw = yf.download(
            tickers=symbols,
            period="5d",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        for sector, info in NIFTY_SECTORS.items():
            sym = info["symbol"]
            try:
                if len(symbols) > 1:
                    col_data = raw[sym]["Close"].dropna() if sym in raw.columns.get_level_values(0) else pd.Series()
                else:
                    col_data = raw["Close"].dropna()

                if len(col_data) >= 2:
                    prev    = float(col_data.iloc[-2])
                    curr    = float(col_data.iloc[-1])
                    change  = ((curr - prev) / prev) * 100
                elif len(col_data) == 1:
                    curr   = float(col_data.iloc[-1])
                    change = 0.0
                else:
                    raise ValueError("No data")

                results[sector] = {
                    "symbol":     sym,
                    "price":      round(curr, 2),
                    "change_pct": round(change, 2),
                    "emoji":      info["emoji"],
                    "ok":         True,
                }
            except Exception as e:
                results[sector] = {
                    "symbol":     sym,
                    "price":      0.0,
                    "change_pct": 0.0,
                    "emoji":      info["emoji"],
                    "ok":         False,
                    "error":      str(e),
                }
    except Exception as e:
        print(f"⚠️  Sector data batch failed: {e}")
        for sector, info in NIFTY_SECTORS.items():
            results[sector] = {
                "symbol": info["symbol"],
                "price": 0.0, "change_pct": 0.0,
                "emoji": info["emoji"], "ok": False,
            }

    return results

def _fetch_watchlist_heatmap_data(symbols: list) -> dict:
    """Batch fetch watchlist stocks for heatmap"""
    results = {}
    try:
        raw = yf.download(
            tickers=symbols,
            period="5d",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        for sym in symbols:
            try:
                if len(symbols) > 1:
                    col_d = raw[sym]["Close"].dropna() if sym in raw.columns.get_level_values(0) else pd.Series()
                else:
                    col_d = raw["Close"].dropna()

                if len(col_d) >= 2:
                    prev   = float(col_d.iloc[-2])
                    curr   = float(col_d.iloc[-1])
                    change = ((curr - prev) / prev) * 100
                elif len(col_d) == 1:
                    curr   = float(col_d.iloc[-1])
                    change = 0.0
                else:
                    raise ValueError("No data")

                display = sym.replace(".NS", "").replace(".BO", "")
                results[display] = {
                    "symbol":     sym,
                    "price":      round(curr, 2),
                    "change_pct": round(change, 2),
                    "ok":         True,
                }
            except Exception as e:
                display = sym.replace(".NS", "").replace(".BO", "")
                results[display] = {
                    "symbol": sym, "price": 0.0,
                    "change_pct": 0.0, "ok": False,
                }
    except Exception as e:
        print(f"⚠️  Watchlist heatmap batch failed: {e}")
        for sym in symbols:
            display = sym.replace(".NS", "").replace(".BO", "")
            results[display] = {
                "symbol": sym, "price": 0.0,
                "change_pct": 0.0, "ok": False,
            }

    return results

def _draw_grid_heatmap(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    items: list,            # list of (label, data_dict)
    y_start: int,
    F: dict,
    cols: int = 4,
    card_w: int = 200,
    card_h: int = 90,
    pad: int = 10,
) -> int:
    """
    Generic grid renderer for sector/watchlist heatmap cards.
    Returns final y position after drawing.
    """
    IMG_W = img.width
    n_rows = (len(items) + cols - 1) // cols
    total_row_w = cols * card_w + (cols - 1) * pad
    x_start = (IMG_W - total_row_w) // 2

    y = y_start
    with Pilmoji(img) as pilmoji:
        for row_i in range(n_rows):
            row_items = items[row_i * cols: (row_i + 1) * cols]
            for col_i, (label, data) in enumerate(row_items):
                x      = x_start + col_i * (card_w + pad)
                pct    = data.get("change_pct", 0.0)
                price  = data.get("price",      0.0)
                emoji  = data.get("emoji",       "")
                bg     = _cell_bg(pct)
                tc     = _text_color(pct)

                # Card
                draw.rounded_rectangle(
                    [(x, y), (x + card_w, y + card_h)],
                    radius=8, fill=bg,
                )

                # Emoji (if present)
                if emoji:
                    pilmoji.text(
                        (x + 8, y + 6), emoji,
                        fill=tc, font=F["emoji"],
                        emoji_scale_factor=1.2,
                    )

                # Label
                draw.text(
                    (x + card_w // 2, y + 10),
                    label[:18],
                    fill=tc, font=F["label"], anchor="mt",
                )

                # Price
                draw.text(
                    (x + card_w // 2, y + 32),
                    f"₹{price:,.0f}" if price > 0 else "—",
                    fill=tc, font=F["small"], anchor="mt",
                )

                # % change (largest text)
                sign = "+" if pct >= 0 else ""
                draw.text(
                    (x + card_w // 2, y + 52),
                    f"{sign}{pct:.2f}%",
                    fill=tc, font=F["pct"], anchor="mt",
                )

            y += card_h + pad

    return y + 10

def generate_sector_heatmap() -> BytesIO:
    """
    Generate India Sector Heatmap (Nifty sector indices).
    Returns PNG BytesIO ready for Telegram.
    """
    print("🏭 Generating sector heatmap...")
    sector_data = _fetch_sector_data()

    items   = sorted(
        [(k, v) for k, v in sector_data.items() if v.get("ok")],
        key=lambda x: x[1]["change_pct"],
        reverse=True,
    )
    cols    = 4
    card_w  = 200
    card_h  = 95
    pad     = 10
    n_rows  = (len(items) + cols - 1) // cols
    IMG_W   = 900
    IMG_H   = 120 + n_rows * (card_h + pad) + 40

    img  = Image.new("RGB", (IMG_W, IMG_H), BG)
    draw = ImageDraw.Draw(img)
    F    = _load_fonts()

    ist    = datetime.now(pytz.timezone("Asia/Kolkata"))
    y      = 15

    draw.text((IMG_W // 2, y), "India Sector Heatmap",
              fill=WHITE, font=F["title"], anchor="mt")
    y += 35

    draw.text((IMG_W // 2, y),
              ist.strftime("As of %d-%b-%Y %H:%M IST"),
              fill=GREY, font=F["small"], anchor="mt")
    y += 25

    # Best/worst bar
    valid = [(k, v) for k, v in sector_data.items() if v.get("ok")]
    if valid:
        best  = max(valid, key=lambda x: x[1]["change_pct"])
        worst = min(valid, key=lambda x: x[1]["change_pct"])
        summary = (
            f"🟢 Best: {best[0]} ({best[1]['change_pct']:+.2f}%)   "
            f"🔴 Worst: {worst[0]} ({worst[1]['change_pct']:+.2f}%)"
        )
        draw.text((IMG_W // 2, y), summary,
                  fill=GREY, font=F["small"], anchor="mt")
        y += 25

    y = _draw_grid_heatmap(
        img, draw, items, y, F,
        cols=cols, card_w=card_w, card_h=card_h, pad=pad,
    )

    img = img.crop((0, 0, IMG_W, y + 15))
    buf = BytesIO()
    buf.name = "sector_heatmap.png"
    img.save(buf, "PNG", optimize=True)
    buf.seek(0)
    return buf

def generate_watchlist_heatmap(symbols: list) -> BytesIO:
    """
    Generate Watchlist Heatmap — your personal stocks.
    Returns PNG BytesIO ready for Telegram.
    """
    print("📊 Generating watchlist heatmap...")
    wl_data = _fetch_watchlist_heatmap_data(symbols)

    items = sorted(
        [(k, v) for k, v in wl_data.items() if v.get("ok")],
        key=lambda x: x[1]["change_pct"],
        reverse=True,
    )
    cols   = 4
    card_w = 200
    card_h = 95
    pad    = 10
    n_rows = (len(items) + cols - 1) // cols
    IMG_W  = 900
    IMG_H  = 120 + n_rows * (card_h + pad) + 40

    img  = Image.new("RGB", (IMG_W, IMG_H), BG)
    draw = ImageDraw.Draw(img)
    F    = _load_fonts()

    ist = datetime.now(pytz.timezone("Asia/Kolkata"))
    y   = 15

    draw.text((IMG_W // 2, y), "My Watchlist Heatmap",
              fill=WHITE, font=F["title"], anchor="mt")
    y += 35
    draw.text((IMG_W // 2, y),
              ist.strftime("As of %d-%b-%Y %H:%M IST"),
              fill=GREY, font=F["small"], anchor="mt")
    y += 30

    y = _draw_grid_heatmap(
        img, draw, items, y, F,
        cols=cols, card_w=card_w, card_h=card_h, pad=pad,
    )

    img = img.crop((0, 0, IMG_W, y + 15))
    buf = BytesIO()
    buf.name = "watchlist_heatmap.png"
    img.save(buf, "PNG", optimize=True)
    buf.seek(0)
    return buf