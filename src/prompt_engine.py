"""
Prompt Coherence Engine — Dynamic prompt prioritization.
Scores each data block by today's relevance, ranks, compresses noise.
Prevents attention dilution when 36 modules produce data.
"""
from typing import Dict, List, Tuple


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCK RELEVANCE SCORING
# ═══════════════════════════════════════════════════════════════════════════════

def score_block_relevance(block_name: str, block_text: str,
                           signals: Dict = None) -> int:
    """
    Score a block's relevance today (0-4).
    4 = critical (extreme signal, high hit rate, confirmed)
    0 = irrelevant (nothing to say today)
    """
    if not block_text or not block_text.strip():
        return 0

    score = 0

    # 1. Has signal fired? (non-neutral content)
    neutral_indicators = ["NEUTRAL", "INLINE", "AVERAGE", "BALANCED"]
    has_fired = not any(ind in block_text.upper() for ind in neutral_indicators)
    if has_fired:
        score += 1

    # 2. Is signal at extreme?
    extreme_indicators = ["EXTREME", "CRITICAL", "STRONGLY", "VERY HIGH",
                          "STRONG", "DEEP VALUE", "EXPENSIVE", "DEPRESSED",
                          "90th", "95th", "10th", "5th", "80th"]
    if any(ind in block_text.upper() for ind in extreme_indicators):
        score += 1

    # 3. Does signal have high hit rate?
    high_hit_indicators = ["AMPLIFIED", "hit rate", "65%", "70%", "75%", "80%"]
    if any(ind in block_text.lower() for ind in high_hit_indicators):
        score += 1

    # 4. Is signal confirmed by another?
    confirmation_indicators = ["confirmed", "corroborat", "aligned", "consistent"]
    if any(ind in block_text.lower() for ind in confirmation_indicators):
        score += 1

    # 5. Does block contain consequence layer? (India-impact framing)
    consequence_indicators = ["cad stress", "inr pressure", "annualized", "import bill",
                              "effective selling", "fii outflow", "margin compress",
                              "current account", "subsidy", "depreciation pressure"]
    if any(ind in block_text.lower() for ind in consequence_indicators):
        score += 1

    return min(5, score)


def rank_blocks(blocks: Dict[str, str], signals: Dict = None) -> List[Tuple[str, int, str]]:
    """
    Rank all blocks by relevance.
    Returns: [(block_name, score, block_text), ...] sorted by score desc.
    """
    scored = []
    for name, text in blocks.items():
        score = score_block_relevance(name, text, signals)
        scored.append((name, score, text))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


# ═══════════════════════════════════════════════════════════════════════════════
# DYNAMIC PROMPT ASSEMBLY
# ═══════════════════════════════════════════════════════════════════════════════

def assemble_coherent_prompt(master_signal: str, blocks: Dict[str, str],
                              max_words: int = 450) -> str:
    """
    Assemble a coherent prompt with dynamic prioritization.

    master_signal: formatted master signal (always included)
    blocks: {block_name: block_text}
    max_words: AI output word budget

    Returns: prioritized prompt with compressed low-relevance blocks.
    """
    # Score and rank
    ranked = rank_blocks(blocks)

    # Always include master signal (Block 0 equivalent)
    prompt_parts = [master_signal, ""]

    # Word budget allocation
    master_words = len(master_signal.split())
    remaining_budget = max_words - master_words

    # Top 4 blocks: full content (60 words each = 240 words)
    top_n = 4
    full_blocks = ranked[:top_n]
    compressed_blocks = ranked[top_n:]

    for name, score, text in full_blocks:
        if text and text.strip():
            prompt_parts.append(text)
            prompt_parts.append("")

    # Remaining blocks: compressed to 1-line summary
    if compressed_blocks:
        prompt_parts.append("[ADDITIONAL CONTEXT — compressed]")
        for name, score, text in compressed_blocks:
            if text and text.strip():
                # Extract first meaningful line
                first_line = _extract_summary(text)
                if first_line:
                    prompt_parts.append(f"  {name}: {first_line}")

    return "\n".join(prompt_parts)


def _extract_summary(text: str) -> str:
    """Extract a 1-line summary from a block."""
    lines = text.strip().split("\n")
    for line in lines:
        line = line.strip()
        # Skip headers and empty lines
        if not line or line.startswith("[") or line.startswith("━"):
            continue
        # Return first substantive line (max 100 chars)
        if len(line) > 5:
            return line[:100] + ("..." if len(line) > 100 else "")
    return ""


# ═══════════════════════════════════════════════════════════════════════════════
# PROMPT LENGTH CHECK
# ═══════════════════════════════════════════════════════════════════════════════

def check_prompt_length(prompt: str, max_words: int = 2000) -> Dict:
    """Check if prompt is within acceptable length for AI attention."""
    word_count = len(prompt.split())
    char_count = len(prompt)

    if word_count > max_words:
        status = "OVER BUDGET"
        recommendation = f"Prompt is {word_count} words (max {max_words}). Compress further."
    elif word_count > max_words * 0.8:
        status = "APPROACHING LIMIT"
        recommendation = f"Prompt is {word_count} words. Monitor for attention degradation."
    else:
        status = "OK"
        recommendation = f"Prompt is {word_count} words — within attention window."

    return {
        "word_count": word_count,
        "char_count": char_count,
        "status": status,
        "recommendation": recommendation,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Test with dummy blocks
    test_blocks = {
        "Block 1: Global Indices": "[Global Indices]\n  Nifty: 25,400 (+0.5%)\n  S&P: 5,800 (+0.3%)",
        "Block 2: Macro": "[Macro Anchors]\n  USD/INR: 83.2\n  Brent: $82",
        "Block 4: Flows": "[Flow Intelligence]\n  FII: -₹1,500Cr (bearish)\n  DII: +₹800Cr",
        "Block 5: Derivatives": "[Options]\n  PCR: 1.42 (elevated put buying)\n  GEX: negative (volatile)",
        "Block 6: News": "[News]\n  Markets mixed on global cues",
        "Block 8: Movers": "[Top Movers]\n  Reliance +2.1%, TCS -1.3%",
    }

    ranked = rank_blocks(test_blocks)
    print("Block ranking:")
    for name, score, _ in ranked:
        print(f"  {score}/4 — {name}")

    prompt = assemble_coherent_prompt(
        "[MASTER SIGNAL: CAUTIOUSLY BULLISH 58/100]", test_blocks
    )
    print(f"\nPrompt length: {len(prompt.split())} words")
    print(check_prompt_length(prompt))
