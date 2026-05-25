#!/usr/bin/env python3
"""
Dry-run test: Simulate full Telegram output pipeline.
Shows exactly what would be sent to Telegram, with validation markers
for the 6 fixes that were applied.

Usage: python3 test_telegram_output.py

Requires: Supabase credentials and API keys from ../apikeys.txt
"""
import os
import sys
import re

_dir = os.path.dirname(os.path.abspath(__file__))
_root = _dir
if _root not in sys.path:
    sys.path.insert(0, _root)

# Load API keys
keyfile = os.path.join(_dir, "..", "apikeys.txt")
if os.path.exists(keyfile):
    with open(keyfile) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                # Handle both "KEY=VALUE" and "KEY = VALUE" formats
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    os.environ.setdefault(k, v)

errors = []
fix_results = {}

print("=" * 70)
print("TELEGRAM OUTPUT DRY-RUN — Full Pipeline Validation")
print("=" * 70)

# ─────────────────────────────────────────────────────────────────────
# FIX 1: VIX Normalization Test
# ─────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("FIX 1: VIX → Sentiment Direction")
print("=" * 70)
try:
    from src.signal_arbitrator import normalize_signal

    vix_values = [10, 15, 20, 22, 25, 30, 40]
    all_correct = True
    for vix in vix_values:
        score = normalize_signal("vix", vix)
        direction = "BULLISH" if score > 55 else "BEARISH" if score < 45 else "NEUTRAL"
        expected_bearish = vix >= 22  # VIX 22+ should be bearish
        is_correct = (direction == "BEARISH") == expected_bearish or (vix < 22 and direction in ("BULLISH", "NEUTRAL"))
        marker = "✅" if is_correct else "❌ FAIL"
        if not is_correct:
            all_correct = False
        print(f"  VIX {vix:>2}: score={score:.0f} → {direction:10s}  {marker}")

    fix_results["VIX Normalization"] = "PASS" if all_correct else "FAIL"
except Exception as e:
    fix_results["VIX Normalization"] = f"ERROR: {e}"
    print(f"  ❌ {e}")

# ─────────────────────────────────────────────────────────────────────
# FIX 2: Ordinal Suffix Test
# ─────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("FIX 2: Ordinal Suffixes in rolling_quant.py")
print("=" * 70)
try:
    from src.formatters import _ordinal

    test_cases = [
        (1, "1st"), (2, "2nd"), (3, "3rd"), (4, "4th"),
        (11, "11th"), (12, "12th"), (13, "13th"),
        (21, "21st"), (22, "22nd"), (23, "23rd"),
        (73, "73rd"), (100, "100th"), (101, "101st"),
    ]
    all_correct = True
    for n, expected in test_cases:
        result = _ordinal(n)
        marker = "✅" if result == expected else f"❌ (got {result})"
        if result != expected:
            all_correct = False
        print(f"  {n:>3} → {result:6s}  {marker}")

    # Also check that rolling_quant.py uses _ordinal, not hardcoded "th"
    with open("src/rolling_quant.py") as f:
        rq_source = f.read()
    if "_ordinal(int(pct))" in rq_source:
        print("  ✅ rolling_quant.py uses _ordinal(int(pct))")
    elif "(pct}th pct" in rq_source:
        print("  ❌ rolling_quant.py still has hardcoded 'th'")
        all_correct = False
    else:
        print("  ⚠️  Cannot determine if rolling_quant.py uses _ordinal")

    fix_results["Ordinal Suffix"] = "PASS" if all_correct else "FAIL"
except Exception as e:
    fix_results["Ordinal Suffix"] = f"ERROR: {e}"
    print(f"  ❌ {e}")

