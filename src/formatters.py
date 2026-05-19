"""
Formatters — Data to Prompt Block conversion
Each formatter returns a string (or "" on failure) for master_prompt.txt
Phase 1: Blocks 1, 2, 4, 6, 8, 10
Intelligence Layer: context_engine + options_engine integrated
Quant Layer: percentiles, cross-signals, significance labels
"""
from typing import Dict, Optional


# ═══════════════════════════════════════════════════════════════════════
# PERCENTILE LOOKUP — Lightweight, cached
# ═══════════════════════════════════════════════════════════════════════

_percentile_cache = {}  # in-memory cache per session

# Metrics where negative = extreme (more negative = higher percentile)
# Default: 1 = higher value = more extreme
_METRIC_DIRECTION = {
    "fii_net": -1,      # negative outflow = extreme selling
    "dii_net": 1,       # positive = extreme buying
    "india_vix": 1,     # high VIX = extreme fear
    "cboe_vix": 1,
    "fear_greed_score": 1,
    "bull_bear_score": 1,
    "pcr": 1,           # high PCR = extreme bearish
}


def _flip_percentile(pct: float, metric: str) -> float:
    """Flip percentile for metrics where negative values are extreme."""
    if _METRIC_DIRECTION.get(metric, 1) < 0:
        return 100 - pct
    return pct


def get_percentile(metric: str, current_value: float, window: str = "1Y") -> str:
    """
    Get percentile context for a metric from daily_market_snapshot.
    Returns: "65th %ile (1Y)" or "(%ile: insufficient data)" if < 10 data points.
    Caches results per session to avoid repeated DB queries.
    """
    if not current_value or current_value == 0:
        return ""

    cache_key = f"{metric}_{window}"
    if cache_key in _percentile_cache:
        history = _percentile_cache[cache_key]
    else:
        try:
            from src.db import get_snapshot_metric_history
            days = {"1Y": 252, "2Y": 504, "6M": 126}.get(window, 252)
            history = get_snapshot_metric_history(metric, days=days)
            _percentile_cache[cache_key] = history
        except Exception:
            return ""

    if not history or len(history) < 10:
        return "(%ile: insufficient data)"

    try:
        from src.rolling_quant import percentile_rank
        history_values = [v for _, v in history if v is not None]
        result = percentile_rank(current_value, history_values)
        pct = _flip_percentile(result.get("percentile", 50), metric)
        return f"{pct:.0f}th %ile ({window})"
    except Exception:
        return ""


def get_percentile_value(metric: str, current_value: float, window: str = "1Y") -> Optional[float]:
    """
    Get raw percentile value (0-100) for mechanism_map arbitration.
    Returns float or None if insufficient data.
    """
    if not current_value or current_value == 0:
        return None

    cache_key = f"{metric}_{window}"
    if cache_key in _percentile_cache:
        history = _percentile_cache[cache_key]
    else:
        try:
            from src.db import get_snapshot_metric_history
            days = {"1Y": 252, "2Y": 504, "6M": 126}.get(window, 252)
            history = get_snapshot_metric_history(metric, days=days)
            _percentile_cache[cache_key] = history
        except Exception:
            return None

    if not history or len(history) < 10:
        return None

    try:
        from src.rolling_quant import percentile_rank
        history_values = [v for _, v in history if v is not None]
        result = percentile_rank(current_value, history_values)
        return _flip_percentile(result.get("percentile", 50), metric)
    except Exception:
        return None


def format_4q(what: str, how_big: str, why: str, so_what: str) -> str:
    """
    4-question format template: WHAT | HOW BIG | WHY → SO WHAT
    Every output block should use this pattern.
    """
    parts = [what]
    if how_big:
        parts.append(how_big)
    if why:
        parts.append(why)
    if so_what:
        parts.append(f"→ {so_what}")
    return " | ".join(parts)


# ═══════════════════════════════════════════════════════════════════════
# INLINE GLOSSARY — Explain terms once per session
# ═══════════════════════════════════════════════════════════════════════

GLOSSARY_TIER1 = {  # Always explain — genuinely confusing terms
    "PCR": "put-call ratio — fear gauge",
    "GEX": "dealer gamma — amplifies moves",
    "DXY": "US dollar index",
    "Brier": "prediction accuracy score (0=perfect, 1=worst)",
    "z-score": "standard deviations from mean",
    "max pain": "price where most options expire worthless",
}

GLOSSARY_TIER2 = {  # Explain once per day — most users know after week 1
    "FII": "foreign institutional investors",
    "DII": "domestic institutional investors",
    "VIX": "India fear gauge",
    "SIP": "systematic investment plan",
    "AMFI": "Association of Mutual Funds in India",
    "CAD": "current account deficit",
    "NIM": "net interest margin",
    "OMC": "oil marketing company",
    "NBFC": "non-banking financial company",
    "HHI": "concentration index",
    "ERP": "equity risk premium",
    "RSI": "relative strength index",
    "MACD": "moving average convergence divergence",
    "OI": "open interest",
    "DMA": "daily moving average",
}

_shown_terms = set()
_brief_count = 0  # tracks which brief we're on


def format_with_glossary(term: str, value: str) -> str:
    """
    Two-tier glossary — explain once per BRIEF, not per block.
    Tier 1: Confusing terms (PCR, GEX, DXY) — explain once per brief
    Tier 2: Common terms (FII, VIX, SIP) — explain once per brief
    """
    global _shown_terms, _brief_count
    brief_key = f"{_brief_count}_{term}"

    # Both tiers: explain once per brief, then abbreviation
    if term in GLOSSARY_TIER1 and brief_key not in _shown_terms:
        _shown_terms.add(brief_key)
        return f"{term} [{GLOSSARY_TIER1[term]}] {value}"

    if term in GLOSSARY_TIER2 and brief_key not in _shown_terms:
        _shown_terms.add(brief_key)
        return f"{term} [{GLOSSARY_TIER2[term]}] {value}"

    return f"{term} {value}"


def reset_glossary():
    """Reset shown terms (call at start of each new brief)."""
    global _shown_terms, _brief_count
    _shown_terms = set()
    _brief_count += 1


# ═══════════════════════════════════════════════════════════════════════
# OUTPUT QUALITY SCORECARD — Pre-send validation
# ═══════════════════════════════════════════════════════════════════════

def validate_output_quality(output_text: str, data_available: bool = True) -> dict:
    """
    Score output on 4 quality checks.
    When data is available: implication MANDATORY + 1 optional.
    When data is unavailable: skip all checks (can't blame formatter).
    Returns: {"score": int, "checks": dict, "pass": bool}
    """
    import re
    checks = {}

    if not data_available:
        # Data fetch failed — can't validate, pass unconditionally
        return {"score": 0, "checks": {"implication": True, "decisive": True, "data_backed": True, "mechanism": True}, "pass": True}

    # MANDATORY — India linkage must be present
    checks["implication"] = any(w in output_text.lower() for w in [
        "impact", "expect", "watch", "risk", "india", "nifty", "fii", "dii",
        "bfsi", "omc", "bank", "it ", "pharma", "metal", "auto",
    ])

    # OPTIONAL — best effort
    lean_words = ["bullish", "bearish", "lean", "direction", "risk-on", "risk-off"]
    checks["decisive"] = any(w in output_text.lower() for w in lean_words)

    checks["data_backed"] = bool(re.search(r'[\d,]+(?:Cr|%|th|st|nd|rd|B|M|K)', output_text))

    why_words = ["because", "driven", "due to", "why", "→", "transmission"]
    checks["mechanism"] = any(w in output_text.lower() for w in why_words)

    optional_pass = sum([checks["decisive"], checks["data_backed"], checks["mechanism"]])
    passed = checks["implication"] and optional_pass >= 1

    return {
        "score": sum(checks.values()),
        "checks": checks,
        "pass": passed,
    }


# Index name mapping for proper labels
INDEX_NAMES = {
    "^GSPC": "S&P 500", "^BVSP": "Bovespa", "^GSPTSE": "S&P/TSX",
    "^MXX": "IPC", "^IPSA": "IPSA", "^KS11": "KOSPI",
    "^STI": "STI", "^TWII": "TWII", "^HSI": "Hang Seng",
    "^N225": "Nikkei 225", "000001.SS": "SSE Composite",
    "^AXJO": "ASX 200", "^NSEI": "Nifty 50", "FTSEMIB.MI": "FTSE MIB",
    "^FTSE": "FTSE 100", "^GDAXI": "DAX", "^SSMI": "SMI", "^FCHI": "CAC 40",
}


# ═══════════════════════════════════════════════════════════════════════
# CATASTROPHIC FALLBACK — Ensures no blank output
# ═══════════════════════════════════════════════════════════════════════

def check_all_blocks_empty(*blocks: str) -> bool:
    """
    Check if all formatter blocks returned empty strings.
    If all empty, return True to trigger fallback message.
    """
    return all(not block.strip() for block in blocks)


def get_fallback_message() -> str:
    """
    Fallback message when all data sources fail.
    NEVER returns empty string — this prevents blank Telegram messages.
    """
    return (
        "🚨 *Market Intel Unavailable*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "All data sources temporarily unavailable.\n"
        "Please try again in the next update cycle."
    )


