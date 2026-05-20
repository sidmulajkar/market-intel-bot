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
from src.formatters     import format_global_indices, format_macro_anchors, format_flows, format_news, format_watchlist, format_mf_flows, format_context_block, format_options_block, format_insider_activity
from src.context_engine import run_contextualization
from src.ai_engine      import AIEngine
from src.telegram_sender import send_text
from src.db             import get_client, save_macro_snapshots_batch
from src.validator      import validate_articles



# AI Response Validation
def validate_ai_response(response: str, min_words: int = 50) -> bool:
    if not response or not isinstance(response, str):
        return False
    return len(response.split()) >= min_words


def get_market_intel_fallback(blocks: dict) -> str:
    lines = ["📊 *Market Intel (Fallback)*", "━━━━━━━━━━━━━━━━━━━━━━━━"]
    
    if blocks.get("block_1"):
        lines.append("\n🌍 *Global:*")
        for line in blocks["block_1"].split("\n")[:3]:
            if line.strip():
                lines.append(f"  {line}")
    
    if blocks.get("block_4"):
        lines.append("\n📈 *Flows:*")
        for line in blocks["block_4"].split("\n")[:3]:
            if line.strip():
                lines.append(f"  {line}")
    
    if blocks.get("block_6"):
        lines.append("\n📰 *News:*")
        for line in blocks["block_6"].split("\n")[:3]:
            if line.strip():
                lines.append(f"  {line}")
    
    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────
