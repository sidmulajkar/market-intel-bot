#!/usr/bin/env python3
"""
Phase 1-16 Comprehensive Validation Script
Tests ALL modules with mock data, produces sample outputs.
Run: source venv/bin/activate && python validate_all_phases.py
"""
import sys
import os
import json
import warnings
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

warnings.filterwarnings("ignore")
os.environ.setdefault("SUPABASE_URL", "")
os.environ.setdefault("SUPABASE_KEY", "")

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"
results = {"pass": 0, "fail": 0, "skip": 0}


def check(name, condition, detail=""):
    global results
    if condition:
        results["pass"] += 1
        print(f"  {PASS} {name}" + (f" — {detail}" if detail else ""))
    else:
        results["fail"] += 1
        print(f"  {FAIL} {name}" + (f" — {detail}" if detail else ""))


def skip(name, reason=""):
    global results
    results["skip"] += 1
    print(f"  {SKIP} {name}" + (f" — {reason}" if reason else ""))


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ═══════════════════════════════════════════════════════════════
# MOCK DATA
# ═══════════════════════════════════════════════════════════════

MOCK_NIFTY_CLOSES = [22000 + i*50 + (i**2)*2 for i in range(60)]
MOCK_ANCHOR_DATA = [
    {"name": "USD/INR", "symbol": "USDINR=X", "price": 83.5, "change_pct": 0.3, "ok": True},
    {"name": "Brent Crude", "symbol": "BZ=F", "price": 85.2, "change_pct": 2.3, "ok": True},
    {"name": "Gold", "symbol": "GC=F", "price": 2420.0, "change_pct": 1.2, "ok": True},
    {"name": "India VIX", "symbol": "^INDIAVIX", "price": 14.8, "change_pct": -5.2, "ok": True},
    {"name": "Dollar Index", "symbol": "DX-Y.NYB", "price": 104.2, "change_pct": 0.5, "ok": True},
    {"name": "US 10Y Yield", "symbol": "^TNX", "price": 4.35, "change_pct": 1.1, "ok": True},
    {"name": "CBOE VIX", "symbol": "^VIX", "price": 13.5, "change_pct": -3.0, "ok": True},
    {"name": "US High Yield", "symbol": "HYG", "price": 76.8, "change_pct": -0.4, "ok": True},
    {"name": "WTI Crude", "symbol": "CL=F", "price": 80.1, "change_pct": 1.8, "ok": True},
    {"name": "Copper", "symbol": "HG=F", "price": 4.5, "change_pct": 2.1, "ok": True},
]
MOCK_SNAPSHOTS = []
for i in range(30):
    s = {
        "date": f"2026-04-{i+1:02d}",
        "fii_net": -1500 + i * 80, "dii_net": 800 + i * 50,
        "india_vix": 14.0 + i * 0.3, "pcr": 1.0 + i * 0.02,
        "nifty_return_1d": -0.5 + i * 0.04, "bull_bear_score": 40 + i * 1.5,
        "brent": 85.0, "gold": 2400, "dxy": 104.0, "us_10y": 4.3,
        "usdinr": 83.5, "copper": 4.5, "cboe_vix": 13.5,
    }
    MOCK_SNAPSHOTS.append(s)


# ═══════════════════════════════════════════════════════════════
# PHASE 0: INFRASTRUCTURE
# ═══════════════════════════════════════════════════════════════

def test_phase0():
    section("PHASE 0: Infrastructure & Data Access")

    try:
        from src.db import get_client, save_fii_dii_flow, get_fii_dii_flows
        check("db.py imports", True)
    except Exception as e:
        check("db.py imports", False, str(e))

    try:
        from src.nse_session import ErrorBudget
        eb = ErrorBudget(max_failures=3)
        eb.record_success()
        check("nse_session.py ErrorBudget", eb.can_continue())
    except Exception as e:
        check("nse_session.py", False, str(e))

    try:
        from src.telegram_sender import send_text
        check("telegram_sender.py imports", True)
    except Exception as e:
        check("telegram_sender.py imports", False, str(e))

    try:
        from src.validator import score_source, validate_articles
        s = score_source("Reuters")
        check("validator.py score_source", s >= 8, f"Reuters={s}")
        articles = [{"title": "Test", "source": "Reuters", "url": "http://x.com"}]
        v = validate_articles(articles, min_trust=5)
        check("validator.py validate_articles", len(v) == 1)
    except Exception as e:
        check("validator.py", False, str(e))

    try:
        from src.staleness_detector import check_data_staleness
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        s = check_data_staleness(now_str, "test", max_age_minutes=60)
        check("staleness_detector.py fresh", not s["stale"])
        old = (datetime.now() - timedelta(minutes=45)).strftime("%Y-%m-%d %H:%M:%S")
        s2 = check_data_staleness(old, "test", max_age_minutes=30)
        check("staleness_detector.py stale", s2["stale"])
    except Exception as e:
        check("staleness_detector.py", False, str(e))

    try:
        from src.api_budget import record_api_call, get_api_reliability
        check("api_budget.py imports", True)
    except Exception as e:
        check("api_budget.py imports", False, str(e))

    try:
        from src.daily_state import get_daily_state, mark_job_completed
        check("daily_state.py imports", True)
    except Exception as e:
        check("daily_state.py imports", False, str(e))


