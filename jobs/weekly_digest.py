import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_fetcher      import fetch_global_indices, fetch_top_movers, fetch_general_news, fetch_macro_anchors
from src.heatmap_generator import generate_heatmap
from src.sector_heatmap    import generate_sector_heatmap, generate_top_movers_heatmap
from src.formatters        import format_weekly_digest, format_top_movers
from src.ai_engine         import AIEngine
from src.telegram_sender   import send_image, send_text
from src.db                import (get_fii_dii_flows, get_breadth_history,
                                   get_fii_institutions, get_daily_market_snapshots,
                                   get_macro_history, save_daily_snapshot)
from src.quant_enrichment  import (compute_sector_regime, compute_volatility_setup,
                                   compute_risk_appetite, compute_breadth_thrust,
                                   compute_fii_institutional_footprint,
                                   format_institutional_signals)
from src.context_engine    import run_contextualization

def compute_scorecard() -> dict:
    """Compute weekly prediction scorecard from stored data."""
    try:
        from src.prediction_tracker import get_weekly_accuracy
        stats = get_weekly_accuracy(days=7)
        if not stats.get("ok"):
            return {"ok": False}

        best  = stats.get("best", {})
        worst = stats.get("worst", {})
        return {
            "ok": True,
            "correct": stats["correct"],
            "total": stats["total"],
            "accuracy_pct": stats["hit_rate"],
            "best_call": f"{best.get('date','')} {'✅' if best.get('correct') else '❌'} ({best.get('change',0):+.1f}%)",
            "worst_call": f"{worst.get('date','')} {'✅' if worst.get('correct') else '❌'} ({worst.get('change',0):+.1f}%)",
        }
    except Exception as e:
        print(f"⚠️ Scorecard: {e}")
        return {"ok": False}


def compute_fii_weekly_pattern() -> dict:
    """Compute FII weekly pattern from stored flows — no API call."""
    try:
        flows = get_fii_dii_flows(days=14)
        if not flows or len(flows) < 3:
            return {"ok": False}

        # Sum this week
        weekly_fii = sum(f.get("fiinet_cr", 0) for f in flows[-5:])
        weekly_dii = sum(f.get("diinet_cr", 0) for f in flows[-5:])

        # 4W average
        all_fii = [f.get("fiinet_cr", 0) for f in flows]
        avg_4w  = round(sum(all_fii) / len(all_fii)) if all_fii else 0

        # Streak detection (count consecutive same-sign weeks)
        streak = 1
        for i in range(len(flows) - 1, 0, -1):
            if (flows[i].get("fiinet_cr", 0) > 0) == (flows[i-1].get("fiinet_cr", 0) > 0):
                streak += 1
            else:
                break

        return {
            "ok": True,
            "weekly_net": round(weekly_fii),
            "dii_net": round(weekly_dii),
            "4w_avg": avg_4w,
            "streak_weeks": streak,
        }
    except Exception as e:
        print(f"⚠️ FII pattern: {e}")
        return {"ok": False}


def compute_regime_shift() -> dict:
    """Compare Monday vs Friday regime from stored daily snapshots."""
    try:
        snapshots = get_daily_market_snapshots(days=7)
        if not snapshots or len(snapshots) < 2:
            return {"ok": False}

        monday  = snapshots[0]
        friday  = snapshots[-1]

        mon_score = monday.get("bull_bear_score", 50)
        fri_score = friday.get("bull_bear_score", 50)
        change    = fri_score - mon_score

        def label(score):
            if score >= 70: return "Strongly Bullish"
            if score >= 60: return "Bullish"
            if score >= 45: return "Neutral"
            if score >= 30: return "Cautious"
            return "Bearish"

        # Determine what changed
        mon_nifty = monday.get("nifty_change", 0)
        fri_nifty = friday.get("nifty_change", 0)
        if abs(change) > 10:
            driver = "Sharp shift in market sentiment"
        elif abs(change) > 5:
            driver = "Gradual sentiment change"
        else:
            driver = "Regime stable"

        return {
            "ok": True,
            "monday_score": mon_score,
            "friday_score": fri_score,
            "monday_label": label(mon_score),
            "friday_label": label(fri_score),
            "score_change": change,
            "what_changed": driver,
        }
    except Exception as e:
        print(f"⚠️ Regime shift: {e}")
        return {"ok": False}


