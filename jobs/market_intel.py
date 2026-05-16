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
from src.formatters     import format_global_indices, format_macro_anchors, format_flows, format_news, format_watchlist, format_mf_flows, format_context_block, format_options_block
from src.context_engine import run_contextualization
from src.ai_engine      import AIEngine
from src.telegram_sender import send_text
from src.db             import get_client
from src.validator      import validate_articles



# AI Response Validation
def validate_ai_response(response: str, min_words: int = 50) -> bool:
    if not response or not isinstance(response, str):
        return False
    return len(response.split()) >= min_words


def get_market_intel_fallback(blocks: dict) -> str:
    lines = ["📊 *Market Intel (Fallback)*", "━━━━━━━━━━━━━━━━━━━━━━━━"]
    
    if blocks.get("block_1"):
        lines.append("\n🌍 *Global:*")
        for line in blocks["block_1"].split("\n")[:3]:
            if line.strip():
                lines.append(f"  {line}")
    
    if blocks.get("block_4"):
        lines.append("\n📈 *Flows:*")
        for line in blocks["block_4"].split("\n")[:3]:
            if line.strip():
                lines.append(f"  {line}")
    
    if blocks.get("block_6"):
        lines.append("\n📰 *News:*")
        for line in blocks["block_6"].split("\n")[:3]:
            if line.strip():
                lines.append(f"  {line}")
    
    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


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
        anchor_data = None
        blocks["block_2"] = ""

    # ── CONTEXT BLOCK: Bull/Bear Score ─────────────────────────────
    print("🔄 CONTEXT: Bull/Bear Score")
    try:
        if anchor_data:
            context_output = format_context_block(anchor_data)
            blocks["block_0"] = context_output  # Block 0 for MARKET POSTURE
            blocks["block_context"] = context_output  # Keep for reference
            print(f"   → {len(context_output)} chars (Bull/Bear context)")
        else:
            blocks["block_0"] = ""
            blocks["block_context"] = ""
    except Exception as e:
        print(f"   ⚠️ Context engine: {e}")
        blocks["block_0"] = ""
        blocks["block_context"] = ""

    # ── OPTIONS BLOCK: PCR, Max Pain, OI Zones ────────────────────
    print("🔄 OPTIONS: PCR, Max Pain, OI Zones")
    try:
        options_output = format_options_block(symbol="NIFTY", run_label=mode)
        blocks["block_options"] = options_output
        print(f"   → {len(options_output)} chars")
    except Exception as e:
        print(f"   ⚠️ Options engine: {e}")
        blocks["block_options"] = ""

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

    # Replace placeholders properly
    prompt = master_template
    block_headers = {
        "block_0": "[BLOCK 0: MARKET POSTURE — READ FIRST]",
        "block_1": "[BLOCK 1: GLOBAL INDICES]",
        "block_2": "[BLOCK 2: MACRO ANCHORS (USDINR, BRENT, GOLD)]",
        "block_context": "[CONTEXT: BULL/BEAR SCORE + MARKET NARRATIVE]",
        "block_options": "[OPTIONS: PCR, MAX PAIN, OI ZONES]",
        "block_3": "[BLOCK 3: SECTOR PERFORMANCE]",
        "block_4": "[BLOCK 4: FLOW INTELLIGENCE (FII/DII)]",
        "block_5": "[BLOCK 5: DERIVATIVES (PCR + MAX PAIN)]",
        "block_6": "[BLOCK 6: NEWS INTELLIGENCE — USE ONLY TRUST ≥ 6]",
        "block_7": "[BLOCK 7: INSIDER ACTIVITY]",
        "block_8": "[BLOCK 8: WATCHLIST — price, day_change%, volume_spike, MA20, 5D momentum, 1M return]",
        "block_9": "[BLOCK 9: MACRO CALENDAR (NEXT 7 DAYS)]",
        "block_10": "[BLOCK 10: MF FLOW INTELLIGENCE — category flows, anomaly vs 3M avg, thematic, top 5 gainers/losers, SIP trend]",
    }

    for key, content in blocks.items():
        placeholder = f"{{{key}}}"
        header = block_headers.get(key, f"[{key.upper()}]")

        if content.strip():
            prompt = prompt.replace(placeholder, content)
        else:
            # Remove both the header line AND the placeholder when empty
            # Need to remove: [BLOCK X: ...]\n{placeholder}
            import re
            prompt = re.sub(rf'{re.escape(header)}\n\s*{re.escape(placeholder)}', '', prompt)

    # Count non-empty blocks
    non_empty = sum(1 for v in blocks.values() if v.strip())
    print(f"   → {non_empty} blocks with data")

    # Count remaining placeholders
    remaining = prompt.count("{block_")
    print(f"   → {remaining} unfilled placeholders")

    # Total failure check - more lenient
    if non_empty == 0:
        print("⚠️ All blocks empty — sending fallback")
        # Try to send a simple message anyway using available data
        try:
            # Last resort: use global indices or watchlist if available
            from src.data_fetcher import fetch_global_indices
            idx = fetch_global_indices()
            if idx:
                lines = [f"{d.get('flag','')} {c}: {d.get('change_pct',0):+.2f}%"
                         for c, d in idx.items() if d.get("ok")][:8]
                send_text(f"🌅 *MARKET SNAPSHOT*\n━━━━━━━━━━━━━━━━━━━━━━━━\n" +
                          "\n".join(lines) + "\n\n━━━━━━━━━━━━━━━━━━━━━━━━")
                return
        except:
            pass
        send_text("🚨 *Market Intel Unavailable*\n\nNo data from any source.")
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
    # Validate AI response - never send blank
    if validate_ai_response(analysis, min_words=50):
        ist_time = "🌅" if mode == "morning" else "🌃"
        header = f"{ist_time} *MARKET INTEL ({mode.upper()})*"
        send_text(f"{header}\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n{analysis}\n\n━━━━━━━━━━━━━━━━━━━━━━━━")
        print("✅ Market Intel sent")
    else:
        # Fallback to raw formatted data
        fallback = get_market_intel_fallback(blocks)
        ist_time = "🌅" if mode == "morning" else "🌃"
        header = f"{ist_time} *MARKET INTEL ({mode.upper()})*"
        send_text(f"{header}\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n{fallback}\n\n━━━━━━━━━━━━━━━━━━━━━━━━")
        print("⚠️ AI response too short - sent fallback")


if __name__ == "__main__":
    main()