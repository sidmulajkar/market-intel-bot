"""
Per-Block Output Validator — catches missing enrichment, stale data, and bare numbers.
Runs after formatters, before AI prompt assembly.

Every block must answer: WHAT | HOW BIG | WHY | SO WHAT
If any is missing → flag it.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCK REQUIREMENTS
# ═══════════════════════════════════════════════════════════════════════════════

BLOCK_REQUIREMENTS = {
    "block_0": {
        "name": "Market Posture",
        "must_contain": ["score", "lean", "confidence"],
        "must_have_consequence": True,
        "must_have_comparison": True,
        "must_have_percentile": True,
        "max_lines": 15,
    },
    "block_1": {
        "name": "Global Indices",
        "must_contain": ["nifty", "advance", "decline"],
        "must_have_consequence": False,
        "must_have_comparison": False,
        "must_have_percentile": False,
        "max_lines": 10,
    },
    "block_2": {
        "name": "Macro Anchors",
        "must_contain": ["brent", "gold", "usd"],
        "must_have_consequence": True,
        "must_have_comparison": True,
        "must_have_percentile": True,
        "max_lines": 20,
    },
    "block_4": {
        "name": "FII/DII Flows",
        "must_contain": ["fii", "dii"],
        "must_have_consequence": True,
        "must_have_comparison": True,
        "must_have_percentile": False,
        "max_lines": 15,
    },
    "block_5": {
        "name": "Derivatives",
        "must_contain": ["pcr", "max pain"],
        "must_have_consequence": False,
        "must_have_comparison": False,
        "must_have_percentile": False,
        "max_lines": 10,
    },
    "block_6": {
        "name": "News",
        "must_contain": [],
        "must_have_consequence": False,
        "must_have_comparison": False,
        "must_have_percentile": False,
        "max_lines": 15,
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# CONSEQUENCE INDICATORS
# ═══════════════════════════════════════════════════════════════════════════════

CONSEQUENCE_INDICATORS = [
    "cad stress", "cad improvement", "inr pressure", "annualized",
    "import bill", "effective selling", "fii outflow", "margin compress",
    "current account", "subsidy", "depreciation pressure", "appreciation",
    "floor exists", "absorption", "net market impact",
    "→",  # arrow prefix from consequence engine
]

COMPARISON_INDICATORS = [
    "vs ", "was ", "yesterday", "1d", "1w", "1m", "weekly", "daily",
    "change", "↑", "↓", "streak", "consecutive", "since",
]

PERCENTILE_INDICATORS = [
    "percentile", "%ile", "1y", "1yr", "historical", "unusual",
    "rare", "extreme", "elevated", "depressed", "normal range",
]


# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATORS
# ═══════════════════════════════════════════════════════════════════════════════

def validate_block(block_id: str, block_text: str, data_timestamp: datetime = None) -> Dict:
    """
    Validate a single block against its requirements.
    Returns: {ok, warnings, errors, has_consequence, line_count, is_stale}
    """
    result = {
        "ok": True,
        "warnings": [],
        "errors": [],
        "has_consequence": False,
        "line_count": 0,
        "is_stale": False,
    }

    if not block_text:
        result["ok"] = False
        result["errors"].append(f"{block_id}: EMPTY BLOCK — no output generated")
        return result

    text_lower = block_text.lower()
    lines = block_text.strip().split("\n")
    result["line_count"] = len(lines)

    req = BLOCK_REQUIREMENTS.get(block_id)
    if not req:
        return result  # unknown block, skip validation

    # Check required content
    for keyword in req.get("must_contain", []):
        if keyword.lower() not in text_lower:
            result["warnings"].append(f"{block_id} ({req['name']}): missing '{keyword}'")

    # Check consequence layer
    has_consequence = any(ind in text_lower for ind in CONSEQUENCE_INDICATORS)
    result["has_consequence"] = has_consequence

    if req.get("must_have_consequence") and not has_consequence:
        result["warnings"].append(f"{block_id} ({req['name']}): NO CONSEQUENCE LAYER — data without India impact")

    # Check comparison layer (Layer 2)
    if req.get("must_have_comparison"):
        has_comparison = any(ind in text_lower for ind in COMPARISON_INDICATORS)
        if not has_comparison:
            result["warnings"].append(f"{block_id} ({req['name']}): NO COMPARISON — bare number without vs yesterday/1W")

    # Check percentile layer (Layer 3)
    if req.get("must_have_percentile"):
        has_percentile = any(ind in text_lower for ind in PERCENTILE_INDICATORS)
        if not has_percentile:
            result["warnings"].append(f"{block_id} ({req['name']}): NO PERCENTILE — how unusual is this?")

    # Check line count
    max_lines = req.get("max_lines", 20)
    if len(lines) > max_lines:
        result["warnings"].append(f"{block_id} ({req['name']}): {len(lines)} lines (max {max_lines})")

    # Check for bare numbers (numbers without context)
    bare_numbers = _find_bare_numbers(block_text)
    if bare_numbers:
        result["warnings"].append(f"{block_id} ({req['name']}): bare numbers without context: {bare_numbers[:3]}")

    # Stale data check
    if data_timestamp:
        age_hours = (datetime.now() - data_timestamp).total_seconds() / 3600
        if age_hours > 24:
            result["is_stale"] = True
            result["warnings"].append(f"{block_id} ({req['name']}): data is {age_hours:.0f}h old (stale)")

    return result


def validate_all_blocks(blocks: Dict[str, str], data_timestamps: Dict[str, datetime] = None) -> Dict:
    """
    Validate all blocks. Returns summary with overall status.
    """
    data_timestamps = data_timestamps or {}
    results = {}
    all_warnings = []
    all_errors = []
    blocks_without_consequence = []

    for block_id, block_text in blocks.items():
        ts = data_timestamps.get(block_id)
        result = validate_block(block_id, block_text, ts)
        results[block_id] = result

        all_warnings.extend(result.get("warnings", []))
        all_errors.extend(result.get("errors", []))

        req = BLOCK_REQUIREMENTS.get(block_id)
        if req and req.get("must_have_consequence") and not result.get("has_consequence"):
            blocks_without_consequence.append(block_id)

    # Overall status
    total_blocks = len(blocks)
    ok_blocks = sum(1 for r in results.values() if r.get("ok"))
    blocks_with_consequence = sum(1 for r in results.values() if r.get("has_consequence"))

    overall_ok = len(all_errors) == 0

    return {
        "ok": overall_ok,
        "total_blocks": total_blocks,
        "ok_blocks": ok_blocks,
        "blocks_with_consequence": blocks_with_consequence,
        "blocks_without_consequence": blocks_without_consequence,
        "warnings": all_warnings,
        "errors": all_errors,
        "results": results,
    }


def format_validation_report(validation: Dict) -> str:
    """Format validation results for logging."""
    lines = []
    lines.append(f"📊 Block Validation: {validation['ok_blocks']}/{validation['total_blocks']} OK")
    lines.append(f"   Consequence layer: {validation['blocks_with_consequence']}/{validation['total_blocks']} blocks")

    if validation.get("blocks_without_consequence"):
        lines.append(f"   ⚠️ Missing consequence: {', '.join(validation['blocks_without_consequence'])}")

    if validation.get("errors"):
        lines.append(f"   ❌ Errors ({len(validation['errors'])}):")
        for e in validation["errors"][:5]:
            lines.append(f"      {e}")

    if validation.get("warnings"):
        lines.append(f"   ⚠️ Warnings ({len(validation['warnings'])}):")
        for w in validation["warnings"][:10]:
            lines.append(f"      {w}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _find_bare_numbers(text: str) -> List[str]:
    """
    Find numbers that appear without context words nearby.
    A number is 'bare' if it has no context word within 20 chars.
    """
    import re

    context_words = [
        "percentile", "%ile", "cr", "lakh", "crore", "bps", "basis",
        "vs", "avg", "average", "since", "day", "week", "month",
        "high", "low", "above", "below", "support", "resistance",
        "→", "stress", "pressure", "impact", "risk",
    ]

    bare = []
    # Find numbers (Indian format or decimal)
    for match in re.finditer(r'\b\d{1,3}(?:,\d{2,3})*(?:\.\d+)?%?\b', text):
        num = match.group()
        start = max(0, match.start() - 20)
        end = min(len(text), match.end() + 20)
        context = text[start:end].lower()

        if not any(w in context for w in context_words):
            bare.append(num)

    return bare[:5]


def check_data_freshness(blocks: Dict[str, str]) -> Dict:
    """
    Check if data in blocks is fresh enough for analysis.
    Returns freshness status per block.
    """
    freshness = {}
    now = datetime.now()

    # Check for date references in block text
    for block_id, text in blocks.items():
        if not text:
            freshness[block_id] = {"status": "missing", "age_hours": None}
            continue

        # Look for today's date or recent dates
        today_str = now.strftime("%Y-%m-%d")
        yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")

        if today_str in text:
            freshness[block_id] = {"status": "fresh", "age_hours": 0}
        elif yesterday_str in text:
            freshness[block_id] = {"status": "recent", "age_hours": 24}
        else:
            freshness[block_id] = {"status": "unknown", "age_hours": None}

    return freshness


def pre_send_checklist(blocks: Dict[str, str], snapshot_data: Dict = None,
                       ai_output: str = None) -> Dict:
    """
    10 hard gates before Telegram send.
    Returns: {ok, passed, failed, warnings}
    """
    passed = []
    failed = []
    warnings = []
    snapshot = snapshot_data or {}

    # 1. Plain English summary present
    if blocks.get("simple_block"):
        passed.append("Plain English summary present")
    else:
        failed.append("MISSING: Plain English summary (Block 0)")

    # 2. Master Signal has consequence
    master = blocks.get("block_0", "")
    if any(ind in master.lower() for ind in CONSEQUENCE_INDICATORS):
        passed.append("Master Signal has consequence")
    else:
        warnings.append("Master Signal missing consequence line")

    # 3. Nifty sanity check
    nifty = snapshot.get("nifty_close")
    if nifty and nifty > 20000:
        passed.append(f"Nifty {nifty:.0f} — sanity OK")
    elif nifty:
        failed.append(f"SANITY FAIL: Nifty {nifty:.0f} < 20,000")
    else:
        warnings.append("Nifty close not available for sanity check")

    # 4. Oil sanity check
    brent = snapshot.get("brent")
    if brent and brent > 50:
        passed.append(f"Brent ${brent:.0f} — sanity OK")
    elif brent:
        failed.append(f"SANITY FAIL: Brent ${brent:.0f} < $50")
    else:
        warnings.append("Brent price not available for sanity check")

    # 5. FII has absorption ratio
    fii_block = blocks.get("block_4", "")
    if "absorption" in fii_block.lower() or "floor" in fii_block.lower():
        passed.append("FII block has absorption context")
    else:
        warnings.append("FII block missing absorption ratio")

    # 6. AI output length check
    if ai_output:
        word_count = len(ai_output.split())
        if word_count >= 50:
            passed.append(f"AI output: {word_count} words")
        else:
            failed.append(f"AI output too short: {word_count} words (min 50)")

    # 7. No hardcoded values (check for common ones)
    hardcoded_patterns = ["17,800", "67%", "soon", "expected to"]
    all_text = " ".join(blocks.values())
    found_hardcoded = [p for p in hardcoded_patterns if p in all_text.lower()]
    if not found_hardcoded:
        passed.append("No hardcoded values detected")
    else:
        warnings.append(f"Possible hardcoded values: {found_hardcoded}")

    # 8. Block validator summary
    validation = validate_all_blocks(blocks)
    if validation["ok"]:
        passed.append(f"Block validation: {validation['ok_blocks']}/{validation['total_blocks']} OK")
    else:
        failed.append(f"Block validation failed: {validation['errors']}")

    # 9. Consequence coverage
    if validation["blocks_with_consequence"] >= 2:
        passed.append(f"Consequence coverage: {validation['blocks_with_consequence']} blocks")
    else:
        warnings.append(f"Low consequence coverage: {validation['blocks_with_consequence']} blocks")

    # 10. Data freshness
    freshness = check_data_freshness(blocks)
    stale_blocks = [bid for bid, f in freshness.items() if f.get("status") == "stale"]
    if not stale_blocks:
        passed.append("All data fresh")
    else:
        warnings.append(f"Stale data in: {stale_blocks}")

    return {
        "ok": len(failed) == 0,
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
    }


def format_checklist_report(checklist: Dict) -> str:
    """Format pre-send checklist for logging."""
    lines = []
    lines.append(f"{'✅' if checklist['ok'] else '❌'} Pre-Send Checklist: {len(checklist['passed'])} passed, {len(checklist['failed'])} failed")

    for item in checklist["passed"]:
        lines.append(f"  ✅ {item}")
    for item in checklist["failed"]:
        lines.append(f"  ❌ {item}")
    for item in checklist["warnings"]:
        lines.append(f"  ⚠️ {item}")

    return "\n".join(lines)