def compute_institutional_signals() -> dict:
    """Compute all 5 institutional signals from stored data."""
    signals = {}

    # Sector regime — from stored macro snapshots or compute from top movers
    try:
        # Try to get sector performance from weekly top movers
        movers = fetch_top_movers(top_n=10)
        if movers:
            # Derive sector perf from top movers (approximate)
            sector_perf = {}
            for m in movers.get("india", {}).get("gainers", []) + movers.get("india", {}).get("losers", []):
                sym = m.get("symbol", "")
                # Map symbols to sectors (rough approximation)
                if sym in ("HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK"):
                    sector_perf.setdefault("BANK", []).append(m.get("weekly_pct", m.get("change_pct", 0)))
                elif sym in ("TATAMOTORS", "M&M", "MARUTI", "BAJAJ-AUTO", "HEROMOTOCO"):
                    sector_perf.setdefault("AUTO", []).append(m.get("weekly_pct", m.get("change_pct", 0)))
                elif sym in ("TCS", "INFY", "WIPRO", "TECHM", "HCLTECH"):
                    sector_perf.setdefault("IT", []).append(m.get("weekly_pct", m.get("change_pct", 0)))
                elif sym in ("RELIANCE", "ONGC", "BPCL", "IOC"):
                    sector_perf.setdefault("ENERGY", []).append(m.get("weekly_pct", m.get("change_pct", 0)))
                elif sym in ("SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB"):
                    sector_perf.setdefault("PHARMA", []).append(m.get("weekly_pct", m.get("change_pct", 0)))
                elif sym in ("HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA"):
                    sector_perf.setdefault("FMCG", []).append(m.get("weekly_pct", m.get("change_pct", 0)))
                elif sym in ("TATASTEEL", "JSW", "HINDALCO", "VEDL"):
                    sector_perf.setdefault("METAL", []).append(m.get("weekly_pct", m.get("change_pct", 0)))

            # Average sector performance
            avg_sector = {k: round(sum(v)/len(v), 2) for k, v in sector_perf.items() if v}
            signals["sector_regime"] = compute_sector_regime(avg_sector)
    except Exception as e:
        print(f"⚠️ Sector regime: {e}")

    # Volatility setup — from stored VIX history
    try:
        vix_history_raw = get_macro_history("India VIX", days=90)
        vix_values = [v.get("price", 0) for v in vix_history_raw if v.get("price")]
        vix_current = vix_values[-1] if vix_values else None
        if vix_values and vix_current:
            signals["volatility_setup"] = compute_volatility_setup(vix_values, vix_current)
    except Exception as e:
        print(f"⚠️ Volatility setup: {e}")

    # Risk appetite — derive from sector regime data
    try:
        sr = signals.get("sector_regime", {})
        if sr.get("ok"):
            sector_perf_proxy = {}
            for s, v in sr.get("leaders", []):
                sector_perf_proxy[s] = v
            for s, v in sr.get("laggards", []):
                sector_perf_proxy[s] = v
            signals["risk_appetite"] = compute_risk_appetite(sector_perf_proxy)
    except Exception as e:
        print(f"⚠️ Risk appetite: {e}")

    # Breadth thrust — from stored breadth history
    try:
        breadth = get_breadth_history(days=30)
        if breadth:
            signals["breadth_thrust"] = compute_breadth_thrust(breadth)
    except Exception as e:
        print(f"⚠️ Breadth thrust: {e}")

    # FII institutional footprint — from stored institutional data
    try:
        institutions = get_fii_institutions(days=30)
        if institutions:
            signals["fii_footprint"] = compute_fii_institutional_footprint(institutions)
    except Exception as e:
        print(f"⚠️ FII footprint: {e}")

    return signals


