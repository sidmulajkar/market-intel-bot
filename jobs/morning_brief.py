import os
import sys

# GUARANTEED PATH FIX - works on all systems
_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_dir)
if _root not in sys.path:
    sys.path.insert(0, _root)

# Verify path fix worked before importing
import importlib.util
_spec = importlib.util.find_spec("src.data_fetcher")
if _spec is None:
    print(f"ERROR: src not found. sys.path = {sys.path}")
    print(f"_root = {_root}")
    print(f"Files in _root: {os.listdir(_root)}")
    sys.exit(1)

print(f"✅ Path confirmed: {_root}")

from src.data_fetcher      import fetch_global_indices, fetch_watchlist_data, fetch_general_news, fetch_top_movers
from src.heatmap_generator  import generate_heatmap
from src.sector_heatmap    import generate_sector_heatmap, generate_watchlist_heatmap, generate_top_movers_heatmap
from src.ai_engine         import AIEngine
from src.telegram_sender   import send_image, send_text, fmt_morning_report
from src.db                import save_daily_snapshot, get_watchlist, purge_old_data

from src.validator         import validate_articles, assess_sentiment_consensus


def validate_ai_response(response: str, min_words: int = 50) -> bool:
    """
    Validate AI response before sending.
    Returns True if response is valid (not None, not empty, word count >= min_words).
    """
    if not response or not isinstance(response, str):
        return False
    word_count = len(response.split())
    return word_count >= min_words


def get_fallback_brief(index_data: dict, validated_news: list, sentiment: str) -> str:
    """
    Fallback when AI fails - format raw data as structured text.
    """
    lines = []
    lines.append("📊 *Morning Market Snapshot*\n")

    # Global indices summary
    if index_data:
        lines.append("🌍 *Global Indices:*")
        for country, d in list(index_data.items())[:5]:
            if d.get("ok"):
                change = d.get("change_pct", 0)
                sign = "+" if change >= 0 else ""
                lines.append(f"  • {country}: {sign}{change:.2f}%")

    # News summary
    if validated_news:
        lines.append("\n📰 *Top Headlines:*")
        for article in validated_news[:3]:
            headline = article.get("headline", "")[:60]
            if headline:
                lines.append(f"  • {headline}...")

    # Sentiment
    if sentiment:
        lines.append(f"\n💭 *Market Sentiment:* {sentiment.title()}")

    return "\n".join(lines)


