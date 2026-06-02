"""
Sector Flow Intelligence — Pillar-Flow Match.
Cross-reference theoretical transmission chains of active pillars
with actual FII sector flow data. Grounds macro theory in hard cash reality.

Classification:
  CONFIRMED:   Sector flows match transmission chain predictions
               → pillar is priced in by actual capital
  UNCONFIRMED: Sector flows diverge → latent vulnerability (not yet priced)

Pillar → Sector Exposure Map:
  STAGFLATION     → selling O&G (margin squeeze), buying IT (INR hedge)
  WEST_ASIA       → selling O&G (cost pressure), buying Energy/FMCG (defensive)
  EM_CONTAGION    → selling Banking (FII liquid names), buying IT (USD rev)
  CARRY_UNWIND    → selling Banking (FII outflow channel), buying IT
  DE_DOLLARIZATION → buying Gold-related, selling Banking (USD reserve shift)
  TECH_CYCLE_BURST → selling IT (demand destruction), buying Pharma (defensive)
"""

from typing import Dict, List, Optional, Tuple


# Pillar → sector exposure mapping
# Each pillar maps to expected sector buying/selling patterns
# (sector_name, expected_direction) where direction: "buy" or "sell"
PILLAR_SECTOR_MAP = {
    "STAGFLATION_SUPPLY": {
        "label": "Stagflation & Supply Shock",
        "expectations": [
            # Brent↑ → OMC margins squeezed → FII sells O&G
            ("Oil & Gas", "sell", "Brent↑ squeezes OMC margins"),
            # PSU Banks pressured by rising NPAs + rate squeeze
            ("PSU Banks", "sell", "Rate squeeze + NPA risk pressures PSU Banks"),
            # INR↓ → IT exports become competitive → FII buys IT
            ("IT", "buy", "INR↓ boosts export competitiveness"),
            # Defensive rotation → Pharma
            ("Pharma", "buy", "Defensive rotation into Pharma"),
        ],
    },
    "WEST_ASIA": {
        "label": "West Asia Energy Crisis",
        "expectations": [
            # Energy cost spike → O&G under-recoveries
            ("Oil & Gas", "sell", "Energy cost spike widens under-recoveries"),
            # Consumer staples as inflation hedge
            ("FMCG", "buy", "Inflation-resistant consumer staples"),
            # Pharma as defensive rotation
            ("Pharma", "buy", "Defensive rotation amid geopolitical uncertainty"),
        ],
    },
    "EM_CONTAGION": {
        "label": "EM Contagion & Carry Unwind",
        "expectations": [
            # FII exodus → liquid banking names sold first
            ("Banking", "sell", "FII exodus targets liquid banking names"),
            # USD revenues shield IT from INR depreciation
            ("IT", "buy", "USD revenue exposure insulates IT"),
        ],
    },
    "CARRY_UNWIND": {
        "label": "Carry Trade Unwind",
        "expectations": [
            # DXY↑ → INR↓ → FII pulls from banking
            ("Banking", "sell", "FII outflow channel targets banking"),
            # Auto faces input cost pressure from INR depreciation
            ("Auto", "sell", "INR depreciation raises imported input costs"),
            # USD-denominated IT revenues hold up
            ("IT", "buy", "USD revenue resilience in IT"),
        ],
    },
    "DE_DOLLARIZATION": {
        "label": "De-Dollarization & Fragmentation",
        "expectations": [
            # Central bank reserve diversification → gold
            ("Insurance", "buy", "Reserve diversification into insurance"),
            # Banking sector faces reserve shift costs
            ("Banking", "sell", "USD reserve shift pressures banking"),
        ],
    },
    "TECH_CYCLE_BURST": {
        "label": "Tech Cycle & Credit Lock",
        "expectations": [
            # Global tech demand slowdown → IT sold
            ("IT", "sell", "Global tech slowdown hits IT demand"),
            # Defensive rotation into pharma
            ("Pharma", "buy", "Defensive rotation away from tech"),
        ],
    },
}

# Map sector_rs names to FII sector names for comparison
SECTOR_NAME_MAP = {
    "Nifty IT": "IT",
    "Nifty Bank": "Banking",
    "Nifty PSU Bank": "PSU Banks",
    "Nifty Financial Services": "Banking",
    "Nifty Energy": "Oil & Gas",
    "Nifty Auto": "Auto",
    "Nifty Pharma": "Pharma",
    "Nifty Metal": "Metal",
    "Nifty FMCG": "FMCG",
    "Nifty Realty": "Realty",
    "Nifty Media": "Media",
}


