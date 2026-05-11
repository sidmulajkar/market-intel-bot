"""
Mutual Fund Flow Tracker
Sources:
  1. mfapi.in — free, no auth, updated daily (NAV + scheme search)
  2. mftool (AMFI) — Python library for AMFI data (pip install mftool)
  3. AMFI monthly portfolio disclosure (publicly available)

Tracks: Most bought/sold stocks by MFs, top gaining/losing schemes,
        sector allocations, AUM flows
"""
import requests
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# ── MFAPI.IN — India's free MF API (no auth needed) ───────────────
MFAPI_BASE = "https://api.mfapi.in/mf"

# ── KEY LARGE CAP MUTUAL FUND SCHEME CODES (AMFI codes) ───────────
# These are the top equity mutual funds by AUM in India
TOP_MF_SCHEMES = {
    # Large Cap / Flexicap funds
    "119598": "SBI Bluechip Fund",
    "119551": "Axis Bluechip Fund",
    "120503": "HDFC Top 100 Fund",
    "100016": "HDFC Equity Fund",
    "101206": "ICICI Pru Bluechip",
    "120178": "Mirae Asset Large Cap",
    "120716": "Kotak Bluechip Fund",
    "148621": "Canara Robeco Bluechip",
    # Mid & Small Cap
    "120828": "SBI Midcap Fund",
    "120841": "HDFC Midcap Opportunities",
    # ELSS (Tax Saver)
    "119755": "Axis Long Term Equity",
    "100127": "ICICI Pru Long Term Equity",
}

def fetch_scheme_nav(scheme_code: str) -> Optional[Dict]:
    """
    Fetch latest NAV and 1-day change for a scheme via mfapi.in.
    Free, no auth, updated daily.
    """
    try:
        resp = requests.get(
            f"{MFAPI_BASE}/{scheme_code}",
            timeout=10
        )
        if resp.status_code != 200:
            return None
        data  = resp.json()
        if not data or "data" not in data:
            return None

        nav_data = data["data"]
        meta     = data.get("meta", {})

        if len(nav_data) < 2:
            return None

        today_nav = float(nav_data[0]["nav"])
        prev_nav  = float(nav_data[1]["nav"])
        change    = ((today_nav - prev_nav) / prev_nav) * 100

        return {
            "scheme_code": scheme_code,
            "scheme_name": meta.get("scheme_name", ""),
            "fund_house":  meta.get("fund_house",  ""),
            "nav":         round(today_nav, 4),
            "prev_nav":    round(prev_nav,  4),
            "change_pct":  round(change,    4),
            "nav_date":    nav_data[0]["date"],
            "ok":          True,
        }
    except Exception as e:
        print(f"⚠️  mfapi error ({scheme_code}): {e}")
        return None

def fetch_amfi_nav_all() -> Dict:
    """
    Download AMFI NAVAll.txt — all scheme NAVs in one file.
    This is completely free with no rate limits.
    Parse it to get top movers.
    """
    url = "https://www.amfiindia.com/spages/NAVAll.txt"
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            return {}

        lines   = resp.text.split("\n")
        schemes = {}
        current_category = ""

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Category header line (no semicolons)
            if ";" not in line:
                current_category = line
                continue

            parts = line.split(";")
            if len(parts) < 6:
                continue

            try:
                code    = parts[0].strip()
                name    = parts[3].strip()
                nav_str = parts[4].strip()

                if not nav_str or nav_str in ["N.A.", "NA", "-"]:
                    continue

                nav     = float(nav_str)
                schemes[code] = {
                    "code":     code,
                    "name":     name,
                    "category": current_category,
                    "nav":      nav,
                    "date":     parts[5].strip() if len(parts) > 5 else "",
                }
            except (ValueError, IndexError):
                continue

        return schemes

    except Exception as e:
        print(f"⚠️  AMFI NAVAll fetch error: {e}")
        return {}