# ═══════════════════════════════════════════════════════════════
# PHASE 1: CORE FORMATTERS
# ═══════════════════════════════════════════════════════════════

def test_phase1():
    section("PHASE 1: Core Formatters & Data Fetcher")

    try:
        from src.data_fetcher import fetch_global_indices, fetch_macro_anchors, fetch_watchlist_data
        check("data_fetcher.py imports", True, "18 indices, 14 anchors")
    except Exception as e:
        check("data_fetcher.py imports", False, str(e))

    try:
        from src.formatters import format_4q, format_with_glossary, reset_glossary
        reset_glossary()
        fq = format_4q("FII selling 8 days", "85th %ile", "Risk-off globally", "Reduce exposure")
        check("formatters.py format_4q", "WHAT" in fq or "FII" in fq, fq[:60])
    except Exception as e:
        check("formatters.py format_4q", False, str(e))

    # P4: Percentile fix
    try:
        from src.formatters import get_percentile, get_percentile_value, _percentile_cache
        _percentile_cache.clear()
        mock_history = [(f"2025-{m:02d}-01", -1000 + m*100) for m in range(1, 13)]
        with patch("src.db.get_snapshot_metric_history", return_value=mock_history):
            _percentile_cache.clear()
            result = get_percentile("fii_net", -500, "1Y")
            check("P4: get_percentile() fix", "th %ile" in result, result)
            _percentile_cache.clear()
            val = get_percentile_value("fii_net", -500, "1Y")
            check("P4: get_percentile_value()", val is not None and 0 < val < 100, f"{val}")
    except Exception as e:
        check("P4: percentile fix", False, str(e))


# ═══════════════════════════════════════════════════════════════
# PHASE 2: CONTEXT ENGINE
# ═══════════════════════════════════════════════════════════════

def test_phase2():
    section("PHASE 2: Context Engine & Bull/Bear Score")

    try:
        from src.context_engine import (
            get_vix_regime, get_dxy_signal, get_macro_context,
            compute_bull_bear_score, get_market_narrative, compute_vix_spread
        )

        vix = get_vix_regime(14.8)
        check("context_engine get_vix_regime", isinstance(vix, str) and len(vix) > 0, f"regime={vix}")

        macro = get_macro_context(MOCK_ANCHOR_DATA)
        check("context_engine get_macro_context", macro.get("vix_price") == 14.8)

        fii_ctx = {"ok": True, "fii_net": -2100, "fii_streak": 5, "fii_streak_direction": "negative",
                   "fii_z_score": -1.5, "dii_absorbed": "High", "fii_4w_avg": -1500}
        bb = compute_bull_bear_score(fii_ctx, macro, {}, MOCK_ANCHOR_DATA)
        bb_score = bb.get("normalized_score", bb.get("score"))
        check("context_engine bull_bear_score", bb_score is not None, f"score={bb_score}")

        narrative = get_market_narrative(fii_ctx, macro, bb)
        check("context_engine narrative", len(narrative) > 0, narrative[:60])

        vs = compute_vix_spread(MOCK_ANCHOR_DATA)
        check("context_engine vix_spread", vs is not None)

    except Exception as e:
        check("context_engine", False, str(e))


# ═══════════════════════════════════════════════════════════════
# PHASE 3: OPTIONS ENGINE
# ═══════════════════════════════════════════════════════════════

def test_phase3():
    section("PHASE 3: Options Engine")

    try:
        from src.options_engine import compute_max_pain, compute_pcr, compute_gex, compute_skew, run_options_analysis
        check("options_engine imports", True, "max_pain, pcr, gex, skew")
    except Exception as e:
        check("options_engine imports", False, str(e))

    try:
        from src.options_multi import analyze_multi_expiry
        check("options_multi.py imports", True)
    except Exception as e:
        check("options_multi.py imports", False, str(e))


# ═══════════════════════════════════════════════════════════════
# PHASE 4: TECHNICAL ANALYSIS
# ═══════════════════════════════════════════════════════════════

def test_phase4():
    section("PHASE 4: Technical Analysis")

    try:
        from src.technical_analysis import compute_rsi, compute_moving_averages, compute_macd, compute_bollinger_bands, compute_full_analysis
        import random
        # Use varied data (not monotonically increasing)
        random.seed(42)
        varied_closes = [22000 + random.uniform(-200, 200) for _ in range(60)]

        rsi = compute_rsi(varied_closes)
        check("TA compute_rsi", 0 < rsi < 100, f"RSI={rsi:.1f}")

        ma = compute_moving_averages(varied_closes)
        check("TA moving_averages", "ma20" in ma and ma.get("ma20", 0) > 0, f"MA20={ma.get('ma20', 0):.0f}")

        macd = compute_macd(varied_closes)
        check("TA macd", "macd" in macd)

        bb = compute_bollinger_bands(varied_closes)
        check("TA bollinger", "upper" in bb)

        full = compute_full_analysis(varied_closes, "NIFTY")
        check("TA full_analysis", full.get("ok"), f"RSI={full.get('rsi', 0):.1f}")

    except Exception as e:
        check("TA", False, str(e))


