"""
FII Concentration Index (HHI) — Herfindahl-Hirschman Index of FII flows.
High concentration = fragile, single-stock dependent.
Low concentration = broad accumulation, sustainable.

Compute from bulk/block deal data in fii_institution_tracker table.
"""
import statistics
from typing import Dict, List, Optional


def compute_hhi(flows: Dict[str, float]) -> float:
    """
    Compute Herfindahl-Hirschman Index.
    HHI = sum of (share_i)^2 where share_i = flow_i / total_flow.
    Returns 0-10000 scale (0 = perfectly distributed, 10000 = all in one).
    """
    total = sum(abs(v) for v in flows.values())
    if total == 0:
        return 0

    shares = [(abs(v) / total) * 100 for v in flows.values()]
    hhi = sum(s ** 2 for s in shares)
    return round(hhi)


def compute_fii_concentration(fii_deals: List[Dict]) -> Dict:
    """
    Compute FII concentration from bulk/block deal data.
    fii_deals: list of {symbol, flow_amount, date}
    Returns HHI + concentration analysis.
    """
    if not fii_deals:
        return {"ok": False, "message": "No FII deal data"}

    # Aggregate flows by stock
    stock_flows = {}
    for deal in fii_deals:
        symbol = deal.get("symbol", "UNKNOWN")
        amount = deal.get("flow_amount", 0) or 0
        stock_flows[symbol] = stock_flows.get(symbol, 0) + amount

    if not stock_flows:
        return {"ok": False, "message": "No flow data"}

    hhi = compute_hhi(stock_flows)
    total_stocks = len(stock_flows)
    total_flow = sum(abs(v) for v in stock_flows.values())

    # Top 5 stocks by flow
    sorted_stocks = sorted(stock_flows.items(), key=lambda x: abs(x[1]), reverse=True)
    top_5 = sorted_stocks[:5]
    top_5_pct = sum(abs(v) for _, v in top_5) / total_flow * 100 if total_flow > 0 else 0

    # Concentration classification
    if hhi > 2500:
        classification = "HIGHLY CONCENTRATED — fragile, single-stock risk"
    elif hhi > 1500:
        classification = "MODERATELY CONCENTRATED — watch for rotation"
    elif hhi > 1000:
        classification = "MODERATELY DISTRIBUTED — healthy"
    else:
        classification = "WIDELY DISTRIBUTED — broad accumulation, sustainable"

    # Trend indicator
    avg_hhi = statistics.mean([compute_hhi({s: stock_flows[s] for s in stock_flows if s != "OTHERS"}) for _ in [1]]) if len(stock_flows) > 5 else hhi

    return {
        "ok": True,
        "hhi": hhi,
        "total_stocks": total_stocks,
        "total_flow": round(total_flow),
        "top_5": [(s, round(v)) for s, v in top_5],
        "top_5_pct": round(top_5_pct, 1),
        "classification": classification,
    }


def format_fii_concentration(conc: Dict) -> str:
    """Format FII concentration for AI prompt."""
    if not conc.get("ok"):
        return ""

    lines = [f"[FII Concentration Index (HHI)]"]
    lines.append(f"  HHI: {conc['hhi']} / 10,000 — {conc['classification']}")
    lines.append(f"  Stocks: {conc['total_stocks']} | Total flow: ₹{conc['total_flow']:,}Cr")
    lines.append(f"  Top 5 stocks account for {conc['top_5_pct']:.1f}% of total FII flow:")
    for stock, flow in conc.get("top_5", []):
        lines.append(f"    {stock}: ₹{flow:+,}Cr")

    if conc["hhi"] > 2000:
        lines.append(f"\n  ⚠️ High concentration — FII activity concentrated in few stocks.")
        lines.append(f"  Single-stock risk elevated. Broadening = healthier signal.")

    return "\n".join(lines)


if __name__ == "__main__":
    # Test
    test_deals = [
        {"symbol": "RELIANCE", "flow_amount": 500},
        {"symbol": "TCS", "flow_amount": 300},
        {"symbol": "HDFCBANK", "flow_amount": 200},
        {"symbol": "INFY", "flow_amount": 150},
        {"symbol": "ICICIBANK", "flow_amount": 100},
        {"symbol": "SBIN", "flow_amount": 80},
        {"symbol": "BHARTIARTL", "flow_amount": 70},
    ]
    result = compute_fii_concentration(test_deals)
    print(format_fii_concentration(result))
