"""
Market Intel — AI-powered market analysis
Modes: morning (blocks 1,2,4,6,8) or evening (all 10 blocks)
"""
import sys
import os

_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_dir)
if _root not in sys.path:
    sys.path.insert(0, _root)

import importlib.util
_spec = importlib.util.find_spec("src.data_fetcher")
if _spec is None:
    print(f"ERROR: src not found. sys.path = {sys.path}")
    sys.exit(1)

from src.data_fetcher   import fetch_global_indices, fetch_macro_anchors, fetch_watchlist_data, fetch_general_news
from src.formatters     import format_global_indices, format_macro_anchors, format_flows, format_news, format_watchlist, format_mf_flows
from src.ai_engine      import AIEngine
from src.telegram_sender import send_text
from src.db             import get_client
from src.validator      import validate_articles


# ── CLI ────────────────────────────────────────────────────────────
def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "morning"
    if mode not in ("morning", "evening"):
        print(f"Usage: python market_intel.py [morning|evening]")
        sys.exit(1)

    print("=" * 50)
    print(f"📊 MARKET INTEL ({mode.upper()}) STARTING")
    print("=" * 50)

    # Load master prompt
    try:
        with open("config/master_prompt.txt", "r") as f:
            master_template = f.read()
    except Exception as e:
        print(f"⚠️  Master prompt not found: {e}")
        send_text("⚠️ Market Intel: Configuration error.")
        return

    blocks = {}

    # ── BLOCK 1: Global Indices ───────────────────────────────────
    print("🔄 BLOCK 1: Global Indices")
    try:
        index_data = fetch_global_indices()
        blocks["block_1"] = format_global_indices(index_data)
        print(f"   → {len(blocks['block_1'])} chars")
    except Exception as e:
        print(f"   ⚠️ {e}")
        blocks["block_1"] = ""

    # ── BLOCK 2: Macro Anchors ───────────────────────────────────
    print("🔄 BLOCK 2: Macro Anchors")
    try:
        anchor_data = fetch_macro_anchors()
        blocks["block_2"] = format_macro_anchors(anchor_data)
        print(f"   → {len(blocks['block_2'])} chars")
    except Exception as e:
        print(f"   ⚠️ {e}")
        blocks["block_2"] = ""

    # ── BLOCK 4: FII/DII Flows ───────────────────────────────────
    print("🔄 BLOCK 4: Flow Intelligence")
    try:
        blocks["block_4"] = format_flows()
        print(f"   → {len(blocks['block_4'])} chars")
    except Exception as e:
        print(f"   ⚠️ {e}")
        blocks["block_4"] = ""

    # ── BLOCK 6: News ────────────────────────────────────────────
    print("🔄 BLOCK 6: News Intelligence")
    try:
        raw_news = fetch_general_news()
        validated = validate_articles(raw_news, min_trust=6) if raw_news else []
        # Get sentiment
        ai = AIEngine()
        for article in validated[:5]:
            sent = ai.sentiment(article.get("headline", ""))
            article["sentiment"] = sent
        blocks["block_6"] = format_news(validated)
        print(f"   → {len(blocks['block_6'])} chars")
    except Exception as e:
        print(f"   ⚠️ {e}")
        blocks["block_6"] = ""

    # ── BLOCK 8: Watchlist ───────────────────────────────────────
    print("🔄 BLOCK 8: Watchlist")
    try:
        from src.db import get_watchlist
        watchlist = get_watchlist()
        if watchlist:
            wl_data = fetch_watchlist_data(watchlist)
            blocks["block_8"] = format_watchlist(wl_data)
        else:
            blocks["block_8"] = ""
        print(f"   → {len(blocks['block_8'])} chars")
    except Exception as e:
        print(f"   ⚠️ {e}")
        blocks["block_8"] = ""

    # ── Evening-only blocks ──────────────────────────────────────
    blocks["block_3"] = ""  # Sector Performance (Phase 2)
    blocks["block_5"] = ""  # Derivatives (Phase 2)
    blocks["block_7"] = ""  # Insider Activity (Phase 2)
    blocks["block_9"] = ""  # Macro Calendar (Phase 2)

    if mode == "evening":
        # BLOCK 10: MF Flows
        print("🔄 BLOCK 10: MF Flows")
        try:
            blocks["block_10"] = format_mf_flows()
            print(f"   → {len(blocks['block_10'])} chars")
        except Exception as e:
            print(f"   ⚠️ {e}")
            blocks["block_10"] = ""
    else:
        blocks["block_10"] = ""

    # ── Assemble prompt ───────────────────────────────────────────
    print("🔄 Assembling prompt...")

    # Replace placeholders
    prompt = master_template
    for key, content in blocks.items():
        placeholder = f"{{{key}}}"
        if content.strip():
            prompt = prompt.replace(placeholder, content)
        else:
            # Remove the block header and placeholder
            # This is a simple approach - remove the placeholder line
            prompt = prompt.replace(f"[{key.upper().replace('_',' ')}]\n{placeholder}", "")
            prompt = prompt.replace(placeholder, "(No data available)")

    # Count non-empty blocks
    non_empty = sum(1 for v in blocks.values() if v.strip())
    print(f"   → {non_empty} blocks with data")

    # Total failure check
    if non_empty == 0:
        print("⚠️ All blocks empty — sending fallback")
        send_text("🚨 *Market Intel Unavailable*\n\nAll data sources failed.")
        return

    # ── AI Analysis ───────────────────────────────────────────────
    print("🔄 Running AI analysis (volume task)...")
    try:
        ai = AIEngine()
        analysis = ai.analyze("volume", prompt)
    except Exception as e:
        print(f"   ⚠️ AI failed: {e}")
        analysis = "⚠️ AI analysis temporarily unavailable."
        send_text(f"🚨 *Market Intel*\n\n{analysis}")
        return

    # ── Send Telegram ───────────────────────────────────────────
    ist_time = "🌅" if mode == "morning" else "🌃"
    header = f"{ist_time} *MARKET INTEL ({mode.upper()})*"

    send_text(f"{header}\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n{analysis}\n\n━━━━━━━━━━━━━━━━━━━━━━━━")
    print("✅ Market Intel sent")


if __name__ == "__main__":
    main()