# ─────────────────────────────────────────────────────────────────────
# BLOCK 1: GLOBAL INDICES
# ─────────────────────────────────────────────────────────────────────
def format_global_indices(index_data: dict) -> str:
    """
    Convert 18 global indices to BLOCK 1 string.
    Uses proper index names (S&P 500, Nifty 50, etc.) instead of just country codes.
    """
    if not index_data:
        return ""

    try:
        lines = []
        for country, d in index_data.items():
            if not d.get("ok"):
                continue
            flag   = d.get("flag", "")
            price  = d.get("price", 0)
            change = d.get("change_pct", 0)
            status = d.get("status", "")
            sign   = "+" if change >= 0 else ""
            sym    = d.get("symbol", "")
            name   = INDEX_NAMES.get(sym, country)
            # Show "Country (Index Name)" for clarity
            label = f"{country} ({name})" if name != country else country
            lines.append(f"{flag} {label}: {sign}{change:.2f}% | {price:,.0f} [{status}]")

        if not lines:
            return ""

        return "Global Indices:\n" + "\n".join(lines)
    except Exception as e:
        print(f"⚠️ format_global_indices: {e}")
        return ""


# ─────────────────────────────────────────────────────────────────────
# BLOCK 2: MACRO ANCHORS (USDINR, Brent, Gold)
# ─────────────────────────────────────────────────────────────────────
def format_macro_anchors(anchor_data: list) -> str:
    """
    Convert macro anchors to BLOCK 2 string.
    Includes weekly change and status for each anchor.
    """
    if not anchor_data:
        return ""

    try:
        lines = []
        for item in anchor_data:
            if not item.get("ok"):
                continue

            name   = item.get("name", "")
            price  = item.get("price")
            change = item.get("change_pct")
            weekly = item.get("weekly_change_pct")
            status = item.get("status", "flat")

            if price is None or change is None:
                continue

            sign      = "+" if change >= 0 else ""
            weekly_s  = f" | Weekly: {sign}{weekly:.2f}%" if weekly else ""
            status_e  = "📈" if status == "up" else ("📉" if status == "down" else "➡️")

            # Yield tickers: show as percentage
            if "Yield" in name:
                formatted = f"{name}: {price:.2f}% ({sign}{change:.2f}%){weekly_s} {status_e}"
            # Currency pairs: no prefix, show as-is
            elif "/" in name:
                formatted = f"{name}: {price:,.2f} ({sign}{change:.2f}%){weekly_s} {status_e}"
            # India VIX / CBOE VIX: no currency
            elif "VIX" in name.upper():
                formatted = f"{name}: {price:.2f} ({sign}{change:.2f}%){weekly_s} {status_e}"
            # INR pairs
            elif "INR" in name.upper() or "Nifty" in name:
                formatted = f"{name}: ₹{price:,.2f} ({sign}{change:.2f}%){weekly_s} {status_e}"
            # Dollar-denominated
            else:
                formatted = f"{name}: ${price:,.2f} ({sign}{change:.2f}%){weekly_s} {status_e}"
            lines.append(formatted)

        if not lines:
            return ""

        return "Macro Anchors:\n" + "\n".join(lines)
    except Exception as e:
        print(f"⚠️ format_macro_anchors: {e}")
        return ""


# ─────────────────────────────────────────────────────────────────────
# VALUATION BLOCK (appended to Block 2)
# ─────────────────────────────────────────────────────────────────────
def format_valuation_block() -> str:
    """
    Fetch and format Nifty valuation metrics with historical context.
    Appended to Block 2 (Macro Anchors).
    """
    try:
        from src.valuation_engine import fetch_nifty_valuation, format_valuation, compute_equity_risk_premium
        from src.db import save_valuation_snapshot, get_valuation_history
        from src.quant_enrichment import compute_percentile
        from datetime import datetime

        val = fetch_nifty_valuation()
        if not val or not val.get("ok"):
            return ""

        # Save snapshot for historical percentile
        today = datetime.now().strftime("%Y-%m-%d")
        save_valuation_snapshot(
            today, val["index"], val["pe"],
            pb=val.get("pb"), div_yield=val.get("dividend_yield"),
            earnings_yield=val.get("earnings_yield"),
        )

        # Get historical P/E for percentile
        history = get_valuation_history(val["index"], days=1095)  # 3 years
        historical_pe = [h["pe"] for h in history if h.get("pe")]

        # Get G-Sec yield (approximate from macro anchors or use default)
        # Try to extract from anchor data — if not available, use recent typical value
        g_sec_yield = 7.1  # Approximate 10Y G-Sec yield
        try:
            import yfinance as yf
            # Indian 10Y G-Sec — ticker may not always work
            gsec = yf.Ticker("^NSEIGS").history(period="5d")
            if not gsec.empty:
                g_sec_yield = float(gsec["Close"].iloc[-1])
        except Exception:
            pass  # Use default

        # Format output
        lines = [f"\n[Valuation — {val['index']}]"]
        lines.append(f"P/E: {val['pe']}x | Earnings Yield: {val['earnings_yield']}%")

        if val.get("pb"):
            lines.append(f"P/B: {val['pb']}x")
        if val.get("dividend_yield"):
            lines.append(f"Div Yield: {val['dividend_yield']}%")

        # Equity Risk Premium
        erp = compute_equity_risk_premium(val["earnings_yield"], g_sec_yield)
        lines.append(f"Equity Risk Premium: {erp['premium']:+.2f}% ({erp['label']})")

        # Reverse DCF
        from src.valuation_engine import compute_reverse_dcf
        rdcf = compute_reverse_dcf(val["pe"])
        if rdcf.get("ok"):
            lines.append(f"Reverse DCF: {rdcf['implied_growth_pct']}% implied growth — {rdcf['assessment']}")

        # Historical percentile
        if historical_pe and len(historical_pe) >= 5:
            pct = compute_percentile(val["pe"], historical_pe)
            if pct.get("percentile") is not None:
                lines.append(f"P/E: {pct['percentile']}th percentile of 3Y ({pct['label']})")

        return "\n".join(lines)

    except Exception as e:
        print(f"⚠️ format_valuation_block: {e}")
        return ""


# ─────────────────────────────────────────────────────────────────────
# BLOCK 4: FLOW INTELLIGENCE (FII/DII)
# ─────────────────────────────────────────────────────────────────────
def format_flows() -> str:
    """
    Compute weekly FII/DII net + 4-week trend + daily breakdown + significance.
    Returns BLOCK 4 string with quant-level detail.
    """
    try:
        from src.db import get_fii_dii_flows
        import pandas as pd

        rows = get_fii_dii_flows(days=45)

        if not rows or len(rows) < 3:
            return ""

        df = pd.DataFrame(rows)
        df["date"]   = pd.to_datetime(df["date"])
        df["fiinet_cr"] = df["fiinet_cr"].astype(float)
        df["diinet_cr"] = df["diinet_cr"].astype(float)
        df = df.sort_values("date")

        # ── Latest day analysis ──
        latest = df.iloc[-1]
        fii_latest = latest["fiinet_cr"]
        dii_latest = latest["diinet_cr"]
        latest_date = latest["date"].strftime("%d %b")

        # ── Consecutive days streak ──
        fii_streak = 0
        for i in range(len(df) - 1, -1, -1):
            if df.iloc[i]["fiinet_cr"] < 0:
                fii_streak += 1
            else:
                break
        fii_buy_streak = 0
        for i in range(len(df) - 1, -1, -1):
            if df.iloc[i]["fiinet_cr"] > 0:
                fii_buy_streak += 1
            else:
                break

        # ── 5-day FII stats ──
        last_5 = df.tail(5)
        fii_5d_total = last_5["fiinet_cr"].sum()
        fii_5d_avg = last_5["fiinet_cr"].mean()
        largest_sell_day = last_5["fiinet_cr"].min()
        largest_buy_day = last_5["fiinet_cr"].max()

        # ── 20-day rolling average (z-score context) ──
        if len(df) >= 20:
            fii_20d_avg = df["fiinet_cr"].tail(20).mean()
            fii_20d_std = df["fiinet_cr"].tail(20).std()
            if fii_20d_std > 0:
                fii_z = (fii_latest - fii_20d_avg) / fii_20d_std
            else:
                fii_z = 0
        else:
            fii_20d_avg = df["fiinet_cr"].mean()
            fii_z = 0

        # ── Group by week ──
        df["year"] = df["date"].dt.isocalendar().year
        df["week"] = df["date"].dt.isocalendar().week
        df["yw"]   = df["year"].astype(str) + "_" + df["week"].astype(str)

        weekly = df.groupby("yw").agg(
            date_start=("date", "min"),
            fiinet_cr=("fiinet_cr", "sum"),
            diinet_cr=("diinet_cr", "sum")
        ).reset_index().sort_values("date_start")

        # Use last completed week (>= 3 days)
        valid_weeks = []
        for yw in weekly["yw"].values:
            count = len(df[df["yw"] == yw])
            if count >= 3:
                valid_weeks.append(yw)

        if not valid_weeks:
            return ""

        # Last valid week
        last_yw   = valid_weeks[-1]
        last_week = weekly[weekly["yw"] == last_yw].iloc[0]
        day_count = len(df[df["yw"] == last_yw])

        # If last week has < 3 days, use previous
        if day_count < 3 and len(valid_weeks) >= 2:
            last_yw   = valid_weeks[-2]
            last_week = weekly[weekly["yw"] == last_yw].iloc[0]

        fii_net = last_week["fiinet_cr"]
        dii_net = last_week["diinet_cr"]
        net     = fii_net + dii_net

        # ── DII absorption ratio ──
        if fii_net < 0 and dii_net > 0:
            absorption = (dii_net / abs(fii_net)) * 100
            if absorption > 80:
                absorb_label = f"DII absorbing {absorption:.0f}% of FII sell — strong floor"
            elif absorption > 50:
                absorb_label = f"DII absorbing {absorption:.0f}% of FII sell — partial support"
            else:
                absorb_label = f"DII absorbing {absorption:.0f}% of FII sell — weak support"
        elif fii_net > 0:
            absorb_label = "FII buying — DII absorption not relevant"
        else:
            absorb_label = "Both FII/DII direction unclear"

        # ── 4-week FII trend ──
        recent_yws = valid_weeks[-4:]
        fii_nets = []
        for yw in recent_yws:
            w = weekly[weekly["yw"] == yw].iloc[0]
            fii_nets.append(w["fiinet_cr"])

        if len(fii_nets) >= 4:
            neg_count = sum(1 for x in fii_nets if x < 0)
            if neg_count >= 3 and fii_nets[-1] < fii_nets[-2]:
                trend_label = "deteriorating"
            elif neg_count <= 1 and fii_nets[-1] > fii_nets[-2]:
                trend_label = "improving"
            else:
                trend_label = "mixed"
            trend_str = f"4-week FII trend: " + " | ".join(
                [f"Wk-{4-len(fii_nets)+i+1}: {x:+.0f}" for i, x in enumerate(fii_nets)
            ]) + f" ({trend_label})"
        else:
            wks = len(fii_nets)
            trend_str = f"4-week trend: ({wks} weeks) " + " | ".join(
                [f"Wk-{i+1}: {x:+.0f}" for i, x in enumerate(reversed(fii_nets))]
            )

        # ── Build output ──
        lines = [
            f"Flow Intelligence (FII/DII):",
            f"Latest day ({latest_date}): FII {fii_latest:+.0f} Cr | DII {dii_latest:+.0f} Cr",
        ]

        # Streak info
        if fii_streak >= 3:
            lines.append(f"🔴 FII selling streak: {fii_streak} consecutive days")
        elif fii_buy_streak >= 3:
            lines.append(f"🟢 FII buying streak: {fii_buy_streak} consecutive days")

        # Weekly summary
        lines.append(f"Last week: FII {fii_net:+.0f} Cr | DII {dii_net:+.0f} Cr | Net {net:+.0f} Cr")

        # Z-score
        if abs(fii_z) > 1.0:
            z_label = "sharp outflow" if fii_z < 0 else "sharp inflow"
            lines.append(f"FII z-score: {fii_z:+.1f} ({z_label} vs 20D avg)")

        # 5-day stats
        lines.append(f"5-day FII: total {fii_5d_total:+.0f} Cr | avg {fii_5d_avg:+.0f} Cr | "
                     f"range [{largest_sell_day:+.0f}, {largest_buy_day:+.0f}]")

        # DII absorption
        lines.append(absorb_label)

        # Trend
        lines.append(trend_str)

        return "\n".join(lines)

    except Exception as e:
        print(f"⚠️ format_flows: {e}")
        return ""


