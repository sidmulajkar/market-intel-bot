import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.insider_tracker import get_market_insider_activity, format_insider_summary
from src.ai_engine       import AIEngine
from src.telegram_sender import send_text


def main():
    print("=" * 50)
    print("🕵️ INSIDER TRACKER STARTING")
    print("=" * 50)

    data = get_market_insider_activity(days=10)

    if data.get("ok"):
        summary = format_insider_summary(data)
        if summary:
            send_text(summary)
            print(f"✅ Sent — {data['total_deals']} deals across {len(data['symbols'])} symbols")
        else:
            print("⚠️  No data to send")
    else:
        print(f"⚠️  Fetch failed: {data.get('message', 'unknown')}")

    # AI analysis of bulk/block activity
    if data.get("ok") and data.get("top_deals"):
        buys  = [d for d in data["top_deals"] if d["side"] == "BUY"][:3]
        sells = [d for d in data["top_deals"] if d["side"] == "SELL"][:3]

        buy_text  = "\n".join([
            f"{d['symbol']}: {d['qty']:,} shares @ ₹{d['price']:,.2f} (₹{d['value_cr']}Cr)"
            for d in buys
        ]) or "None"
        sell_text = "\n".join([
            f"{d['symbol']}: {d['qty']:,} shares @ ₹{d['price']:,.2f} (₹{d['value_cr']}Cr)"
            for d in sells
        ]) or "None"

        ai    = AIEngine()
        prompt = f"""
Bulk & block deal activity ({data['date_range']}):

TOP BUYS:
{buy_text}

TOP SELLS:
{sell_text}

Interpret:
1. What does heavy buy-side activity signal? (institutional accumulation?)
2. What does heavy sell-side signal? (profit-taking, exit?)
3. Any notable patterns: small-cap focus, specific sectors, repeat clients?
4. Overall institutional sentiment: Confident / Cautious / Mixed?

Under 120 words.
"""
        try:
            analysis = ai.analyze("fast", prompt)
            send_text(f"🤖 *AI — Bulk/Block Activity:*\n\n{analysis}")
        except Exception as e:
            print(f"⚠️  AI failed: {e}")

    print("✅ INSIDER TRACKER COMPLETE")


if __name__ == "__main__":
    main()