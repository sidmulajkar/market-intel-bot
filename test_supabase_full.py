#!/usr/bin/env python3
"""
Full Supabase-dependent feature validation.
Requires: SUPABASE_URL + SUPABASE_KEY env vars.
Usage: SUPABASE_URL=... SUPABASE_KEY=... .venv/bin/python3 test_supabase_full.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

all_pass = True
failures = []

def check(label, ok, detail=""):
    global all_pass
    status = "✅" if ok else "❌"
    msg = f"  {status} {label}"
    if detail:
        msg += f": {detail}"
    print(msg)
    if not ok:
        all_pass = False
        failures.append(label)


# ═══════════════════════════════════════════════════════════════════
print("=" * 70)
print("SUPABASE-DEPENDENT FEATURE VALIDATION (Full)")
print("=" * 70)

# ── 1. DB CONNECTION ──────────────────────────────────────────────
print("\n1. DB CONNECTION")
try:
    from src.db import get_client
    check("Supabase client", get_client() is not None)
except Exception as e:
    check("Supabase client", False, str(e))

# ── 2. FII/DII FLOWS ─────────────────────────────────────────────
print("\n2. FII/DII FLOWS")
try:
    from src.db import get_fii_dii_flows
    rows = get_fii_dii_flows(days=60)
    check("FII/DII rows", len(rows) > 0, f"{len(rows)} rows")
    if rows:
        latest = rows[-1]
        fiinet = latest.get("fiinet_cr")
        diinet = latest.get("diinet_cr")
        check("Latest FII/DII values", fiinet is not None and diinet is not None,
              f"FII={fiinet}, DII={diinet}")
except Exception as e:
    check("FII/DII flows", False, str(e))

# ── 3. WATCHLIST ──────────────────────────────────────────────────
print("\n3. WATCHLIST")
try:
    from src.db import get_watchlist
    stocks = get_watchlist()
    check("Watchlist", len(stocks) > 0, f"{len(stocks)} stocks")
except Exception as e:
    check("Watchlist", False, str(e))

# ── 4. DAILY MARKET SNAPSHOT ─────────────────────────────────────
print("\n4. DAILY MARKET SNAPSHOT")
try:
    from src.db import get_daily_market_snapshots
    snaps = get_daily_market_snapshots(days=300)
    check("Market snapshots", len(snaps) > 0, f"{len(snaps)} rows")
    if len(snaps) >= 100:
        check("Sufficient for rolling quant", True, f"{len(snaps)} >= 100")
    else:
        check("Sufficient for rolling quant", False, f"only {len(snaps)} rows")
except Exception as e:
    check("Market snapshots", False, str(e))

# ── 5. VALUATION HISTORY ─────────────────────────────────────────
print("\n5. VALUATION HISTORY")
try:
    from src.db import get_valuation_history
    val = get_valuation_history(days=1095)
    check("Valuation history", len(val) > 0, f"{len(val)} rows")
except Exception as e:
    check("Valuation history", False, str(e))

# ── 6. FLOW METRICS ──────────────────────────────────────────────
print("\n6. FLOW METRICS (compute_flow_metrics)")
try:
    from src.db import get_fii_dii_flows
    from src.metrics import compute_flow_metrics
    rows = get_fii_dii_flows(days=60)
    if rows:
        fm = compute_flow_metrics(rows)
        check("Flow metrics ok", fm.get("ok"), f"date={fm.get('date')}")
        check("FII net", fm.get("fii_net") is not None, f"₹{fm.get('fii_net')}Cr")
        check("DII net", fm.get("dii_net") is not None, f"₹{fm.get('dii_net')}Cr")
        check("FII streak", fm.get("fii_streak") is not None,
              f"{fm.get('fii_streak')}d {fm.get('fii_streak_direction')}")
        check("FII z-score", fm.get("fii_z_score") is not None, str(fm.get('fii_z_score')))
        check("Absorption %", fm.get("dii_absorption_pct") is not None,
              f"{fm.get('dii_absorption_pct'):.0f}%")
        check("Absorption label", fm.get("dii_absorption_label") not in (None, ""),
              fm.get('dii_absorption_label', ""))
        check("4-week trend", fm.get("fii_4w_trend") is not None, fm.get('fii_4w_trend'))
        check("5-day total", fm.get("fii_5d_total") is not None, f"₹{fm.get('fii_5d_total')}Cr")
    else:
        check("Flow metrics", False, "no rows")
except Exception as e:
    check("Flow metrics", False, str(e))

# ── 7. CONTEXT ENGINE FULL ───────────────────────────────────────
print("\n7. CONTEXT ENGINE (run_contextualization)")
try:
    from src.context_engine import run_contextualization
    anchors = [
        {"name": "India VIX", "ok": True, "price": 16.5, "change_pct": -2.0},
        {"name": "Dollar Index", "ok": True, "price": 104.0, "change_pct": 0.3},
        {"name": "Brent Crude", "ok": True, "price": 78.0, "change_pct": 1.0},
        {"name": "Gold", "ok": True, "price": 2350.0, "change_pct": 0.5},
        {"name": "USD/INR", "ok": True, "price": 83.50, "change_pct": 0.1},
        {"name": "US 10Y Yield", "ok": True, "price": 4.3, "change_pct": -0.5},
        {"name": "CBOE VIX", "ok": True, "price": 15.0, "change_pct": -1.0},
        {"name": "US High Yield", "ok": True, "price": 46.0, "weekly_change_pct": 0.2},
        {"name": "WTI Crude", "ok": True, "price": 74.0, "change_pct": 0.8},
    ]
    ctx = run_contextualization(anchors)

    for key in ["bull_bear", "cross_asset_regime", "flow_metrics",
                "vix_context", "valuation", "yield_spread", "vix_spread",
                "credit_stress", "risk_mood"]:
        present = key in ctx
        if present:
            val = ctx[key]
            if isinstance(val, dict):
                ok = val.get("ok", val.get("score") is not None or val.get("normalized_score") is not None)
                check(f"ctx[{key}]", bool(ok))
            else:
                check(f"ctx[{key}]", True, str(val))
        else:
            check(f"ctx[{key}]", False, "MISSING")

    # Pre-computed interpretations
    for key in ["vix_interpretation", "fii_interpretation", "absorption_interpretation"]:
        if key in ctx:
            val = ctx[key]
            check(f"ctx[{key}]", val.get("ok"),
                  val.get("interpretation", val.get("message", ""))[:80])
        else:
            check(f"ctx[{key}]", False, "MISSING")
except Exception as e:
    check("Context engine", False, str(e))
    import traceback; traceback.print_exc()

# ── 8. INTERPRETATIONS IN AI PROMPT ──────────────────────────────
print("\n8. INTERPRETATIONS IN AI PROMPT (format_context_for_ai_full)")
try:
    from src.context_engine import run_contextualization, format_context_for_ai_full
    anchors = [
        {"name": "India VIX", "ok": True, "price": 16.5, "change_pct": -2.0},
        {"name": "Dollar Index", "ok": True, "price": 104.0, "change_pct": 0.3},
        {"name": "Brent Crude", "ok": True, "price": 78.0, "change_pct": 1.0},
        {"name": "Gold", "ok": True, "price": 2350.0, "change_pct": 0.5},
        {"name": "USD/INR", "ok": True, "price": 83.50, "change_pct": 0.1},
        {"name": "US 10Y Yield", "ok": True, "price": 4.3, "change_pct": -0.5},
        {"name": "CBOE VIX", "ok": True, "price": 15.0, "change_pct": -1.0},
        {"name": "US High Yield", "ok": True, "price": 46.0, "weekly_change_pct": 0.2},
        {"name": "WTI Crude", "ok": True, "price": 74.0, "change_pct": 0.8},
    ]
    ctx = run_contextualization(anchors)
    prompt = format_context_for_ai_full(ctx)
    check("AI prompt generated", prompt is not None and len(prompt) > 200,
          f"{len(prompt)} chars")

    for section in ["VIX Interpretation", "FII Flow Interpretation", "DII Absorption Interpretation"]:
        check(f"Prompt contains {section}", section in prompt)
        if section in prompt:
            idx = prompt.find(section)
            check(f"  Preview", True, prompt[idx:idx+80].replace("\n", " "))
except Exception as e:
    check("AI prompt formatting", False, str(e))
    import traceback; traceback.print_exc()

# ── 9. FORMATTERS WITH REAL CTX ──────────────────────────────────
print("\n9. FORMATTERS WITH REAL CONTEXT")
try:
    from src.formatters import format_flows, format_valuation_block
    from src.db import get_fii_dii_flows
    from src.metrics import compute_flow_metrics

    rows = get_fii_dii_flows(days=60)
    ctx_flow = {}
    if rows:
        fm = compute_flow_metrics(rows)
        ctx_flow["flow_metrics"] = fm

    flows_out = format_flows(ctx_flow if ctx_flow else None)
    check("format_flows", flows_out and len(flows_out) > 50, f"{len(flows_out) if flows_out else 0} chars")

    val_out = format_valuation_block(ctx_flow if ctx_flow else None)
    check("format_valuation_block", val_out and len(val_out) > 50, f"{len(val_out) if val_out else 0} chars")
except Exception as e:
    check("Formatters with ctx", False, str(e))

# ── 10. SIGNAL ARBITRATOR ────────────────────────────────────────
print("\n10. SIGNAL ARBITRATOR")
try:
    from src.signal_arbitrator import run_arbitration, format_master_signal_dashboard
    arb = run_arbitration({"bull_bear": 50, "fear_greed": 50, "vix": 16.5})
    check("Arbitration ok", arb.get("ok"))
    if arb.get("ok"):
        art = arb["arbitration"]
        check("Master score", True, f"{art['master_score']}/100 ({art['master_label']})")
        dash = format_master_signal_dashboard(art)
        check("Dashboard", dash is not None and len(dash) > 50, f"{len(dash)} chars")
except Exception as e:
    check("Signal arbitrator", False, str(e))

# ── 11. CONSEQUENCE ENGINE ───────────────────────────────────────
print("\n11. CONSEQUENCE ENGINE")
try:
    from src.consequence_engine import compute_consequence, format_consequence_line
    # Check actual API
    import inspect
    sig = inspect.signature(compute_consequence)
    params = list(sig.parameters.keys())

    # Try with keyword args based on what we find
    result = compute_consequence(
        variable="brent",
        current_value=85.0,
        change_value=-2.5,
        change_pct=-3.0,
    )
    if result:
        line = format_consequence_line("brent", result)
        check("Consequence", True, line[:100])
    else:
        check("Consequence", False, "empty result")
except Exception as e:
    check("Consequence engine", False, str(e))

# ── 12. BLOCK VALIDATOR ──────────────────────────────────────────
print("\n12. BLOCK VALIDATOR")
try:
    from src.block_validator import pre_send_checklist
    result = pre_send_checklist({})
    check("Block validator runs", True, f"{len(result)} items")
except Exception as e:
    check("Block validator", False, str(e))

# ── 13. PURGE OLD DATA ───────────────────────────────────────────
print("\n13. PURGE OLD DATA")
try:
    from src.db import purge_old_data
    result = purge_old_data()
    check("Purge runs", True, f"{result.get('sent_alerts', 0)} alerts purged")
except Exception as e:
    check("Purge old data", False, str(e))

# ── 14. MARKET STATE DASHBOARD (with real ctx) ───────────────────
print("\n14. MARKET STATE DASHBOARD")
try:
    from src.context_engine import run_contextualization, compute_market_phase
    from src.formatters import format_market_state_dashboard

    anchors = [
        {"name": "India VIX", "ok": True, "price": 16.5, "change_pct": -2.0},
        {"name": "Dollar Index", "ok": True, "price": 104.0, "change_pct": 0.3},
        {"name": "Brent Crude", "ok": True, "price": 78.0, "change_pct": 1.0},
        {"name": "Gold", "ok": True, "price": 2350.0, "change_pct": 0.5},
        {"name": "USD/INR", "ok": True, "price": 83.50, "change_pct": 0.1},
        {"name": "US 10Y Yield", "ok": True, "price": 4.3, "change_pct": -0.5},
        {"name": "CBOE VIX", "ok": True, "price": 15.0, "change_pct": -1.0},
        {"name": "US High Yield", "ok": True, "price": 46.0, "weekly_change_pct": 0.2},
        {"name": "WTI Crude", "ok": True, "price": 74.0, "change_pct": 0.8},
    ]
    ctx = run_contextualization(anchors)
    phase = compute_market_phase(ctx, {}, {"ok": False})
    dashboard = format_market_state_dashboard(phase, ctx)
    check("Market State Dashboard", dashboard is not None and len(dashboard) > 100,
          f"{len(dashboard)} chars")
except Exception as e:
    check("Market State Dashboard", False, str(e))

# ── 15. CROSS-ASSET REGIME WITH REAL DATA ────────────────────────
print("\n15. CROSS-ASSET REGIME")
try:
    from src.context_engine import run_contextualization
    anchors = [
        {"name": "India VIX", "ok": True, "price": 16.5, "change_pct": -2.0},
        {"name": "Dollar Index", "ok": True, "price": 104.0, "change_pct": 0.3},
        {"name": "Brent Crude", "ok": True, "price": 78.0, "change_pct": 1.0},
        {"name": "Gold", "ok": True, "price": 2350.0, "change_pct": 0.5},
        {"name": "USD/INR", "ok": True, "price": 83.50, "change_pct": 0.1},
        {"name": "US 10Y Yield", "ok": True, "price": 4.3, "change_pct": -0.5},
        {"name": "CBOE VIX", "ok": True, "price": 15.0, "change_pct": -1.0},
        {"name": "US High Yield", "ok": True, "price": 46.0, "weekly_change_pct": 0.2},
        {"name": "WTI Crude", "ok": True, "price": 74.0, "change_pct": 0.8},
    ]
    ctx = run_contextualization(anchors)
    regime = ctx.get("cross_asset_regime", {})
    check("Cross-asset regime", regime.get("ok"),
          regime.get("label", regime.get("message", "")))
except Exception as e:
    check("Cross-asset regime", False, str(e))

# ── 16. VIX CONTEXT WITH REAL DATA ───────────────────────────────
print("\n16. VIX CONTEXT")
try:
    from src.context_engine import run_contextualization
    anchors = [
        {"name": "India VIX", "ok": True, "price": 16.5, "change_pct": -2.0},
    ]
    ctx = run_contextualization(anchors)
    vix_ctx = ctx.get("vix_context", {})
    check("VIX context", vix_ctx.get("ok"),
          f"regime={vix_ctx.get('vix_regime')}, label={vix_ctx.get('vix_label')}")
except Exception as e:
    check("VIX context", False, str(e))

# ── 17. VALUATION WITH REAL DATA ────────────────────────────────
print("\n17. VALUATION (run_contextualization)")
try:
    from src.context_engine import run_contextualization
    anchors = [
        {"name": "US 10Y Yield", "ok": True, "price": 4.3, "change_pct": -0.5},
    ]
    ctx = run_contextualization(anchors)
    val = ctx.get("valuation", {})
    check("Valuation context", val.get("ok"),
          f"pe={val.get('pe')}, erp={val.get('erp_label')}")
except Exception as e:
    check("Valuation context", False, str(e))

# ── 18. INSIDER TRACKER ─────────────────────────────────────────
print("\n18. INSIDER TRACKER")
try:
    from src.formatters import format_insider_activity
    result = format_insider_activity()
    check("Insider activity", result is not None and len(result) > 10,
          f"{len(result)} chars")
except Exception as e:
    check("Insider tracker", False, str(e))

# ── 19. RISK MOOD ────────────────────────────────────────────────
print("\n19. RISK MOOD (from run_contextualization)")
try:
    from src.context_engine import run_contextualization
    anchors = [
        {"name": "India VIX", "ok": True, "price": 16.5, "change_pct": -2.0},
        {"name": "Dollar Index", "ok": True, "price": 104.0, "change_pct": 0.3},
        {"name": "Brent Crude", "ok": True, "price": 78.0, "change_pct": 1.0},
        {"name": "Gold", "ok": True, "price": 2350.0, "change_pct": 0.5},
        {"name": "USD/INR", "ok": True, "price": 83.50, "change_pct": 0.1},
        {"name": "US 10Y Yield", "ok": True, "price": 4.3, "change_pct": -0.5},
        {"name": "CBOE VIX", "ok": True, "price": 15.0, "change_pct": -1.0},
        {"name": "US High Yield", "ok": True, "price": 46.0, "weekly_change_pct": 0.2},
        {"name": "WTI Crude", "ok": True, "price": 74.0, "change_pct": 0.8},
    ]
    ctx = run_contextualization(anchors)
    risk_mood = ctx.get("risk_mood")
    check("Risk mood", risk_mood is not None, f"{risk_mood}/100")
except Exception as e:
    check("Risk mood", False, str(e))

# ── 20. COMPUTE BUDGET ───────────────────────────────────────────
print("\n20. COMPUTE BUDGET")
try:
    from src.compute_budget import ComputeBudget
    budget = ComputeBudget(max_seconds=180)
    budget.start()
    budget.start_stage("Block 0")
    import time; time.sleep(0.01)
    budget.end_stage("Block 0")
    health = budget.check_budget_health()
    check("ComputeBudget", True, f"stage={budget.current_stage}, health={health}")
except Exception as e:
    check("ComputeBudget", False, str(e))


# ── SUMMARY ───────────────────────────────────────────────────────
print("\n" + "=" * 70)
print(f"SUPABASE VALIDATION: {'PASS' if all_pass else 'FAIL'}")
print("=" * 70)
if failures:
    print(f"\n  Failed checks: {len(failures)}")
    for f in failures:
        print(f"    - {f}")
else:
    print("\n  ✅ All Supabase-dependent features validated with live data")