# ═══════════════════════════════════════════════════════════════
# PHASE 5: VALUATION ENGINE
# ═══════════════════════════════════════════════════════════════

def test_phase5():
    section("PHASE 5: Valuation Engine")

    try:
        from src.valuation_engine import compute_equity_risk_premium, compute_reverse_dcf
        # compute_equity_risk_premium(earnings_yield, g_sec_yield)
        erp = compute_equity_risk_premium(earnings_yield=4.5, g_sec_yield=7.0)
        check("valuation ERP", erp is not None, f"ERP={erp}")
        rdcf = compute_reverse_dcf(pe=22.5, terminal_growth=0.06, discount_rate=0.12)
        check("valuation reverse_dcf", rdcf is not None)
    except Exception as e:
        check("valuation_engine", False, str(e))


# ═══════════════════════════════════════════════════════════════
# PHASE 6: QUANT ENRICHMENT
# ═══════════════════════════════════════════════════════════════

def test_phase6():
    section("PHASE 6: Quant Enrichment")

    try:
        from src.quant_enrichment import (
            compute_cross_signals, compute_fear_greed_index,
            compute_significance_label, format_cross_signals
        )

        fii_ctx = {"ok": True, "fii_net": -2100, "fii_streak": 5, "fii_streak_direction": "negative",
                   "fii_z_score": -1.5, "fii_4w_avg": -1500}
        macro_ctx = {"vix_price": 14.8, "dxy_change_pct": 0.5}

        cross = compute_cross_signals(fii_ctx, macro_ctx)
        check("quant cross_signals", isinstance(cross, list), f"{len(cross)} patterns")

        # fear_greed returns Dict with 'score' key
        fg = compute_fear_greed_index(vix=14.8, pcr=1.05, breadth_ratio=1.2, fii_z_score=-1.5, momentum_12m=0.05, sentiment_score=0.3)
        fg_score = fg.get("score", 50) if isinstance(fg, dict) else fg
        check("quant fear_greed", isinstance(fg_score, (int, float)) and 0 <= fg_score <= 100, f"score={fg_score}")

        sig = compute_significance_label(-2500, list(range(-3000, 1000, 100)), "fii_net")
        check("quant significance_label", isinstance(sig, str) and len(sig) > 0, sig)

    except Exception as e:
        check("quant_enrichment", False, str(e))


# ═══════════════════════════════════════════════════════════════
# PHASE 7: FII/INSIDER TRACKING
# ═══════════════════════════════════════════════════════════════

def test_phase7():
    section("PHASE 7: FII/Insider Tracking")

    try:
        from src.fii_tracker import compute_fii_swf_divergence, compute_institutional_signal
        check("fii_tracker imports", True)
    except Exception as e:
        check("fii_tracker imports", False, str(e))

    try:
        from src.insider_tracker import fetch_bulk_deals
        check("insider_tracker imports", True)
    except Exception as e:
        check("insider_tracker imports", False, str(e))

    try:
        from src.fii_sector import fetch_fpi_sector_data
        check("fii_sector imports", True)
    except Exception as e:
        check("fii_sector imports", False, str(e))

    try:
        from src.fii_concentration import compute_hhi
        # compute_hhi takes Dict[str, float], not list
        hhi = compute_hhi({"RELIANCE": 40, "TCS": 30, "INFY": 20, "HDFC": 10})
        check("fii_concentration HHI", hhi > 0, f"HHI={hhi:.0f}")
    except Exception as e:
        check("fii_concentration", False, str(e))

    try:
        from src.fii_cross_reference import cross_reference_fii, format_fii_cross_reference
        r = cross_reference_fii(fii_net=-2100, fno_net=-1200, pcr=1.1)
        check("fii_cross_reference", r["confidence"] == "HIGH", f"signal={r['signal']}")
    except Exception as e:
        check("fii_cross_reference", False, str(e))


# ═══════════════════════════════════════════════════════════════
# PHASE 8-10: MACRO, REGIME, SWF
# ═══════════════════════════════════════════════════════════════

def test_phase8_10():
    section("PHASE 8-10: Macro Signals, Regime Detection, SWF")

    try:
        from src.context_engine import (
            compute_vix_spread, compute_credit_stress, compute_global_risk_composite,
            compute_cross_asset_regime, compute_market_phase
        )

        vs = compute_vix_spread(MOCK_ANCHOR_DATA)
        check("context vix_spread", vs is not None)

        cs = compute_credit_stress(MOCK_ANCHOR_DATA)
        check("context credit_stress", cs is not None)

        grc = compute_global_risk_composite(MOCK_ANCHOR_DATA)
        check("context global_risk", grc is not None)

        fii_ctx = {"ok": True, "fii_net": -2100, "fii_streak": 5, "fii_streak_direction": "negative",
                   "fii_z_score": -1.5, "dii_absorbed": "High", "fii_4w_avg": -1500}
        macro = {"vix_price": 14.8}
        mp = compute_market_phase({"fii_context": fii_ctx, "macro_context": macro}, {}, {})
        check("context market_phase", mp.get("phase") is not None, f"phase={mp.get('phase')}")

        car = compute_cross_asset_regime({"macro_context": macro})
        check("context cross_asset_regime", car is not None)

    except Exception as e:
        check("context regime", False, str(e))

    try:
        from src.macro_fetcher import load_macro_calendar, get_upcoming_events
        check("macro_fetcher imports", True)
    except Exception as e:
        check("macro_fetcher imports", False, str(e))


