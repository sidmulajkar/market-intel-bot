"""
Formatters — Data to Prompt Block conversion
Each formatter returns a string (or "" on failure) for master_prompt.txt
Phase 1: Blocks 1, 2, 4, 6, 8, 10
Intelligence Layer: context_engine + options_engine integrated
Quant Layer: percentiles, cross-signals, significance labels
"""
from typing import Dict, Optional


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
    Splits into Global News and Indian News sections.
    Includes sentiment, impact scoring, category tags, and extracted numbers.
    """
    if not global_articles and not indian_articles:
        return ""

    try:
        from src.quant_enrichment import enrich_news_articles

        sections = []

        # ── Global News ──
        if global_articles:
            global_enriched = enrich_news_articles(global_articles[:10])
            global_lines = []
            for article in global_enriched[:5]:
                line = _format_news_line(article)
                if line:
                    global_lines.append(line)
            if global_lines:
                sections.append("Global News:\n" + "\n".join(global_lines))

        # ── Indian News ──
        if indian_articles:
            indian_enriched = enrich_news_articles(indian_articles[:10])
            indian_lines = []
            for article in indian_enriched[:5]:
                line = _format_news_line(article)
                if line:
                    indian_lines.append(line)
            if indian_lines:
                sections.append("India News:\n" + "\n".join(indian_lines))

        if not sections:
            return ""

        result = "News Intelligence (trust >= 6, sorted by impact):\n\n" + "\n\n".join(sections)

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
    """Format a single news article line with sentiment and impact."""
    headline = article.get("headline", "")[:100]
    source   = article.get("source", "unknown")
    sent     = article.get("sentiment", {})
    impact   = article.get("impact", "LOW")
    category = article.get("category", "general")
    numbers  = article.get("extracted_numbers", "")

    # Get dominant sentiment
    if sent:
        dominant = max(sent, key=sent.get)
        score    = sent.get(dominant, 0)
        sent_str = f"{dominant.upper()}"
    else:
        sent_str = "NEUTRAL"
        score = 0

    # Impact emoji
    impact_e = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "⚪"}.get(impact, "⚪")

    # Build line
    parts = [f"{impact_e} [{impact}]"]
    parts.append(f"{headline}")
    if numbers:
        parts.append(f"({numbers})")
    parts.append(f"— {sent_str} {score:+.2f} | {source}")

    return " ".join(parts)


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

        # ── Thematic signals ──
        thematic_lines = []
        sector_df = current_df[current_df["category"].str.contains(
            "Sector|Infra|IT|PSU|Thematic", case=False, na=False
        )]
        for _, row in sector_df.iterrows():
            cat  = row["category"]
            curr = row["amount_cr"]
            prior_s = prior_months[prior_months["category"] == cat].sort_values("month", ascending=False)
            if len(prior_s) >= 2:
                if curr > 0 and all(prior_s["amount_cr"] > 0):
                    streak = sum(1 for x in prior_s["amount_cr"] if x > 0) + 1
                    thematic_lines.append(f"{cat}: +{curr:.0f} Cr ({streak}th consecutive inflow)")
                elif curr < 0 and all(prior_s["amount_cr"] < 0):
                    streak = sum(1 for x in prior_s["amount_cr"] if x < 0) + 1
                    thematic_lines.append(f"{cat}: {curr:.0f} Cr ({streak}th consecutive outflow)")
                else:
                    thematic_lines.append(f"{cat}: {curr:+.0f} Cr")
            else:
                thematic_lines.append(f"{cat}: {curr:+.0f} Cr")
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

        parts = [category_block, anomaly_block]
        if thematic_block:
            parts.append(thematic_block)
        parts.extend([top5_block, sip_block])

        return "MF Flow Intelligence:\n\n" + "\n\n".join(parts)

    except Exception as e:
        print(f"⚠️ format_mf_flows: {e}")
        return ""

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

        if not ctx.get("fii_context", {}).get("ok"):
            return ""

        # Format for AI injection (includes yield spread and momentum)
        from src.context_engine import format_context_for_ai_full
        ctx["extra_signals"] = extra_signals
        return format_context_for_ai_full(ctx)

    except Exception as e:
        print(f"⚠️ format_context_block: {e}")
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

