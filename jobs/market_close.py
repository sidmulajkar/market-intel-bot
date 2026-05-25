import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_fetcher    import fetch_global_indices, fetch_top_movers, fetch_general_news, fetch_macro_anchors
from src.formatters      import format_top_movers
from src.ai_engine       import AIEngine
from src.telegram_sender import send_text
from src.db              import was_alert_sent, log_alert_sent
from src.validator       import validate_articles, assess_sentiment_consensus
from src.validation_helper import ai_generate_and_validate, build_ground_truth_from_index

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

    # ── Get bull/bear context + build ground truth ─────────────────
    bull_bear = {}
    ground_truth = {}
    try:
        from src.context_engine import run_contextualization
        anchor_data = fetch_macro_anchors()
        if anchor_data:
            ctx = run_contextualization(anchor_data)
            bull_bear = ctx.get("bull_bear", {})
            # Build ground truth for validation
            gt_extra = {}
            if bull_bear.get("score") is not None:
                gt_extra["bull_bear_score"] = bull_bear["score"]
            if ctx.get("flow_metrics", {}).get("ok"):
                fm = ctx["flow_metrics"]
                gt_extra["fii_net"] = fm.get("fii_net")
                gt_extra["dii_net"] = fm.get("dii_net")
            if ctx.get("vix_context", {}).get("ok"):
                gt_extra["india_vix"] = ctx["vix_context"].get("vix_price")
            for a in anchor_data:
                name = a.get("name", "")
                if name == "Brent Crude" and a.get("ok") and a.get("price"):
                    gt_extra["brent"] = a["price"]
                elif name == "Gold" and a.get("ok") and a.get("price"):
                    gt_extra["gold"] = a["price"]
            ground_truth = build_ground_truth_from_index(valid_index, gt_extra if gt_extra else None)
    except Exception as e:
        print(f"   ⚠️ Context engine: {e}")

    # ── Big move alerts (computed before AI call — needed for fallback) ──
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

    # ── AI market summary (with universal validation) ──────────────
    print("🤖 Generating market summary...")
    summary = ""
    try:
        prompt = AIEngine.eod_market_prompt(
            movers, valid_index, validated_news, consensus, bull_bear
        )
    except Exception as e:
        print(f"   ⚠️ Prompt build failed: {e}")
        prompt = ""

    nifty = valid_index.get("Nifty 50", {})
    vix   = valid_index.get("India VIX", {})
    header_parts = []
    if nifty:
        header_parts.append(f"Nifty {nifty.get('price', 0):,.0f} ({nifty.get('change_pct', 0):+.1f}%)")
    if vix and vix.get("price"):
        header_parts.append(f"VIX {vix.get('price', 0):.1f}")
    header = " | ".join(header_parts) if header_parts else "Market Close"

    def make_fallback():
        fb = f"🔔 *END OF DAY SUMMARY*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n📊 {header}\n\n"
        fb += format_top_movers(movers)
        if big_moves:
            fb += f"\n\n⚠️ *Big Moves (5%+):*\n" + "\n".join(big_moves)
        fb += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n_See you tomorrow! 🌙_"
        return fb

    def send_eod(text):
        msg = f"🔔 *END OF DAY SUMMARY*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n📊 {header}\n\n"
        msg += text + "\n\n"
        msg += format_top_movers(movers)
        if big_moves:
            msg += f"\n\n⚠️ *Big Moves (5%+):*\n" + "\n".join(big_moves)
        msg += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n_See you tomorrow! 🌙_"
        send_text(msg)

    if prompt and ground_truth.get("nifty_close"):
        ai_generate_and_validate(
            ai, "volume", prompt, ground_truth,
            output_type="market_close",
            fallback_fn=make_fallback,
            send_fn=send_eod,
            max_retries=1,
        )
    else:
        # No ground truth — send without AI validation (degraded)
        msg = f"🔔 *END OF DAY SUMMARY*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n📊 {header}\n\n"
        if summary:
            msg += summary + "\n\n"
        msg += format_top_movers(movers)
        if big_moves:
            msg += f"\n\n⚠️ *Big Moves (5%+):*\n" + "\n".join(big_moves)
        msg += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n_See you tomorrow! 🌙_"
        send_text(msg)
    print("✅ MARKET CLOSE COMPLETE")

if __name__ == "__main__":
    main()
