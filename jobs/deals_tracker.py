"""
📋 DEALS TRACKER — 4:30 PM IST (after market close)
Fetches bulk & block deals of the day
"""
import sys
import json
sys.path.insert(0, ".")

from src.bulk_block_deals import get_all_deals, format_deals_message
from src.ai_engine        import AIEngine
from src.telegram_sender  import send_text

def main():
    print("=" * 50)
    print("📋 DEALS TRACKER STARTING")
    print("=" * 50)

    with open("config/watchlist.json") as f:
        config = json.load(f)
    symbols = config.get("stocks", [])

    # Fetch all deals
    deals = get_all_deals(watchlist=symbols)

    # Format and send base message
    msg = format_deals_message(deals)
    send_text(msg)

    # AI analysis of significant deals
    if deals["all"]:
        top = deals["all"][:5]
        deal_summary = "\n".join([
            f"{d['symbol']}: {d['client'][:30]} "
            f"{d['buy_sell']} ₹{d['deal_value']}Cr"
            for d in top
        ])
        ai     = AIEngine()
        prompt = f"""
Today's significant bulk/block deals:
{deal_summary}

Analyse what these deals signal:
1. Which deals are most significant and why?
2. Are there any patterns (accumulation/distribution)?
3. Any watchlist stocks you'd flag based on this?
4. Overall smart money direction: Bullish/Bearish/Mixed?

Under 150 words. Sharp and direct.
"""
        analysis = ai.analyze("fast", prompt)
        send_text(f"🤖 *AI Analysis — Today's Deals:*\n\n{analysis}")

    print("✅ Deals tracker complete!")

if __name__ == "__main__":
    main()