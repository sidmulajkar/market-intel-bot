import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_fetcher      import fetch_global_indices, fetch_general_news
from src.heatmap_generator import generate_heatmap
from src.ai_engine         import AIEngine
from src.telegram_sender   import send_image, send_text
from src.db                import get_watchlist
from src.validator        import validate_articles, assess_sentiment_consensus


def validate_ai_response(response: str, min_words: int = 50) -> bool:
    if not response or not isinstance(response, str):
        return False
    word_count = len(response.split())
    return word_count >= min_words


def get_fallback_evening(index_data: dict, validated_news: list, sentiment: str) -> str:
    lines = ["🌃 *Evening Global Report*", "_US Session Now Live_", "━━━━━━━━━━━━━━━━━━━━━━━━"]
    
    if index_data:
        lines.append("\n🌍 *Global Indices:*")
        for country, d in list(index_data.items())[:5]:
            if d.get("ok"):
                change = d.get("change_pct", 0)
                sign = "+" if change >= 0 else ""
                lines.append(f"  • {country}: {sign}{change:.2f}%")
    
    if validated_news:
        lines.append("\n📰 *Top Headlines:*")
        for article in validated_news[:3]:
            headline = article.get("headline", "")[:60]
            if headline:
                lines.append(f"  • {headline}...")
    
    if sentiment:
        lines.append(f"\n💭 *Sentiment:* {sentiment.title()}")
    
    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━\n_India outlook for tomorrow ↑_")
    return "\n".join(lines)


def main():
    print("=" * 50)
    print("🌃 EVENING REPORT STARTING")
    print("=" * 50)

    stocks      = get_watchlist()
    index_data  = fetch_global_indices()
    valid_index = {k: v for k, v in index_data.items()
                   if v.get("ok") and v.get("price", 0) > 0}

    try:
        heatmap = generate_heatmap(valid_index)
        send_image(heatmap, caption="🌃 *Evening Global Heatmap — US Session Live*")
        print("   ✅ Evening heatmap sent")
    except Exception as e:
        print(f"   ⚠️ Heatmap failed: {e}")

    lines = []
    for country, d in valid_index.items():
        sign = "+" if d.get("change_pct", 0) >= 0 else ""
        lines.append(f"{d.get('flag','')} {country}: {sign}{d.get('change_pct',0):.2f}% [{d.get('status','?')}]")

    # Fetch and validate news
    news = fetch_general_news()
    ai = AIEngine()
    validated_news = validate_articles(news, min_trust=6) if news else []

    # Get sentiment
    sentiments = []
    for article in validated_news[:5]:
        sent = ai.sentiment(article.get("headline", ""))
        article["sentiment"] = sent
        if sent:
            sentiments.append(sent)
    consensus_sentiment = assess_sentiment_consensus(sentiments) if sentiments else "neutral"

    # Format news for prompt
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
Evening global markets (US session just opened):
{chr(10).join(lines)}
{news_block}

Market sentiment: {consensus_sentiment.upper()}

Evening report for Indian investors (base on actual news):
1. 🌃 US Opening Direction + reason
2. 🌍 Global Risk Mood: Risk-on/Risk-off/Neutral
3. 🇮🇳 India Tomorrow Setup
4. 📊 Key levels to watch (not invented events)
5. 💡 Tomorrow's Strategy

Under 200 words. Reference actual headlines provided.
"""
    ai = AIEngine()
    try:
        analysis = ai.analyze("fast", prompt)
    except Exception as e:
        analysis = f"AI unavailable: {e}"

    # Build closing summary from global indices
    closing_lines = []
    nifty_close = None
    for country, d in valid_index.items():
        if country == "India" and d.get("price"):
            nifty_close = d.get("price")
            nifty_change = d.get("change_pct", 0)
            sign = "+" if nifty_change >= 0 else ""
            closing_lines.append(f"Nifty closed at {nifty_close:,.0f} ({sign}{nifty_change:.2f}%)")
            break
    
    closing_summary = ""
    if closing_lines:
        closing_summary = "\n\n📊 *EOD Summary:*\n" + "\n".join(closing_lines)
    
    send_text(
        "🌃 *EVENING GLOBAL REPORT*\n_US Session Now Live_\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        + analysis
        + closing_summary
        + "\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n_India outlook for tomorrow ↑_"
    )

    # ── Market State Dashboard ─────────────────────────────────────
    try:
        from src.data_fetcher import fetch_macro_anchors
        from src.context_engine import run_contextualization, compute_market_phase
        from src.formatters import format_market_state_dashboard

        anchors = fetch_macro_anchors()
        ctx = run_contextualization(anchors)

        earnings_regime = {"ok": False}
        try:
            from src.earnings_tracker import compute_earnings_regime
            earnings_regime = compute_earnings_regime()
        except Exception:
            pass

        market_phase = compute_market_phase(ctx, {}, earnings_regime)
        dashboard = format_market_state_dashboard(market_phase, ctx)
        if dashboard:
            send_text(dashboard)
            print("   → Market State Dashboard sent")
    except Exception as e:
        print(f"   ⚠️ Market State Dashboard: {e}")

    print("✅ EVENING REPORT COMPLETE")

if __name__ == "__main__":
    main()