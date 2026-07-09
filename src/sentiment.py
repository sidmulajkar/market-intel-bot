"""
Sentiment Engine — Layered Sentiment Proxy
Primary: Gemini (batch, zero-shot, model fallback chain)
Fallback: Custom Financial Keyword Lexicon (pure Python, 0ms)

Replaces FinBERT (HuggingFace Inference API) which was:
  - DNS-unreliable in GHA (154s timeout)
  - ~440MB cold-start overhead
  - Single-headline-per-call (N API calls for N headlines)
"""
import os
import json
import re
from typing import Dict, List, Optional

# ── Financial Keyword Lexicon (pure Python, 0 dependencies) ─────
# Polarity: -1.0 (extreme bearish) to +1.0 (extreme bullish)
# Sources: Loughran-McDonald financial dictionary, Henry's word list,
#          SentiBignomics subset, custom Indian market terms
FINANCIAL_LEXICON: Dict[str, float] = {
    # ── Strong Bullish (+0.8 to +1.0) ──
    "beat estimates": 0.9, "record high": 0.9, "all-time high": 0.9,
    "bull run": 0.9, "strong buy": 0.9, "outperform": 0.8,
    "upgrade": 0.8, "bullish": 0.8, "positive outlook": 0.8,
    "dividend hike": 0.9, "bonus issue": 0.8, "stock split": 0.8,
    "profit surge": 0.9, "revenue jump": 0.8, "sales jump": 0.8,
    "guidance raised": 0.9, "guidance upgrade": 0.9,
    "order win": 0.8, "contract win": 0.8, "expansion plan": 0.8,
    "capacity expansion": 0.8, "maiden profit": 0.8,
    "buyback": 0.8, "share buyback": 0.8,
    "credit rating upgrade": 0.9, "rating upgrade": 0.9,
    "rate cut": 0.8, "repo rate cut": 0.8,
    "fii buying": 0.8, "dii buying": 0.8,
    "inflow": 0.7, "strong inflow": 0.8,
    "turnaround": 0.8, "profit turnaround": 0.8,
    "breakout": 0.8, "debt reduction": 0.7,
    "margin expansion": 0.8, "margin improvement": 0.7,

    # ── Moderate Bullish (+0.3 to +0.7) ──
    "rises": 0.4, "rose": 0.4, "gain": 0.4, "gains": 0.4,
    "higher": 0.3, "surge": 0.6, "surges": 0.6, "surged": 0.6,
    "rally": 0.6, "rallies": 0.6, "rallied": 0.6,
    "jump": 0.5, "jumps": 0.5, "jumped": 0.5,
    "climb": 0.4, "climbs": 0.4, "climbed": 0.4,
    "recovery": 0.5, "rebound": 0.5, "bounce": 0.4,
    "uptick": 0.3, "uptrend": 0.5,
    "overweight": 0.5, "accumulate": 0.5, "add": 0.3,
    "positive": 0.4, "optimistic": 0.5, "confidence": 0.4,
    "stable": 0.3, "steady": 0.3, "resilient": 0.5,
    "growth": 0.5, "grew": 0.4, "growing": 0.4,
    "profit": 0.5, "profitable": 0.6, "profitability": 0.6,
    "revenue growth": 0.6, "sales growth": 0.6,
    "ebitda": 0.4, "margin": 0.3,
    "outstanding": 0.5, "improve": 0.4, "improvement": 0.4,
    "uptick in volume": 0.4, "strong demand": 0.6,
    "robust": 0.6, "momentum": 0.4,
    "easing": 0.4, "softening": 0.3,
    "acquisition": 0.4, "merger": 0.4,
    "bull": 0.5, "bulls": 0.6,
    "overbought": 0.3, "support": 0.4,
    "reform": 0.5, "stimulus": 0.5,
    "rate hold": 0.3, "status quo": 0.2,

    # ── Neutral (near zero) ──
    "unchanged": 0.0, "flat": 0.0, "mixed": 0.0,
    "rangebound": 0.0, "consolidation": 0.0,
    "announced": 0.0, "announcement": 0.0,
    "meeting": 0.0, "discussion": 0.0, "review": 0.0,
    "expected": 0.0, "in line": 0.0, "in-line": 0.0,
    "opening": 0.0, "closed": 0.0, "session": 0.0,
    "trading": 0.0, "volume": 0.0, "turnover": 0.0,
    "board meeting": 0.0, "agm": 0.0,
    "to consider": 0.0, "approval": 0.0,

    # ── Moderate Bearish (-0.3 to -0.7) ──
    "falls": -0.4, "fell": -0.4, "fall": -0.4,
    "drop": -0.5, "drops": -0.5, "dropped": -0.5,
    "decline": -0.5, "declines": -0.5, "declined": -0.5,
    "lower": -0.3, "down": -0.3,
    "slip": -0.4, "slips": -0.4, "slipped": -0.4,
    "slide": -0.5, "slides": -0.5, "slid": -0.5,
    "sell-off": -0.6, "selloff": -0.6,
    "downgrade": -0.6, "underperform": -0.6,
    "bearish": -0.6, "negative outlook": -0.6,
    "weak": -0.4, "weakness": -0.5, "weaken": -0.4,
    "volatile": -0.3, "volatility": -0.3,
    "uncertainty": -0.4, "uncertain": -0.4,
    "subdued": -0.4, "lackluster": -0.4,
    "underweight": -0.4, "reduce": -0.4, "sell": -0.5,
    "profit warning": -0.7, "guidance cut": -0.7,
    "revenue miss": -0.6, "earnings miss": -0.6,
    "fii selling": -0.6, "dii selling": -0.4,
    "outflow": -0.5, "capital outflow": -0.6,
    "slowdown": -0.5, "slowing": -0.4,
    "debt": -0.3, "leverage": -0.3,
    "layoff": -0.5, "layoffs": -0.5,
    "inflation": -0.4, "inflationary": -0.5,
    "rate hike": -0.6, "repo rate hike": -0.6,
    "crash": -0.7, "correction": -0.4,
    "bear": -0.5, "bears": -0.5,
    "distribution": -0.3, "profit booking": -0.4,

    # ── Strong Bearish (-0.8 to -1.0) ──
    "plunge": -0.8, "plunges": -0.8, "plunged": -0.8,
    "tank": -0.8, "tanks": -0.8, "tanked": -0.8,
    "nosedive": -0.9, "freefall": -0.9,
    "wiped out": -0.9, "collapse": -0.9,
    "bankruptcy": -1.0, "insolvency": -1.0, "default": -0.9,
    "fraud": -0.9, "scam": -0.9,
    "sebi inquiry": -0.8, "sebi probe": -0.8,
    "rating downgrade": -0.9, "credit rating downgrade": -0.9,
    "recession": -0.8, "depression": -0.9,
    "crisis": -0.8, "meltdown": -0.9,
    "loss": -0.6, "net loss": -0.7, "operating loss": -0.7,
    "write-off": -0.7, "impairment": -0.6,
    "provision": -0.4,
    "fear": -0.5, "panic": -0.7,
    "bloodbath": -0.9, "massacre": -0.9,
    "war": -0.6, "conflict": -0.5, "sanctions": -0.6,
    "pandemic": -0.7, "lockdown": -0.6,
}