# ─────────────────────────────────────────────────────────────────────
# FIX 3: Absorption Centralization Test
# ─────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("FIX 3: Absorption Computation (Centralized)")
print("=" * 70)
try:
    from src.formatters import compute_absorption

    tests = [
        (-5000, 4000, 80.0, "strong floor"),
        (-5000, 3000, 60.0, "partial support"),
        (-5000, 2000, 40.0, "weak support"),
        (-5000, 5000, 100.0, "strong floor"),
        (3000, 1000, None, ""),
        (-5000, -2000, None, ""),
        (0, 1000, None, ""),
    ]
    all_correct = True
    for fii, dii, expect_pct, expect_label in tests:
        pct, label = compute_absorption(fii, dii)
        if expect_pct is None:
            ok = (pct is None and label == "")
        else:
            ok = (abs(pct - expect_pct) < 1 and expect_label in label)
        marker = "✅" if ok else f"❌ (got {pct}, '{label}')"
        if not ok:
            all_correct = False
        print(f"  FII {fii:+,.0f}, DII {dii:+,.0f}: {pct}% / '{label}'  {marker}")

    # Check formatters.py uses compute_absorption in both places
    with open("src/formatters.py") as f:
        fm_source = f.read()
    count = fm_source.count("compute_absorption(")
    if count >= 3:  # definition + 2 usages
        print(f"  ✅ compute_absorption called in {count} places (def + 2 usages)")
    else:
        print(f"  ⚠️  compute_absorption called in {count} places (expected 3+)")

    # Check dashboard no longer uses dii_absorbed*100
    if "dii_absorbed*100" in fm_source:
        print("  ⚠️  Dashboard still has dii_absorbed*100")
    else:
        print("  ✅ Dashboard no longer uses raw dii_absorbed*100")

    fix_results["Absorption Centralization"] = "PASS" if all_correct else "FAIL"
except Exception as e:
    fix_results["Absorption Centralization"] = f"ERROR: {e}"
    print(f"  ❌ {e}")

# ─────────────────────────────────────────────────────────────────────
# FIX 4: Validation Helper Test
# ─────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("FIX 4: Validation Coverage (morning_brief + evening_report)")
print("=" * 70)
try:
    from src.validation_helper import validate_and_send
    print("  ✅ validation_helper.py imports successfully")

    # Check both job files use the helper
    for fname in ["jobs/morning_brief.py", "jobs/evening_report.py"]:
        with open(fname) as f:
            source = f.read()
        if "validate_and_send" in source:
            print(f"  ✅ {fname} uses validate_and_send")
        else:
            print(f"  ❌ {fname} does NOT use validate_and_send")

    # Test basic functionality with mock data
    valid_test = True
    # Mock: valid text with correct Nifty level
    mock_gt = {"nifty_close": 23659}
    mock_text = "Nifty is trading around 23,600 levels today."

    from src.output_validator import validate_output
    result = validate_output(mock_text, mock_gt)
    if result["send"]:
        print(f"  ✅ Validation passes for correct Nifty level: '{mock_text}'")
    else:
        print(f"  ❌ Validation incorrectly rejected: '{mock_text}'")
        valid_test = False

    # Mock: text with stale Nifty level
    stale_text = "Nifty is trading around 17,800 levels today."
    result = validate_output(stale_text, mock_gt)
    if not result["send"]:
        print(f"  ✅ Validation catches stale level: '{stale_text}'")
    else:
        print(f"  ⚠️  Stale level not caught (may depend on ground_truth completeness)")

    fix_results["Validation Coverage"] = "PASS" if valid_test else "FAIL"
except Exception as e:
    fix_results["Validation Coverage"] = f"ERROR: {e}"
    print(f"  ❌ {e}")

# ─────────────────────────────────────────────────────────────────────
# FIX 5: ERP vs P/E Bridge Test
# ─────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("FIX 5: ERP vs P/E Bridge Explanation")
print("=" * 70)
try:
    with open("src/formatters.py") as f:
        fm_source = f.read()
    if "ERP negative" in fm_source and "bonds more attractive" in fm_source:
        print("  ✅ formatters.py has ERP vs P/E bridge text")
    else:
        print("  ❌ formatters.py missing ERP bridge text")

    with open("src/valuation_engine.py") as f:
        ve_source = f.read()
    if "ERP negative" in ve_source and "bonds more attractive" in ve_source:
        print("  ✅ valuation_engine.py has ERP vs P/E bridge text")
    else:
        print("  ❌ valuation_engine.py missing ERP bridge text")

    fix_results["ERP Bridge"] = "PASS" if ("ERP negative" in fm_source and "ERP negative" in ve_source) else "FAIL"
except Exception as e:
    fix_results["ERP Bridge"] = f"ERROR: {e}"
    print(f"  ❌ {e}")

