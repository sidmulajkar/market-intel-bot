"""
Validation Helper — Reusable AI output validation for all jobs.

Two entry points:
  1. validate_and_send() — legacy, for callers who already have AI text
  2. ai_generate_and_validate() — universal wrapper: AI call + validate + retry + fallback
"""
import re
import hashlib
from typing import Callable, Dict, Optional


# ── Infrastructure Leakage Scrubber ──────────────────────────────

_LEAKAGE_PATTERNS = [
    "ai brief failed",
    "fallback sent",
    "fallback",
    "[MATERIAL]",             # Debug tag — consequence engine uses ⚠️ instead
    "quota exhaustion",
    "ai output fell to",
    "ai output discarded",
    "ai output too short",
    "rejected — sending fallback",
    "rejected - sending fallback",
    "ai failed",
    "manual review recommended",
    "discarded due to",
    "raw data provided instead",
    "unchanged since last send",
    "validation",
    "rejected — sending",
    "quota exceeded",
    "RESOURCE_EXHAUSTED",
    "even fallback failed",
]

_BLOCKED_PATTERNS = [
    r'[Bb]ias:\s*(Long|Short|Buy|Sell)[^\n]*',
    r'[Bb]ias:.*',
    r'[Kk]ey levels?:[^\n]*',
    r'[Uu]nless [Nn]ifty[^\n]*',
    r'[Uu]pside bias[^\n]*',
    r'[Dd]ownside bias[^\n]*',
    r'[Uu]pside[^\n]*(capped|limited|resistance)',
    r'[Dd]ownside[^\n]*(support|floor)',
    r'[Mm]onitor [^\n]*developments',
    r'[Ii]f [Nn]ifty (holds|breaks|crosses)[^\n]*',
    r'[Ww]atch:.*→.*(cut|reduce|hedge|add|raise|trim|buy|sell)',
    r'(cut|reduce|hedge|trim|raise)\s+(beta|exposure|allocation|position|weight|cash)',
    r'(avoid|prefer|accumulate)\s+[A-Z]',
    r'\b(may|likely|possibly|probably)\s+(test|hit|reach|break|slide|rally|correct|set|move|drift|remain)',
    r'\b(full|partial)\s+(defensive|hedge|cash)',
    r'\bif\s+\w+\s+(breaks|crosses|holds|sustains)\b',
    # Scenario speculative language scrub (Phase 34)
    r'fears(?!\s+data)',        # Allow "fears" only if followed by data
    r'expected(?!\s+actual)',   # Allow "expected" only if followed by actual
    r'impact(?!\s+parallel)',   # Allow "impact" only in scenario context
    r'likely(?!\s+based)',      # Allow "likely" only if followed by "based on"
    r'[Ss]uggesting\s+caution',  # "suggesting caution" — advice language
    r'[Ss]hould\s+(watch|consider|avoid|hedge|monitor|raise|cut|reduce|trim|accumulate|remain|be)',  # advisory "should"
    r'\bset\s+direction\b',      # "set direction" — prediction language
    # Structural speculation patterns (Phase 35 — P0)
    r'\b(could|would|will|might|shall)\b',              # Future tense modals
    r'if\s+.*?,\s+.*?(rally|decline|fall|rise|move|break|slide|climb)',  # If-then conditionals
    r'[Rr]ange\s+[Tt]rade[^\n]*',                       # Range trade (trading signal)
    r'(?<=\.)\s*(watch|monitor|avoid|prefer|hedge|accumulate|capitalize|stay)\b',  # Sentence-start imperatives
    r'^\s*(watch|monitor|avoid|prefer|hedge|accumulate|capitalize|stay)\b',         # Line-start imperatives
    r'(?:^|Action:\s*)(watch|monitor|avoid|prefer|hedge|accumulate|capitalize|stay|scale\s+in)\b',  # Imperatives after Action: prefix
    r'\b(oversold\s+bounce|scale\s+in\s+cautiously)\b', # Directional prediction + trading action
    r'\b(elevated|strong|weak|material|significant|moderate|substantial|robust|firm)\b(?!\s+[\d₹$%\-])',  # Unqualified adjectives (must have number after)
    r'→\s*(Nifty|Bank|Market|Sensex|Sector|Index)',    # Conditional arrow advice
    # Clone block speculation protection (T4.2)
    r'(Clone|clone|Historical Clone).*?(could|may|might|will|if|likely|possibly|probably)',
    # Posture: lines (emoji-prefixed or bare)
    r'Posture:',
    # Sector-specific advice
    r'\b(OMC|OMCs|oil\s+importers)\b',
    # Direct stock recommendations
    r'\brecommends?\b',
    # AI speculation patterns (Analyst 1: may/can + speculative verbs)
    r'may\s+influence',
    r'may\s+decline',
    r'can\s+mitigate',
    r'can\s+lead\s+to',
    r'\d{1,3}%\s+correlation',
]


