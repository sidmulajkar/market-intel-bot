"""
Sector + Watchlist Heatmap Generator
Fixed: yfinance batch column access using _safe_series helper
"""
import time
import pandas as pd
import yfinance as yf
from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji
from io import BytesIO
from datetime import datetime
import pytz

try:
    from pilmoji import Pilmoji
    PILMOJI_OK = True
except ImportError:
    PILMOJI_OK = False

NIFTY_SECTORS = {
    "IT":             {"symbol": "^CNXIT",    "emoji": "💻"},
    "Bank":           {"symbol": "^NSEBANK",  "emoji": "🏦"},
    "Pharma":         {"symbol": "^CNXPHARMA","emoji": "💊"},
    "Auto":           {"symbol": "^CNXAUTO",  "emoji": "🚗"},
    "FMCG":           {"symbol": "^CNXFMCG",  "emoji": "🛒"},
    "Metal":          {"symbol": "^CNXMETAL", "emoji": "⚙️"},
    "Energy":         {"symbol": "^CNXENERGY","emoji": "⚡"},
    "Realty":         {"symbol": "^CNXREALTY","emoji": "🏠"},
    "Financial Svcs": {"symbol": "^CNXFIN",   "emoji": "💰"},
    "PSU Bank":       {"symbol": "^CNXPSUBANK","emoji": "🏛️"},
    "Healthcare":     {"symbol": "^CNXHEALTH","emoji": "🏥"},
    "Media":          {"symbol": "^CNXMEDIA", "emoji": "📺"},
}

BG        = (0,   0,   0)
HDR_GREEN = (0, 153,  51)
WHITE     = (255, 255, 255)
GREY      = (150, 150, 150)

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
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            return ImageFont.load_default()
    return {
        "title":  tf(bold, 22),
        "label":  tf(bold, 13),
        "pct":    tf(bold, 16),
        "small":  tf(reg,  11),
        "emoji":  tf(reg,  16),
    }

def _safe_close(raw: pd.DataFrame, symbol: str, symbols: list) -> pd.Series:
    """BUG FIX: Same safe series helper as data_fetcher.py"""
    try:
        if isinstance(raw.columns, pd.MultiIndex):
            if symbol in raw.columns.get_level_values(0):
                return raw[symbol]["Close"].dropna()
            return pd.Series(dtype=float)
        else:
            return raw["Close"].dropna() if "Close" in raw.columns else pd.Series(dtype=float)
    except Exception:
        return pd.Series(dtype=float)

def _fetch_batch(symbols: list) -> dict:
    """Fetch batch price data with safe column access"""
    results = {}
    if not symbols:
        return results
    try:
        raw = yf.download(
            tickers=symbols, period="5d", interval="1d",
            group_by="ticker", auto_adjust=True,
            progress=False, threads=True,
        )
        for sym in symbols:
            try:
                s = _safe_close(raw, sym, symbols)
                if len(s) >= 2:
                    prev = float(s.iloc[-2])
                    curr = float(s.iloc[-1])
                    results[sym] = {
                        "price":      round(curr, 2),
                        "change_pct": round(((curr - prev) / prev) * 100, 2),
                        "ok":         True,
                    }
                elif len(s) == 1:
                    results[sym] = {
                        "price":      round(float(s.iloc[-1]), 2),
                        "change_pct": 0.0, "ok": True,
                    }
                else:
                    results[sym] = {"price": 0.0, "change_pct": 0.0, "ok": False}
            except Exception as e:
                results[sym] = {"price": 0.0, "change_pct": 0.0,
                                "ok": False, "error": str(e)}
    except Exception as e:
        print(f"⚠️  Batch fetch failed: {e}")
    return results

