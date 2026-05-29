"""
Sector Relative Strength — Rank 11 Nifty sectors by RS vs Nifty 50.
Quantified sector rotation: 1W/1M/3M relative strength scores.

Source: yfinance sector index tickers via symbol_map (free, batch fetch).
"""
import yfinance as yf
import statistics
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.symbol_map import SECTOR_INDICES


# Canonical benchmark
NIFTY_50 = "^NSEI"


# ═══════════════════════════════════════════════════════════════════════════════
# DATA FETCHING
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_sector_data() -> Dict:
    """
    Fetch Nifty 50 + all sector indices in parallel.
    Returns {sector_name: {"price": float, "1d": float, "1w": float, "1m": float, "3m": float}}
    """
    import time

    all_symbols = {NIFTY_50: "Nifty 50"}
    all_symbols.update(SECTOR_INDICES)

    try:
        # Batch fetch all tickers at once (single yfinance call)
        tickers = list(all_symbols.keys())
        data = yf.download(tickers, period="3mo", interval="1d",
                           group_by="ticker", progress=False, threads=True)

        results = {}

        for symbol, name in all_symbols.items():
            try:
                if len(tickers) > 1:
                    series = data[symbol]["Close"].dropna()
                else:
                    series = data["Close"].dropna()

                if series is None or len(series) < 5:
                    continue

                current = float(series.iloc[-1])

                # Compute returns
                def _pct_change(series, days):
                    if len(series) > days:
                        return round(((series.iloc[-1] / series.iloc[-days]) - 1) * 100, 2)
                    return 0.0

                results[name] = {
                    "symbol": symbol,
                    "price": current,
                    "1d": _pct_change(series, 1),
                    "1w": _pct_change(series, 5),
                    "1m": _pct_change(series, 21),
                    "3m": _pct_change(series, 63),
                }
            except Exception:
                continue

        return results

    except Exception as e:
        print(f"⚠️ Sector data fetch error: {e}")
        return {}


def compute_relative_strength(sector_data: Dict) -> List[Dict]:
    """
    Compute relative strength vs Nifty 50 for each sector.
    RS = sector return / Nifty return (ratio > 1 = outperforming)
    RS Score = weighted combination of 1W/1M/3M RS (0-100)
    """
    if not sector_data or "Nifty 50" not in sector_data:
        return []

    nifty = sector_data["Nifty 50"]
    sectors = []

    for name, data in sector_data.items():
        if name == "Nifty 50":
            continue

        # Relative strength for each period
        nifty_1w = nifty.get("1w", 0)
        nifty_1m = nifty.get("1m", 0)
        nifty_3m = nifty.get("3m", 0)

        def _rs(sector_ret, nifty_ret):
            if nifty_ret == 0:
                return 1.0 if sector_ret == 0 else 2.0 if sector_ret > 0 else 0.0
            return round(sector_ret / nifty_ret, 2) if nifty_ret != 0 else 1.0

        rs_1w = _rs(data.get("1w", 0), nifty_1w)
        rs_1m = _rs(data.get("1m", 0), nifty_1m)
        rs_3m = _rs(data.get("3m", 0), nifty_3m)

        # RS Score: weighted combination (1M has highest weight)
        # 1W: 20%, 1M: 50%, 3M: 30%
        rs_raw = 0.2 * rs_1w + 0.5 * rs_1m + 0.3 * rs_3m

        # Normalize to 0-100 scale
        # RS=1.0 means in-line with Nifty → score ~50
        # RS=1.5 means 50% outperformance → score ~75
        # RS=0.5 means 50% underperformance → score ~25
        rs_score = max(0, min(100, round(rs_raw * 50)))

        # Momentum: 1M return
        momentum_1m = data.get("1m", 0)

        # Money flow direction (price × volume trend — simplified)
        if data.get("1w", 0) > 0 and data.get("1m", 0) > 0:
            flow = "INFLOW"
        elif data.get("1w", 0) < 0 and data.get("1m", 0) < 0:
            flow = "OUTFLOW"
        else:
            flow = "MIXED"

        sectors.append({
            "name": name,
            "price": data.get("price"),
            "rs_1w": rs_1w,
            "rs_1m": rs_1m,
            "rs_3m": rs_3m,
            "rs_score": rs_score,
            "momentum_1m": momentum_1m,
            "flow": flow,
            "return_1d": data.get("1d", 0),
        })

    # Sort by RS score (highest = strongest)
    sectors.sort(key=lambda x: x["rs_score"], reverse=True)

    # Add rank
    for i, s in enumerate(sectors):
        s["rank"] = i + 1
        s["vs_nifty"] = "OUTPERFORM" if s["rs_score"] > 55 else "UNDERPERFORM" if s["rs_score"] < 45 else "INLINE"

    return sectors


