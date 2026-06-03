import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_fetcher    import fetch_global_indices, fetch_top_movers, fetch_general_news, fetch_macro_anchors
from src.formatters      import format_top_movers
from src.ai_engine       import AIEngine
from src.telegram_sender import send_text
from src.db              import was_alert_sent, log_alert_sent
from src.validator       import validate_articles, assess_sentiment_consensus
from src.validation_helper import build_ground_truth_from_index
from typing import Dict


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
        "BULLISH": "Constructive — broad-based participation.",
        "NEUTRAL": "Neutral — range-bound with balanced risks.",
        "DEFENSIVE": "Defensive — elevated macro stress indicators.",
    }
    return posture_map.get(regime, "Neutral — balanced posture.")

def _format_minimal_eod_fallback(
    regime_label: str,
    nifty: Dict,
    stress_banner: str = "",
    pillar_block: str = "",
) -> str:
    """Fail-safe EOD when full block assembly produces nothing."""
    lines = []
    reg_emoji = {"BULLISH": "🟢", "NEUTRAL": "🟡", "DEFENSIVE": "🔴"}.get(regime_label, "🟡")
    lines.append(f"🔔 *END OF DAY*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n{reg_emoji} *REGIME: {regime_label}*")
    if nifty.get("price"):
        nifty_str = f" | Nifty {nifty['price']:,.0f}"
        if nifty.get("change_pct") is not None:
            sign = "+" if nifty["change_pct"] >= 0 else ""
            nifty_str += f" ({sign}{nifty['change_pct']:.1f}%)"
        lines[-1] += nifty_str
    if stress_banner:
        lines.append(f"\n{stress_banner}")
    if pillar_block:
        lines.append(f"\n{pillar_block}")
    lines.append("\n_Some data blocks unavailable (fallback mode)_")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


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

        # ── P10 Sentinel: Preflight data integrity check ────────────────
        try:
            from src.sentinel import preflight_check
            from src.db import get_prev_macro_anchors, anchors_list_to_dict
            current = anchors_list_to_dict(anchor_data)
            if current:
                prev = get_prev_macro_anchors()
                is_safe, reason = preflight_check(current, prev)
                if not is_safe:
                    send_text(f"🚨 DATA INTEGRITY FAILURE: {reason} Regime locked to previous state.")
                    sys.exit(1)
        except Exception as e:
            print(f"   ⚠️ Sentinel preflight: {e}")

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

    # ── Flows block (FII/DII) + P5 Institutional Microscopy ────────
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

        # P5.1: FII Decomposition
        try:
            from src.fii_decomposition import compute_fii_entity_concentration, format_fii_decomposition
            decomp = compute_fii_entity_concentration(days=7)
            if decomp.get("ok"):
                decomp_str = format_fii_decomposition(decomp)
                if decomp_str:
                    flows_block += "\n\n" + decomp_str
            elif "Entity data pending" not in flows_block and flows_block.strip():
                flows_block += " | Entity data pending"
        except Exception as e:
            print(f"   ⚠️ FII decomposition: {e}")

        # P5.2: DII Capacity Gauge
        try:
            from src.dii_capacity import compute_dii_capacity, format_dii_capacity
            cap = compute_dii_capacity(days=5)
            if cap.get("ok") and cap.get("status") not in ("INSUFFICIENT_DATA",):
                cap_str = format_dii_capacity(cap)
                if cap_str:
                    flows_block += "\n\n" + cap_str
        except Exception as e:
            print(f"   ⚠️ DII capacity: {e}")

        # P5.3: Sector Flow Match (pillar-flow confirmation)
        try:
            from src.pillar_classifier import get_current_pillar_scores
            pr = get_current_pillar_scores()
            if pr.get("ok") and pr["pillars"]:
                from src.sectoral_drag import compute_pillar_flow_match, format_pillar_flow_match
                match = compute_pillar_flow_match(pr["pillars"], lookback_days=2)
                if match.get("ok"):
                    match_str = format_pillar_flow_match(match)
                    if match_str:
                        flows_block += "\n\n" + match_str
        except Exception as e:
            print(f"   ⚠️ Pillar-flow match: {e}")

        # P11.2: Liquidity Freeze Override (appended to DII section)
        try:
            from src.liquidity_freeze import compute_liquidity_velocity
            lf = compute_liquidity_velocity()
            if lf.get("ok") and lf.get("freeze_active"):
                flows_block += (
                    "\n\n⚠️ Override: Global liquidity freeze active; "
                    "domestic absorption may be overridden by dollar repatriation."
                )
        except Exception as e:
            print(f"   ⚠️ Liquidity freeze: {e}")

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
        else:
            derivs_block = "📉 *Derivatives:* PCR unavailable (NSE v3 lag) | GEX: N/A | Max Pain: N/A"
            print("   ⚠️ Derivatives block: no data — using stub")
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
    # Suppress US equity movers before 19:00 IST (US cash market opens 9:30 ET = 19:00 IST)
    # On weekends, suppress US movers entirely (markets closed)
    from datetime import datetime, timezone, timedelta
    now_utc = datetime.now(timezone.utc)
    ist_hour_big = (now_utc + timedelta(hours=5, minutes=30)).hour
    is_weekend_big = now_utc.weekday() >= 5
    us_filtered = is_weekend_big or ist_hour_big < 19

    us_gainers = [] if us_filtered else movers.get("us", {}).get("gainers", [])
    us_losers  = [] if us_filtered else movers.get("us", {}).get("losers", [])

    all_movers = (
        movers.get("india", {}).get("gainers", []) +
        movers.get("india", {}).get("losers", []) +
        us_gainers +
        us_losers
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

        # Build scenario block from state (with CSV fallback for pillars)
        scenario_block = ""
        compact_pillar_block = ""
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

        # If scenario_block is empty (no Supabase state), build compact pillar line from CSV
        if not scenario_block:
            try:
                from src.pillar_classifier import get_percentiles_from_csv, classify_pillars
                pctiles = get_percentiles_from_csv()
                if pctiles:
                    pillars = classify_pillars(pctiles)
                    if pillars:
                        from src.pillar_lifecycle import compute_pillar_lifecycle, get_pillar_history_from_db
                        parts = []
                        for p in pillars[:2]:
                            lc = {}
                            try:
                                history = get_pillar_history_from_db(p["name"])
                                lc = compute_pillar_lifecycle(p["name"], p["score"], history)
                            except Exception:
                                pass
                            lc_suffix = f" | {lc.get('formatted', '')}" if lc.get("ok") and lc.get("formatted") else ""
                            parts.append(f"{p['label']} ({p['score']:.0f}/100){lc_suffix}")
                        if parts:
                            scenario_block = f"Active Pillars: {'; '.join(parts)}"
            except Exception:
                pass

        # P11.4: Archetype Collision Banner (prepended to scenario block)
        try:
            from src.liquidity_freeze import check_liquidity_freeze
            from src.scenario_collision import detect_collision, format_collision, \
                has_dxy_spike, has_gold_spike, has_usdinr_spike

            macro = ms.get("macro", {}) if ms else {}
            pillar_scores = {}
            try:
                from src.pillar_classifier import load_pillar_scores
                if ms and ms.get("pillar_scores"):
                    pillar_scores = ms["pillar_scores"]
                else:
                    pillar_scores = load_pillar_scores() or {}
            except Exception:
                if ms:
                    pillar_scores = ms.get("pillar_scores", {})

            lf = check_liquidity_freeze(macro)
            extra = {
                "dxy_spike": has_dxy_spike(macro),
                "gold_spike": has_gold_spike(macro),
                "cny_strength": False,
                "usdinr_spike": has_usdinr_spike(macro),
                "liquidity_freeze": lf,
            }
            archetype = detect_collision(pillar_scores, extra)
            collision_banner = format_collision(archetype)
            if collision_banner:
                scenario_block = collision_banner + "\n\n" + scenario_block
            elif pillar_scores:
                scenario_block = "📋 Archetype: None detected\n\n" + scenario_block
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

        # P7.2: Sector Rotation Map (Fragility > 50)
        rotation_block = ""
        try:
            from src.sector_rotation_map import format_rotation_map
            if ms:
                fragility = ms.get("fragility_score")
                p_scores = ms.get("pillar_scores", {}) or {}
                active_pillars = [k for k, v in p_scores.items() if isinstance(v, (int, float)) and v >= 40]
                rotation_block = format_rotation_map(active_pillars, fragility)
        except Exception:
            pass

        # P7–P12 Supplementary block (ERP, India vs EM, flags)
        supplementary_block = ""
        try:
            sup_parts = []

            # P11.1: External Debt Stress flag
            try:
                from src.db import get_fii_dii_flows
                macro = ms.get("macro", {}) if ms else {}
                us10y_entry = macro.get("^TNX") or macro.get("us_10y") or {}
                us10y = float(us10y_entry.get("price", 0) if isinstance(us10y_entry, dict) else (us10y_entry or 0))
                usdinr_entry = macro.get("USDINR=X") or macro.get("usdinr") or {}
                usdinr = float(usdinr_entry.get("price", 0) if isinstance(usdinr_entry, dict) else (usdinr_entry or 0))
                flows = get_fii_dii_flows(days=7)
                fii_5d = sum(r.get("fiinet_cr", 0) or 0 for r in (flows or [])[-5:])
                if us10y > 4.5 and usdinr > 84.0 and fii_5d < -10000:
                    sup_parts.append("⚠️ External Debt Stress: US10Y + USDINR + FII_5D threshold met")
            except Exception:
                pass

            # P11: Liquidity Freeze sentinel
            try:
                from src.liquidity_freeze import check_liquidity_freeze
                lf = check_liquidity_freeze(macro if ms else {})
                sup_parts.append("🚫 Liquidity Freeze: Detected" if lf else "💧 Liquidity Freeze: Not detected")
            except Exception:
                pass

            # IN10Y: India 10Y G-Sec yield (dual-source, fallback explicit)
            try:
                from src.data_fetcher import get_india_10y_yield
                in10y_result = get_india_10y_yield()
                in10y_val = in10y_result.get("IN10Y", 7.0)
                in10y_source = in10y_result.get("source", "fallback")
                note = in10y_result.get("note", "")
                label = f"📊 IN10Y: {in10y_val:.2f}% ({in10y_source})"
                if note:
                    label += f" — {note}"
                sup_parts.append(label)
                # Also show Nifty GS 10YR index level when available
                gs10_entry = (macro or {}).get("NIFTYGS10YR.NS") or {}
                gs10_val = float(gs10_entry.get("price", 0)) if isinstance(gs10_entry, dict) else float(gs10_entry or 0)
                if gs10_val:
                    sup_parts.append(f"📊 Nifty GS 10YR: {gs10_val:.2f} (index level)")
            except Exception:
                sup_parts.append("📊 IN10Y: 7.00% (RBI API unavailable)")

            # P12: SMH/COPX macro movers (>2%)
            for sym, label in [("SMH", "Semiconductor"), ("COPX", "Copper Miners")]:
                try:
                    entry = (macro or {}).get(sym) or {}
                    price = float(entry.get("price", 0)) if isinstance(entry, dict) else 0
                    chg = float(entry.get("change_pct", 0)) if isinstance(entry, dict) else 0
                    if price and abs(chg) >= 2:
                        direction = "📈" if chg > 0 else "📉"
                        sup_parts.append(f"{label} ({sym}): ${price:.0f} ({direction} {chg:+.1f}%)")
                except Exception:
                    pass

            # P8: ERP Decile (India 10Y from macro state or baseline)
            try:
                from src.value_metrics import compute_erp, get_current_erp_decile, format_erp_decile
                india_10y = in10y_val
                nifty_pe = None
                if ms and (ms.get("bull_bear_score") or ms.get("pe")) is not None:
                    nifty_pe = ms.get("bull_bear_score") or ms.get("pe")
                if nifty_pe and nifty_pe > 0:
                    erp = compute_erp(nifty_pe, india_10y)
                    d = get_current_erp_decile(erp)
                    sup_parts.append(format_erp_decile(erp) if d.get("ok") else f"ERP: {erp:.2f}%")
            except Exception:
                pass

            # P8: India vs EM spread
            try:
                from src.value_metrics import compute_india_vs_em_rs
                rs = compute_india_vs_em_rs()
                if rs.get("ok"):
                    spread = rs.get("spread_30d", 0)
                    direction = "underperforming" if spread < 0 else "outperforming"
                    sup_parts.append(f"India vs EM (30D): {spread:+.1f}% ({direction})")
            except Exception:
                pass

            # P7: Dynamic weight evidence
            try:
                from src.adaptive_weights import get_dynamic_weights
                dw = get_dynamic_weights()
                weighted = [f"{k.replace('_',' ').title()} ×{v:.1f}" for k, v in dw.items() if v != 1.0]
                if weighted:
                    sup_parts.append(f"Adaptive Weights: {' | '.join(weighted[:3])}")
                else:
                    sup_parts.append("Adaptive Weights: all at 1.0 (default)")
            except Exception:
                pass

            if sup_parts:
                supplementary_block = "📋 *Supplementary:*\n" + "\n".join(sup_parts)
        except Exception:
            pass

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
            rotation_block=rotation_block,
            supplementary_block=supplementary_block,
        )
        if not msg or not msg.strip():
            msg = _format_minimal_eod_fallback(regime_label, nifty, "", scenario_block or "")
        send_text(msg)

    # No AI — all blocks are deterministic. send_eod() assembles them
    # into a single message via reorder_market_blocks().
    send_eod("")
    print("✅ MARKET CLOSE COMPLETE")

if __name__ == "__main__":
    main()