def main():
    print("=" * 50)
    print("🌅 MORNING BRIEF STARTING")
    print("=" * 50)

    # ── DB Cleanup ─────────────────────────────────────────────────
    try:
        purge_result = purge_old_data()
        print(f"🧹 DB cleanup: {purge_result['sent_alerts']} alerts, {purge_result['snapshots']} snapshots")
    except Exception as e:
        print(f"⚠️  DB cleanup failed: {e}")

    # ── Validate Yesterday's Prediction ───────────────────────────
    try:
        from src.prediction_tracker import validate_yesterday_prediction
        validation = validate_yesterday_prediction()
        if validation.get("ok"):
            emoji = "✅" if validation.get("regime_correct") else "❌"
            print(f"📊 Prediction validation: {emoji} {validation.get('predicted_regime')} vs {validation.get('actual_regime')}")

            # ── Record signal accuracy for dynamic weighting ────
            try:
                from src.prediction_tracker import record_signals_that_fired
                from src.context_engine import get_fii_dii_context, get_macro_context

                fii_ctx = get_fii_dii_context(days=30)
                macro_ctx = get_macro_context()

                # Determine actual direction from change
                change_pct = validation.get("change_pct", 0)
                actual_direction = "UP" if change_pct > 0.3 else "DOWN" if change_pct < -0.3 else "FLAT"

                record_signals_that_fired(
                    fii_context=fii_ctx if fii_ctx.get("ok") else {},
                    macro_context=macro_ctx if macro_ctx else {},
                    extra_signals={},
                    actual_direction=actual_direction,
                    nifty_return=change_pct,
                )
            except Exception as e:
                print(f"⚠️  Signal accuracy recording: {e}")
    except Exception as e:
        print(f"⚠️  Prediction validation: {e}")

    stocks = get_watchlist()
    print(f"📋 Watchlist: {len(stocks)} stocks — {stocks}")

    if not stocks:
        send_text(
            "⚠️ *Morning Brief*\n"
            "Watchlist is empty!\n"
            "Add stocks: `/add SYMBOL`"
        )
        return

    # ── Global Heatmap ────────────────────────────────────────────
    print("🌍 Fetching global indices...")
    index_data  = fetch_global_indices()
    valid_index = {
        k: v for k, v in index_data.items()
        if v.get("ok") and v.get("price", 0) > 0
    }
    print(f"   Valid: {len(valid_index)}/18")

    try:
        send_image(
            generate_heatmap(valid_index),
            caption="🌍 *World Equity Heatmap*"
        )
        print("   ✅ World heatmap sent")
    except Exception as e:
        print(f"   ⚠️ World heatmap failed: {e}")

    # ── Sector Heatmap ────────────────────────────────────────────
    try:
        send_image(
            generate_sector_heatmap(),
            caption="🏭 *India Sector Heatmap*"
        )
        print("   ✅ Sector heatmap sent")
    except Exception as e:
        print(f"   ⚠️ Sector heatmap failed: {e}")

    # ── Top Movers Heatmap (India + US separately) ────────────────
    print("📊 Fetching top movers for heatmap...")
    try:
        movers = fetch_top_movers(top_n=10)
        send_image(
            generate_top_movers_heatmap(movers),
            caption="📊 *Top Market Movers — India & US*"
        )
        print("   ✅ Top movers heatmap sent")
    except Exception as e:
        print(f"   ⚠️ Top movers heatmap failed: {e}")

    # ── Fetch & Validate News ─────────────────────────────────────
    print("📰 Fetching and validating news...")
    raw_news = fetch_general_news()
    validated_news = validate_articles(raw_news, min_trust=6) if raw_news else []

    # Get sentiment for each validated headline
    ai = AIEngine()
    sentiments = []
    for article in validated_news[:5]:  # Top 5 only
        sent = ai.sentiment(article.get("headline", ""))
        article["sentiment"] = sent
        if sent:
            sentiments.append(sent)

    consensus_sentiment = assess_sentiment_consensus(sentiments) if sentiments else "neutral"
    print(f"   Validated: {len(validated_news)} articles, consensus: {consensus_sentiment}")

    # ── AI Brief ─────────────────────────────────────────────────
    print("🤖 Running AI analysis...")
    try:
        prompt = AIEngine.morning_brief_prompt(valid_index, validated_news, consensus_sentiment)
        brief  = ai.analyze("fast", prompt)

        # Validate AI response - never send blank
        if validate_ai_response(brief, min_words=50):
            send_text(fmt_morning_report(brief))
            print("   ✅ AI brief sent")
        else:
            # Fallback to raw data
            fallback = get_fallback_brief(valid_index, validated_news, consensus_sentiment)
            send_text(fallback)
            print("   ⚠️ AI response too short - sent fallback")
    except Exception as e:
        print(f"   ⚠️ AI brief failed: {e}")
        fallback = get_fallback_brief(valid_index, validated_news, consensus_sentiment)
        send_text(fallback)

    # ── Watchlist Alerts ──────────────────────────────────────────
    print("📈 Checking watchlist alerts...")
    try:
        wl_data = fetch_watchlist_data(stocks)
        alerts  = []
        for sym, d in wl_data.items():
            if not d.get("ok"):
                continue
            change = d.get("day_change", 0)
            if abs(change) >= 3.0:
                emoji = "🟢" if change > 0 else "🔴"
                alerts.append(f"{emoji} *{sym}*: {change:+.2f}%")
            if d.get("volume_spike"):
                alerts.append(f"⚡ *{sym}*: Volume spike!")
        if alerts:
            send_text(
                "🔔 *Pre-Market Alerts*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                + "\n".join(alerts)
            )
    except Exception as e:
        print(f"   ⚠️ Alert scan failed: {e}")

    # ── Save Snapshot ─────────────────────────────────────────────
    try:
        save_daily_snapshot(valid_index)
    except Exception as e:
        print(f"   ⚠️ Snapshot failed: {e}")

    # ── Market State Dashboard ─────────────────────────────────────
    try:
        from src.data_fetcher import fetch_macro_anchors
        from src.context_engine import run_contextualization, compute_market_phase
        from src.formatters import format_market_state_dashboard

        anchors = fetch_macro_anchors()
        ctx = run_contextualization(anchors)

        # Institutional signals
        inst_signals = {}
        try:
            from src.quant_enrichment import (
                compute_sector_regime, compute_volatility_setup,
                compute_risk_appetite, compute_breadth_thrust,
                compute_fii_institutional_footprint
            )
            from src.db import get_macro_history, get_breadth_history, get_fii_institutions

            # Sector regime from top movers
            _sector_perf = {}
            for m in (movers.get("india", {}).get("gainers", []) + movers.get("india", {}).get("losers", [])):
                sym = m.get("symbol", "")
                if sym in ("HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK"):
                    _sector_perf.setdefault("BANK", []).append(m.get("weekly_pct", m.get("change_pct", 0)))
                elif sym in ("TCS", "INFY", "WIPRO", "TECHM"):
                    _sector_perf.setdefault("IT", []).append(m.get("weekly_pct", m.get("change_pct", 0)))
                elif sym in ("SUNPHARMA", "DRREDDY"):
                    _sector_perf.setdefault("PHARMA", []).append(m.get("weekly_pct", m.get("change_pct", 0)))
                elif sym in ("HINDUNILVR", "ITC"):
                    _sector_perf.setdefault("FMCG", []).append(m.get("weekly_pct", m.get("change_pct", 0)))
            avg_sector = {k: round(sum(v)/len(v), 2) for k, v in _sector_perf.items() if v}
            inst_signals["sector_regime"] = compute_sector_regime(avg_sector)

            _vix_hist = get_macro_history("India VIX", days=90)
            _vix_vals = [v.get("price", 0) for v in _vix_hist if v.get("price")]
            if _vix_vals:
                inst_signals["volatility_setup"] = compute_volatility_setup(_vix_vals, _vix_vals[-1])

            sr = inst_signals.get("sector_regime", {})
            if sr.get("ok"):
                _perf = {s: v for s, v in sr.get("leaders", []) + sr.get("laggards", [])}
                inst_signals["risk_appetite"] = compute_risk_appetite(_perf)

            _breadth = get_breadth_history(days=30)
            if _breadth:
                inst_signals["breadth_thrust"] = compute_breadth_thrust(_breadth)

            _inst = get_fii_institutions(days=30)
            if _inst:
                inst_signals["fii_footprint"] = compute_fii_institutional_footprint(_inst)
        except Exception:
            pass

        earnings_regime = {"ok": False}
        try:
            from src.earnings_tracker import compute_earnings_regime
            earnings_regime = compute_earnings_regime()
        except Exception:
            pass

        market_phase = compute_market_phase(ctx, inst_signals, earnings_regime)
        dashboard = format_market_state_dashboard(market_phase, ctx)
        if dashboard:
            send_text(dashboard)
            print("   → Market State Dashboard sent")
    except Exception as e:
        print(f"   ⚠️ Market State Dashboard: {e}")

    print("=" * 50)
    print("✅ MORNING BRIEF COMPLETE")
    print("=" * 50)


if __name__ == "__main__":
    main()