def sentiment_via_lexicon(text: str) -> Dict[str, float]:
    """Pure Python financial sentiment using keyword lexicon.
    
    Returns {positive: x, negative: y, neutral: z} with scores summing to 1.0.
    Takes ~0.5ms. Zero network calls. Zero dependencies beyond stdlib.
    """
    if not text or not text.strip():
        return {"neutral": 1.0}
    
    text_lower = text.lower()
    total_score = 0.0
    match_count = 0
    
    # Score multi-word phrases first (longer = higher priority)
    matched = set()
    for phrase, score in sorted(FINANCIAL_LEXICON.items(), key=lambda x: -len(x[0])):
        if phrase in text_lower:
            count = text_lower.count(phrase)
            total_score += score * count
            match_count += count
            matched.add(phrase)
    
    # Single-word checks for unigrams not already matched as phrases
    words = re.findall(r"[a-z]+", text_lower)
    for word in words:
        if word in FINANCIAL_LEXICON and word not in matched:
            # Check not already counted via phrase match
            already_counted = any(word in phrase for phrase in matched)
            if not already_counted:
                total_score += FINANCIAL_LEXICON[word]
                match_count += 1
    
    if match_count == 0:
        return {"neutral": 1.0}
    
    avg_score = total_score / match_count  # -1 to +1
    
    # Convert to positive/negative/neutral distribution
    # Maps -1..+1 to a 3-way distribution
    if avg_score > 0:
        pos = min(1.0, avg_score)
        neg = 0.0
        neu = 1.0 - pos
    elif avg_score < 0:
        neg = min(1.0, abs(avg_score))
        pos = 0.0
        neu = 1.0 - neg
    else:
        pos, neg, neu = 0.0, 0.0, 1.0
    
    return {
        "positive": round(pos, 3),
        "negative": round(neg, 3),
        "neutral": round(neu, 3),
        "score": round(avg_score, 3),
        "method": "lexicon",
    }


