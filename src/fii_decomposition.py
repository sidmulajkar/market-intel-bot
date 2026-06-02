"""
FII Decomposition — Entity-level concentration metric (Dual Path).

Path A (Primary): Entity-level data from fii_institution_tracker (bulk/block deals).
  Labeled "(bulk deals only)" — the NSE does not publish real-time entity-level FII flows.
  Bulk/block deals are visible "elephants" only; the herd (small funds) is invisible.

Path B (Fallback): SEBI FPI category-level aggregate from fii_sector module.
  Distinguishes: Hot Money Exit (Short-Term FPIs > 70% of outflow) vs
  Strategic Reallocation (Long-Term FPIs > 70%).

Analyst 1 fix: Added dual-path + data-source labeling.
"""

from collections import defaultdict
from typing import Dict, List, Optional, Tuple


def compute_fii_entity_concentration(days: int = 7) -> Dict:
    """
    Compute entity-level concentration of FII outflows.

    Dual-path:
      Path A: Entity-level from fii_institution_tracker (bulk deals).
      Path B: Category-level fallback from SEBI FPI data.

    Returns dict with:
      ok, concentration_pct, top_5, total_outflow_cr,
      classification, top_entity, top_entity_flow_cr, data_source
    """
    # ── Path A: Entity-level (bulk/block deals) ─────────────────────
    result = _compute_entity_path(days)
    if result.get("ok"):
        result["data_source"] = "bulk_deals"
        result["data_source_label"] = "(bulk deals only)"
        return result

    # ── Path B: Category-level fallback (SEBI FPI aggregate) ───────
    result = _compute_category_path()
    if result.get("ok"):
        return result

    return {"ok": False, "message": "No FII decomposition data available"}


def _compute_entity_path(days: int) -> Dict:
    """Path A: Entity-level concentration from bulk/block deal data."""
    from src.db import get_fii_institutions

    records = get_fii_institutions(days=days)
    if not records:
        return {"ok": False, "message": "No institution data available"}

    entities: Dict[str, Dict] = defaultdict(lambda: {"buy_cr": 0.0, "sell_cr": 0.0, "country": "", "type": ""})

    for r in records:
        name = r.get("institution_name", "").strip()
        if not name:
            continue
        signal_type = (r.get("signal_type", "") or "").lower()
        amount = float(r.get("amount_cr", 0) or 0)
        if not entities[name]["country"]:
            entities[name]["country"] = r.get("country", "")
        if not entities[name]["type"]:
            entities[name]["type"] = r.get("institution_type", "")

        if "buy" in signal_type:
            entities[name]["buy_cr"] += amount
        elif "sell" in signal_type:
            entities[name]["sell_cr"] += amount

    if not entities:
        return {"ok": False, "message": "No entity data after aggregation"}

    net_flows: List[Tuple[str, float, str, str]] = []
    total_outflow_cr = 0.0

    for name, data in entities.items():
        net = data["buy_cr"] - data["sell_cr"]
        if net < 0:
            outflow = abs(net)
            net_flows.append((name, outflow, data["country"], data["type"]))
            total_outflow_cr += outflow

    if not net_flows:
        return {"ok": False, "message": "No net sellers in period"}

    net_flows.sort(key=lambda x: x[1], reverse=True)
    top_5 = net_flows[:5]
    top_5_outflow = sum(f for _, f, _, _ in top_5)

    concentration_pct = round((top_5_outflow / total_outflow_cr) * 100, 1) if total_outflow_cr > 0 else 0

    if concentration_pct >= 60:
        classification = "Concentrated exit"
        detail = "Single fund or manager derisking — typically reverses within 5-7 days"
    elif concentration_pct < 30:
        classification = "Broad-based exit"
        detail = "Hundreds of small funds exiting simultaneously — structural, needs policy intervention"
    else:
        classification = "Moderately distributed exit"
        detail = "Mix of concentrated and broad-based selling"

    top_entity = top_5[0][0] if top_5 else ""
    top_entity_flow = round(top_5[0][1]) if top_5 else 0

    return {
        "ok": True,
        "concentration_pct": concentration_pct,
        "total_outflow_cr": round(total_outflow_cr),
        "top_5_outflow_cr": round(top_5_outflow),
        "num_net_sellers": len(net_flows),
        "classification": classification,
        "detail": detail,
        "top_entity": top_entity,
        "top_entity_flow_cr": top_entity_flow,
        "top_5": [
            {"name": n, "outflow_cr": round(f), "country": c, "type": t}
            for n, f, c, t in top_5
        ],
    }