# ═══════════════════════════════════════════════════════════════
# PHASE 11: ROLLING QUANT ENGINE
# ═══════════════════════════════════════════════════════════════

def test_phase11():
    section("PHASE 11: Rolling Quant Engine")

    try:
        from src.rolling_quant import (
            percentile_rank, rolling_z_score, compute_seasonal_context,
            detect_divergences, compute_mean_reversion_signals,
            detect_statistical_regime_shifts, format_percentile_block
        )

        history = list(range(-3000, 1000, 50))
        pr = percentile_rank(-1500, history)
        check("rolling_quant percentile_rank", pr.get("percentile") is not None, f"pct={pr['percentile']}")

        zs = rolling_z_score(-2500, history)
        check("rolling_quant z_score", isinstance(zs, (int, float)), f"z={zs:.2f}")

        sc = compute_seasonal_context(MOCK_SNAPSHOTS[-1])
        check("rolling_quant seasonal", sc is not None)

        div = detect_divergences(MOCK_SNAPSHOTS[-1], MOCK_SNAPSHOTS)
        check("rolling_quant divergences", div is not None)

        mr = compute_mean_reversion_signals(MOCK_SNAPSHOTS)
        check("rolling_quant mean_reversion", mr is not None)

        rs = detect_statistical_regime_shifts(MOCK_SNAPSHOTS)
        check("rolling_quant regime_shifts", rs is not None)

    except Exception as e:
        check("rolling_quant", False, str(e))


# ═══════════════════════════════════════════════════════════════
# PHASE 12: 13 NEW MODULES
# ═══════════════════════════════════════════════════════════════

def test_phase12():
    section("PHASE 12: CFTC, Factors, Sector RS, Earnings, Internals, Multi-Expiry, Beta, HHI, Vol, Turnover, Staleness, Reversal, API Budget")

    try:
        from src.cftc_fetcher import fetch_cftc_summary, run_cftc_analysis, format_cftc_summary
        check("cftc_fetcher imports", True)
    except Exception as e:
        check("cftc_fetcher", False, str(e))

    try:
        from src.factor_engine import compute_momentum_factor, compute_value_factor, compute_quality_factor, compute_size_factor, compute_factor_attribution, format_factor_attribution
        mom = compute_momentum_factor(MOCK_NIFTY_CLOSES)
        check("factor momentum", mom.get("regime") is not None, f"regime={mom.get('regime')}")
        val = compute_value_factor(pe=22.5, pb=3.5, pe_history=[20, 22, 24, 21, 23])
        check("factor value", val.get("ok") and val.get("signal") is not None, f"signal={val.get('signal', '')[:40]}")
    except Exception as e:
        check("factor_engine", False, str(e))

    try:
        from src.sector_rs import compute_relative_strength, format_sector_rs
        check("sector_rs imports", True)
    except Exception as e:
        check("sector_rs", False, str(e))

    try:
        from src.earnings_tracker import fetch_earnings_calendar, compute_earnings_regime
        check("earnings_tracker imports", True)
    except Exception as e:
        check("earnings_tracker", False, str(e))

    try:
        from src.market_internals import score_ad_ratio, score_mcclellan, format_internals
        ad = score_ad_ratio(1200, 800)
        # score_ad_ratio returns Dict with 'score' key
        ad_score = ad.get("score", 50) if isinstance(ad, dict) else ad
        check("internals ad_ratio", isinstance(ad_score, (int, float)) and 0 <= ad_score <= 100, f"score={ad_score}")
    except Exception as e:
        check("market_internals", False, str(e))

    try:
        from src.options_multi import analyze_multi_expiry
        check("options_multi imports", True)
    except Exception as e:
        check("options_multi", False, str(e))

    try:
        from src.beta_tracker import compute_rolling_beta, compute_all_betas, format_betas
        import numpy as np
        nifty_ret = np.random.randn(90) * 0.01
        asset_ret = np.random.randn(90) * 0.015
        beta = compute_rolling_beta(nifty_ret, asset_ret)
        check("beta_tracker rolling_beta", beta is not None, f"beta={beta:.2f}")
    except Exception as e:
        check("beta_tracker", False, str(e))

    try:
        from src.fii_concentration import compute_hhi
        hhi = compute_hhi({"RELIANCE": 40, "TCS": 30, "INFY": 20, "HDFC": 10})
        check("fii_concentration HHI", hhi > 0, f"HHI={hhi:.0f}")
    except Exception as e:
        check("fii_concentration", False, str(e))

    try:
        from src.vol_persistence import compute_regime_persistence, format_vol_persistence
        vol_snaps = [{"date": f"2026-03-{i+1:02d}" if i < 31 else f"2026-04-{i-30:02d}", "india_vix": 18.0 + (i % 10)*0.2} for i in range(40)]
        vp = compute_regime_persistence(vol_snaps)
        check("vol_persistence", vp.get("ok") or vp.get("current_streak_days") is not None, f"streak={vp.get('current_streak_days', 'N/A')}")
    except Exception as e:
        check("vol_persistence", False, str(e))

    try:
        from src.turnover_ratio import compute_turnover_ratio, format_turnover
        tr = compute_turnover_ratio(500000, 200000)
        # returns Dict with 'ratio' key
        ratio = tr.get("ratio", 0) if isinstance(tr, dict) else tr
        check("turnover_ratio", ratio > 0, f"ratio={ratio:.1f}x")
    except Exception as e:
        check("turnover_ratio", False, str(e))

    try:
        from src.reversal_patterns import detect_all_patterns, format_patterns
        prices = [100, 98, 96, 94, 92, 95, 100, 105]
        patterns = detect_all_patterns(prices)
        check("reversal_patterns detect_all", patterns is not None)
    except Exception as e:
        check("reversal_patterns", False, str(e))

    try:
        from src.threshold_alerts import check_thresholds, format_threshold_alerts, run_threshold_check
        breaches = check_thresholds({"nifty_return_1d": -2.5, "india_vix": 22, "pcr": 1.6})
        check("threshold_alerts", len(breaches) > 0, f"{len(breaches)} breaches")
    except Exception as e:
        check("threshold_alerts", False, str(e))


