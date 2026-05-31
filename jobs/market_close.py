import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_fetcher    import fetch_global_indices, fetch_top_movers, fetch_general_news, fetch_macro_anchors
from src.formatters      import format_top_movers
from src.ai_engine       import AIEngine
from src.telegram_sender import send_text
from src.db              import was_alert_sent, log_alert_sent
from src.validator       import validate_articles, assess_sentiment_consensus
from src.validation_helper import ai_generate_and_validate, build_ground_truth_from_index


# ── Arbiter regime helpers (single source of truth) ────────────────

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

        # Try today's state first
        prev = get_market_state(today)
        if not prev:
            prev = get_latest_market_state(before_date=today)
        if prev and prev.get("final_regime"):
            return {
                "regime": prev["final_regime"],
                "confidence": prev.get("final_regime_confidence", "MEDIUM"),
                "dominant_driver": prev.get("final_dominant_driver", ""),
                "posture_text": _posture_for_regime(prev["final_regime"]),
            }

        state = MarketState(trade_date=today)
        verdict = arbitrate_regime(state)
        return {
            "regime": verdict.regime,
            "confidence": verdict.confidence,
            "dominant_driver": verdict.dominant_driver,
            "posture_text": _posture_for_regime(verdict.regime),
        }
    except Exception as e:
        print(f"   ⚠️ Regime fetch: {e}")
        return {
            "regime": "NEUTRAL",
            "confidence": "MEDIUM",
            "dominant_driver": "",
            "posture_text": "No edge",
        }


def _posture_for_regime(regime: str) -> str:
    posture_map = {
        "BULLISH": "Add beta; buy dips on support holds.",
        "NEUTRAL": "No edge — range trade; neutral positioning.",
        "DEFENSIVE": "Cut beta, hedge, raise cash; reduce OMCs and oil importers.",
    }
    return posture_map.get(regime, "No edge — neutral positioning.")

