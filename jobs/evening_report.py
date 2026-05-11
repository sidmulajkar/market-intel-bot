"""
🌃 EVENING GLOBAL REPORT
Schedule: 7:00 PM IST (1:15 PM UTC) — Mon to Fri
Workflow: .github/workflows/evening_global.yml

What it does:
  1. Reads watchlist FROM SUPABASE
  2. Fetches updated global data (US markets now open)
  3. Generates fresh heatmap with US showing OPEN
  4. Sends AI evening brief + India tomorrow outlook
"""
import sys
sys.path.insert(0, ".")

from src.data_fetcher      import fetch_global_indices
from src.heatmap_generator import generate_heatmap
from src.ai_engine         import AIEngine
from src.telegram_sender   import send_image, send_text
from src.db                import get_watchlist    # ← READS FROM SUPABASE

def main():
    print("=" * 50)
    print("🌃 EVENING GLOBAL REPORT STARTING")
    print("=" * 50)

    # ── STEP 1: Load watchlist from Supabase ──────────────────
    # Evening report doesn't use stock-specific data but
    # we load it to show watchlist count in status
    stocks = get_watchlist()
    print(f"📋 Watchlist: {len(stocks)} stocks tracked")

    # ── STEP 2: Fetch updated global data (US now OPEN) ───────
    print("🌍 Fetching global indices (US session live)...")
    index_data  = fetch_global_indices()
    valid_index = {
        k: v for k, v in index_data.items()
        if v.get("ok") and v.get("price", 0) > 0
    }
    print(f"   Valid markets: {len(valid_index)}/18")

    # ── STEP 3: Generate updated heatmap ──────────────────────
    print("🎨 Generating evening heatmap (US OPEN)...")
    try:
        heatmap = generate_heatmap(valid_index)
        send_image(
            heatmap,
            caption="🌃 *Evening Global Heatmap — US Session Live*"
        )
        print("   ✅ Evening heatmap sent")
    except Exception as e:
        print(f"   ⚠️ Heatmap failed: {e}")

    # ── STEP 4: AI evening analysis ───────────────────────────
    print("🤖 Running AI evening analysis...")
    ai     = AIEngine()

    # Build evening-specific prompt
    lines = []
    for country, d in valid_index.items():
        sign = "+" if d.get("change_pct", 0) >= 0 else ""
        lines.append(
            f"{d.get('flag', '')} {country}: "
            f"{sign}{d.get('change_pct', 0):.2f}% [{d.get('status', '?')}]"
        )

    prompt = f"""
Evening global market snapshot (US session just opened):
{chr(10).join(lines)}

This is the EVENING report for Indian investors.

Provide:
1. 🌃 US Opening Direction: Bullish/Bearish/Flat + key reason
2. 🌍 Global Risk Mood: Risk-on / Risk-off / Neutral
3. 🇮🇳 India Tomorrow Setup: What this means for Nifty opening
4. ⚠️ Overnight Risk Events: Key things to monitor tonight
5. 💡 Tomorrow's Strategy: One actionable idea for morning

Under 200 words. Sharp and direct for Indian investors.
"""
    try:
        analysis = ai.analyze("fast", prompt)
    except Exception as e:
        print(f"   ⚠️ AI analysis failed: {e}")
        analysis = "AI analysis temporarily unavailable"

    # ── STEP 5: Send evening brief ────────────────────────────
    msg = (
        "🌃 *EVENING GLOBAL REPORT*\n"
        "_US Session Now Live_\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        + analysis
        + "\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "_India market outlook for tomorrow ↑_"
    )
    send_text(msg)
    print("   ✅ Evening brief sent")

    print("=" * 50)
    print("✅ EVENING REPORT COMPLETE")
    print("=" * 50)

if __name__ == "__main__":
    main()