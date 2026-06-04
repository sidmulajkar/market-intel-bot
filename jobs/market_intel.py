"""
Market Intel — AI-powered market analysis
Modes: morning (blocks 1,2,4,6,8) or evening (all 10 blocks)
"""
import sys
import os
import time as _time
import statistics

_job_start = _time.time()

_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_dir)
if _root not in sys.path:
    sys.path.insert(0, _root)

import importlib.util
_spec = importlib.util.find_spec("src.data_fetcher")
if _spec is None:
    print(f"ERROR: src not found. sys.path = {sys.path}")
    sys.exit(1)

from src.data_fetcher   import fetch_global_indices, fetch_macro_anchors, fetch_watchlist_data, fetch_general_news, fetch_indian_news
from src.formatters     import format_global_indices, format_macro_anchors, format_flows, format_news, format_watchlist, format_mf_flows, format_context_block, format_options_block, format_insider_activity, set_seen_headlines, get_all_seen_headlines
from src.context_engine import run_contextualization
from src.ai_engine      import AIEngine
from src.telegram_sender import send_text
from src.db             import get_client, save_macro_snapshots_batch, get_seen_headlines, save_seen_headlines
from src.validator      import validate_articles
from src.validation_helper import _validate_with_output_type, _OUTPUT_TYPE_CONFIG
from src.compute_budget import ComputeBudget, get_block_fallback, BLOCK_PRIORITY
from src.manifest import load as manifest_load
from src.fingerprint import compute_raw_fingerprint, build_anchor_dict, should_skip
from src.bot_state import get_skip_meta, update_skip_meta
from src.guardian import Guardian, TriageLevel



# AI Response Validation
def validate_ai_response(response: str, min_words: int = 50) -> bool:
    if not response or not isinstance(response, str):
        return False
    return len(response.split()) >= min_words


def _check_extreme_conditions(raw_data: dict) -> tuple[int, list]:
    """Check for extreme macro conditions. Returns (count, list of messages)."""
    extreme_count = 0
    messages = []

    anchors = raw_data.get("anchor_data", [])
    fii_data = raw_data.get("fii_data", {})

    for a in anchors:
        if not a.get("ok") or not a.get("price"):
            continue
        name = a.get("name", "")
        price = a["price"]

        if name == "USD/INR" and price >= 90:
            extreme_count += 1
            messages.append(f"INR at historic lows (₹{price:.1f})")
        elif name == "Brent Crude" and price >= 90:
            extreme_count += 1
            messages.append(f"Brent at stress level (${price:.0f})")
        elif name == "India VIX" and price >= 20:
            extreme_count += 1
            messages.append(f"VIX elevated ({price:.1f})")
        elif name == "Gold" and price >= 4000:
            extreme_count += 1
            messages.append(f"Gold at extreme (${price:,.0f})")

    # FII selling streak
    streak = fii_data.get("fii_streak", 0)
    fii_net = fii_data.get("fii_net", 0)
    if streak >= 3 and fii_net < 0:
        extreme_count += 1
        messages.append(f"FII selling streak ({streak} days, ₹{fii_net:+,.0f}Cr)")

    return extreme_count, messages


def _build_market_intel_bluf(snapshot_data: dict) -> str:
    """Build BLUF header for market intel messages — regime-template-driven."""
    try:
        from src.telegram_sender import build_bluf
        regime_verdict = _get_arbiter_regime_for_intel()
        return build_bluf(
            regime_verdict=regime_verdict,
        )
    except Exception:
        return ""


def _get_arbiter_regime_for_intel() -> dict:
    """Read arbitrated regime from MarketState for market_intel jobs."""
    try:
        from datetime import datetime
        from src.db import get_latest_market_state
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


def render_deterministic_intel(raw_data: dict, mode: str = "morning") -> str:
    """Render a complete intelligence brief from raw data — no AI needed, no apology.

    Produces: arbitrated regime header, tension variables, key data, posture, triggers.
    Regime comes from the single arbiter — not recomputed locally.
    """
    from src.posture_engine import format_posture_card
    from src.regime_arbiter import arbitrate_regime, RegimeVerdict
    from src.state import MarketState

    mode_label = "MORNING" if mode == "morning" else "EVENING"
    lines = []

    # ── Extract macro data for MarketState ─────────────────────────
    anchors = raw_data.get("anchor_data", [])
    fii_data = raw_data.get("fii_data", {})
    snapshot_data = raw_data.get("snapshot_data", {})

    vix = usdinr = brent = gold = None
    fii_net = fii_streak = dii_net = None
    bb_norm = None
    nifty_price = None
    nifty_change = None

    for a in anchors:
        if not a.get("ok") or not a.get("price"):
            continue
        name = a.get("name", "")
        if name == "India VIX":
            vix = a["price"]
        elif name == "USD/INR":
            usdinr = a["price"]
        elif name == "Brent Crude":
            brent = a["price"]
        elif name == "Gold":
            gold = a["price"]

    if fii_data:
        fii_net = fii_data.get("fii_net")
        fii_streak = fii_data.get("fii_streak")
        dii_net = fii_data.get("dii_net")

    if snapshot_data:
        nifty_price = snapshot_data.get("nifty_close")
        nifty_change = snapshot_data.get("nifty_return_1d")
        bb_norm = snapshot_data.get("bull_bear_normalized")

    # ── Build minimal MarketState and call arbiter ─────────────────
    from datetime import datetime
    state = MarketState(trade_date=datetime.now().strftime("%Y-%m-%d"))
    if bb_norm is not None:
        state.bull_bear_normalized = bb_norm
    if vix is not None:
        state.macro.vix = vix
    if usdinr is not None:
        state.macro.usdinr = usdinr
    if brent is not None:
        state.macro.brent = brent
    if gold is not None:
        state.macro.gold = gold
    if fii_net is not None:
        state.flows.fii_net = fii_net
        state.flows.fii_streak_days = fii_streak or 0
    if dii_net is not None:
        state.flows.dii_net = dii_net

    flow_metrics = {
        "fii_net": fii_net,
        "fii_streak_days": fii_streak or 0,
    }
    verdict = arbitrate_regime(state, flow_metrics=flow_metrics)

    # ── Build arbitrated BLUF header ───────────────────────────────
    emoji = "🟢" if verdict.regime in ("BULLISH", "CONSTRUCTIVE") else ("🔴" if verdict.regime == "DEFENSIVE" else "🟡")
    nifty_str = f" | Nifty {nifty_price:,.0f}" if nifty_price else ""
    if nifty_price and nifty_change is not None:
        sign = "+" if nifty_change >= 0 else ""
        nifty_str += f" ({sign}{nifty_change:.1f}%)"

    lines.append(f"*{mode_label} INTEL*")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append(f"{emoji} *REGIME: {verdict.regime}* ({verdict.confidence}){nifty_str}")
    lines.append(f"  {verdict.narrative}")
    if verdict.dominant_driver:
        lines.append(f"  Drivers: {verdict.dominant_driver}")
    lines.append("")

    # ── Tension variables (opposing forces) ────────────────────────
    tensions = []
    if usdinr and usdinr >= 90:
        tensions.append(f"INR ₹{usdinr:.0f}: import pain, but IT revenue tailwind")
    if brent and brent >= 80:
        tensions.append(f"Brent ${brent:.0f}: CAD drag, fiscal pressure")
    if fii_net and fii_net < 0:
        tensions.append(f"FII ₹{fii_net:+,.0f}Cr: liquidity drain")
    if vix and vix < 15:
        tensions.append(f"VIX {vix:.0f}: complacency, not fear")
    if tensions:
        lines.append(f"Tension: {'; '.join(tensions[:3])}")
        lines.append("")

    # ── Build key data section ─────────────────────────────────────
    key_lines = []
    for a in anchors:
        if not a.get("ok") or not a.get("price"):
            continue
        name = a.get("name", "")
        price = a["price"]
        chg = a.get("change_pct", 0)
        if name in ("USD/INR", "Brent Crude", "India VIX", "Gold"):
            if name == "USD/INR":
                key_lines.append(f"  USDINR: ₹{price:.2f} ({chg:+.1f}%)")
            elif name == "India VIX":
                key_lines.append(f"  VIX: {price:.1f} ({chg:+.1f}%)")
            else:
                symbol = name.split()[0]
                key_lines.append(f"  {symbol}: ${price:,.0f} ({chg:+.1f}%)")

    if fii_net is not None:
        key_lines.append(f"  FII: ₹{fii_net:+,.0f}Cr")
        if fii_streak and abs(fii_streak) >= 3:
            direction = "buying" if fii_net > 0 else "selling"
            key_lines.append(f"  FII {direction} streak: {abs(fii_streak)} days")

    if dii_net is not None:
        key_lines.append(f"  DII: ₹{dii_net:+,.0f}Cr")

    if key_lines:
        lines.append("Key data:")
        lines.extend(key_lines)
        lines.append("")

    # ── Posture card (Action + Watch levels) from arbiter verdict ──
    if verdict.posture:
        lines.append(format_posture_card(verdict.posture))
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────
def _save_morning_fingerprint(snapshot_data: dict, state) -> None:
    """Save morning snapshot fingerprint for evening delta comparison."""
    try:
        import json
        from datetime import datetime
        from src.db import set_bot_state
        fp = {
            "nifty_close": snapshot_data.get("nifty_close"),
            "vix": snapshot_data.get("india_vix"),
            "usdinr": snapshot_data.get("usdinr"),
            "brent": snapshot_data.get("brent"),
            "fii_net": snapshot_data.get("fii_net"),
            "regime": getattr(state, "final_regime", None),
        }
        set_bot_state(f"morning_fingerprint_{datetime.now().strftime('%Y-%m-%d')}", json.dumps(fp))
        print(f"   ✅ Morning fingerprint saved")
    except Exception as e:
        print(f"   ⚠️ Morning fingerprint: {e}")