def main():
    print("=" * 50)
    print("📅 WEEKLY DIGEST STARTING")
    print("=" * 50)

    ai = AIEngine()

    # ── 1. Heatmaps (2 max — global + sector) ─────────────────────
    print("📊 Generating heatmaps...")
    index_data  = fetch_global_indices()
    valid_index = {k: v for k, v in index_data.items()
                   if v.get("ok") and v.get("price", 0) > 0}

    try:
        send_image(generate_heatmap(valid_index), caption="📅 *Weekly Global Heatmap*")
    except Exception as e:
        print(f"⚠️ World heatmap: {e}")

    try:
        send_image(generate_sector_heatmap(), caption="🏭 *Weekly Sector Performance*")
    except Exception as e:
        print(f"⚠️ Sector heatmap: {e}")

    # ── 2. Fetch dynamic data ──────────────────────────────────────
    print("📊 Fetching top movers + news...")
    movers = fetch_top_movers(top_n=10)
    raw_news = fetch_general_news()

    from src.validator import validate_articles, assess_sentiment_consensus
    validated_news = validate_articles(raw_news, min_trust=6) if raw_news else []
    sentiments = []
    for article in validated_news[:5]:
        sent = ai.sentiment(article.get("headline", ""))
        article["sentiment"] = sent
        if sent:
            sentiments.append(sent)
    consensus = assess_sentiment_consensus(sentiments) if sentiments else "neutral"

    # ── 3. Compute all signals from stored data ────────────────────
    print("📊 Computing signals from stored data...")
    scorecard    = compute_scorecard()
    fii_pattern  = compute_fii_weekly_pattern()
    regime_shift = compute_regime_shift()

    print("📊 Computing institutional signals...")
    inst_signals = compute_institutional_signals()
    inst_formatted = format_institutional_signals(inst_signals) if inst_signals else ""

    # Top movers heatmap
    try:
        send_image(generate_top_movers_heatmap(movers), caption="📊 *Top Movers — India & US*")
    except Exception as e:
        print(f"⚠️ Movers heatmap: {e}")

    # ── 4. Bull/Bear context ───────────────────────────────────────
    bull_bear = {}
    try:
        anchor_data = fetch_macro_anchors()
        if anchor_data:
            ctx = run_contextualization(anchor_data)
            bull_bear = ctx.get("bull_bear", {})
    except Exception as e:
        print(f"⚠️ Context: {e}")

    # ── 5. AI summary ──────────────────────────────────────────────
    print("🤖 Generating AI weekly narrative...")
    ai_summary = ""
    try:
        prompt = AIEngine.weekly_digest_intelligence_prompt(
            scorecard=scorecard,
            fii_pattern=fii_pattern,
            regime_shift=regime_shift,
            institutional_signals=inst_signals,
            global_indices=valid_index,
            news_items=validated_news,
            bull_bear=bull_bear
        )
        ai_summary = ai.analyze("volume", prompt)
    except Exception as e:
        print(f"⚠️ AI summary: {e}")

    # ── 6. Format and send digest ──────────────────────────────────
    digest = format_weekly_digest(
        scorecard=scorecard,
        fii_pattern=fii_pattern,
        regime_shift=regime_shift,
        movers=movers,
        institutional=inst_formatted,
        ai_summary=ai_summary,
    )
    send_text(digest)

    # ── 7. Save snapshot for future weeks ──────────────────────────
    try:
        save_daily_snapshot(valid_index)
    except Exception as e:
        print(f"⚠️ Snapshot: {e}")

    # ── 8. Top movers detailed text ────────────────────────────────
    try:
        movers_text = format_top_movers(movers)
        if movers_text:
            send_text(movers_text)
    except Exception as e:
        print(f"⚠️ Movers text: {e}")

    send_text("📅 *Weekly digest complete!*\n_See you Monday 🌅_")
    print("✅ WEEKLY DIGEST COMPLETE")


if __name__ == "__main__":
    main()