def compute_pillar_flow_match(active_pillars: List[Dict], lookback_days: int = 0) -> Dict:
    """
    Cross-reference active pillars with actual FII sector flows.

    Args:
        active_pillars: List from pillar_classifier.classify_pillars()
            [{"name": "STAGFLATION_SUPPLY", "score": 63.0, "tier": "ELEVATED", ...}]
        lookback_days: If > 0, caches sector flows and falls back to previous cache.

    Returns:
        Dict with per-pillar flow match results and overall summary.
    """
    if not active_pillars:
        return {"ok": False, "message": "No active pillars"}

    # Get FII sector data (with optional T-1 fallback)
    sector_flows = _fetch_fii_sector_flows(lookback_days=lookback_days)
    if not sector_flows:
        return {"ok": False, "message": "No FII sector flow data available"}

    results = []
    total_confirmed = 0
    total_expectations = 0

    for pillar in active_pillars:
        pillar_name = pillar.get("name", "")
        pillar_config = PILLAR_SECTOR_MAP.get(pillar_name)
        if not pillar_config:
            continue

        # Only check ACTIVE+ pillars (score >= 40)
        if pillar.get("score", 0) < 40:
            continue

        expectations = pillar_config["expectations"]
        pillar_results = []

        for sector_name, expected_dir, rationale in expectations:
            total_expectations += 1

            # Look up actual sector flow
            actual_flow = sector_flows.get(sector_name)
            if actual_flow is None:
                pillar_results.append({
                    "sector": sector_name,
                    "expected": expected_dir,
                    "actual_flow": None,
                    "match": "NO_DATA",
                    "rationale": rationale,
                })
                continue

            # Determine actual direction
            if actual_flow > 100:
                actual_dir = "buy"
            elif actual_flow < -100:
                actual_dir = "sell"
            else:
                actual_dir = "flat"

            match = actual_dir == expected_dir
            if match:
                total_confirmed += 1

            pillar_results.append({
                "sector": sector_name,
                "expected": expected_dir,
                "actual_flow": round(actual_flow),
                "actual_dir": actual_dir,
                "match": "CONFIRMED" if match else "UNCONFIRMED",
                "rationale": rationale,
            })

        results.append({
            "pillar_name": pillar_name,
            "pillar_label": pillar_config["label"],
            "pillar_score": pillar["score"],
            "pillar_tier": pillar.get("tier", ""),
            "matches": pillar_results,
            "confirmed_count": sum(1 for m in pillar_results if m.get("match") == "CONFIRMED"),
            "total_count": len(pillar_results),
        })

    if not results:
        return {"ok": False, "message": "No active pillars >= 40 score"}

        # Overall assessment
        if total_expectations > 0:
            confirmation_rate = round((total_confirmed / total_expectations) * 100, 1)
        else:
            confirmation_rate = 0.0

        if confirmation_rate >= 60:
            overall = "HIGH CONFIRMATION — Pillars priced in by capital flows"
        elif confirmation_rate >= 30:
            overall = "PARTIAL CONFIRMATION — Some pillars validated, others latent"
        else:
            overall = "LOW CONFIRMATION — Pillar risks not yet priced by market"

        return {
            "ok": True,
            "overall": overall,
            "confirmation_rate": confirmation_rate,
            "total_confirmed": total_confirmed,
            "total_expectations": total_expectations,
            "pillar_results": results,
            "data_source": sector_flows.get("_data_source"),
        }


