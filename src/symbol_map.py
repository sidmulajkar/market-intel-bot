"""
Symbol Map — Centralized yfinance symbol resolution.

All yfinance symbols flow through here. No hardcoded ".NS" or "^CNX*"
in any other module. Fixes: TATAMOTORS.NS, ^NSEIGS, sector index failures.

Usage:
    from src.symbol_map import to_yfinance, resolve, SECTOR_INDICES, MACRO_ANCHORS
    yf_sym = to_yfinance("TATAMOTORS")          # → "TATAMOTORS.NS"
    sym = resolve("TATAMOTORS")                 # → "TATAMOTORS.NS" (validated)
    idx = get_sector_index("Nifty Bank")        # → "^NSEBANK"
"""
from __future__ import annotations
from typing import Dict, Optional

# ═══════════════════════════════════════════════════════════════════════════════
# MACRO ANCHORS — cross-asset yfinance symbols
# ═══════════════════════════════════════════════════════════════════════════════

MACRO_ANCHORS: Dict[str, str] = {
    "USD/INR":       "USDINR=X",
    "Brent Crude":   "BZ=F",
    "Gold":          "GC=F",
    "India VIX":     "^INDIAVIX",
    "Dollar Index":  "DX-Y.NYB",
    "US 10Y Yield":  "^TNX",
    "CBOE VIX":      "^VIX",
    "HYG":           "HYG",
    "WTI Crude":     "CL=F",
    "Copper":        "HG=F",
    "S&P 500 Futures":"ES=F",
    "Nasdaq Futures": "NQ=F",
    "Nikkei 225":    "^N225",
}

# ═══════════════════════════════════════════════════════════════════════════════
# INDICES — NSE/BSE major indices
# ═══════════════════════════════════════════════════════════════════════════════

INDICES: Dict[str, str] = {
    "Nifty 50":      "^NSEI",
    "Nifty Bank":    "^NSEBANK",
    "Nifty IT":      "^CNXIT",
    "Nifty Pharma":  "^CNXPHARMA",
    "Nifty Auto":    "^CNXAUTO",
    "Nifty Metal":   "^CNXMETAL",
    "Nifty Energy":  "^CNXENERGY",
    "Nifty FMCG":    "^CNXFMCG",
    "Nifty Realty":  "^CNXREALTY",
    "Nifty PSU Bank":"^CNXPSUBANK",
    "Nifty Financial Services": "^CNXFIN",
    "Nifty Media":   "^CNXMEDIA",
    "Nifty Infra":   "^CNXINFRA",
    "Nifty 500":     "^CRSLDX",
    "Nifty Midcap 50":"^CNXMIDCAP",
    "Nifty Smallcap 250": "^CNXSCAP",
    "India VIX":     "^INDIAVIX",
    "Sensex":        "^BSESN",
    "Bankex":        "^BSEBK",
}

# Alias map — alternative names that map to the same index
INDEX_ALIASES: Dict[str, str] = {
    "CNXIT":        "Nifty IT",
    "CNXPHARMA":    "Nifty Pharma",
    "CNXAUTO":      "Nifty Auto",
    "CNXMETAL":     "Nifty Metal",
    "CNXENERGY":    "Nifty Energy",
    "CNXFMCG":      "Nifty FMCG",
    "CNXREALTY":    "Nifty Realty",
    "CNXPSUBANK":   "Nifty PSU Bank",
    "CNXFINANCE":   "Nifty Financial Services",
    "CNXFIN":       "Nifty Financial Services",
    "CNXMEDIA":     "Nifty Media",
    "CNXINFRA":     "Nifty Infra",
    "NSEBANK":      "Nifty Bank",
    "NIFTY":        "Nifty 50",
    "NIFTY50":      "Nifty 50",
    "BANKNIFTY":    "Nifty Bank",
}

# ═══════════════════════════════════════════════════════════════════════════════
# SECTOR INDICES — sector heatmap / sector_rs canonical mapping
# ═══════════════════════════════════════════════════════════════════════════════

SECTOR_INDICES: Dict[str, str] = {
    "Nifty Bank":         "^NSEBANK",
    "Nifty IT":           "^CNXIT",
    "Nifty Pharma":       "^CNXPHARMA",
    "Nifty Auto":         "^CNXAUTO",
    "Nifty Metal":        "^CNXMETAL",
    "Nifty Energy":       "^CNXENERGY",
    "Nifty FMCG":         "^CNXFMCG",
    "Nifty Realty":       "^CNXREALTY",
    "Nifty PSU Bank":     "^CNXPSUBANK",
    "Nifty Financial Services": "^CNXFIN",
    "Nifty Media":        "^CNXMEDIA",
    "Nifty Infra":        "^CNXINFRA",
}

# ═══════════════════════════════════════════════════════════════════════════════
# NIFTY 50 CONSTITUENTS — current list (update when rebalance happens)
# ═══════════════════════════════════════════════════════════════════════════════

