import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_fetcher    import fetch_global_indices, fetch_top_movers, fetch_general_news
from src.ai_engine       import AIEngine
from src.telegram_sender import send_text
from src.validator       import validate_articles, assess_sentiment_consensus
from src.db              import was_alert_sent, log_alert_sent
from src.validation_helper import ai_generate_and_validate, build_ground_truth_from_index

def main():
    print("=" * 50)
    print("📊 MIDDAY SCAN STARTING")
    print("=" * 50)

    # ── Fetch market data in parallel ──────────────────────────────
    print("🌍 Fetching global indices + top movers + news...")
    index_data = fetch_global_indices()
    movers     = fetch_top_movers(top_n=5)
    raw_news   = fetch_general_news()

    valid_index = {
        k: v for k, v in index_data.items()
        if v.get("ok") and v.get("price", 0) > 0
    }
    print(f"   Indices: {len(valid_index)}/18 | Movers: {len(movers.get('india',{}).get('gainers',[]))} gainers")

    # ── Validate news + sentiment ──────────────────────────────────
    ai = AIEngine()
    validated_news = validate_articles(raw_news, min_trust=6) if raw_news else []
    sentiments = []
    for article in validated_news[:3]:
        sent = ai.sentiment(article.get("headline", ""))
        article["sentiment"] = sent
        if sent:
            sentiments.append(sent)
    consensus = assess_sentiment_consensus(sentiments) if sentiments else "neutral"

    # ── Build market snapshot ──────────────────────────────────────
    lines = []

    # Nifty + VIX line
    nifty = valid_index.get("Nifty 50", {})
    vix   = valid_index.get("India VIX", {})
    if nifty:
        nifty_change = nifty.get("change_pct", 0)
        nifty_emoji  = "🟢" if nifty_change > 0 else ("🔴" if nifty_change < 0 else "⚪")
        vix_note     = ""
        if vix and vix.get("price"):
            vix_price = vix.get("price", 0)
            vix_note  = f" | VIX {vix_price:.1f}"
        lines.append(f"{nifty_emoji} Nifty {nifty.get('price', 0):,.0f} ({nifty_change:+.1f}%){vix_note}")

    # Global indices — top 3 by absolute change
    global_sorted = sorted(
        [(c, d) for c, d in valid_index.items()
         if c not in ("Nifty 50", "India VIX", "Bank Nifty", "Nifty Next 50")],
        key=lambda x: abs(x[1].get("change_pct", 0)),
        reverse=True
    )
    if global_sorted:
        g_parts = []
        for country, d in global_sorted[:3]:
            sign = "+" if d.get("change_pct", 0) >= 0 else ""
            g_parts.append(f"{d.get('flag','')} {country} {sign}{d.get('change_pct',0):.1f}%")
        lines.append(f"🌍 {' | '.join(g_parts)}")

    # News headline
    if validated_news:
        top = validated_news[0]
        headline = top.get("headline", "")[:60]
        trust    = top.get("trust_score", 0)
        source   = top.get("source", "unknown")
        lines.append(f"📰 {headline} ({source}, Trust:{trust}/10)")

    # Top gainers + losers from dynamic movers
    india_g = movers.get("india", {}).get("gainers", [])
    india_l = movers.get("india", {}).get("losers", [])
    if india_g:
        g_str = ", ".join(f"{m['symbol']} +{m['change_pct']:.1f}%" for m in india_g[:3])
        lines.append(f"🟢 Gainers: {g_str}")
    if india_l:
        l_str = ", ".join(f"{m['symbol']} {m['change_pct']:.1f}%" for m in india_l[:3])
        lines.append(f"🔴 Losers: {l_str}")

    # ── Stock-level alerts (only for extraordinary moves) ──────────
    alerts = []
    for m in india_g + india_l:
        change = abs(m.get("change_pct", 0))
        sym    = m.get("symbol", "")
        if change >= 5.0:
            emoji = "🚀" if m.get("change_pct", 0) > 0 else "💥"
            key   = f"midday_extreme_{sym}"
            if not was_alert_sent(sym, key):
                alerts.append(f"{emoji} *{sym}* {m['change_pct']:+.1f}% — extreme move")
                log_alert_sent(sym, key)

    # ── AI midday brief (with universal validation) ────────────────
    print("🤖 Running AI midday analysis...")
    analysis = ""
    ground_truth = {}
    try:
        # Get bull/bear context
        from src.context_engine import run_contextualization, get_fii_dii_context, get_macro_context
        from src.data_fetcher import fetch_macro_anchors
        fii_ctx  = get_fii_dii_context(days=30)
        macro_ctx = get_macro_context()
        anchor_data = fetch_macro_anchors()
        ctx = run_contextualization(anchor_data) if anchor_data else {}
        bull_bear = ctx.get("bull_bear", {})

        # Build ground truth
        gt_extra = {}
        if bull_bear.get("score") is not None:
            gt_extra["bull_bear_score"] = bull_bear["score"]
        if fii_ctx.get("ok"):
            gt_extra["fii_net"] = fii_ctx.get("fii_net")
        for a in (anchor_data or []):
            name = a.get("name", "")
            if name == "India VIX" and a.get("ok") and a.get("price"):
                gt_extra["india_vix"] = a["price"]
            elif name == "Brent Crude" and a.get("ok") and a.get("price"):
                gt_extra["brent"] = a["price"]
        ground_truth = build_ground_truth_from_index(valid_index, gt_extra if gt_extra else None)

        prompt = AIEngine.midday_market_prompt(valid_index, movers, validated_news, bull_bear)
    except Exception as e:
        print(f"   ⚠️ AI or context failed: {e}")
        prompt = ""

    def make_fallback():
        fb = "📊 *MIDDAY MARKET SCAN*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        fb += "\n".join(lines)
        fb += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n_Mid-session check_"
        if alerts:
            fb += f"\n\n⚠️ *Extreme Moves:*\n" + "\n".join(alerts)
        return fb

    if prompt and ground_truth.get("nifty_close"):
        def send_midday(text):
            msg = "📊 *MIDDAY MARKET SCAN*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            msg += "\n".join(lines)
            msg += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n{text}"
            if alerts:
                msg += f"\n\n⚠️ *Extreme Moves:*\n" + "\n".join(alerts)
            msg += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n_Mid-session check_"
            send_text(msg)

        ai_generate_and_validate(
            ai, "fast", prompt, ground_truth,
            output_type="midday_scan",
            fallback_fn=make_fallback,
            send_fn=send_midday,
            max_retries=1,
        )
    else:
        # No ground truth or no prompt — send unvalidated (degraded)
        msg = "📊 *MIDDAY MARKET SCAN*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += "\n".join(lines)
        if analysis:
            msg += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n{analysis}"
        if alerts:
            msg += f"\n\n⚠️ *Extreme Moves:*\n" + "\n".join(alerts)
        msg += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n_Mid-session check_"
        send_text(msg)
    print("✅ MIDDAY SCAN COMPLETE")

if __name__ == "__main__":
    main()
