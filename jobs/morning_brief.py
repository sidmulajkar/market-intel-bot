import os
import sys
import hashlib

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


def get_fallback_brief(index_data: dict, validated_news: list, sentiment: str, anchor_data: list = None) -> str:
    """
    Fallback when AI fails - format raw data as structured text.
    Appends posture line if anchor data available.
    """
    lines = []
    lines.append("*Morning Market Snapshot*\n")

    # Global indices summary
    if index_data:
        lines.append("*Global Indices:*")
        for country, d in list(index_data.items())[:5]:
            if d.get("ok"):
                change = d.get("change_pct", 0)
                sign = "+" if change >= 0 else ""
                lines.append(f"  {country}: {sign}{change:.2f}%")

    # Sentiment — only render if a measurable model produced a directional call
    if sentiment and sentiment.lower() != "neutral":
        lines.append(f"\n*Market Sentiment:* {sentiment.title()}")

    # Posture line from anchor data
    if anchor_data:
        try:
            from src.posture_engine import compute_posture
            posture_vix = posture_usdinr = posture_brent = None
            for a in anchor_data:
                if not a.get("ok") or not a.get("price"):
                    continue
                name = a.get("name", "")
                if name == "India VIX":
                    posture_vix = a["price"]
                elif name == "USD/INR":
                    posture_usdinr = a["price"]
                elif name == "Brent Crude":
                    posture_brent = a["price"]
            # Context locked to arbiter's regime — never use separate posture engine
            try:
                from src.db import get_latest_market_state
                _ms = get_latest_market_state()
                _regime = (_ms or {}).get("final_regime", "NEUTRAL")
            except Exception:
                _regime = "NEUTRAL"
            _ctx_map = {
                "BULLISH": "Broad market strength; constructive session.",
                "NEUTRAL": "No dominant macro driver. Range-bound posture.",
                "DEFENSIVE": "Elevated macro stress indicators active.",
            }
            ctx = _ctx_map.get(_regime, "Range-bound posture.")
            lines.append(f"\n📌 *Context:* Regime: {_regime}. {ctx}")
        except Exception:
            pass

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

    # ── World Heatmap (Phase 26: single most useful image) ─────────
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

    # ── Store Nifty prior-close anchor (Fix 5: consistent baseline for 9:15AM) ─
    nifty_data = valid_index.get("India", {})
    if nifty_data.get("price"):
        try:
            from src.db import get_market_state, save_market_state
            from datetime import datetime
            _d = datetime.now().strftime("%Y-%m-%d")
            prev_state = get_market_state(_d) or {}
            prev_state["nifty_prior_close"] = nifty_data["price"]
            save_market_state(_d, prev_state)
            print(f"   → Nifty prior-close anchor: {nifty_data['price']} (from yfinance)")
        except Exception as e:
            print(f"   ⚠️ Nifty anchor save: {e}")

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

    consensus_sentiment = assess_sentiment_consensus(sentiments) if sentiments else None
    print(f"   Validated: {len(validated_news)} articles, consensus: {consensus_sentiment}")

    # ── Deterministic brief (no AI — regime card + alerts carry all context) ──
    brief_text = ""

    # ── Watchlist Alerts (Sector Grouped) ──────────────────────────
    alerts_text = ""
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

    # Fetch top movers (needed for alert scan sector grouping)
    movers = fetch_top_movers(top_n=5)

    # Pre-market alert gate: only non-price catalysts.
    # Pure price moves on Nifty 50 stocks will appear in the 09:15 gap list —
    # alerting them at 08:00 is redundant and violates the "delta only" principle.
    # Only fire on: earnings surprises, regulatory (SEBI/RBI), geopolitical, or ADR >4%.
    # Price-based watchlist alerts are suppressed here.

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

            # Skip price-only alerts — these appear in 09:15 gap lists
            # Only allow non-price catalysts (earnings, regulatory, geopolitical)
            # identified via news-sector matching
            has_news_catalyst = False
            for article in (validated_news or [])[:5]:
                headline = article.get("headline", "").lower()
                # Check if any sector keyword or company name appears in headlines
                if clean_sym.lower().split()[0] in headline or sector.lower() in headline:
                    has_news_catalyst = True
                    break

            if not has_news_catalyst:
                continue  # Pure price move — will appear in 09:15 gaps

            # Only alert on stocks with a news catalyst
            threshold = 2.5
            if abs(change) >= threshold:
                if sector not in sector_alerts:
                    sector_alerts[sector] = []
                sector_alerts[sector].append((clean_sym, change, vol_ratio))
            elif vol_ratio >= 2.5:
                vol_spikes.append((clean_sym, change, vol_ratio))

        # Filter: require at least 2 stocks with same catalyst in a sector
        filtered_alerts = {}
        for sector, stocks_data in sector_alerts.items():
            if len(stocks_data) >= 2:
                filtered_alerts[sector] = stocks_data
        sector_alerts = filtered_alerts

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
            alerts_text = "🔔 *Pre-Market Alerts*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n" + "\n".join(alert_lines)
        else:
            alerts_text = ""
    except Exception as e:
        print(f"   ⚠️ Alert scan failed: {e}")

    # ── Save Snapshot ─────────────────────────────────────────────
    try:
        save_daily_snapshot(valid_index)
    except Exception as e:
        print(f"   ⚠️ Snapshot failed: {e}")

    # ── Single Regime Card (Phase 26: replaces Dashboard + Master Signal + MF) ──
    try:
        from src.data_fetcher import fetch_macro_anchors
        from src.context_engine import run_contextualization, compute_market_phase
        from src.state import MarketState
        from src.db import get_latest_market_state, get_bot_state, set_bot_state
        from src.delta import compute_delta, news_fingerprint_hash, get_relevant_indices
        from src.delta_renderer import render_regime_card

        from datetime import datetime
        today_str = datetime.now().strftime("%Y-%m-%d")

        anchors = fetch_macro_anchors()
        ctx = run_contextualization(anchors)

        # Build MarketState from current data
        state = MarketState(trade_date=today_str)
        bb = ctx.get("bull_bear", {})
        if bb.get("score") is not None:
            state.bull_bear_score = bb["score"]
        if bb.get("normalized") is not None:
            state.bull_bear_normalized = bb["normalized"]
        state.market_phase = ctx.get("market_phase", {}).get("phase")
        state.cross_asset_regime = ctx.get("cross_asset_regime", {}).get("regime", "")

        # Populate macro
        macro = ctx.get("macro_context", {})
        if macro.get("vix_price") is not None:
            state.macro.vix = macro["vix_price"]
        if macro.get("vix_regime"):
            state.macro.vix_regime = macro["vix_regime"]
        if macro.get("brent") is not None:
            state.macro.brent = macro["brent"]
            if macro.get("brent_change") is not None:
                state.macro.brent_change_pct = macro["brent_change"]
        if macro.get("usdinr") is not None:
            state.macro.usdinr = macro["usdinr"]
            if macro.get("usdinr_change") is not None:
                state.macro.usdinr_change_pct = macro["usdinr_change"]
        if macro.get("gold") is not None:
            state.macro.gold = macro["gold"]
        if macro.get("copper") is not None:
            state.macro.copper = macro["copper"]
        if macro.get("dxy") is not None:
            dxy = macro["dxy"]
            if isinstance(dxy, dict):
                state.macro.dxy_signal = dxy.get("signal", "FLAT")

        # Populate flows
        fii_ctx = ctx.get("fii_context", {})
        if fii_ctx.get("ok"):
            state.flows.fii_net = fii_ctx.get("fii_net")
            state.flows.dii_net = fii_ctx.get("dii_net")
            state.flows.absorption_ratio = fii_ctx.get("absorption_ratio")

        # Populate derivatives
        opt = ctx.get("options", {})
        if opt.get("ok"):
            if opt.get("pcr") is not None:
                state.derivatives.pcr = opt["pcr"]
            if opt.get("max_pain") is not None:
                state.derivatives.max_pain = opt["max_pain"]

        # ── Run Regime Arbiter (single source of truth) ───────────
        try:
            from src.regime_arbiter import arbitrate_regime
            from src.db import save_market_state
            flow_metrics = {
                "fii_net": state.flows.fii_net,
                "fii_streak_days": state.flows.fii_streak_days,
            }
            verdict = arbitrate_regime(state, flow_metrics=flow_metrics)
            state.final_regime = verdict.regime
            state.final_regime_confidence = verdict.confidence
            state.final_dominant_driver = verdict.dominant_driver
            state.final_override_reason = verdict.override_reason
            # Persist for all downstream jobs (09:15, 12:30, 15:30, 18:00, 20:00)
            save_market_state(today_str, state)
            print(f"   → Arbiter regime persisted: {verdict.regime} ({verdict.confidence})")
        except Exception as e:
            print(f"   ⚠️ Regime arbiter: {e}")

        # Get previous state for delta
        prev_state_data = get_latest_market_state()
        prev_state = None
        if prev_state_data:
            try:
                prev_state = MarketState.model_validate(prev_state_data)
            except Exception:
                pass

        delta = compute_delta(state, prev_state)

        # News fingerprint for staleness
        if validated_news:
            current_fp = news_fingerprint_headlines = news_fingerprint_hash([a.get("headline", "") for a in validated_news])
            prev_fp = get_bot_state("news_fingerprint_morning")
            if prev_fp and current_fp == prev_fp:
                news_block = ""
            else:
                set_bot_state("news_fingerprint_morning", current_fp)
                # Show only fresh headlines with trust scores
                top_headlines = []
                headline_hashes = []
                for a in validated_news[:3]:
                    trust = a.get("trust_score", 0)
                    if not trust:
                        continue
                    h = a.get("headline", "")
                    # Truncate at sentence boundary
                    if len(h) > 60:
                        pos = h.rfind('. ', 0, 60)
                        h = h[:pos + 2].rstrip() if pos > 0 else h[:60] + "…"
                    if h:
                        top_headlines.append(f"• {h} ({a.get('source', 'unknown')}, trust {trust}/10)")
                        headline_hashes.append(hashlib.md5(h.encode()).hexdigest())
                news_block = "📰 *Top Headlines:*\n" + "\n".join(top_headlines) if top_headlines else ""

                # Persist headline hashes for cross-job dedup (09:15 market_open reads these)
                try:
                    from src.db import save_seen_headlines
                    save_seen_headlines(today_str, headline_hashes)
                except Exception:
                    pass
        else:
            news_block = ""

        # Key levels for regime card
        key_levels = {}
        if state.derivatives.max_pain:
            key_levels["max_pain"] = state.derivatives.max_pain
        # Support/resistance from Nifty TA
        try:
            from src.technical_analysis import compute_support_resistance
            ta = compute_support_resistance()
            if ta:
                key_levels["support"] = ta.get("support_1")
                key_levels["resistance"] = ta.get("resistance_1")
        except Exception:
            pass

        # Render unified regime card with news appended
        regime_card = render_regime_card(state, delta, job_time="08:00", key_levels=key_levels)
        if news_block:
            regime_card += "\n\n" + news_block

        # ── Brier score accountability header ─────────────────────
        try:
            from src.prediction_tracker import validate_yesterday_prediction, get_weekly_accuracy
            from src.formatters import render_scorecard
            yv = validate_yesterday_prediction()
            if yv.get("ok"):
                regime_correct = yv.get("regime_correct", False)
                verdict_label = "correct" if regime_correct else "wrong (prediction ≠ actual)"
                emoji = "✅" if regime_correct else "❌"
                predicted = yv.get("predicted_regime", "?")
                actual = yv.get("actual_regime", "?")
                brier = yv.get("brier_score", 0)

                week = get_weekly_accuracy(days=7)
                avg_brier = week.get("avg_brier", 0.25)
                correct = week.get("correct", 0)
                total = week.get("total", 0)

                scorecard = render_scorecard(correct, total, avg_brier)
                brier_line = (
                    f"\n\n📌 *Scorecard:*"
                    f" Predicted regime: {predicted} → actual regime: {actual} {emoji}\n"
                    f"  → {verdict_label} | {scorecard}"
                )
                regime_card += brier_line
        except Exception:
            pass

        # ── Economic Calendar ─────────────────────────────────
        try:
            from src.economic_calendar import get_upcoming_events, format_calendar
            cal_events = get_upcoming_events(days=7)
            cal_str = format_calendar(cal_events)
            if cal_str:
                regime_card += "\n\n" + cal_str
        except Exception as e:
            print(f"   ⚠️ Calendar: {e}")

        # ── P6.1: Event Volatility Profiles ────────────────────
        try:
            from src.event_volatility import scan_upcoming_events, format_event_volatility
            ev_profiles = scan_upcoming_events(days_ahead=7)
            if ev_profiles:
                vol_text = format_event_volatility(ev_profiles)
                if vol_text:
                    regime_card += "\n\n" + vol_text
        except Exception as e:
            print(f"   ⚠️ Event volatility: {e}")

        # ── P6.2: Correlation Regime Clamp ────────────────────
        try:
            from src.correlation_clamp import compute_correlation_clamp, format_correlation_clamp
            clamp_result = compute_correlation_clamp()
            clamp_block = format_correlation_clamp(clamp_result)
        except Exception:
            clamp_block = ""

        # ── P6.3: Calendar Flows ──────────────────────────────
        try:
            from src.calendar_flows import get_calendar_flows, format_calendar_flows
            cal_flow_result = get_calendar_flows()
            cal_flow_block = format_calendar_flows(cal_flow_result)
        except Exception:
            cal_flow_block = ""

        # ── P6.4: Pre-Event Positioning ────────────────────────
        try:
            from src.event_volatility import scan_upcoming_events
            ev_all = scan_upcoming_events(days_ahead=7)
            nearest_high_impact = None
            for evt in ev_all:
                # scan_upcoming_events returns impact as "H"/"M" (single letter from CSV)
                if evt.get("impact") in ("H", "M"):
                    nearest_high_impact = evt
                    break
            if nearest_high_impact:
                from datetime import datetime
                evt_date = datetime.strptime(nearest_high_impact["event_date"], "%Y-%m-%d")
                days_away = (evt_date - datetime.now()).days
                if 0 <= days_away <= 2:
                    # Fetch stale snapshot from Supabase as fallback (NSE down at 08:00)
                    from src.options_engine import get_latest_snapshot, detect_pre_event_positioning
                    stale_snap = get_latest_snapshot("NIFTY", run="morning")
                    if not stale_snap:
                        for fb_run in ("midday", "evening", "close"):
                            stale_snap = get_latest_snapshot("NIFTY", run=fb_run)
                            if stale_snap:
                                break
                    pos = detect_pre_event_positioning(
                        symbol="NIFTY",
                        event_label=nearest_high_impact.get("event_label", ""),
                        lookback_days=5,
                        run="morning",
                        existing_snapshot=stale_snap,
                    )
                    if pos.get("ok") and pos.get("signals"):
                        pos_lines = ["📡 *Pre-Event Positioning*"]
                        for sig in pos["signals"]:
                            pos_lines.append(f"• {sig}")
                        if pos.get("details"):
                            pos_lines.append(f"  ({pos['details']})")
                        regime_card += "\n\n" + "\n".join(pos_lines)
        except Exception as e:
            print(f"   ⚠️ Pre-event positioning: {e}")

        # ── Pre-event VIX term structure signal ──────────────
        try:
            from src.vol_term_structure import compute_vol_term_structure, check_vol_term_structure_pre_event
            _vt = compute_vol_term_structure()
            pre_evt_vol = check_vol_term_structure_pre_event(_vt)
        except Exception:
            pre_evt_vol = ""

        # Append systemic risk blocks before sending
        extra_blocks = []
        if clamp_block:
            extra_blocks.append(clamp_block)
        if cal_flow_block:
            extra_blocks.append(cal_flow_block)
        if pre_evt_vol:
            extra_blocks.append(pre_evt_vol)
        regime_supplement = "\n\n".join(extra_blocks)
        regime_card_full = regime_card
        if regime_supplement:
            regime_card_full += "\n\n" + regime_supplement

        if regime_card_full:
            merged = ""
            if brief_text:
                merged += brief_text + "\n\n"
            if alerts_text:
                merged += alerts_text + "\n\n"
            merged += regime_card_full
            send_text(merged)
            print(f"   → Merged morning brief sent ({len(merged)} chars)")
    except Exception as e:
        print(f"   ⚠️ Regime card: {e}")
        import traceback
        traceback.print_exc()

    print("=" * 50)
    print("✅ MORNING BRIEF COMPLETE")
    print("=" * 50)


if __name__ == "__main__":
    main()
