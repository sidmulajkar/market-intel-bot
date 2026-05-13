import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_fetcher      import fetch_global_indices, fetch_general_news
from src.heatmap_generator import generate_heatmap
from src.ai_engine         import AIEngine
from src.telegram_sender   import send_image, send_text
from src.db                import get_watchlist
from src.validator        import validate_articles, assess_sentiment_consensus

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

    send_text(
        "🌃 *EVENING GLOBAL REPORT*\n_US Session Now Live_\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        + analysis
        + "\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n_India outlook for tomorrow ↑_"
    )
    print("✅ EVENING REPORT COMPLETE")

if __name__ == "__main__":
    main()