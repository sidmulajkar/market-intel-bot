import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_fetcher    import fetch_global_indices, fetch_top_movers, fetch_general_news, fetch_macro_anchors
from src.ai_engine       import AIEngine
from src.telegram_sender import send_text
from src.validator       import validate_articles, assess_sentiment_consensus
from src.validation_helper import ai_generate_and_validate, build_ground_truth_from_index
from src.delta           import get_relevant_indices, news_fingerprint_hash

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

    # ── Get bull/bear context + macro anchors ──────────────────────
    bull_bear = {}
    macro_anchors = []
    try:
        from src.context_engine import run_contextualization
        anchor_data = fetch_macro_anchors()
        if anchor_data:
            macro_anchors = anchor_data
            ctx = run_contextualization(anchor_data)
            bull_bear = ctx.get("bull_bear", {})
    except Exception as e:
        print(f"   ⚠️ Context engine: {e}")

    # ── Delta check: what moved since morning brief (8AM)? ────────
    overnight_note = ""
    try:
        relevant = get_relevant_indices("09:15", valid_index)
        if relevant:
            parts = []
            for country, d in relevant.items():
                if d.get("ok") and d.get("change_pct") is not None:
                    sign = "+" if d.get("change_pct", 0) >= 0 else ""
                    parts.append(f"{d.get('flag','')} {country} {sign}{d.get('change_pct',0):.1f}%")
            if parts:
                overnight_note = f"🌍 Overnight: {' | '.join(parts[:3])}"
    except Exception:
        pass

    # ── News fingerprint: avoid repeating stale headlines ─────────
    news_note = ""
    if validated_news:
        try:
            from src.db import get_bot_state, set_bot_state
            current_fp = news_fingerprint_hash([a.get("headline", "") for a in validated_news[:3]])
            prev_fp = get_bot_state("news_fingerprint_open")
            if prev_fp and current_fp == prev_fp:
                news_note = "📰 Headlines unchanged since morning."
            else:
                set_bot_state("news_fingerprint_open", current_fp)
                top = validated_news[0]
                headline = top.get("headline", "")[:60]
                trust    = top.get("trust_score", 0)
                source   = top.get("source", "unknown")
                news_note = f"📰 {headline} ({source}, Trust:{trust}/10)"
        except Exception:
            top = validated_news[0]
            headline = top.get("headline", "")[:60]
            trust    = top.get("trust_score", 0)
            source   = top.get("source", "unknown")
            news_note = f"📰 {headline} ({source}, Trust:{trust}/10)"

    # ── Pre-market gap classification ─────────────────────────────
    gap_ups   = [m for m in movers.get("india", {}).get("gainers", []) if m.get("change_pct", 0) >= 1.5]
    gap_downs = [m for m in movers.get("india", {}).get("losers", []) if m.get("change_pct", 0) <= -1.5]

    lines = []
    if overnight_note:
        lines.append(overnight_note)

    if gap_ups:
        g_str = ", ".join(f"{m['symbol']} +{m['change_pct']:.1f}%" for m in gap_ups[:3])
        lines.append(f"🚀 Gap Up: {g_str}")
    if gap_downs:
        d_str = ", ".join(f"{m['symbol']} {m['change_pct']:.1f}%" for m in gap_downs[:3])
        lines.append(f"🔻 Gap Down: {d_str}")

    if news_note:
        lines.append(news_note)

    # ── Consequence mapping: macro events → India sector impact ───
    consequence_block = ""
    compound_lines = []
    try:
        from src.consequence_engine import (
            compute_all_consequences, format_consequence_block,
            compute_compound_consequences,
        )
        consequences = compute_all_consequences(macro_anchors)
        if consequences:
            consequence_block = format_consequence_block(consequences)
        # Cross-asset compounding (e.g., USDINR extreme → amplify oil impact)
        compound_lines = compute_compound_consequences(macro_anchors)
    except Exception as e:
        print(f"   ⚠️ Consequence mapping: {e}")

    # ── Anomaly scan: stocks >3% pre-market on unusual volume ────
    anomaly_block = ""
    all_india = (
        movers.get("india", {}).get("gainers", []) +
        movers.get("india", {}).get("losers", [])
    )
    anomalies = [m for m in all_india if abs(m.get("change_pct", 0)) >= 3.0]
    if anomalies:
        parts = []
        for m in anomalies[:3]:
            emoji = "🚀" if m.get("change_pct", 0) > 0 else "💥"
            parts.append(f"{emoji} {m['symbol']} {m['change_pct']:+.1f}%")
        anomaly_block = f"⚡ *Anomalies (3%+):* {'; '.join(parts)}"

    # ── Build ground truth for validation ──────────────────────────
    gt_extra = {}
    if bull_bear.get("score") is not None:
        gt_extra["bull_bear_score"] = bull_bear["score"]
    for a in macro_anchors:
        name = a.get("name", "")
        if name == "India VIX" and a.get("ok") and a.get("price"):
            gt_extra["india_vix"] = a["price"]
        elif name == "Brent Crude" and a.get("ok") and a.get("price"):
            gt_extra["brent"] = a["price"]
    ground_truth = build_ground_truth_from_index(valid_index, gt_extra if gt_extra else None)

    # ── AI opening brief (with universal validation) ───────────────
    print("🤖 Running AI opening analysis...")
    try:
        prompt = AIEngine.market_open_prompt(valid_index, movers, validated_news, bull_bear)
    except Exception as e:
        print(f"   ⚠️ Prompt build failed: {e}")
        prompt = ""

    def make_fallback():
        return ""

    def send_open(text):
        msg = "📈 *MARKET OPEN — 9:15 AM IST*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += "\n".join(lines)
        if consequence_block:
            msg += f"\n\n{consequence_block}"
        if compound_lines:
            msg += "\n\n" + "\n".join(compound_lines)
        if anomaly_block:
            msg += f"\n\n{anomaly_block}"
        if text:
            msg += f"\n\n{text}"
        msg += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━"
        send_text(msg)

    if prompt and ground_truth.get("nifty_close"):
        ai_generate_and_validate(
            ai, "fast", prompt, ground_truth,
            output_type="market_open",
            fallback_fn=make_fallback,
            send_fn=send_open,
            max_retries=1,
        )
    else:
        if not ground_truth.get("nifty_close"):
            print("   ⚠️ No Nifty price — skipping AI validation")
        send_text(make_fallback())

    print("✅ MARKET OPEN COMPLETE")

if __name__ == "__main__":
    main()