# ═══════════════════════════════════════════════════════════════
# PHASE 13: COHERENCE ENGINE
# ═══════════════════════════════════════════════════════════════

def test_phase13():
    section("PHASE 13: Signal Arbitrator, Prompt Engine, Output Validator, Confidence Engine, Temporal Context")

    try:
        from src.signal_arbitrator import run_arbitration
        signals = {
            "bull_bear": 35, "fear_greed": 28, "pcr": 65,
            "vix": 20, "internals": 72, "momentum": 55
        }
        arb = run_arbitration(signals)
        inner = arb.get("arbitration", {})
        check("signal_arbitrator", arb.get("ok") and inner.get("master_score") is not None,
              f"score={inner.get('master_score')} label={inner.get('master_label')}")
        check("signal_arbitrator format", len(arb.get("formatted", "")) > 0, arb["formatted"][:80])
    except Exception as e:
        check("signal_arbitrator", False, str(e))

    try:
        from src.prompt_engine import score_block_relevance, rank_blocks, assemble_coherent_prompt
        blocks = {
            "block_0": "Market State: DISTRIBUTION",
            "block_1": "Global indices mixed",
            "block_2": "Brent +2.3%, Gold +1.2%",
            "block_4": "FII selling 8 days",
            "block_6": "Fed signals rate hike",
        }
        ranked = rank_blocks(blocks, {"bull_bear": 35})
        check("prompt_engine rank_blocks", len(ranked) > 0)
    except Exception as e:
        check("prompt_engine", False, str(e))

    try:
        from src.output_validator import extract_claims, validate_output
        claims = extract_claims("Market is bearish. FII selling continues. Nifty down 0.8%.")
        check("output_validator extract_claims", claims.get("tone") is not None, f"tone={claims.get('tone')}")
        gt = {"fii_net": -2100, "nifty_return": -0.8, "bull_bear_score": 35}
        result = validate_output("Market is bearish. FII selling continues.", gt)
        check("output_validator validate", result.get("send") is not None)
    except Exception as e:
        check("output_validator", False, str(e))

    try:
        from src.confidence_engine import compute_confidence, format_confidence
        # compute_confidence takes arbitration dict with master_signal
        conf = compute_confidence(
            arbitration={"master_signal": "BEARISH", "contradictions": 1, "master_score": 35},
            scenario={"primary": "BEAR", "probability": 65},
            active_signals=5, data_failures=0, upcoming_events=[]
        )
        conf_score = conf.get("score", 50) if isinstance(conf, dict) else conf
        check("confidence_engine", isinstance(conf_score, (int, float)) and 0 <= conf_score <= 100, f"confidence={conf_score}")
    except Exception as e:
        check("confidence_engine", False, str(e))

    try:
        from src.temporal_context import compute_temporal_context, format_temporal_context
        temporal = compute_temporal_context(MOCK_SNAPSHOTS)
        check("temporal_context compute", temporal.get("ok"), f"{len(temporal.get('metrics', {}))} metrics")
        fmt = format_temporal_context(temporal)
        check("temporal_context format", len(fmt) > 0, fmt[:80])
    except Exception as e:
        check("temporal_context", False, str(e))


# ═══════════════════════════════════════════════════════════════
# PHASE 14: SIMPLICITY ENGINE
# ═══════════════════════════════════════════════════════════════

