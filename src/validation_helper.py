"""
Validation Helper — Reusable AI output validation for all jobs.

Two entry points:
  1. validate_and_send() — legacy, for callers who already have AI text
  2. ai_generate_and_validate() — universal wrapper: AI call + validate + retry + fallback
"""
from typing import Callable, Dict, Optional


def validate_and_send(
    ai_text: str,
    valid_index: dict,
    fallback_fn,
    send_fn,
    fmt_fn=None,
    extra_ground_truth: Optional[dict] = None,
    min_words: int = 50,
) -> bool:
    """Validate AI output against ground truth, send or fallback.

    Args:
        ai_text: The AI-generated text to validate.
        valid_index: Dict from fetch_global_indices, with "India" entry containing Nifty data.
        fallback_fn: Callable that returns fallback text when validation fails.
        send_fn: Callable to send text (e.g., send_text).
        fmt_fn: Optional callable to format the text before sending (e.g., fmt_morning_report).
        extra_ground_truth: Additional ground_truth entries from the caller (e.g., fii_net, vix).
        min_words: Minimum word count for valid AI response.

    Returns:
        True if AI output was sent, False if fallback was used.
    """
    # Basic sanity check
    if not ai_text or not isinstance(ai_text, str) or len(ai_text.split()) < min_words:
        fallback = fallback_fn()
        send_fn(fallback)
        return False

    # Build minimal ground_truth from available data
    ground_truth: Dict = {}

    # Nifty from valid_index
    india = valid_index.get("India", {})
    if india.get("price"):
        ground_truth["nifty_close"] = india["price"]

    # Extra data from caller (FII, VIX, etc.)
    if extra_ground_truth:
        ground_truth.update(extra_ground_truth)

    if not ground_truth:
        # No ground truth available — skip validation, send as-is
        if fmt_fn:
            send_fn(fmt_fn(ai_text))
        else:
            send_fn(ai_text)
        return True

    # Run full validation
    try:
        from src.output_validator import validate_output
        result = validate_output(ai_text, ground_truth)

        if result["send"]:
            if fmt_fn:
                send_fn(fmt_fn(ai_text))
            else:
                send_fn(ai_text)
            return True
        else:
            # Major contradiction — use fallback
            fallback = fallback_fn()
            send_fn(fallback)
            return False

    except Exception as e:
        print(f"   ⚠️ Validation error: {e}")
        # On validation error, send as-is (safer than silently dropping)
        if fmt_fn:
            send_fn(fmt_fn(ai_text))
        else:
            send_fn(ai_text)
        return True


# ═══════════════════════════════════════════════════════════════════
# UNIVERSAL AI WRAPPER — Generate, Validate, Retry, Fallback
# ═══════════════════════════════════════════════════════════════════

_OUTPUT_TYPE_CONFIG = {
    "market_open": {
        "label": "Market Open Brief",
        "checks": ["stale_level", "hallucinated_pct", "advice"],
        "min_words": 30,
    },
    "market_close": {
        "label": "Market Close Summary",
        "checks": ["stale_level", "hallucinated_pct", "advice"],
        "min_words": 40,
    },
    "midday_scan": {
        "label": "Midday Scan",
        "checks": ["stale_level", "advice"],
        "min_words": 30,
    },
    "weekly_digest": {
        "label": "Weekly Digest",
        "checks": ["stale_level", "hallucinated_pct", "advice", "confidence"],
        "min_words": 50,
    },
    "market_intel": {
        "label": "Market Intel",
        "checks": ["stale_level", "hallucinated_pct", "advice", "confidence"],
        "min_words": 50,
    },
}


def ai_generate_and_validate(
    ai,
    task: str,
    prompt: str,
    ground_truth: Dict,
    output_type: str,
    fallback_fn: Callable[[], str],
    send_fn: Callable[[str], None],
    max_retries: int = 1,
) -> bool:
    """Universal wrapper: call AI, validate output, retry on MAJOR violation, fallback.

    Args:
        ai: AIEngine instance.
        task: "fast" or "volume" (passed to ai.analyze).
        prompt: The prompt to send to AI.
        ground_truth: Dict with current market data for validation.
            Must include at minimum: nifty_close (for stale level check).
            Optional: brent, gold, usdinr, vix_percentile, fii_net, dii_net,
                      absorption_pct, bull_bear_score, cross_asset_regime.
        output_type: One of "market_open", "market_close", "midday_scan", "weekly_digest".
        fallback_fn: Callable returning fallback text if all retries fail.
        send_fn: Callable to send final text.
        max_retries: Number of targeted retries after MAJOR violation (default 1).

    Returns:
        True if validated AI output was sent, False if fallback was used.
    """
    config = _OUTPUT_TYPE_CONFIG.get(output_type, _OUTPUT_TYPE_CONFIG["market_close"])
    label = config["label"]
    min_words = config["min_words"]

    # Step 1: Call AI
    try:
        draft = ai.analyze(task, prompt)
    except Exception as e:
        print(f"   ⚠️ AI failed ({label}): {e}")
        send_fn(fallback_fn())
        return False

    if not draft or not isinstance(draft, str) or len(draft.split()) < min_words:
        print(f"   ⚠️ AI output too short ({label})")
        send_fn(fallback_fn())
        return False

    # Step 2: Validate
    result = _validate_with_output_type(draft, ground_truth, config)

    if result["send"]:
        send_fn(draft)
        return True

    # MAJOR violation — build targeted retry prompt
    if max_retries > 0 and result.get("retry_instruction"):
        retry_prompt = _build_retry_prompt(prompt, result, label)
        try:
            print(f"   🔄 Retrying {label} with targeted correction...")
            retry_draft = ai.analyze(task, retry_prompt)
            if retry_draft and isinstance(retry_draft, str) and len(retry_draft.split()) >= min_words:
                retry_result = _validate_with_output_type(retry_draft, ground_truth, config)
                if retry_result["send"]:
                    send_fn(retry_draft)
                    return True
                else:
                    print(f"   ⚠️ Retry still failed ({label}): {retry_result['reason']}")
        except Exception as e:
            print(f"   ⚠️ Retry AI failed ({label}): {e}")

    # All retries exhausted — fallback
    print(f"   ⚠️ {label} rejected — sending fallback")
    send_fn(fallback_fn())
    return False