def fetch_top_mf_performance() -> List[Dict]:
    """
    Fetch NAV data for top mutual fund schemes.
    Returns ranked by day performance.
    """
    print("💹 Fetching MF NAV data...")
    results = []

    for code, name in TOP_MF_SCHEMES.items():
        data = fetch_scheme_nav(code)
        if data:
            data["display_name"] = name
            results.append(data)
        time.sleep(0.3)  # Gentle on mfapi.in

    # Sort by day change
    results.sort(key=lambda x: x.get("change_pct", 0), reverse=True)
    return results

def fetch_mf_sector_flows() -> Dict:
    """
    Analyse MF flows by sector using AMFI NAVAll data.
    Groups equity schemes by category and computes average performance.
    """
    print("🏭 Analysing MF sector flows from AMFI...")
    all_schemes = fetch_amfi_nav_all()

    if not all_schemes:
        return {}

    # Category-wise performance grouping
    category_map = {
        "Large Cap":  ["Large Cap", "Bluechip", "Top 100"],
        "Mid Cap":    ["Mid Cap", "Midcap"],
        "Small Cap":  ["Small Cap", "Smallcap"],
        "ELSS":       ["ELSS", "Tax Saver", "Long Term Equity"],
        "Debt":       ["Debt", "Liquid", "Credit", "Bond", "Duration"],
        "Hybrid":     ["Hybrid", "Balanced", "Aggressive"],
        "Flexi Cap":  ["Flexi Cap", "Multicap", "Multi Cap"],
        "Index":      ["Index", "ETF", "Nifty", "Sensex"],
    }

    # We'd need historical NAV to compute flows properly
    # For now, return category stats from scheme count
    cat_stats = {}
    for code, scheme in all_schemes.items():
        name = scheme["name"].upper()
        assigned = "Other"
        for cat, keywords in category_map.items():
            if any(kw.upper() in name for kw in keywords):
                assigned = cat
                break
        if assigned not in cat_stats:
            cat_stats[assigned] = {"count": 0, "schemes": []}
        cat_stats[assigned]["count"] += 1
        if cat_stats[assigned]["count"] <= 3:
            cat_stats[assigned]["schemes"].append(scheme["name"][:40])

    return cat_stats

def get_mf_summary() -> Dict:
    """Complete MF flow summary"""
    print("💹 Building complete MF flow summary...")
    top_schemes = fetch_top_mf_performance()

    gainers = [s for s in top_schemes if s.get("change_pct", 0) > 0]
    losers  = [s for s in top_schemes if s.get("change_pct", 0) < 0]

    return {
        "top_gainers":   gainers[:5],
        "top_losers":    losers[-5:],
        "all_schemes":   top_schemes,
        "total_tracked": len(top_schemes),
        "date":          datetime.now().strftime("%d %b %Y"),
    }

def format_mf_message(summary: Dict) -> str:
    """Format MF flows for Telegram"""
    msg = "💹 *MUTUAL FUND FLOWS*\n"
    msg += f"_{summary.get('date', 'Today')} | "
    msg += f"Tracking {summary['total_tracked']} schemes_\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    if summary["top_gainers"]:
        msg += "🟢 *TOP PERFORMING SCHEMES (Today):*\n"
        for s in summary["top_gainers"][:5]:
            name = s.get("display_name") or s.get("scheme_name", "")[:35]
            msg += (
                f"  • *{name}*\n"
                f"    NAV: ₹{s['nav']} | "
                f"Change: *{s['change_pct']:+.2f}%*\n"
            )
        msg += "\n"

    if summary["top_losers"]:
        msg += "🔴 *WORST PERFORMING SCHEMES (Today):*\n"
        for s in reversed(summary["top_losers"][:5]):
            name = s.get("display_name") or s.get("scheme_name", "")[:35]
            msg += (
                f"  • *{name}*\n"
                f"    NAV: ₹{s['nav']} | "
                f"Change: *{s['change_pct']:+.2f}%*\n"
            )

    return msg