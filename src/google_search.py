"""
Google Search Context — Enrich AI prompts with live web-grounded market data.

Uses Gemini with Google Search Retrieval to fetch fresh market context
BEFORE the main AI call. This way, even when Groq is the primary AI,
the prompt contains Google-sourced intelligence.

Usage:
    from src.google_search import get_market_context
    context = get_market_context("NIFTY 50", mode="morning")
    # Inject context['summary'] into the AI prompt

This is separate from AI engine's _try_google_search (which is a fallback).
This module runs FIRST to enrich the prompt, regardless of which AI runs.
"""
import os
from datetime import datetime
from typing import Dict, Optional

GOOGLE_KEY = os.environ.get('GOOGLE_AI_KEY', '')

# Check availability
_GOOGLE_SEARCH_AVAILABLE = False
try:
    from google import genai
    from google.genai import types
    _GOOGLE_SEARCH_AVAILABLE = bool(GOOGLE_KEY)
except ImportError:
    pass

# Cache context for the day — don't re-search on every block
_cache: Dict[str, dict] = {}
_cache_date: str = ""


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def get_market_context(symbol: str = "NIFTY 50", mode: str = "morning") -> dict:
    """Fetch Google-search-grounded market context.

    Returns a dict with:
        - summary: One-paragraph market narrative
        - key_levels: Dict of support/resistance levels
        - news_headlines: List of top 3 headlines from Google sources
        - sentiment: RISK_ON / RISK_OFF / NEUTRAL
        - sources: List of source URLs used
    """
    today = _today_str()
    cache_key = f"{symbol}_{mode}"

    # Day-level cache — same symbol + mode only searched once per day
    global _cache_date, _cache
    if _cache_date == today and cache_key in _cache:
        return _cache[cache_key]

    if not _GOOGLE_SEARCH_AVAILABLE:
        return {"ok": False, "reason": "Google Search unavailable"}

    try:
        client = genai.Client(api_key=GOOGLE_KEY)

        time_label = "opening" if mode == "morning" else "closing"
        prompt = (
            f"Provide a concise market intelligence brief for {symbol} as of "
            f"{today} {time_label} session in India. Include:\n"
            f"1. Current price level and today's move\n"
            f"2. The single most important driver today\n"
            f"3. Key support and resistance levels\n"
            f"4. One headline that captures the market mood\n"
            f"5. Overall sentiment: RISK_ON, RISK_OFF, or NEUTRAL\n\n"
            f"Keep it under 100 words. Use specific numbers. No disclaimers."
        )

        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.GoogleSearchRetrieval()],
                temperature=0.3,
                max_output_tokens=500,
            ),
        )

        result = {
            "ok": True,
            "summary": response.text,
            "sources": [],
            "mode": mode,
            "symbol": symbol,
            "fetched_at": today,
        }

        # Extract grounding sources
        if hasattr(response, 'grounding_metadata') and response.grounding_metadata:
            gm = response.grounding_metadata
            if gm.grounding_chunks:
                result["sources"] = [
                    c.uri for c in gm.grounding_chunks[:5]
                    if c.uri and c.title
                ]
                result["source_titles"] = [
                    c.title for c in gm.grounding_chunks[:5]
                    if c.uri and c.title
                ]

        # Cache
        _cache[cache_key] = result
        _cache_date = today

        print(f"   🔍 Google Search context fetched for {symbol} ({mode})")
        return result

    except Exception as e:
        print(f"⚠️  Google Search context failed: {e}")
        return {"ok": False, "reason": str(e)}


def get_google_search_context_block(context: dict) -> str:
    """Format Google Search context for injection into AI prompt.

    Returns a formatted string block, or empty if context is unavailable.
    """
    if not context.get("ok"):
        return ""

    lines = ["\n[Google Search Context — Powered by Google]\n"]
    if context.get("summary"):
        lines.append(f"AI Summary: {context['summary']}")
    if context.get("source_titles") and context.get("sources"):
        lines.append("\nSources:")
        for title, url in zip(context["source_titles"], context["sources"]):
            lines.append(f"  • {title}: {url}")
    lines.append(f"\nFetched: {context.get('fetched_at', 'unknown')}")

    return "\n".join(lines)


def get_all_context(mode: str = "morning") -> str:
    """Fetch Google Search context for all key assets in one call.

    Returns a formatted string block with NIFTY + key anchors.
    """
    if not _GOOGLE_SEARCH_AVAILABLE:
        return ""
    if os.environ.get('DRY_RUN', '').lower() in ('1', 'true', 'yes'):
        return ""

    today = _today_str()
    cache_key = f"all_{mode}"

    global _cache_date, _cache
    if _cache_date == today and cache_key in _cache:
        return get_google_search_context_block(_cache[cache_key])

    try:
        client = genai.Client(api_key=GOOGLE_KEY)

        time_label = "Indian market opening" if mode == "morning" else "Indian market closing"
        prompt = (
            f"Provide a concise global market intelligence brief for {time_label} "
            f"today ({today}). Cover:\n"
            f"1. Nifty 50: price, today's move, key level\n"
            f"2. USD/INR: current rate, trend\n"
            f"3. Brent Crude: price, impact on India\n"
            f"4. India VIX: current level, regime\n"
            f"5. US markets (S&P 500): overnight move\n"
            f"6. One headline that captures today's market theme\n"
            f"7. Overall sentiment: RISK_ON, RISK_OFF, or NEUTRAL\n\n"
            f"Keep it under 150 words. Use specific numbers with sources. "
            f"Every number must be verifiable. No disclaimers."
        )

        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.GoogleSearchRetrieval()],
                temperature=0.3,
                max_output_tokens=500,
            ),
        )

        context = {
            "ok": True,
            "summary": response.text,
            "sources": [],
            "mode": mode,
            "symbol": "ALL",
            "fetched_at": today,
        }

        if hasattr(response, 'grounding_metadata') and response.grounding_metadata:
            gm = response.grounding_metadata
            if gm.grounding_chunks:
                context["sources"] = [
                    c.uri for c in gm.grounding_chunks[:5]
                    if c.uri and c.title
                ]
                context["source_titles"] = [
                    c.title for c in gm.grounding_chunks[:5]
                    if c.uri and c.title
                ]

        _cache[cache_key] = context
        _cache_date = today

        print(f"   🔍 Google Search context fetched for all assets ({mode})")
        return get_google_search_context_block(context)

    except Exception as e:
        print(f"⚠️  Google Search all-context failed: {e}")
        return ""
