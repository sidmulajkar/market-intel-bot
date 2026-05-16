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

from src.data_fetcher   import fetch_global_indices, fetch_macro_anchors, fetch_watchlist_data, fetch_general_news, fetch_indian_news
from src.formatters     import format_global_indices, format_macro_anchors, format_flows, format_news, format_watchlist, format_mf_flows, format_context_block, format_options_block, format_insider_activity
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

    # ── MARKET BREADTH ───────────────────────────────────────────
    print("🔄 MARKET BREADTH")
    breadth = None
    try:
        from src.data_fetcher import fetch_market_breadth, format_market_breadth
        breadth = fetch_market_breadth()
        # Save breadth snapshot for historical percentile
        if breadth and breadth.get("advances") and breadth.get("declines"):
            from src.db import save_breadth_snapshot, today_str
            adv = breadth["advances"]
            dec = breadth["declines"]
            ratio = round(adv / dec, 2) if dec > 0 else 0
            save_breadth_snapshot(today_str(), adv, dec, ratio)
        breadth_str = format_market_breadth(breadth)
        if breadth_str:
            blocks["block_1"] = blocks.get("block_1", "") + "\n\n" + breadth_str
            print(f"   → Breadth: {len(breadth_str)} chars")
    except Exception as e:
        print(f"   ⚠️ Breadth: {e}")

    # ── BLOCK 2: Macro Anchors ───────────────────────────────────
    print("🔄 BLOCK 2: Macro Anchors")
    try:
        anchor_data = fetch_macro_anchors()
        blocks["block_2"] = format_macro_anchors(anchor_data)
        print(f"   → {len(blocks['block_2'])} chars")
    except Exception as e:
        print(f"   ⚠️ {e}")

    # ── VALUATION METRICS (append to Block 2) ────────────────────
    print("🔄 VALUATION (P/E, P/B, Risk Premium)")
    try:
        from src.formatters import format_valuation_block
        val_str = format_valuation_block()
        if val_str:
            blocks["block_2"] = blocks.get("block_2", "") + "\n\n" + val_str
            print(f"   → Valuation: {len(val_str)} chars")
    except Exception as e:
        print(f"   ⚠️ Valuation: {e}")
        anchor_data = None
        blocks["block_2"] = ""

    # ── NIFTY TECHNICAL ANALYSIS ──────────────────────────────────
    print("🔄 NIFTY TECHNICAL LEVELS")
    nifty_closes = []
    try:
        import yfinance as yf
        from src.technical_analysis import compute_full_analysis, format_technical_analysis
        nifty_hist = yf.Ticker("^NSEI").history(period="1y")["Close"].dropna()
        if len(nifty_hist) >= 20:
            nifty_closes = nifty_hist.tolist()
            nifty_ta = compute_full_analysis(nifty_closes, "NIFTY 50")
            nifty_ta_str = format_technical_analysis(nifty_ta)
            if nifty_ta_str:
                # Promote 200-DMA distance to headline in Block 1
                ma200_dist = nifty_ta.get("ma200_dist_pct")
                if ma200_dist is not None:
                    trend_label = "above" if ma200_dist > 0 else "below"
                    headline_ta = f"📍 Nifty 50: {trend_label} 200-DMA by {abs(ma200_dist):.1f}%"
                    blocks["block_1"] = blocks.get("block_1", "") + "\n" + headline_ta
                # Append full TA below
                blocks["block_1"] = blocks.get("block_1", "") + "\n\n" + nifty_ta_str
                print(f"   → Nifty TA: {len(nifty_ta_str)} chars")
    except Exception as e:
        print(f"   ⚠️ Nifty TA: {e}")

    # ── CONTEXT BLOCK: Bull/Bear Score ─────────────────────────────
    print("🔄 CONTEXT: Bull/Bear Score")
    try:
        if anchor_data:
            # Gather extra signals from already-fetched data
            extra_signals = {}
            # Market breadth
            if breadth and isinstance(breadth, dict):
                adv = breadth.get("advances", 0)
                dec = breadth.get("declines", 0)
                if dec > 0:
                    extra_signals["breadth_ratio"] = round(adv / dec, 2)
            # Nifty vs 200-DMA
            if nifty_closes and len(nifty_closes) >= 200:
                from src.technical_analysis import compute_moving_averages
                ma_data = compute_moving_averages(nifty_closes)
                if ma_data.get("ma200_dist_pct") is not None:
                    extra_signals["nifty_vs_ma200_pct"] = ma_data["ma200_dist_pct"]
            # PCR from options engine (fetched directly, not from formatted block)
            try:
                from src.options_engine import run_options_analysis
                pcr_data = run_options_analysis("NIFTY", store=False, run_label="context")
                if pcr_data and pcr_data.get("pcr") is not None:
                    extra_signals["pcr"] = pcr_data["pcr"]
            except Exception:
                pass  # Non-critical

            context_output = format_context_block(anchor_data, extra_signals=extra_signals)
            blocks["block_0"] = context_output
            blocks["block_context"] = context_output
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
        blocks["block_5"] = options_output  # Wire to {block_5} in master_prompt.txt
        print(f"   → {len(options_output)} chars")
    except Exception as e:
        print(f"   ⚠️ Options engine: {e}")
        blocks["block_5"] = ""

    # ── FII/DII F&O POSITIONING ──────────────────────────────────
    print("🔄 F&O PARTICIPANT POSITIONING")
    try:
        from src.fii_derivatives import run_fno_analysis
        fno_output = run_fno_analysis()
    except Exception as e:
        print(f"   ⚠️ F&O positioning: {e}")
        fno_output = ""

    # ── BLOCK 4: FII/DII Flows ───────────────────────────────────
    print("🔄 BLOCK 4: Flow Intelligence")
    try:
        blocks["block_4"] = format_flows()
        # Append F&O positioning to Block 4
        if fno_output:
            blocks["block_4"] = blocks["block_4"] + "\n\n" + fno_output
        print(f"   → {len(blocks['block_4'])} chars")
    except Exception as e:
        print(f"   ⚠️ {e}")
        blocks["block_4"] = ""

    # ── BLOCK 6: News (Global + Indian) ───────────────────────────
    print("🔄 BLOCK 6: News Intelligence")
    try:
        ai = AIEngine()

        # Global news (Finnhub)
        raw_global = fetch_general_news()
        global_validated = validate_articles(raw_global, min_trust=6) if raw_global else []
        for article in global_validated[:5]:
            article["sentiment"] = ai.sentiment(article.get("headline", ""))

        # Indian news (RSS)
        raw_indian = fetch_indian_news()
        indian_validated = validate_articles(raw_indian, min_trust=4) if raw_indian else []
        for article in indian_validated[:5]:
            article["sentiment"] = ai.sentiment(article.get("headline", ""))

        blocks["block_6"] = format_news(global_validated, indian_validated)
        print(f"   → {len(blocks['block_6'])} chars ({len(global_validated)} global, {len(indian_validated)} indian)")
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

    # ── SHAREHOLDING QoQ CHANGES (evening only, top 5 stocks) ────
    if mode == "evening" and blocks.get("block_8"):
        print("🔄 SHAREHOLDING PATTERN (QoQ)")
        try:
            from src.shareholding_tracker import track_all_watchlist_shareholding
            if watchlist:
                sh_results = track_all_watchlist_shareholding(watchlist[:5])
                sig_changes = [r for r in sh_results if r.get("has_significant_change")]
                if sig_changes:
                    sh_lines = ["\n📊 *Shareholding QoQ Changes:*"]
                    for r in sig_changes:
                        for c in r["changes"][:2]:
                            sig = "🚨" if c.get("significant") else "⚠️"
                            sh_lines.append(
                                f"{sig} {r['symbol']}: {c['category'][:25]} "
                                f"{c['previous']:.1f}%→{c['current']:.1f}% ({c['delta']:+.1f}%)"
                            )
                    blocks["block_8"] += "\n" + "\n".join(sh_lines)
                    print(f"   → {len(sig_changes)} stocks with significant QoQ changes")
                else:
                    print("   → No significant QoQ changes")
        except Exception as e:
            print(f"   ⚠️ Shareholding: {e}")

    # ── BLOCK 3: Sector FPI Activity ─────────────────────────────
    print("🔄 BLOCK 3: Sector FPI Activity")
    try:
        from src.fii_sector import run_sector_fpi_analysis
        blocks["block_3"] = run_sector_fpi_analysis()
        print(f"   → {len(blocks['block_3'])} chars")
    except Exception as e:
        print(f"   ⚠️ {e}")
        blocks["block_3"] = ""

    # ── BLOCK 7: Insider Activity ────────────────────────────────
    print("🔄 BLOCK 7: Insider Activity")
    try:
        blocks["block_7"] = format_insider_activity()
        print(f"   → {len(blocks['block_7'])} chars")
    except Exception as e:
        print(f"   ⚠️ {e}")
        blocks["block_7"] = ""

    # ── BLOCK 9: Macro Calendar ─────────────────────────────────────
    print("🔄 BLOCK 9: Macro Calendar")
    try:
        from src.macro_fetcher import format_macro_block
        blocks["block_9"] = format_macro_block()
        if blocks["block_9"]:
            print(f"   → Macro: {len(blocks['block_9'])} chars")
    except Exception as e:
        print(f"   ⚠️ Macro calendar: {e}")
        blocks["block_9"] = ""

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