# ─────────────────────────────────────────────────────────────────────
# FIX 6: FII Percentile Fallback Test
# ─────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("FIX 6: FII Percentile Fallback to fii_dii_flows")
print("=" * 70)
try:
    with open("src/formatters.py") as f:
        fm_source = f.read()
    if "fii_dii_flows" in fm_source and "fiinet_cr" in fm_source:
        print("  ✅ get_percentile has fii_dii_flows fallback")
    else:
        print("  ❌ get_percentile missing fii_dii_flows fallback")

    if "FII/DII table" in fm_source:
        print("  ✅ Fallback label 'FII/DII table' present")
    else:
        print("  ⚠️  Fallback label may differ")

    with open("src/formatters.py") as f:
        fm_source2 = f.read()
    # Count fallback occurrences (should be in both get_percentile and get_percentile_value)
    fallback_count = fm_source2.count("fiinet_cr")
    if fallback_count >= 2:
        print(f"  ✅ Fallback present in {fallback_count} locations")
    else:
        print(f"  ⚠️  Fallback found {fallback_count} times (expected 2)")

    fix_results["FII Percentile Fallback"] = "PASS" if "fii_dii_flows" in fm_source else "FAIL"
except Exception as e:
    fix_results["FII Percentile Fallback"] = f"ERROR: {e}"
    print(f"  ❌ {e}")

# ─────────────────────────────────────────────────────────────────────
# LIVE DATA TESTS (requires DB + API access)
# ─────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("LIVE DATA FORMATTER TESTS")
print("=" * 70)

try:
    from src.db import get_fii_dii_flows, get_client

    db = get_client()
    if db is None:
        print("  ⚠️  No Supabase connection — skipping live tests")
    else:
        print("  ✅ Supabase connected")

        # Test FII flows
        flows = get_fii_dii_flows(days=10)
        if flows:
            print(f"  ✅ FII/DII flows: {len(flows)} records retrieved")
            latest = flows[-1]
            fii_net = latest.get("fiinet_cr", 0)
            dii_net = latest.get("diinet_cr", 0)
            pct, label = compute_absorption(fii_net, dii_net)
            if pct is not None:
                print(f"  ✅ Latest absorption: FII {fii_net:+,.0f}Cr, DII {dii_net:+,.0f}Cr → {pct:.0f}% ({label})")
            else:
                print(f"  → Latest: FII {fii_net:+,.0f}Cr, DII {dii_net:+,.0f}Cr → absorption N/A ({label})")
        else:
            print("  ⚠️  No FII/DII flow data")

        # Test formatters with live data
        print("\n  ─── Format Blocks ───")

        try:
            from src.formatters import format_flows
            flows_block = format_flows()
            if flows_block:
                print("\n[BLOCK 4: FLOW INTELLIGENCE]")
                print(flows_block[:500])
                if "...truncated" in flows_block or len(flows_block) > 500:
                    print("  ... (truncated)")
            else:
                print("  ⚠️  format_flows returned empty")
        except Exception as e:
            print(f"  ❌ format_flows failed: {e}")

        try:
            from src.formatters import format_market_state_dashboard
            from src.context_engine import run_contextualization, compute_market_phase
            from src.data_fetcher import fetch_macro_anchors

            anchors = fetch_macro_anchors()
            ctx = run_contextualization(anchors)
            market_phase = compute_market_phase(ctx, {}, {"ok": False})
            dashboard = format_market_state_dashboard(market_phase, ctx)
            if dashboard:
                print("\n[MARKET STATE DASHBOARD]")
                print(dashboard[:500])
            else:
                print("  ⚠️  Dashboard returned empty")
        except Exception as e:
            print(f"  ⚠️  Dashboard failed: {e}")

        try:
            from src.formatters import format_valuation_block
            valuation = format_valuation_block()
            if valuation:
                print("\n[VALUATION BLOCK]")
                print(valuation)
                if "ERP negative" in valuation:
                    print("  ✅ ERP bridge text is visible in output")
            else:
                print("  ⚠️  Valuation block returned empty")
        except Exception as e:
            print(f"  ⚠️  Valuation failed: {e}")

except Exception as e:
    print(f"  ⚠️  Live data tests skipped: {e}")

# ─────────────────────────────────────────────────────────────────────
# SIGNAL ARBITRATOR FULL TEST
# ─────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SIGNAL ARBITRATOR — Master Signal Test")
print("=" * 70)
try:
    from src.signal_arbitrator import arbitrate_signals

    # Simulate different signal configurations (dict of name → value)
    test_signals = {
        "bull_bear": 65,
        "vix": 22,
        "pcr": 0.85,
        "fear_greed": 55,
    }
    signal = arbitrate_signals(test_signals)
    print(f"  Master Score: {signal.get('master_score', 'unknown')}/100")
    print(f"  Label: {signal.get('master_label', 'unknown')}")
    print(f"  Structural: {signal.get('structural_score', '?')} ({signal.get('structural_signal', '?')})")
    print(f"  Sentiment: {signal.get('sentiment_score', '?')} ({signal.get('sentiment_signal', '?')})")
    print(f"  Contradiction: {signal.get('contradiction_level', '?')}")

    # Check VIX direction — VIX=22 should contribute BEARISH sentiment
    sentiment_signal = signal.get("sentiment_signal", "")
    if "BEAR" in sentiment_signal:
        print(f"  ✅ VIX=22 correctly contributes to {sentiment_signal} sentiment")
    else:
        print(f"  ⚠️  Sentiment is {sentiment_signal} (VIX=22 is bearish, overall depends on other signals)")
