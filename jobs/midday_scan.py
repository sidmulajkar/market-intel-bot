import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_fetcher    import fetch_global_indices, fetch_top_movers, fetch_general_news
from src.ai_engine       import AIEngine
from src.telegram_sender import send_text
from src.validator       import validate_articles, assess_sentiment_consensus
from src.db              import was_alert_sent, log_alert_sent, get_latest_market_state
from src.validation_helper import ai_generate_and_validate, build_ground_truth_from_index


def _get_arbiter_regime() -> dict:
    """Read arbitrated regime from MarketState — never recompute."""
    try:
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        prev = get_latest_market_state(before_date=today)
        if prev and prev.get("final_regime"):
            return {
                "regime": prev["final_regime"],
                "confidence": prev.get("final_regime_confidence", "MEDIUM"),
                "dominant_driver": prev.get("final_dominant_driver", ""),
                "posture_text": "",
                "watch_levels": "",
            }
    except Exception:
        pass
    return {"regime": "NEUTRAL", "confidence": "LOW", "dominant_driver": "", "posture_text": "", "watch_levels": ""}

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
    consensus = assess_sentiment_consensus(sentiments) if sentiments else None

    # ── Conditional skip gate (Phase 26: no signal = no send) ─────
    # Skip unless: Nifty moved >1% from open, OR VIX spiked >20%, OR extreme moves detected
    nifty = valid_index.get("India", {})
    vix = valid_index.get("India VIX", {})
    nifty_change_abs = abs(nifty.get("change_pct", 0))
    nifty_change_pct = nifty.get("change_pct", 0)
    vix_spike = False
    if vix and vix.get("price"):
        vix_price = vix.get("price", 0)
        # Check if VIX spiked >20% from typical morning baseline (~16)
        try:
            from src.db import get_latest_market_state
            from src.state import MarketState
            prev = get_latest_market_state()
            if prev and prev.get("macro", {}).get("vix"):
                prev_vix = prev["macro"]["vix"]
                if prev_vix > 0 and (vix_price - prev_vix) / prev_vix > 0.20:
                    vix_spike = True
        except Exception:
            pass

    # Pre-scan for extreme moves (needed for skip gate)
    alerts = []
    india_all = movers.get("india", {}).get("gainers", []) + movers.get("india", {}).get("losers", [])
    for m in india_all:
        change = abs(m.get("change_pct", 0))
        sym = m.get("symbol", "")
        if change >= 5.0:
            alerts.append(m)

    has_extreme = len(alerts) > 0
    nifty_moved = nifty_change_abs > 1.0

    if not nifty_moved and not vix_spike and not has_extreme:
        # No push on quiet days — regime card is the pinned source of truth
        skip_note = f"Nifty {nifty_change_pct:+.2f}% | Skip: >1.0%"
        print(f"   🟡 Quiet session — no Telegram push ({skip_note})")
        print("✅ MIDDAY SCAN COMPLETE")
        return

    if nifty_moved:
        print(f"   ⚡ Skip gate: Nifty moved {nifty_change_abs:.1f}%")
    if vix_spike:
        print(f"   ⚡ Skip gate: VIX spiked >20%")
    if has_extreme:
        print(f"   ⚡ Skip gate: {len(alerts)} extreme moves detected")

    # ── Remove global indices from midday snapshot (Phase 26: stale at 12:30)
    # Build local snapshot only — no global indices at midday
    lines = []

    # Nifty + VIX line
    if nifty:
        nifty_change = nifty.get("change_pct", 0)
        nifty_emoji  = "🟢" if nifty_change > 0 else ("🔴" if nifty_change < 0 else "⚪")
        vix_note     = ""
        if vix and vix.get("price"):
            vix_price = vix.get("price", 0)
            vix_note  = f" | VIX {vix_price:.1f}"
        lines.append(f"{nifty_emoji} Nifty {nifty.get('price', 0):,.0f} ({nifty_change:+.1f}%){vix_note}")

    # Top gainers + losers from dynamic movers
    india_g = movers.get("india", {}).get("gainers", [])
    india_l = movers.get("india", {}).get("losers", [])
    if india_g:
        g_str = ", ".join(f"{m['symbol']} +{m['change_pct']:.1f}%" for m in india_g[:3])
        lines.append(f"🟢 Gainers: {g_str}")
    if india_l:
        l_str = ", ".join(f"{m['symbol']} {m['change_pct']:.1f}%" for m in india_l[:3])
        lines.append(f"🔴 Losers: {l_str}")

    # News headline (only if fresh — check fingerprint)
    if validated_news:
        try:
            from src.db import get_bot_state, set_bot_state
            from src.delta import news_fingerprint_hash
            current_fp = news_fingerprint_hash([a.get("headline", "") for a in validated_news[:3]])
            prev_fp = get_bot_state("news_fingerprint_midday")
            if not prev_fp or current_fp != prev_fp:
                set_bot_state("news_fingerprint_midday", current_fp)
                top = validated_news[0]
                headline = top.get("headline", "")[:60]
                trust    = top.get("trust_score", 0)
                source   = top.get("source", "unknown")
                lines.append(f"📰 {headline} ({source}, Trust:{trust}/10)")
            else:
                lines.append("📰 Headlines unchanged")
        except Exception:
            top = validated_news[0]
            headline = top.get("headline", "")[:60]
            trust    = top.get("trust_score", 0)
            source   = top.get("source", "unknown")
            lines.append(f"📰 {headline} ({source}, Trust:{trust}/10)")

    # ── Stock-level alerts (format pre-scanned extreme moves) ────
    formatted_alerts = []
    for m in alerts:
        sym = m.get("symbol", "")
        emoji = "⚠️" if m.get("change_pct", 0) > 0 else "⚠️"
        key = f"midday_extreme_{sym}"
        if not was_alert_sent(sym, key):
            formatted_alerts.append(f"{emoji} *{sym}* {m['change_pct']:+.1f}% — extreme move")
            log_alert_sent(sym, key)
    alerts = formatted_alerts

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

    regime_info = _get_arbiter_regime()

    if prompt and ground_truth.get("nifty_close"):
        # Snapshot already in `lines` above — send_midday uses it directly
        def send_midday(text):
            bluf = ""
            try:
                from src.telegram_sender import build_bluf
                bluf = build_bluf(
                    regime_verdict=regime_info,
                )
            except Exception:
                pass
            msg = "📊 *MIDDAY MARKET SCAN*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            if bluf:
                msg += bluf + "\n\n"
            msg += "\n".join(lines)
            if text:
                msg += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n{text}"
            if alerts:
                msg += f"\n\n⚠️ *Extreme Moves:*\n" + "\n".join(alerts)
            msg += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n_Mid-session check_"
            send_text(msg)

        ai_generate_and_validate(
            ai, "fast", prompt, ground_truth,
            output_type="midday_scan",
            fallback_fn=lambda: "",
            send_fn=send_midday,
            max_retries=1,
        )
    else:
        # No ground truth or no prompt — send unvalidated (degraded)
        msg = "📊 *MIDDAY MARKET SCAN*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += "\n".join(lines)
        if alerts:
            msg += f"\n\n⚠️ *Extreme Moves:*\n" + "\n".join(alerts)
        msg += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n_Mid-session check_"
        send_text(msg)
    print("✅ MIDDAY SCAN COMPLETE")

if __name__ == "__main__":
    main()
