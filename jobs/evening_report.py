import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_fetcher      import fetch_global_indices, fetch_general_news, fetch_macro_anchors
from src.heatmap_generator import generate_heatmap
from src.ai_engine         import AIEngine
from src.telegram_sender   import send_image, send_text
from src.validator         import validate_articles, assess_sentiment_consensus
from src.validation_helper import validate_and_send
from src.delta             import get_relevant_indices


def main():
    print("=" * 50)
    print("🌃 EVENING REPORT STARTING")
    print("=" * 50)

    index_data  = fetch_global_indices()
    valid_index = {k: v for k, v in index_data.items()
                   if v.get("ok") and v.get("price", 0) > 0}

    # ── Skip gate: is US session worth a full report? ─────────────
    us_evening = get_relevant_indices("20:00", valid_index)
    us_moved = False
    vix_changed = False

    if us_evening:
        for country, d in us_evening.items():
            if d.get("ok") and abs(d.get("change_pct", 0)) >= 0.5:
                us_moved = True
                break

    # Check VIX change vs Indian close baseline
    try:
        from src.db import get_latest_market_state
        prev = get_latest_market_state()
        if prev and prev.get("macro", {}).get("vix"):
            prev_vix = prev["macro"]["vix"]
            cboe_vix_entry = valid_index.get("CBOE VIX", {})
            if cboe_vix_entry.get("ok") and cboe_vix_entry.get("price"):
                curr_vix = cboe_vix_entry["price"]
                if prev_vix > 0 and abs(curr_vix - prev_vix) / prev_vix >= 0.10:
                    vix_changed = True
    except Exception:
        pass

    if not us_moved and not vix_changed:
        send_text("🟡 *Evening:* US session quiet (SPX flat, VIX unchanged). No shift to India outlook.")
        print("   🟡 Quiet US session — one-liner sent")
        print("✅ EVENING REPORT COMPLETE")
        return

    if us_moved:
        print(f"   ⚡ Skip gate: US moved significantly")
    if vix_changed:
        print(f"   ⚡ Skip gate: VIX changed >10%")

    # ── Fetch news + sentiment ─────────────────────────────────────
    news = fetch_general_news()
    ai = AIEngine()
    validated_news = validate_articles(news, min_trust=6) if news else []

    sentiments = []
    for article in validated_news[:5]:
        sent = ai.sentiment(article.get("headline", ""))
        article["sentiment"] = sent
        if sent:
            sentiments.append(sent)
    consensus_sentiment = assess_sentiment_consensus(sentiments) if sentiments else "neutral"

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

    # ── Build relevant global indices lines ────────────────────────
    lines = []
    if us_evening:
        for country, d in sorted(us_evening.items(), key=lambda x: abs(x[1].get("change_pct", 0)), reverse=True):
            sign = "+" if d.get("change_pct", 0) >= 0 else ""
            lines.append(f"{d.get('flag','')} {country}: {sign}{d.get('change_pct',0):.2f}% [{d.get('status','?')}]")
    else:
        # Fallback: show all valid indices
        for country, d in valid_index.items():
            sign = "+" if d.get("change_pct", 0) >= 0 else ""
            lines.append(f"{d.get('flag','')} {country}: {sign}{d.get('change_pct',0):.2f}%")

    # ── Nifty close recap ─────────────────────────────────────────
    nifty_close_line = ""
    nifty = valid_index.get("Nifty 50", {})
    if nifty.get("ok") and nifty.get("price"):
        n_change = nifty.get("change_pct", 0)
        sign = "+" if n_change >= 0 else ""
        nifty_close_line = f"📍 Nifty closed {nifty['price']:,.0f} ({sign}{n_change:.1f}%)"

    # ── AI evening brief ───────────────────────────────────────────
    news_block = ""
    if validated_news:
        news_lines = []
        for n in validated_news[:5]:
            headline = n.get("headline", "")[:60]
            trust = n.get("trust_score", 0)
            source = n.get("source", "unknown")
            news_lines.append(f"• {headline} ({source}, Trust:{trust}/10)")
        news_block = f"\nToday's news:\n{chr(10).join(news_lines)}\n"

    prompt = f"""
Evening global markets (US session):
{chr(10).join(lines)}
{nifty_close_line}
{news_block}

Market sentiment: {consensus_sentiment.upper()}

Evening report for Indian investors (base on actual data):
1. 🌃 US Session Direction + key driver
2. 🌍 Overnight Risk Setup
3. 🇮🇳 India Tomorrow Setup
4. 🎯 Bias: [Direction] unless [specific condition]
5. 📊 Key levels to watch

Under 150 words. Reference actual headlines. Single actionable bias line.
"""

    def make_fallback():
        parts = []
        if nifty_close_line:
            parts.append(nifty_close_line)
        parts.extend(lines[:5])
        if validated_news:
            top = validated_news[0]
            parts.append(f"📰 {top.get('headline', '')[:50]}...")
        return " | ".join(parts[:4])

    def send_evening(text):
        msg = "🌃 *EVENING REPORT*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        if nifty_close_line:
            msg += f"{nifty_close_line}\n\n"
        msg += text
        msg += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n_India outlook for tomorrow ↑_"
        send_text(msg)

    try:
        analysis = ai.analyze("fast", prompt)
    except Exception as e:
        analysis = ""

    # ── Heatmap: only if US moved significantly ────────────────────
    if us_moved:
        try:
            heatmap = generate_heatmap(valid_index)
            send_image(heatmap, caption="🌃 *Evening Global Heatmap — US Session Live*")
            print("   ✅ Evening heatmap sent")
        except Exception as e:
            print(f"   ⚠️ Heatmap failed: {e}")

    sent = validate_and_send(
        analysis, valid_index,
        fallback_fn=make_fallback,
        send_fn=send_evening,
    )
    if sent:
        print("   ✅ AI evening report sent")
    else:
        print("   ⚠️ AI evening report failed validation — sent fallback")

    print("✅ EVENING REPORT COMPLETE")

if __name__ == "__main__":
    main()
