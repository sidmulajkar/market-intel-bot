"""
🕵️ INSIDER TRACKER — Daily at 5:00 PM IST
Tracks top insider buys and sells
"""
import sys
import json
sys.path.insert(0, ".")

from src.insider_tracker import get_insider_summary, format_insider_message
from src.ai_engine       import AIEngine
from src.telegram_sender import send_text

def main():
    print("=" * 50)
    print("🕵️ INSIDER TRACKER STARTING")
    print("=" * 50)

    with open("config/watchlist.json") as f:
        config = json.load(f)
    symbols = config.get("stocks", [])

    summary = get_insider_summary(symbols)
    msg     = format_insider_message(summary)
    send_text(msg)

    # AI reads into insider patterns
    if summary["all"]:
        top_buys  = summary["top_buys"][:3]
        top_sells = summary["top_sells"][:3]

        buy_text  = "\n".join([
            f"BUY: {t['symbol']} — {t['insider'][:25]} "
            f"₹{t['value_cr']}Cr ({t['delta_pct']:+.3f}%)"
            for t in top_buys
        ])
        sell_text = "\n".join([
            f"SELL: {t['symbol']} — {t['insider'][:25]} "
            f"₹{t['value_cr']}Cr ({t['delta_pct']:+.3f}%)"
            for t in top_sells
        ])

        ai     = AIEngine()
        prompt = f"""
Recent insider trading activity (last 14 days):

TOP BUYS BY INSIDERS:
{buy_text if buy_text else 'None'}

TOP SELLS BY INSIDERS:
{sell_text if sell_text else 'None'}

Interpret this insider activity:
1. What does the buying pattern signal?
2. What does the selling pattern signal?
3. Any high-conviction insider moves to flag?
4. Overall smart money sentiment: Confident/Cautious/Mixed?

Under 150 words. Be direct.
"""
        analysis = ai.analyze("fast", prompt)
        send_text(f"🤖 *AI — Insider Activity Interpretation:*\n\n{analysis}")

    print("✅ Insider tracker complete!")

if __name__ == "__main__":
    main()