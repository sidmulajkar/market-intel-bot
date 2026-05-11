"""
Mutual Fund Flow Tracker
Sources:
  1. mfapi.in       — Free Indian MF API, no auth, updated daily
  2. AMFI NAVAll.txt — All scheme NAVs, completely free, no auth

Dependencies: requests, pandas — both already in requirements.txt
No mftool library needed — calls APIs directly via requests
"""
import time
import requests
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional

MFAPI_BASE = "https://api.mfapi.in/mf"
AMFI_URL   = "https://www.amfiindia.com/spages/NAVAll.txt"

# ── DEFAULT SCHEMES (used only if Supabase watchlist is empty) ────
DEFAULT_SCHEMES = {
    "119598": "SBI Bluechip Fund",
    "119551": "Axis Bluechip Fund",
    "120503": "HDFC Top 100 Fund",
    "100016": "HDFC Equity Fund",
    "101206": "ICICI Pru Bluechip",
    "120178": "Mirae Asset Large Cap",
    "120716": "Kotak Bluechip Fund",
    "120828": "SBI Midcap Fund",
    "120841": "HDFC Midcap Opportunities",
    "119755": "Axis Long Term Equity",
}


# ── SINGLE SCHEME NAV ─────────────────────────────────────────────

def fetch_scheme_nav(scheme_code: str) -> Optional[Dict]:
    """
    Fetch latest NAV and 1-day change for a scheme via mfapi.in.
    Free, no auth required, updated daily by AMFI.
    """
    try:
        resp = requests.get(
            f"{MFAPI_BASE}/{scheme_code}",
            timeout=10,
        )
        if resp.status_code != 200:
            return None

        data     = resp.json()
        nav_data = data.get("data", [])
        meta     = data.get("meta", {})

        if not nav_data or len(nav_data) < 1:
            return None

        today_nav = float(nav_data[0]["nav"])

        # Compute change if previous NAV available
        if len(nav_data) >= 2:
            prev_nav   = float(nav_data[1]["nav"])
            change_pct = ((today_nav - prev_nav) / prev_nav) * 100
        else:
            prev_nav   = today_nav
            change_pct = 0.0

        return {
            "scheme_code": scheme_code,
            "scheme_name": meta.get("scheme_name",     ""),
            "fund_house":  meta.get("fund_house",      ""),
            "category":    meta.get("scheme_category", ""),
            "nav":         round(today_nav, 4),
            "prev_nav":    round(prev_nav,  4),
            "change_pct":  round(change_pct, 4),
            "nav_date":    nav_data[0].get("date", ""),
            "ok":          True,
        }

    except Exception as e:
        print(f"  ⚠️  mfapi error (scheme {scheme_code}): {e}")
        return None


# ── AMFI NAV ALL ──────────────────────────────────────────────────

def fetch_amfi_nav_all() -> Dict[str, Dict]:
    """
    Download AMFI NAVAll.txt — every scheme's current NAV.
    Completely free, no rate limits, updated daily by AMFI.
    Returns dict keyed by scheme code.
    """
    print("  📥 Downloading AMFI NAVAll.txt...")
    try:
        resp = requests.get(AMFI_URL, timeout=30)
        if resp.status_code != 200:
            print(f"  ⚠️  AMFI HTTP {resp.status_code}")
            return {}

        schemes          = {}
        current_category = ""
        lines            = resp.text.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Category header — no semicolons
            if ";" not in line:
                current_category = line
                continue

            parts = line.split(";")
            if len(parts) < 5:
                continue

            try:
                code    = parts[0].strip()
                name    = parts[3].strip()
                nav_str = parts[4].strip()

                if not nav_str or nav_str in ["N.A.", "NA", "-", ""]:
                    continue
                if not code.isdigit():
                    continue

                nav = float(nav_str)
                schemes[code] = {
                    "scheme_code": code,
                    "scheme_name": name,
                    "category":    current_category,
                    "nav":         nav,
                    "date":        parts[5].strip() if len(parts) > 5 else "",
                }
            except (ValueError, IndexError):
                continue

        print(f"  ✅ AMFI: {len(schemes)} schemes loaded")
        return schemes

    except Exception as e:
        print(f"  ⚠️  AMFI NAVAll fetch error: {e}")
        return {}


# ── SEARCH MF BY NAME ─────────────────────────────────────────────

