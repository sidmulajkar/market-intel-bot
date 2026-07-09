import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_fetcher      import fetch_global_indices, fetch_general_news, fetch_macro_anchors
from src.heatmap_generator import generate_heatmap
from src.ai_engine         import AIEngine
from src.telegram_sender   import send_image, send_text
from src.validator         import validate_articles, assess_sentiment_consensus
from src.validation_helper import validate_and_send
from src.delta             import get_relevant_indices
from src.formatters        import set_seen_headlines, is_headline_seen, add_seen_headline, get_all_seen_headlines
from src.db                import get_seen_headlines, save_seen_headlines


def _get_evening_regime(valid_index: dict) -> dict:
    """Read arbitrated regime from MarketState — never recompute.

    Tries today's persisted state first, then yesterday's,
    then falls back to building minimal state.
    Returns dict with regime, confidence, dominant_driver, posture_text, watch_levels.
    """
    try:
        from datetime import datetime, timedelta
        from src.state import MarketState
        from src.regime_arbiter import arbitrate_regime
        from src.db import get_market_state, get_latest_market_state

        today = datetime.now().strftime("%Y-%m-%d")

        # Try today's state first
        prev = get_market_state(today)
        if not prev:
            prev = get_latest_market_state(before_date=today)
        if prev and prev.get("final_regime"):
            return {
                "regime": prev["final_regime"],
                "confidence": prev.get("final_regime_confidence", "MEDIUM"),
                "dominant_driver": prev.get("final_dominant_driver", ""),
                "posture_text": "",
                "watch_levels": "",
            }

        # Fallback: build minimal state from available macro data
        state = MarketState(trade_date=today)
        try:
            from src.data_fetcher import fetch_macro_anchors
            anchors = fetch_macro_anchors()
            for a in anchors:
                if not a.get("ok") or not a.get("price"):
                    continue
                name = a.get("name", "")
                if name == "India VIX":
                    state.macro.vix = a["price"]
                elif name == "USD/INR":
                    state.macro.usdinr = a["price"]
                elif name == "Brent Crude":
                    state.macro.brent = a["price"]
        except Exception:
            pass

        verdict = arbitrate_regime(state)
        return {
            "regime": verdict.regime,
            "confidence": verdict.confidence,
            "dominant_driver": verdict.dominant_driver,
            "posture_text": "",
            "watch_levels": "",
        }
    except Exception:
        return {"regime": "NEUTRAL", "confidence": "LOW", "dominant_driver": "", "posture_text": "", "watch_levels": ""}


def _send_evening_brief_confirmation(regime_label: str, valid_index: dict):
    """Send a brief evening confirmation when US is quiet but regime is directional.

    For DEFENSIVE/BEARISH regimes, the user needs overnight posture closure
    even when global markets are quiet.
    """
    # Build a one-liner with key macro data
    parts = [f"{regime_label} regime unchanged."]
    try:
        from src.db import get_latest_market_state
        prev = get_latest_market_state()
        if prev:
            macro = prev.get("macro", {})
            brent = macro.get("brent")
            if brent:
                parts.append(f"Brent holds ${brent:.0f}.")
            usdinr = macro.get("usdinr")
            if usdinr:
                parts.append(f"INR at ₹{usdinr:.1f}.")
    except Exception:
        pass
    parts.append("No new global delta.")
    send_text(f"📌 *Evening:* US session quiet. {' '.join(parts)}")
    print(f"   📌 Quiet US session — {regime_label} confirmation sent")


