import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_fetcher    import fetch_watchlist_data
from src.ai_engine       import AIEngine
from src.telegram_sender import send_text, fmt_eod_report
from src.db              import get_watchlist, was_alert_sent, log_alert_sent

def main():
    print("=" * 50)
    print("🔔 MARKET CLOSE STARTING")
    print("=" * 50)

    stocks = get_watchlist()
    if not stocks:
        send_text("🔔 *Market Close*\n⚠️ Watchlist empty!")
        return

    data      = fetch_watchlist_data(stocks)
    ok_stocks = {s: d for s, d in data.items() if d.get("ok")}
    winners   = sorted([(s, d) for s, d in ok_stocks.items()
                        if d.get("day_change", 0) > 0],
                       key=lambda x: x[1]["day_change"], reverse=True)[:3]
    losers    = sorted([(s, d) for s, d in ok_stocks.items()
                        if d.get("day_change", 0) < 0],
                       key=lambda x: x[1]["day_change"])[:3]
    vol_alerts = [s for s, d in ok_stocks.items() if d.get("volume_spike")]

    ai     = AIEngine()
    prompt = AIEngine.eod_summary_prompt(data)
    try:
        summary = ai.analyze("volume", prompt)
    except Exception as e:
        summary = f"AI unavailable: {e}"

    msg = fmt_eod_report(summary)
    if winners or losers:
        msg += "\n\n📊 *Today's Scoreboard:*\n"
        for s, d in winners:
            msg += f"🟢 *{s}*: {d['day_change']:+.2f}%\n"
        for s, d in losers:
            msg += f"🔴 *{s}*: {d['day_change']:+.2f}%\n"
    if vol_alerts:
        msg += f"\n⚡ *Volume Spikes:* {', '.join(vol_alerts)}"

    send_text(msg)

    for sym, d in ok_stocks.items():
        change = d.get("day_change", 0)
        key    = f"eod_bigmove_{sym}"
        if abs(change) >= 5.0 and not was_alert_sent(sym, key):
            emoji = "🚀" if change > 0 else "💥"
            send_text(f"{emoji} *BIG MOVE — {sym}*\n\nDay Change: *{change:+.2f}%*\nPrice: ₹{d.get('price', 0)}")
            log_alert_sent(sym, key)

    print("✅ MARKET CLOSE COMPLETE")

if __name__ == "__main__":
    main()