import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_fetcher    import fetch_global_indices, fetch_top_movers, fetch_general_news, fetch_macro_anchors
from src.formatters      import format_top_movers
from src.ai_engine       import AIEngine
from src.telegram_sender import send_text
from src.db              import was_alert_sent, log_alert_sent
from src.validator       import validate_articles, assess_sentiment_consensus

def main():
    print("=" * 50)
    print("🔔 MARKET CLOSE STARTING")
    print("=" * 50)

    # ── Fetch market data ──────────────────────────────────────────
    print("📊 Fetching top movers + global indices + news...")
    movers     = fetch_top_movers(top_n=10)
    index_data = fetch_global_indices()
    raw_news   = fetch_general_news()

    valid_index = {
        k: v for k, v in index_data.items()
        if v.get("ok") and v.get("price", 0) > 0
    }
    print(f"   Movers: {len(movers.get('india',{}).get('gainers',[]))} India gainers, "
          f"{len(movers.get('us',{}).get('gainers',[]))} US gainers")

    # ── Validate news + sentiment ──────────────────────────────────
    ai = AIEngine()
    validated_news = validate_articles(raw_news, min_trust=6) if raw_news else []
    sentiments = []
    for article in validated_news[:5]:
        sent = ai.sentiment(article.get("headline", ""))
        article["sentiment"] = sent
        if sent:
            sentiments.append(sent)
    consensus = assess_sentiment_consensus(sentiments) if sentiments else "neutral"

    # ── Get bull/bear context ──────────────────────────────────────
    bull_bear = {}
    try:
        from src.context_engine import run_contextualization
        anchor_data = fetch_macro_anchors()
        if anchor_data:
            ctx = run_contextualization(anchor_data)
            bull_bear = ctx.get("bull_bear", {})
    except Exception as e:
        print(f"   ⚠️ Context engine: {e}")

    # ── AI market summary ──────────────────────────────────────────
    print("🤖 Generating market summary...")
    try:
        prompt  = AIEngine.eod_market_prompt(
            movers, valid_index, validated_news, consensus, bull_bear
        )
        summary = ai.analyze("volume", prompt)
    except Exception as e:
        print(f"   ⚠️ AI failed: {e}")
        summary = ""

    # ── Build message ──────────────────────────────────────────────
    # Header with Nifty + VIX + FII context
    nifty = valid_index.get("Nifty 50", {})
    vix   = valid_index.get("India VIX", {})
    header_parts = []
    if nifty:
        header_parts.append(f"Nifty {nifty.get('price', 0):,.0f} ({nifty.get('change_pct', 0):+.1f}%)")
    if vix and vix.get("price"):
        header_parts.append(f"VIX {vix.get('price', 0):.1f}")
    header = " | ".join(header_parts) if header_parts else "Market Close"

    msg = f"🔔 *END OF DAY SUMMARY*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n📊 {header}\n\n"
    if summary:
        msg += summary + "\n\n"

    # Top movers formatted
    msg += format_top_movers(movers)

    # ── Big move alerts (from top movers, not watchlist) ───────────
    all_movers = (
        movers.get("india", {}).get("gainers", []) +
        movers.get("india", {}).get("losers", []) +
        movers.get("us", {}).get("gainers", []) +
        movers.get("us", {}).get("losers", [])
    )
    big_moves = []
    for m in all_movers:
        change = abs(m.get("change_pct", 0))
        sym    = m.get("symbol", "")
        if change >= 5.0:
            key = f"eod_bigmove_{sym}"
            if not was_alert_sent(sym, key):
                emoji = "🚀" if m.get("change_pct", 0) > 0 else "💥"
                big_moves.append(f"{emoji} *{sym}* {m['change_pct']:+.1f}%")
                log_alert_sent(sym, key)

    if big_moves:
        msg += f"\n\n⚠️ *Big Moves (5%+):*\n" + "\n".join(big_moves)

    msg += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n_See you tomorrow! 🌙_"
    send_text(msg)
    print("✅ MARKET CLOSE COMPLETE")

if __name__ == "__main__":
    main()