def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "morning"
    if mode not in ("morning", "evening"):
        print(f"Usage: python market_intel.py [morning|evening]")
        sys.exit(1)

    print("=" * 50)
    print(f"📊 MARKET INTEL ({mode.upper()}) STARTING")
    print("=" * 50)

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

    # ── BLOCK 2: Macro Anchors ───────────────────────────────────
    print(f"   ⏱️ Block 1: {_time.time()-_t0:.1f}s")
    _t0 = _time.time()
    print("🔄 BLOCK 2: Macro Anchors")
    try:
        anchor_data = fetch_macro_anchors()
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
        import yfinance as yf
        from src.technical_analysis import compute_full_analysis, format_technical_analysis
        nifty_hist = yf.Ticker("^NSEI").history(period="1y")["Close"].dropna()
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
                    extra_signals["pcr"] = pcr_data["pcr"]
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
        blocks["block_4"] = format_flows()
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
    print("🔄 BLOCK 7: Insider Activity")
    try:
        blocks["block_7"] = format_insider_activity()
        print(f"   → {len(blocks['block_7'])} chars")
    except Exception as e:
        print(f"   ⚠️ {e}")
        blocks["block_7"] = ""

    # ── BLOCK 9: Macro Calendar ─────────────────────────────────────
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
        print("🔄 BLOCK 10: MF Flows")
        try:
            blocks["block_10"] = format_mf_flows()
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
    try:
        from src.rolling_quant import run_rolling_quant_engine, format_rolling_quant_block
        from src.db import get_daily_market_snapshots, save_daily_market_snapshot

        # Build today's snapshot from collected data
        snapshot_data = {
            "nifty_close": nifty_closes[-1] if nifty_closes else None,
            "nifty_pe": None,  # Will be populated from valuation if available
            "india_vix": None,
            "pcr": extra_signals.get("pcr"),
            "advance_decline_ratio": extra_signals.get("breadth_ratio"),
            "bull_bear_score": ctx.get("bull_bear", {}).get("normalized_score") if ctx else None,
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

        # FII/DII
        from src.context_engine import get_fii_dii_context
        fii_ctx = get_fii_dii_context(days=5)
        if fii_ctx.get("ok"):
            snapshot_data["fii_net"] = fii_ctx.get("fii_net")
            snapshot_data["dii_net"] = fii_ctx.get("dii_net")

        # FII F&O net (from derivatives positioning)
        if fno_analysis and fno_analysis.get("fii"):
            snapshot_data["fii_fno_net"] = fno_analysis["fii"].get("net")

        # Compute 1D return
        if nifty_closes and len(nifty_closes) >= 2:
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
        # Get Nifty price history for momentum factor
        nifty_hist_data = None
        try:
            import yfinance as yf
            nifty_hist = yf.Ticker("^NSEI").history(period="1y")["Close"].dropna()
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
        from src.earnings_tracker import run_earnings_analysis
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
            fg_data["bull_bear_score"] = snapshot_data["bull_bear_score"]
        if nifty_closes and len(nifty_closes) >= 252:
            fg_data["momentum_12m"] = ((nifty_closes[-1] / nifty_closes[-252]) - 1) * 100
        fear_greed = compute_fear_greed_index(**fg_data)
        fg_score = fear_greed.get("score") or fear_greed.get("index")  # handle both key names
        if fg_score is not None:
            fear_greed_block = f"\n[Fear & Greed Index: {fg_score}/100 — {fear_greed.get('label', 'NEUTRAL')}]"
            print(f"   → Fear/Greed: {fg_score}/100 ({fear_greed.get('label')})")
    except Exception as e:
        print(f"   ⚠️ Fear/Greed: {e}")

    # ── MARKET STATE DASHBOARD ─────────────────────────────────
    market_state_block = ""
    try:
        from src.context_engine import compute_market_phase
        from src.formatters import format_market_state_dashboard

        # Get context from format_context_block
        ctx = getattr(format_context_block, 'last_ctx', None) or {}

        # Inject temporal context for dashboard duration display
        if 'temporal' in dir() and temporal.get("ok"):
            ctx["temporal_context"] = temporal

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

        # Format dashboard
        market_state_block = format_market_state_dashboard(market_phase, ctx)
        if market_state_block:
            print(f"   → Market State: {market_phase['phase']} ({market_phase['stance']})")
    except Exception as e:
        print(f"   ⚠️ Market State: {e}")

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

    # Replace placeholders properly
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
            # Remove both the header line AND the placeholder when empty
            # Need to remove: [BLOCK X: ...]\n{placeholder}
            import re
            prompt = re.sub(rf'{re.escape(header)}\n\s*{re.escape(placeholder)}', '', prompt)

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

    # ── INJECT MARKET STATE DASHBOARD ──────────────────────────
    if market_state_block:
        prompt += "\n\n" + market_state_block

    # ── INJECT SIGNAL WEIGHTS (accuracy feedback) ──────────────
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

    # ── INJECT MASTER SIGNAL (replaces Block 0) ─────────────────
    if master_signal_block:
        # Replace Block 0 with master signal
        prompt = prompt.replace("{block_0}", master_signal_block)

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

    # ── AI Analysis ───────────────────────────────────────────────
    print(f"   ⏱️ Data + Quant: {_time.time()-_t0:.1f}s")
    _t0 = _time.time()
    print("🔄 Running AI analysis (volume task)...")
    try:
        ai = AIEngine()
        analysis = ai.analyze("volume", prompt)
    except Exception as e:
        print(f"   ⚠️ AI failed: {e}")
        analysis = "⚠️ AI analysis temporarily unavailable."
        send_text(f"🚨 *Market Intel*\n\n{analysis}")
        return

    # ── PRE-SEND CHECKLIST (10 hard gates) ───────────────────────
    try:
        from src.block_validator import pre_send_checklist, format_checklist_report
        checklist = pre_send_checklist(blocks, snapshot_data, analysis)
        print(format_checklist_report(checklist))
    except Exception as e:
        print(f"   ⚠️ Pre-send checklist: {e}")

    # ── OUTPUT VALIDATION (pre-send consistency check) ───────────
    print("🔄 VALIDATING OUTPUT")
    try:
        from src.output_validator import validate_output
        # Compute absorption % for fallback context
        _fii_net = snapshot_data.get("fii_net", 0) or 0
        _dii_net = snapshot_data.get("dii_net", 0) or 0
        _absorption_pct = None
        if _fii_net < 0 and _dii_net > 0:
            _absorption_pct = (_dii_net / abs(_fii_net)) * 100

        # Compute VIX percentile for consistency check
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
            "fii_net": snapshot_data.get("fii_net"),
            "dii_net": snapshot_data.get("dii_net"),
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
        validation = validate_output(analysis, ground_truth)
        if not validation["send"]:
            print(f"   ⚠️ OUTPUT REJECTED: {validation['reason']}")
            for issue in validation["issues"]:
                print(f"      → {issue}")
            analysis = validation["fallback_text"] or analysis
        else:
            print(f"   ✅ Output validated: {validation['reason']}")
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

    # ── Send Telegram ───────────────────────────────────────────
    # Validate AI response - never send blank
    if validate_ai_response(analysis, min_words=50):
        ist_time = "🌅" if mode == "morning" else "🌃"
        header = f"{ist_time} *MARKET INTEL ({mode.upper()})*"
        send_text(f"{header}\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n{analysis}\n\n━━━━━━━━━━━━━━━━━━━━━━━━")
        print("✅ Market Intel sent")
    else:
        # Fallback to raw formatted data
        fallback = get_market_intel_fallback(blocks)
        ist_time = "🌅" if mode == "morning" else "🌃"
        header = f"{ist_time} *MARKET INTEL ({mode.upper()})*"
        send_text(f"{header}\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n{fallback}\n\n━━━━━━━━━━━━━━━━━━━━━━━━")
        print("⚠️ AI response too short - sent fallback")

    # ── Execution time summary ──────────────────────────────────
    total_time = _time.time() - _job_start
    print(f"\n⏱️ Total execution: {total_time:.1f}s ({total_time/60:.1f}min)")
    if total_time > 240:
        print(f"⚠️ EXCEEDED 4-MIN LIMIT — consider splitting into separate jobs")


if __name__ == "__main__":
    main()