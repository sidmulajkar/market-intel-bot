import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_fetcher      import fetch_global_indices, fetch_watchlist_data
from src.heatmap_generator import generate_heatmap
from src.sector_heatmap    import generate_sector_heatmap, generate_watchlist_heatmap
from src.ai_engine         import AIEngine
from src.telegram_sender   import send_image, send_text, fmt_morning_report
from src.db                import save_daily_snapshot, get_watchlist

def main():
    print("=" * 50)
    print("🌅 MORNING BRIEF STARTING")
    print("=" * 50)

    stocks = get_watchlist()
    print(f"📋 Watchlist loaded: {len(stocks)} stocks")
    print(f"   Symbols: {', '.join(stocks)}")

    if not stocks:
        send_text("⚠️ *Morning Brief*\nWatchlist is empty!\nAdd stocks via: `/add SYMBOL`")
        return

    print("🌍 Fetching global indices...")
    index_data  = fetch_global_indices()
    valid_index = {k: v for k, v in index_data.items()
                   if v.get("ok") and v.get("price", 0) > 0}
    print(f"   Valid markets: {len(valid_index)}/18")

    print("🎨 Generating world heatmap...")
    try:
        heatmap = generate_heatmap(valid_index)
        send_image(heatmap, caption="🌍 *World Equity Heatmap*")
        print("   ✅ World heatmap sent")
    except Exception as e:
        print(f"   ⚠️ World heatmap failed: {e}")

    print("🏭 Generating sector heatmap...")
    try:
        sector_map = generate_sector_heatmap()
        send_image(sector_map, caption="🏭 *India Sector Heatmap*")
        print("   ✅ Sector heatmap sent")
    except Exception as e:
        print(f"   ⚠️ Sector heatmap failed: {e}")

    print("📊 Generating watchlist heatmap...")
    try:
        wl_map = generate_watchlist_heatmap(stocks)
        send_image(wl_map, caption="📊 *My Watchlist Heatmap*")
        print("   ✅ Watchlist heatmap sent")
    except Exception as e:
        print(f"   ⚠️ Watchlist heatmap failed: {e}")

    print("🤖 Running AI morning brief...")
    try:
        ai     = AIEngine()
        prompt = AIEngine.morning_brief_prompt(valid_index)
        brief  = ai.analyze("fast", prompt)
        send_text(fmt_morning_report(brief))
        print("   ✅ AI brief sent")
    except Exception as e:
        print(f"   ⚠️ AI brief failed: {e}")
        send_text("⚠️ AI brief temporarily unavailable")

    print("📈 Scanning watchlist alerts...")
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
            send_text("🔔 *Pre-Market Alerts*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n" + "\n".join(alerts))
    except Exception as e:
        print(f"   ⚠️ Alert scan failed: {e}")

    try:
        save_daily_snapshot(valid_index)
    except Exception as e:
        print(f"   ⚠️ Snapshot save failed: {e}")

    print("=" * 50)
    print("✅ MORNING BRIEF COMPLETE")
    print("=" * 50)

if __name__ == "__main__":
    main()