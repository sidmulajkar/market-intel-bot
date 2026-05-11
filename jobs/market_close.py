"""
🔔 MARKET CLOSE — END OF DAY SUMMARY
Schedule: 3:45 PM IST (10:00 AM UTC) — Mon to Fri
Workflow: .github/workflows/market_close.yml

What it does:
  1. Reads watchlist FROM SUPABASE
  2. Fetches closing prices for all watchlist stocks
  3. Ranks winners and losers
  4. Sends AI-powered EOD summary
  5. Flags volume spikes and big moves
"""
import sys
sys.path.insert(0, ".")

from src.data_fetcher    import fetch_watchlist_data
from src.ai_engine       import AIEngine
from src.telegram_sender import send_text, fmt_eod_report
from src.db              import (
    get_watchlist,           # ← READS FROM SUPABASE
    was_alert_sent,
    log_alert_sent,
)

def main():
    print("=" * 50)
    print("🔔 MARKET CLOSE JOB STARTING")
    print("=" * 50)

    # ── STEP 1: Load watchlist from Supabase ──────────────────
    stocks = get_watchlist()
    print(f"📋 Watchlist loaded: {len(stocks)} stocks")
    print(f"   Symbols: {', '.join(stocks)}")

    if not stocks:
        send_text(
            "🔔 *Market Close Summary*\n"
            "⚠️ Watchlist is empty!\n"
            "Add stocks via: `/add SYMBOL`"
        )
        return

    # ── STEP 2: Fetch final closing prices ────────────────────
    print("📊 Fetching closing prices...")
    watchlist_data = fetch_watchlist_data(stocks)

    # ── STEP 3: Rank performance ──────────────────────────────
    ok_stocks = {
        sym: d for sym, d in watchlist_data.items()
        if d.get("ok")
    }

    winners = sorted(
        [(s, d) for s, d in ok_stocks.items()
         if d.get("day_change", 0) > 0],
        key=lambda x: x[1]["day_change"],
        reverse=True,
    )[:3]

    losers = sorted(
        [(s, d) for s, d in ok_stocks.items()
         if d.get("day_change", 0) < 0],
        key=lambda x: x[1]["day_change"],
    )[:3]

    flat = [
        s for s, d in ok_stocks.items()
        if d.get("day_change", 0) == 0
    ]

    vol_alerts = [
        sym for sym, d in ok_stocks.items()
        if d.get("volume_spike")
    ]

    print(f"   Winners: {len(winners)} | "
          f"Losers: {len(losers)} | "
          f"Vol spikes: {len(vol_alerts)}")

    # ── STEP 4: AI EOD summary ────────────────────────────────
    print("🤖 Running AI EOD analysis...")
    ai     = AIEngine()
    prompt = AIEngine.eod_summary_prompt(watchlist_data)
    try:
        summary = ai.analyze("volume", prompt)
    except Exception as e:
        print(f"   ⚠️ AI summary failed: {e}")
        summary = "AI analysis temporarily unavailable"

    # ── STEP 5: Build EOD message ─────────────────────────────
    msg = fmt_eod_report(summary)

    # Append winners/losers table
    if winners or losers:
        msg += "\n\n📊 *Today's Scoreboard:*\n"
        if winners:
            for s, d in winners:
                msg += f"🟢 *{s}*: {d['day_change']:+.2f}%\n"
        if losers:
            for s, d in losers:
                msg += f"🔴 *{s}*: {d['day_change']:+.2f}%\n"
        if flat:
            msg += f"⚪ Flat: {', '.join(flat)}\n"

    if vol_alerts:
        msg += f"\n⚡ *Volume Spikes:* {', '.join(vol_alerts)}"

    send_text(msg)
    print("   ✅ EOD summary sent")

    # ── STEP 6: Big mover EOD alerts (>5%) ────────────────────
    big_threshold = 5.0
    for sym, d in ok_stocks.items():
        change    = d.get("day_change", 0)
        alert_key = f"eod_bigmove_{sym}"
        if abs(change) >= big_threshold and not was_alert_sent(sym, alert_key):
            emoji = "🚀" if change > 0 else "💥"
            send_text(
                f"{emoji} *BIG MOVE ALERT — {sym}*\n\n"
                f"Day Change: *{change:+.2f}%*\n"
                f"Price: ₹{d.get('price', 0)}\n"
                f"Volume: {d.get('volume', 0):,}\n\n"
                f"_Significant move detected at close_"
            )
            log_alert_sent(sym, alert_key, f"Big move: {change:+.2f}%")
            print(f"   ✅ Big move alert sent: {sym} {change:+.2f}%")

    print("=" * 50)
    print("✅ MARKET CLOSE COMPLETE")
    print("=" * 50)

if __name__ == "__main__":
    main()