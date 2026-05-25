"""
News Validation Layer
Filters noise, scores source trust, deduplicates headlines,
checks freshness (staleness) and India linkage relevance.
"""
import os
import json
import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict

TRUST_SCORES = {
    "reuters":           10,
    "bloomberg":         10,
    "bseindia":          10,
    "nseindia":          10,
    "sebi":              10,
    "moneycontrol":       8,
    "economictimes":      8,
    "livemint":           8,
    "financialexpress":   7,
    "cnbc":               8,
    "marketwatch":        8,
    "wsj":                9,
    "ft.com":             9,
    "hindubusinessline":  7,
    "business-standard":  7,
    "finnhub":            7,
}

# ── News staleness cache ────────────────────────────────────────
_SEEN_CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".news_seen.json")
_CACHE_TTL_HOURS = 24


def _load_seen_cache() -> Dict[str, float]:
    """Load headline seen-cache from disk. Auto-cleanses expired entries."""
    if not os.path.exists(_SEEN_CACHE_FILE):
        return {}
    try:
        with open(_SEEN_CACHE_FILE) as f:
            cache = json.load(f)
        # Cleanse expired entries
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=_CACHE_TTL_HOURS)).timestamp()
        cache = {k: v for k, v in cache.items() if v > cutoff}
        return cache
    except (json.JSONDecodeError, IOError):
        return {}


def _save_seen_cache(cache: Dict[str, float]):
    """Persist headline seen-cache to disk."""
    try:
        with open(_SEEN_CACHE_FILE, "w") as f:
            json.dump(cache, f)
    except IOError:
        pass


def _check_staleness(articles: List[Dict]) -> List[Dict]:
    """
    Tag articles with seen_before/freshness_score if headline appeared in last 24h.
    Also saves current headlines to cache for future runs.
    """
    cache = _load_seen_cache()
    now = datetime.now(timezone.utc)

    for article in articles:
        headline = article.get("headline", "").lower().strip()
        if not headline:
            continue

        # Check if this or a near-duplicate was seen before
        seen_at = None
        for cached_headline, timestamp in cache.items():
            # Exact match
            if cached_headline == headline:
                seen_at = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                break
            # Near-duplicate (word overlap > 0.5)
            words_a = set(cached_headline.split())
            words_b = set(headline.split())
            if len(words_a) > 3 and len(words_b) > 3:
                overlap = len(words_a & words_b) / max(len(words_a | words_b), 1)
                if overlap > 0.5:
                    seen_at = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                    break

        if seen_at:
            article["seen_before"] = True
            article["first_seen_at"] = seen_at.isoformat()
            age_hours = (now - seen_at).total_seconds() / 3600
            # Freshness: 10 = just published, 0 = >24h old
            article["freshness_score"] = max(0, round(10 - (age_hours / _CACHE_TTL_HOURS) * 10))
        else:
            article["seen_before"] = False
            article["freshness_score"] = 10
            cache[headline] = now.timestamp()

    # Save updated cache
    _save_seen_cache(cache)
    return articles


# ── India linkage scoring ───────────────────────────────────────
_INDIA_DIRECT = re.compile(
    r'\b(india|indian|nifty|sensex|nse|bse|rbi|sebi|rupee|inr|'
    r'reliance|tcs|infosys|infy|hdfc bank|icici|wipro|tata|bharti|'
    r'adani|jsw|asian paints|maruti|sun pharma|dr reddy|itc|'
    r'bajaj finance|kotak|axis bank|sbi|larsen|lt|'
    r'india\'s|india-focused|domestic|bharat|'
    r'mumbai|delhi|bangalore|chennai|kolkata|'
    r'sensex|banknifty|nifty50|midcap|smallcap)\b',
    re.IGNORECASE
)

