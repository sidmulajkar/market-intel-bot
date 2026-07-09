import sys
import os
import time
import hashlib
import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_fetcher    import fetch_global_indices, fetch_top_movers, fetch_general_news, fetch_macro_anchors
from src.ai_engine       import AIEngine
from src.telegram_sender import send_text
from src.db              import was_alert_sent, log_alert_sent, get_latest_market_state
from src.validator       import validate_articles, assess_sentiment_consensus
from src.validation_helper import ai_generate_and_validate, build_ground_truth_from_index
from src.formatters      import format_options_block
from src.manifest import load as manifest_load
from src.fingerprint import compute_raw_fingerprint, build_anchor_dict, hours_since, fmt_time_since
from src.bot_state import get_skip_meta, update_skip_meta
from src.guardian import Guardian, TriageLevel
from src.daily_state import mark_job_completed


def _get_arbiter_regime() -> dict:
    """Read arbitrated regime from MarketState — never recompute."""
    try:
        today = datetime.datetime.now().strftime("%Y-%m-%d")
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
    _job_start = time.time()
    _midday_fragility = None     # single fragility score for banner + context
    _pillars_result = {}         # single pillar scores call
    _pillar_check = {}           # single pillar confirmation check
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

    # ── P18/P14/P16: Guardian + Fingerprint Gate ─────────
    try:
        _m_anchor = fetch_macro_anchors()
        _manifest_mid = manifest_load()
        guardian = Guardian(_manifest_mid)
        for a in _m_anchor or []:
            guardian.check_source(
                a.get("symbol", ""), a.get("price"),
                "live" if a.get("ok") else "fallback", 0,
            )
        _anchors_dict = build_anchor_dict(_m_anchor, index_data)
        _current_fp = compute_raw_fingerprint(_anchors_dict, _manifest_mid)
        _meta = get_skip_meta()
        if _current_fp == _meta.last_fingerprint:
            # ── FAST PATH: deterministic stub, no compute/AI ──
            _h = hours_since(_meta.last_sent_at)
            _tpl_key = "no_change_short" if _h < 4 else "no_change_standard"
            _tpl = _manifest_mid["templates"][_tpl_key]
            _msg = _tpl.format(
                regime=_meta.last_regime,
                fragility=_meta.last_fragility,
                nifty=_anchors_dict.get("NIFTY", 0),
                vix=_anchors_dict.get("VIX", 0),
                time_since=fmt_time_since(_meta.last_sent_at),
            )
            send_text(f"📌 *MIDDAY SCAN*\n{_msg}")
            update_skip_meta(
                fingerprint=_current_fp,
                sent_at_iso=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                regime=_meta.last_regime,
                fragility=_meta.last_fragility,
            )
            try:
                from src.state_journal import append_journal
                append_journal(
                    job_tag="midday_scan",
                    regime=_meta.last_regime,
                    fragility=_meta.last_fragility,
                    fingerprint=_current_fp,
                    manifest_version=_manifest_mid.get("version"),
                    nifty=_anchors_dict.get("NIFTY"),
                    vix=_anchors_dict.get("VIX"),
                )
            except Exception:
                pass
            print("✅ MIDDAY SCAN COMPLETE (fast-path stub)")
            return
        update_skip_meta(
            fingerprint=_current_fp,
            sent_at_iso=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        _triage = guardian.finalize(_anchors_dict)
        if _triage == TriageLevel.RED:
            send_text("🚨 DATA INTEGRITY FAILURE: Macro fetch >30% null. Pipeline halted.")
            sys.exit(1)
        elif _triage == TriageLevel.YELLOW:
            from src.formatters import set_triage_mode
            set_triage_mode(True)
            from src.telegram_sender import set_triage_badge
            set_triage_badge("⚠️ *Partial Data*")
    except Exception as e:
        print(f"   ⚠️ Guardian/fingerprint: {e}")

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

    # ── Midday breadth (A/D ratio, strength) — fetched before skip gate ──
    breadth_data = {}
    try:
        from src.data_fetcher import fetch_market_breadth
        breadth = fetch_market_breadth()
        if breadth and breadth.get("ok"):
            breadth_data = breadth
    except Exception as e:
        print(f"   ⚠️ Breadth pre-fetch: {e}")

    # ── Conditional skip gate (Phase 34: breadth + VIX refinement) ─────
    # Pass through (don't skip) if ANY signal is notable
    nifty = valid_index.get("India", {})
    vix = valid_index.get("India VIX", {})
    nifty_change_abs = abs(nifty.get("change_pct", 0))
    nifty_change_pct = nifty.get("change_pct", 0)
    nifty_moved = nifty_change_abs > 1.0

    # VIX: baseline spike + intraday change
    vix_spike = False
    vix_intraday_spike = False
    if vix and vix.get("price"):
        vix_price = vix.get("price", 0)
        vix_change_abs = abs(vix.get("change_pct", 0))
        if vix_change_abs > 15:
            vix_intraday_spike = True
        try:
            from src.db import get_latest_market_state
            prev = get_latest_market_state()
            if prev and prev.get("macro", {}).get("vix"):
                prev_vix = prev["macro"]["vix"]
                if prev_vix > 0 and (vix_price - prev_vix) / prev_vix > 0.20:
                    vix_spike = True
        except Exception:
            pass
    vix_notable = vix_spike or vix_intraday_spike

    # Breadth: A/D ratio outside 0.67-1.5 = notable breadth action
    breadth_notable = False
    ad_ratio = 0.0
    if breadth_data:
        adv = breadth_data.get("advances", 0)
        dec = breadth_data.get("declines", 0)
        ad_ratio = adv / max(dec, 1)
        breadth_notable = ad_ratio < 0.67 or ad_ratio > 1.5

    # Pre-scan for extreme moves (needed for skip gate)
    alerts = []
    seen_symbols = set()
    india_all = movers.get("india", {}).get("gainers", []) + movers.get("india", {}).get("losers", [])
    for m in india_all:
        sym = m.get("symbol", "")
        if sym in seen_symbols:
            continue
        change = abs(m.get("change_pct", 0))
        if change >= 5.0:
            seen_symbols.add(sym)
            alerts.append(m)
    # Composite: 4%+ moves with notable breadth also counts
    for m in india_all:
        sym = m.get("symbol", "")
        if sym in seen_symbols:
            continue
        change = abs(m.get("change_pct", 0))
        if change >= 4.0 and breadth_notable:
            seen_symbols.add(sym)
            alerts.append(m)

    has_extreme = len(alerts) > 0

    if not nifty_moved and not vix_notable and not has_extreme:
        # Stealth decline: flat index + hostile breadth
        if breadth_notable and ad_ratio < 0.67:
            stealth_note = (
                f"⚠️ STEALTH DECLINE: Index flat ({nifty_change_pct:+.2f}%), "
                f"but breadth hostile (A/D {breadth_data.get('advances',0)}/"
                f"{breadth_data.get('declines',0)}). "
                f"Large-caps masking broad market weakness."
            )
            print(f"   🟡 Stealth decline detected — sending alert")
            send_text(f"📌 *Midday:* {stealth_note}")
            print("✅ MIDDAY SCAN COMPLETE")
            return
        # Stealth rally: flat index + broad buying
        if breadth_notable and ad_ratio > 1.5:
            stealth_note = (
                f"⚠️ STEALTH RALLY: Index flat ({nifty_change_pct:+.2f}%), "
                f"but breadth positive (A/D {breadth_data.get('advances',0)}/"
                f"{breadth_data.get('declines',0)}). "
                f"Broad buying masked by index weight cap."
            )
            print(f"   🟡 Stealth rally detected — sending alert")
            send_text(f"📌 *Midday:* {stealth_note}")
            print("✅ MIDDAY SCAN COMPLETE")
            return
        # Genuinely quiet
        skip_note = f"Nifty {nifty_change_pct:+.2f}% (< 1.0% threshold)"
        print(f"   🟡 Quiet session — sending keepalive ({skip_note})")
        send_text(f"📌 *Midday:* Quiet session. {skip_note}. No notable change.")
        print("✅ MIDDAY SCAN COMPLETE")
        return

    if nifty_moved:
        print(f"   ⚡ Skip gate: Nifty moved {nifty_change_abs:.1f}%")
    if vix_intraday_spike:
        vix_cp = vix.get("change_pct", 0)
        print(f"   ⚡ Skip gate: VIX intraday {vix_cp:+.1f}% (>15%)")
    if vix_spike:
        print(f"   ⚡ Skip gate: VIX spiked >20% from morning baseline")
    if breadth_notable:
        direction = "broad buying" if ad_ratio > 1.5 else "broad selling"
        print(f"   ⚡ Skip gate: Breadth A/D {ad_ratio:.2f} ({direction})")
    if has_extreme:
        alts = ", ".join(f"{m.get('symbol','')} {m.get('change_pct',0):+.1f}%" for m in alerts[:3])
        print(f"   ⚡ Skip gate: Extreme stock moves ({alts})")

    # ── Fragility Index banner (composite, with Pillar Lifecycle subtext) ──
    fragility_banner = ""
    pillar_lifecycle_str = ""
    try:
        from src.pillar_classifier import get_percentiles_from_csv, classify_pillars
        from src.pillar_lifecycle import compute_pillar_lifecycle, get_pillar_history_from_db
        from src.stress_index import compute_stress_index
        from src.fragility_index import compute_fragility_index
        _pcts = get_percentiles_from_csv()
        if _pcts:
            _plls = classify_pillars(_pcts)
            _stress = compute_stress_index()

            # Pillar lifecycle for each active pillar
            try:
                active_pillars = _stress.get("pillars", _plls) if _stress.get("ok") else _plls
                lc_parts = []
                for p in (active_pillars or [])[:4]:
                    p_name = p.get("name", p.get("pillar_name", ""))
                    p_score = p.get("score", 0)
                    if p_name and p_score >= 40:
                        _history = []
                        try:
                            _history = get_pillar_history_from_db(p_name, days=30)
                        except Exception:
                            pass
                        lc = compute_pillar_lifecycle(p_name, p_score, _history)
                        if lc.get("ok"):
                            lc_state = lc["state"]
                            lc_age = lc["age_days"]
                            lc_peak = lc.get("peak_score", "")
                            peak_str = f", Peak: {lc_peak:.0f}" if lc_peak else ""
                            lc_label = p.get("label", p_name.replace("_", " ").title())
                            lc_parts.append(f"{lc_label} ({lc_state}, Day {lc_age}{peak_str})")
                if lc_parts:
                    pillar_lifecycle_str = " | ".join(lc_parts)
            except Exception as e:
                print(f"   ⚠️ Pillar lifecycle: {e}")

            if _stress.get("ok"):
                _frag = compute_fragility_index(_stress["stress_score"], _plls)
                if _frag.get("ok"):
                    score = _frag["fragility_score"]
                    _midday_fragility = score
                    severity = _frag["severity"]
                    drivers = _stress.get("top_drivers", [])
                    driver_labels = {
                        "vix": "VIX", "fii": "FII Velocity", "usdinr": "USDINR",
                        "brent": "Brent", "skew": "Put-Call Skew", "breadth": "A/D Breadth",
                    }
                    driver_str = ", ".join(driver_labels.get(d, d) for d in drivers) if drivers else "none"
                    emoji = "🚨" if score >= 85 else "⚠️" if score >= 65 else "📌"
                    fragility_banner = f"{emoji} Fragility: {severity} ({score:.0f}/100) | Drivers: {driver_str}"
    except Exception as e:
        print(f"   ⚠️ Fragility banner: {e}")

    # Build local snapshot only — no global indices at midday
    lines = []
    if fragility_banner:
        lines.append(fragility_banner)
    if pillar_lifecycle_str:
        lines.append(f"📌 Pillars: {pillar_lifecycle_str}")

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

    # ── Midday breadth (A/D ratio, strength) ─────────────────────
    if breadth_data:
        adv = breadth_data.get("advances", 0)
        dec = breadth_data.get("declines", 0)
        if adv == 0 and dec == 0:
            if datetime.datetime.now().weekday() >= 5:
                lines.append("🏥 Midday Breadth: — (weekend)")
                print("   ⚠️ Weekend scan — skip gate was triggered by pre-market data")
            else:
                lines.append("")  # suppressed — no breadcrumb text
        else:
            strength = breadth_data.get("strength", "")
            lines.append(f"🏥 Midday Breadth: A/D {adv}/{dec} | {strength}")

    # ── Sector RS (rotation phases) ────────────────────────────
    try:
        from src.sector_rs import run_sector_rs_analysis
        sector_result = run_sector_rs_analysis()
        if sector_result.get("ok") and sector_result.get("phases"):
            lines.append("🔄 " + sector_result["phases"])
    except Exception as e:
        print(f"   ⚠️ Sector RS: {e}")

    # News headline (only if fresh — check cross-job + intra-day fingerprint)
    if validated_news:
        try:
            from src.db import get_bot_state, set_bot_state, get_seen_headlines, save_seen_headlines
            from src.formatters import set_seen_headlines as _set_form_hashes, is_headline_seen, add_seen_headline, get_all_seen_headlines
            from src.delta import news_fingerprint_hash

            # Load cross-job headline dedup from Supabase
            _today_str = datetime.datetime.now().strftime("%Y-%m-%d")
            _prev_hashes = get_seen_headlines(_today_str)
            if _prev_hashes:
                _set_form_hashes(_prev_hashes)

            # Intra-day fingerprint check
            current_fp = news_fingerprint_hash([a.get("headline", "") for a in validated_news[:3]])
            prev_fp = get_bot_state("news_fingerprint_midday")

            # Check first headline against cross-job hashes
            first_hash = hashlib.md5(validated_news[0].get("headline", "").encode()).hexdigest()
            already_seen_cross = is_headline_seen(first_hash)

            if (not prev_fp or current_fp != prev_fp) and not already_seen_cross:
                set_bot_state("news_fingerprint_midday", current_fp)
                top = validated_news[0]
                headline = top.get("headline", "")[:60]
                trust    = top.get("trust_score", 0)
                source   = top.get("source", "unknown")
                lines.append(f"📰 {headline} ({source}, trust {trust}/10)")
                # Mark seen for cross-job dedup
                add_seen_headline(first_hash)
                save_seen_headlines(_today_str, get_all_seen_headlines())
            else:
                lines.append("📰 Headlines unchanged")
        except Exception:
            top = validated_news[0]
            headline = top.get("headline", "")[:60]
            trust    = top.get("trust_score", 0)
            source   = top.get("source", "unknown")
            lines.append(f"📰 {headline} ({source}, trust {trust}/10)")

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

    # ── Derivatives snapshot (PCR, Max Pain, GEX) ─────────────────
    derivs_block = ""
    try:
        derivs_block = format_options_block(symbol="NIFTY", run_label="midday")
        print(f"   → Derivatives: {len(derivs_block)} chars")
    except Exception as e:
        print(f"   ⚠️ Derivatives: {e}")

    # ── Options Momentum (delta vs 09:15 baseline) ─────────────────
    opt_delta_str = ""
    try:
        from src.options_engine import get_latest_snapshot, run_options_analysis
        morning = get_latest_snapshot("NIFTY", "morning")
        midday_analysis = run_options_analysis("NIFTY", store=True, run_label="midday")
        if morning and midday_analysis.get("ok"):
            # Freshness guard: both sides must be live for meaningful comparison
            _both_live = (
                morning.get("data_source") == "live"
                and midday_analysis.get("data_source") == "live"
            )
            _morning_ts = morning.get("created_at", "")
            _today_prefix = datetime.datetime.now().strftime("%Y-%m-%d")
            _morning_from_today = _morning_ts.startswith(_today_prefix)

            if not _morning_from_today:
                print("   ⚠️ Options delta: morning snapshot from previous day — suppressed")
            elif not _both_live:
                print(f"   ⚠️ Options delta: source mismatch (morning={morning.get('data_source')}, midday={midday_analysis.get('data_source')}) — suppressed")
            else:
                delta_parts = []
                mp_m = morning.get("pcr")
                mp_c = midday_analysis.get("pcr", {}).get("pcr")
                if mp_m and mp_c and abs(mp_c - mp_m) > 0.01:
                    arrow = "↑" if mp_c > mp_m else "↓"
                    delta_parts.append(f"PCR {mp_m:.2f} → {mp_c:.2f} {arrow}")

                gex_m = morning.get("gex")
                gex_c = midday_analysis.get("gex", {}).get("net_gex_cr")
                if gex_m is not None and gex_c is not None and abs(gex_c - gex_m) > 10:
                    arrow = "↑" if gex_c > gex_m else "↓"
                    delta_parts.append(f"GEX ₹{gex_m:+.0f}Cr → ₹{gex_c:+.0f}Cr {arrow}")

                skew_m = morning.get("skew_25d")
                skew_c = midday_analysis.get("skew", {}).get("skew_25d")
                if skew_m is not None and skew_c is not None and abs(skew_c - skew_m) > 0.3:
                    arrow = "↑" if skew_c > skew_m else "↓"
                    delta_parts.append(f"Skew {skew_m:+.1f} → {skew_c:+.1f} {arrow}")

                if delta_parts:
                    opt_delta_str = "📊 Options Delta (vs 09:15): " + " | ".join(delta_parts)

            # GEX magnetic levels from midday snapshot (shown regardless of delta freshness)
            try:
                from src.options_engine import format_gex_levels
                gex_lvl = format_gex_levels(midday_analysis.get("gex", {}), midday_analysis.get("spot_price"))
                if gex_lvl:
                    opt_delta_str = (opt_delta_str + "\n" + gex_lvl) if opt_delta_str else gex_lvl
            except Exception:
                pass
    except Exception as e:
        print(f"   ⚠️ Options delta: {e}")

    if opt_delta_str:
        lines.append(opt_delta_str)

    # ── Regime / Fragility context (single source of truth) ──────────
    regime_info = _get_arbiter_regime()
    try:
        _reg = regime_info.get("regime", "NEUTRAL")
        if _midday_fragility is not None:
            lines.append(f"🏛 Regime: {_reg} | Fragility: {_midday_fragility:.0f}/100")
        else:
            lines.append(f"🏛 Regime: {_reg}")
    except Exception as e:
        print(f"   ⚠️ Regime context: {e}")

    # ── P6.3: Intraday Pillar Confirmation ──────────────────────────
    try:
        from src.pillar_classifier import get_current_pillar_scores
        _pillars_result = get_current_pillar_scores()
        if _pillars_result.get("ok") and _pillars_result["pillars"]:
            from src.intraday_pulse import check_intraday_pillar_confirmation, format_intraday_pillar_check
            _pillar_check = check_intraday_pillar_confirmation(_pillars_result["pillars"])
            if _pillar_check.get("ok"):
                pillar_check_text = format_intraday_pillar_check(_pillar_check)
                if pillar_check_text:
                    lines.append("\n" + pillar_check_text)
                    print(f"   → Intraday pillar check: {len(pillar_check_text)} chars")
            else:
                print(f"   ⚠️ Intraday pillar check skipped: {_pillar_check.get('reason', 'unknown')}")
        else:
            print(f"   ⚠️ No active pillars for intraday check")
    except Exception as e:
        print(f"   ⚠️ Intraday pillar check error: {e}")

    # ── AI midday brief (with universal validation) ────────────────
    print("🤖 Running AI midday analysis...")
    analysis = ""
    ground_truth = {}
    try:
        # Get bull/bear context
        from src.context_engine import run_contextualization, get_fii_dii_context, get_macro_context
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

    # Build computed pillar status summary (replaces generic AI paragraph)
    def _build_pillar_status_summary() -> str:
        """Compute a summary string from the intraday pillar check."""
        parts = []
        try:
            if _pillar_check.get("ok") and _pillar_check.get("pillar_confirmations"):
                for pc in _pillar_check["pillar_confirmations"]:
                    pname = pc.get("pillar_label", pc["pillar_name"].replace("_", " ").title())
                    status = pc["result"]
                    parts.append(f"{pname}: {status.lower()}")
            regime_label = regime_info.get("regime", "NEUTRAL") if regime_info else "NEUTRAL"
            status_str = " | ".join(parts) if parts else "No active pillars"
            return f"Pillar Status: {status_str}. Regime unchanged ({regime_label})."
        except Exception:
            return ""

    pillar_summary = _build_pillar_status_summary()

    def send_midday(text):
        bluf = ""
        try:
            from src.telegram_sender import build_bluf
            bluf = build_bluf(
                regime_verdict=regime_info,
            )
        except Exception:
            pass
        # Build body content
        body_parts = "\n".join(lines)
        computed = pillar_summary or text
        # Empty body guard — send heartbeat instead of blank message
        if not body_parts.strip() and not computed:
            _ts = datetime.datetime.now().strftime("%H:%M")
            send_text(f"📊 *MIDDAY SCAN* ({_ts}): No notable change. Nifty {nifty_change_pct:+.2f}%.")
            return
        msg = "📊 *MIDDAY MARKET SCAN*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        if bluf:
            msg += bluf + "\n\n"
        msg += body_parts
        if computed:
            msg += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n{computed}"
        if derivs_block:
            msg += f"\n\n{derivs_block}"
        if alerts:
            msg += f"\n\n⚠️ *Extreme Moves:*\n" + "\n".join(alerts)
        msg += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n_Mid-session check_"
        send_text(msg)

    if prompt and ground_truth.get("nifty_close"):
        ai_generate_and_validate(
            ai, "fast", prompt, ground_truth,
            output_type="midday_scan",
            fallback_fn=lambda: "",
            send_fn=send_midday,
            max_retries=1,
        )
    else:
        send_midday("")

    # ── Persist midday findings to daily_state ──
    try:
        _midday_findings = {
            "pillar_summary": pillar_summary,
            "options_delta": opt_delta_str,
            "regime": regime_info.get("regime") if regime_info else None,
        }
        if _pillar_check.get("ok") and _pillar_check.get("pillar_confirmations"):
            _midday_findings["pillar_confirmations"] = [
                {"pillar_name": p["pillar_name"], "result": p["result"]}
                for p in _pillar_check["pillar_confirmations"]
            ]
        mark_job_completed("midday_scan", _midday_findings)
    except Exception:
        pass

    # ── P27: State Journal append (fail-open) ──
    try:
        from src.state_journal import append_journal
        _ri = locals().get("regime_info", {})
        append_journal(
            job_tag="midday_scan",
            regime=_ri.get("regime"),
            fingerprint=locals().get("_current_fp"),
            manifest_version=locals().get("_manifest_mid", {}).get("version"),
            triage=str(locals().get("_triage", "GREEN")),
            nifty=locals().get("valid_index", {}).get("India", {}).get("price"),
            vix=locals().get("valid_index", {}).get("VIX", {}).get("price"),
        )
    except Exception:
        pass

    print("✅ MIDDAY SCAN COMPLETE")
    print(f"  → Total execution: {time.time() - _job_start:.1f}s")

if __name__ == "__main__":
    main()
