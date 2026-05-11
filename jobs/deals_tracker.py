import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bulk_block_deals import get_all_deals, format_deals_message
from src.ai_engine        import AIEngine
from src.telegram_sender  import send_text
from src.db               import get_watchlist

def main():
    print("=" * 50)
    print("📋 DEALS TRACKER STARTING")
    print("=" * 50)

    symbols = get_watchlist()
    deals   = get_all_deals(watchlist=symbols)
    send_text(format_deals_message(deals))

    if deals["all"]:
        top = deals["all"][:5]
        deal_summary = "\n".join([
            f"{d['symbol']}: {d['client'][:25]} {d['buy_sell']} ₹{d['deal_value']}Cr"
            for d in top
        ])
        ai     = AIEngine()
        prompt = f"""
Today's significant bulk/block deals:
{deal_summary}

Analyse:
1. Which deals are most significant and why?
2. Accumulation or distribution pattern?
3. Any watchlist stocks to flag?
4. Smart money direction: Bullish/Bearish/Mixed?

Under 150 words.
"""
        try:
            analysis = ai.analyze("fast", prompt)
            send_text(f"🤖 *AI Analysis — Today's Deals:*\n\n{analysis}")
        except Exception as e:
            print(f"⚠️ AI analysis failed: {e}")

    print("✅ DEALS TRACKER COMPLETE")

if __name__ == "__main__":
    main()