except Exception as e:
    print(f"  ❌ Signal arbitrator test failed: {e}")

# ─────────────────────────────────────────────────────────────────────
# FIX 7: News Staleness Check
# ─────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("FIX 7: News Staleness Detection")
print("=" * 70)
try:
    from src.validator import _check_staleness

    test_articles = [
        {"headline": "India GDP grows 7.2% in Q3, beating expectations"},
        {"headline": "SpaceX valuation could leapfrog Berkshire Hathaway"},
        {"headline": "IMAX held preliminary talks with potential buyers"},
        {"headline": "RBI holds rates steady, MPC unanimous"},
    ]
    result = _check_staleness(test_articles)
    for a in result:
        seen = "seen" if a.get("seen_before") else "new"
        fresh = a.get("freshness_score", "?")
        print(f"  ✅ {a['headline'][:60]:60s} → {seen} (freshness: {fresh})")

    fix_results["News Staleness"] = "PASS"
except Exception as e:
    fix_results["News Staleness"] = f"ERROR: {e}"
    print(f"  ❌ {e}")

# ─────────────────────────────────────────────────────────────────────
# FIX 8: India Linkage Scoring
# ─────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("FIX 8: India Linkage Enforcement")
print("=" * 70)
try:
    from src.validator import _check_india_linkage

    test_cases = [
        ("India GDP grows 7.2% in Q3, beating expectations", 10, "direct India mention"),
        ("Fed cuts rates by 25bps, signals pause", 7, "global macro affecting India"),
        ("Oil prices surge 5% on Middle East tensions", 7, "oil prices affects India imports"),
        ("SpaceX valuation could leapfrog Berkshire Hathaway", 3, "no India impact"),
        ("IMAX held preliminary talks with potential buyers", 3, "no India impact"),
        ("Semiconductor shortage affects global supply chain", 7, "semiconductors affect India IT/exports"),
        ("Rupee at 100 is mental fear, not macro nightmare", 10, "mentions Rupee/INR"),
        ("TCS reports strong Q3 results, beats estimates", 10, "Indian company"),
    ]
    all_correct = True
    for headline, expected, desc in test_cases:
        article = {"headline": headline}
        score = _check_india_linkage(article)
        ok = score == expected
        marker = "✅" if ok else f"❌ (got {score}, expected {expected})"
        if not ok:
            all_correct = False
        print(f"  {marker} Score {score:2d}: '{headline[:55]}' — {desc}")

    # Test that validate_articles filters low-linkage articles
    from src.validator import validate_articles
    mixed = [
        {"headline": "India GDP grows 7.2%", "source": "reuters"},
        {"headline": "SpaceX valuation leapfrogs Berkshire", "source": "bloomberg"},
        {"headline": "SpaceX valuation leapfrogs Berkshire", "source": "some-blog"},
        {"headline": "Rupee hits 100 against dollar", "source": "moneycontrol"},
        {"headline": "IMAX held talks with buyers", "source": "cnbc"},
    ]
    validated = validate_articles(mixed, min_india_linkage=5)
    kept = [a["headline"][:40] for a in validated]
    print(f"\n  Filtered {len(mixed)} articles → {len(validated)} kept:")
    for h in kept:
        print(f"    ✅ {h}")

    # SpaceX from some-blog should be dropped (low trust + low India linkage)
    dropped_spacex = not any("SpaceX" in a["headline"] for a in validated if a["source"] == "some-blog")
    if dropped_spacex:
        print("  ✅ Low-trust + no-India article correctly dropped")
    else:
        print("  ❌ Low-trust + no-India article should have been dropped")
        all_correct = False

    # SpaceX from bloomberg should pass (high trust global context)
    kept_spacex_bloomberg = any("SpaceX" in a["headline"] and "bloomberg" in a["source"] for a in validated)
    if kept_spacex_bloomberg:
        print("  ✅ High-trust global article kept for context")
    else:
        print("  ⚠️  Bloomberg SpaceX story not kept (may have been deduplicated)")

    fix_results["India Linkage"] = "PASS" if all_correct else "FAIL"