def _check_evening_delta() -> bool:
    """Compare evening metrics against morning fingerprint. Send compressed if no change. Returns True if sent."""
    try:
        import json
        from datetime import datetime
        from src.db import get_bot_state, get_market_state
        from src.data_fetcher import fetch_macro_anchors, fetch_global_indices
        from src.context_engine import get_fii_dii_context

        today_str = datetime.now().strftime("%Y-%m-%d")
        raw = get_bot_state(f"morning_fingerprint_{today_str}")
        if not raw:
            return False

        morning = json.loads(raw)
        evening_anchors = fetch_macro_anchors() or []
        evening_indices = fetch_global_indices() or {}

        def _get(name):
            for a in evening_anchors:
                if a.get("name") == name and a.get("ok") and a.get("price"):
                    return a["price"]
            return None

        e_vix = _get("India VIX")
        e_usdinr = _get("USD/INR")
        e_brent = _get("Brent Crude")
        e_nifty = evening_indices.get("India", {}).get("price")

        e_fii = None
        try:
            fii_ctx = get_fii_dii_context(days=5)
            if fii_ctx.get("ok"):
                e_fii = fii_ctx.get("fii_net")
        except Exception:
            pass

        persisted = get_market_state(today_str)
        e_regime = persisted.get("final_regime") if persisted else None

        # Thresholds: diff beyond these → run full analysis
        m_nifty = morning.get("nifty_close")
        if m_nifty and e_nifty and abs(e_nifty - m_nifty) / m_nifty > 0.003:
            return False
        m_vix = morning.get("vix")
        if m_vix and e_vix and abs(e_vix - m_vix) > 1.5:
            return False
        m_usdinr = morning.get("usdinr")
        if m_usdinr and e_usdinr and abs(e_usdinr - m_usdinr) / m_usdinr > 0.005:
            return False
        m_brent = morning.get("brent")
        if m_brent and e_brent and abs(e_brent - m_brent) / m_brent > 0.03:
            return False
        m_fii = morning.get("fii_net")
        if m_fii is not None and e_fii is not None and abs(e_fii - m_fii) > 500:
            return False
        m_regime = morning.get("regime")
        if m_regime and e_regime and e_regime != m_regime:
            return False

        # No notable change — send compressed
        override = persisted.get("final_override_reason", "") if persisted else ""
        macro_data = persisted.get("macro", {}) if persisted else {}
        u = macro_data.get("usdinr", "")
        b = macro_data.get("brent", "")
        v = macro_data.get("vix", "")
        triggers = []
        if u:
            triggers.append(f"USDINR ₹{u}")
        if b:
            triggers.append(f"Brent ${b}")
        if v:
            triggers.append(f"VIX {v}")
        trigger_str = ", ".join(triggers[:3])
        regime_label = (e_regime or morning.get("regime", "NEUTRAL")).lower().title()
        compressed = f"📌 *EVENING INTEL CHECK:* {regime_label}"
        if e_regime == "DEFENSIVE" and trigger_str:
            compressed += f" | Triggers: {trigger_str}"
        try:
            from src.economic_calendar import get_high_impact_soon
            hi = get_high_impact_soon(days=2)
            if hi:
                compressed += f" | ⚠️ {hi}"
            else:
                compressed += " | Tracking — no notable change."
        except Exception:
            compressed += " | Tracking — no notable change."

        from src.telegram_sender import send_text
        send_text(compressed)
        print("   ✅ Delta Tracker: no notable change — compressed")
        return True
    except Exception as e:
        print(f"   ⚠️ Delta Tracker check: {e}")
        return False


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "morning"
    if mode not in ("morning", "evening"):
        print(f"Usage: python market_intel.py [morning|evening]")
        sys.exit(1)

    print("=" * 50)
    print(f"📊 MARKET INTEL ({mode.upper()}) STARTING")
    print("=" * 50)

    # Evening delta check: skip full computation if nothing changed
    if mode == "evening" and _check_evening_delta():
        print("✅ MARKET INTEL COMPLETE (compressed — no delta)")
        return

    # Load master prompt
    try:
        with open("config/master_prompt.txt", "r") as f:
            master_template = f.read()
    except Exception as e:
        print(f"⚠️  Master prompt not found: {e}")
        send_text("⚠️ Market Intel: Configuration error.")
        return

    blocks = {}
    source_health = {}  # Track which sources succeeded/failed
    anchor_data = None  # Initialized for health check

    # ── Compute budget tracking (Phase 23) ────────────────────────
    budget = ComputeBudget(max_seconds=200)  # 3m20s (GitHub Actions limit ~3-4m)
    budget.start()

    # ── BLOCK 1: Global Indices ───────────────────────────────────
    _t0 = _time.time()
    print("🔄 BLOCK 1: Global Indices")
    try:
        index_data = fetch_global_indices()
        blocks["block_1"] = format_global_indices(index_data)
        print(f"   → {len(blocks['block_1'])} chars")
    except Exception as e:
        print(f"   ⚠️ {e}")
        blocks["block_1"] = ""

    # ── MARKET BREADTH ───────────────────────────────────────────
    print("🔄 MARKET BREADTH")
    breadth = None
    try:
        from src.data_fetcher import fetch_market_breadth, format_market_breadth
        breadth = fetch_market_breadth()
        # Save breadth snapshot for historical percentile
        if breadth and breadth.get("advances") and breadth.get("declines"):
            from src.db import save_breadth_snapshot, today_str
            adv = breadth["advances"]
            dec = breadth["declines"]
            ratio = round(adv / dec, 2) if dec > 0 else 0
            save_breadth_snapshot(today_str(), adv, dec, ratio)
        breadth_str = format_market_breadth(breadth)
        if breadth_str:
            blocks["block_1"] = blocks.get("block_1", "") + "\n\n" + breadth_str
            print(f"   → Breadth: {len(breadth_str)} chars")
    except Exception as e:
        print(f"   ⚠️ Breadth: {e}")

    # ── ECONOMIC CALENDAR (Block 1 — event risk context) ──────────
    try:
        from src.economic_calendar import get_upcoming_events, format_calendar
        cal_events = get_upcoming_events(days=7)
        cal_str = format_calendar(cal_events)
        if cal_str:
            blocks["block_1"] = blocks.get("block_1", "") + "\n\n" + cal_str
            print(f"   → Calendar: {len(cal_str)} chars")
    except Exception as e:
        print(f"   ⚠️ Calendar: {e}")

    # ── BLOCK 2: Macro Anchors ───────────────────────────────────
    print(f"   ⏱️ Block 1: {_time.time()-_t0:.1f}s")
    _t0 = _time.time()
    print("🔄 BLOCK 2: Macro Anchors")
    try:
        anchor_data = fetch_macro_anchors()

        # ── P18/P14/P16: Guardian + Fingerprint Skip Gate ─────────
        try:
            from datetime import datetime, timezone
            _manifest = manifest_load()
            guardian = Guardian(_manifest)
            for a in anchor_data or []:
                guardian.check_source(
                    a.get("symbol", ""), a.get("price"),
                    "live" if a.get("ok") else "fallback", 0,
                )
            _anchors_dict = build_anchor_dict(anchor_data, index_data)
            _current_fp = compute_raw_fingerprint(_anchors_dict, _manifest)
            _last_fp, _last_sent_at = get_skip_meta()
            _skip, _reason = should_skip(_current_fp, _last_fp, _last_sent_at, heartbeat_min=240)
            if _skip:
                if "Heartbeat" in _reason:
                    send_text(f"📌 *MARKET INTEL ({mode.upper()})*: Steady state. No notable change.")
                    update_skip_meta(_current_fp, datetime.now(timezone.utc).isoformat())
                else:
                    print(f"⏭️  FINGERPRINT SKIP: {_reason}")
                print("✅ MARKET INTEL COMPLETE (skipped)")
                return
            update_skip_meta(_current_fp, datetime.now(timezone.utc).isoformat())
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

        blocks["block_2"] = format_macro_anchors(anchor_data)
        print(f"   → {len(blocks['block_2'])} chars")
        # Save macro snapshots for historical percentile + cross-asset tracking
        try:
            saved = save_macro_snapshots_batch(anchor_data)
            print(f"   → Saved {saved} macro snapshots")
        except Exception as e:
            print(f"   ⚠️ Macro snapshot save: {e}")
    except Exception as e:
        print(f"   ⚠️ {e}")

    # ── P8.1: India vs EM Basket (30D RS) ──────────────────────────
    try:
        from src.value_metrics import compute_india_vs_em_rs
        rs = compute_india_vs_em_rs()
        if rs.get("ok"):
            print(f"   📊 India vs EM spread: {rs['spread']:+.1f}% (30D)")
    except Exception as e:
        print(f"   ⚠️ India vs EM: {e}")

    # ── MECHANISM TRIGGERS (macro → sector impact) ─────────────
    mechanism_block = ""
    try:
        from src.mechanism_map import detect_triggered_mechanisms, format_mechanism_triggers
        from src.formatters import get_percentile_value
        if anchor_data:
            # Build percentile data for arbitration
            mechanism_percentiles = {}
            symbol_to_metric = {
                "BZ=F": "brent", "DX-Y.NYB": "dxy", "^TNX": "us_10y",
                "GC=F": "gold", "HG=F": "copper", "^INDIAVIX": "india_vix",
                "CL=F": "wti", "^VIX": "cboe_vix", "HYG": "hyg",
            }
            for sym, metric in symbol_to_metric.items():
                for a in anchor_data:
                    if a.get("symbol") == sym and a.get("ok") and a.get("price"):
                        pct = get_percentile_value(metric, a["price"], "1Y")
                        if pct is not None:
                            mechanism_percentiles[sym] = {"percentile": pct}
                        break
            triggered = detect_triggered_mechanisms(anchor_data, percentile_data=mechanism_percentiles)
            mechanism_block = format_mechanism_triggers(triggered)
            if mechanism_block:
                print(f"   → Mechanism triggers: {len(triggered)} triggered")
    except Exception as e:
        print(f"   ⚠️ Mechanism triggers: {e}")

    # ── VALUATION METRICS (append to Block 2) ────────────────────
    print("🔄 VALUATION (P/E, P/B, Risk Premium)")
    try:
        from src.formatters import format_valuation_block
        val_str = format_valuation_block()
        if val_str:
            blocks["block_2"] = blocks.get("block_2", "") + "\n\n" + val_str
            print(f"   → Valuation: {len(val_str)} chars")
    except Exception as e:
        print(f"   ⚠️ Valuation: {e}")
        anchor_data = None
        blocks["block_2"] = ""

    # ── NIFTY TECHNICAL ANALYSIS ──────────────────────────────────
    print("🔄 NIFTY TECHNICAL LEVELS")
    nifty_closes = []
    try:
        from src.csv_data import get_nifty_close_series
        from src.technical_analysis import compute_full_analysis, format_technical_analysis
        nifty_hist = get_nifty_close_series(days=252)
        if len(nifty_hist) >= 20:
            nifty_closes = nifty_hist.tolist()
            nifty_ta = compute_full_analysis(nifty_closes, "NIFTY 50")
            nifty_ta_str = format_technical_analysis(nifty_ta)
            if nifty_ta_str:
                # Promote 200-DMA distance to headline in Block 1
                ma200_dist = nifty_ta.get("ma200_dist_pct")
                if ma200_dist is not None:
                    trend_label = "above" if ma200_dist > 0 else "below"
                    headline_ta = f"📍 Nifty 50: {trend_label} 200-DMA by {abs(ma200_dist):.1f}%"
                    blocks["block_1"] = blocks.get("block_1", "") + "\n" + headline_ta
                # Append full TA below
                blocks["block_1"] = blocks.get("block_1", "") + "\n\n" + nifty_ta_str
                print(f"   → Nifty TA: {len(nifty_ta_str)} chars")
    except Exception as e:
        print(f"   ⚠️ Nifty TA: {e}")

    # ── CONTEXT BLOCK: Bull/Bear Score ─────────────────────────────
    print("🔄 CONTEXT: Bull/Bear Score")
    try:
        if anchor_data:
            # Gather extra signals from already-fetched data
            extra_signals = {}
            # Market breadth
            if breadth and isinstance(breadth, dict):
                adv = breadth.get("advances", 0)
                dec = breadth.get("declines", 0)
                if dec > 0:
                    extra_signals["breadth_ratio"] = round(adv / dec, 2)
            # Nifty vs 200-DMA
            if nifty_closes and len(nifty_closes) >= 200:
                from src.technical_analysis import compute_moving_averages
                ma_data = compute_moving_averages(nifty_closes)
                if ma_data.get("ma200_dist_pct") is not None:
                    extra_signals["nifty_vs_ma200_pct"] = ma_data["ma200_dist_pct"]
            # PCR from options engine (fetched directly, not from formatted block)
            try:
                from src.options_engine import run_options_analysis
                pcr_data = run_options_analysis("NIFTY", store=False, run_label="context")
                if pcr_data and pcr_data.get("pcr") is not None:
                    pcr_value = pcr_data["pcr"]
                    extra_signals["pcr"] = pcr_value if isinstance(pcr_value, (int, float)) else pcr_value.get("pcr")
            except Exception:
                pass  # Non-critical

            context_output = format_context_block(anchor_data, extra_signals=extra_signals)
            blocks["block_0"] = context_output
            blocks["block_context"] = context_output
            print(f"   → {len(context_output)} chars (Bull/Bear context)")
        else:
            blocks["block_0"] = ""
            blocks["block_context"] = ""
    except Exception as e:
        print(f"   ⚠️ Context engine: {e}")
        blocks["block_0"] = ""
        blocks["block_context"] = ""

    # ── OPTIONS BLOCK: PCR, Max Pain, OI Zones ────────────────────
    print("🔄 OPTIONS: PCR, Max Pain, OI Zones")
    try:
        options_output = format_options_block(symbol="NIFTY", run_label=mode)
        blocks["block_5"] = options_output  # Wire to {block_5} in master_prompt.txt
        print(f"   → {len(options_output)} chars")
    except Exception as e:
        print(f"   ⚠️ Options engine: {e}")
        blocks["block_5"] = ""

    # ── FII/DII F&O POSITIONING ──────────────────────────────────
    print("🔄 F&O PARTICIPANT POSITIONING")
    fno_analysis = {}
    try:
        from src.fii_derivatives import run_fno_analysis_with_data
        fno_output, fno_analysis = run_fno_analysis_with_data()
    except Exception as e:
        print(f"   ⚠️ F&O positioning: {e}")
        fno_output = ""

    # ── BLOCK 4: FII/DII Flows ───────────────────────────────────
    print(f"   ⏱️ Blocks 2-3: {_time.time()-_t0:.1f}s")
    _t0 = _time.time()
    print("🔄 BLOCK 4: Flow Intelligence")
    try:
        ctx_for_flows = getattr(format_context_block, 'last_ctx', None) or {}
        blocks["block_4"] = format_flows(ctx_for_flows)
        # Append F&O positioning to Block 4
        if fno_output:
            blocks["block_4"] = blocks["block_4"] + "\n\n" + fno_output
        print(f"   → {len(blocks['block_4'])} chars")
    except Exception as e:
        print(f"   ⚠️ {e}")
        blocks["block_4"] = ""

    # ── BLOCK 6: News (Global + Indian) ───────────────────────────
    print(f"   ⏱️ Blocks 4-5: {_time.time()-_t0:.1f}s")
    _t0 = _time.time()
    print("🔄 BLOCK 6: News Intelligence")
    try:
        # Load cross-job headline dedup hashes
        try:
            from src.db import today_str as _ts
            _date_str = _ts()
            _prev = get_seen_headlines(_date_str)
            if _prev:
                set_seen_headlines(_prev)
        except Exception:
            pass

        ai = AIEngine()

        # Global news (Finnhub)
        raw_global = fetch_general_news()
        global_validated = validate_articles(raw_global, min_trust=6) if raw_global else []
        for article in global_validated[:5]:
            article["sentiment"] = ai.sentiment(article.get("headline", ""))

        # Indian news (RSS)
        raw_indian = fetch_indian_news()
        indian_validated = validate_articles(raw_indian, min_trust=4) if raw_indian else []
        for article in indian_validated[:5]:
            article["sentiment"] = ai.sentiment(article.get("headline", ""))

        blocks["block_6"] = format_news(global_validated, indian_validated)

        # Persist updated headline hashes for cross-job dedup
        try:
            save_seen_headlines(_date_str, get_all_seen_headlines())
        except Exception:
            pass

        print(f"   → {len(blocks['block_6'])} chars ({len(global_validated)} global, {len(indian_validated)} indian)")
    except Exception as e:
        print(f"   ⚠️ {e}")
        blocks["block_6"] = ""

    # ── BLOCK 8: Top Movers (India + US) ─────────────────────────
    print(f"   ⏱️ Blocks 6-7: {_time.time()-_t0:.1f}s")
    _t0 = _time.time()
    print("🔄 BLOCK 8: Top Movers (India + US)")
    try:
        from src.data_fetcher import fetch_top_movers
        from src.formatters import format_top_movers
        movers = fetch_top_movers(top_n=10)
        blocks["block_8"] = format_top_movers(movers)
        print(f"   → {len(blocks['block_8'])} chars")
    except Exception as e:
        print(f"   ⚠️ {e}")
        blocks["block_8"] = ""

    # ── SHAREHOLDING QoQ CHANGES (evening only, top 5 gainers) ───
    if mode == "evening" and blocks.get("block_8"):
        print("🔄 SHAREHOLDING PATTERN (QoQ)")
        try:
            from src.shareholding_tracker import track_all_watchlist_shareholding
            # Use top 5 India gainers for shareholding tracking
            top_stocks = [s["symbol"] for s in movers.get("india", {}).get("gainers", [])[:5]] if movers else []
            if top_stocks:
                sh_results = track_all_watchlist_shareholding(top_stocks)
                sig_changes = [r for r in sh_results if r.get("has_significant_change")]
                if sig_changes:
                    sh_lines = ["\n📊 *Shareholding QoQ Changes:*"]
                    for r in sig_changes:
                        for c in r["changes"][:2]:
                            sig = "🚨" if c.get("significant") else "⚠️"
                            sh_lines.append(
                                f"{sig} {r['symbol']}: {c['category'][:25]} "
                                f"{c['previous']:.1f}%→{c['current']:.1f}% ({c['delta']:+.1f}%)"
                            )
                    blocks["block_8"] += "\n" + "\n".join(sh_lines)
                    print(f"   → {len(sig_changes)} stocks with significant QoQ changes")
                else:
                    print("   → No significant QoQ changes")
        except Exception as e:
            print(f"   ⚠️ Shareholding: {e}")

    # ── BLOCK 3: Sector FPI Activity ─────────────────────────────
    budget.start_stage("formatters")
    if budget.should_skip_block("block_3"):
        print("  ⏭️ BLOCK 3: Skipped (budget tight)")
        blocks["block_3"] = get_block_fallback("block_3")
    else:
        print("🔄 BLOCK 3: Sector FPI Activity")
        try:
            from src.fii_sector import run_sector_fpi_analysis
            blocks["block_3"] = run_sector_fpi_analysis()
            print(f"   → {len(blocks['block_3'])} chars")
        except Exception as e:
            print(f"   ⚠️ {e}")
            blocks["block_3"] = ""

    # ── FII INSTITUTION TRACKER (SWF/Pension Fund Activity) ──────
    print("🔄 FII INSTITUTION TRACKER")
    try:
        from src.fii_tracker import run_fii_tracker
        tracker_output = run_fii_tracker()
        if tracker_output:
            blocks["block_3"] = blocks.get("block_3", "") + "\n\n" + tracker_output
            print(f"   → Institution tracker: {len(tracker_output)} chars")
    except Exception as e:
        print(f"   ⚠️ FII tracker: {e}")

    # ── BLOCK 7: Insider Activity ────────────────────────────────
    if budget.should_skip_block("block_7"):
        print("  ⏭️ BLOCK 7: Skipped (budget tight)")
        blocks["block_7"] = get_block_fallback("block_7")
    else:
        print("🔄 BLOCK 7: Insider Activity")
        try:
            insider_str = format_insider_activity()
            turnover_str = ""
            try:
                from src.turnover_ratio import compute_turnover_ratio, format_turnover
                from src.data_fetcher import fetch_nse_volumes
                vols = fetch_nse_volumes()
                if vols and vols.get("ok"):
                    tr = compute_turnover_ratio(vols.get("fno_volume", 0), vols.get("cash_volume", 0))
                    turnover_str = format_turnover(tr)
            except Exception as e2:
                print(f"   ⚠️ Turnover ratio: {e2}")
            if insider_str and turnover_str:
                blocks["block_7"] = insider_str + "\n\n" + turnover_str
            elif turnover_str:
                blocks["block_7"] = turnover_str
            else:
                blocks["block_7"] = insider_str or ""
            print(f"   → {len(blocks['block_7'])} chars")
        except Exception as e:
            print(f"   ⚠️ {e}")
            blocks["block_7"] = ""

    # ── BLOCK 9: Macro Calendar ─────────────────────────────────────
    if budget.should_skip_block("block_9"):
        print("  ⏭️ BLOCK 9: Skipped (budget tight)")
        blocks["block_9"] = get_block_fallback("block_9")
    else:
        print("🔄 BLOCK 9: Macro Calendar")
        try:
            from src.macro_fetcher import format_macro_block
            blocks["block_9"] = format_macro_block()
            if blocks["block_9"]:
                print(f"   → Macro: {len(blocks['block_9'])} chars")
        except Exception as e:
            print(f"   ⚠️ Macro calendar: {e}")
            blocks["block_9"] = ""

    if mode == "evening":
        # BLOCK 10: MF Flows
        if budget.should_skip_block("block_10"):
            print("  ⏭️ BLOCK 10: Skipped (budget tight)")
            blocks["block_10"] = get_block_fallback("block_10")
        else:
            print("🔄 BLOCK 10: MF Flows")
            try:
                mf_str = format_mf_flows()
                carry_str = ""
                try:
                    anchors = fetch_macro_anchors()
                    india_10y = us_10y = None
                    for a in anchors or []:
                        if a.get("name") == "India 10Y Yield" and a.get("ok"):
                            india_10y = a["price"]
                        elif a.get("name") == "US 10Y Yield" and a.get("ok"):
                            us_10y = a["price"]
                    parts = []
                    if india_10y is not None and us_10y is not None:
                        spread = india_10y - us_10y
                        hist = get_daily_market_snapshots(days=10)
                        spread_vals = []
                        for snap in hist:
                            iy = snap.get("india_10y")
                            uy = snap.get("us_10y")
                            if iy and uy:
                                spread_vals.append(iy - uy)
                        spread_note = ""
                        if len(spread_vals) >= 3:
                            from statistics import mean
                            avg_spread = mean(spread_vals)
                            if abs(spread - avg_spread) > 0.2:
                                spread_note = " ↑ widening vs 5D avg" if spread > avg_spread else " ↓ narrowing vs 5D avg"
                        parts.append(f"IND-US 10Y spread: {spread:.1f}%{spread_note}")
                    fno_o, fno_a = run_fno_analysis_with_data()
                    if fno_a and fno_a.get("fii_long_short_ratio"):
                        parts.append(f"FII F&O L/S: {fno_a['fii_long_short_ratio']:.2f}x")
                    if parts:
                        carry_str = "\n\n📊 Post-Close: " + " | ".join(parts)
                except Exception as e2:
                    print(f"   ⚠️ Post-close carry: {e2}")
                blocks["block_10"] = (mf_str + carry_str) if mf_str else carry_str or ""
                print(f"   → {len(blocks['block_10'])} chars")
            except Exception as e:
                print(f"   ⚠️ {e}")
                blocks["block_10"] = ""
    else:
        blocks["block_10"] = ""

    # ── ROLLING QUANT ENGINE (percentiles, divergences, scenarios, correlations) ──
    print(f"   ⏱️ Blocks 8-10: {_time.time()-_t0:.1f}s")
    _t0 = _time.time()
    print("🔄 ROLLING QUANT ENGINE")
    rolling_quant_block = ""
    snapshot_data = {}
    hist_snapshots = []
    try:
        from src.rolling_quant import run_rolling_quant_engine, format_rolling_quant_block
        from src.db import get_daily_market_snapshots, save_daily_market_snapshot

        # Build today's snapshot from collected data
        _ctx_rq = getattr(format_context_block, 'last_ctx', None) or {}

        # Live Nifty from global indices (not CSV) — keeps display consistent with Open/Close
        _live_nifty = None
        _live_nifty_chg = None
        try:
            _in = (index_data or {}).get("India", {})
            if _in.get("price"):
                _live_nifty = _in["price"]
                _live_nifty_chg = _in.get("change_pct")
        except Exception:
            pass

        snapshot_data = {
            "nifty_close": _live_nifty or (nifty_closes[-1] if nifty_closes else None),
            "nifty_return_1d": _live_nifty_chg,
            "nifty_pe": None,  # Will be populated from valuation if available
            "india_vix": None,
            "pcr": extra_signals.get("pcr"),
            "advance_decline_ratio": extra_signals.get("breadth_ratio"),
            "bull_bear_score": _ctx_rq.get("bull_bear", {}).get("normalized_score") if _ctx_rq else None,
            "fear_greed_score": None,
        }

        # Extract metrics from anchor data
        if anchor_data:
            for a in anchor_data:
                name = a.get("name", "")
                if name == "India VIX" and a.get("ok"):
                    snapshot_data["india_vix"] = a["price"]
                elif name == "CBOE VIX" and a.get("ok"):
                    snapshot_data["cboe_vix"] = a["price"]
                elif name == "USD/INR" and a.get("ok"):
                    snapshot_data["usdinr"] = a["price"]
                elif name == "Brent Crude" and a.get("ok"):
                    snapshot_data["brent"] = a["price"]
                elif name == "Gold" and a.get("ok"):
                    snapshot_data["gold"] = a["price"]
                elif name == "Dollar Index" and a.get("ok"):
                    snapshot_data["dxy"] = a["price"]
                elif name == "US 10Y Yield" and a.get("ok"):
                    snapshot_data["us_10y"] = a["price"]
                elif name == "Copper" and a.get("ok"):
                    snapshot_data["copper"] = a["price"]
                elif name == "India 10Y Yield" and a.get("ok"):
                    snapshot_data["india_10y"] = a["price"]

        # FII/DII
        from src.context_engine import get_fii_dii_context
        fii_ctx = get_fii_dii_context(days=5)
        if fii_ctx.get("ok"):
            snapshot_data["fii_net"] = fii_ctx.get("fii_net")
            snapshot_data["dii_net"] = fii_ctx.get("dii_net")

        # FII F&O net (from derivatives positioning)
        if fno_analysis and fno_analysis.get("fii"):
            snapshot_data["fii_fno_net"] = fno_analysis["fii"].get("net")

        # Compute 1D return from CSV fallback (only if live data unavailable)
        if snapshot_data.get("nifty_return_1d") is None and nifty_closes and len(nifty_closes) >= 2:
            snapshot_data["nifty_return_1d"] = round(
                ((nifty_closes[-1] / nifty_closes[-2]) - 1) * 100, 2
            )

        # Cross-asset regime (from context engine)
        try:
            ctx = getattr(format_context_block, 'last_ctx', None)
            if ctx and ctx.get("cross_asset_regime", {}).get("ok"):
                car = ctx["cross_asset_regime"]
                snapshot_data["cross_asset_regime"] = car.get("regime", "")
                snapshot_data["cross_asset_confirmation"] = car.get("confirmation_pct", 0)
                print(f"   → Cross-asset regime: {car['regime']} ({car['confirmation_pct']}% confirm)")
        except Exception as e:
            print(f"   ⚠️ Cross-asset regime: {e}")

        # Earnings regime
        try:
            from src.earnings_tracker import compute_earnings_regime
            earnings_regime = compute_earnings_regime()
            if earnings_regime.get("ok"):
                snapshot_data["earnings_regime"] = earnings_regime.get("regime", "QUIET")
                print(f"   → Earnings regime: {earnings_regime['regime']} ({earnings_regime.get('count_next_7d', 0)} in 7d)")
        except Exception as e:
            print(f"   ⚠️ Earnings regime: {e}")

        # Save snapshot
        from src.db import today_str
        snapshot_data["data_quality"] = "real"  # Phase 19: mark as real (not estimated)
        save_daily_market_snapshot(today_str(), snapshot_data)
        print(f"   → Snapshot saved for {today_str()}")

        # Get historical snapshots (252 days = 1 year)
        hist_snapshots = get_daily_market_snapshots(days=252)
        print(f"   → Historical snapshots: {len(hist_snapshots)}")

        # Run rolling quant engine
        rolling_data = run_rolling_quant_engine(snapshot_data, hist_snapshots)
        rolling_quant_block = format_rolling_quant_block(rolling_data)
        if rolling_quant_block:
            print(f"   → Rolling quant: {len(rolling_quant_block)} chars")
    except Exception as e:
        print(f"   ⚠️ Rolling quant: {e}")
        import traceback
        traceback.print_exc()

    # ── OPTIONS FLOW INFERENCE ──────────────────────────────────
    print("🔄 OPTIONS FLOW INFERENCE")
    options_flow_block = ""
    try:
        from src.options_engine import infer_options_flow, format_options_flow, fetch_nse_options_chain
        options_data = fetch_nse_options_chain("NIFTY")
        if options_data:
            spot = options_data[0].get("_underlying", 0) if options_data else None
            flow = infer_options_flow(options_data, spot)
            options_flow_block = format_options_flow(flow)
            if options_flow_block:
                # Append to options block
                blocks["block_5"] = blocks.get("block_5", "") + "\n\n" + options_flow_block
                print(f"   → Options flow: {len(options_flow_block)} chars")
    except Exception as e:
        print(f"   ⚠️ Options flow: {e}")

    # ── SMART THRESHOLD ALERTS ──────────────────────────────────
    # NOTE: last_ctx is always fresh — set at line ~226 (format_context_block),
    # read here at line ~512. Same function, same run. No standalone alert job exists.
    # If a standalone alert cron is added in the future, recompute context at trigger time.
    print("🔄 THRESHOLD ALERTS")
    threshold_alert_text = ""
    try:
        from src.threshold_alerts import run_threshold_check
        _ctx = getattr(format_context_block, 'last_ctx', None) or {}
        threshold_result = run_threshold_check(
            snapshot_data,
            bull_bear=_ctx.get("bull_bear"),
            fii_context=_ctx.get("fii_context"),
            macro_context=_ctx.get("macro_context"),
        )
        if threshold_result.get("has_alerts"):
            threshold_alert_text = threshold_result["alert_text"]
            print(f"   → {len(threshold_result['breaches'])} threshold breaches detected")
    except Exception as e:
        print(f"   ⚠️ Threshold alerts: {e}")

    # ── CFTC COT DATA (weekly positioning) ──────────────────────
    print("🔄 CFTC COT DATA")
    cftc_block = ""
    try:
        from src.cftc_fetcher import run_cftc_analysis
        cftc = run_cftc_analysis()
        if cftc.get("ok"):
            cftc_block = cftc["formatted"]
            print(f"   → CFTC: {len(cftc_block)} chars ({len(cftc.get('summary', {}))} contracts)")
        else:
            print("   → CFTC: no data available (endpoint may be down)")
    except Exception as e:
        print(f"   ⚠️ CFTC: {e}")

    # ── FACTOR ATTRIBUTION (momentum/value/quality/size) ─────────
    print("🔄 FACTOR ATTRIBUTION")
    factor_block = ""
    try:
        from src.factor_engine import run_factor_analysis
        from src.csv_data import get_nifty_close_series
        nifty_hist_data = None
        try:
            nifty_hist = get_nifty_close_series(days=252)
            nifty_hist_data = nifty_hist.tolist() if len(nifty_hist) > 0 else None
        except Exception:
            pass

        factor = run_factor_analysis(snapshot_data, nifty_hist_data)
        if factor.get("ok"):
            factor_block = factor["formatted"]
            print(f"   → Factors: {factor['attribution']['dominant']}")
        else:
            print("   → Factor attribution: insufficient data")
    except Exception as e:
        print(f"   ⚠️ Factor attribution: {e}")

    # ── SECTOR RS (relative strength vs Nifty) ──────────────────
    print("🔄 SECTOR RS")
    sector_rs_block = ""
    try:
        from src.sector_rs import run_sector_rs_analysis
        sector_rs = run_sector_rs_analysis()
        if sector_rs.get("ok"):
            sector_rs_block = sector_rs["formatted"]
            print(f"   → Sector RS: {len(sector_rs['sectors'])} sectors ranked")
        else:
            print(f"   → Sector RS: {sector_rs.get('message', 'no data')}")
    except Exception as e:
        print(f"   ⚠️ Sector RS: {e}")

    # ── EARNINGS CALENDAR (upcoming Nifty 50 earnings) ──────────
    print("🔄 EARNINGS CALENDAR")
    earnings_block = ""
    try:
        from src.earnings_tracker import run_earnings_analysis, format_earnings
        earnings = run_earnings_analysis(upcoming_limit=5)
        if earnings.get("ok"):
            earnings_block = format_earnings(earnings)
            print(f"   → Earnings: {len(earnings.get('upcoming', []))} stocks with upcoming earnings")
        else:
            print(f"   → Earnings: {earnings.get('message', 'no data')}")
    except Exception as e:
        print(f"   ⚠️ Earnings: {e}")

    # ── MARKET INTERNALS (composite health score) ────────────────
    print("🔄 MARKET INTERNALS")
    internals_block = ""
    try:
        from src.market_internals import run_internals_analysis
        # Use breadth data from block_1
        breadth_data = {}
        if breadth:
            breadth_data = breadth
        # Add MA breadth if available
        if nifty_closes:
            # Simple approximation: % above MAs
            if len(nifty_closes) >= 20:
                pct_20ma = sum(1 for i in range(-20, 0) if nifty_closes[i] > statistics.mean(nifty_closes[-20:])) / 20 * 100
                breadth_data["pct_above_20ma"] = pct_20ma
            if len(nifty_closes) >= 50:
                pct_50ma = sum(1 for i in range(-50, 0) if nifty_closes[i] > statistics.mean(nifty_closes[-50:])) / 50 * 100
                breadth_data["pct_above_50ma"] = pct_50ma
            if len(nifty_closes) >= 200:
                pct_200ma = sum(1 for i in range(-200, 0) if nifty_closes[i] > statistics.mean(nifty_closes[-200:])) / 200 * 100
                breadth_data["pct_above_200ma"] = pct_200ma
        if breadth_data:
            internals = run_internals_analysis(breadth_data, nifty_closes)
            if internals.get("ok"):
                internals_block = internals["formatted"]
                print(f"   → Internals: {internals['composite']['composite_score']}/100")
            else:
                print(f"   → Internals: {internals.get('message', 'no data')}")
    except Exception as e:
        print(f"   ⚠️ Internals: {e}")

    # ── BETA TRACKER (cross-asset betas) ────────────────────────
    print("🔄 BETA TRACKER")
    beta_block = ""
    try:
        from src.beta_tracker import compute_all_betas, format_betas
        if hist_snapshots and len(hist_snapshots) >= 90:
            betas = compute_all_betas(hist_snapshots)
            if betas.get("ok"):
                beta_block = format_betas(betas)
                print(f"   → Betas: {len(betas.get('betas', {}))} assets")
        else:
            print(f"   → Betas: {len(hist_snapshots or [])} snapshots (need 90+)")
    except Exception as e:
        print(f"   ⚠️ Betas: {e}")

    # ── VOLATILITY PERSISTENCE (VIX regime duration) ─────────────
    print("🔄 VOL PERSISTENCE")
    vol_persist_block = ""
    try:
        from src.vol_persistence import compute_regime_persistence, format_vol_persistence
        if hist_snapshots and len(hist_snapshots) >= 30:
            vol_persist = compute_regime_persistence(hist_snapshots)
            if vol_persist.get("ok"):
                vol_persist_block = format_vol_persistence(vol_persist)
                print(f"   → VIX: {vol_persist['current_regime']} for {vol_persist['current_streak_days']}d")
    except Exception as e:
        print(f"   ⚠️ Vol persistence: {e}")

    # ── REVERSAL PATTERNS (statistical price patterns) ───────────
    print("🔄 REVERSAL PATTERNS")
    reversal_block = ""
    try:
        from src.reversal_patterns import detect_all_patterns, format_patterns
        if nifty_closes and len(nifty_closes) >= 25:
            patterns = detect_all_patterns(nifty_closes)
            if patterns.get("ok") and patterns.get("count", 0) > 0:
                reversal_block = format_patterns(patterns)
                print(f"   → Patterns: {patterns['count']} detected")
    except Exception as e:
        print(f"   ⚠️ Reversal patterns: {e}")

    # ── FII CROSS-REFERENCE (cash × derivatives) ────────────────
    print("🔄 FII CROSS-REFERENCE")
    fii_xref_block = ""
    try:
        from src.fii_cross_reference import cross_reference_fii, format_fii_cross_reference
        fii_net_val = snapshot_data.get("fii_net")
        pcr_val = snapshot_data.get("pcr")
        fno_net_val = fno_analysis.get("fii", {}).get("net") if fno_analysis else None
        if fii_net_val is not None:
            fii_xref = cross_reference_fii(fii_net=fii_net_val, fno_net=fno_net_val, pcr=pcr_val)
            fii_xref_block = format_fii_cross_reference(fii_xref)
            print(f"   → FII: {fii_xref['signal']} ({fii_xref['direction']})")
    except Exception as e:
        print(f"   ⚠️ FII cross-ref: {e}")

    # ── TEMPORAL CONTEXT (duration/direction) ────────────────────
    print("🔄 TEMPORAL CONTEXT")
    temporal_block = ""
    try:
        from src.temporal_context import compute_temporal_context, format_temporal_context
        if hist_snapshots and len(hist_snapshots) >= 10:
            temporal = compute_temporal_context(hist_snapshots)
            if temporal.get("ok"):
                temporal_block = format_temporal_context(temporal)
                print(f"   → Temporal: {len(temporal['metrics'])} metrics tracked")
    except Exception as e:
        print(f"   ⚠️ Temporal: {e}")

    # ── CONFIDENCE ENGINE (uncertainty quantification) ───────────
    print("🔄 CONFIDENCE ENGINE")
    confidence_block = ""
    try:
        from src.confidence_engine import compute_confidence, compute_confidence_interval, format_confidence
        arb_data = locals().get("arbitration", {}).get("arbitration", {}) if "arbitration" in dir() else {}
        scenario_data = locals().get("rolling_data", {}).get("scenario", {}) if "rolling_data" in dir() else {}
        confidence = compute_confidence(
            arbitration=arb_data if arb_data else None,
            scenario=scenario_data if scenario_data else None,
            active_signals=len(arb_data.get("normalized", {})) if arb_data else 0,
        )
        ci = compute_confidence_interval(scenario_data) if scenario_data else None
        confidence_block = format_confidence(confidence, ci)
        print(f"   → Confidence: {confidence['confidence_score']}/100 ({confidence['level']})")
    except Exception as e:
        print(f"   ⚠️ Confidence: {e}")

    # ── SIMPLICITY ENGINE (human-readable one-liners) ────────────
    print("🔄 SIMPLICITY ENGINE")
    simple_block = ""
    try:
        from src.simplicity_engine import generate_simple_lines, format_simple_block
        arb_data_for_simple = locals().get("arbitration", {})
        temporal_data_for_simple = locals().get("temporal", {})
        conf_data_for_simple = locals().get("confidence", {})

        # Extract brent data for oil signal
        brent_price_simple = None
        brent_change_simple = None
        brent_pct_simple = None
        for a in (anchor_data or []):
            if a.get("symbol") == "BZ=F" and a.get("ok"):
                brent_price_simple = a.get("price")
                brent_change_simple = a.get("change_pct")
                break
        # Get brent percentile if available
        try:
            from src.formatters import get_percentile_value
            if brent_price_simple:
                brent_pct_simple = get_percentile_value("brent", brent_price_simple, "1Y")
        except Exception:
            pass

        simple_lines = generate_simple_lines(
            arbitration=arb_data_for_simple.get("arbitration", {}) if arb_data_for_simple else None,
            temporal=temporal_data_for_simple,
            internals_score=internals.get("composite", {}).get("composite_score") if 'internals' in dir() and internals else None,
            factor_dominant=factor.get("attribution", {}).get("dominant") if 'factor' in dir() and factor else None,
            confidence_score=conf_data_for_simple.get("confidence_score") if conf_data_for_simple else None,
            pcr=snapshot_data.get("pcr"),
            vix_regime=vol_persist.get("current_regime") if 'vol_persist' in dir() and vol_persist else None,
            vix_streak=vol_persist.get("current_streak_days") if 'vol_persist' in dir() and vol_persist else None,
            vix_avg_duration=vol_persist.get("avg_historical_duration") if 'vol_persist' in dir() and vol_persist else None,
            brent_price=brent_price_simple,
            brent_change_pct=brent_change_simple,
            brent_percentile=brent_pct_simple,
        )
        if simple_lines:
            simple_block = format_simple_block(simple_lines)
            print(f"   → Simple lines: {len(simple_lines)} generated")
            for line in simple_lines:
                print(f"      {line}")
    except Exception as e:
        print(f"   ⚠️ Simplicity: {e}")

    # ── SOURCE HEALTH CHECK ──────────────────────────────────────
    print("🔄 SOURCE HEALTH CHECK")
    source_health = {}
    try:
        # Check which blocks have content (non-empty)
        block_checks = {
            "Global Indices": bool(blocks.get("block_1", "").strip()),
            "Macro Anchors": bool(blocks.get("block_2", "").strip()),
            "Sector FPI": bool(blocks.get("block_3", "").strip()),
            "FII/DII Flows": bool(blocks.get("block_4", "").strip()),
            "Options": bool(blocks.get("block_5", "").strip()),
            "News": bool(blocks.get("block_6", "").strip()),
            "Insider": bool(blocks.get("block_7", "").strip()),
            "Watchlist": bool(blocks.get("block_8", "").strip()),
            "Calendar": bool(blocks.get("block_9", "").strip()),
        }
        # Check critical data objects (use locals().get for safety)
        _anchor = locals().get("anchor_data")
        _fii_ctx = locals().get("fii_ctx")
        data_checks = {
            "Breadth": breadth is not None,
            "Anchor Data": _anchor is not None and len(_anchor) > 0,
            "FII Context": _fii_ctx is not None,
        }
        source_health = {**block_checks, **data_checks}
        failed = [k for k, v in source_health.items() if not v]
        if failed:
            print(f"   ⚠️ Sources missing: {', '.join(failed)}")
        else:
            print(f"   ✅ All sources healthy")
    except Exception as e:
        print(f"   ⚠️ Health check: {e}")

    # Build health block for AI prompt
    staleness_block = ""
    try:
        failed_sources = [k for k, v in source_health.items() if not v]
        if failed_sources:
            lines = ["[Data Source Status]"]
            for src in failed_sources:
                lines.append(f"  ⚠️ {src}: data unavailable — analysis may be incomplete")
            lines.append(f"  {len(failed_sources)} source(s) missing. Context based on available data only.")
            staleness_block = "\n".join(lines)
            print(f"   → Health: {len(failed_sources)} sources missing")
    except Exception as e:
        print(f"   ⚠️ Health block: {e}")

    # ── FEAR & GREED INDEX (from quant_enrichment) ───────────────
    print("🔄 FEAR & GREED INDEX")
    fear_greed_block = ""
    fear_greed = None
    try:
        from src.quant_enrichment import compute_fear_greed_index
        fg_data = {}
        if snapshot_data.get("india_vix"):
            fg_data["vix"] = snapshot_data["india_vix"]
        if snapshot_data.get("pcr"):
            fg_data["pcr"] = snapshot_data["pcr"]
        if snapshot_data.get("advance_decline_ratio"):
            fg_data["breadth_ratio"] = snapshot_data["advance_decline_ratio"]
        if snapshot_data.get("bull_bear_score"):
            # bull_bear_score used separately in regime card, not in Fear/Greed
            pass
        if nifty_closes and len(nifty_closes) >= 252:
            fg_data["momentum_12m"] = ((nifty_closes[-1] / nifty_closes[-252]) - 1) * 100
        fear_greed = compute_fear_greed_index(**fg_data)
        fg_score = fear_greed.get("score") or fear_greed.get("index")  # handle both key names
        if fg_score is not None:
            fear_greed_block = f"\n[Fear & Greed Index: {fg_score}/100 — {fear_greed.get('label', 'NEUTRAL')}]"
            print(f"   → Fear/Greed: {fg_score}/100 ({fear_greed.get('label')})")
    except Exception as e:
        print(f"   ⚠️ Fear/Greed: {e}")

    # ── UNIFIED REGIME CARD (replaces Dashboard + Master Signal) ──
    regime_card_text = ""
    try:
        from src.context_engine import compute_market_phase
        from src.state import MarketState
        from src.delta import compute_delta
        from src.delta_renderer import render_regime_card
        from src.db import get_latest_market_state
        from datetime import datetime

        # Get context from format_context_block
        ctx = getattr(format_context_block, 'last_ctx', None) or {}

        # Get institutional signals
        inst_signals = {}
        try:
            from src.quant_enrichment import (
                compute_sector_regime, compute_volatility_setup,
                compute_risk_appetite, compute_breadth_thrust,
                compute_fii_institutional_footprint
            )
            # Sector regime from top movers
            try:
                from src.data_fetcher import fetch_top_movers
                _movers = fetch_top_movers(top_n=10)
                _sector_perf = {}
                for m in (_movers.get("india", {}).get("gainers", []) + _movers.get("india", {}).get("losers", [])):
                    sym = m.get("symbol", "")
                    if sym in ("HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK"):
                        _sector_perf.setdefault("BANK", []).append(m.get("weekly_pct", m.get("change_pct", 0)))
                    elif sym in ("TATAMOTORS", "M&M", "MARUTI"):
                        _sector_perf.setdefault("AUTO", []).append(m.get("weekly_pct", m.get("change_pct", 0)))
                    elif sym in ("TCS", "INFY", "WIPRO", "TECHM"):
                        _sector_perf.setdefault("IT", []).append(m.get("weekly_pct", m.get("change_pct", 0)))
                    elif sym in ("SUNPHARMA", "DRREDDY"):
                        _sector_perf.setdefault("PHARMA", []).append(m.get("weekly_pct", m.get("change_pct", 0)))
                    elif sym in ("HINDUNILVR", "ITC"):
                        _sector_perf.setdefault("FMCG", []).append(m.get("weekly_pct", m.get("change_pct", 0)))
                    elif sym in ("TATASTEEL", "JSW", "HINDALCO"):
                        _sector_perf.setdefault("METAL", []).append(m.get("weekly_pct", m.get("change_pct", 0)))
                avg_sector = {k: round(sum(v)/len(v), 2) for k, v in _sector_perf.items() if v}
                inst_signals["sector_regime"] = compute_sector_regime(avg_sector)
            except Exception:
                pass

            # Volatility setup from VIX history
            try:
                from src.db import get_macro_history
                _vix_hist = get_macro_history("India VIX", days=90)
                _vix_vals = [v.get("price", 0) for v in _vix_hist if v.get("price")]
                if _vix_vals:
                    inst_signals["volatility_setup"] = compute_volatility_setup(_vix_vals, _vix_vals[-1])
            except Exception:
                pass

            # Risk appetite from sector regime
            sr = inst_signals.get("sector_regime", {})
            if sr.get("ok"):
                _perf = {}
                for s, v in sr.get("leaders", []):
                    _perf[s] = v
                for s, v in sr.get("laggards", []):
                    _perf[s] = v
                inst_signals["risk_appetite"] = compute_risk_appetite(_perf)

            # Breadth thrust
            try:
                from src.db import get_breadth_history
                _breadth = get_breadth_history(days=30)
                if _breadth:
                    inst_signals["breadth_thrust"] = compute_breadth_thrust(_breadth)
            except Exception:
                pass

            # FII footprint
            try:
                from src.db import get_fii_institutions
                _inst = get_fii_institutions(days=30)
                if _inst:
                    inst_signals["fii_footprint"] = compute_fii_institutional_footprint(_inst)
            except Exception:
                pass
        except Exception:
            pass

        # Earnings regime
        earnings_regime = {"ok": False}
        try:
            from src.earnings_tracker import compute_earnings_regime
            earnings_regime = compute_earnings_regime()
        except Exception:
            pass

        # Compute market phase
        market_phase = compute_market_phase(ctx, inst_signals, earnings_regime)

        # Build MarketState from current data
        today_str = datetime.now().strftime("%Y-%m-%d")
        state = MarketState(trade_date=today_str)
        bb = ctx.get("bull_bear", {})
        if bb.get("score") is not None:
            state.bull_bear_score = bb["score"]
        if bb.get("normalized") is not None:
            state.bull_bear_normalized = bb["normalized"]
        state.market_phase = market_phase.get("phase")
        state.cross_asset_regime = ctx.get("global_risk", {}).get("risk_mood")

        # Populate macro
        macro = ctx.get("macro_context", {})
        if macro.get("vix_price") is not None:
            state.macro.vix = macro["vix_price"]
        if macro.get("vix_regime"):
            state.macro.vix_regime = macro["vix_regime"]
        if macro.get("brent"):
            state.macro.brent = macro["brent"]
        if macro.get("usdinr"):
            state.macro.usdinr = macro["usdinr"]

        # Populate flows
        fii_ctx_val = ctx.get("fii_context", {})
        if fii_ctx_val.get("ok"):
            state.flows.fii_net = fii_ctx_val.get("fii_net")
            state.flows.dii_net = fii_ctx_val.get("dii_net")
            state.flows.absorption_ratio = fii_ctx_val.get("absorption_ratio")

        # Populate derivatives
        opt = ctx.get("options_context", {})
        if snapshot_data.get("pcr") is not None:
            state.derivatives.pcr = snapshot_data["pcr"]

        # ── Call regime arbiter — single source of truth ────────────
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
            save_market_state(datetime.now().strftime("%Y-%m-%d"), state)
        except Exception as e:
            print(f"   ⚠️ Regime arbiter (regime card): {e}")

        # Get previous state for delta
        prev_state_data = get_latest_market_state()
        prev_state = None
        if prev_state_data:
            try:
                prev_state = MarketState.model_validate(prev_state_data)
            except Exception:
                pass

        delta = compute_delta(state, prev_state)

        # Key levels
        key_levels = {}
        if snapshot_data.get("nifty_close"):
            key_levels["spot"] = snapshot_data["nifty_close"]
        try:
            from src.technical_analysis import compute_support_resistance
            ta = compute_support_resistance()
            if ta:
                key_levels["support"] = ta.get("support_1")
                key_levels["resistance"] = ta.get("resistance_1")
        except Exception:
            pass

        job_time_str = "07:00" if mode == "morning" else "18:00"
        regime_card_text = render_regime_card(state, delta, job_time=job_time_str, key_levels=key_levels)
        if regime_card_text:
            print(f"   → Regime card: {state.final_regime or market_phase['phase']} (arbiter={state.final_regime is not None})")
    except Exception as e:
        print(f"   ⚠️ Regime card: {e}")
        import traceback
        traceback.print_exc()

    # ── SIGNAL ARBITRATION (master signal synthesis) ─────────────
    print("🔄 SIGNAL ARBITRATION")
    master_signal_block = ""
    try:
        from src.signal_arbitrator import run_arbitration, format_master_signal
        from src.prediction_tracker import get_dynamic_signal_weights

        # Collect all signals for arbitration
        arb_signals = {}
        if snapshot_data.get("bull_bear_score") is not None:
            arb_signals["bull_bear"] = snapshot_data["bull_bear_score"]
        if fear_greed:
            fg_val = fear_greed.get("score") or fear_greed.get("index")
            if fg_val is not None:
                arb_signals["fear_greed"] = fg_val
        if snapshot_data.get("pcr") is not None:
            arb_signals["pcr"] = snapshot_data["pcr"]
        if snapshot_data.get("india_vix") is not None:
            arb_signals["vix"] = snapshot_data["india_vix"]
        # Wire internals if available
        if snapshot_data.get("internals_score") is not None:
            arb_signals["internals"] = snapshot_data["internals_score"]
        # Get signal weights for dynamic weighting
        weights = get_dynamic_signal_weights(days=90)

        if arb_signals:
            # Query historical scores for trending (Phase 19)
            historical_scores = []
            try:
                from src.db import get_daily_market_snapshots
                hist = get_daily_market_snapshots(days=252)
                historical_scores = [
                    {"date": s.get("date"), "bull_bear_score": s.get("bull_bear_score"),
                     "structural_score": s.get("structural_score"),
                     "sentiment_score": s.get("sentiment_score"),
                     "data_quality": s.get("data_quality", "real")}
                    for s in hist if s.get("bull_bear_score") is not None
                ]
            except Exception:
                pass

            # Get nifty percentile for accumulation/distribution detection
            nifty_pct_arb = None
            try:
                from src.formatters import get_percentile_value
                if snapshot_data.get("nifty_close"):
                    nifty_pct_arb = get_percentile_value("nifty_close", snapshot_data["nifty_close"], "1Y")
            except Exception:
                pass

            arbitration = run_arbitration(arb_signals, weights, historical_scores=historical_scores, nifty_percentile=nifty_pct_arb)
            if arbitration.get("ok"):
                master_signal_block = arbitration["formatted"]
                art = arbitration["arbitration"]
                print(f"   → Master: {art['master_score']}/100 ({art['master_label']})")
                print(f"   → Contradiction: {art['contradiction_level']}, Confidence: {art['confidence']}")

                # Persist cluster scores to snapshot (Phase 19)
                snapshot_data["structural_score"] = art.get("structural_score")
                snapshot_data["sentiment_score"] = art.get("sentiment_score")
                snapshot_data["cluster_gap"] = art.get("spread")
                # Re-save with cluster scores
                try:
                    save_daily_market_snapshot(today_str(), snapshot_data)
                except Exception:
                    pass
    except Exception as e:
        print(f"   ⚠️ Arbitration: {e}")

    # ── Assemble prompt ───────────────────────────────────────────
    print("🔄 Assembling prompt...")

    # Compositional: fill blocks, strip empty ones — no regex surgery
    prompt = master_template
    block_headers = {
        "block_0": "[BLOCK 0: MARKET POSTURE — READ FIRST]",
        "block_1": "[BLOCK 1: GLOBAL INDICES]",
        "block_2": "[BLOCK 2: MACRO ANCHORS (USDINR, BRENT, GOLD)]",
        "block_3": "[BLOCK 3: SECTOR PERFORMANCE]",
        "block_4": "[BLOCK 4: FLOW INTELLIGENCE (FII/DII)]",
        "block_5": "[BLOCK 5: DERIVATIVES (PCR + MAX PAIN)]",
        "block_6": "[BLOCK 6: NEWS INTELLIGENCE — USE ONLY TRUST ≥ 6]",
        "block_7": "[BLOCK 7: INSIDER ACTIVITY]",
        "block_8": "[BLOCK 8: WATCHLIST — price, day_change%, volume_spike, MA20, 5D momentum, 1M return]",
        "block_9": "[BLOCK 9: MACRO CALENDAR (NEXT 7 DAYS)]",
        "block_10": "[BLOCK 10: MF FLOW INTELLIGENCE — category flows, anomaly vs 3M avg, thematic, top 5 gainers/losers, SIP trend]",
    }

    for key, content in blocks.items():
        placeholder = f"{{{key}}}"
        header = block_headers.get(key, f"[{key.upper()}]")

        if content.strip():
            prompt = prompt.replace(placeholder, content)
        else:
            # Remove placeholder and its header line — empty blocks excluded from prompt
            prompt = prompt.replace(f"{header}\n{placeholder}", "")
            prompt = prompt.replace(f"{header}\n{{{placeholder}}}", "")
            prompt = prompt.replace(placeholder, "")

    # Count non-empty blocks
    non_empty = sum(1 for v in blocks.values() if v.strip())
    print(f"   → {non_empty} blocks with data")

    # Count remaining placeholders
    remaining = prompt.count("{block_")
    print(f"   → {remaining} unfilled placeholders")

    # ── INJECT ROLLING QUANT BLOCK ──────────────────────────────
    if rolling_quant_block:
        prompt += "\n\n" + rolling_quant_block

    # ── INJECT THRESHOLD ALERTS ─────────────────────────────────
    if threshold_alert_text:
        prompt += "\n\n" + threshold_alert_text

    # ── INJECT CFTC COT DATA ────────────────────────────────────
    if cftc_block:
        prompt += "\n\n" + cftc_block

    # ── INJECT FACTOR ATTRIBUTION ───────────────────────────────
    if factor_block:
        prompt += "\n\n" + factor_block

    # ── INJECT SECTOR RS ────────────────────────────────────────
    if sector_rs_block:
        prompt += "\n\n" + sector_rs_block

    # ── INJECT EARNINGS CALENDAR ────────────────────────────────
    if earnings_block:
        prompt += "\n\n" + earnings_block

    # ── INJECT MARKET INTERNALS ─────────────────────────────────
    if internals_block:
        prompt += "\n\n" + internals_block

    # ── INJECT BETA TRACKER ─────────────────────────────────────
    if beta_block:
        prompt += "\n\n" + beta_block

    # ── INJECT VOL PERSISTENCE ──────────────────────────────────
    if vol_persist_block:
        prompt += "\n\n" + vol_persist_block

    # ── INJECT REVERSAL PATTERNS ────────────────────────────────
    if reversal_block:
        prompt += "\n\n" + reversal_block

    # ── INJECT FII CROSS-REFERENCE ──────────────────────────────
    if fii_xref_block:
        prompt += "\n\n" + fii_xref_block

    # ── INJECT TEMPORAL CONTEXT ─────────────────────────────────
    if temporal_block:
        prompt += "\n\n" + temporal_block

    # ── INJECT MECHANISM TRIGGERS ──────────────────────────────
    if mechanism_block:
        prompt += "\n\n" + mechanism_block

    # ── INJECT CONFIDENCE ───────────────────────────────────────
    if confidence_block:
        prompt += "\n\n" + confidence_block

    # ── INJECT STALENESS ────────────────────────────────────────
    if staleness_block:
        prompt += "\n\n" + staleness_block

    # ── INJECT FEAR & GREED ─────────────────────────────────────
    if fear_greed_block:
        prompt += "\n\n" + fear_greed_block

    # ── GOOGLE SEARCH CONTEXT (live web-grounded intelligence) ───
    # Only fetched when Groq is available — preserves Google quota
    # for the primary AI call (Google is primary for "volume" tasks).
    # When Groq runs the analysis, Google context enriches the prompt.
    # When Google runs the analysis, search grounding is built into
    # the _try_google_search fallback, so no separate fetch needed.
    google_context_block = ""
    try:
        from src.ai_engine import GROQ_AVAILABLE
        from src.google_search import get_all_context
        if GROQ_AVAILABLE:
            google_context_block = get_all_context(mode=mode)
            if google_context_block:
                prompt += "\n\n" + google_context_block
    except Exception as e:
        print(f"   ⚠️ Google Search context: {e}")

    # ── INJECT REGIME CARD (replaces Dashboard + Master Signal) ───
    if regime_card_text:
        prompt = "\n\n[REGIME CARD — READ FIRST]\n" + regime_card_text + "\n\n" + prompt

    # ── INJECT MASTER SIGNAL (if regime card failed) ──────────────
    if master_signal_block and not regime_card_text:
        # Replace Block 0 with master signal as fallback
        prompt = prompt.replace("{block_0}", master_signal_block)
    try:
        from src.prediction_tracker import format_signal_weights
        if weights:
            signal_weights_block = format_signal_weights(weights)
            if signal_weights_block:
                prompt += "\n\n" + signal_weights_block
    except Exception:
        pass

    # ── INJECT SIMPLE LINES (Block -1, always first) ────────────
    if simple_block:
        prompt = simple_block + "\n\n" + prompt

    # Total failure check - more lenient
    if non_empty == 0:
        print("⚠️ All blocks empty — sending fallback")
        # Try to send a simple message anyway using available data
        try:
            # Last resort: use global indices or watchlist if available
            idx = fetch_global_indices()
            if idx:
                lines = [f"{d.get('flag','')} {c}: {d.get('change_pct',0):+.2f}%"
                         for c, d in idx.items() if d.get("ok")][:8]
                send_text(f"🌅 *MARKET SNAPSHOT*\n━━━━━━━━━━━━━━━━━━━━━━━━\n" +
                          "\n".join(lines) + "\n\n━━━━━━━━━━━━━━━━━━━━━━━━")
                return
        except:
            pass
        send_text("🚨 *Market Intel Unavailable*\n\nNo data from any source.")
        return

    # ── BLOCK VALIDATION (pre-AI quality check) ───────────────────
    try:
        from src.block_validator import validate_all_blocks, format_validation_report
        block_validation = validate_all_blocks(blocks)
        print(format_validation_report(block_validation))
    except Exception as e:
        print(f"   ⚠️ Block validation: {e}")

    # ── Budget health check before AI call ────────────────────────
    budget.end_stage("formatters")
    budget_warning = budget.check_budget_health()
    if budget_warning:
        print(f"  ⚠️ {budget_warning}")

    # ── Strong-conviction check: bypass AI if quota exhausted AND ≥2 macro extremes ──
    try:
        raw_for_extreme = {
            "anchor_data": anchor_data or [],
            "fii_data": {
                "fii_net": snapshot_data.get("fii_net"),
                "fii_streak": snapshot_data.get("fii_streak_days", 0),
            },
        }
        extreme_count, extreme_msgs = _check_extreme_conditions(raw_for_extreme)
        if extreme_count >= 2:
            ai_temp = AIEngine()
            if not ai_temp.has_quota("volume"):
                send_text(
                    "🚨 *STRONG CONVICTION OVERRIDE*\n\n"
                    "DEFENSIVE regime triggered by: "
                    f"{'; '.join(extreme_msgs)}. "
                    "No analysis available."
                )
                print(f"   → Strong-conviction override — AI bypassed ({extreme_count} extremes)")
                return
    except Exception as e:
        print(f"   ⚠️ Strong-conviction check: {e}")

    # ── AI Analysis ───────────────────────────────────────────────
    print(f"   ⏱️ Data + Quant: {_time.time()-_t0:.1f}s")
    _t0 = _time.time()
    print("🔄 Running AI analysis (volume task)...")
    try:
        ai = AIEngine()
        analysis = ai.analyze("volume", prompt)
    except Exception as e:
        print(f"   ⚠️ AI failed: {e}")
        send_text(render_deterministic_intel({
            "anchor_data": anchor_data or [],
            "fii_data": {},
            "snapshot_data": snapshot_data,
        }, mode=mode))
        return

    # ── PRE-SEND CHECKLIST (10 hard gates) ───────────────────────
    try:
        from src.block_validator import pre_send_checklist, format_checklist_report
        checklist = pre_send_checklist(blocks, snapshot_data, analysis)
        print(format_checklist_report(checklist))
    except Exception as e:
        print(f"   ⚠️ Pre-send checklist: {e}")

    # ── OUTPUT VALIDATION (pre-send consistency check with retry) ──
    print("🔄 VALIDATING OUTPUT")
    try:
        from src.output_validator import validate_output
        from src.validation_helper import _validate_with_output_type, _OUTPUT_TYPE_CONFIG, _build_retry_instruction

        # Build ground truth from all available data
        _fii_net = snapshot_data.get("fii_net", 0) or 0
        _dii_net = snapshot_data.get("dii_net", 0) or 0
        _absorption_pct = None
        if _fii_net < 0 and _dii_net > 0:
            _absorption_pct = (_dii_net / abs(_fii_net)) * 100

        _vix_pct = None
        try:
            from src.formatters import get_percentile_value
            _vix_val = snapshot_data.get("india_vix")
            if _vix_val:
                _vix_pct = get_percentile_value("india_vix", _vix_val, "1Y")
        except Exception:
            pass

        ground_truth = {
            "bull_bear_score": snapshot_data.get("bull_bear_score"),
            "fii_net": _fii_net,
            "dii_net": _dii_net,
            "nifty_close": snapshot_data.get("nifty_close"),
            "pcr": snapshot_data.get("pcr"),
            "india_vix": snapshot_data.get("india_vix"),
            "vix_percentile": _vix_pct,
            "brent": snapshot_data.get("brent"),
            "gold": snapshot_data.get("gold"),
            "usdinr": snapshot_data.get("usdinr"),
            "cross_asset_regime": snapshot_data.get("cross_asset_regime"),
            "absorption_pct": _absorption_pct,
        }

        # Run validation with output-type scoping (Phase 23: universal validator)
        config = _OUTPUT_TYPE_CONFIG.get("market_intel", _OUTPUT_TYPE_CONFIG["market_close"])
        result = _validate_with_output_type(analysis, ground_truth, config)

        if result["send"]:
            print(f"   ✅ Output validated: {result['reason']}")
        else:
            # MAJOR contradiction — attempt targeted retry
            print(f"   ⚠️ OUTPUT REJECTED: {result['reason']}")
            for issue in result["issues"]:
                print(f"      → {issue}")

            retry_instruction = result.get("retry_instruction", "")
            if retry_instruction and len(analysis.split()) >= 50:
                print(f"   🔄 Retrying with targeted correction...")
                retry_prompt = (
                    f"Rewrite your previous Market Intel output. Your response contained these errors:\n"
                    f"{retry_instruction}\n\n"
                    f"Original context:\n{prompt[:3000]}"
                )
                try:
                    retry_analysis = ai.analyze("volume", retry_prompt)
                    if retry_analysis and len(retry_analysis.split()) >= 50:
                        retry_result = _validate_with_output_type(retry_analysis, ground_truth, config)
                        if retry_result["send"]:
                            print(f"   ✅ Retry passed — using corrected output")
                            analysis = retry_analysis
                        else:
                            print(f"   ⚠️ Retry also rejected — using fallback")
                            analysis = retry_result.get("fallback_text") or analysis
                    else:
                        print(f"   ⚠️ Retry output too short — using fallback")
                        analysis = result.get("fallback_text") or analysis
                except Exception as e:
                    print(f"   ⚠️ Retry AI failed: {e}")
                    analysis = result.get("fallback_text") or analysis
    except Exception as e:
        print(f"   ⚠️ Validation: {e}")

    # ── Store Prediction for Accuracy Tracking ───────────────────
    print(f"   ⏱️ AI Analysis: {_time.time()-_t0:.1f}s")
    try:
        from src.prediction_tracker import parse_and_store_prediction
        nifty_close_for_pred = None
        try:
            import yfinance as yf
            nifty_hist = yf.Ticker("^NSEI").history(period="2d")["Close"].dropna()
            if len(nifty_hist) >= 1:
                nifty_close_for_pred = float(nifty_hist.iloc[-1])
        except Exception:
            pass
        if nifty_close_for_pred:
            parse_and_store_prediction(analysis, nifty_close_for_pred, run_type=mode)
    except Exception as e:
        print(f"   ⚠️ Prediction tracking: {e}")

    # ── Historical Clone Engine (T4.2 / G3) ──────────────────────────
    clone_blocks: list[str] = []
    try:
        from src.clone_engine import find_clones, find_global_clones, format_clone_block, format_global_clone_block, get_current_fii_5d, save_clones
        from src.state import MarketState
        _macro_v = getattr(state, 'macro', None)
        _deriv_v = getattr(state, 'derivatives', None)

        # India Clone (T4.2)
        if all([
            getattr(_macro_v, 'vix', None),
            getattr(_macro_v, 'usdinr', None),
            getattr(_macro_v, 'brent', None),
            getattr(_macro_v, 'dxy', None),
        ]):
            _fii_5d = get_current_fii_5d() or getattr(getattr(state, 'flow_metrics', None), 'fii_5d_total', None)
            _pcr = getattr(_deriv_v, 'pcr', None)
            _clone_data = find_clones(
                current_vix=_macro_v.vix,
                current_usdinr=_macro_v.usdinr,
                current_brent=_macro_v.brent,
                current_dxy=_macro_v.dxy,
                current_fii_5d=_fii_5d,
                current_pcr=_pcr,
            )
            if _clone_data.get("status") == "ok":
                _scenarios = getattr(state, 'active_scenarios', None)
                _cb = format_clone_block(_clone_data, active_scenarios=_scenarios)
                if _cb:
                    clone_blocks.append(_cb)
                try:
                    save_clones(datetime.now().strftime("%Y-%m-%d"), _clone_data)
                except Exception:
                    pass

        # Global Clone (G3)
        if all([
            getattr(_macro_v, 'dxy', None),
            getattr(_macro_v, 'us_10y', None),
            getattr(_macro_v, 'hyg', None),
            getattr(_macro_v, 'gold', None),
            getattr(_macro_v, 'copper', None),
            getattr(_macro_v, 'usd_jpy', None),
        ]):
            _global_data = find_global_clones(
                current_dxy=_macro_v.dxy,
                current_us_10y=_macro_v.us_10y,
                current_hyg=_macro_v.hyg,
                current_gold=_macro_v.gold,
                current_copper=_macro_v.copper,
                current_usdjpy=_macro_v.usd_jpy,
            )
            if _global_data.get("status") == "ok":
                _gb = format_global_clone_block(_global_data)
                if _gb:
                    clone_blocks.append(_gb)

        clone_block = "\n\n".join(clone_blocks) if clone_blocks else ""
    except Exception as e:
        print(f"   ⚠️ Clone engine: {e}")
        clone_block = ""

    # ── Pillar Block (inject before clone block) ────────────────
    pillar_block = ""
    try:
        from src.pillar_classifier import get_percentiles_from_csv, classify_pillars, format_pillar_output
        _pctiles = get_percentiles_from_csv()
        if _pctiles:
            _pillars = classify_pillars(_pctiles)
            if _pillars:
                pillar_block = format_pillar_output(_pillars, max_pillars=2)
    except Exception as e:
        print(f"   ⚠️ Pillar block: {e}")

    # ── Fragility Index banner (replaces old Stress Index) ──────
    fragility_banner = ""
    try:
        from src.fragility_index import compute_fragility_index, format_fragility_banner
        from src.stress_index import compute_stress_index
        stress = compute_stress_index()
        _pctiles = _pctiles if '_pctiles' in dir() else None
        _pillars = _pillars if '_pillars' in dir() else None
        if stress.get("ok"):
            from src.pillar_classifier import get_percentiles_from_csv, classify_pillars
            if not _pctiles:
                _pctiles = get_percentiles_from_csv()
            if _pctiles and not _pillars:
                _pillars = classify_pillars(_pctiles)
            if _pillars:
                fragility = compute_fragility_index(stress["stress_score"], _pillars)
            else:
                fragility = compute_fragility_index(stress["stress_score"], [])
            if fragility.get("ok"):
                fragility_banner = format_fragility_banner(fragility)
                state.fragility_score = fragility["fragility_score"]
                state.fragility_components = fragility.get("components", {})
    except Exception as e:
        print(f"   ⚠️ Fragility banner: {e}")

    # ── Send Telegram ───────────────────────────────────────────
    # Validate AI response - never send blank
    if validate_ai_response(analysis, min_words=50):
        bluf = _build_market_intel_bluf(snapshot_data)
        header = "*MARKET INTEL ({mode})*".format(mode=mode.upper())
        msg = ""
        if fragility_banner:
            msg += fragility_banner + "\n"
        if pillar_block:
            msg += pillar_block + "\n\n"
        if clone_block:
            msg += clone_block + "\n"
        msg += header + "\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        if bluf:
            msg += bluf + "\n\n"
        msg += analysis + "\n\n━━━━━━━━━━━━━━━━━━━━━━━━"
        send_text(msg)
        print("✅ Market Intel sent")
        if mode == "morning":
            try:
                _save_morning_fingerprint(snapshot_data, state)
            except NameError:
                print("   ⚠️ Morning fingerprint: state unavailable")
    else:
        # Fallback: AI failed — check if regime changed since morning card
        from src.db import get_market_state
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        persisted = get_market_state(today)
        current_regime = persisted.get("final_regime") if persisted else None
        mode_label = "MORNING" if mode == "morning" else "EVENING"

        # Check VIX for significant movement
        vix_moved = False
        if persisted and persisted.get("macro", {}).get("vix"):
            prev_vix = persisted["macro"]["vix"]
            for a in (anchor_data or []):
                if a.get("name") == "India VIX" and a.get("ok") and a.get("price") and prev_vix > 0:
                    if abs(a["price"] - prev_vix) / prev_vix >= 0.10:
                        vix_moved = True
                    break

        # Use fragility score for compression gate
        fragility_score_for_gate = getattr(state, "fragility_score", None) or 50
        fragility_extreme = fragility_score_for_gate >= 80
        if current_regime and not vix_moved and not fragility_extreme:
            # Regime unchanged, VIX stable → compress to one-liner with key context
            override = persisted.get("final_override_reason", "") if persisted else ""
            macro_data = persisted.get("macro", {}) if persisted else {}
            usdinr_val = macro_data.get("usdinr", "")
            brent_val = macro_data.get("brent", "")
            vix_val = macro_data.get("vix", "")
            triggers = []
            if usdinr_val:
                triggers.append(f"USDINR ₹{usdinr_val}")
            if brent_val:
                triggers.append(f"Brent ${brent_val}")
            if vix_val:
                triggers.append(f"VIX {vix_val}")
            trigger_str = ", ".join(triggers[:3])
            compressed = (
                f"📌 *{mode_label} INTEL CHECK:* "
                f"{current_regime}".lower().title()
            )
            if fragility_banner:
                compressed = fragility_banner + "\n" + compressed
            if trigger_str:
                compressed += f" | {trigger_str}"
            # Check for high-impact calendar events
            try:
                from src.economic_calendar import get_high_impact_soon
                hi = get_high_impact_soon(days=2)
                if hi:
                    compressed += f" | ⚠️ {hi}"
                else:
                    compressed += f" | No new catalyst."
            except Exception:
                compressed += f" | No new catalyst."
            send_text(compressed)
            print(f"   → Intel compressed to one-liner — regime unchanged, no delta")
        else:
            # Regime changed or VIX moved → send full deterministic fallback
            ctx_for_fallback = getattr(format_context_block, 'last_ctx', None) or {}
            fii_dii = ctx_for_fallback.get("fii_context", {})
            fii_data = {
                "fii_net": fii_dii.get("fii_net"),
                "dii_net": fii_dii.get("dii_net"),
                "fii_streak": fii_dii.get("fii_streak", 0),
            } if fii_dii.get("ok") else {}
            fallback = render_deterministic_intel({
                "index_data": index_data,
                "fii_data": fii_data,
                "anchor_data": anchor_data,
                "validated_news": (global_validated or []) + (indian_validated or []),
                "movers": movers,
                "snapshot_data": snapshot_data,
            }, mode=mode)
            if fragility_banner:
                fallback = fragility_banner + "\n" + fallback
            if pillar_block:
                fallback = pillar_block + "\n\n" + fallback
            if clone_block:
                fallback += "\n" + clone_block
            send_text(fallback)
            print("⚠️ AI response too short - sent fallback")

    # ── Execution time summary ──────────────────────────────────
    total_time = _time.time() - _job_start
    budget_status = budget.get_status()
    print(f"\n⏱️ Total execution: {total_time:.1f}s ({total_time/60:.1f}min) | Budget: {budget_status['pct_used']:.0f}%")
    if budget_status["stage_times"]:
        for stage, t in budget_status["stage_times"].items():
            if isinstance(t, (int, float)):
                print(f"   {stage}: {t:.1f}s")
    if total_time > 240:
        print(f"⚠️ EXCEEDED 4-MIN LIMIT — consider splitting into separate jobs")


if __name__ == "__main__":
    main()