def _log_scrubber_event(event: str, details: dict) -> None:
    """Log scrubber event to analytics_ledger for audit. Best-effort, no raise."""
    try:
        from src.db import save_analytics_ledger
        from datetime import datetime
        save_analytics_ledger(datetime.now().strftime("%Y-%m-%d"), "scrubber", {
            "event": event,
            **details,
        })
    except Exception:
        pass


# Lines starting with these prefixes are deterministic bot output (not AI).
# The scrubber must not strip them — they carry structured data, not speculation.
_DETERMINISTIC_PREFIX = r'^(━|📌|🟢|🔴|🟡|📊|📈|📉|⚠️|🚨)'

def _is_deterministic_line(stripped: str) -> bool:
    """Check if line is deterministic Python-generated bot output (not AI text)."""
    if not re.match(_DETERMINISTIC_PREFIX, stripped):
        return False
    # Lines containing "Posture:" or "Open Posture:" (deterministic prefix or not) are always AI
    if re.search(r'\*?Posture:', stripped):
        return False
    if re.search(r'\*?Open\s+Posture:', stripped):
        return False
    return True

def _strip_trading_signals(text: str) -> str:
    """Remove trading advice and speculative language from AI output — keep only factual statements."""
    lines = text.split('\n')
    filtered = []
    stripped_count = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            filtered.append(line)
            continue
        # Deterministic bot output lines carry structured data — skip trading signal check
        if _is_deterministic_line(stripped):
            filtered.append(line)
            continue
        is_signal = False
        for pattern in _BLOCKED_PATTERNS:
            if re.search(pattern, stripped):
                is_signal = True
                break
        if is_signal:
            stripped_count += 1
        else:
            filtered.append(line)
    if stripped_count:
        _log_scrubber_event("trading_signals_stripped", {"lines_removed": stripped_count})
    return '\n'.join(filtered)



def _scrub_leakage(text: str) -> str:
    """Detect infrastructure leakage in user-facing text.

    Returns None if leakage detected (caller should use fallback instead).
    Returns cleaned text if clean.
    """
    lower = text.lower()
    for pattern in _LEAKAGE_PATTERNS:
        if pattern in lower:
            return None
    return text


def output_scrubber(text: str) -> str:
    """Final-pass scrubber before Telegram dispatch.

    Three-stage pipeline:
      1. _scrub_leakage — catch infrastructure leakage
      2. _strip_ghost_regime — remove AI-generated regime lines
      3. _strip_trading_signals — remove trading advice

    If leakage detected, returns _deterministic_fallback({}) instead of
    None — guaranteed to produce safe text.
    """
    cleaned = _scrub_leakage(text)
    if cleaned is None:
        _log_scrubber_event("leakage_detected", {"pattern": "infrastructure_leakage"})
        return _deterministic_fallback({})
    cleaned = _strip_ghost_regime(cleaned)
    return _strip_trading_signals(cleaned)


