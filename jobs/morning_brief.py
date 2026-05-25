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
from src.validation_helper import validate_and_send


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

        def make_fallback():
            return get_fallback_brief(valid_index, validated_news, consensus_sentiment)

        sent = validate_and_send(
            brief, valid_index,
            fallback_fn=make_fallback,
            send_fn=send_text,
            fmt_fn=fmt_morning_report,
        )
        if sent:
            print("   ✅ AI brief sent")
        else:
            print("   ⚠️ AI brief failed validation — sent fallback")
    except Exception as e:
        print(f"   ⚠️ AI brief failed: {e}")
        fallback = get_fallback_brief(valid_index, validated_news, consensus_sentiment)
        send_text(fallback)

    # ── Watchlist Alerts (Sector Grouped) ──────────────────────────
    STOCK_SECTORS = {
        "RELIANCE": "ENERGY", "TCS": "IT", "INFY": "IT", "HDFCBANK": "BANKING",
        "ICICIBANK": "BANKING", "WIPRO": "IT", "TATASTEEL": "STEEL",
        "JSWSTEEL": "STEEL", "LT": "INFRA", "BHARTIARTL": "TELECOM",
        "ASIANPAINT": "PAINT", "MARUTI": "AUTO", "TATAMOTORS": "AUTO",
        "SUNPHARMA": "PHARMA", "DRREDDY": "PHARMA", "HINDUNILVR": "FMCG",
        "ITC": "FMCG", "NTPC": "POWER", "POWERGRID": "POWER",
        "ONGC": "ENERGY", "COALINDIA": "MINING", "ADANIPORTS": "INFRA",
        "BAJFINANCE": "NBFC", "BAJAJFINSV": "NBFC", "SBIN": "BANKING",
        "AXISBANK": "BANKING", "KOTAKBANK": "BANKING", "TECHM": "IT",
        "HCLTECH": "IT", "ULTRACEMCO": "CEMENT", "GRASIM": "CEMENT",
        "NESTLEIND": "FMCG", "BRITANNIA": "FMCG", "TITAN": "LUXURY",
        "DIVISLAB": "PHARMA", "CIPLA": "PHARMA", "EICHERMOT": "AUTO",
        "HEROMOTOCO": "AUTO", "BAJAJ-AUTO": "AUTO", "BPCL": "ENERGY",
        "HINDALCO": "METAL", "VEDL": "METAL",
        "AAPL": "US-TECH", "TSLA": "US-TECH", "NVDA": "US-TECH",
        "MSFT": "US-TECH", "AMZN": "US-TECH", "GOOGL": "US-TECH",
    }

    # Sector keywords for matching news to sectors (Phase 23: word-boundary matching)
    SECTOR_KEYWORDS = {
        "METAL": [r"iron ore", r"steel", r"metal", r"china pmi", r"commodit", r"copper", r"aluminium"],
        "IT": [r"tech", r"software", r"h1b", r"outsourcing", r"digital", r"\bai\b", r"cloud"],
        "BANKING": [r"bank", r"rbi", r"rate cut", r"rate hike", r"credit", r"npa", r"repo"],
        "AUTO": [r"auto", r"car", r"vehicle", r"\bev\b", r"sales data", r"dispatch"],
        "PHARMA": [r"pharma", r"drug", r"fda", r"healthcare", r"medicine"],
        "ENERGY": [r"oil", r"crude", r"opec", r"energy", r"fuel", r"petrol", r"diesel"],
        "FMCG": [r"fmcg", r"consumer", r"retail", r"demand", r"rural"],
        "INFRA": [r"infra", r"construction", r"cement", r"capex", r"government spending"],
        "NBFC": [r"nbfc", r"finance", r"lending", r"credit growth"],
        "STEEL": [r"steel", r"iron ore", r"china demand", r"metal"],
    }
    # Compile regex patterns for word-boundary matching
    import re
    _SECTOR_PATTERNS = {
        sector: [re.compile(rf"(?i)\b{pat}\b" if not pat.endswith(r"\b") else rf"(?i){pat}")
                 for pat in pats]
        for sector, pats in SECTOR_KEYWORDS.items()
    }

    print("📈 Checking watchlist alerts...")
    try:
        wl_data = fetch_watchlist_data(stocks)
        sector_alerts = {}  # sector -> [(symbol, change, vol_ratio)]
        vol_spikes = []     # high volume but low price change

        for sym, d in wl_data.items():
            if not d.get("ok"):
                continue
            change = d.get("day_change", 0)
            vol = d.get("volume", 0)
            avg_vol = d.get("avg_volume", 1) or 1
            vol_ratio = round(vol / avg_vol, 1) if avg_vol > 0 else 0

            # Clean symbol name (remove .NS suffix)
            clean_sym = sym.replace(".NS", "").replace(".BO", "")
            sector = STOCK_SECTORS.get(clean_sym, "OTHER")

            if abs(change) >= 2.5:
                if sector not in sector_alerts:
                    sector_alerts[sector] = []
                sector_alerts[sector].append((clean_sym, change, vol_ratio))
            elif vol_ratio >= 2.5:
                # High volume without big price move — unusual
                vol_spikes.append((clean_sym, change, vol_ratio))

        # Match news headlines to sectors for WHY context (Phase 23: word-boundary regex)
        sector_context = {}
        for article in (validated_news or [])[:5]:
            headline = article.get("headline", "")
            for sector, patterns in _SECTOR_PATTERNS.items():
                if sector in sector_context:
                    continue  # first match wins
                if any(p.search(headline) for p in patterns):
                    sector_context[sector] = headline[:60]

        # Format sector-grouped alerts
        alert_lines = []
        # Sort sectors by worst performer
        sorted_sectors = sorted(
            sector_alerts.items(),
            key=lambda x: min(c for _, c, _ in x[1])
        )

        for sector, stocks_data in sorted_sectors:
            # Determine sector emoji (use worst stock in group)
            worst = min(c for _, c, _ in stocks_data)
            best = max(c for _, c, _ in stocks_data)
            sector_emoji = "🔴" if worst < -2.5 else "🟡" if best > 2.5 else "🟢"

            # Format stock entries
            stock_parts = []
            for sym, change, vol_r in stocks_data:
                vol_str = f" (Vol {vol_r}x)" if vol_r >= 2.0 else ""
                stock_parts.append(f"{sym} {change:+.1f}%{vol_str}")

            alert_lines.append(f"{sector_emoji} *{sector}:* {', '.join(stock_parts)}")

            # WHY context from news
            context = sector_context.get(sector)
            if context:
                alert_lines.append(f"   ↳ {context}")

        # Volume spikes section
        if vol_spikes:
            spike_parts = [f"{sym} {vol_r}x avg" for sym, _, vol_r in vol_spikes]
            alert_lines.append(f"⚡ *High Volume:* {', '.join(spike_parts)}")

        if alert_lines:
            send_text(
                "🔔 *Pre-Market Alerts*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                + "\n".join(alert_lines)
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

    # ── Master Signal Arbitration ─────────────────────────────────
    try:
        from src.signal_arbitrator import run_arbitration, format_master_signal_dashboard

        # Collect signals for arbitration
        arb_signals = {}
        bb = ctx.get("bull_bear", {})
        if bb.get("score") is not None:
            arb_signals["bull_bear"] = bb["score"]
        fg = ctx.get("fear_greed", {})
        fg_score = fg.get("score") or fg.get("index")  # handle both key names
        if fg_score is not None:
            arb_signals["fear_greed"] = fg_score
        macro = ctx.get("macro_context", {})
        if macro.get("vix_price") is not None:
            arb_signals["vix"] = macro["vix_price"]

        # Wire internals if available
        try:
            from src.market_internals import run_internals_analysis
            from src.db import get_market_breadth
            breadth = get_market_breadth()
            if breadth:
                internals = run_internals_analysis(breadth)
                if internals.get("ok") and internals.get("composite", {}).get("composite_score") is not None:
                    arb_signals["internals"] = internals["composite"]["composite_score"]
        except Exception:
            pass

        if arb_signals:
            arbitration = run_arbitration(arb_signals)
            if arbitration.get("ok"):
                master_block = format_master_signal_dashboard(arbitration["arbitration"])
                if master_block:
                    send_text(master_block)
                    art = arbitration["arbitration"]
                    print(f"   → Master Signal: {art['master_score']}/100 ({art['master_label']})")
    except Exception as e:
        print(f"   ⚠️ Master Signal: {e}")

    # ── MF Intelligence (daily inferred signals) ──────────────────
    try:
        from src.formatters import compute_mf_intelligence
        # Build macro_data dict from anchors
        macro_data = {"anchors": anchors} if anchors else {}
        # Add VIX
        for a in (anchors or []):
            if "India VIX" in str(a.get("name", "")) or a.get("symbol") == "^INDIAVIX":
                macro_data["vix_price"] = a.get("price")
                macro_data["vix_regime"] = "HIGH" if (a.get("price") or 0) > 20 else "LOW" if (a.get("price") or 0) < 15 else "NORMAL"
                break

        mf_block = compute_mf_intelligence(ctx=ctx, macro_data=macro_data)
        if mf_block:
            send_text(mf_block)
            print("   → MF Intelligence sent")
    except Exception as e:
        print(f"   ⚠️ MF Intelligence: {e}")

    print("=" * 50)
    print("✅ MORNING BRIEF COMPLETE")
    print("=" * 50)


if __name__ == "__main__":
    main()