# ─────────────────────────────────────────────────────────────────────
# BLOCK 6: NEWS INTELLIGENCE
# ─────────────────────────────────────────────────────────────────────
def format_news(global_articles: list, indian_articles: list = None) -> str:
    """
    Convert validated news to BLOCK 6 string.
    Splits into Global News, Indian News, and Data Signals sections.
    Data sources (NSE, BSE, SEBI) are separated from news articles.
    """
    if not global_articles and not indian_articles:
        return ""

    try:
        from src.quant_enrichment import enrich_news_articles

        # Data sources (not news — flow/market data)
        DATA_SOURCES = {"NSE", "BSE", "SEBI", "AMFI", "RBI"}

        sections = []
        data_lines = []

        # ── Global News ──
        if global_articles:
            global_enriched = enrich_news_articles(global_articles[:10])
            global_news = []
            for article in global_enriched[:5]:
                line = _format_news_line(article)
                if line:
                    source = article.get("source", "")
                    if any(ds in source.upper() for ds in DATA_SOURCES):
                        data_lines.append(line.replace("⦿", "📊"))
                    else:
                        global_news.append(line)
            if global_news:
                sections.append("Global News:\n" + "\n".join(global_news))

        # ── Indian News ──
        if indian_articles:
            indian_enriched = enrich_news_articles(indian_articles[:10])
            indian_news = []
            for article in indian_enriched[:5]:
                line = _format_news_line(article)
                if line:
                    source = article.get("source", "")
                    if any(ds in source.upper() for ds in DATA_SOURCES):
                        data_lines.append(line.replace("⦿", "📊"))
                    else:
                        indian_news.append(line)
            if indian_news:
                sections.append("India News:\n" + "\n".join(indian_news))

        # ── Data Signals (from NSE/BSE/SEBI — not news articles) ──
        if data_lines:
            sections.insert(0, "Data Signals:\n" + "\n".join(data_lines))

        if not sections:
            return ""

        result = "News Intelligence (sorted by impact):\n\n" + "\n\n".join(sections)

        # Contrarian sentiment extreme detection
        try:
            from src.quant_enrichment import compute_sentiment_extreme
            all_articles = (global_articles or []) + (indian_articles or [])
            sent_extreme = compute_sentiment_extreme(all_articles)
            if sent_extreme.get("ok"):
                result += f"\n\n[Sentiment Signal]\n{sent_extreme['signal']}"
                if sent_extreme["direction"] != "neutral":
                    result += f"\n({sent_extreme['pct_very_negative']:.0f}% very negative, {sent_extreme['pct_very_positive']:.0f}% very positive)"
        except Exception:
            pass  # Non-critical

        return result
    except Exception as e:
        print(f"⚠️ format_news: {e}")
        return ""


def _format_news_line(article: dict) -> str:
    """Format a single news article line — editorial style with India linkage."""
    headline = article.get("headline", "")[:100]
    source   = article.get("source", "unknown")
    numbers  = article.get("extracted_numbers", "")

    # Detect mechanism trigger from headline
    india_link = ""
    try:
        from src.mechanism_map import get_mechanism_for_news, get_india_linkage_for_event
        mechanism = get_mechanism_for_news(headline)
        if mechanism:
            india_link = get_india_linkage_for_event(mechanism["key"])
    except Exception:
        pass  # isolate mechanism failures from news output

    # Clean editorial format — impact/sentiment still computed upstream for sorting
    if numbers:
        line = f"⦿ {headline.rstrip('.')} ({numbers}). ({source})"
    else:
        line = f"⦿ {headline.rstrip('.')} ({source})"

    # Add India linkage if mechanism detected
    if india_link:
        line += f"\n   → {india_link}"

    return line


# ─────────────────────────────────────────────────────────────────────
# BLOCK 7: INSIDER / BULK DEAL ACTIVITY
# ─────────────────────────────────────────────────────────────────────
def format_insider_activity() -> str:
    """
    Fetch and format NSE bulk + block deal activity for Block 7.
    Data is ~10 days old (SEBI publication lag).
    Returns BLOCK 7 string.
    """
    try:
        from src.insider_tracker import get_market_insider_activity
        data = get_market_insider_activity(days=10)
        if not data.get("ok"):
            return ""

        lines = []
        lines.append(f"[Insider / Bulk Activity — {data['date_range']}]")
        lines.append(f"Bulk: {data['bulk_count']} deals | Block: {data['block_count']} deals | {len(data['symbols'])} symbols\n")

        # Top 5 symbols by net flow
        for sf in data["symbol_flows"][:5]:
            net = sf["net_val_cr"]
            sign = "+" if net >= 0 else ""
            emoji = "🟢" if net > 0 else "🔴"
            lines.append(
                f"{emoji} {sf['symbol']}: In ₹{sf['buy_val_cr']:.0f}Cr | "
                f"Out ₹{sf['sell_val_cr']:.0f}Cr | Net {sign}{net:.0f}Cr"
            )

        if not lines:
            return ""
        return "\n".join(lines)
    except Exception as e:
        print(f"⚠️ format_insider_activity: {e}")
        return ""


