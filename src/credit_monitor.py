"""
Credit Rating Monitor
Sources:
  1. NSE corporate announcements API (free, no key needed)
  2. RSS feeds from CRISIL / ICRA / CARE press release pages
  3. Finnhub news filtered for rating keywords
  4. Keyword scanning of exchange filings

Agencies: CRISIL, ICRA, CARE, India Ratings, Acuite, Brickwork, INFOMERICS
"""
import os
import re
import time
import requests
import feedparser
from datetime import datetime, timedelta
from typing import List, Dict

FINNHUB_KEY = os.environ.get("FINNHUB_KEY", "")

# ── RATING KEYWORDS TO SCAN FOR ───────────────────────────────────
RATING_KEYWORDS = [
    "upgraded", "downgraded", "rating", "outlook",
    "watch negative", "watch positive", "affirmed",
    "credit rating", "CRISIL", "ICRA", "CARE",
    "India Ratings", "Ind-Ra", "Acuite", "Brickwork",
    "AAA", "AA+", "AA-", "A+", "BBB", "BB",
    "default", "D rating", "negative watch",
    "positive watch", "stable outlook", "negative outlook",
]

# ── RSS FEEDS (publicly available, no auth needed) ─────────────────
RATING_RSS_FEEDS = {
    "CRISIL":        "https://www.crisil.com/en/home/newsroom/press-releases.rss",
    "ICRA":          "https://www.icra.in/Media/MediaReleases",  # Scraped
    "CARE":          "https://www.careratings.com/press-release.aspx",  # Scraped
    "NSE_Filings":   "https://www.nseindia.com/api/corporate-announcements?index=equities",
    "MoneyControl":  "https://www.moneycontrol.com/rss/business.xml",
    "ET_Markets":    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
}

# ── NSE HEADERS ────────────────────────────────────────────────────
NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.nseindia.com/",
}

def _is_rating_related(text: str) -> bool:
    """Check if text contains any credit rating related keywords"""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in RATING_KEYWORDS)

def _extract_rating_detail(text: str) -> Dict:
    """
    Try to extract rating agency, action, and new rating from text.
    Returns structured rating change info.
    """
    text_upper = text.upper()

    # Detect agency
    agency = "Unknown"
    for a in ["CRISIL", "ICRA", "CARE", "IND-RA",
              "INDIA RATINGS", "ACUITE", "BRICKWORK"]:
        if a in text_upper:
            agency = a
            break

    # Detect action
    action = "MENTIONED"
    if any(w in text_upper for w in ["UPGR", "RAISED", "ENHANCED"]):
        action = "UPGRADED ⬆️"
    elif any(w in text_upper for w in ["DOWNGR", "LOWERED", "REDUCED", "CUT"]):
        action = "DOWNGRADED ⬇️"
    elif "DEFAULT" in text_upper:
        action = "DEFAULTED 🚨"
    elif "WATCH" in text_upper and "NEG" in text_upper:
        action = "WATCH NEGATIVE ⚠️"
    elif "WATCH" in text_upper and "POS" in text_upper:
        action = "WATCH POSITIVE 🔔"
    elif "AFFIRM" in text_upper or "REAFFIRM" in text_upper:
        action = "AFFIRMED ✅"
    elif "STABLE" in text_upper:
        action = "STABLE OUTLOOK"

    # Try to extract rating symbols
    rating_pattern = re.findall(
        r'\b(AAA|AA\+|AA-|AA|A\+|A-|A|BBB\+|BBB-|BBB|BB\+|BB-|BB|B|D)\b',
        text_upper
    )

    return {
        "agency":  agency,
        "action":  action,
        "ratings": rating_pattern[:3] if rating_pattern else [],
    }

def fetch_nse_rating_announcements() -> List[Dict]:
    """
    Fetch corporate announcements from NSE and filter rating-related ones.
    NSE announces rating changes as corporate filings.
    """
    session = requests.Session()
    session.headers.update(NSE_HEADERS)

    # Init session with homepage
    try:
        session.get("https://www.nseindia.com", timeout=15)
        time.sleep(1)
    except Exception:
        pass

    url = "https://www.nseindia.com/api/corporate-announcements?index=equities"
    results = []
    try:
        resp = session.get(url, timeout=15)
        if resp.status_code != 200:
            return []
        data = resp.json()
        items = data if isinstance(data, list) else data.get("data", [])

        for item in items[:50]:  # Check top 50 recent announcements
            subject = str(item.get("subject", ""))
            attchmnt = str(item.get("attchmnt", ""))
            combined = f"{subject} {attchmnt}"

            if _is_rating_related(combined):
                detail = _extract_rating_detail(combined)
                results.append({
                    "symbol":   item.get("symbol", ""),
                    "company":  item.get("cname",  ""),
                    "subject":  subject[:200],
                    "agency":   detail["agency"],
                    "action":   detail["action"],
                    "ratings":  detail["ratings"],
                    "date":     item.get("an_dt",  ""),
                    "source":   "NSE Announcement",
                })
    except Exception as e:
        print(f"⚠️  NSE announcements error: {e}")

    return results