def _validate_with_output_type(text: str, ground_truth: Dict, config: Dict) -> Dict:
    """Run output_validator with checks scoped to output type."""
    from src.output_validator import validate_output

    result = validate_output(text, ground_truth)

    # Filter issues by output type configuration
    active_checks = config.get("checks", ["stale_level", "hallucinated_pct", "advice"])

    # validate_output returns send=False only on MAJOR contradiction
    base_is_major = result.get("send") is False

    active_issues = []
    for issue in result.get("issues", []):
        issue_upper = issue.upper()
        is_active = False

        # Map issue type to active checks
        if "STALE LEVEL" in issue_upper and "stale_level" in active_checks:
            is_active = True
        if ("HALLUCINATED %:" in issue_upper or ("HALLUCINATED" in issue_upper and "CONFIDENCE" not in issue_upper)) and "hallucinated_pct" in active_checks:
            is_active = True
        if "ADVICE VIOLATION" in issue_upper and "advice" in active_checks:
            is_active = True
        if "HALLUCINATED CONFIDENCE" in issue_upper and "confidence" in active_checks:
            is_active = True
        # Consistency checks always active
        if "CONSISTENCY" in issue_upper:
            is_active = True
        if "TONE MISMATCH" in issue_upper or "FLOW MISMATCH" in issue_upper or "NUMBER MISMATCH" in issue_upper:
            is_active = True
        if "COMMODITY MISMATCH" in issue_upper or "FX MISMATCH" in issue_upper:
            is_active = True
        # Consequence absence is always MINOR
        if "CONSEQUENCE ABSENT" in issue_upper:
            is_active = True

        if is_active:
            active_issues.append(issue)

    # Determine effective severity
    active_has_major = False
    if base_is_major:
        # At least one active issue is a MAJOR-type issue
        active_has_major = any(
            t in issue.upper()
            for issue in active_issues
            for t in ["STALE LEVEL", "HALLUCINATED", "ADVICE VIOLATION", "CONFIDENCE",
                      "COMMODITY MISMATCH", "FX MISMATCH", "TONE MISMATCH", "FLOW MISMATCH"]
        )

    if active_has_major:
        retry_instruction = _build_retry_instruction(active_issues, ground_truth)
        return {
            "send": False,
            "reason": f"Major contradiction in {config['label']}",
            "issues": active_issues,
            "fallback_text": None,
            "retry_instruction": retry_instruction,
        }

    # MINOR or OK — pass through
    result["issues"] = active_issues
    result["send"] = True
    result["retry_instruction"] = None
    return result


def _build_retry_instruction(issues: list, ground_truth: Dict) -> str:
    """Build a targeted retry prompt that tells AI exactly what to fix."""
    parts = []
    for issue in issues:
        if "STALE LEVEL" in issue:
            nifty = ground_truth.get("nifty_close")
            if nifty:
                parts.append(
                    f"Price levels in your output are stale. Current Nifty is {nifty:,.0f}. "
                    f"Use only these validated levels: support {nifty*0.98:,.0f}, "
                    f"resistance {nifty*1.02:,.0f}."
                )
        elif "ADVICE VIOLATION" in issue:
            parts.append(
                "Remove any trade recommendations (buy/sell/long/short/consider adding). "
                "Use conditional language: 'If X holds → Y likely'."
            )
        elif "HALLUCINATED %" in issue or "HALLUCINATED CONFIDENCE" in issue:
            parts.append(
                "Remove invented probabilities and confidence levels. "
                "Do not assign percentages to outcomes. Use conditional framing."
            )
        elif "CONSISTENCY" in issue:
            parts.append(
                "Your narrative contradicts the data. Align tone with: "
                + ", ".join(
                    f"{k}={v}" for k, v in ground_truth.items()
                    if v is not None and isinstance(v, (int, float, str)) and len(str(v)) < 20
                )
            )

    return "REVISE your previous output. Fix ONLY these specific issues, keep everything else:\n" + "\n".join(parts)


def _build_retry_prompt(original_prompt: str, result: Dict, label: str) -> str:
    """Wrap original prompt + retry instruction for the AI retry call."""
    retry_instruction = result.get("retry_instruction", "")
    if not retry_instruction:
        return original_prompt
    return (
        f"Rewrite your previous {label} output. Your previous response contained these errors:\n"
        f"{retry_instruction}\n\n"
        f"Original context:\n{original_prompt}"
    )


def build_ground_truth_from_index(valid_index: dict, extra: Optional[Dict] = None) -> Dict:
    """Build minimal ground_truth dict from fetch_global_indices output.

    Extracts Nifty spot price from the "India" entry.
    """
    gt: Dict = {}
    india = valid_index.get("India", {})
    if india.get("price"):
        gt["nifty_close"] = india["price"]
    if extra:
        gt.update(extra)
    return gt
