import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_fetcher      import fetch_global_indices, fetch_watchlist_data
from src.heatmap_generator import generate_heatmap
from src.chart_generator   import generate_technical_chart
from src.sector_heatmap    import generate_sector_heatmap, generate_watchlist_heatmap
from src.ai_engine         import AIEngine
from src.telegram_sender   import send_image, send_text, fmt_weekly_report
from src.db                import save_daily_snapshot, get_watchlist

def main():
    print("=" * 50)
    print("📅 WEEKLY DIGEST STARTING")
    print("=" * 50)

    stocks = get_watchlist()
    if not stocks:
        send_text("📅 *Weekly Digest*\n⚠️ Watchlist empty!")
        return

    index_data     = fetch_global_indices()
    valid_index    = {k: v for k, v in index_data.items()
                     if v.get("ok") and v.get("price", 0) > 0}
    watchlist_data = fetch_watchlist_data(stocks)

    try:
        send_image(generate_heatmap(valid_index), caption="📅 *Weekly Global Heatmap*")
    except Exception as e:
        print(f"⚠️ World heatmap failed: {e}")

    try:
        send_image(generate_sector_heatmap(), caption="🏭 *Weekly Sector Performance*")
    except Exception as e:
        print(f"⚠️ Sector heatmap failed: {e}")

    try:
        send_image(generate_watchlist_heatmap(stocks), caption="📊 *Weekly Watchlist Performance*")
    except Exception as e:
        print(f"⚠️ Watchlist heatmap failed: {e}")

    ai = AIEngine()
    try:
        digest = ai.analyze("volume", AIEngine.weekly_digest_prompt(valid_index, watchlist_data))
        send_text(fmt_weekly_report(digest))
    except Exception as e:
        print(f"⚠️ Weekly digest failed: {e}")

    # ── Weekly Accuracy Report ──────────────────────────────────
    try:
        from src.prediction_tracker import format_weekly_accuracy
        accuracy = format_weekly_accuracy()
        if accuracy:
            send_text(accuracy)
            print(f"📊 Accuracy report sent")
    except Exception as e:
        print(f"⚠️ Accuracy report: {e}")

    for symbol in list({s: d for s, d in watchlist_data.items() if d.get("ok")}.keys())[:3]:
        try:
            send_image(generate_technical_chart(symbol, period="1mo"),
                       caption=f"📊 *{symbol}* — Monthly Technical Chart")
        except Exception as e:
            print(f"⚠️ Chart failed {symbol}: {e}")

    ok_stocks = {s: d for s, d in watchlist_data.items() if d.get("ok")}
    sorted_stocks = sorted(ok_stocks.items(), key=lambda x: x[1].get("day_change", 0), reverse=True)
    lines = [f"{'🟢' if d.get('day_change',0)>0 else '🔴'} *{s}*: {d.get('day_change',0):+.2f}%"
             for s, d in sorted_stocks]
    if lines:
        send_text("📋 *Weekly Scoreboard:*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n" + "\n".join(lines))

    try:
        save_daily_snapshot(valid_index)
    except Exception as e:
        print(f"⚠️ Snapshot failed: {e}")

    send_text(f"📅 *Weekly digest complete!*\n_Tracking {len(stocks)} stocks_\n_See you Monday 🌅_")
    print("✅ WEEKLY DIGEST COMPLETE")

if __name__ == "__main__":
    main()