def search_mf_by_name(query: str, max_results: int = 8) -> List[Dict]:
    """
    Search AMFI NAVAll.txt for schemes matching a query string.
    Used by Telegram /searchmf command.
    Returns top matches with scheme code and name.
    """
    try:
        resp = requests.get(AMFI_URL, timeout=30)
        if resp.status_code != 200:
            return []

        results     = []
        query_upper = query.upper().strip()

        for line in resp.text.split("\n"):
            line = line.strip()
            if ";" not in line:
                continue
            parts = line.split(";")
            if len(parts) < 4:
                continue
            code = parts[0].strip()
            name = parts[3].strip()
            if query_upper in name.upper() and code.isdigit():
                results.append({
                    "scheme_code": code,
                    "scheme_name": name,
                })
            if len(results) >= max_results:
                break

        return results

    except Exception as e:
        print(f"  ⚠️  MF search error: {e}")
        return []


# ── TOP MF PERFORMANCE ────────────────────────────────────────────

def fetch_top_mf_performance() -> List[Dict]:
    """
    Fetch NAV + performance for all schemes in the Supabase MF watchlist.
    Falls back to DEFAULT_SCHEMES if Supabase is empty.
    Returns list sorted by day change (best first).
    """
    # ── Load scheme list from Supabase ───────────────────────────
    try:
        from src.db import get_mf_watchlist
        db_schemes = get_mf_watchlist()
    except Exception:
        db_schemes = []

    if db_schemes:
        scheme_map = {
            s["scheme_code"]: s.get("scheme_name", s["scheme_code"])
            for s in db_schemes
        }
        print(f"  💹 Tracking {len(scheme_map)} schemes from Supabase")
    else:
        scheme_map = DEFAULT_SCHEMES
        print(f"  💹 Using {len(scheme_map)} default schemes (Supabase empty)")

    results = []
    for code, display_name in scheme_map.items():
        data = fetch_scheme_nav(code)
        if data and data.get("ok"):
            # Use our known display name if available
            data["display_name"] = display_name or data.get("scheme_name", code)
            results.append(data)
        time.sleep(0.3)  # Polite rate limiting for mfapi.in

    # Sort by day change — best performing first
    results.sort(key=lambda x: x.get("change_pct", 0), reverse=True)
    print(f"  ✅ MF performance: {len(results)}/{len(scheme_map)} schemes fetched")
    return results


# ── MF SUMMARY ────────────────────────────────────────────────────

def get_mf_summary() -> Dict:
    """
    Build complete MF flow summary.
    Returns top gainers, top losers, all schemes.
    """
    print("💹 Building MF flow summary...")
    all_schemes = fetch_top_mf_performance()

    gainers = [s for s in all_schemes if s.get("change_pct", 0) > 0]
    losers  = [s for s in all_schemes if s.get("change_pct", 0) < 0]
    flat    = [s for s in all_schemes if s.get("change_pct", 0) == 0]

    return {
        "top_gainers":   gainers[:5],
        "top_losers":    losers[-5:] if losers else [],
        "flat":          flat,
        "all_schemes":   all_schemes,
        "total_tracked": len(all_schemes),
        "date":          datetime.now().strftime("%d %b %Y"),
    }


# ── TELEGRAM FORMATTER ────────────────────────────────────────────

def format_mf_message(summary: Dict) -> str:
    """Format MF flow summary for Telegram"""
    msg  = "💹 *MUTUAL FUND FLOWS*\n"
    msg += f"_{summary.get('date', 'Today')} | "
    msg += f"Tracking {summary['total_tracked']} schemes_\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    if not summary["all_schemes"]:
        msg += (
            "_No MF data available_\n\n"
            "_Note: AMFI updates NAV daily after market close._\n"
            "_Data may not be available on weekends/holidays._"
        )
        return msg

    # Top gainers
    if summary["top_gainers"]:
        msg += "🟢 *TOP PERFORMING SCHEMES TODAY:*\n"
        for s in summary["top_gainers"][:5]:
            name = s.get("display_name") or s.get("scheme_name", "")
            msg += (
                f"  • *{name[:40]}*\n"
                f"    NAV: ₹{s['nav']} | "
                f"Change: *{s['change_pct']:+.2f}%* "
                f"| Date: {s.get('nav_date', '')}\n"
            )
        msg += "\n"

    # Top losers
    if summary["top_losers"]:
        msg += "🔴 *WORST PERFORMING SCHEMES TODAY:*\n"
        for s in reversed(summary["top_losers"][:5]):
            name = s.get("display_name") or s.get("scheme_name", "")
            msg += (
                f"  • *{name[:40]}*\n"
                f"    NAV: ₹{s['nav']} | "
                f"Change: *{s['change_pct']:+.2f}%*\n"
            )
        msg += "\n"

    # Quick stats
    total   = summary["total_tracked"]
    g_count = len(summary["top_gainers"])
    l_count = len(summary["top_losers"])
    f_count = len(summary.get("flat", []))
    msg += (
        f"📊 *Summary:* {g_count} up | "
        f"{l_count} down | {f_count} flat "
        f"out of {total} tracked\n\n"
        "_/listmf to see your schemes | "
        "/addmf CODE to add more_"
    )

    return msg