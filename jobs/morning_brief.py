import os
import sys

# GUARANTEED PATH FIX - works on all systems
_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_dir)
if _root not in sys.path:
    sys.path.insert(0, _root)

# Verify path fix worked before importing
import importlib.util
_spec = importlib.util.find_spec("src.data_fetcher")
if _spec is None:
    print(f"ERROR: src not found. sys.path = {sys.path}")
    print(f"_root = {_root}")
    print(f"Files in _root: {os.listdir(_root)}")
    sys.exit(1)

print(f"✅ Path confirmed: {_root}")

from src.data_fetcher      import fetch_global_indices, fetch_watchlist_data, fetch_general_news
from src.heatmap_generator  import generate_heatmap
from src.sector_heatmap    import generate_sector_heatmap, generate_watchlist_heatmap
from src.ai_engine         import AIEngine
from src.telegram_sender   import send_image, send_text, fmt_morning_report
from src.db                import save_daily_snapshot, get_watchlist, purge_old_data
from src.validator         import validate_articles, assess_sentiment_consensus


def main():
    print("=" * 50)
    print("🌅 MORNING BRIEF STARTING")
    print("=" * 50)

    # ── DB Cleanup ─────────────────────────────────────────────────
    try:
        purge_result = purge_old_data()
        print(f"🧹 DB cleanup: {purge_result['sent_alerts']} alerts, {purge_result['snapshots']} snapshots")
    except Exception as e:
        print(f"⚠️  DB cleanup failed: {e}")

    stocks = get_watchlist()
    print(f"📋 Watchlist: {len(stocks)} stocks — {stocks}")

    if not stocks:
        send_text(
            "⚠️ *Morning Brief*\n"
            "Watchlist is empty!\n"
            "Add stocks: `/add SYMBOL`"
        )
        return

    # ── Global Heatmap ────────────────────────────────────────────
    print("🌍 Fetching global indices...")
    index_data  = fetch_global_indices()
    valid_index = {
        k: v for k, v in index_data.items()
        if v.get("ok") and v.get("price", 0) > 0
    }
    print(f"   Valid: {len(valid_index)}/18")

    try:
        send_image(
            generate_heatmap(valid_index),
            caption="🌍 *World Equity Heatmap*"
        )
        print("   ✅ World heatmap sent")
    except Exception as e:
        print(f"   ⚠️ World heatmap failed: {e}")

    # ── Sector Heatmap ────────────────────────────────────────────
    try:
        send_image(
            generate_sector_heatmap(),
            caption="🏭 *India Sector Heatmap*"
        )
        print("   ✅ Sector heatmap sent")
    except Exception as e:
        print(f"   ⚠️ Sector heatmap failed: {e}")

    # ── Watchlist Heatmap ─────────────────────────────────────────
    try:
        send_image(
            generate_watchlist_heatmap(stocks),
            caption="📊 *My Watchlist Heatmap*"
        )
        print("   ✅ Watchlist heatmap sent")
    except Exception as e:
        print(f"   ⚠️ Watchlist heatmap failed: {e}")

    # ── Fetch & Validate News ─────────────────────────────────────
    print("📰 Fetching and validating news...")
    raw_news = fetch_general_news()
    validated_news = validate_articles(raw_news, min_trust=6) if raw_news else []

    # Get sentiment for each validated headline
    ai = AIEngine()
    sentiments = []
    for article in validated_news[:5]:  # Top 5 only
        sent = ai.sentiment(article.get("headline", ""))
        article["sentiment"] = sent
        if sent:
            sentiments.append(sent)

    consensus_sentiment = assess_sentiment_consensus(sentiments) if sentiments else "neutral"
    print(f"   Validated: {len(validated_news)} articles, consensus: {consensus_sentiment}")

    # ── AI Brief ─────────────────────────────────────────────────
    print("🤖 Running AI analysis...")
    try:
        prompt = AIEngine.morning_brief_prompt(valid_index, validated_news, consensus_sentiment)
        brief  = ai.analyze("fast", prompt)
        send_text(fmt_morning_report(brief))
        print("   ✅ AI brief sent")
    except Exception as e:
        print(f"   ⚠️ AI brief failed: {e}")
        send_text("⚠️ AI brief temporarily unavailable")

    # ── Watchlist Alerts ──────────────────────────────────────────
    print("📈 Checking watchlist alerts...")
    try:
        wl_data = fetch_watchlist_data(stocks)
        alerts  = []
        for sym, d in wl_data.items():
            if not d.get("ok"):
                continue
            change = d.get("day_change", 0)
            if abs(change) >= 3.0:
                emoji = "🟢" if change > 0 else "🔴"
                alerts.append(f"{emoji} *{sym}*: {change:+.2f}%")
            if d.get("volume_spike"):
                alerts.append(f"⚡ *{sym}*: Volume spike!")
        if alerts:
            send_text(
                "🔔 *Pre-Market Alerts*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                + "\n".join(alerts)
            )
    except Exception as e:
        print(f"   ⚠️ Alert scan failed: {e}")

    # ── Save Snapshot ─────────────────────────────────────────────
    try:
        save_daily_snapshot(valid_index)
    except Exception as e:
        print(f"   ⚠️ Snapshot failed: {e}")

    print("=" * 50)
    print("✅ MORNING BRIEF COMPLETE")
    print("=" * 50)


if __name__ == "__main__":
    main()
