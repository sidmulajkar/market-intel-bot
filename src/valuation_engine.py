"""
Valuation Engine — Nifty & Sector Valuation Metrics
Sources: NSE API (P/E, P/B, Dividend Yield), yfinance (G-Sec yields)
Zero-cost computation for derived metrics (earnings yield, risk premium, reverse DCF)
"""
import os
import requests
from datetime import datetime
from typing import Dict, List, Optional
from src.formatters import _ordinal

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.nseindia.com/",
    "Accept": "application/json",
}


# ═══════════════════════════════════════════════════════════════════════
# NIFTY VALUATION — P/E, P/B, Dividend Yield from NSE
# ═══════════════════════════════════════════════════════════════════════

def fetch_nifty_valuation() -> Dict:
    """
    Fetch Nifty 50 valuation metrics from NSE API.
    Uses /api/allIndices endpoint which includes P/E and P/B.
    Returns: pe, pb, dividend_yield, earnings_yield, index_name
    """
    session = requests.Session()
    try:
        session.get("https://www.nseindia.com", headers=NSE_HEADERS, timeout=10)
    except Exception:
        pass

    url = "https://www.nseindia.com/api/allIndices"
    try:
        resp = session.get(url, headers=NSE_HEADERS, timeout=15)
        if resp.status_code == 403:
            session = requests.Session()
            session.get("https://www.nseindia.com", headers=NSE_HEADERS, timeout=10)
            resp = session.get(url, headers=NSE_HEADERS, timeout=15)

        if resp.status_code != 200:
            return {"ok": False, "error": f"NSE returned {resp.status_code}"}

        data = resp.json()
        indices = data.get("data", [])

        # Find NIFTY 50 in the list
        nifty = None
        for idx in indices:
            if idx.get("index") == "NIFTY 50" or idx.get("indexSymbol") == "NIFTY 50":
                nifty = idx
                break

        if not nifty:
            return {"ok": False, "error": "NIFTY 50 not found in indices"}

        pe = nifty.get("pe")
        pb = nifty.get("pb")
        last_price = nifty.get("last")
        index_name = nifty.get("index", "NIFTY 50")

        if pe is None:
            return {"ok": False, "error": "PE not found in NSE response"}

        pe = float(pe)
        pb = float(pb) if pb else None
        last_price = float(last_price) if last_price else None

        # Derived metrics
        earnings_yield = (1 / pe * 100) if pe > 0 else 0  # In %

        return {
            "ok": True,
            "index": index_name,
            "pe": round(pe, 2),
            "pb": round(pb, 2) if pb else None,
            "dividend_yield": None,  # Not available from this endpoint
            "earnings_yield": round(earnings_yield, 2),
            "last_price": last_price,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        return {"ok": False, "error": str(e)}


def fetch_sector_valuations() -> List[Dict]:
    """
    Fetch P/E and P/B for major Nifty sector indices.
    Returns list of {index, pe, pb, div_yield}.
    """
    sectors = [
        "NIFTY BANK", "NIFTY IT", "NIFTY PHARMA", "NIFTY AUTO",
        "NIFTY FMCG", "NIFTY METAL", "NIFTY ENERGY", "NIFTY REALTY",
        "NIFTY FINANCIAL SERVICES", "NIFTY PSU BANK",
    ]

    session = requests.Session()
    try:
        session.get("https://www.nseindia.com", headers=NSE_HEADERS, timeout=10)
    except Exception:
        pass

    results = []
    for sector in sectors:
        url_sector = sector.replace(" ", "%20")
        url = f"https://www.nseindia.com/api/equity-stockIndices?index={url_sector}"
        try:
            resp = session.get(url, headers=NSE_HEADERS, timeout=10)
            if resp.status_code != 200:
                continue
            data = resp.json()
            meta = data.get("metadata", {})
            pe = meta.get("pe")
            pb = meta.get("pb")
            if pe is not None:
                results.append({
                    "index": meta.get("indexName", sector),
                    "pe": round(float(pe), 2),
                    "pb": round(float(pb), 2) if pb else None,
                    "div_yield": round(float(meta.get("divYield", 0)), 2),
                })
        except Exception:
            continue

    return results


# ═══════════════════════════════════════════════════════════════════════
# DERIVED VALUATION METRICS — Zero API cost
# ═══════════════════════════════════════════════════════════════════════

def compute_equity_risk_premium(earnings_yield: float, g_sec_yield: float) -> Dict:
    """
    Equity Risk Premium = Earnings Yield - 10Y G-Sec Yield.
    Negative = equities expensive vs bonds. Positive = equities attractive.
    Returns {"ok": False} if out of plausible bounds (-10% to +15%).
    """
    premium = round(earnings_yield - g_sec_yield, 2)
    if premium < -10.0 or premium > 15.0:
        return {"ok": False, "premium": premium, "note": "ERP out of plausible bounds"}
    if premium < -2:
        label = "EXTREMELY EXPENSIVE vs bonds"
    elif premium < -1:
        label = "EXPENSIVE vs bonds"
    elif premium < 0:
        label = "SLIGHTLY EXPENSIVE vs bonds"
    elif premium < 1:
        label = "FAIR vs bonds"
    elif premium < 2:
        label = "ATTRACTIVE vs bonds"
    else:
        label = "VERY ATTRACTIVE vs bonds"

    return {
        "premium": premium,
        "label": label,
        "earnings_yield": earnings_yield,
        "g_sec_yield": g_sec_yield,
    }


def compute_reverse_dcf(pe: float, terminal_growth: float = 0.06,
                         discount_rate: float = 0.12) -> Dict:
    """
    Reverse DCF: What growth rate does the current P/E imply?
    Uses simplified Gordon Growth Model inversion.
    """
    if pe <= 0:
        return {"ok": False}

    # Implied growth = (1/PE) + terminal_growth - discount_rate... simplified
    # More accurate: earnings yield = discount_rate - growth
    # So: implied_growth = discount_rate - earnings_yield
    earnings_yield = 1 / pe
    implied_growth = discount_rate - earnings_yield

    if implied_growth > 0.15:
        assessment = "AGGRESSIVE — market pricing unrealistic growth"
    elif implied_growth > 0.10:
        assessment = "OPTIMISTIC — high growth expected"
    elif implied_growth > 0.06:
        assessment = "REASONABLE — moderate growth priced in"
    elif implied_growth > 0.02:
        assessment = "PESSIMISTIC — low growth priced in"
    else:
        assessment = "NEGATIVE — market pricing contraction"

    return {
        "ok": True,
        "implied_growth_pct": round(implied_growth * 100, 1),
        "assessment": assessment,
        "earnings_yield_pct": round(earnings_yield * 100, 2),
        "discount_rate_pct": round(discount_rate * 100, 1),
    }


# ═══════════════════════════════════════════════════════════════════════
# FORMATTER — For AI prompt injection
# ═══════════════════════════════════════════════════════════════════════

def format_valuation(val: Dict, g_sec_yield: float = None,
                      historical_pe: List[float] = None) -> str:
    """
    Format valuation metrics for AI prompt injection.
    """
    if not val or not val.get("ok"):
        return ""

    lines = [f"[Valuation — {val.get('index', 'NIFTY')}]"]
    lines.append(f"P/E: {val['pe']}x | Earnings Yield: {val['earnings_yield']}%")

    if val.get("pb"):
        lines.append(f"P/B: {val['pb']}x")
    if val.get("dividend_yield"):
        lines.append(f"Dividend Yield: {val['dividend_yield']}%")

    # Equity Risk Premium (if G-Sec yield provided)
    if g_sec_yield is not None:
        erp = compute_equity_risk_premium(val["earnings_yield"], g_sec_yield)
        lines.append(f"Equity Risk Premium: {erp['premium']:+.2f}% ({erp['label']})")

    # Reverse DCF
    rdcf = compute_reverse_dcf(val["pe"])
    if rdcf.get("ok"):
        lines.append(f"Reverse DCF: market implies {rdcf['implied_growth_pct']}% earnings growth")
        lines.append(f"  → {rdcf['assessment']}")

    # Historical percentile
    pe_pct = None
    if historical_pe and len(historical_pe) >= 5:
        from src.quant_enrichment import compute_percentile
        pct = compute_percentile(val["pe"], historical_pe)
        if pct.get("percentile") is not None:
            pe_pct = pct["percentile"]
            lines.append(f"P/E percentile: {_ordinal(int(pe_pct))} ({pct['label']})")

    # ERP vs P/E bridge — explain when they conflict
    if g_sec_yield is not None:
        erp_val = erp.get("premium", 0)
        if pe_pct is not None and pe_pct < 40 and erp_val < 0:
            lines.append("  Note: P/E historically cheap but ERP negative → bonds more attractive than equities at current rates")

    return "\n".join(lines)
