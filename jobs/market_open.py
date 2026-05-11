import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_fetcher    import fetch_watchlist_data, fetch_general_news
from src.ai_engine       import AIEngine
from src.telegram_sender import send_text
from src.db              import get_watchlist

def main():
    print("=" * 50)
    print("📈 MARKET OPEN JOB STARTING")
    print("=" * 50)

    stocks = get_watchlist()
    print(f"📋 Watchlist loaded: {len(stocks)} stocks")

    if not stocks:
        send_text("📈 *Market Open*\n⚠️ Watchlist empty!\nUse `/add SYMBOL`")
        return

    data      = fetch_watchlist_data(stocks)
    lines     = []
    gap_ups   = []
    gap_downs = []

    for sym, d in data.items():
        if not d.get("ok"):
            lines.append(f"⚪ *{sym}*: No data")
            continue
        change = d.get("day_change", 0)
        emoji  = "🟢" if change > 0 else ("🔴" if change < 0 else "⚪")
        spike  = " ⚡" if d.get("volume_spike") else ""
        lines.append(f"{emoji} *{sym}*: {change:+.2f}%{spike}")
        if change >= 2.0:
            gap_ups.append(f"*{sym}* +{change:.2f}%")
        elif change <= -2.0:
            gap_downs.append(f"*{sym}* {change:.2f}%")

    news   = fetch_general_news()
    ai     = AIEngine()
    prompt = f"""
Indian market just opened at 9:15 AM IST.
Watchlist snapshot:
{chr(10).join(lines)}
Recent news: {chr(10).join([n['headline'] for n in news[:3]])}
Give a sharp 3-point opening briefing:
1. Opening Mood + reason
2. 2-3 stocks to watch today
3. Key Nifty level to watch
Under 100 words.
"""
    try:
        analysis = ai.analyze("fast", prompt)
    except Exception as e:
        analysis = f"AI unavailable: {e}"

    msg = "📈 *MARKET OPEN — 9:15 AM IST*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += "\n".join(lines) + "\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n" + analysis
    if gap_ups:
        msg += f"\n\n🚀 *Gap Ups:* {' | '.join(gap_ups)}"
    if gap_downs:
        msg += f"\n🔻 *Gap Downs:* {' | '.join(gap_downs)}"

    send_text(msg)
    print("✅ MARKET OPEN COMPLETE")

if __name__ == "__main__":
    main()