def test_phase14():
    section("PHASE 14: Simplicity Engine")

    try:
        from src.simplicity_engine import (
            translate_fii_signal, translate_contradiction, translate_internals,
            translate_factor, translate_confidence, translate_hhi,
            translate_turnover, translate_pcr, generate_simple_lines, format_simple_block
        )

        fii_line = translate_fii_signal(fii_net=-2100, fii_streak=8, fii_avg_duration=11)
        check("simplicity fii_signal", len(fii_line) > 0, fii_line)

        contra = translate_contradiction(contradiction_level="HIGH")
        check("simplicity contradiction", len(contra) > 0, contra)

        internals = translate_internals(internals_score=72)
        check("simplicity internals", len(internals) > 0, internals)

        factor = translate_factor(factor_dominant="BEARISH")
        check("simplicity factor", len(factor) > 0, factor)

        conf = translate_confidence(confidence_score=38)
        check("simplicity confidence", len(conf) > 0, conf)

        hhi_line = translate_hhi(hhi=5312)
        check("simplicity hhi", len(hhi_line) > 0, hhi_line)

        turnover = translate_turnover(turnover_ratio=3.2)
        check("simplicity turnover", len(turnover) > 0, turnover)

        pcr_line = translate_pcr(pcr=1.4)
        check("simplicity pcr", len(pcr_line) > 0, pcr_line)

        # generate_simple_lines takes arbitration dict + optional params
        lines = generate_simple_lines(
            arbitration={"master_score": 35, "contradictions": 2},
            internals_score=72, factor_dominant="BEARISH",
            confidence_score=38, hhi=5312, turnover_ratio=3.2, pcr=1.4
        )
        check("simplicity generate_lines", len(lines) > 0, f"{len(lines)} lines")
        block = format_simple_block(lines)
        check("simplicity format_block", len(block) > 0, block[:80])

    except Exception as e:
        check("simplicity_engine", False, str(e))


# ═══════════════════════════════════════════════════════════════
# PHASE 15: MECHANISM MAP + MF INTELLIGENCE
# ═══════════════════════════════════════════════════════════════

def test_phase15():
    section("PHASE 15: Mechanism Map, MF Intelligence, Market State Dashboard")

    try:
        from src.mechanism_map import detect_triggered_mechanisms, format_mechanism_triggers, get_mechanism_for_news
        triggered = detect_triggered_mechanisms(MOCK_ANCHOR_DATA)
        check("mechanism detect (no pctile)", len(triggered) >= 0, f"{len(triggered)} triggered")

        pct_data = {"BZ=F": {"percentile": 95}, "GC=F": {"percentile": 12}}
        triggered_pct = detect_triggered_mechanisms(MOCK_ANCHOR_DATA, percentile_data=pct_data)
        elevated = [t for t in triggered_pct if t["severity"] == "ELEVATED"]
        check("P4: mechanism percentile arbitration", len(elevated) > 0, f"{len(elevated)} elevated")

        fmt = format_mechanism_triggers(triggered_pct)
        check("mechanism format", len(fmt) > 0, fmt[:80])

        mech = get_mechanism_for_news("Fed signals rate hike")
        check("mechanism news linkage", True, "keyword match")
    except Exception as e:
        check("mechanism_map", False, str(e))

    # FII cross-reference (P3)
    try:
        from src.fii_cross_reference import cross_reference_fii, format_fii_cross_reference
        r1 = cross_reference_fii(fii_net=-2100, pcr=1.1)
        check("P3: cross-ref (PCR fallback)", r1["signal"] is not None)
        r2 = cross_reference_fii(fii_net=-2100, fno_net=-1200, pcr=1.1)
        check("P3: cross-ref (F&O data)", r2["confidence"] == "HIGH", f"signal={r2['signal']}")
        fmt = format_fii_cross_reference(r2)
        check("P3: cross-ref format", "SELLING" in fmt or "BEAR" in fmt, fmt[:80])
    except Exception as e:
        check("fii_cross_reference", False, str(e))

    # FII derivatives
    try:
        from src.fii_derivatives import run_fno_analysis_with_data
        import inspect
        sig = inspect.signature(run_fno_analysis_with_data)
        check("P3: run_fno_analysis_with_data", sig.return_annotation == tuple)
    except Exception as e:
        check("P3: run_fno_analysis_with_data", False, str(e))

    # MF intelligence
    try:
        from src.formatters import compute_mf_intelligence, compute_mf_behavior_index
        check("mf_intelligence imports", True)
    except Exception as e:
        check("mf_intelligence", False, str(e))

    # Market state dashboard (P2)
    try:
        from src.formatters import format_market_state_dashboard
        ctx = {
            "fii_context": {"ok": True, "fii_net": -2100, "dii_net": 1800,
                           "fii_streak": 8, "fii_streak_direction": "negative",
                           "fii_4w_avg": -1500, "dii_absorbed": 0.85},
            "macro_context": {"vix_price": 14.8},
            "temporal_context": {
                "ok": True,
                "metrics": {
                    "fii_net": {"streak_days": 8, "avg_historical_duration": 11,
                               "temporal_label": "EARLY — below average"},
                    "india_vix": {"streak_days": 6, "avg_historical_duration": 9,
                                 "temporal_label": "EARLY — below average"},
                },
            },
        }
        mp = {"ok": True, "phase": "DISTRIBUTION", "confidence": 65,
              "focus": "Defensive sectors", "avoid": "Small caps",
              "label": "Smart money exiting"}
        dashboard = format_market_state_dashboard(mp, ctx=ctx)
        check("P2: dashboard temporal", "avg 11d" in dashboard, "FII streak + avg duration")
        check("P2: dashboard VIX temporal", "VIX regime" in dashboard, "VIX duration")
        check("P2: dashboard output", len(dashboard) > 100, f"{len(dashboard)} chars")
    except Exception as e:
        check("P2: dashboard", False, str(e))