_INDIA_MACRO = re.compile(
    r'\b(fed(eral reserve)?|interest rate|hike|cut|pause|'
    r'crude oil|brent|wti|oil prices?|gold prices?|'
    r'china gdp|china economy|pakistan|sri lanka|bangladesh|middle east|'
    r'us election|geopolitical|war|sanction|tariff|'
    r'fii|foreign investor|emerging market|em flow|'
    r'inflation|cpi|pp[i]|trade deficit|current account|'
    r'semiconductor|chip|pharma|it services|outsourcing|'
    r'us dollar|dxy|strengthening dollar|weak dollar)\b',
    re.IGNORECASE
)


def _check_india_linkage(article: Dict) -> int:
    """Score article's India relevance: 10=direct, 7=macro, 6=sector, 3=no impact."""
    text = f"{article.get('headline', '')} {article.get('summary', '')} {article.get('snippet', '')}"
    text_lower = text.lower()

    # Direct India mentions
    if _INDIA_DIRECT.search(text):
        return 10

    # Global macro that affects India
    if _INDIA_MACRO.search(text):
        # Check if it's about a specific non-India company with no India angle
        # SpaceX valuation leapfrogging Berkshire = no India impact
        if any(kw in text_lower for kw in [
            'spacex', 'imax', 'berkshire hathaway', 'tesla', 'apple',
            'amazon', 'google', 'microsoft', 'meta', 'netflix',
            'disney', 'nike', 'cocacola', 'mcdonald', 'starbucks'
        ]):
            # These companies only matter for India if there's a specific India angle
            if any(kw in text_lower for kw in [
                'india', 'nse', 'bse', 'outsourcing', 'supply chain',
                'vendor', 'partner', 'subsidiary', 'export'
            ]):
                return 7
            return 3
        return 7

    # Check for sector/theme that could affect Indian peers
    if any(kw in text_lower for kw in [
        'sector', 'industry', 'banking', 'auto sales', 'cement',
        'steel', 'telecom', 'fintech', 'ev ', 'electric vehicle'
    ]):
        return 6

    return 3


def validate_articles(
    articles: List[Dict],
    min_trust: int = 5,
    min_india_linkage: int = 5,
) -> List[Dict]:
    """
    Filter articles by trust score, India linkage relevance, and deduplicate.
    min_trust: minimum trust score to pass (5 = moderate trust)
    min_india_linkage: minimum India relevance score (5 = must have macro relevance)
    """
    scored = []
    for a in articles:
        source = a.get("source", "")
        trust  = score_source(source)
        if trust >= min_trust:
            a["trust_score"] = trust
            a["india_linkage"] = _check_india_linkage(a)
            scored.append(a)

    # Filter by India linkage — but keep Bloomberg/Reuters (trust 9-10) as global context
    linkage_filtered = []
    for a in scored:
        if a["india_linkage"] >= min_india_linkage:
            linkage_filtered.append(a)
        elif a["trust_score"] >= 9:
            # High-trust global source — keep but tag
            a["india_linkage_note"] = "(Global context)"
            linkage_filtered.append(a)

    return _deduplicate(linkage_filtered)


def score_source(source_name: str) -> int:
    source_lower = source_name.lower()
    for key, score in TRUST_SCORES.items():
        if key in source_lower:
            return score
    return 4


def _deduplicate(articles: List[Dict]) -> List[Dict]:
    """Remove near-duplicate headlines using word overlap"""
    if len(articles) <= 1:
        return articles

    unique     = []
    seen_words = []

    for article in articles:
        headline = article.get("headline", "").lower()
        words    = set(headline.split())

        is_duplicate = False
        for prev_words in seen_words:
            if len(words) > 0 and len(prev_words) > 0:
                overlap = len(words & prev_words) / max(len(words | prev_words), 1)
                if overlap > 0.6:
                    is_duplicate = True
                    break

        if not is_duplicate:
            unique.append(article)
            seen_words.append(words)

    return unique


def assess_sentiment_consensus(sentiments: List[dict]) -> str:
    """Return consensus sentiment from multiple FinBERT results"""
    if not sentiments:
        return "neutral"
    totals = {"positive": 0.0, "negative": 0.0, "neutral": 0.0}
    for s in sentiments:
        for label, score in s.items():
            if label in totals:
                totals[label] += score
    return max(totals, key=totals.get)