def main():
    print("=" * 50)
    print("🔔 MARKET CLOSE STARTING")
    print("=" * 50)

    # ── Fetch market data ──────────────────────────────────────────
    print("📊 Fetching top movers + global indices + news...")
    movers     = fetch_top_movers(top_n=10)
    index_data = fetch_global_indices()
    raw_news   = fetch_general_news()

    valid_index = {
        k: v for k, v in index_data.items()
        if v.get("ok") and v.get("price", 0) > 0
    }
    print(f"   Movers: {len(movers.get('india',{}).get('gainers',[]))} India gainers, "
          f"{len(movers.get('us',{}).get('gainers',[]))} US gainers")

    # ── Validate news + sentiment ──────────────────────────────────
    ai = AIEngine()
    validated_news = validate_articles(raw_news, min_trust=6) if raw_news else []
    sentiments = []
    for article in validated_news[:5]:
        sent = ai.sentiment(article.get("headline", ""))
        article["sentiment"] = sent
        if sent:
            sentiments.append(sent)
    consensus = assess_sentiment_consensus(sentiments) if sentiments else None

    # ── Get bull/bear context + build ground truth ─────────────────
    bull_bear = {}
    ground_truth = {}
    try:
        from src.context_engine import run_contextualization
        anchor_data = fetch_macro_anchors()
        if anchor_data:
            ctx = run_contextualization(anchor_data)
            bull_bear = ctx.get("bull_bear", {})
            # Build ground truth for validation
            gt_extra = {}
            if bull_bear.get("score") is not None:
                gt_extra["bull_bear_score"] = bull_bear["score"]
            if ctx.get("flow_metrics", {}).get("ok"):
                fm = ctx["flow_metrics"]
                gt_extra["fii_net"] = fm.get("fii_net")
                gt_extra["dii_net"] = fm.get("dii_net")
            if ctx.get("vix_context", {}).get("ok"):
                gt_extra["india_vix"] = ctx["vix_context"].get("vix_price")
            for a in anchor_data:
                name = a.get("name", "")
                if name == "Brent Crude" and a.get("ok") and a.get("price"):
                    gt_extra["brent"] = a["price"]
                elif name == "Gold" and a.get("ok") and a.get("price"):
                    gt_extra["gold"] = a["price"]
            ground_truth = build_ground_truth_from_index(valid_index, gt_extra if gt_extra else None)
    except Exception as e:
        print(f"   ⚠️ Context engine: {e}")

    # ── Flows block (FII/DII) ──────────────────────────────────────
    flows_block = ""
    try:
        if ctx.get("flow_metrics", {}).get("ok"):
            fm = ctx["flow_metrics"]
            fii_net = fm.get("fii_net")
            dii_net = fm.get("dii_net")
            absorption = fm.get("absorption_ratio")
            if fii_net is not None or dii_net is not None:
                fii_str = f"FII Net: ₹{fii_net:+,.0f}Cr" if fii_net is not None else "FII: n/a"
                dii_str = f"DII Net: ₹{dii_net:+,.0f}Cr" if dii_net is not None else "DII: n/a"
                abs_str = f"Absorption: {absorption:.0f}%" if absorption is not None else ""
                flows_block = f"📊 *Flows:* {fii_str} | {dii_str}"
                if abs_str:
                    flows_block += f" | {abs_str}"
    except Exception:
        pass

    # ── Derivatives block (PCR, Max Pain, GEX, Skew) ──────────────
    derivs_block = ""
    try:
        from src.options_engine import get_latest_snapshot
        snap = get_latest_snapshot("NIFTY", "morning")
        pcr = max_pain = gex = skew = None
        if snap:
            pcr = snap.get("pcr")
            max_pain = snap.get("max_pain")
            gex = snap.get("gex")
            skew = snap.get("skew_25d")
            if pcr is not None:
                print(f"   ✅ Options snapshot: PCR={pcr}")
        # Fallback tier 1: persisted MarketState
        if pcr is None or max_pain is None or gex is None or skew is None:
            try:
                from src.db import get_market_state
                from datetime import datetime
                ms = get_market_state(datetime.now().strftime("%Y-%m-%d"))
                if ms and ms.get("derivatives"):
                    d = ms["derivatives"]
                    if pcr is None:
                        pcr = d.get("pcr")
                    if max_pain is None:
                        max_pain = d.get("max_pain")
                    if gex is None:
                        gex = d.get("gex")
                    if skew is None:
                        skew = d.get("skew_25d")
                    if pcr is not None:
                        print(f"   ✅ Fallback MarketState: PCR={pcr}")
            except Exception:
                pass
        # Fallback tier 2: live NSE fetch if still empty
        if pcr is None:
            print("   🔄 Falling back to live NSE options fetch...")
            try:
                from src.options_engine import analyze_options_chain
                live = analyze_options_chain("NIFTY")
                if live.get("ok"):
                    mp_data = live.get("max_pain", {}) or {}
                    pcr_data = live.get("pcr", {}) or {}
                    gex_data = live.get("gex", {}) or {}
                    skew_data = live.get("skew", {}) or {}
                    if pcr is None:
                        pcr = pcr_data.get("pcr")
                    if max_pain is None:
                        max_pain = mp_data.get("max_pain")
                    if gex is None:
                        gex_val = gex_data.get("net_gex_cr")
                        gex = float(f"{gex_val:.1f}") if gex_val is not None else None
                    if skew is None:
                        skew = skew_data.get("skew_25d")
                    if pcr is not None:
                        print(f"   ✅ Live NSE fetch: PCR={pcr}")
                else:
                    print(f"   ⚠️ NSE options API unavailable ({live.get('message')})")
            except Exception as e:
                print(f"   ⚠️ NSE options fetch error: {e}")
        if pcr is None:
            print("   ⚠️ No PCR data from any source")
        # GEX staleness guard: suppress live morning snapshot if >4h old
        gex_stale = True
        if gex is not None:
            gex_stale = False
            if snap and snap.get("run") == "morning":
                from datetime import datetime, timezone
                snap_ts = snap.get("created_at")
                if snap_ts:
                    try:
                        snap_time = datetime.fromisoformat(snap_ts.replace("Z", "+00:00"))
                        age = (datetime.now(timezone.utc) - snap_time).total_seconds()
                        if age > 14400:
                            gex_stale = True
                    except Exception:
                        pass

        parts = []
        if pcr is not None:
            parts.append(f"PCR: {pcr:.2f}")
        if max_pain is not None:
            parts.append(f"Max Pain: {max_pain:,.0f}")
        if gex is not None and not gex_stale:
            parts.append(f"GEX: {gex:+,.0f}")
        elif gex is not None and gex_stale:
            pass  # Suppress stale GEX
        if skew is not None:
            parts.append(f"Skew (25d): {skew:.2f}")
        if parts:
            derivs_block = f"📉 *Derivatives:* {' | '.join(parts)}"
            print(f"   ✅ Derivatives block built: {' | '.join(parts)}")
        # GEX magnetic levels (from live fetch if available)
        try:
            from src.options_engine import format_gex_levels
            if 'live' in dir() and live and live.get("ok"):
                gex_lvl = format_gex_levels(live.get("gex", {}), live.get("spot_price"))
                if gex_lvl:
                    derivs_block += f"\n{gex_lvl}" if derivs_block else gex_lvl
        except Exception:
            pass
    except Exception:
        import traceback
        traceback.print_exc()

    # ── Big move alerts (computed before AI call — needed for fallback) ──
    all_movers = (
        movers.get("india", {}).get("gainers", []) +
        movers.get("india", {}).get("losers", []) +
        movers.get("us", {}).get("gainers", []) +
        movers.get("us", {}).get("losers", [])
    )
    big_moves = []
    for m in all_movers:
        change = abs(m.get("change_pct", 0))
        sym    = m.get("symbol", "")
        if change >= 5.0:
            key = f"eod_bigmove_{sym}"
            if not was_alert_sent(sym, key):
                emoji = "⚠️"
                big_moves.append(f"{emoji} *{sym}* {m['change_pct']:+.1f}%")
                log_alert_sent(sym, key)

    # ── Read arbitrated regime (single source of truth) ─────────────
    regime_info = _get_arbiter_regime()
    regime_label = regime_info.get("regime", "NEUTRAL")
    regime_confidence = regime_info.get("confidence", "MEDIUM")
    regime_driver = regime_info.get("dominant_driver", "")
    regime_posture = regime_info.get("posture_text", "")

    # ── Identify key drivers — India only for EOD, US for overnight ─
    india_drivers = []
    us_drivers = []
    india_all = movers.get("india", {}).get("gainers", []) + movers.get("india", {}).get("losers", [])
    if india_all:
        top = max(india_all, key=lambda x: abs(x.get("change_pct", 0)))
        india_drivers.append(f"{top['symbol']} {top['change_pct']:+.1f}% (top India mover)")
    us_all = movers.get("us", {}).get("gainers", []) + movers.get("us", {}).get("losers", [])
    if us_all:
        # Suppress individual US equity movers before 7 PM IST (US cash market opens at 9:30 ET)
        # Also suppress on weekends Sat/Sun when US markets are closed
        from datetime import datetime, timezone, timedelta
        now_utc = datetime.now(timezone.utc)
        ist_hour = (now_utc + timedelta(hours=5, minutes=30)).hour
        is_weekend = now_utc.weekday() >= 5  # Sat=5, Sun=6
        if not is_weekend and ist_hour >= 19:
            top_us = max(us_all, key=lambda x: abs(x.get("change_pct", 0)))
            us_drivers.append(f"{top_us['symbol']} {top_us['change_pct']:+.1f}% (top US mover)")

    # ── Overnight handoff (Phase 26: US/Europe live) ──────────────
    overnight_note = ""
    try:
        from src.delta import get_relevant_indices
        relevant = get_relevant_indices("15:30", valid_index)
        if relevant:
            parts = []
            for country, d in relevant.items():
                if d.get("ok") and d.get("change_pct") is not None:
                    sign = "+" if d.get("change_pct", 0) >= 0 else ""
                    parts.append(f"{d.get('flag','')} {country} {sign}{d.get('change_pct',0):.1f}%")
            if parts:
                overnight_note = f"\n🌍 *Overnight:* {' | '.join(parts[:3])}"
    except Exception:
        pass

    # ── AI market summary (with universal validation) ──────────────
    print("🤖 Generating market summary...")
    summary = ""
    try:
        prompt = AIEngine.eod_market_prompt(
            movers, valid_index, validated_news, consensus, bull_bear
        )
    except Exception as e:
        print(f"   ⚠️ Prompt build failed: {e}")
        prompt = ""

    nifty = valid_index.get("India", {})
    vix_price = gt_extra.get("india_vix") if gt_extra else None
    header_parts = []
    if nifty and nifty.get("price", 0) > 0:
        header_parts.append(f"Nifty {nifty.get('price', 0):,.0f} ({nifty.get('change_pct', 0):+.1f}%)")
    if vix_price:
        header_parts.append(f"VIX {vix_price:.1f}")
    header = " | ".join(header_parts) if header_parts else "Market Close"

    if not header_parts:
        print("   ⚠️ CRITICAL: No Nifty closing price available — cannot send EOD summary")
        send_text("⚠️ *END OF DAY:* Nifty closing data unavailable — no summary available.")
        return

    # ── Brier scorecard (unified format) ──────────────────────────────
    brier_block = ""
    try:
        from src.prediction_tracker import validate_yesterday_prediction, get_weekly_accuracy
        from src.formatters import render_scorecard
        yv = validate_yesterday_prediction()
        if yv and yv.get("ok"):
            regime_correct = yv.get("regime_correct", False)
            emoji = "✅" if regime_correct else "❌"
            predicted = yv.get("predicted_regime", "?")
            actual = yv.get("actual_regime", "?")
            brier = yv.get("brier_score", 0)
            week = get_weekly_accuracy(days=7)
            avg_brier = week.get("avg_brier", 0.25)
            correct = week.get("correct", 0)
            total = week.get("total", 0)
            scorecard = render_scorecard(correct, total, avg_brier)
            brier_block = (
                f"\n📌 *Scorecard:* Yesterday {predicted} → {actual} {emoji}\n"
                f"  {scorecard}"
            )
        else:
            brier_block = "\n⚠️ *Scorecard:* Pending (yesterday's data unavailable)"
    except Exception:
        brier_block = "\n⚠️ *Scorecard:* Pending (data unavailable)"

    def make_fallback():
        """Deterministic EOD text-only note — no AI needed. Blocks are rendered by send_eod."""
        regime_posture = regime_info.get("posture_text", "")
        if regime_posture:
            return f"Posture: {regime_posture}"
        return f"Regime: {regime_label}. Session closed."

    # ── Regime-gated sign-off ──────────────────────────────────────
    sign_off = "_See you tomorrow!_"
    if regime_label in ("DEFENSIVE", "BEARISH"):
        sign_off = "_Evening macro watch continues. Evening intel at 18:00._"

    # ── Drawdown anatomy ──────────────────────────────────────────
    drawdown_block = ""
    try:
        from src.drawdown_anatomy import run_drawdown_analysis
        dd_result = run_drawdown_analysis(current_price=nifty.get("price") if nifty else None)
        if dd_result.get("ok") and dd_result.get("formatted"):
            drawdown_block = dd_result["formatted"]
    except Exception as e:
        print(f"   ⚠️ Drawdown: {e}")

    def send_eod(text):
        from src.formatters import reorder_market_blocks, format_scenario_block

        # Build scenario block from state
        scenario_block = ""
        try:
            from datetime import datetime
            from src.db import get_market_state
            ms = get_market_state(datetime.now().strftime("%Y-%m-%d"))
            if ms:
                from src.state import MarketState
                state = MarketState.model_validate(ms)
                scenario_block = format_scenario_block(state)
        except Exception:
            pass

        reg_emoji = {"BULLISH": "🟢", "NEUTRAL": "🟡", "DEFENSIVE": "🔴"}.get(regime_label, "🟡")
        nifty_str = f" | Nifty {nifty.get('price'):,.0f}" if nifty.get("price") else ""
        if nifty.get("price") and nifty.get("change_pct") is not None:
            sign = "+" if nifty["change_pct"] >= 0 else ""
            nifty_str += f" ({sign}{nifty['change_pct']:.1f}%)"
        regime_block = f"🔔 *END OF DAY*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n{reg_emoji} *REGIME: {regime_label}*{nifty_str}"
        header_block = f"📊 {header}"
        india_block = f"📊 *India Drivers:* {'; '.join(india_drivers)}" if india_drivers else ""
        us_block = f"🌍 *Overnight Watch:* {'; '.join(us_drivers)}" if us_drivers else ""
        big_moves_block = ""
        if big_moves:
            big_moves_block = "⚠️ *Big Moves (5%+):*\n" + "\n".join(big_moves)

        msg = reorder_market_blocks(
            regime=regime_label,
            regime_block=regime_block,
            scorecard_block=brier_block,
            header_block=header_block,
            flows_block=flows_block or "",
            derivs_block=derivs_block or "",
            india_drivers_block=india_block,
            ai_block=text or "",
            overnight_block=overnight_note.strip() if overnight_note else "",
            us_drivers_block=us_block,
            big_moves_block=big_moves_block,
            sign_off_block=f"━━━━━━━━━━━━━━━━━━━━━━━━\n{sign_off}",
            scenario_block=scenario_block,
            drawdown_block=drawdown_block,
        )
        send_text(msg)

    if prompt and ground_truth.get("nifty_close"):
        ai_generate_and_validate(
            ai, "volume", prompt, ground_truth,
            output_type="market_close",
            fallback_fn=make_fallback,
            send_fn=send_eod,
            max_retries=1,
        )
    else:
        send_eod(make_fallback())
    print("✅ MARKET CLOSE COMPLETE")

if __name__ == "__main__":
    main()