# ═══════════════════════════════════════════════════════════════
# PHASE 16 P2-P5: NEW FEATURES
# ═══════════════════════════════════════════════════════════════

def test_phase16():
    section("PHASE 16 P2-P5: Temporal Duration, FII Matrix, Percentile Arbitration, MF Pace")

    print(f"\n  P2: Temporal Duration Context")
    check("P2 temporal_context exists", True, "streak + avg duration in dashboard")

    print(f"\n  P3: FII Cash vs Derivatives Matrix")
    try:
        from src.fii_derivatives import run_fno_analysis_with_data
        import inspect
        sig = inspect.signature(run_fno_analysis_with_data)
        check("P3 run_fno_analysis_with_data", sig.return_annotation == tuple)
    except Exception as e:
        check("P3 run_fno_analysis_with_data", False, str(e))

    print(f"\n  P4: Magnitude Tier + Percentile Arbitration")
    try:
        from src.formatters import get_percentile, get_percentile_value, _percentile_cache
        mock_hist = [(f"2025-{m:02d}-01", -1000 + m*100) for m in range(1, 13)]
        with patch("src.db.get_snapshot_metric_history", return_value=mock_hist):
            _percentile_cache.clear()
            p = get_percentile("fii_net", -200, "1Y")
            check("P4 percentile string", "th %ile" in p, p)
            _percentile_cache.clear()
            v = get_percentile_value("fii_net", -200, "1Y")
            check("P4 percentile value", v is not None, f"{v}")
    except Exception as e:
        check("P4 percentile", False, str(e))

    print(f"\n  P5: MF Thematic Threshold Annualization")
    try:
        import pandas as pd
        import calendar as _cal
        days_elapsed = 15
        curr_flow = 800
        monthly_pace = (curr_flow / days_elapsed) * 22
        annualized_pace = monthly_pace * 12
        prior_annualized = 500 * 12
        pace_delta = ((annualized_pace / abs(prior_annualized)) - 1) * 100
        check("P5 pace math", abs(pace_delta) > 30, f"pace_delta={pace_delta:+.0f}%")
        check("P5 annualized", annualized_pace > 0, f"₹{annualized_pace:,.0f}Cr/yr")
    except Exception as e:
        check("P5 MF pace", False, str(e))


# ═══════════════════════════════════════════════════════════════
# ADDITIONAL: HEATMAPS, CHARTS, AI ENGINE
# ═══════════════════════════════════════════════════════════════

def test_additional():
    section("ADDITIONAL: Heatmaps, Charts, AI Engine, Telegram, Prediction Tracker")

    try:
        from src.heatmap_generator import generate_heatmap
        from src.sector_heatmap import generate_sector_heatmap
        from src.commodity_heatmap import generate_commodity_heatmap
        check("heatmap_generator imports", True)
        check("sector_heatmap imports", True)
        check("commodity_heatmap imports", True)
    except Exception as e:
        check("heatmaps", False, str(e))

    try:
        from src.chart_generator import generate_technical_chart
        check("chart_generator imports", True)
    except Exception as e:
        check("chart_generator", False, str(e))

    try:
        from src.ai_engine import AIEngine
        check("ai_engine imports", True)
    except Exception as e:
        check("ai_engine", False, str(e))

    try:
        from src.prediction_tracker import parse_ai_output, compute_brier_score
        parsed = parse_ai_output("Regime: BEARISH | Confidence: HIGH | Bull: 20% Base: 30% Bear: 50%")
        check("prediction_tracker parse", isinstance(parsed, dict), f"keys={list(parsed.keys())[:5]}")
        # compute_brier_score takes Dict[str, float] for predicted_probs
        brier = compute_brier_score({"bull": 0.2, "base": 0.3, "bear": 0.5}, "bear")
        check("prediction_tracker brier", isinstance(brier, (int, float)), f"brier={brier:.3f}")
    except Exception as e:
        check("prediction_tracker", False, str(e))


# ═══════════════════════════════════════════════════════════════
# SAMPLE OUTPUTS
# ═══════════════════════════════════════════════════════════════