def batch_sentiment_via_lexicon(headlines: List[str]) -> List[Dict[str, float]]:
    """Batch sentiment via lexicon. ~1ms for 20 headlines."""
    return [sentiment_via_lexicon(h) for h in headlines]


# Gemini model fallback chain (synced with ai_engine.py)
_GEMINI_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
]


def batch_sentiment_via_gemini(
    headlines: List[str],
    google_client=None,
    models: Optional[List[str]] = None,
) -> Optional[List[Dict[str, float]]]:
    """Batch sentiment via Gemini.
    
    Sends all headlines in ONE API call with a structured JSON prompt.
    Tries model chain on 404. Returns list of dicts or None on failure.
    """
    if not google_client or not headlines:
        return None
    
    items = []
    for i, h in enumerate(headlines):
        if h and h.strip():
            items.append({"id": i, "headline": h.strip()[:200]})
    
    if not items:
        return None
    
    prompt = f"""Analyze these {len(items)} financial news headlines for market sentiment.

For EACH headline, classify sentiment as positive, negative, or neutral from a 
market/investor perspective. Return a JSON array of objects with:
  - id: integer (0-based index, starting from 0)
  - positive: float 0-1
  - negative: float 0-1  
  - neutral: float 0-1
(scores must sum to 1.0 per headline)

Headlines:
{json.dumps([item["headline"] for item in items], indent=2)}

Return ONLY valid JSON. No explanation. No markdown."""
    
    model_chain = models or _GEMINI_MODELS
    from google.genai import types as genai_types
    
    for model in model_chain:
        try:
            resp = google_client.models.generate_content(
                model=model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    max_output_tokens=1024,
                    temperature=0.1,
                ),
            )
            
            raw = resp.text.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
                raw = raw.rsplit("```", 1)[0]
            
            results = json.loads(raw)
            if not isinstance(results, list):
                return None
            
            ordered = []
            result_map = {r.get("id"): r for r in results if isinstance(r, dict) and "id" in r}
            for i in range(len(headlines)):
                if i in result_map:
                    r = result_map[i]
                    ordered.append({
                        "positive": float(r.get("positive", 0)),
                        "negative": float(r.get("negative", 0)),
                        "neutral": float(r.get("neutral", 1)),
                        "method": "gemini",
                    })
                else:
                    ordered.append({"positive": 0, "negative": 0, "neutral": 1, "method": "gemini"})
            
            return ordered
        except Exception as e:
            if "404" in str(e) or "not found" in str(e).lower():
                continue
            print(f"   ⚠️ Gemini ({model}) batch sentiment: {e}")
            return None
    return None


def batch_sentiment(
    headlines: List[str],
    google_client=None,
) -> List[Dict[str, float]]:
    """Layered sentiment: Gemini primary → lexicon fallback.
    
    Tier 1: Gemini 2.5 Flash-Lite (batch, ~0.8s, reliable Google infra)
    Tier 2: Financial keyword lexicon (pure Python, ~1ms, zero network)
    
    Returns list of {positive, negative, neutral, method} in headline order.
    """
    # Tier 1: Gemini
    try:
        result = batch_sentiment_via_gemini(headlines, google_client)
        if result and len(result) == len(headlines):
            return result
    except Exception:
        pass
    
    # Tier 2: Lexicon fallback
    return batch_sentiment_via_lexicon(headlines)


def consensus_sentiment(results: List[Dict[str, float]]) -> str:
    """Aggregate multiple sentiment results into 'positive'/'negative'/'neutral'."""
    if not results:
        return "neutral"
    totals = {"positive": 0.0, "negative": 0.0, "neutral": 0.0}
    for r in results:
        for label in totals:
            totals[label] += r.get(label, 0)
    return max(totals, key=totals.get)