def _strip_ghost_regime(text: str) -> str:
    """Remove AI-generated regime lines — regime is set by arbiter, not AI."""
    lines = text.split('\n')
    filtered = []
    skip_next = False
    stripped_count = 0
    for line in lines:
        stripped = line.strip()
        # Deterministic bot output carries the Arbiter's regime card — never strip it
        if _is_deterministic_line(stripped):
            skip_next = False
            filtered.append(line)
            continue
        # Match: REGIME:, emoji + REGIME:, *REGIME:, **REGIME:, etc.
        if re.match(r'^[*\s]*[\U0001F300-\U0001FAFF]*\s*REGIME[:\s]', stripped, re.IGNORECASE):
            skip_next = True
            stripped_count += 1
            continue
        # Match: Posture: lines (AI-generated, always stripped)
        if re.match(r'^[*\s]*[📌]?\s*\*?Posture:', stripped):
            skip_next = True
            stripped_count += 1
            continue
        # Match: Open Posture: lines (AI-generated)
        if re.match(r'^[*\s]*[📌]?\s*\*?Open\s+Posture:', stripped):
            skip_next = True
            stripped_count += 1
            continue
        if skip_next and re.match(r'^(Confidence|Dominant|Why|Observation|Triggers)', stripped, re.IGNORECASE):
            stripped_count += 1
            continue
        # Ghost phase labels appended below regime card — not in canonical set
        if re.match(r'^[*\s]*[🟡🔴]?\s*[*\s]*(Transition|Cautious|Recovery|Consolidation|Breakdown)\s+Phase\b', stripped, re.IGNORECASE):
            skip_next = True
            stripped_count += 1
            continue
        skip_next = False
        filtered.append(line)
    if stripped_count:
        _log_scrubber_event("ghost_regime_stripped", {"lines_removed": stripped_count})
    return '\n'.join(filtered)


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
        cleaned = _scrub_leakage(fallback)
        send_fn(cleaned if cleaned else _deterministic_fallback({}))
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
        ai_text = _strip_ghost_regime(ai_text)
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
            ai_text = _strip_ghost_regime(ai_text)
            if fmt_fn:
                send_fn(fmt_fn(ai_text))
            else:
                send_fn(ai_text)
            return True
        else:
            # Major contradiction — use fallback
            fallback = fallback_fn()
            cleaned = _scrub_leakage(fallback)
            send_fn(cleaned if cleaned else _deterministic_fallback({}))
            return False

    except Exception as e:
        print(f"   ⚠️ Validation error: {e}")
        # On validation error, send as-is (safer than silently dropping)
        ai_text = _strip_ghost_regime(ai_text)
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

    Terminal guarantee: wraps entire flow in try/except. If ANYTHING fails,
    a deterministic fallback is sent. User never sees infrastructure errors.
    """
    try:
        return _ai_generate_and_validate_inner(ai, task, prompt, ground_truth, output_type, fallback_fn, send_fn, max_retries)
    except Exception as e:
        print(f"   CRITICAL: ai_generate_and_validate total failure: {e}")
        try:
            content = fallback_fn()
            content = _scrub_leakage(content) if content else None
            if content is None:
                content = _deterministic_fallback(ground_truth)
            send_fn(content)
        except Exception:
            print(f"   CRITICAL: even fallback generation failed")
            send_fn(_deterministic_fallback(ground_truth))
        return False


def _ai_generate_and_validate_inner(
    ai,
    task: str,
    prompt: str,
    ground_truth: Dict,
    output_type: str,
    fallback_fn: Callable[[], str],
    send_fn: Callable[[str], None],
    max_retries: int = 1,
) -> bool:
    """Inner implementation — see ai_generate_and_validate for terminal wrapper."""
    config = _OUTPUT_TYPE_CONFIG.get(output_type, _OUTPUT_TYPE_CONFIG["market_close"])
    label = config["label"]
    min_words = config["min_words"]

    # Pre-flight quota check — skip AI entirely if quota exhausted
    if hasattr(ai, 'has_quota') and not ai.has_quota(task):
        print(f"   ⚠️ AI quota pre-check failed ({label}) — skipping to fallback")
        _send_fallback(fallback_fn, send_fn, ground_truth)
        return False

    # Step 1: Call AI
    try:
        draft = ai.analyze(task, prompt)
    except Exception as e:
        print(f"   AI call failed ({label}): {e}")
        _send_fallback(fallback_fn, send_fn, ground_truth)
        return False

    if not draft or not isinstance(draft, str) or len(draft.split()) < min_words:
        print(f"   AI output too short ({label})")
        _send_fallback(fallback_fn, send_fn, ground_truth)
        return False

    # Step 1b: Schema check for volume tasks (structured Forecast required)
    if task == "volume":
        try:
            if not ai._validate_forecast_schema(draft):
                print(f"   AI output lacks structured forecast ({label})")
                _send_fallback(fallback_fn, send_fn, ground_truth)
                return False
        except Exception as e:
            print(f"   Schema validation error: {e}")
            # Continue — schema check is best-effort

    # Step 2: Validate
    result = _validate_with_output_type(draft, ground_truth, config)

    if result["send"]:
        cleaned = _scrub_leakage(_strip_ghost_regime(draft))
        if cleaned is not None:
            send_fn(cleaned)
        else:
            print(f"   Leakage detected in AI output — using fallback")
            _send_fallback(fallback_fn, send_fn, ground_truth)
        return True

    # MAJOR violation — build targeted retry prompt
    if max_retries > 0 and result.get("retry_instruction"):
        retry_prompt = _build_retry_prompt(prompt, result, label)
        try:
            print(f"   Retrying {label} with targeted correction...")
            retry_draft = ai.analyze(task, retry_prompt)
            if retry_draft and isinstance(retry_draft, str) and len(retry_draft.split()) >= min_words:
                retry_result = _validate_with_output_type(retry_draft, ground_truth, config)
                if retry_result["send"]:
                    cleaned = _scrub_leakage(_strip_ghost_regime(retry_draft))
                    if cleaned is not None:
                        send_fn(cleaned)
                    else:
                        _send_fallback(fallback_fn, send_fn, ground_truth)
                    return True
                else:
                    print(f"   Retry still failed ({label}): {retry_result['reason']}")
        except Exception as e:
            print(f"   Retry AI failed ({label}): {e}")

    # All retries exhausted — fallback
    print(f"   {label} rejected — sending fallback")
    _send_fallback(fallback_fn, send_fn, ground_truth)
    return False


def _send_fallback(fallback_fn: Callable[[], str], send_fn: Callable[[str], None], ground_truth: Dict) -> None:
    """Send fallback content, scrubbed for leakage. Guaranteed to emit something."""
    try:
        content = fallback_fn()
    except Exception:
        content = _deterministic_fallback(ground_truth)
    cleaned = _scrub_leakage(content) if content else None
    if cleaned is None:
        cleaned = _deterministic_fallback(ground_truth)
    send_fn(cleaned)


def _deterministic_fallback(ground_truth: Dict) -> str:
    """Pure data summary — zero network calls, completes in <1ms."""
    lines = []

    # Flows summary if available
    fii = ground_truth.get("fii_net")
    dii = ground_truth.get("dii_net")
    if fii is not None or dii is not None:
        fii_sign = "-" if fii < 0 else "+"
        fii_str = f"FII {fii_sign}₹{abs(fii):,.0f}Cr" if fii is not None else "FII N/A"
        dii_sign = "-" if dii < 0 else "+"
        dii_str = f"DII {dii_sign}₹{abs(dii):,.0f}Cr" if dii is not None else "DII N/A"
        lines.append(f"Flows: {fii_str} | {dii_str}")

    # Absorption if meaningful
    absorption = ground_truth.get("absorption_pct")
    if absorption is not None:
        try:
            lines.append(f"Absorption: {float(absorption):.0f}% of FII flow absorbed by DII")
        except (ValueError, TypeError):
            pass

    if not lines:
        # Bare minimum — regime or nothing
        regime = ground_truth.get("cross_asset_regime")
        if regime:
            lines.append(f"Regime: {regime}")
        else:
            lines.append("No actionable data available.")
    lines.append("")
    return "\n".join(lines)


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