def main():
    print("=" * 50)
    print("🌃 EVENING REPORT STARTING")
    print("=" * 50)

    index_data  = fetch_global_indices()
    valid_index = {k: v for k, v in index_data.items()
                   if v.get("ok") and v.get("price", 0) > 0}

    # ── Skip gate: is US session worth a full report? ─────────────
    us_evening = get_relevant_indices("20:00", valid_index)
    us_moved = False
    vix_changed = False

    if us_evening:
        for country, d in us_evening.items():
            if d.get("ok") and abs(d.get("change_pct", 0)) >= 0.5:
                us_moved = True
                break

    # Check VIX change vs Indian close baseline
    try:
        from src.db import get_latest_market_state
        prev = get_latest_market_state()
        if prev and prev.get("macro", {}).get("vix"):
            prev_vix = prev["macro"]["vix"]
            cboe_vix_entry = valid_index.get("CBOE VIX", {})
            if cboe_vix_entry.get("ok") and cboe_vix_entry.get("price"):
                curr_vix = cboe_vix_entry["price"]
                if prev_vix > 0 and abs(curr_vix - prev_vix) / prev_vix >= 0.10:
                    vix_changed = True
    except Exception:
        pass

    if not us_moved and not vix_changed:
        # Check if there's any new information worth sending
        # Lightweight news fetch for fingerprint only
        evening_news_quiet = True
        try:
            from src.delta import news_fingerprint_hash
            from src.db import get_bot_state, set_bot_state
            raw_news = fetch_general_news()
            ev_news = validate_articles(raw_news, min_trust=6) if raw_news else []
            if ev_news:
                current_fp = news_fingerprint_hash([a.get("headline", "") for a in ev_news[:3]])
                prev_fp = get_bot_state("news_fingerprint_evening")
                if prev_fp and current_fp == prev_fp:
                    # News unchanged AND US quiet → regime-gated decision
                    regime_info = _get_evening_regime(valid_index)
                    regime_label = regime_info.get("regime", "NEUTRAL")
                    if regime_label in ("DEFENSIVE", "BEARISH"):
                        # Directional regime — send brief confirmation
                        _send_evening_brief_confirmation(regime_label, valid_index)
                        print("✅ EVENING REPORT COMPLETE")
                        return
                    elif regime_label == "NEUTRAL":
                        # Brief keepalive — no notable change, no silent completion
                        send_text(f"📌 *Evening:* US session quiet. NEUTRAL regime unchanged. No new global delta.")
                        print(f"   📌 Quiet US session — NEUTRAL confirmation sent")
                        print("✅ EVENING REPORT COMPLETE")
                        return
                    else:
                        # Directional regime — send brief confirmation
                        send_text(f"📌 *Evening:* US session quiet. {regime_label} regime unchanged. No new global delta.")
                        print(f"   📌 Quiet US session — {regime_label} confirmation sent")
                        print("✅ EVENING REPORT COMPLETE")
                        return
                elif prev_fp:
                    set_bot_state("news_fingerprint_evening", current_fp)
                    evening_news_quiet = False
            else:
                # No news AND US quiet → regime-gated decision
                regime_info = _get_evening_regime(valid_index)
                regime_label = regime_info.get("regime", "NEUTRAL")
                if regime_label in ("DEFENSIVE", "BEARISH"):
                    _send_evening_brief_confirmation(regime_label, valid_index)
                    print("✅ EVENING REPORT COMPLETE")
                    return
                elif regime_label == "NEUTRAL":
                    send_text(f"📌 *Evening:* US session quiet. NEUTRAL regime unchanged. No new global delta.")
                    print(f"   📌 Quiet US session — NEUTRAL confirmation sent")
                    print("✅ EVENING REPORT COMPLETE")
                    return
                else:
                    send_text(f"📌 *Evening:* US session quiet. {regime_label} regime unchanged. No new global delta.")
                    print(f"   📌 Quiet US session — {regime_label} confirmation sent")
                    print("✅ EVENING REPORT COMPLETE")
                    return
        except Exception:
            evening_news_quiet = False

        # Fallback: couldn't determine regime or news — send generic
        send_text("🟡 *Evening:* US session quiet (SPX flat, VIX unchanged). No shift to India outlook.")
        print("   🟡 Quiet US session — one-liner sent")
        print("✅ EVENING REPORT COMPLETE")
        return

    if us_moved:
        print(f"   ⚡ Skip gate: US moved significantly")
    if vix_changed:
        print(f"   ⚡ Skip gate: VIX changed >10%")

    # ── Fetch news + sentiment ─────────────────────────────────────
    news = fetch_general_news()
    ai = AIEngine()
    validated_news = validate_articles(news, min_trust=6) if news else []

    sentiments = []
    for article in validated_news[:5]:
        sent = ai.sentiment(article.get("headline", ""))
        article["sentiment"] = sent
        if sent:
            sentiments.append(sent)
    consensus_sentiment = assess_sentiment_consensus(sentiments) if sentiments else None

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

    # ── Build relevant global indices lines ────────────────────────
    lines = []
    if us_evening:
        for country, d in sorted(us_evening.items(), key=lambda x: abs(x[1].get("change_pct", 0)), reverse=True):
            sign = "+" if d.get("change_pct", 0) >= 0 else ""
            lines.append(f"{d.get('flag','')} {country}: {sign}{d.get('change_pct',0):.2f}% [{d.get('status','?')}]")
    else:
        # Fallback: show all valid indices
        for country, d in valid_index.items():
            sign = "+" if d.get("change_pct", 0) >= 0 else ""
            lines.append(f"{d.get('flag','')} {country}: {sign}{d.get('change_pct',0):.2f}%")

    # ── Nifty close recap ─────────────────────────────────────────
    nifty_close_line = ""
    nifty = valid_index.get("Nifty 50", {}) or valid_index.get("India", {})
    if nifty.get("ok") and nifty.get("price"):
        n_change = nifty.get("change_pct", 0)
        sign = "+" if n_change >= 0 else ""
        nifty_close_line = f"📍 Nifty closed {nifty['price']:,.0f} ({sign}{n_change:.1f}%)"

    # ── AI evening brief ───────────────────────────────────────────
    news_block = ""
    if validated_news:
        # Load cross-job headline dedup hashes
        try:
            from datetime import datetime
            _today = datetime.now().strftime("%Y-%m-%d")
            _prev_hashes = get_seen_headlines(_today)
            if _prev_hashes:
                set_seen_headlines(_prev_hashes)
        except Exception:
            pass

        news_lines = []
        for n in validated_news[:5]:
            headline = n.get("headline", "")[:60]
            trust = n.get("trust_score", 0)
            source = n.get("source", "unknown")
            news_lines.append(f"• {headline} ({source}, trust {trust}/10)")

        news_block = f"\nToday's news:\n{chr(10).join(news_lines)}\n"

        # Persist updated hashes so headlines don't reappear across jobs
        try:
            save_seen_headlines(_today, get_all_seen_headlines())
        except Exception:
            pass

    prompt = f"""
Evening global markets (US session):
{chr(10).join(lines)}
{nifty_close_line}
{news_block}

Market sentiment: {consensus_sentiment.upper() if consensus_sentiment else "NEUTRAL"}

Evening report for Indian investors — factual summary only, NO predictions or trading advice:
1. 🌃 US Session Direction + magnitude
2. 📰 Top Catalyst (from news headlines)
3. 🌍 Overnight Risk Setup (what to watch, not what will happen)
4. 🇮🇳 India context: current regime

Under 100 words. Reference actual data only. No bias, no key levels, no conditionals. Do not use the word 'Posture' or 'posture'. Use 'regime' instead.
"""

    def make_fallback():
        parts = []
        if nifty_close_line:
            parts.append(nifty_close_line)
        parts.extend(lines[:5])
        if validated_news:
            top = validated_news[0]
            parts.append(f"📰 {top.get('headline', '')[:50]}...")

        text = " | ".join(parts[:4])
        # Context line locked to arbiter's regime (never contradicts final_regime)
        _context_map = {
            "BULLISH": "Broad market strength; constructive session.",
            "NEUTRAL": "No dominant macro driver. Range-bound session.",
            "DEFENSIVE": "Elevated macro stress indicators active.",
        }
        regime_label = regime_info.get("regime", "NEUTRAL") if 'regime_info' in dir() else "NEUTRAL"
        context = _context_map.get(regime_label, "Range-bound session.")
        text += f"\n\n📌 *Context:* Regime: {regime_label}. {context}"
        # Watch levels from arbiter's watch_levels (not posture engine)
        watch_levels = regime_info.get("watch_levels", "") if 'regime_info' in dir() else ""
        if watch_levels:
            text += f"\n  Watch: {watch_levels}"
        return text

    def _build_outlook_line():
        """Built from arbiter's watch_levels — not posture engine (avoid regime contradiction)."""
        try:
            from src.db import get_latest_market_state
            prev = get_latest_market_state()
            if prev and prev.get("watch_levels"):
                return f"  Watch: {prev['watch_levels']}"
        except Exception:
            pass
        return ""

    def _build_tomorrow_trap_line():
        """Deterministic forward outlook: key level + overnight risk + catalyst."""
        parts = []
        try:
            # Key level from snapshot
            from src.db import get_latest_market_state
            prev = get_latest_market_state()
            if prev:
                levels = prev.get("key_levels", {})
                support = levels.get("support") or prev.get("support")
                resistance = levels.get("resistance") or prev.get("resistance")
                if support:
                    parts.append(f"Nifty must hold {support}")
            # Macro calendar for next 1-2 days
            from src.macro_calendar import get_macro_calendar
            events = get_macro_calendar(days=3)
            tomorrow = datetime.now() + timedelta(days=1)
            tomorrow_str = tomorrow.strftime("%Y-%m-%d")
            next_events = [e for e in (events or []) if e.get("date", "")[:10] == tomorrow_str]
            if next_events:
                event_names = [e.get("event", e.get("name", "")) for e in next_events[:2]]
                if event_names:
                    parts.append(f"Tomorrow: {', '.join(event_names)}")
            # US market close impact
            if valid_index.get("US"):
                us_change = valid_index["US"].get("change_pct")
                if us_change is not None and abs(us_change) > 0.5:
                    dir_str = "up" if us_change > 0 else "down"
                    parts.append(f"US {dir_str} {abs(us_change):.1f}% — gap {dir_str} risk")
            if not parts:
                return ""
            return "  Tomorrow's Trap: " + " | ".join(parts)
        except Exception:
            return ""

    def send_evening(text):
        bluf = ""
        regime_verdict = {}
        try:
            from src.telegram_sender import build_bluf
            regime_verdict = _get_evening_regime(valid_index)
            bluf = build_bluf(
                regime_verdict=regime_verdict,
            )
        except Exception:
            pass
        msg = "*EVENING REPORT*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        if bluf:
            msg += bluf + "\n\n"
        # Skip duplicate nifty_close_line if BLUF already includes Nifty
        if nifty_close_line and not bluf:
            msg += f"{nifty_close_line}\n\n"
        msg += text
        # Suppress duplicate outlook if AI/fallback already printed watch guidance
        outlook = _build_outlook_line()
        if outlook and "Watch:" not in text:
            msg += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n{outlook}"
        trap = _build_tomorrow_trap_line()
        if trap:
            msg += f"\n{trap}"
        send_text(msg)

    try:
        analysis = ai.analyze("fast", prompt)
    except Exception as e:
        analysis = ""

    # ── Heatmap: only if US moved significantly ────────────────────
    if us_moved:
        try:
            heatmap = generate_heatmap(valid_index)
            send_image(heatmap, caption="🌃 *Evening Global Heatmap — US Session Live*")
            print("   ✅ Evening heatmap sent")
        except Exception as e:
            print(f"   ⚠️ Heatmap failed: {e}")

    sent = validate_and_send(
        analysis, valid_index,
        fallback_fn=make_fallback,
        send_fn=send_evening,
    )
    if sent:
        print("   ✅ AI evening report sent")
    else:
        print("   ⚠️ AI evening report failed validation — sent fallback")

    print("✅ EVENING REPORT COMPLETE")

if __name__ == "__main__":
    main()
