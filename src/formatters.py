"""
Formatters — Data to Prompt Block conversion
Each formatter returns a string (or "" on failure) for master_prompt.txt
Phase 1: Blocks 1, 2, 4, 6, 8, 10
Intelligence Layer: context_engine + options_engine integrated
"""
from typing import Optional


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


# ═══════════════════════════════════════════════════════════════════════
# BLOCK 1: GLOBAL INDICES
# ═══════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────
# BLOCK 1: GLOBAL INDICES
# ─────────────────────────────────────────────────────────────────────
def format_global_indices(index_data: dict) -> str:
    """
    Convert 18 global indices to BLOCK 1 string.
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
            lines.append(f"{flag} {country}: {sign}{change:.2f}% | {price:,.0f} [{status}]")

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
    anchor_data: list from fetch_macro_anchors()
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

            lines.append(f"{name}: ₹{price:,.2f} ({sign}{change:.2f}%){weekly_s} {status_e}")

        if not lines:
            return ""

        return "Macro Anchors:\n" + "\n".join(lines)
    except Exception as e:
        print(f"⚠️ format_macro_anchors: {e}")
        return ""


# ─────────────────────────────────────────────────────────────────────
# BLOCK 4: FLOW INTELLIGENCE (FII/DII)
# ─────────────────────────────────────────────────────────────────────
def format_flows() -> str:
    """
    Compute weekly FII/DII net + 4-week trend from DB.
    Returns BLOCK 4 string.
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
        df["dow"]    = df["date"].dt.dayofweek

        # Group by week
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

        # 4-week FII trend
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
            trend_str = f"4-week trend (FII net, Cr): " + " | ".join(
                [f"Wk-{4-len(fii_nets)+i+1}: {x:+.0f}" for i, x in enumerate(fii_nets)
            ]) + f" ({trend_label})"
        else:
            wks = len(fii_nets)
            trend_str = f"4-week trend: ({wks} weeks available) " + " | ".join(
                [f"Wk-{i+1}: {x:+.0f}" for i, x in enumerate(reversed(fii_nets))]
            ) + " (insufficient history)"

        return (f"Flow Intelligence (FII/DII):\n"
                f"FII (last week): {fii_net:+.0f} Cr | DII (last week): {dii_net:+.0f} Cr | "
                f"Net (last week): {net:+.0f} Cr\n{trend_str}")

    except Exception as e:
        print(f"⚠️ format_flows: {e}")
        return ""