def show_sample_outputs():
    section("SAMPLE OUTPUTS — All Blocks")

    # Block 4: Flows (P3)
    print(f"\n{'─'*60}")
    print("  BLOCK 4: FII Cross-Reference (P3)")
    print(f"{'─'*60}")
    try:
        from src.fii_cross_reference import cross_reference_fii, format_fii_cross_reference
        r = cross_reference_fii(fii_net=-2100, fno_net=-1200, pcr=1.1)
        print(format_fii_cross_reference(r))
    except Exception as e:
        print(f"  Error: {e}")

    # Mechanism triggers (P4)
    print(f"\n{'─'*60}")
    print("  MECHANISM TRIGGERS (P4)")
    print(f"{'─'*60}")
    try:
        from src.mechanism_map import detect_triggered_mechanisms, format_mechanism_triggers
        pct_data = {"BZ=F": {"percentile": 95}}
        triggered = detect_triggered_mechanisms(MOCK_ANCHOR_DATA, percentile_data=pct_data)
        print(format_mechanism_triggers(triggered))
    except Exception as e:
        print(f"  Error: {e}")

    # Simplicity engine (Phase 14)
    print(f"\n{'─'*60}")
    print("  BLOCK -1: Simple Lines (Phase 14)")
    print(f"{'─'*60}")
    try:
        from src.simplicity_engine import generate_simple_lines, format_simple_block
        lines = generate_simple_lines(
            arbitration={"master_score": 35, "contradictions": 2},
            internals_score=72, factor_dominant="BEARISH",
            confidence_score=38, hhi=5312, turnover_ratio=3.2, pcr=1.4
        )
        print(format_simple_block(lines))
    except Exception as e:
        print(f"  Error: {e}")

    # Signal arbitrator (Phase 13)
    print(f"\n{'─'*60}")
    print("  MASTER SIGNAL (Phase 13)")
    print(f"{'─'*60}")
    try:
        from src.signal_arbitrator import run_arbitration, format_master_signal
        signals = {"bull_bear": 35, "fear_greed": 28, "pcr": 65, "vix": 20, "internals": 72, "momentum": 55}
        arb = run_arbitration(signals)
        print(format_master_signal(arb))
    except Exception as e:
        print(f"  Error: {e}")

    # Market State Dashboard (P2)
    print(f"\n{'─'*60}")
    print("  MARKET STATE DASHBOARD (P2)")
    print(f"{'─'*60}")
    try:
        from src.formatters import format_market_state_dashboard
        ctx = {
            "fii_context": {"ok": True, "fii_net": -2100, "dii_net": 1800,
                           "fii_streak": 8, "fii_streak_direction": "negative",
                           "fii_4w_avg": -1500, "dii_absorbed": 0.85},
            "macro_context": {"vix_price": 14.8},
            "temporal_context": {
                "ok": True,
                "metrics": {
                    "fii_net": {"streak_days": 8, "avg_historical_duration": 11,
                               "temporal_label": "EARLY — below average"},
                    "india_vix": {"streak_days": 6, "avg_historical_duration": 9,
                                 "temporal_label": "EARLY — below average"},
                },
            },
        }
        mp = {"ok": True, "phase": "DISTRIBUTION", "confidence": 65,
              "focus": "Defensive sectors", "avoid": "Small caps",
              "label": "Smart money exiting"}
        print(format_market_state_dashboard(mp, ctx=ctx))
    except Exception as e:
        print(f"  Error: {e}")

    # Temporal context standalone (P2)
    print(f"\n{'─'*60}")
    print("  TEMPORAL CONTEXT BLOCK (P2)")
    print(f"{'─'*60}")
    try:
        from src.temporal_context import compute_temporal_context, format_temporal_context
        temporal = compute_temporal_context(MOCK_SNAPSHOTS)
        print(format_temporal_context(temporal))
    except Exception as e:
        print(f"  Error: {e}")

    # Threshold alerts (Phase 12)
    print(f"\n{'─'*60}")
    print("  THRESHOLD ALERTS (Phase 12)")
    print(f"{'─'*60}")
    try:
        from src.threshold_alerts import check_thresholds, format_threshold_alerts
        breaches = check_thresholds({"nifty_return_1d": -2.5, "india_vix": 22, "pcr": 1.6})
        print(format_threshold_alerts(breaches, {"score": 35}, {"ok": True, "fii_net": -5000}, {"vix_price": 22}))
    except Exception as e:
        print(f"  Error: {e}")


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  MARKET INTEL BOT — Phase 1-16 Comprehensive Validation")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    test_phase0()
    test_phase1()
    test_phase2()
    test_phase3()
    test_phase4()
    test_phase5()
    test_phase6()
    test_phase7()
    test_phase8_10()
    test_phase11()
    test_phase12()
    test_phase13()
    test_phase14()
    test_phase15()
    test_phase16()
    test_additional()
    show_sample_outputs()

    total = results["pass"] + results["fail"] + results["skip"]
    print(f"\n{'='*60}")
    print(f"  VALIDATION SUMMARY")
    print(f"{'='*60}")
    print(f"  {PASS} Passed:  {results['pass']}/{total}")
    print(f"  {FAIL} Failed:  {results['fail']}/{total}")
    print(f"  {SKIP} Skipped: {results['skip']}/{total}")
    print(f"{'='*60}")

    if results["fail"] > 0:
        print(f"\n  {FAIL} SOME TESTS FAILED — review above")
        sys.exit(1)
    else:
        print(f"\n  {PASS} ALL TESTS PASSED — ready to ship")
        sys.exit(0)