# ─────────────────────────────────────────────────────────────────────
# BLOCK 8: WATCHLIST
# ─────────────────────────────────────────────────────────────────────
def format_watchlist(watchlist_data: dict) -> str:
    """
    Convert watchlist data to BLOCK 8 string.
    Computes MA20, 5D momentum, 1M return from close_series.
    Adds significance labels for notable moves.
    Appends technical analysis (RSI, S/R, MACD) for each symbol.
    """
    if not watchlist_data:
        return ""

    try:
        from src.technical_analysis import compute_full_analysis, format_technical_analysis

        lines = []
        ta_lines = []
        for symbol, d in watchlist_data.items():
            if not d.get("ok"):
                continue

            price        = d.get("price", 0)
            day_change   = d.get("day_change", 0)
            volume       = d.get("volume", 0)
            avg_volume   = d.get("avg_volume", 1)
            close_series = d.get("close_series", [])

            # Volume spike with significance
            vol_ratio = volume / avg_volume if avg_volume > 0 else 0
            if vol_ratio > 3.0:
                vol_str = f"Vol spike: {vol_ratio:.1f}x 20D avg 🔥"
            elif vol_ratio > 2.0:
                vol_str = f"Vol spike: {vol_ratio:.1f}x 20D avg"
            else:
                vol_str = f"Vol: {vol_ratio:.1f}x 20D avg"

            # MA20
            ma20_val = None
            ma20_diff = None
            if len(close_series) >= 20:
                ma20_val = sum(close_series[-20:]) / 20
                ma20_diff = ((price - ma20_val) / ma20_val * 100) if ma20_val else 0
                ma_status = "above" if ma20_diff > 0 else "below"
                if abs(ma20_diff) > 5:
                    ma20_str = f"MA20: {ma_status} ({ma20_diff:+.1f}%) ⚡"
                else:
                    ma20_str = f"MA20: {ma_status} ({ma20_diff:+.1f}%)"
            else:
                ma20_str = "MA20: N/A"

            # 5D momentum with significance
            if len(close_series) >= 2:
                prev_5d = close_series[-6] if len(close_series) > 5 else close_series[0]
                mom_5d = ((price - prev_5d) / prev_5d * 100) if prev_5d else 0
                if abs(mom_5d) > 5:
                    mom5d_str = f"5D mom: {mom_5d:+.1f}% ⚡"
                else:
                    mom5d_str = f"5D mom: {mom_5d:+.1f}%"
            else:
                mom5d_str = "5D mom: N/A"

            # 1M return
            if len(close_series) >= 5:
                month_start = close_series[0]
                mom_1m = ((price - month_start) / month_start * 100) if month_start else 0
                mom1m_str = f"1M: {mom_1m:+.1f}%"
            else:
                mom1m_str = "1M: N/A"

            sign = "+" if day_change >= 0 else ""
            lines.append(f"{symbol}: ₹{price:,.0f} ({sign}{day_change:+.1f}%) | {vol_str} | {ma20_str} | {mom5d_str} | {mom1m_str}")

            # Technical analysis for this symbol
            if len(close_series) >= 20:
                ta = compute_full_analysis(close_series, symbol)
                ta_str = format_technical_analysis(ta)
                if ta_str:
                    ta_lines.append(ta_str)

        if not lines:
            return ""

        result = "Watchlist:\n" + "\n".join(lines)

        # Append technical analysis section
        if ta_lines:
            result += "\n\n[Technical Analysis — Key Levels]\n" + "\n\n".join(ta_lines)

        return result
    except Exception as e:
        print(f"⚠️ format_watchlist: {e}")
        return ""


# ─────────────────────────────────────────────────────────────────────
# BLOCK 10: MF FLOW INTELLIGENCE
# ─────────────────────────────────────────────────────────────────────
def format_mf_flows() -> str:
    """
    Compute anomaly vs 3M avg, thematic signals, top5, SIP trend from DB.
    Returns BLOCK 10 string.
    """
    try:
        from src.db import get_mf_flows
        import pandas as pd

        rows = get_mf_flows(months=4)

        if not rows or len(rows) < 5:
            return ""

        df = pd.DataFrame(rows)
        df["month"]      = pd.to_datetime(df["month"])
        df["amount_cr"]   = df["amount_cr"].astype(float)
        if "sip_amount_cr" in df.columns:
            df["sip_amount_cr"] = pd.to_numeric(df["sip_amount_cr"], errors="coerce")

        current_month  = df["month"].max()
        current_df     = df[df["month"] == current_month]
        prior_months   = df[df["month"] < current_month]

        if current_df.empty or len(prior_months) < 1:
            return ""

        # ── Category flows ──
        cat_parts = [f"{r['category']}: {r['amount_cr']:+.0f} Cr" for _, r in current_df.iterrows()]
        # Data freshness indicator
        data_date = current_month.strftime('%Y-%m-%d')
        category_block = f"[Category Flows — {current_month.strftime('%b %Y')} | Data: {data_date}]\n" + " | ".join(cat_parts)

        # ── Anomaly vs 3M avg ──
        anomaly_lines = []
        for _, row in current_df.iterrows():
            cat  = row["category"]
            curr = row["amount_cr"]
            prior_cat = prior_months[prior_months["category"] == cat]
            if len(prior_cat) >= 3:
                avg_3m = prior_cat["amount_cr"].mean()
                delta  = curr - avg_3m
                if avg_3m != 0:
                    pct_vs = (delta / abs(avg_3m)) * 100
                    anomaly_lines.append(
                        f"{cat}: {curr:+.0f} Cr (vs 3M avg {avg_3m:+.0f} Cr; {pct_vs:+.0f}% vs avg)"
                    )
                else:
                    anomaly_lines.append(f"{cat}: {curr:+.0f} Cr (vs 3M avg: N/A)")
            else:
                anomaly_lines.append(f"{cat}: {curr:+.0f} Cr (insufficient history)")
        anomaly_block = "[Anomaly vs 3M Avg]\n" + "\n".join(anomaly_lines)

        # ── Thematic signals (with pace annualization) ──
        import calendar as _cal
        from datetime import datetime as _dt
        thematic_lines = []
        sector_df = current_df[current_df["category"].str.contains(
            "Sector|Infra|IT|PSU|Thematic", case=False, na=False
        )]
        # Days elapsed in current month for pace projection
        cm_date = current_month.to_pydatetime() if hasattr(current_month, 'to_pydatetime') else current_month
        days_in_month = _cal.monthrange(cm_date.year, cm_date.month)[1]
        today = _dt.now()
        if today.month == cm_date.month and today.year == cm_date.year:
            days_elapsed = today.day
        else:
            days_elapsed = days_in_month  # past month = full month

        for _, row in sector_df.iterrows():
            cat  = row["category"]
            curr = row["amount_cr"]
            prior_s = prior_months[prior_months["category"] == cat].sort_values("month", ascending=False)

            # Compute annualized pace for current month
            pace_str = ""
            if days_elapsed > 0 and curr != 0:
                monthly_pace = (curr / days_elapsed) * 22  # 22 avg trading days/month
                annualized_pace = monthly_pace * 12
                if len(prior_s) >= 3:
                    prior_3m_avg = prior_s["amount_cr"].head(3).mean()
                    prior_annualized = prior_3m_avg * 12
                    if prior_annualized != 0:
                        pace_delta_pct = ((annualized_pace / abs(prior_annualized)) - 1) * 100
                        if abs(pace_delta_pct) > 30:
                            pace_label = "accelerating" if pace_delta_pct > 0 else "decelerating"
                            pace_str = f" (pace: ₹{annualized_pace:,.0f}Cr/yr vs avg ₹{prior_annualized:,.0f}Cr/yr → {pace_delta_pct:+.0f}% {pace_label})"

            if len(prior_s) >= 2:
                if curr > 0 and all(prior_s["amount_cr"] > 0):
                    streak = sum(1 for x in prior_s["amount_cr"] if x > 0) + 1
                    if pace_str:
                        thematic_lines.append(f"{cat}: +₹{curr:.0f}Cr MTD{pace_str}")
                    else:
                        thematic_lines.append(f"{cat}: +₹{curr:.0f}Cr ({streak}th consecutive inflow)")
                elif curr < 0 and all(prior_s["amount_cr"] < 0):
                    streak = sum(1 for x in prior_s["amount_cr"] if x < 0) + 1
                    if pace_str:
                        thematic_lines.append(f"{cat}: ₹{curr:.0f}Cr MTD{pace_str}")
                    else:
                        thematic_lines.append(f"{cat}: ₹{curr:.0f}Cr ({streak}th consecutive outflow)")
                else:
                    if pace_str:
                        thematic_lines.append(f"{cat}: {curr:+.0f}Cr MTD{pace_str}")
                    else:
                        thematic_lines.append(f"{cat}: {curr:+.0f}Cr")
            else:
                thematic_lines.append(f"{cat}: {curr:+.0f}Cr")
        thematic_block = "[Thematic/Segment Signals]\n" + "\n".join(thematic_lines) if thematic_lines else ""

        # ── Top 5 gainers/losers ──
        sorted_df = current_df.sort_values("amount_cr", ascending=False)
        gainers = sorted_df.head(5)
        losers  = sorted_df.tail(5).iloc[::-1]
        gainer_lines = [f"{i+1}) {r['category']}: {r['amount_cr']:+.0f} Cr" for i, (_, r) in enumerate(gainers.iterrows())]
        loser_lines  = [f"{i+1}) {r['category']}: {r['amount_cr']:+.0f} Cr" for i, (_, r) in enumerate(losers.iterrows())]
        top5_block = "[Top 5 Gainers]\n" + "\n".join(gainer_lines) + "\n\n[Top 5 Losers]\n" + "\n".join(loser_lines)

        # ── SIP trend ──
        sip_curr = current_df["sip_amount_cr"].sum() if "sip_amount_cr" in current_df else None
        if pd.notna(sip_curr) and sip_curr > 0:
            prev_month = prior_months["month"].max()
            sip_prev   = prior_months[prior_months["month"] == prev_month]["sip_amount_cr"].sum()
            if pd.notna(sip_prev) and sip_prev > 0:
                if sip_curr > sip_prev * 1.01:
                    sip_trend = f"SIP: {sip_curr:,.0f} Cr (vs prior month {sip_prev:,.0f} Cr; rising)"
                elif sip_curr < sip_prev * 0.99:
                    sip_trend = f"SIP: {sip_curr:,.0f} Cr (vs prior month {sip_prev:,.0f} Cr; falling)"
                else:
                    sip_trend = f"SIP: {sip_curr:,.0f} Cr (vs prior month {sip_prev:,.0f} Cr; flat)"
            else:
                sip_trend = f"SIP: {sip_curr:,.0f} Cr"
        else:
            sip_trend = "SIP trend: NOT AVAILABLE"
        sip_block = "[SIP Trend]\n" + sip_trend

        # ── MF Signals: Rotation, Risk Appetite, Bubble ──────────
        signal_lines = []

        # Rotation Index: Small Cap vs Large Cap
        small = current_df[current_df["category"] == "Small Cap"]
        large = current_df[current_df["category"] == "Large Cap"]
        if not small.empty and not large.empty:
            small_flow = small.iloc[0]["amount_cr"]
            large_flow = large.iloc[0]["amount_cr"]
            if large_flow > 0 and small_flow > 0:
                ratio = small_flow / large_flow
                if ratio > 2.0:
                    signal_lines.append(f"🔴 Small Cap {ratio:.1f}x Large Cap — retail chasing risk, bubble signal")
                elif ratio > 1.5:
                    signal_lines.append(f"🟡 Small Cap {ratio:.1f}x Large Cap — risk appetite elevated")
                elif ratio < 0.5:
                    signal_lines.append(f"🟢 Large Cap {1/ratio:.1f}x Small Cap — defensive positioning")

        # Risk Appetite: Equity vs Debt+Gold
        equity_cats = ["Large Cap", "Mid Cap", "Small Cap", "Flexi Cap", "ELSS"]
        debt_cats = ["Debt", "Liquid", "Hybrid"]
        equity_flow = current_df[current_df["category"].isin(equity_cats)]["amount_cr"].sum()
        debt_flow = current_df[current_df["category"].isin(debt_cats)]["amount_cr"].sum()
        if equity_flow > 0 and debt_flow < 0:
            signal_lines.append(f"🟢 Equity +₹{equity_flow:,.0f}Cr / Debt ₹{debt_flow:,.0f}Cr — risk-on rotation")
        elif equity_flow < 0 and debt_flow > 0:
            signal_lines.append(f"🔴 Equity ₹{equity_flow:,.0f}Cr / Debt +₹{debt_flow:,.0f}Cr — risk-off rotation")

        # Consecutive streaks (3+ months)
        for _, row in current_df.iterrows():
            cat = row["category"]
            curr = row["amount_cr"]
            prior_s = prior_months[prior_months["category"] == cat].sort_values("month", ascending=False)
            if len(prior_s) >= 2:
                all_same_sign = all(prior_s["amount_cr"] > 0) if curr > 0 else all(prior_s["amount_cr"] < 0)
                if all_same_sign and abs(curr) > 100:  # only flag meaningful flows
                    streak = sum(1 for x in prior_s["amount_cr"] if (x > 0) == (curr > 0)) + 1
                    if streak >= 3:
                        direction = "inflow" if curr > 0 else "outflow"
                        signal_lines.append(f"{'🟡' if curr < 0 else '🟢'} {cat}: {streak} months consecutive {direction} — trend building")

        signal_block = "[MF Flow Signals]\n" + "\n".join(signal_lines) if signal_lines else ""

        parts = [category_block, anomaly_block]
        if thematic_block:
            parts.append(thematic_block)
        if signal_block:
            parts.append(signal_block)
        parts.extend([top5_block, sip_block])

        return "MF Flow Intelligence:\n\n" + "\n\n".join(parts)

    except Exception as e:
        print(f"⚠️ format_mf_flows: {e}")
        return ""

