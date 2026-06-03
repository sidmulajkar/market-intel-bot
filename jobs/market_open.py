import sys
import os
import hashlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_fetcher    import fetch_global_indices, fetch_top_movers, fetch_general_news, fetch_macro_anchors
from src.telegram_sender import send_text
from src.validator       import validate_articles
from src.delta           import get_relevant_indices, news_fingerprint_hash
from src.formatters      import format_options_block


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
    """Map regime to description — factual only, no trading advice."""
    posture_map = {
        "BULLISH": "Constructive — broad-based participation.",
        "NEUTRAL": "Neutral — range-bound with balanced risks.",
        "DEFENSIVE": "Defensive — elevated macro stress indicators.",
    }
    return posture_map.get(regime, "Neutral — balanced posture.")


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

    validated_news = validate_articles(raw_news, min_trust=6) if raw_news else []

    valid_index = {
        k: v for k, v in index_data.items()
        if v.get("ok") and v.get("price", 0) > 0
    }
    print(f"   Indices: {len(valid_index)}/18 | Movers: {len(movers.get('india',{}).get('gainers',[]))} gainers")

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

    # ── Corporate Actions (why stocks gap: dividend/bonus/split) ──
    try:
        from src.corporate_actions import (
            NIFTY_50, fetch_corporate_actions_nse, format_corporate_actions,
            save_corporate_actions, fetch_cached_actions, merge_corporate_actions,
        )
        # Live fetch: Nifty 50 only (~50 calls = ~15s)
        live = fetch_corporate_actions_nse(symbols=NIFTY_50)
        # Cache read: watchlist actions from Sunday scan
        cached = fetch_cached_actions()
        ca_result = merge_corporate_actions(live, cached)
        ca_str = format_corporate_actions(ca_result)
        if ca_str:
            lines.append("")
            lines.append(ca_str)
            print(f"   → Corp actions: {len(ca_str)} chars")
        # Persist to Supabase for downstream jobs
        try:
            save_corporate_actions(ca_result)
        except Exception:
            pass
    except Exception as e:
        print(f"   ⚠️ Corp actions: {e}")

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

    # ── Bulk/Block Deals ──────────────────────────────────────────
    deals_block = ""
    try:
        from src.insider_tracker import get_market_insider_activity
        deals = get_market_insider_activity(days=10)
        if deals.get("ok") and deals.get("symbol_flows"):
            deal_lines = []
            for sf in deals["symbol_flows"][:3]:
                net = sf["net_val_cr"]
                if abs(net) > 5:  # only show material deals >₹5 Cr
                    emoji = "🟢" if net > 0 else "🔴"
                    deal_lines.append(f"{emoji} {sf['symbol']}: {sf['buy_val_cr']:.0f}₹ / {sf['sell_val_cr']:.0f}₹ out → net {sf['net_val_cr']:+.0f}₹ Cr")
            if deal_lines:
                deals_block = "📦 *Bulk/Block Deals:*\n" + "\n".join(deal_lines) + "\n⚠️ SEBI filings lag ~10 days"
                # Store hash for cross-job dedup (midday_scan checks this)
                try:
                    from src.db import set_bot_state
                    set_bot_state("deals_hash_morning", hashlib.md5(deals_block.encode()).hexdigest())
                except Exception:
                    pass
    except Exception as e:
        print(f"   ⚠️ Deals fetch: {e}")

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
            parts.append(f"{m['symbol']} {m['change_pct']:+.1f}%")
        anomaly_block = f"⚡ *Anomalies (3%+):* {'; '.join(parts)}"

    # ── Derivatives snapshot (PCR, Max Pain, GEX) ─────────────────
    derivs_block = ""
    try:
        derivs_block = format_options_block(symbol="NIFTY", run_label="morning")
        print(f"   → Derivatives: {len(derivs_block)} chars")
    except Exception as e:
        print(f"   ⚠️ Derivatives: {e}")

    # ── Build Python postscript (no AI — deterministic) ────────────
    gap_direction = "No Gaps"
    n_gap_up = len(gap_ups)
    n_gap_down = len(gap_downs)
    if n_gap_up > 0 and n_gap_down > 0:
        gap_direction = f"Mixed Gaps ({n_gap_up} up, {n_gap_down} down)"
    elif n_gap_up > 0:
        gap_direction = f"Gap Up ({n_gap_up})"
    elif n_gap_down > 0:
        gap_direction = f"Gap Down ({n_gap_down})"

    # Top consequence for postscript
    top_consequence = ""
    for a in macro_anchors:
        name = a.get("name", "")
        if name == "Brent Crude" and a.get("ok") and a.get("price") and a.get("price", 0) >= 80:
            top_consequence = f"Brent ${a['price']:.0f} CAD material"
            break
    if not top_consequence:
        for a in macro_anchors:
            name = a.get("name", "")
            if name == "USD/INR" and a.get("ok") and a.get("price") and a.get("price", 0) >= 87:
                top_consequence = f"INR ₹{a['price']:.1f} stress"
                break
    if not top_consequence:
        for a in macro_anchors:
            name = a.get("name", "")
            if name == "India VIX" and a.get("ok") and a.get("price") and a.get("price", 0) >= 18:
                top_consequence = f"VIX {a['price']:.1f} elevated"
                break

    posture_line = f"📌 Open Posture: {regime_label} | {gap_direction}"
    if top_consequence:
        posture_line += f" | {top_consequence}"

    # ── Build and send deterministic opening brief ─────────────────
    nifty = valid_index.get("India", {})
    reg_emoji = {"BULLISH": "🟢", "NEUTRAL": "🟡", "DEFENSIVE": "🔴"}.get(regime_label, "")
    # Use stored prior-close anchor for consistent baseline (Fix 5)
    from datetime import datetime
    from src.db import get_market_state
    ms = get_market_state(datetime.now().strftime("%Y-%m-%d"))
    prior_close = ms.get("nifty_prior_close") if ms else None
    if nifty.get("price"):
        if prior_close and prior_close > 0:
            nifty_change = round(((nifty["price"] / prior_close) - 1) * 100, 2)
        else:
            nifty_change = nifty.get("change_pct")
        sign = "+" if nifty_change and nifty_change >= 0 else ""
        nifty_str = f" | Nifty {nifty['price']:,.0f} ({sign}{nifty_change:.1f}%)" if nifty_change is not None else f" | Nifty {nifty['price']:,.0f}"
    else:
        nifty_str = ""

    msg = "📈 *MARKET OPEN — 9:15 AM IST*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    msg += f"{reg_emoji} *REGIME: {regime_label}*{nifty_str}\n\n"
    if lines:
        msg += "\n".join(lines) + "\n"
    if consequence_block:
        msg += f"\n{consequence_block}"
    if compound_lines:
        msg += "\n\n" + "\n".join(compound_lines)
    if derivs_block:
        msg += f"\n\n{derivs_block}"
    if deals_block:
        msg += f"\n\n{deals_block}"
    if anomaly_block:
        msg += f"\n\n{anomaly_block}"
    msg += f"\n\n{posture_line}"
    msg += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━"
    send_text(msg)

    print("✅ MARKET OPEN COMPLETE")

if __name__ == "__main__":
    main()
