import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_fetcher    import fetch_watchlist_data, fetch_news_finnhub
from src.ai_engine       import AIEngine
from src.telegram_sender import send_text
from src.validator       import validate_articles
from src.db              import get_watchlist, was_alert_sent, log_alert_sent

def main():
    print("=" * 50)
    print("📊 MIDDAY SCAN STARTING")
    print("=" * 50)

    stocks = get_watchlist()
    print(f"📋 Watchlist loaded: {len(stocks)} stocks")

    if not stocks:
        send_text("📊 *Midday Scan*\n⚠️ Watchlist empty!\nUse `/add SYMBOL`")
        return

    data       = fetch_watchlist_data(stocks)
    lines      = []
    big_movers = []

    for sym, d in data.items():
        if not d.get("ok"):
            lines.append(f"⚪ *{sym}*: No data")
            continue
        change = d.get("day_change", 0)
        emoji  = "🟢" if change > 0 else ("🔴" if change < 0 else "⚪")
        spike  = " ⚡" if d.get("volume_spike") else ""
        lines.append(f"{emoji} *{sym}*: {change:+.2f}%{spike}")
        if abs(change) >= 3.0:
            big_movers.append((sym, d))

    send_text(
        "📊 *MIDDAY WATCHLIST SNAPSHOT*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        + "\n".join(lines)
        + "\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n_Mid-session check_"
    )

    ai = AIEngine()
    for sym, d in big_movers[:3]:
        key = f"midday_mover_{sym}"
        if was_alert_sent(sym, key):
            continue
        try:
            news     = fetch_news_finnhub(sym)
            valid_n  = validate_articles(news)
            prompt   = AIEngine.stock_analysis_prompt(sym, d, valid_n)
            analysis = ai.analyze("fast", prompt)
            send_text(f"🔍 *{sym} — Midday Alert*\n\n{analysis}")
            log_alert_sent(sym, key)
        except Exception as e:
            print(f"   ⚠️ Analysis failed for {sym}: {e}")

    print("✅ MIDDAY SCAN COMPLETE")

if __name__ == "__main__":
    main()