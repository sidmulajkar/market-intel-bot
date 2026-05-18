import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_fetcher    import fetch_global_indices, fetch_top_movers, fetch_general_news, fetch_macro_anchors
from src.ai_engine       import AIEngine
from src.telegram_sender import send_text
from src.validator       import validate_articles, assess_sentiment_consensus

def main():
    print("=" * 50)
    print("📈 MARKET OPEN JOB STARTING")
    print("=" * 50)

    # ── Fetch market data ──────────────────────────────────────────
    print("🌍 Fetching overnight global indices + pre-market movers...")
    index_data = fetch_global_indices()
    movers     = fetch_top_movers(top_n=10)
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

    # ── Get bull/bear context ──────────────────────────────────────
    bull_bear = {}
    try:
        from src.context_engine import run_contextualization
        anchor_data = fetch_macro_anchors()
        if anchor_data:
            ctx = run_contextualization(anchor_data)
            bull_bear = ctx.get("bull_bear", {})
    except Exception as e:
        print(f"   ⚠️ Context engine: {e}")

    # ── Build market context lines ─────────────────────────────────
    lines = []

    # Overnight global moves — top 3 by absolute change
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
        lines.append(f"🌍 Overnight: {' | '.join(g_parts)}")

    # Pre-market gap ups/downs from dynamic movers
    india_g = movers.get("india", {}).get("gainers", [])
    india_l = movers.get("india", {}).get("losers", [])

    gap_ups   = [m for m in india_g if m.get("change_pct", 0) >= 1.5]
    gap_downs = [m for m in india_l if m.get("change_pct", 0) <= -1.5]

    if gap_ups:
        g_str = ", ".join(f"{m['symbol']} +{m['change_pct']:.1f}%" for m in gap_ups[:3])
        lines.append(f"🚀 Gap Up: {g_str}")
    if gap_downs:
        d_str = ", ".join(f"{m['symbol']} {m['change_pct']:.1f}%" for m in gap_downs[:3])
        lines.append(f"🔻 Gap Down: {d_str}")

    # News headline
    if validated_news:
        top = validated_news[0]
        headline = top.get("headline", "")[:60]
        trust    = top.get("trust_score", 0)
        source   = top.get("source", "unknown")
        lines.append(f"📰 {headline} ({source}, Trust:{trust}/10)")

    # ── AI opening brief ───────────────────────────────────────────
    print("🤖 Running AI opening analysis...")
    try:
        prompt   = AIEngine.market_open_prompt(valid_index, movers, validated_news, bull_bear)
        analysis = ai.analyze("fast", prompt)
    except Exception as e:
        print(f"   ⚠️ AI failed: {e}")
        analysis = ""

    # ── Send message ───────────────────────────────────────────────
    msg = "📈 *MARKET OPEN — 9:15 AM IST*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += "\n".join(lines)
    if analysis:
        msg += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n{analysis}"
    msg += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━"

    send_text(msg)
    print("✅ MARKET OPEN COMPLETE")

if __name__ == "__main__":
    main()
