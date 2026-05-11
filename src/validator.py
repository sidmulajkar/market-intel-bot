"""
News Validation Layer
Filters noise, scores source trust, deduplicates headlines
"""
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

def score_source(source_name: str) -> int:
    source_lower = source_name.lower()
    for key, score in TRUST_SCORES.items():
        if key in source_lower:
            return score
    return 4

def validate_articles(
    articles: List[Dict],
    min_trust: int = 5,
) -> List[Dict]:
    """
    Filter articles by trust score and deduplicate.
    min_trust: minimum trust score to pass (5 = moderate trust)
    """
    scored = []
    for a in articles:
        source = a.get("source", "")
        score  = score_source(source)
        if score >= min_trust:
            a["trust_score"] = score
            scored.append(a)

    return _deduplicate(scored)

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