def _fetch_fii_sector_flows(lookback_days: int = 0) -> Dict[str, float]:
    """Fetch FII sector flow data and return {sector_name: net_flow} dict.

    Tries fii_sector module first, falls back gracefully.
    Maps sector names to canonical labels used in PILLAR_SECTOR_MAP.

    Args:
        lookback_days: If > 0, caches successful fetch to Supabase bot_state
                       for historical fallback; on primary failure, reads cache.
    """
    source_date = None
    result = {}
    try:
        from src.fii_sector import fetch_fpi_sector_data, compute_sector_rotation

        data = fetch_fpi_sector_data()
        if data and data.get("ok"):
            source_date = data.get("date", "")
            rotation = compute_sector_rotation(data)
            if rotation:
                for s in rotation:
                    name = s.get("name", "")
                    net = s.get("net", 0)
                    canonical = _map_sector_name(name)
                    if canonical:
                        result[canonical] = result.get(canonical, 0) + net
                    else:
                        result[name] = net

        # Cache to Supabase if requested and data is available
        if lookback_days > 0 and result:
            try:
                from src.db import get_client
                client = get_client()
                if client:
                    client.table("bot_state").upsert({
                        "key": "last_sector_flows",
                        "value": {"flows": result, "date": source_date},
                    }).execute()
            except Exception as e:
                print(f"⚠️ sectoral_drag: cache error: {e}")
    except Exception as e:
        print(f"⚠️ sectoral_drag: FII sector data unavailable: {e}")

    # If primary fetch failed and lookback_days > 0, try cached data
    if not result and lookback_days > 0:
        try:
            from src.db import get_bot_state
            cached = get_bot_state("last_sector_flows")
            if cached and isinstance(cached, dict) and cached.get("flows"):
                result = cached["flows"]
                result["_data_source"] = "T-1"
                print(f"   → Using cached sector flows (T-1: {cached.get('date', 'unknown')})")
        except Exception as e:
            print(f"⚠️ sectoral_drag: cache read error: {e}")

    return result


def _map_sector_name(name: str) -> Optional[str]:
    """Map a sector name from data sources to canonical PILLAR_SECTOR_MAP name."""
    name_upper = name.upper().strip()

    mapping = {
        "IT": "IT", "INFORMATION TECHNOLOGY": "IT", "TECHNOLOGY": "IT",
        "BANKING": "Banking", "BANKS": "Banking", "PSU BANKS": "PSU Banks", "PUBLIC SECTOR BANKS": "PSU Banks", "FINANCIAL SERVICES": "Banking",
        "OIL": "Oil & Gas", "GAS": "Oil & Gas", "ENERGY": "Oil & Gas",
        "OIL & GAS": "Oil & Gas", "OIL AND GAS": "Oil & Gas",
        "PHARMA": "Pharma", "PHARMACEUTICALS": "Pharma", "HEALTHCARE": "Pharma",
        "FMCG": "FMCG", "CONSUMER GOODS": "FMCG", "CONSUMER": "FMCG",
        "AUTO": "Auto", "AUTOMOBILES": "Auto", "AUTOMOTIVE": "Auto",
        "METAL": "Metal", "METALS": "Metal", "MINING": "Metal",
        "REALTY": "Realty", "REAL ESTATE": "Realty", "PROPERTY": "Realty",
        "MEDIA": "Media", "ENTERTAINMENT": "Media",
        "INSURANCE": "Insurance",
    }

    for key, canonical in mapping.items():
        if key == name_upper or key in name_upper or name_upper in key:
            return canonical

    return None


def format_pillar_flow_match(match: Dict) -> str:
    """Format pillar-flow match for AI prompt injection."""
    if not match.get("ok"):
        return ""

    source_tag = ""
    if match.get("data_source") == "T-1":
        source_tag = " (T-1)"

    lines = [f"[Pillar-Flow Match — {match['overall']}]{source_tag}"]
    lines.append(f"  Confirmation Rate: {match['confirmation_rate']}% ({match['total_confirmed']}/{match['total_expectations']} expectations met)")
    lines.append("")

    for pr in match.get("pillar_results", []):
        lines.append(f"  {pr['pillar_label']} ({pr['pillar_tier']}, Score: {pr['pillar_score']:.0f})")
        for m in pr.get("matches", []):
            if m["match"] == "CONFIRMED":
                icon = "✅"
            elif m["match"] == "UNCONFIRMED":
                icon = "❌"
            else:
                icon = "⚪"

            flow_str = f"₹{m['actual_flow']:+,}Cr" if m["actual_flow"] is not None else "N/A"
            lines.append(f"    {icon} {m['sector']}: expected {m['expected']}, actual {flow_str} ({m['match']})")
            lines.append(f"       Rationale: {m['rationale']}")

        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    # Test with synthetic pillars
    test_pillars = [
        {"name": "STAGFLATION_SUPPLY", "score": 63, "tier": "ELEVATED"},
        {"name": "EM_CONTAGION", "score": 53, "tier": "ACTIVE"},
        {"name": "CARRY_UNWIND", "score": 47, "tier": "ACTIVE"},
    ]
    result = compute_pillar_flow_match(test_pillars)
    print(format_pillar_flow_match(result))