# ─────────────────────────────────────────────────────────────────────
# BLOCK 6: NEWS INTELLIGENCE
# ─────────────────────────────────────────────────────────────────────
def format_news(validated_articles: list) -> str:
    """
    Convert validated news (trust >= 6) to BLOCK 6 string.
    Include sentiment label + score per article.
    """
    if not validated_articles:
        return ""

    try:
        lines = []
        for article in validated_articles[:5]:  # Top 5 only
            headline = article.get("headline", "")[:80]
            source   = article.get("source", "unknown")
            sent     = article.get("sentiment", {})

            # Get dominant sentiment
            if sent:
                dominant = max(sent, key=sent.get)
                score    = sent.get(dominant, 0)
                sent_str = f"[{dominant.upper()}, {score:+.2f}]"
            else:
                sent_str = "[neutral]"

            lines.append(f"{sent_str} {headline} (source: {source})")

        if not lines:
            return ""

        return "News Intelligence (trust >= 6):\n" + "\n".join(lines)
    except Exception as e:
        print(f"⚠️ format_news: {e}")
        return ""


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
    """
    if not watchlist_data:
        return ""

    try:
        lines = []
        for symbol, d in watchlist_data.items():
            if not d.get("ok"):
                continue

            price        = d.get("price", 0)
            day_change   = d.get("day_change", 0)
            volume       = d.get("volume", 0)
            avg_volume   = d.get("avg_volume", 1)
            close_series = d.get("close_series", [])

            # Volume spike
            vol_ratio = volume / avg_volume if avg_volume > 0 else 0
            if vol_ratio > 2.0:
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
                ma20_str = f"MA20: {ma_status} ({ma20_diff:+.1f}%)"
            else:
                ma20_str = "MA20: N/A"

            # 5D momentum
            if len(close_series) >= 2:
                prev_5d = close_series[-6] if len(close_series) > 5 else close_series[0]
                mom_5d = ((price - prev_5d) / prev_5d * 100) if prev_5d else 0
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

        if not lines:
            return ""

        return "Watchlist:\n" + "\n".join(lines)
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
    """
    Query mf_flows table, compute anomaly vs 3M avg, thematic, top5.
    Returns BLOCK 10 string.
    """
    if not db_client:
        return ""

    try:
        from datetime import timedelta
        import pandas as pd

        # Get last 4 months
        today = pd.Timestamp.now()
        cutoff = (today - timedelta(days=120)).strftime("%Y-%m-%d")

        result = (
            db_client.table("mf_flows")
            .select("month, category, amount_cr, sip_amount_cr")
            .gte("month", cutoff)
            .order("month")
            .execute()
        )

        if not result.data:
            return ""

        rows = result.data
        if len(rows) < 5:
            return ""

        df = pd.DataFrame(rows)
        df["month"] = pd.to_datetime(df["month"])

        # Current month (most recent)
        current_month = df["month"].max()
        current_df  = df[df["month"] == current_month]
        prior_months = df[df["month"] < current_month]

        if current_df.empty or len(prior_months) < 1:
            return ""

        # ── Category flows ──
        cat_lines = [f"{r['category']}: {r['amount_cr']:+.0f} Cr" for _, r in current_df.iterrows()]
        month_str = current_month.strftime("%b %Y")
        category_block = f"[Category Flows — {month_str}]\n" + " | ".join(cat_lines)

        # ── Anomaly vs 3M avg ──
        anomaly_lines = []
        for _, row in current_df.iterrows():
            cat = row["category"]
            curr = row["amount_cr"]

            # Get prior 3 months for this category
            prior_cat = prior_months[prior_months["category"] == cat]
            if len(prior_cat) >= 3:
                avg_3m = prior_cat["amount_cr"].mean()
                delta = curr - avg_3m
                if avg_3m != 0:
                    pct_vs = (delta / abs(avg_3m)) * 100
                    label = f"{cat}: {curr:+.0f} Cr (vs 3M avg {avg_3m:+.0f} Cr; {pct_vs:+.0f}% vs avg)"
                else:
                    label = f"{cat}: {curr:+.0f} Cr (vs 3M avg: N/A)"
            else:
                label = f"{cat}: {curr:+.0f} Cr (insufficient history)"

            anomaly_lines.append(label)

        anomaly_block = "[Anomaly vs 3M Avg]\n" + "\n".join(anomaly_lines)

        # ── Thematic signals (sector categories) ──
        sector_cats = current_df[current_df["category"].str.contains("Sector|Infra|IT|PSU|Thematic", case=False, na=False)]
        thematic_lines = []

        for _, row in sector_cats.iterrows():
            cat = row["category"]
            curr = row["amount_cr"]

            # Check prior months for streak
            prior_sector = prior_cat[prior_cat["category"] == cat].sort_values("month", ascending=False)
            if len(prior_sector) >= 2:
                # Check direction
                if curr > 0 and all(prior_sector["amount_cr"] > 0):
                    streak = sum(1 for x in prior_sector["amount_cr"] if x > 0) + 1
                    thematic_lines.append(f"{cat}: +{curr:.0f} Cr ({streak}th consecutive inflow)")
                elif curr < 0 and all(prior_sector["amount_cr"] < 0):
                    streak = sum(1 for x in prior_sector["amount_cr"] if x < 0) + 1
                    thematic_lines.append(f"{cat}: {curr:.0f} Cr ({streak}th consecutive outflow)")
                else:
                    thematic_lines.append(f"{cat}: {curr:+.0f} Cr")
            else:
                thematic_lines.append(f"{cat}: {curr:+.0f} Cr")

        thematic_block = "[Thematic/Segment Signals]\n" + "\n".join(thematic_lines) if thematic_lines else ""

        # ── Top 5 gainers/losers ──
        sorted_df = current_df.sort_values("amount_cr", ascending=False)
        gainers = sorted_df.head(5)
        losers = sorted_df.tail(5).iloc[::-1]

        gainer_lines = [f"{i+1}) {r['category']}: {r['amount_cr']:+.0f} Cr" for i, (_, r) in enumerate(gainers.iterrows())]
        loser_lines  = [f"{i+1}) {r['category']}: {r['amount_cr']:+.0f} Cr" for i, (_, r) in enumerate(losers.iterrows())]

        top5_block = "[Top 5 Gainers]\n" + "\n".join(gainer_lines) + "\n\n[Top 5 Losers]\n" + "\n".join(loser_lines)

        # ── SIP trend ──
        sip_current = current_df["sip_amount_cr"].sum()
        prior_month = prior_months["month"].max()
        prior_sip = prior_months[prior_months["month"] == prior_month]["sip_amount_cr"].sum()

        if pd.notna(sip_current) and pd.notna(prior_sip):
            if sip_current > prior_sip * 1.01:
                sip_trend = f"SIP: {sip_current:,.0f} Cr (vs prior month {prior_sip:,.0f} Cr; rising)"
            elif sip_current < prior_sip * 0.99:
                sip_trend = f"SIP: {sip_current:,.0f} Cr (vs prior month {prior_sip:,.0f} Cr; falling)"
            else:
                sip_trend = f"SIP: {sip_current:,.0f} Cr (vs prior month {prior_sip:,.0f} Cr; flat)"
        else:
            sip_trend = "SIP trend: NOT AVAILABLE"

        sip_block = f"[SIP Trend]\n{sip_trend}"

        # Combine all blocks
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

def format_context_block(anchor_data: list = None) -> str:
    """
    Format Bull/Bear score + market narrative from context_engine.
    Returns pre-computed conclusions for AI prompt injection.
    """
    try:
        from src.context_engine import run_contextualization, format_context_for_ai

        if not anchor_data:
            return ""

        # Run full contextualization pipeline
        ctx = run_contextualization(anchor_data)

        if not ctx.get("fii_context", {}).get("ok"):
            return ""

        # Format for AI injection
        return format_context_for_ai(
            ctx["fii_context"],
            ctx["macro_context"],
            ctx["bull_bear"]
        )

    except Exception as e:
        print(f"⚠️ format_context_block: {e}")
        return ""


# ═══════════════════════════════════════════════════════════════════════
# BLOCK: OPTIONS INTELLIGENCE (Intelligence Layer)
# ═══════════════════════════════════════════════════════════════════════

def format_options_block(symbol: str = "NIFTY", run_label: str = "morning") -> str:
    """
    Format options analysis: max pain, PCR, OI zones.
    Morning: uses computed values directly.
    Evening: compares to morning snapshot for OI shifts.
    """
    try:
        from src.options_engine import run_options_analysis, fetch_nse_options_chain, compute_oi_shifts

        # Run options analysis for this execution
        analysis = run_options_analysis(symbol=symbol, store=True, run_label=run_label)

        if not analysis.get("ok"):
            return ""

        # Format output
        lines = []
        lines.append("📊 *OPTIONS INTELLIGENCE*\n")

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