# ═══════════════════════════════════════════════════════════════════════════════
# FORMATTING
# ═══════════════════════════════════════════════════════════════════════════════

def format_sector_rs(sectors: List[Dict]) -> str:
    """Format sector RS rankings for AI prompt injection."""
    if not sectors:
        return ""

    lines = ["[Sector Relative Strength — Ranked vs Nifty 50]"]
    lines.append("RS Score: 100=strong outperform, 50=inline, 0=strong underperform")
    lines.append("")

    # Top 3 + Bottom 3
    lines.append("  TOP 3 (Strongest):")
    for s in sectors[:3]:
        icon = "🟢" if s["rs_score"] > 60 else "⚪"
        lines.append(f"    {icon} #{s['rank']} {s['name']}: RS={s['rs_score']} | 1M={s['momentum_1m']:+.1f}% | {s['flow']}")

    lines.append("")
    lines.append("  BOTTOM 3 (Weakest):")
    for s in sectors[-3:]:
        icon = "🔴" if s["rs_score"] < 40 else "⚪"
        lines.append(f"    {icon} #{s['rank']} {s['name']}: RS={s['rs_score']} | 1M={s['momentum_1m']:+.1f}% | {s['flow']}")

    # Sector rotation signal
    top3_names = [s["name"] for s in sectors[:3]]
    bottom3_names = [s["name"] for s in sectors[-3:]]

    defensive = ["Nifty FMCG", "Nifty Pharma", "Nifty IT"]
    cyclicals = ["Nifty Metal", "Nifty Auto", "Nifty Realty", "Nifty Energy"]

    top_defensive = sum(1 for s in top3_names if s in defensive)
    top_cyclical = sum(1 for s in top3_names if s in cyclicals)

    if top_defensive >= 2:
        rotation = "DEFENSIVE rotation — risk-off signal"
    elif top_cyclical >= 2:
        rotation = "CYCLICAL rotation — risk-on signal"
    else:
        rotation = "MIXED rotation — no clear preference"

    lines.append(f"\n  Rotation: {rotation}")

    # Full table
    lines.append("\n  Full Ranking:")
    for s in sectors:
        marker = "★" if s["rank"] <= 3 else "☆" if s["rank"] >= len(sectors) - 2 else " "
        lines.append(f"  {marker} #{s['rank']:2d} {s['name']:<25s} RS={s['rs_score']:3d} | 1W={s['rs_1w']:+.2f} | 1M={s['rs_1m']:+.2f} | 3M={s['rs_3m']:+.2f} | {s['flow']}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def run_sector_rs_analysis() -> Dict:
    """
    Full sector RS analysis pipeline.
    Returns structured data + formatted block for AI prompt.
    """
    sector_data = fetch_sector_data()
    if not sector_data:
        return {"ok": False, "message": "No sector data available"}

    sectors = compute_relative_strength(sector_data)
    if not sectors:
        return {"ok": False, "message": "Could not compute relative strength"}

    formatted = format_sector_rs(sectors)

    return {
        "ok": True,
        "sectors": sectors,
        "formatted": formatted,
        "nifty_price": sector_data.get("Nifty 50", {}).get("price"),
    }


if __name__ == "__main__":
    result = run_sector_rs_analysis()
    if result["ok"]:
        print(result["formatted"])
    else:
        print(f"Error: {result.get('message')}")