# ═══════════════════════════════════════════════════════════════════════
# MF INTELLIGENCE — Daily Inferred Signals (no DB dependency)
# ═══════════════════════════════════════════════════════════════════════

def compute_mf_intelligence(ctx: Dict = None, macro_data: Dict = None,
                             sector_scores: Dict = None) -> str:
    """
    Daily MF intelligence from signals we already fetch.
    Works on Day 1, before any AMFI data exists.
    AMFI data (from format_mf_flows) becomes optional enhancement.
    """
    ctx = ctx or {}
    macro = macro_data or {}

    # ── Gather signals ────────────────────────────────────────────
    # Smallcap ratio (risk-on proxy)
    sc = ctx.get("india_structural", {}).get("smallcap_ratio", {})
    sc_ratio = sc.get("ratio", 0)
    sc_label = sc.get("label", "")

    # VIX (fear gauge)
    vix = macro.get("vix_price")
    vix_regime = macro.get("vix_regime", "UNKNOWN")

    # DII context (domestic MF buying/selling)
    fii_ctx = ctx.get("fii_context", {})
    dii_net = fii_ctx.get("dii_net", 0) if fii_ctx.get("ok") else 0
    dii_absorbed = fii_ctx.get("dii_absorbed", 0) if fii_ctx.get("ok") else 0

    # Gold (defensive proxy)
    gold = None
    for anchor in (macro.get("anchors") or []):
        if "Gold" in str(anchor.get("name", "")) or anchor.get("symbol") == "GC=F":
            gold = anchor.get("change_pct")
            break

    # Date for SIP window
    from datetime import datetime
    today = datetime.now()
    day_of_month = today.day

    # ── Score 1: Retail Participation (0-100) ────────────────────
    retail_score = 50  # neutral baseline

    # Smallcap outperforming = retail risk-on
    if sc_ratio > 0.9:
        retail_score += 25  # euphoria
    elif sc_ratio > 0.8:
        retail_score += 15  # outperformance
    elif sc_ratio < 0.6:
        retail_score -= 20  # flight to largecap

    # Low VIX = retail confident, likely adding SIPs
    if vix and vix < 14:
        retail_score += 15
    elif vix and vix > 20:
        retail_score -= 15

    # DII positive = MFs deploying (SIP money flowing)
    if dii_net > 1000:
        retail_score += 10
    elif dii_net < -1000:
        retail_score -= 10

    retail_score = max(0, min(100, retail_score))

    # ── Score 2: Institutional Quality (0-100) ──────────────────
    inst_score = 50

    # DII absorbing FII selling = strong domestic base
    if dii_absorbed > 0.8:
        inst_score += 20  # absorbing 80%+ of FII selling
    elif dii_absorbed > 0.5:
        inst_score += 10
    elif dii_absorbed < 0.3:
        inst_score -= 15  # weak absorption

    # DII net positive = MFs buying
    if dii_net > 500:
        inst_score += 15
    elif dii_net < -500:
        inst_score -= 15

    # Low VIX + DII buying = stable institutional flow
    if vix and vix < 15 and dii_net > 0:
        inst_score += 10

    inst_score = max(0, min(100, inst_score))

    # ── Score 3: Category Rotation Signal ───────────────────────
    # Determine rotation direction
    rotation = "NEUTRAL"
    rotation_detail = ""

    if sc_ratio > 0.85 and vix and vix < 15:
        rotation = "EQUITY GROWTH"
        if sector_scores and sector_scores.get("ok"):
            leaders = sector_scores.get("leaders", [])[:2]
            laggards = sector_scores.get("laggards", [])[:2]
            hot = ", ".join([s[0] for s in leaders]) if leaders else "Growth"
            cold = ", ".join([s[0] for s in laggards]) if laggards else "Debt"
            rotation_detail = f"Hot: {hot} | Cold: {cold}"
        else:
            rotation_detail = "Smallcap outperforming + low VIX → retail chasing growth funds"
    elif sc_ratio < 0.6 and vix and vix > 18:
        rotation = "DEFENSIVE"
        rotation_detail = "Largecap flight + elevated VIX → debt/hybrid rotation likely"
    elif gold and gold > 1.5:
        rotation = "FLIGHT TO SAFETY"
        rotation_detail = f"Gold +{gold:.1f}% → debt/gold fund inflows rising"
    elif dii_net > 1500 and sc_ratio > 0.75:
        rotation = "BROAD RISK-ON"
        rotation_detail = "Strong DII buying + smallcap strength → equity fund boom"

    # ── Narrative generation ────────────────────────────────────
    narrative_lines = []

    if retail_score >= 65 and inst_score >= 65:
        narrative_lines.append("Broad-based MF buying. SIP + lump-sum both active.")
        narrative_lines.append("Market internals confirm healthy domestic flows.")
    elif retail_score >= 65 and inst_score < 40:
        narrative_lines.append("Retail FOMO active while institutions distributing.")
        narrative_lines.append("Historically precedes correction. Watch smallcap fund inflow spike.")
    elif retail_score < 40 and inst_score >= 65:
        narrative_lines.append("Institutional accumulation during retail fear.")
        narrative_lines.append("Classic smart-money buy-the-dip. SIP pauses likely but MFs deploying reserves.")
    elif retail_score < 40 and inst_score < 40:
        narrative_lines.append("Broad redemption pressure. Both retail and institutional defensive.")
        narrative_lines.append("Debt/Liquid fund inflows likely spiking.")
    else:
        narrative_lines.append("Mixed signals. No strong directional conviction on MF flows.")

    # ── SIP window context ──────────────────────────────────────
    sip_line = ""
    if 1 <= day_of_month <= 7:
        sip_line = "📅 SIP deployment window (1st-7th) — systematic buying pressure from ₹26,000Cr+ monthly pool"
    elif 20 <= day_of_month <= 31:
        days_to_next = 31 - day_of_month + 1
        sip_line = f"📅 Next SIP cycle in {days_to_next} days"
    else:
        days_to_sip = 31 - day_of_month + 1
        sip_line = f"📅 Next SIP cycle in {days_to_sip} days (mid-month lull)"

    # ── Format output ──────────────────────────────────────────
    lines = ["💹 *MF INTELLIGENCE*"]
    lines.append("━" * 26)

    # Retail score
    if retail_score >= 65:
        ret_label = "HIGH — retail active, SIP additions likely"
    elif retail_score >= 40:
        ret_label = "MODERATE — retail watching, not committing"
    else:
        ret_label = "LOW — retail fearful, redemptions possible"
    lines.append(f"🧠 Retail: {ret_label}")

    # Institutional score
    if inst_score >= 65:
        inst_label = "HEALTHY — MFs deploying, strong absorption"
    elif inst_score >= 40:
        inst_label = "STABLE — no major flow shifts"
    else:
        inst_label = "WEAK — redemption pressure, defensive"
    lines.append(f"🏦 Institutional: {inst_label}")

    # Rotation
    if rotation != "NEUTRAL":
        lines.append(f"🔄 Rotation: {rotation}")
        if rotation_detail:
            lines.append(f"   {rotation_detail}")

    # DII context
    if dii_net != 0:
        if dii_net > 0:
            lines.append(f"💰 DII: buying ₹{abs(dii_net):,.0f}Cr (absorbed {dii_absorbed*100:.0f}% of FII)")
        else:
            lines.append(f"💰 DII: selling ₹{abs(dii_net):,.0f}Cr — adding to downside pressure")

    # Narrative
    if narrative_lines:
        lines.append("")
        for n in narrative_lines:
            lines.append(f"   {n}")

    # SIP window
    if sip_line:
        lines.append("")
        lines.append(sip_line)

    # Data source tag
    lines.append("")
    lines.append("_Inferred from live market signals. AMFI confirmed data available after 8th._")
    lines.append("━" * 26)

    return "\n".join(lines)


