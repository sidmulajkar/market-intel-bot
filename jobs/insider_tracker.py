import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.insider_tracker import get_insider_summary, format_insider_message
from src.ai_engine       import AIEngine
from src.telegram_sender import send_text
from src.db              import get_watchlist

def main():
    print("=" * 50)
    print("🕵️ INSIDER TRACKER STARTING")
    print("=" * 50)

    symbols = get_watchlist()
    summary = get_insider_summary(symbols)
    send_text(format_insider_message(summary))

    if summary["all"]:
        buy_text  = "\n".join([f"BUY: {t['symbol']} — {t['insider'][:20]} ₹{t['value_cr']}Cr"
                               for t in summary["top_buys"][:3]])
        sell_text = "\n".join([f"SELL: {t['symbol']} — {t['insider'][:20]} ₹{t['value_cr']}Cr"
                               for t in summary["top_sells"][:3]])
        ai     = AIEngine()
        prompt = f"""
Recent insider activity (last 14 days):
TOP BUYS: {buy_text if buy_text else 'None'}
TOP SELLS: {sell_text if sell_text else 'None'}

Interpret:
1. What does buying pattern signal?
2. What does selling pattern signal?
3. High-conviction moves to flag?
4. Overall sentiment: Confident/Cautious/Mixed?

Under 150 words.
"""
        try:
            analysis = ai.analyze("fast", prompt)
            send_text(f"🤖 *AI — Insider Activity:*\n\n{analysis}")
        except Exception as e:
            print(f"⚠️ AI failed: {e}")

    print("✅ INSIDER TRACKER COMPLETE")

if __name__ == "__main__":
    main()