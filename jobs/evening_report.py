import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_fetcher      import fetch_global_indices
from src.heatmap_generator import generate_heatmap
from src.ai_engine         import AIEngine
from src.telegram_sender   import send_image, send_text
from src.db                import get_watchlist

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

    prompt = f"""
Evening global markets (US session just opened):
{chr(10).join(lines)}

Evening report for Indian investors:
1. 🌃 US Opening Direction + reason
2. 🌍 Global Risk Mood: Risk-on/Risk-off/Neutral
3. 🇮🇳 India Tomorrow Setup
4. ⚠️ Overnight Risk Events
5. 💡 Tomorrow's Strategy

Under 200 words.
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