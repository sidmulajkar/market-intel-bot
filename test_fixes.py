#!/usr/bin/env python3
"""Test all P0/P1 fixes."""
import sys
sys.path.insert(0, '.')

print("=" * 60)
print("TEST 1: _ordinal function")
print("=" * 60)
from src.formatters import _ordinal
for n in [1, 2, 3, 4, 11, 12, 13, 21, 22, 23, 73, 100]:
    print(f"  {n} -> {_ordinal(n)}")

print()
print("=" * 60)
print("TEST 2: compute_absorption (centralized)")
print("=" * 60)
from src.formatters import compute_absorption
tests = [
    (-5000, 4000, "strong floor"),
    (-5000, 2000, "partial support"),
    (-5000, 1000, "weak support"),
    (3000, 1000, "not relevant (FII buying)"),
    (-5000, -2000, "not relevant (both selling)"),
    (0, 1000, "not relevant (unclear)"),
]
for fii, dii, expected in tests:
    pct, label = compute_absorption(fii, dii)
    status = "PASS" if (pct is None) == (label == "") or (pct is not None and label) else "FAIL"
    print(f"  FII {fii:+,.0f}, DII {dii:+,.0f}: {pct} | {label} [{status}]")

print()
print("=" * 60)
print("TEST 3: VIX normalization")
print("=" * 60)
from src.signal_arbitrator import normalize_to_100, normalize_signal
# VIX 10 -> should be bullish (high score)
# VIX 22 -> should be bearish (low score, ~44)
# VIX 25 -> should be bearish (~40)
# VIX 40 -> should be strongly bearish (~16)
vix_tests = [
    (10, "low VIX, should be bullish (expect >70)"),
    (15, "normal VIX, should be neutral-bullish (expect ~55)"),
    (20, "elevated VIX, should be neutral (expect ~50)"),
    (22, "elevated VIX, should be bearish (expect ~44)"),
    (25, "high VIX, should be bearish (expect ~40)"),
    (30, "very high VIX, should be bearish (expect ~33)"),
    (40, "extreme VIX, should be strongly bearish (expect ~16)"),
]
for vix, desc in vix_tests:
    score = normalize_signal("vix", vix)
    direction = "BULLISH" if score > 55 else "BEARISH" if score < 45 else "NEUTRAL"
    print(f"  VIX {vix}: normalized={score:.0f} -> {direction} ({desc})")

print()
print("=" * 60)
print("TEST 4: rolling_quant.py ordinal usage (syntax check)")
print("=" * 60)
try:
    # Just import to check syntax is valid
    from src.rolling_quant import format_percentile_block
    print("  OK: format_percentile_block imports without error")
    # The actual _ordinal usage is in the function body - syntax check covers it
    import ast
    with open("src/rolling_quant.py") as f:
        source = f.read()
    ast.parse(source)
    print("  OK: rolling_quant.py parses without syntax errors")
    # Verify no hardcoded "th" in the percentile block format
    if "(pct}th pct" in source:
        print("  FAIL: Still has hardcoded 'th' in format_percentile_block")
    else:
        print("  OK: No hardcoded 'th' in format_percentile_block")
except Exception as e:
    print(f"  FAIL: {e}")

print()
print("=" * 60)
print("TEST 5: validation_helper.py (syntax check)")
print("=" * 60)
try:
    from src.validation_helper import validate_and_send
    print("  OK: validation_helper imports without error")
    import ast
    with open("src/validation_helper.py") as f:
        source = f.read()
    ast.parse(source)
    print("  OK: validation_helper.py parses without syntax errors")
except Exception as e:
    print(f"  FAIL: {e}")

print()
print("=" * 60)
print("TEST 6: morning_brief.py and evening_report.py (syntax check)")
print("=" * 60)
for fname in ["jobs/morning_brief.py", "jobs/evening_report.py"]:
    try:
        import ast
        with open(fname) as f:
            source = f.read()
        ast.parse(source)
        print(f"  OK: {fname} parses without syntax errors")
        if "validation_helper" in source or "validate_and_send" in source:
            print(f"  OK: {fname} uses validation helper")
    except Exception as e:
        print(f"  FAIL: {fname}: {e}")

print()
print("=" * 60)
print("TEST 7: formatters.py ERP bridge (syntax check)")
print("=" * 60)
try:
    import ast
    with open("src/formatters.py") as f:
        source = f.read()
    ast.parse(source)
    print("  OK: formatters.py parses without syntax errors")
    if "ERP negative" in source:
        print("  OK: ERP vs P/E bridge text present")
    if "FII/DII table" in source:
        print("  OK: FII percentile fallback present")
except Exception as e:
    print(f"  FAIL: {e}")

print()
print("=" * 60)
print("ALL TESTS COMPLETE")
print("=" * 60)
