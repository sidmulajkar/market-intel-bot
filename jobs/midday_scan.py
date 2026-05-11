"""
📊 MIDDAY WATCHLIST SCAN
Schedule: 12:30 PM IST (6:45 AM UTC) — Mon to Fri
Workflow: .github/workflows/midday_scan.yml

What it does:
  1. Reads watchlist FROM SUPABASE
  2. Fetches current prices for all watchlist stocks
  3. Deep analysis on big movers (>3% move)
  4. Flags volume spikes
  5. Sends mid-session snapshot + AI analysis
"""
import sys
sys.path.insert(0, ".")

from src.data_fetcher    import fetch_watchlist_data, fetch_news_finnhub
from src.ai_engine       import AIEngine
from src.telegram_sender import send_text
from src.validator       import validate_articles
from src.db              import (
    get_watchlist,           # ← READS FROM SUPABASE
    was_alert_sent,
    log_alert_sent,
)

def main():
    print("=" * 50)
    print("📊 MIDDAY SCAN STARTING")
    print("=" * 50)

    # ── STEP 1: Load watchlist from Supabase ──────────────────
    stocks = get_watchlist()
    print(f"📋 Watchlist loaded: {len(stocks)} stocks")
    print(f"   Symbols: {', '.join(stocks)}")

    if not stocks:
        send_text(
            "📊 *Midday Scan*\n"
            "⚠️ Watchlist is empty!\n"
            "Add stocks via: `/add SYMBOL`"
        )
        return

    # ── STEP 2: Fetch current prices ─────────────────────────
    print("📈 Fetching current prices...")
    data = fetch_watchlist_data(stocks)

    # ── STEP 3: Build snapshot + identify movers ──────────────
    lines       = []
    big_movers  = []
    vol_spikes  = []
    threshold   = 3.0    # 3% = big mover requiring deep analysis

    for sym, d in data.items():
        if not d.get("ok"):
            lines.append(f"⚪ *{sym}*: Data unavailable")
            continue

        change = d.get("day_change", 0)
        emoji  = "🟢" if change > 0 else ("🔴" if change < 0 else "⚪")
        spike  = " ⚡" if d.get("volume_spike") else ""
        lines.append(f"{emoji} *{sym}*: {change:+.2f}%{spike}")

        if abs(change) >= threshold:
            big_movers.append((sym, d))
        if d.get("volume_spike"):
            vol_spikes.append(sym)

    # ── STEP 4: Send midday snapshot ──────────────────────────
    snapshot = (
        "📊 *MIDDAY WATCHLIST SNAPSHOT*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        + "\n".join(lines)
        + "\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "_Mid-session check_"
    )
    send_text(snapshot)
    print(f"   ✅ Snapshot sent — {len(big_movers)} big movers, "
          f"{len(vol_spikes)} volume spikes")

    # ── STEP 5: Deep analysis on big movers ───────────────────
    ai = AIEngine()
    for sym, d in big_movers[:3]:   # Max 3 to stay within AI rate limits
        alert_key = f"midday_mover_{sym}"
        if was_alert_sent(sym, alert_key):
            print(f"   ⏭️  {sym} already alerted today — skipping")
            continue

        print(f"🔍 Deep analysis: {sym}")
        try:
            news     = fetch_news_finnhub(sym)
            valid_n  = validate_articles(news)
            prompt   = AIEngine.stock_analysis_prompt(sym, d, valid_n)
            analysis = ai.analyze("fast", prompt)

            send_text(
                f"🔍 *{sym} — Midday Alert Analysis*\n\n"
                f"{analysis}"
            )
            log_alert_sent(sym, alert_key, f"Midday mover: {d.get('day_change',0):+.2f}%")
            print(f"   ✅ {sym} deep analysis sent")
        except Exception as e:
            print(f"   ⚠️ Deep analysis failed for {sym}: {e}")

    # ── STEP 6: Volume spike alerts ───────────────────────────
    for sym in vol_spikes:
        alert_key = f"volume_spike_{sym}"
        if not was_alert_sent(sym, alert_key):
            d = data.get(sym, {})
            send_text(
                f"⚡ *VOLUME SPIKE — {sym}*\n\n"
                f"Volume: {d.get('volume', 0):,}\n"
                f"3M Avg: {d.get('avg_volume', 0):,}\n"
                f"Day Change: {d.get('day_change', 0):+.2f}%\n\n"
                f"_Unusually high activity detected_"
            )
            log_alert_sent(sym, alert_key, "Volume spike")
            print(f"   ✅ Volume spike alert sent: {sym}")

    print("=" * 50)
    print("✅ MIDDAY SCAN COMPLETE")
    print("=" * 50)

if __name__ == "__main__":
    main()