def compute_mf_behavior_index(db_flows: list = None, ctx: Dict = None) -> Dict:
    """
    MF Behavior Index — 5 sub-signals from AMFI category flow data.
    Each score 0-100. Higher = more extreme.

    Args:
        db_flows: list of dicts from mf_flows table [{month, category, amount_cr, sip_amount_cr}]
        ctx: context dict with fii_context, macro_context
    Returns:
        dict with 5 sub-signal scores + composite
    """
    ctx = ctx or {}
    db_flows = db_flows or []
    scores = {}

    if not db_flows:
        return {"ok": False, "reason": "no_flow_data"}

    # Group flows by month
    from collections import defaultdict
    by_month = defaultdict(dict)
    for row in db_flows:
        month = row.get("month", "")
        cat = row.get("category", "")
        by_month[month][cat] = row

    months = sorted(by_month.keys(), reverse=True)
    if len(months) < 2:
        return {"ok": False, "reason": "insufficient_months"}

    current = by_month[months[0]]
    prior = by_month[months[1]]

    # ── 1. SIP Momentum (0-100) ──────────────────────────────
    sip_current = sum(r.get("sip_amount_cr") or 0 for r in current.values())
    sip_prior = sum(r.get("sip_amount_cr") or 0 for r in prior.values())
    if sip_current > 0 and sip_prior > 0:
        sip_change = (sip_current - sip_prior) / sip_prior * 100
        scores["sip_momentum"] = int(max(0, min(100, 50 + sip_change * 5)))
    else:
        scores["sip_momentum"] = 50  # neutral if no data

    # ── 2. Retail Rotation (0-100) ──────────────────────────
    sc_flow = current.get("Small Cap", {}).get("amount_cr", 0)
    lc_flow = current.get("Large Cap", {}).get("amount_cr", 0)
    if lc_flow > 0 and sc_flow > 0:
        ratio = sc_flow / lc_flow
        scores["retail_rotation"] = int(min(100, ratio * 40))
    elif sc_flow > 0 and lc_flow <= 0:
        scores["retail_rotation"] = 80  # smallcap inflow + largecap outflow
    else:
        scores["retail_rotation"] = 50

    # ── 3. Redemption Pressure (0-100) ──────────────────────
    outflow_cats = sum(1 for r in current.values() if (r.get("amount_cr") or 0) < 0)
    dii_net = ctx.get("fii_context", {}).get("dii_net", 0) if ctx.get("fii_context", {}).get("ok") else 0
    scores["redemption_pressure"] = int(min(100, 20 + (outflow_cats * 12) + (25 if dii_net < 0 else 0)))

    # ── 4. Thematic FOMO (0-100) ────────────────────────────
    sector_cats = [k for k in current if "Sector" in k]
    sectoral_flow = sum(current.get(c, {}).get("amount_cr", 0) for c in sector_cats)
    if len(months) >= 3:
        prior_sectoral = sum(by_month[months[2]].get(c, {}).get("amount_cr", 0) for c in sector_cats)
        if prior_sectoral > 0:
            fomo_ratio = sectoral_flow / prior_sectoral
            scores["thematic_fomo"] = int(min(100, fomo_ratio * 50))
        else:
            scores["thematic_fomo"] = 50
    else:
        scores["thematic_fomo"] = 50

    # ── 5. Defensive Shift (0-100) ─────────────────────────
    equity_cats = ["Large Cap", "Mid Cap", "Small Cap", "Flexi Cap", "ELSS",
                   "Large & Mid Cap", "Multi Cap", "Focused", "Contra/Value"]
    debt_cats = ["Debt", "Liquid", "Hybrid"]
    equity_flow = sum(current.get(c, {}).get("amount_cr", 0) for c in equity_cats if c in current)
    debt_flow = sum(current.get(c, {}).get("amount_cr", 0) for c in debt_cats if c in current)
    total_abs = abs(equity_flow) + abs(debt_flow)
    if total_abs > 0:
        defensive_ratio = abs(debt_flow) / total_abs
        scores["defensive_shift"] = int(defensive_ratio * 100)
    else:
        scores["defensive_shift"] = 50

    # ── Composite ───────────────────────────────────────────
    weights = {
        "sip_momentum": 0.25,
        "retail_rotation": 0.20,
        "redemption_pressure": 0.25,
        "thematic_fomo": 0.15,
        "defensive_shift": 0.15,
    }
    composite = sum(scores[k] * weights[k] for k in weights)

    return {
        "ok": True,
        "scores": scores,
        "composite": round(composite, 1),
        "data_month": months[0] if months else None,
    }


# ═══════════════════════════════════════════════════════════════════════
# BLOCK: MARKET CONTEXT (Intelligence Layer)
# ═══════════════════════════════════════════════════════════════════════

def format_context_block(anchor_data: list = None, extra_signals: dict = None) -> str:
    """
    Format Bull/Bear score + market narrative from context_engine.
    Returns pre-computed conclusions for AI prompt injection.
    extra_signals: optional dict with breadth_ratio, nifty_vs_ma200_pct, pcr, fii_fno_net
    """
    try:
        from src.context_engine import run_contextualization, format_context_for_ai

        if not anchor_data:
            return ""

        # Run full contextualization pipeline with extra signals
        ctx = run_contextualization(anchor_data, extra_signals=extra_signals)

        # Store raw context for snapshot access (cross_asset_regime, etc.)
        format_context_block.last_ctx = ctx

        if not ctx.get("fii_context", {}).get("ok"):
            return ""

        # Format for AI injection (includes yield spread and momentum)
        from src.context_engine import format_context_for_ai_full
        ctx["extra_signals"] = extra_signals
        return format_context_for_ai_full(ctx)

    except Exception as e:
        print(f"⚠️ format_context_block: {e}")
        format_context_block.last_ctx = None
        return ""


# ═══════════════════════════════════════════════════════════════════════
# BLOCK: OPTIONS INTELLIGENCE (Intelligence Layer)
# ═══════════════════════════════════════════════════════════════════════

def format_options_block(symbol: str = "NIFTY", run_label: str = "morning") -> str:
    """
    Format options analysis: max pain, PCR, OI zones, GEX, skew, advanced OI.
    Morning: uses computed values directly.
    Evening: compares to morning snapshot for OI shifts.
    """
    try:
        from src.options_engine import run_options_analysis, fetch_nse_options_chain, compute_oi_shifts, format_derivatives_intel

        # Run options analysis for this execution
        analysis = run_options_analysis(symbol=symbol, store=True, run_label=run_label)

        if not analysis.get("ok"):
            return ""

        # Format output
        lines = []
        lines.append("📊 *OPTIONS & DERIVATIVES INTELLIGENCE*\n")

        # Max Pain
        mp = analysis.get("max_pain", {})
        lines.append(f"┌─ Max Pain ────────────────────")
        lines.append(f"│ Strike: {mp.get('max_pain', 'N/A')}")
        lines.append(f"│ Distance: {mp.get('max_pain_distance', 0):+.2f}% from spot")

        # PCR (with contrarian interpretation)
        pcr = analysis.get("pcr", {})
        pcr_val = pcr.get("pcr", 0)
        if pcr_val > 1.4:
            pcr_label = "CONTRARIAN BULL (crowded bear)"
        elif pcr_val > 1.0:
            pcr_label = "BEARISH lean"
        elif pcr_val > 0.7:
            pcr_label = "NEUTRAL"
        else:
            pcr_label = "CONTRARIAN BEAR (crowded bull)"

        lines.append(f"┌─ Put-Call Ratio ───────────────")
        lines.append(f"│ PCR: {pcr_val} → {pcr_label}")

        # OI Zones
        zones = analysis.get("zones", {})
        support = zones.get("support_zone", [])
        resistance = zones.get("resistance_zone", [])

        lines.append(f"┌─ OI Zones ─────────────────────")
        if support:
            lines.append(f"│ Support: {', '.join(map(str, support))}")
        if resistance:
            lines.append(f"│ Resistance: {', '.join(map(str, resistance))}")

        # GEX, Skew, Advanced OI
        deriv_intel = format_derivatives_intel(analysis)
        if deriv_intel:
            lines.append(f"┌─ Gamma & Skew ─────────────────")
            for dl in deriv_intel.split("\n"):
                lines.append(f"│ {dl}")

        # Evening only: compute OI shifts vs morning snapshot
        if run_label == "evening":
            try:
                evening_data = fetch_nse_options_chain(symbol)
                if evening_data:
                    shifts = compute_oi_shifts(evening_data, symbol)
                    if shifts.get("ok") and shifts.get("shifts"):
                        lines.append("\n" + shifts.get("signal_text", ""))
            except Exception as e:
                print(f"   ⚠️ OI shift detection: {e}")

        lines.append("└" + "─" * 30)
        return "\n".join(lines)

    except Exception as e:
        print(f"⚠️ format_options_block: {e}")
        return ""