def _make_heatmap_image(title: str, items: list,
                         cols: int = 4,
                         card_w: int = 200,
                         card_h: int = 95,
                         pad: int = 10) -> BytesIO:
    """Generic heatmap grid renderer"""
    F      = _load_fonts()
    IMG_W  = 900
    n_rows = (len(items) + cols - 1) // cols
    IMG_H  = 100 + n_rows * (card_h + pad) + 30

    img  = Image.new("RGB", (IMG_W, IMG_H), BG)
    draw = ImageDraw.Draw(img)

    ist = datetime.now(pytz.timezone("Asia/Kolkata"))
    y   = 15
    draw.text((IMG_W // 2, y), title,
              fill=WHITE, font=F["title"], anchor="mt")
    y += 32
    draw.text((IMG_W // 2, y),
              ist.strftime("As of %d-%b-%Y %H:%M IST"),
              fill=GREY, font=F["small"], anchor="mt")
    y += 28

    def draw_cards(y):
        for row_i in range(n_rows):
            row_items = items[row_i * cols: (row_i + 1) * cols]
            tot_w     = len(row_items) * card_w + (len(row_items) - 1) * pad
            x0        = (IMG_W - tot_w) // 2

            for col_i, (label, data, extra) in enumerate(row_items):
                x   = x0 + col_i * (card_w + pad)
                pct = data.get("change_pct", 0.0)
                bg  = _cell_bg(pct)
                tc  = _text_color(pct)

                draw.rounded_rectangle(
                    [(x, y), (x + card_w, y + card_h)],
                    radius=8, fill=bg)

                # Extra text (emoji or code) on top left
                if extra:
                    draw.text((x + 6, y + 6), extra,
                              fill=tc, font=F["small"])

                draw.text((x + card_w // 2, y + 12), label[:16],
                          fill=tc, font=F["label"], anchor="mt")

                price = data.get("price", 0)
                if price > 0:
                    draw.text((x + card_w // 2, y + 34),
                              f"{price:,.0f}",
                              fill=tc, font=F["small"], anchor="mt")

                sign = "+" if pct >= 0 else ""
                draw.text((x + card_w // 2, y + 52),
                          f"{sign}{pct:.2f}%",
                          fill=tc, font=F["pct"], anchor="mt")

            y += card_h + pad
        return y

    y = draw_cards(y)

    img = img.crop((0, 0, IMG_W, y + 15))
    buf = BytesIO()
    buf.name = "heatmap.png"
    img.save(buf, "PNG", optimize=True)
    buf.seek(0)
    return buf

def generate_sector_heatmap() -> BytesIO:
    """Generate India Sector Heatmap"""
    print("🏭 Fetching sector data...")
    symbols    = [v["symbol"] for v in NIFTY_SECTORS.values()]
    raw_data   = _fetch_batch(symbols)
    sym_to_sec = {v["symbol"]: k for k, v in NIFTY_SECTORS.items()}

    items = []
    for sym, data in raw_data.items():
        sector = sym_to_sec.get(sym, sym)
        emoji  = NIFTY_SECTORS.get(sector, {}).get("emoji", "")
        items.append((sector, data, emoji))

    items.sort(key=lambda x: x[1].get("change_pct", 0), reverse=True)

    print(f"  ✅ Sector data: {sum(1 for _, d, _ in items if d.get('ok'))}/{len(items)} fetched")
    return _make_heatmap_image("India Sector Heatmap", items, cols=4)

def generate_watchlist_heatmap(symbols: list) -> BytesIO:
    """Generate Watchlist Heatmap"""
    print("📊 Fetching watchlist heatmap data...")
    raw_data = _fetch_batch(symbols)

    items = []
    for sym in symbols:
        data    = raw_data.get(sym, {"price": 0, "change_pct": 0, "ok": False})
        display = sym.replace(".NS", "").replace(".BO", "")
        items.append((display, data, ""))

    items.sort(key=lambda x: x[1].get("change_pct", 0), reverse=True)
    print(f"  ✅ Watchlist heatmap: {sum(1 for _, d, _ in items if d.get('ok'))}/{len(items)} fetched")
    return _make_heatmap_image("My Watchlist Heatmap", items, cols=4)