def fetch_rss_rating_news() -> List[Dict]:
    """Scan RSS feeds for credit rating related news"""
    results = []
    rss_sources = {
        "ET_Markets":   "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        "MoneyControl": "https://www.moneycontrol.com/rss/business.xml",
        "LiveMint":     "https://www.livemint.com/rss/markets",
        "BusinessLine": "https://www.thehindubusinessline.com/markets/feeder/default.rss",
    }

    for source_name, rss_url in rss_sources.items():
        try:
            feed  = feedparser.parse(rss_url)
            for entry in feed.entries[:20]:
                title   = entry.get("title",   "")
                summary = entry.get("summary", "")
                combined = f"{title} {summary}"

                if _is_rating_related(combined):
                    detail = _extract_rating_detail(combined)
                    results.append({
                        "symbol":   "",
                        "company":  "",
                        "subject":  title[:200],
                        "agency":   detail["agency"],
                        "action":   detail["action"],
                        "ratings":  detail["ratings"],
                        "date":     entry.get("published", ""),
                        "url":      entry.get("link",      ""),
                        "source":   source_name,
                    })
            time.sleep(0.5)
        except Exception as e:
            print(f"⚠️  RSS feed error ({source_name}): {e}")

    return results

def fetch_finnhub_rating_news(symbols: List[str]) -> List[Dict]:
    """Fetch Finnhub company news and filter for rating mentions"""
    if not FINNHUB_KEY:
        return []
    results = []
    today  = datetime.now().strftime("%Y-%m-%d")
    week   = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    for symbol in symbols[:5]:  # Limit to 5 — respect 60/min rate limit
        nse_sym = symbol.replace(".NS", "").replace(".BO", "")
        url     = (
            f"https://finnhub.io/api/v1/company-news"
            f"?symbol={nse_sym}&from={week}&to={today}&token={FINNHUB_KEY}"
        )
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                articles = resp.json()
                for a in articles[:10]:
                    headline = a.get("headline", "")
                    if _is_rating_related(headline):
                        detail = _extract_rating_detail(headline)
                        results.append({
                            "symbol":   nse_sym,
                            "company":  "",
                            "subject":  headline[:200],
                            "agency":   detail["agency"],
                            "action":   detail["action"],
                            "ratings":  detail["ratings"],
                            "date":     str(a.get("datetime", "")),
                            "url":      a.get("url", ""),
                            "source":   "Finnhub",
                        })
        except Exception as e:
            print(f"⚠️  Finnhub rating news error ({nse_sym}): {e}")
        time.sleep(1)

    return results

def get_all_rating_events(symbols: List[str]) -> List[Dict]:
    """Aggregate all rating events from all sources"""
    print("🏦 Fetching NSE rating announcements...")
    nse_alerts = fetch_nse_rating_announcements()

    print("📰 Scanning RSS feeds for rating news...")
    rss_alerts = fetch_rss_rating_news()

    print("📡 Checking Finnhub for rating news...")
    finnhub_alerts = fetch_finnhub_rating_news(symbols)

    all_events = nse_alerts + rss_alerts + finnhub_alerts

    # Prioritise: defaults/downgrades first, then upgrades
    priority = {
        "DEFAULTED 🚨": 0,
        "DOWNGRADED ⬇️": 1,
        "WATCH NEGATIVE ⚠️": 2,
        "UPGRADED ⬆️": 3,
        "WATCH POSITIVE 🔔": 4,
        "AFFIRMED ✅": 5,
        "MENTIONED": 6,
    }
    all_events.sort(key=lambda x: priority.get(x.get("action", ""), 9))
    return all_events[:20]  # Top 20 most significant

def format_credit_alerts_message(events: List[Dict]) -> str:
    """Format credit rating alerts for Telegram"""
    if not events:
        return "🏦 *CREDIT RATINGS*\n_No rating changes detected today_"

    msg = "🏦 *CREDIT RATING ALERTS*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    for e in events[:10]:
        sym     = f"*{e['symbol']}* — " if e.get("symbol") else ""
        agency  = f"[{e['agency']}] " if e["agency"] != "Unknown" else ""
        ratings = f" → {'/'.join(e['ratings'])}" if e.get("ratings") else ""
        msg += (
            f"{e['action']}\n"
            f"{sym}{agency}{e['subject'][:100]}{ratings}\n"
            f"_Source: {e['source']}_\n\n"
        )

    return msg