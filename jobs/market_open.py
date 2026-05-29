import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_fetcher    import fetch_global_indices, fetch_top_movers, fetch_general_news, fetch_macro_anchors
from src.ai_engine       import AIEngine
from src.telegram_sender import send_text
from src.validator       import validate_articles, assess_sentiment_consensus
from src.validation_helper import ai_generate_and_validate, build_ground_truth_from_index
from src.delta           import get_relevant_indices, news_fingerprint_hash


def _get_arbiter_regime() -> dict:
    """Read arbitrated regime from MarketState — never recompute.

    Tries today's persisted state first (from 07:00/08:00 job),
    then yesterday's, then builds minimal state as fallback.
    """
    try:
        from datetime import datetime, timedelta
        from src.db import get_market_state, get_latest_market_state
        from src.state import MarketState
        from src.regime_arbiter import arbitrate_regime

        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        # Try today's state first (morning brief should have saved it)
        prev = get_market_state(today)
        if not prev:
            # Try yesterday's state
            prev = get_latest_market_state(before_date=today)
        if prev and prev.get("final_regime"):
            return {
                "regime": prev["final_regime"],
                "confidence": prev.get("final_regime_confidence", "MEDIUM"),
                "dominant_driver": prev.get("final_dominant_driver", ""),
                "posture_text": _posture_for_regime(prev["final_regime"]),
                "watch_levels": _watch_levels_for_regime(prev["final_regime"]),
            }

        # Fallback: build minimal state and call arbiter
        state = MarketState(trade_date=today)
        verdict = arbitrate_regime(state)
        return {
            "regime": verdict.regime,
            "confidence": verdict.confidence,
            "dominant_driver": verdict.dominant_driver,
            "posture_text": _posture_for_regime(verdict.regime),
            "watch_levels": _watch_levels_for_regime(verdict.regime),
        }
    except Exception as e:
        print(f"   ⚠️ Regime fetch: {e}")
        return {
            "regime": "NEUTRAL",
            "confidence": "LOW",
            "dominant_driver": "",
            "posture_text": "No edge",
            "watch_levels": "",
        }


def _posture_for_regime(regime: str) -> str:
    """Map regime to actionable posture."""
    posture_map = {
        "BULLISH": "Add beta; buy dips on support holds.",
        "NEUTRAL": "No edge — range trade; stay light.",
        "DEFENSIVE": "Cut beta, hedge, raise cash; reduce OMCs and oil importers.",
    }
    return posture_map.get(regime, "No edge — stay light.")