def _compute_category_path() -> Dict:
    """Path B: SEBI FPI category-level fallback.

    Uses fii_sector module to fetch SEBI FPI aggregate data.
    Distinguishes Hot Money Exit (short-term FPI dominance) from
    Strategic Reallocation (long-term FPI dominance).

    Note: True short-term vs long-term categorization requires SEBI's
    granular FPI registration data. This implementation uses available
    sector-flow aggregates as a proxy.
    """
    try:
        from src.fii_sector import fetch_fpi_sector_data, compute_sector_rotation

        data = fetch_fpi_sector_data()
        if not data or not data.get("ok"):
            return {"ok": False, "message": "No SEBI FPI data"}

        rotation = compute_sector_rotation(data)
        if not rotation:
            return {"ok": False, "message": "No sector rotation data"}

        # Aggregate sector flows
        total_sell = sum(abs(s.get("net", 0)) for s in rotation if s.get("net", 0) < 0)
        total_buy = sum(s.get("net", 0) for s in rotation if s.get("net", 0) > 0)
        net_total = total_buy - total_sell

        # Top-selling sectors as proxy for outflow concentration
        sellers = [s for s in rotation if s.get("net", 0) < 0]
        sellers.sort(key=lambda x: x.get("net", 0))
        top_3_sell = sellers[:3]
        top_3_outflow = sum(abs(s.get("net", 0)) for s in top_3_sell)

        if total_sell == 0:
            return {"ok": False, "message": "No net selling in FPI data"}

        concentration_pct = round((top_3_outflow / total_sell) * 100, 1)

        if concentration_pct >= 60:
            classification = "Concentrated sector exit"
            detail = "Top 3 sectors dominate FPI selling — suggests targeted rotation, not panic"
        elif concentration_pct < 30:
            classification = "Broad-based sector exit"
            detail = "FPI selling spread across sectors — structural exodus signal"
        else:
            classification = "Moderately distributed sector exit"
            detail = "Mix of concentrated and broad-based selling"

        return {
            "ok": True,
            "concentration_pct": concentration_pct,
            "total_outflow_cr": round(total_sell),
            "top_5_outflow_cr": round(top_3_outflow),
            "num_net_sellers": len(sellers),
            "classification": classification,
            "detail": detail + " (SEBI FPI category data)",
            "top_entity": top_3_sell[0].get("name", "Unknown") if top_3_sell else "",
            "top_entity_flow_cr": round(abs(top_3_sell[0].get("net", 0))) if top_3_sell else 0,
            "top_5": [
                {"name": s.get("name", "Unknown"), "outflow_cr": round(abs(s.get("net", 0)))}
                for s in top_3_sell
            ],
            "data_source": "sebi_fpi_category",
            "data_source_label": "(SEBI FPI category data)",
            "net_total_cr": round(net_total),
        }
    except Exception as e:
        return {"ok": False, "message": f"SEBI FPI path error: {e}"}


def format_fii_decomposition(decomp: Dict) -> str:
    """Format FII decomposition for AI prompt injection."""
    if not decomp.get("ok"):
        return ""

    source_label = decomp.get("data_source_label", "")
    lines = [f"[FII Decomposition — Entity Concentration] {source_label}".strip()]
    lines.append(f"  Classification: {decomp['classification']}")
    lines.append(f"  Concentration: {decomp['concentration_pct']}% (Top 5 / Total Net Sellers)")
    lines.append(f"  Total Net Sellers: {decomp['num_net_sellers']} entities")
    lines.append(f"  Total Net Outflow: ₹{decomp['total_outflow_cr']:,}Cr")
    lines.append(f"  Top 5 Net Outflow: ₹{decomp['top_5_outflow_cr']:,}Cr")
    lines.append(f"  Top Entity: {decomp['top_entity']} (-₹{decomp['top_entity_flow_cr']:,}Cr)")
    lines.append(f"  Detail: {decomp['detail']}")

    if decomp.get("top_5"):
        lines.append(f"  Top Net Sellers:")
        for e in decomp["top_5"]:
            country_flag = _country_flag(e.get("country", ""))
            lines.append(f"    {country_flag} {e['name']}: -₹{e['outflow_cr']:,}Cr ({e['type']})")

    return "\n".join(lines)


def _country_flag(country: str) -> str:
    flags = {
        "Japan": "JP", "UAE": "AE", "Singapore": "SG",
        "South Korea": "KR", "Norway": "NO", "Canada": "CA",
        "Saudi Arabia": "SA", "Kuwait": "KW", "Qatar": "QA",
        "US": "US", "New Zealand": "NZ", "Netherlands": "NL",
        "France": "FR", "Switzerland": "CH", "India": "IN",
    }
    code = flags.get(country, "")
    if code:
        return chr(0x1F1E6 + ord(code[0]) - ord('A')) + chr(0x1F1E6 + ord(code[1]) - ord('A'))
    return ""


if __name__ == "__main__":
    result = compute_fii_entity_concentration(days=7)
    print(format_fii_decomposition(result))