def format_top_movers(movers: Dict) -> str:
    """
    Format top 10 gainers/losers from India + US markets.
    Replaces the static watchlist block.
    """
    if not movers:
        return ""

    lines = ["📈📉 *Top Market Movers (Auto-Fetched)*"]
    lines.append("━" * 30)

    # India
    india = movers.get("india", {})
    if india.get("gainers"):
        lines.append("")
        lines.append(f"🇮🇳 *India (Nifty 50) — {india.get('total', 0)} stocks*")
        lines.append("")

        lines.append("📈 *Top 10 Gainers*")
        for i, s in enumerate(india["gainers"], 1):
            weekly = f" | W: {s['weekly_pct']:+.1f}%" if s.get("weekly_pct") else ""
            lines.append(f"{i:2d}. {s['symbol']:15s} ₹{s['price']:>8,.1f}  {s['change_pct']:+.2f}%{weekly}")

        lines.append("")
        lines.append("📉 *Top 10 Losers*")
        for i, s in enumerate(india["losers"], 1):
            weekly = f" | W: {s['weekly_pct']:+.1f}%" if s.get("weekly_pct") else ""
            lines.append(f"{i:2d}. {s['symbol']:15s} ₹{s['price']:>8,.1f}  {s['change_pct']:+.2f}%{weekly}")

    # US
    us = movers.get("us", {})
    if us.get("gainers"):
        lines.append("")
        lines.append(f"🇺🇸 *US Market — {us.get('total', 0)} stocks*")
        lines.append("")

        lines.append("📈 *Top 10 Gainers*")
        for i, s in enumerate(us["gainers"], 1):
            weekly = f" | W: {s['weekly_pct']:+.1f}%" if s.get("weekly_pct") else ""
            price_str = f"${s['price']:>8,.1f}"
            lines.append(f"{i:2d}. {s['symbol']:8s} {price_str}  {s['change_pct']:+.2f}%{weekly}")

        lines.append("")
        lines.append("📉 *Top 10 Losers*")
        for i, s in enumerate(us["losers"], 1):
            weekly = f" | W: {s['weekly_pct']:+.1f}%" if s.get("weekly_pct") else ""
            price_str = f"${s['price']:>8,.1f}"
            lines.append(f"{i:2d}. {s['symbol']:8s} {price_str}  {s['change_pct']:+.2f}%{weekly}")

    # Market breadth summary
    india_up = sum(1 for s in india.get("gainers", []) if s["change_pct"] > 0)
    india_down = sum(1 for s in india.get("losers", []) if s["change_pct"] < 0)
    us_up = sum(1 for s in us.get("gainers", []) if s["change_pct"] > 0)
    us_down = sum(1 for s in us.get("losers", []) if s["change_pct"] < 0)

    lines.append("")
    lines.append("📊 *Quick Read*")
    if india.get("gainers") and india.get("losers"):
        top_india = india["gainers"][0]
        bot_india = india["losers"][0]
        lines.append(f"🇮🇳 Best: {top_india['symbol']} ({top_india['change_pct']:+.1f}%) | Worst: {bot_india['symbol']} ({bot_india['change_pct']:+.1f}%)")
    if us.get("gainers") and us.get("losers"):
        top_us = us["gainers"][0]
        bot_us = us["losers"][0]
        lines.append(f"🇺🇸 Best: {top_us['symbol']} ({top_us['change_pct']:+.1f}%) | Worst: {bot_us['symbol']} ({bot_us['change_pct']:+.1f}%)")

    return "\n".join(lines)


def format_market_state_dashboard(market_phase: Dict, ctx: Dict = None) -> str:
    """
    Format the Market State Dashboard — decisive, contextual, causal.
    Always shows a lean even if weak. Explains WHY, not just WHAT.
    """
    if not market_phase or not market_phase.get("ok"):
        return ""

    mp = market_phase
    ctx = ctx or {}

    # Phase emoji
    phase_emoji = {
        "EXPANSION": "🟢",
        "DISTRIBUTION": "🟡",
        "CONTRACTION": "🔴",
        "RECOVERY": "🔵",
        "NEUTRAL": "⚪",
    }.get(mp["phase"], "⚪")

    # Phase label — always decisive, never "no edge"
    phase_labels = {
        "EXPANSION": "Rally mode — breadth healthy",
        "RECOVERY": "Bouncing — watch for follow-through",
        "NEUTRAL": "Transition — waiting for catalyst",
        "DISTRIBUTION": "Smart money exiting — be careful",
        "CONTRACTION": "Defensive — protect capital first",
    }
    phase_label = phase_labels.get(mp["phase"], mp.get("phase_label", ""))

    # Directional lean from bull_bear score
    bull_bear = ctx.get("bull_bear", {})
    bb_score = bull_bear.get("score", 50)  # 0-100, 50=neutral
    if bb_score >= 65:
        lean = "Bullish"
    elif bb_score >= 55:
        lean = "Slight Bullish"
    elif bb_score <= 35:
        lean = "Bearish"
    elif bb_score <= 45:
        lean = "Slight Bearish"
    else:
        lean = "Neutral"

    # Conviction from signal alignment
    conf = mp.get("confidence", 50)
    if conf >= 70:
        conviction = "HIGH"
    elif conf >= 40:
        conviction = "MEDIUM"
    else:
        conviction = "LOW"

    lines = ["🎯 *MARKET STATE*"]
    lines.append("━" * 26)

    # Header: Phase + Lean + Conviction
    lines.append(f"{phase_emoji} *{mp['phase']} PHASE*")
    lines.append(f"Lean: {lean} | Conviction: {conviction}")
    lines.append("━" * 26)

    # What this means — plain English
    focus = mp.get("focus", "N/A")
    avoid = mp.get("avoid", "N/A")
    lines.append(f"📍 {phase_label}")
    lines.append(f"   ✅ {focus}")
    lines.append(f"   ❌ {avoid}")

    # Key Evidence — real data with context
    evidence = []

    # Temporal context for duration display
    temporal_ctx = ctx.get("temporal_context", {})
    temporal_metrics = temporal_ctx.get("metrics", {}) if temporal_ctx.get("ok") else {}

    # FII streak + flow
    fii = ctx.get("fii_context", {})
    if fii.get("ok"):
        fii_net = fii.get("fii_net", 0)
        streak = fii.get("fii_streak", 0)
        direction = fii.get("fii_streak_direction", "")
        fii_pct = get_percentile("fii_net", fii_net, "1Y")
        pct_str = f" | {fii_pct}" if fii_pct else ""
        # Temporal duration context
        fii_temporal = temporal_metrics.get("fii_net", {})
        temporal_suffix = ""
        if fii_temporal and streak >= 3:
            avg_dur = fii_temporal.get("avg_historical_duration", 0)
            t_label = fii_temporal.get("temporal_label", "")
            label_word = t_label.split(" — ")[0] if " — " in t_label else ""
            if avg_dur > 0:
                temporal_suffix = f" (avg {avg_dur:.0f}d)"
            if label_word:
                temporal_suffix += f" → {label_word.lower()}"
        if streak >= 3 and direction == "negative":
            total = fii.get("fii_4w_avg", 0) * streak
            evidence.append(f"FII: -₹{abs(fii_net):,.0f}Cr | Day {streak}{temporal_suffix}{pct_str} | ₹{abs(total):,.0f}Cr total")
        elif streak >= 3 and direction == "positive":
            total = fii.get("fii_4w_avg", 0) * streak
            evidence.append(f"FII: +₹{fii_net:,.0f}Cr | Day {streak}{temporal_suffix}{pct_str} | ₹{total:,.0f}Cr total")
        elif abs(fii_net) > 1000:
            sign = "-" if fii_net < 0 else "+"
            evidence.append(f"FII: {sign}₹{abs(fii_net):,.0f}Cr{pct_str} yesterday")

    # DII context
    if fii.get("ok"):
        dii_net = fii.get("dii_net", 0)
        dii_absorbed = fii.get("dii_absorbed", 0)
        if dii_net > 0 and fii_net < 0:
            evidence.append(f"DII: +₹{dii_net:,.0f}Cr | absorbing {dii_absorbed*100:.0f}% of FII — floor exists")
        elif dii_net > 0:
            evidence.append(f"DII: +₹{dii_net:,.0f}Cr — domestic buying")
        elif dii_net < -500:
            evidence.append(f"DII: -₹{abs(dii_net):,.0f}Cr — domestic selling pressure")

    # VIX level
    macro = ctx.get("macro_context", {})
    vix_price = macro.get("vix_price")
    if vix_price:
        vix_pct = get_percentile("india_vix", vix_price, "1Y")
        vix_pct_str = f" | {vix_pct}" if vix_pct else ""
        if vix_price > 20:
            evidence.append(f"VIX: {vix_price:.1f} | HIGH{vix_pct_str} | elevated fear")
        elif vix_price > 15:
            evidence.append(f"VIX: {vix_price:.1f} | NORMAL{vix_pct_str}")
        else:
            if mp.get("phase") in ("EXPANSION", "RECOVERY"):
                evidence.append(f"VIX: {vix_price:.1f} | complacent{vix_pct_str} — crowded longs risk")
            else:
                evidence.append(f"VIX: {vix_price:.1f} | calm{vix_pct_str}")

    # VIX regime duration
    vix_temporal = temporal_metrics.get("india_vix", {})
    if vix_temporal:
        vix_streak = vix_temporal.get("streak_days", 0)
        vix_avg = vix_temporal.get("avg_historical_duration", 0)
        vix_tlabel = vix_temporal.get("temporal_label", "")
        if vix_streak >= 3 and vix_avg > 0:
            vix_label_word = vix_tlabel.split(" — ")[0] if " — " in vix_tlabel else ""
            vix_dur_str = f"VIX regime: {vix_streak}d (avg {vix_avg:.0f}d)"
            if vix_label_word:
                vix_dur_str += f" → {vix_label_word.lower()}"
            evidence.append(vix_dur_str)

    if evidence:
        lines.append("")
        lines.append("🔑 *Key Evidence:*")
        for e in evidence[:4]:
            lines.append(f"   • {e}")

    # Conflicting signals — what contradicts the lean
    conflicting = []

    # PCR contrarian signal
    pcr = ctx.get("pcr")
    if pcr:
        if pcr > 1.4 and lean in ("Bearish", "Slight Bearish"):
            conflicting.append(f"PCR {pcr:.2f} (contrarian bullish — crowded bears, squeeze risk)")
        elif pcr < 0.6 and lean in ("Bullish", "Slight Bullish"):
            conflicting.append(f"PCR {pcr:.2f} (contrarian bearish — crowded bulls, dump risk)")

    # VIX in opposite direction
    if vix_price:
        if vix_price < 13 and lean in ("Bearish", "Slight Bearish"):
            conflicting.append(f"VIX {vix_price:.1f} (complacent — market not pricing risk)")
        elif vix_price > 25 and lean in ("Bullish", "Slight Bullish"):
            conflicting.append(f"VIX {vix_price:.1f} (extreme fear — contrarian buy signal)")

    # DII vs FII divergence
    if fii.get("ok"):
        if fii_net < -2000 and fii.get("dii_net", 0) > 1500:
            conflicting.append("FII heavy selling vs DII strong buying — tug of war")

    # Risk actions from market phase
    for action in mp.get("risk_actions", [])[:2]:
        if "Insufficient signal" not in action:
            conflicting.append(action)

    if conflicting:
        lines.append("")
        lines.append("⚠️ *Conflicting Signals:*")
        for c in conflicting[:3]:
            lines.append(f"   • {c}")

    # Signal alignment — 3 clear metrics
    # Count signals that fired
    fii_ok = fii.get("ok", False)
    vix_fired = vix_price is not None
    pcr_fired = pcr is not None
    dii_fired = fii_ok and fii.get("dii_net") is not None
    total_signals = 7
    fired = sum([
        1 if fii_ok else 0,
        1 if dii_fired else 0,
        1 if vix_fired else 0,
        1 if pcr_fired else 0,
        1 if ctx.get("breadth") else 0,
        1 if ctx.get("momentum") else 0,
        1 if ctx.get("cross_asset") else 0,
    ])

    # Count signals pointing in lean direction
    lean_bearish = lean in ("Bearish", "Slight Bearish")
    aligned = 0
    if fii_ok:
        if (fii_net < 0 and lean_bearish) or (fii_net > 0 and not lean_bearish):
            aligned += 1
    if vix_fired:
        if (vix_price > 20 and lean_bearish) or (vix_price < 15 and not lean_bearish):
            aligned += 1
    if pcr_fired:
        if (pcr > 1.3 and not lean_bearish) or (pcr < 0.7 and lean_bearish):
            aligned += 1  # contrarian
    if dii_fired:
        dii_val = fii.get("dii_net", 0)
        if (dii_val > 500 and not lean_bearish) or (dii_val < -500 and lean_bearish):
            aligned += 1

    lines.append("")
    lines.append(f"📊 Signals: {fired}/{total_signals} fired | {aligned}/{fired} → {lean}")
    lines.append(f"📈 Bull/Bear: {bb_score}/100 ({lean})")

    # Earnings context (only if active)
    er = mp.get("earnings_regime", "QUIET")
    if er not in ("QUIET", ""):
        lines.append(f"📅 Earnings: {er}")

    lines.append("━" * 26)

    return "\n".join(lines)