def _watch_levels_for_regime(regime: str) -> str:
    """Return regime-specific watch levels."""
    if regime == "DEFENSIVE":
        return "Brent $98 / INR ₹97 / VIX 20"
    if regime == "BULLISH":
        return "VIX spike +5 / Support break"
    return ""

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
    consensus = assess_sentiment_consensus(sentiments) if sentiments else None

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

    # ── Read arbitrated regime from MarketState (single source of truth) ──
    regime_info = _get_arbiter_regime()
    regime_label = regime_info.get("regime", "NEUTRAL")
    regime_confidence = regime_info.get("confidence", "LOW")
    regime_driver = regime_info.get("dominant_driver", "")
    regime_posture_text = regime_info.get("posture_text", "")
    regime_watch_levels = regime_info.get("watch_levels", "")

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

    # ── News fingerprint: cross-job dedup with 08:00 morning brief ──
    from datetime import datetime
    today_str = datetime.now().strftime("%Y-%m-%d")
    news_note = ""
    if validated_news:
        try:
            from src.db import get_bot_state, set_bot_state, get_seen_headlines
            from src.formatters import set_seen_headlines as _set_form_hashes, is_headline_seen, add_seen_headline, get_all_seen_headlines

            # Load persisted hashes from 08:00 job
            try:
                prev_hashes = get_seen_headlines(today_str)
                if prev_hashes:
                    _set_form_hashes(prev_hashes)
            except Exception:
                pass

            current_fp = news_fingerprint_hash([a.get("headline", "") for a in validated_news[:3]])
            prev_fp = get_bot_state("news_fingerprint_open")
            if prev_fp and current_fp == prev_fp:
                news_note = ""  # Suppress entirely — headlines unchanged
            else:
                set_bot_state("news_fingerprint_open", current_fp)
                # Show only headlines not already rendered at 08:00
                fresh = []
                for a in validated_news[:3]:
                    h = a.get("headline", "")
                    if not is_headline_seen(h):
                        trust = a.get("trust_score", 0)
                        source = a.get("source", "unknown")
                        # Truncate at sentence boundary
                        if len(h) > 60:
                            pos = h.rfind('. ', 0, 60)
                            h = h[:pos + 2].rstrip() if pos > 0 else h[:60] + "…"
                        fresh.append(f"{h} ({source}, trust {trust}/10)")
                        add_seen_headline(h)
                if fresh:
                    news_note = f"📰 {fresh[0]}"
                # Persist updated hash set for next jobs
                try:
                    from src.db import save_seen_headlines
                    save_seen_headlines(today_str, get_all_seen_headlines())
                except Exception:
                    pass
        except Exception:
            top = validated_news[0]
            headline = top.get("headline", "")
            # Truncate at sentence boundary
            if len(headline) > 60:
                pos = headline.rfind(". ", 0, 60)
                headline = headline[:pos + 2].rstrip() if pos > 0 else headline[:60] + "…"
            trust    = top.get("trust_score", 0)
            source   = top.get("source", "unknown")
            news_note = f"📰 {headline} ({source}, trust {trust}/10)"

    # ── Pre-market gap classification ─────────────────────────────
    gap_ups   = [m for m in movers.get("india", {}).get("gainers", []) if m.get("change_pct", 0) >= 1.5]
    gap_downs = [m for m in movers.get("india", {}).get("losers", []) if m.get("change_pct", 0) <= -1.5]

    lines = []
    if overnight_note:
        lines.append(overnight_note)

    if gap_ups:
        g_str = ", ".join(f"{m['symbol']} +{m['change_pct']:.1f}%" for m in gap_ups[:3])
        lines.append(f"⚠️ Gap Up: {g_str}")
    if gap_downs:
        d_str = ", ".join(f"{m['symbol']} {m['change_pct']:.1f}%" for m in gap_downs[:3])
        lines.append(f"📉 Gap Down: {d_str}")

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
            # Compress: only show ⚠️ or 🚨 severity variables
            significant = {
                k: v for k, v in consequences.items()
                if v.get("severity") in ("ELEVATED", "HIGH", "STRESS", "EXTREME")
            }
            if significant:
                consequence_block = format_consequence_block(significant)
            else:
                consequence_block = "Macro crosswinds balanced. No urgent tailwinds/headwinds."
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
            emoji = "⚠️"
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
        """Deterministic opening brief — no AI needed."""
        parts = []
        if lines:
            parts.extend(lines)
        if consequence_block:
            parts.append(consequence_block)
        if anomaly_block:
            parts.append(anomaly_block)
        regime_posture = regime_info.get("posture_text", "")
        if regime_posture:
            parts.append(f"Posture: {regime_posture}")
        return "\n".join(parts) if parts else f"Regime: {regime_label}. Opening session begins."

    def send_open(text):
        nifty = valid_index.get("India", {})

        # ── Regime header: single-line reference (full detail in 08:00 Regime Card) ──
        reg_emoji = {"BULLISH": "🟢", "NEUTRAL": "🟡", "DEFENSIVE": "🔴"}.get(regime_label, "")
        nifty_str = f" | Nifty {nifty.get('price'):,.0f}" if nifty.get("price") else ""
        if nifty.get("price") and nifty.get("change_pct") is not None:
            sign = "+" if nifty["change_pct"] >= 0 else ""
            nifty_str += f" ({sign}{nifty['change_pct']:.1f}%)"

        msg = "📈 *MARKET OPEN — 9:15 AM IST*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += f"{reg_emoji} *REGIME: {regime_label}*{nifty_str}\n\n"

        # Note: BLUF narrative omitted — consequence layer provides causal data.
        # The regime header above is the single regime line (phase 31 invariant).
        if lines:
            msg += "\n".join(lines) + "\n"
        if consequence_block:
            msg += f"\n{consequence_block}"
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
