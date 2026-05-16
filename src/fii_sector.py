"""
FII/FPI Sector-Wise Data — Where is institutional money flowing?
Data: SEBI daily FPI activity by sector
Shows sector rotation: IT +2400 Cr | Banking -1800 Cr | Pharma +800 Cr
"""
import math
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional

SEBI_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/csv, application/json, */*",
}

# SEBI FPI data URL pattern (daily sector-wise)
SEBI_FPI_URL = "https://www.sebi.gov.in/sebiweb/data/ReportAction.do?startPeriod={start}&endPeriod={end}&type=fpi"


def _safe_float(val, default=0.0) -> float:
    """Convert to float, handle NaN/Inf."""
    try:
        f = float(str(val).replace(",", "").strip() or 0)
        return default if math.isnan(f) or math.isinf(f) else f
    except (ValueError, TypeError):
        return default


def fetch_fpi_sector_data() -> Optional[Dict]:
    """
    Fetch FPI sector-wise investment data from SEBI.
    Falls back to NSE API if SEBI is unavailable.
    """
    # Try NSE FPI activity endpoint first (more reliable API)
    data = _fetch_nse_fpi_data()
    if data:
        return data

    # Fallback: try SEBI CSV
    data = _fetch_sebi_fpi_csv()
    return data


def _fetch_nse_fpi_data() -> Optional[Dict]:
    """Fetch FPI activity from NSE API."""
    url = "https://www.nseindia.com/api/fiidiiTradeActivity"
    try:
        session = requests.Session()
        session.get("https://www.nseindia.com", headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }, timeout=10)
        resp = session.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }, timeout=15)

        if resp.status_code != 200:
            return None

        data = resp.json()

        if not data or not isinstance(data, list):
            return None

        # Parse FII/DII activity by category
        sectors = {}
        for row in data:
            category = row.get("category", "")
            buy = _safe_float(row.get("buyValue", 0))
            sell = _safe_float(row.get("sellValue", 0))
            net = buy - sell

            if "FII" in category or "FPI" in category:
                sectors["FPI Aggregate"] = {
                    "buy": buy,
                    "sell": sell,
                    "net": net,
                    "category": "aggregate",
                }

        if not sectors:
            return None

        return {
            "ok": True,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "source": "NSE",
            "sectors": sectors,
        }

    except Exception as e:
        print(f"⚠️ NSE FPI data: {e}")
        return None


def _fetch_sebi_fpi_csv() -> Optional[Dict]:
    """
    Fetch FPI sector-wise data from SEBI.
    Note: SEBI's data format may change. This is a best-effort parser.
    """
    try:
        # SEBI publishes monthly FPI sector data
        url = "https://www.sebi.gov.in/sebiweb/data/ReportAction.do?startPeriod=&endPeriod=&type=fpi"
        resp = requests.get(url, headers=SEBI_HEADERS, timeout=15)

        if resp.status_code != 200:
            return None

        # SEBI returns CSV or HTML — try to parse
        content = resp.text

        if "Sector" not in content[:500]:
            return None

        # Basic CSV parsing
        lines = content.strip().split("\n")
        if len(lines) < 3:
            return None

        # Assume first line is header
        header = lines[0].split(",")

        sectors = {}
        for line in lines[1:]:
            cols = line.split(",")
            if len(cols) >= 3:
                sector_name = cols[0].strip().strip('"')
                buy_val = _safe_float(cols[1])
                sell_val = _safe_float(cols[2])
                net_val = buy_val - sell_val

                if sector_name:
                    sectors[sector_name] = {
                        "buy": buy_val,
                        "sell": sell_val,
                        "net": net_val,
                        "category": "sector",
                    }

        if not sectors:
            return None

        return {
            "ok": True,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "source": "SEBI",
            "sectors": sectors,
        }

    except Exception as e:
        print(f"⚠️ SEBI FPI data: {e}")
        return None


def compute_sector_rotation(sector_data: Dict) -> List[Dict]:
    """
    Rank sectors by net FPI flow to identify rotation patterns.
    Returns: sorted list of sectors with flow analysis.
    """
    if not sector_data or not sector_data.get("sectors"):
        return []

    sectors = sector_data["sectors"]
    rotation = []

    for name, data in sectors.items():
        net = data.get("net", 0)
        buy = data.get("buy", 0)
        sell = data.get("sell", 0)

        # Determine flow direction
        if net > 0:
            direction = "INFLOW"
            emoji = "🟢"
        elif net < 0:
            direction = "OUTFLOW"
            emoji = "🔴"
        else:
            direction = "FLAT"
            emoji = "⚪"

        # Compute buy/sell ratio
        if sell > 0:
            bs_ratio = buy / sell
        else:
            bs_ratio = float('inf') if buy > 0 else 1.0

        rotation.append({
            "name": name,
            "buy": buy,
            "sell": sell,
            "net": net,
            "direction": direction,
            "emoji": emoji,
            "bs_ratio": round(bs_ratio, 2),
        })

    # Sort by net flow (descending)
    rotation.sort(key=lambda x: x["net"], reverse=True)
    return rotation


def format_sector_fpi(sector_data: Dict) -> str:
    """
    Format sector FPI data for prompt injection (Block 3).
    Shows top inflows, top outflows, and rotation signals.
    """
    if not sector_data or not sector_data.get("ok"):
        return ""

    rotation = compute_sector_rotation(sector_data)
    if not rotation:
        return ""

    lines = [f"[FPI Sector Activity — {sector_data.get('date', 'today')}]"]

    # Top inflows
    inflows = [s for s in rotation if s["direction"] == "INFLOW"][:3]
    if inflows:
        lines.append("Top FPI Inflows:")
        for s in inflows:
            lines.append(f"  {s['emoji']} {s['name']}: +{s['net']:,.0f} Cr (B/S: {s['bs_ratio']})")

    # Top outflows
    outflows = [s for s in rotation if s["direction"] == "OUTFLOW"][:3]
    if outflows:
        lines.append("Top FPI Outflows:")
        for s in outflows:
            lines.append(f"  {s['emoji']} {s['name']}: {s['net']:,.0f} Cr (B/S: {s['bs_ratio']})")

    # Rotation signal
    if inflows and outflows:
        top_in = inflows[0]["name"]
        top_out = outflows[0]["name"]
        lines.append(f"Rotation: {top_out} → {top_in}")

    return "\n".join(lines)


def run_sector_fpi_analysis() -> str:
    """
    Full pipeline: fetch → analyze → format.
    Returns: formatted sector FPI string for Block 3.
    """
    print("📡 Fetching FPI sector data...")
    data = fetch_fpi_sector_data()

    if not data:
        print("   ⚠️ No FPI sector data available")
        return ""

    output = format_sector_fpi(data)
    print(f"   → Sector FPI: {len(output)} chars")
    return output