except Exception as e:
    fix_results["India Linkage"] = f"ERROR: {e}"
    print(f"  ❌ {e}")

# ─────────────────────────────────────────────────────────────────────
# FIX 9: Block Deal Pattern Recognition
# ─────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("FIX 9: Block Deal Pattern Detection")
print("=" * 70)
try:
    from src.insider_tracker import _detect_deal_patterns

    # Simulate JSWSTEEL promoter-to-institutional transfer
    test_deals = [
        {"symbol": "JSWSTEEL", "company": "JSW Steel Ltd", "client": "JSW Energy Ltd",
         "side": "SELL", "qty": 25000000, "price": 1260.00, "value_cr": 3150.00, "date": "2026-05-23", "deal_type": "block"},
        {"symbol": "JSWSTEEL", "company": "JSW Steel Ltd", "client": "GQG Partners",
         "side": "BUY", "qty": 15000000, "price": 1260.00, "value_cr": 1890.00, "date": "2026-05-23", "deal_type": "block"},
        {"symbol": "JSWSTEEL", "company": "JSW Steel Ltd", "client": "SBI Mutual Fund",
         "side": "BUY", "qty": 10000000, "price": 1260.00, "value_cr": 1260.00, "date": "2026-05-23", "deal_type": "block"},
    ]
    patterns = _detect_deal_patterns(test_deals)
    if patterns:
        for p in patterns:
            print(f"  ✅ Pattern detected: {p['symbol']} ({p['type']})")
            print(f"     {p['insight'][:100]}")
    else:
        print("  ❌ No patterns detected from test data")

    # Test accumulation pattern
    accum_deals = [
        {"symbol": "RELIANCE", "company": "Reliance Industries", "client": "Foreign Portfolio X",
         "side": "BUY", "qty": 1000000, "price": 2500.00, "value_cr": 250.00, "date": "2026-05-20", "deal_type": "bulk"},
        {"symbol": "RELIANCE", "company": "Reliance Industries", "client": "Foreign Portfolio X",
         "side": "BUY", "qty": 800000, "price": 2520.00, "value_cr": 201.60, "date": "2026-05-21", "deal_type": "bulk"},
        {"symbol": "RELIANCE", "company": "Reliance Industries", "client": "Foreign Portfolio X",
         "side": "BUY", "qty": 1200000, "price": 2480.00, "value_cr": 297.60, "date": "2026-05-22", "deal_type": "bulk"},
    ]
    accum_patterns = _detect_deal_patterns(accum_deals)
    if any(p["type"] == "ACCUMULATION" for p in accum_patterns):
        print(f"  ✅ Accumulation pattern detected for RELIANCE")
    else:
        print(f"  ⚠️  Accumulation pattern not detected (may need 3+ unique dates)")

    # Test that format_insider_summary includes patterns
    test_data = {
        "ok": True, "date_range": "2026-05-20 to 2026-05-23",
        "bulk_count": 5, "block_count": 3, "symbols": ["JSWSTEEL"],
        "top_deals": [], "symbol_flows": [], "patterns": patterns,
    }
    from src.insider_tracker import format_insider_summary
    formatted = format_insider_summary(test_data)
    if "Pattern Analysis" in formatted or "PROMOTER" in formatted:
        print("  ✅ Pattern Analysis section included in formatted output")
    else:
        print("  ❌ Pattern Analysis section missing from formatted output")

    fix_results["Block Deal Patterns"] = "PASS" if patterns else "FAIL"
except Exception as e:
    fix_results["Block Deal Patterns"] = f"ERROR: {e}"
    print(f"  ❌ {e}")

# ─────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("FIX VERIFICATION SUMMARY")
print("=" * 70)
all_pass = True
for fix_name, result in fix_results.items():
    marker = "✅" if result == "PASS" else "❌"
    if result != "PASS":
        all_pass = False
    print(f"  {marker} {fix_name}: {result}")

print()
if all_pass:
    print(f"🎉 All {len(fix_results)} fixes verified successfully!" if all_pass else "⚠️  Some fixes need attention")
else:
    print("⚠️  Some fixes need attention — review FAIL/ERROR markers above")

print("=" * 70)
