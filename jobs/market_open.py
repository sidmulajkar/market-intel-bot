"""
📈 MARKET OPEN ALERT
Schedule: 9:15 AM IST (3:30 AM UTC) — Mon to Fri
Workflow: .github/workflows/market_open.yml

What it does:
  1. Reads watchlist FROM SUPABASE
  2. Fetches opening prices for all watchlist stocks
  3. Identifies gap-ups and gap-downs
  4. Sends AI-powered opening brief
  5. Flags stocks above price change threshold
"""
import sys
sys.path.insert(0, ".")

from src.data_fetcher    import fetch_watchlist_data, fetch_general_news
from src.ai_engine       import AIEngine
from src.telegram_sender import send_text
from src.db              import get_watchlist       # ← READS FROM SUPABASE

def main():
    print("=" * 50)
    print("📈 MARKET OPEN JOB STARTING")
    print("=" * 50)

    # ── STEP 1: Load watchlist from Supabase ──────────────────
    stocks = get_watchlist()
    print(f"📋 Watchlist loaded: {len(stocks)} stocks")
    print(f"   Symbols: {', '.join(stocks)}")

    if not stocks:
        send_text(
            "📈 *Market Open — 9:15 AM*\n"
            "⚠️ Watchlist is empty!\n"
            "Add stocks via: `/add SYMBOL`"
        )
        return

    # ── STEP 2: Fetch opening data ────────────────────────────
    print("📊 Fetching opening prices...")
    data = fetch_watchlist_data(stocks)

    # ── STEP 3: Categorise movers ─────────────────────────────
    lines      = []
    gap_ups    = []
    gap_downs  = []
    vol_spikes = []
    threshold  = 2.0     # 2% = gap up/down

    for sym, d in data.items():
        if not d.get("ok"):
            lines.append(f"⚪ *{sym}*: No data")
            continue

        change = d.get("day_change", 0)
        emoji  = "🟢" if change > 0 else ("🔴" if change < 0 else "⚪")
        spike  = " ⚡" if d.get("volume_spike") else ""
        lines.append(f"{emoji} *{sym}*: {change:+.2f}%{spike}")

        if change >= threshold:
            gap_ups.append(f"*{sym}* +{change:.2f}%")
        elif change <= -threshold:
            gap_downs.append(f"*{sym}* {change:.2f}%")
        if d.get("volume_spike"):
            vol_spikes.append(sym)

    # ── STEP 4: Fetch general news ────────────────────────────
    print("📰 Fetching general news...")
    news = fetch_general_news()

    # ── STEP 5: AI opening analysis ───────────────────────────
    print("🤖 Running AI opening analysis...")
    ai     = AIEngine()
    prompt = f"""
Indian market just opened at 9:15 AM IST.
Watchlist opening snapshot:
{chr(10).join(lines)}

Recent general news headlines:
{chr(10).join([n['headline'] for n in news[:3]])}

Give a sharp opening briefing in 3 points:
1. Opening Mood: Bullish/Bearish/Flat + reason
2. Focus Stocks: 2-3 stocks to watch closely today
3. Key Level: One critical Nifty level to watch

Under 100 words. Snappy and direct.
"""
    try:
        analysis = ai.analyze("fast", prompt)
    except Exception as e:
        print(f"   ⚠️ AI analysis failed: {e}")
        analysis = "AI analysis temporarily unavailable"

    # ── STEP 6: Build and send message ───────────────────────
    msg  = "📈 *MARKET OPEN — 9:15 AM IST*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += "\n".join(lines)
    msg += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += analysis

    if gap_ups:
        msg += f"\n\n🚀 *Gap Ups:* {' | '.join(gap_ups)}"
    if gap_downs:
        msg += f"\n🔻 *Gap Downs:* {' | '.join(gap_downs)}"
    if vol_spikes:
        msg += f"\n⚡ *Volume Spikes:* {', '.join(vol_spikes)}"

    send_text(msg)
    print("=" * 50)
    print("✅ MARKET OPEN ALERT COMPLETE")
    print("=" * 50)

if __name__ == "__main__":
    main()