def format_weekly_digest(scorecard: Dict = None, fii_pattern: Dict = None,
                         regime_shift: Dict = None, movers: Dict = None,
                         institutional: str = "", contrarian: str = "",
                         ai_summary: str = "") -> str:
    """
    Format the complete weekly digest message.
    Structure ordered by engagement:
    1. Prediction Scorecard (hero)
    2. FII Weekly Pattern
    3. Regime Shift
    4. Top Movers of the Week
    5. Institutional Signals
    6. Contrarian / AI Summary
    7. Next Week Preview
    """
    lines = ["📅 *WEEKLY MARKET DIGEST*"]
    lines.append("━" * 30)
    lines.append("")

    # ── 1. Prediction Scorecard (HERO) ─────────────────────────────
    if scorecard and scorecard.get("ok"):
        sc = scorecard
        emoji = "🏆" if sc.get("accuracy_pct", 0) >= 70 else ("📊" if sc.get("accuracy_pct", 0) >= 50 else "⚠️")
        lines.append(f"{emoji} *This Week: {sc.get('correct', 0)}/{sc.get('total', 0)} predictions correct ({sc.get('accuracy_pct', 0):.0f}%)*")
        if sc.get("cumulative_pct"):
            lines.append(f"📈 Cumulative: {sc['cumulative_pct']:.0f}% ({sc.get('cumulative_total', 0)} predictions)")
        if sc.get("best_call"):
            lines.append(f"🏆 Best call: {sc['best_call']}")
        if sc.get("worst_call"):
            lines.append(f"❌ Worst call: {sc['worst_call']}")
        lines.append("")

    # ── 2. FII Weekly Pattern ──────────────────────────────────────
    if fii_pattern and fii_pattern.get("ok"):
        fp = fii_pattern
        emoji = "🟢" if fp.get("weekly_net", 0) > 0 else "🔴"
        streak = ""
        if fp.get("streak_weeks", 0) > 1:
            direction = "buying" if fp["weekly_net"] > 0 else "selling"
            streak = f" ({fp['streak_weeks']} consecutive {direction} weeks)"
        lines.append(f"💰 *FII Weekly:* {emoji} ₹{fp.get('weekly_net', 0):+,.0f} Cr{streak}")
        if fp.get("dii_net"):
            dii_emoji = "🟢" if fp["dii_net"] > 0 else "🔴"
            lines.append(f"   DII: {dii_emoji} ₹{fp['dii_net']:+,.0f} Cr")
        if fp.get("4w_avg"):
            lines.append(f"   4W avg: ₹{fp['4w_avg']:+,.0f} Cr")
        lines.append("")

    # ── 3. Regime Shift ────────────────────────────────────────────
    if regime_shift and regime_shift.get("ok"):
        rs = regime_shift
        lines.append(f"🔄 *Regime Shift:* {rs.get('monday_label', 'N/A')} → {rs.get('friday_label', 'N/A')}")
        if rs.get("score_change"):
            direction = "improved" if rs["score_change"] > 0 else "weakened"
            lines.append(f"   Bull/Bear: {rs.get('monday_score', '?')} → {rs.get('friday_score', '?')} ({direction} by {abs(rs['score_change'])} pts)")
        if rs.get("what_changed"):
            lines.append(f"   Key driver: {rs['what_changed']}")
        lines.append("")

    # ── 4. Top Movers of the Week ──────────────────────────────────
    if movers:
        india = movers.get("india", {})
        us = movers.get("us", {})
        if india.get("gainers") or us.get("gainers"):
            lines.append("📊 *Top Movers (Weekly)*")

            if india.get("gainers"):
                g = india["gainers"][:3]
                g_str = ", ".join(f"{m['symbol']} {m.get('weekly_pct', m.get('change_pct', 0)):+.1f}%" for m in g)
                lines.append(f"🇮🇳 Gainers: {g_str}")
            if india.get("losers"):
                l = india["losers"][:3]
                l_str = ", ".join(f"{m['symbol']} {m.get('weekly_pct', m.get('change_pct', 0)):+.1f}%" for m in l)
                lines.append(f"🇮🇳 Losers: {l_str}")

            if us.get("gainers"):
                g = us["gainers"][:3]
                g_str = ", ".join(f"{m['symbol']} {m.get('weekly_pct', m.get('change_pct', 0)):+.1f}%" for m in g)
                lines.append(f"🇺🇸 Gainers: {g_str}")
            if us.get("losers"):
                l = us["losers"][:3]
                l_str = ", ".join(f"{m['symbol']} {m.get('weekly_pct', m.get('change_pct', 0)):+.1f}%" for m in l)
                lines.append(f"🇺🇸 Losers: {l_str}")
            lines.append("")

    # ── 5. Institutional Signals ───────────────────────────────────
    if institutional:
        lines.append(institutional)
        lines.append("")

    # ── 6. AI Summary (includes contrarian + next week) ────────────
    if ai_summary:
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(ai_summary)

    # ── 7. Contrarian Signal ───────────────────────────────────────
    if contrarian:
        lines.append("")
        lines.append("🔄 *Contrarian Signal*")
        lines.append(contrarian)

    lines.append("")
    lines.append("━" * 30)
    lines.append("_Weekly digest — see you Monday! 🌅_")

    return "\n".join(lines)