NIFTY_50_SYMBOLS: list[str] = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "LT.NS", "AXISBANK.NS", "BAJFINANCE.NS", "ASIANPAINT.NS", "MARUTI.NS",
    "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS", "NESTLEIND.NS", "WIPRO.NS",
    "HCLTECH.NS", "M&M.NS", "NTPC.NS", "TATAMOTORS.NS", "POWERGRID.NS",
    "ONGC.NS", "JSWSTEEL.NS", "TATASTEEL.NS", "ADANIENT.NS", "ADANIPORTS.NS",
    "BAJAJFINSV.NS", "TECHM.NS", "HDFCLIFE.NS", "DIVISLAB.NS", "DRREDDY.NS",
    "CIPLA.NS", "EICHERMOT.NS", "BRITANNIA.NS", "COALINDIA.NS", "GRASIM.NS",
    "HEROMOTOCO.NS", "INDUSINDBK.NS", "TATACONSUM.NS", "APOLLOHOSP.NS",
    "BPCL.NS", "HINDALCO.NS", "SBILIFE.NS", "UPL.NS", "BAJAJ-AUTO.NS",
    "SHRIRAMFIN.NS",
]

# ═══════════════════════════════════════════════════════════════════════════════
# EXCHANGE SUFFIXES
# ═══════════════════════════════════════════════════════════════════════════════

_NSE_SUFFIX = ".NS"
_BSE_SUFFIX = ".BO"

# Known BSE-only symbols (not on NSE)
_BSE_ONLY: set[str] = set()

# Known NSE symbols (without suffix)
_NSE_STOCKS: set[str] = {s.replace(_NSE_SUFFIX, "") for s in NIFTY_50_SYMBOLS}


# ═══════════════════════════════════════════════════════════════════════════════
# RESOLUTION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def to_yfinance(symbol: str, exchange: str = "NSE") -> str:
    """
    Convert a bare symbol to yfinance format.

    Args:
        symbol: e.g. "TATAMOTORS", "^NSEI", "USDINR=X"
        exchange: "NSE" (default) or "BSE"

    Returns:
        yfinance-compatible symbol. Indices and FX pass through unchanged.
    """
    sym = symbol.strip().upper()

    # Already a yfinance symbol
    if "." in sym or sym.startswith("^") or sym.endswith("=X"):
        return sym

    # Index lookup
    if sym in INDEX_ALIASES:
        return INDICES[INDEX_ALIASES[sym]]
    if sym in INDICES:
        return INDICES[sym]

    # Macro anchor reverse lookup
    for name, yf_sym in MACRO_ANCHORS.items():
        if name.replace("/", "").replace(" ", "").upper() == sym:
            return yf_sym

    # Stock symbol — add exchange suffix
    suffix = _BSE_SUFFIX if exchange.upper() == "BSE" else _NSE_SUFFIX
    return sym + suffix


def resolve(symbol: str, timeout: float = 3.0) -> Optional[str]:
    """
    Resolve a symbol to a working yfinance ticker.

    Strategy: try .NS → try .BO → return None.
    Indices and macro anchors pass through immediately.
    """
    sym = symbol.strip().upper()

    # Already resolved (indices, FX, commodities)
    if "." in sym or sym.startswith("^") or "=" in sym:
        return sym

    # Index/alias lookup
    if sym in INDEX_ALIASES:
        return INDICES[INDEX_ALIASES[sym]]
    if sym in INDICES:
        return INDICES[sym]

    # Macro anchor reverse lookup
    for name, yf_sym in MACRO_ANCHORS.items():
        if name.replace("/", "").replace(" ", "").upper() == sym:
            return yf_sym

    # Try NSE first, then BSE
    import yfinance as yf
    for suffix in [_NSE_SUFFIX, _BSE_SUFFIX]:
        try:
            t = yf.Ticker(sym + suffix)
            info = t.fast_info
            if info and getattr(info, "last_price", None) is not None:
                return sym + suffix
        except Exception:
            continue

    return None


def get_sector_index(sector_name: str) -> Optional[str]:
    """
    Get yfinance symbol for a sector index.

    Handles both canonical names ("Nifty Bank") and short names ("Bank", "IT").
    """
    if sector_name in SECTOR_INDICES:
        return SECTOR_INDICES[sector_name]

    # Short name aliases
    short_map = {
        "BANK": "Nifty Bank",
        "IT": "Nifty IT",
        "PHARMA": "Nifty Pharma",
        "AUTO": "Nifty Auto",
        "METAL": "Nifty Metal",
        "ENERGY": "Nifty Energy",
        "FMCG": "Nifty FMCG",
        "REALTY": "Nifty Realty",
        "PSU BANK": "Nifty PSU Bank",
        "PSU": "Nifty PSU Bank",
        "FINANCIAL": "Nifty Financial Services",
        "FIN": "Nifty Financial Services",
        "MEDIA": "Nifty Media",
        "INFRA": "Nifty Infra",
    }
    key = sector_name.strip().upper()
    if key in short_map:
        return SECTOR_INDICES[short_map[key]]

    return None


def get_index_symbol(index_name: str) -> Optional[str]:
    """
    Get yfinance symbol for any index by name or alias.
    """
    key = index_name.strip().upper()
    if key in INDICES:
        return INDICES[key]
    if key in INDEX_ALIASES:
        return INDICES[INDEX_ALIASES[key]]
    return None


def is_nse_stock(symbol: str) -> bool:
    """Check if a bare symbol (no suffix) is a known NSE stock."""
    return symbol.upper().replace(_NSE_SUFFIX, "") in _NSE_STOCKS


def batch_symbols(symbols: list[str]) -> str:
    """
    Join symbols for yfinance batch download.
    Handles both already-suffixed and bare symbols.
    """
    resolved = []
    for s in symbols:
        s = s.strip()
        if not s:
            continue
        if "." in s or s.startswith("^") or "=" in s:
            resolved.append(s)
        else:
            resolved.append(s.upper() + _NSE_SUFFIX)
    return " ".join(resolved)
