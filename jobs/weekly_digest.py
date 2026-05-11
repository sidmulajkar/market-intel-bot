"""
📅 WEEKLY DIGEST
Schedule: Sunday 9:00 AM IST (3:15 AM UTC)
Workflow: .github/workflows/weekly_digest.yml

What it does:
  1. Reads watchlist FROM SUPABASE
  2. Fetches global indices + full watchlist data
  3. Generates world heatmap + technical charts
  4. Sends AI deep weekly strategic analysis
  5. Saves weekly snapshot to Supabase
"""
import sys
sys.path.insert(0, ".")

from src.data_fetcher      import fetch_global_indices, fetch_watchlist_data
from src.heatmap_generator import generate_heatmap
from src.chart_generator   import generate_technical_chart
from src.sector_heatmap    import generate_sector_heatmap, generate_watchlist_heatmap
from src.ai_engine         import AIEngine
from src.telegram_sender   import send_image, send_text, fmt_weekly_report
from src.db                import (
    save_daily_snapshot,
    get_watchlist,           # ← READS FROM SUPABASE
)

def main():
    print("=" * 50)
    print("📅 WEEKLY DIGEST STARTING")
    print("=" * 50)

    # ── STEP 1: Load watchlist from Supabase ──────────────────
    stocks = get_watchlist()
    print(f"📋 Watchlist loaded: {len(stocks)} stocks")
    print(f"   Symbols: {', '.join(stocks)}")

    if not stocks:
        send_text(
            "📅 *Weekly Digest*\n"
            "⚠️ Watchlist is empty!\n"
            "Add stocks via: `/add SYMBOL`"
        )
        return

    # ── STEP 2: Fetch global indices ──────────────────────────
    print("🌍 Fetching global indices...")
    index_data  = fetch_global_indices()
    valid_index = {
        k: v for k, v in index_data.items()
        if v.get("ok") and v.get("price", 0) > 0
    }
    print(f"   Valid markets: {len(valid_index)}/18")

    # ── STEP 3: Fetch watchlist data ──────────────────────────
    print("📈 Fetching watchlist performance...")
    watchlist_data = fetch_watchlist_data(stocks)
    ok_stocks      = {
        s: d for s, d in watchlist_data.items()
        if d.get("ok")
    }
    print(f"   Valid stocks: {len(ok_stocks)}/{len(stocks)}")

    # ── STEP 4: Generate world heatmap ────────────────────────
    print("🎨 Generating world heatmap...")
    try:
        heatmap = generate_heatmap(valid_index)
        send_image(heatmap, caption="📅 *Weekly Global Heatmap*")
        print("   ✅ World heatmap sent")
    except Exception as e:
        print(f"   ⚠️ World heatmap failed: {e}")

    # ── STEP 5: Generate sector heatmap ───────────────────────
    print("🏭 Generating sector heatmap...")
    try:
        sector_map = generate_sector_heatmap()
        send_image(sector_map, caption="🏭 *Weekly Sector Performance*")
        print("   ✅ Sector heatmap sent")
    except Exception as e:
        print(f"   ⚠️ Sector heatmap failed: {e}")

    # ── STEP 6: Generate watchlist heatmap ────────────────────
    print("📊 Generating watchlist heatmap...")
    try:
        wl_map = generate_watchlist_heatmap(stocks)
        send_image(wl_map, caption="📊 *Weekly Watchlist Performance*")
        print("   ✅ Watchlist heatmap sent")
    except Exception as e:
        print(f"   ⚠️ Watchlist heatmap failed: {e}")

    # ── STEP 7: AI weekly digest ──────────────────────────────
    print("🤖 Running AI weekly analysis...")
    ai     = AIEngine()
    prompt = AIEngine.weekly_digest_prompt(valid_index, watchlist_data)
    try:
        digest = ai.analyze("volume", prompt)
        send_text(fmt_weekly_report(digest))
        print("   ✅ Weekly digest sent")
    except Exception as e:
        print(f"   ⚠️ Weekly digest failed: {e}")

    # ── STEP 8: Technical charts for top 3 stocks ────────────
    print("📊 Generating technical charts...")
    chart_symbols = list(ok_stocks.keys())[:3]   # Top 3 only

    for symbol in chart_symbols:
        print(f"   📊 Chart: {symbol}")
        try:
            chart = generate_technical_chart(symbol, period="1mo")
            send_image(
                chart,
                caption=f"📊 *{symbol}* — Monthly Technical Chart"
            )
            print(f"   ✅ Chart sent: {symbol}")
        except Exception as e:
            print(f"   ⚠️ Chart failed for {symbol}: {e}")

    # ── STEP 9: Weekly watchlist scoreboard ───────────────────
    scoreboard_lines = []
    sorted_stocks    = sorted(
        ok_stocks.items(),
        key=lambda x: x[1].get("day_change", 0),
        reverse=True,
    )
    for sym, d in sorted_stocks:
        change = d.get("day_change", 0)
        emoji  = "🟢" if change > 0 else ("🔴" if change < 0 else "⚪")
        spike  = " ⚡" if d.get("volume_spike") else ""
        scoreboard_lines.append(
            f"{emoji} *{sym}*: {change:+.2f}%{spike}"
        )

    if scoreboard_lines:
        send_text(
            "📋 *Weekly Watchlist Scoreboard:*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            + "\n".join(scoreboard_lines)
        )

    # ── STEP 10: Save snapshot ────────────────────────────────
    try:
        save_daily_snapshot(valid_index)
        print("   ✅ Weekly snapshot saved")
    except Exception as e:
        print(f"   ⚠️ Snapshot save failed: {e}")

    # ── STEP 11: Closing message ──────────────────────────────
    send_text(
        "📅 *Weekly digest complete!*\n"
        f"_Tracking {len(stocks)} stocks across your watchlist_\n"
        "_See you Monday morning at 8 AM 🌅_"
    )

    print("=" * 50)
    print("✅ WEEKLY DIGEST COMPLETE")
    print("=" * 50)

if __name__ == "__main__":
    main()