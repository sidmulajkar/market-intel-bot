"""
Smart FII Institution Tracker — Intelligence layer for institutional activity in India.
Tracks SWFs, pension funds, global asset managers, and Indian institutions.

Data sources:
- NSE bulk/block deals API (historical, 7-day lookback)
- Supabase fii_institution_tracker table (historical patterns)
- Supabase fii_dii_flows table (FII divergence signal)
- Static watchlist (config/swf_watchlist.json)
"""
import json
import os
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict


NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
}

_WATCHLIST_CACHE = None


# ═══════════════════════════════════════════════════════════════════════════════
# WATCHLIST LOADING
# ═══════════════════════════════════════════════════════════════════════════════

def load_swf_watchlist() -> Dict:
    """Load all institutional watchlists from config."""
    global _WATCHLIST_CACHE
    if _WATCHLIST_CACHE is not None:
        return _WATCHLIST_CACHE

    try:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "swf_watchlist.json")
        with open(config_path, "r") as f:
            _WATCHLIST_CACHE = json.load(f)
        return _WATCHLIST_CACHE
    except Exception as e:
        print(f"⚠️ SWF watchlist load error: {e}")
        return {"sovereign_funds": [], "pension_funds": [], "global_managers": [], "indian_institutions": []}


def _get_all_funds() -> List[Dict]:
    """Get flat list of all tracked funds with type tag."""
    wl = load_swf_watchlist()
    funds = []
    for f in wl.get("sovereign_funds", []):
        f["_type"] = "swf"
        funds.append(f)
    for f in wl.get("pension_funds", []):
        f["_type"] = "pension"
        funds.append(f)
    for f in wl.get("global_managers", []):
        f["_type"] = "asset_manager"
        funds.append(f)
    for f in wl.get("indian_institutions", []):
        f["_type"] = f.get("type", "institution")
        funds.append(f)
    return funds


def _get_max_aum() -> float:
    """Get max AUM in watchlist for normalization."""
    funds = _get_all_funds()
    return max((f.get("aum_bn", 0) for f in funds), default=1)


# ═══════════════════════════════════════════════════════════════════════════════
# NAME MATCHING — fuzzy match against all tracked institutions
# ═══════════════════════════════════════════════════════════════════════════════

def _match_institution(name: str, watchlist: Dict = None) -> Optional[Dict]:
    """Check if a counterparty name matches a known institution."""
    if not name:
        return None

    if watchlist is None:
        watchlist = load_swf_watchlist()

    name_upper = name.upper().strip()

    # Build lookup from all fund categories
    all_funds = _get_all_funds()

    # Direct match on name or full_name
    for fund in all_funds:
        fund_name = fund["name"].upper()
        full_name = fund.get("full_name", "").upper()
        if fund_name in name_upper or name_upper in fund_name:
            return fund
        if full_name and (full_name in name_upper or name_upper in full_name):
            return fund

    # Fuzzy patterns for common abbreviations
    patterns = {
        "GPIF": ["GPIF", "GOVERNMENT PENSION INVESTMENT"],
        "ADIA": ["ADIA", "ABU DHABI INVESTMENT"],
        "GIC": ["GIC PTE", "GIC PRIVATE"],
        "TEMASEK": ["TEMASEK"],
        "NBIM": ["NBIM", "NORGES BANK"],
        "CDPQ": ["CDPQ", "CAISSE DEPOT"],
        "PIF": ["PUBLIC INVESTMENT FUND"],
        "KIA": ["KIA", "KUWAIT INVESTMENT"],
        "QIA": ["QIA", "QATAR INVESTMENT"],
        "NPS": ["NPS", "NATIONAL PENSION SERVICE"],
        "CALPERS": ["CALPERS", "CALIFORNIA PUBLIC EMPLOYEES"],
        "OTPP": ["OTPP", "ONTARIO TEACHERS"],
        "CPP": ["CPP INVESTMENT", "CANADA PENSION"],
        "BLACKROCK": ["BLACKROCK", "ISHARES", "BLK"],
        "VANGUARD": ["VANGUARD"],
        "FIDELITY": ["FIDELITY"],
        "MORGAN STANLEY": ["MORGAN STANLEY"],
        "GOLDMAN": ["GOLDMAN SACHS", "GSAM"],
        "JP MORGAN": ["JP MORGAN", "JPMORGAN", "J.P. MORGAN"],
        "AMUNDI": ["AMUNDI"],
        "UBS": ["UBS ASSET", "UBS AM"],
        "LIC": ["LIC OF INDIA", "LIFE INSURANCE CORP"],
        "SBI LIFE": ["SBI LIFE"],
        "HDFC LIFE": ["HDFC LIFE"],
        "ICICI PRU": ["ICICI PRUDENTIAL"],
        "SBI MF": ["SBI MUTUAL", "SBI FUND"],
        "HDFC MF": ["HDFC MUTUAL", "HDFC FUND"],
        "ICICI MF": ["ICICI MUTUAL", "ICICI FUND"],
        "NIPPON MF": ["NIPPON LIFE", "NIPPON INDIA"],
        "KOTAK MF": ["KOTAK MAHINDRA", "KOTAK MUTUAL"],
    }

    for fund_key, pats in patterns.items():
        for pat in pats:
            if pat in name_upper:
                for fund in all_funds:
                    if fund["name"].upper() == fund_key:
                        return fund

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# NSE DEAL FETCHING — historical lookback (7 days)
# ═══════════════════════════════════════════════════════════════════════════════

def _safe_float(val) -> float:
    """Safely convert to float."""
    try:
        return float(val) if val else 0.0
    except (ValueError, TypeError):
        return 0.0


def _is_valid_indian_symbol(symbol: str) -> bool:
    """Check if symbol looks like a valid Indian equity symbol."""
    if not symbol:
        return False
    skip = {"-", "NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYIT"}
    return symbol.upper().strip() not in skip


def fetch_nse_deals(days: int = 7) -> List[Dict]:
    """
    Fetch NSE bulk + block deals for last N days using historical API.
    Reuses the pattern from insider_tracker.py.
    Returns unified list with: date, symbol, client, side, qty, price, value_cr, deal_type
    """
    from_d = (datetime.now() - timedelta(days=days)).strftime("%d-%m-%Y")
    to_d = datetime.now().strftime("%d-%m-%Y")

    all_deals = []

    for deal_type in ["bulk_deals", "block_deals"]:
        url = (
            f"https://www.nseindia.com/api/historicalOR/bulk-block-short-deals"
            f"?optionType={deal_type}&segment=NSE&from={from_d}&to={to_d}"
        )
        try:
            from src.nse_session import nse_get
            resp = nse_get(url, timeout=20)

            if resp.status_code != 200:
                continue

            data = resp.json()
            rows = data if isinstance(data, list) else data.get("data", [])

            for r in rows:
                symbol = r.get("BD_SYMBOL", "")
                if not _is_valid_indian_symbol(symbol):
                    continue

                qty = _safe_float(r.get("BD_QTY_TRD", 0))
                price = _safe_float(r.get("BD_TP_WATP", 0))
                val_rs = qty * price
                if val_rs <= 0:
                    continue

                all_deals.append({
                    "date": r.get("BD_DT_DATE", ""),
                    "symbol": symbol,
                    "company": r.get("BD_SCRIP_NAME", ""),
                    "client": r.get("BD_CLIENT_NAME", ""),
                    "side": r.get("BD_BUY_SELL", "").strip(),
                    "qty": qty,
                    "price": price,
                    "value_cr": round(val_rs / 1e7, 2),
                    "deal_type": "block" if "block" in deal_type else "bulk",
                })

        except Exception as e:
            print(f"⚠️ NSE {deal_type} fetch error: {e}")

    return all_deals


# ═══════════════════════════════════════════════════════════════════════════════
# DEAL SCANNING — match deals against institutional watchlist
# ═══════════════════════════════════════════════════════════════════════════════

def scan_deals_for_institutions(deals: List[Dict]) -> List[Dict]:
    """Scan NSE deals for matches against full institutional watchlist."""
    watchlist = load_swf_watchlist()
    all_funds = _get_all_funds()
    max_aum = _get_max_aum()
    signals = []

    for deal in deals:
        client_name = deal.get("client", "")
        match = _match_institution(client_name, watchlist)
        if not match:
            continue

        # AUM weight (normalized 0-1)
        aum_weight = round(match.get("aum_bn", 0) / max_aum, 2) if max_aum > 0 else 0.5
        weighted_cr = round(deal["value_cr"] * aum_weight, 2)

        signals.append({
            "date": deal.get("date", ""),
            "institution_name": match["name"],
            "institution_type": match.get("_type", "unknown"),
            "country": match.get("country", ""),
            "aum_bn": match.get("aum_bn", 0),
            "bias": match.get("bias", "unknown"),
            "side": deal.get("side", ""),
            "symbol": deal.get("symbol", ""),
            "company": deal.get("company", ""),
            "qty": deal.get("qty", 0),
            "price": deal.get("price", 0),
            "value_cr": deal["value_cr"],
            "aum_weight": aum_weight,
            "weighted_cr": weighted_cr,
            "deal_type": deal.get("deal_type", ""),
            "client_name": client_name,
        })

    return signals


# ═══════════════════════════════════════════════════════════════════════════════
# HISTORICAL PATTERN ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_institutional_patterns(days: int = 90) -> Dict:
    """
    Analyze stored fii_institution_tracker data for patterns.
    Returns: per-institution net flow, frequency trends, new entrants, exits.
    """
    from src.db import get_fii_institutions
    records = get_fii_institutions(days=days)
    if not records:
        return {"ok": False, "message": "No historical data"}

    now = datetime.now()
    recent_cutoff = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    old_cutoff = (now - timedelta(days=60)).strftime("%Y-%m-%d")

    # Per-institution aggregation
    institutions = defaultdict(lambda: {
        "net_flow_cr": 0, "buy_count": 0, "sell_count": 0,
        "total_deals": 0, "symbols": set(), "recent_deals": 0, "old_deals": 0,
        "aum_bn": 0, "country": "", "type": "",
    })

    for r in records:
        name = r.get("institution_name", "")
        date = r.get("date", "")
        amount = r.get("amount_cr", 0) or 0
        signal_type = r.get("signal_type", "")

        inst = institutions[name]
        inst["total_deals"] += 1
        inst["country"] = r.get("country", "")

        if "buy" in signal_type.lower():
            inst["buy_count"] += 1
            inst["net_flow_cr"] += amount
        elif "sell" in signal_type.lower():
            inst["sell_count"] += 1
            inst["net_flow_cr"] -= amount

        if date >= recent_cutoff:
            inst["recent_deals"] += 1
        elif date >= old_cutoff:
            inst["old_deals"] += 1

    # Look up AUM from watchlist
    all_funds = _get_all_funds()
    fund_map = {f["name"]: f for f in all_funds}
    for name, data in institutions.items():
        fund = fund_map.get(name, {})
        data["aum_bn"] = fund.get("aum_bn", 0)
        data["type"] = fund.get("_type", "unknown")

    # Detect signals
    signals = {
        "new_entrants": [],
        "exits": [],
        "accelerating": [],
        "decelerating": [],
        "net_accumulators": [],
        "net_distributors": [],
    }

    for name, data in institutions.items():
        # New entrant: deals in last 30 days, none in previous 60
        if data["recent_deals"] > 0 and data["old_deals"] == 0:
            signals["new_entrants"].append({"name": name, "deals": data["recent_deals"], "aum_bn": data["aum_bn"]})

        # Exit: deals in previous 60, none in last 30
        if data["old_deals"] > 0 and data["recent_deals"] == 0:
            signals["exits"].append({"name": name, "old_deals": data["old_deals"]})

        # Accelerating: recent 30d deals > 2x old 30d deals
        if data["recent_deals"] > 2 and data["old_deals"] > 0:
            ratio = data["recent_deals"] / data["old_deals"]
            if ratio >= 2:
                signals["accelerating"].append({"name": name, "ratio": round(ratio, 1), "recent": data["recent_deals"]})

        # Decelerating: old 30d deals > 2x recent
        if data["old_deals"] > 2 and data["recent_deals"] > 0:
            ratio = data["old_deals"] / data["recent_deals"]
            if ratio >= 2:
                signals["decelerating"].append({"name": name, "ratio": round(ratio, 1)})

        # Net accumulators / distributors
        if data["net_flow_cr"] > 100:
            signals["net_accumulators"].append({"name": name, "net_cr": data["net_flow_cr"], "deals": data["recent_deals"]})
        elif data["net_flow_cr"] < -100:
            signals["net_distributors"].append({"name": name, "net_cr": data["net_flow_cr"], "deals": data["recent_deals"]})

    return {
        "ok": True,
        "institutions": dict(institutions),
        "signals": signals,
        "total_records": len(records),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# FII FLOW DIVERGENCE — cross-reference with aggregate FII
# ═══════════════════════════════════════════════════════════════════════════════

def compute_fii_swf_divergence(swf_signals: List[Dict]) -> Dict:
    """
    Compare SWF net activity with aggregate FII flows.
    Divergence = smart money vs retail money signal.
    """
    from src.db import get_fii_dii_flows

    # SWF net flow from today's signals
    swf_buy = sum(s["value_cr"] for s in swf_signals if s.get("side", "").upper() == "BUY")
    swf_sell = sum(s["value_cr"] for s in swf_signals if s.get("side", "").upper() == "SELL")
    swf_net = swf_buy - swf_sell

    # Aggregate FII from DB (last 5 days)
    fii_flows = get_fii_dii_flows(days=5)
    fii_net_5d = sum(f.get("fiinet_cr", 0) for f in fii_flows) if fii_flows else 0

    signals = []
    divergence = False

    if fii_net_5d < -5000 and swf_net > 0:
        signals.append(f"DIVERGENCE: FII ₹{fii_net_5d:+,.0f} Cr (5d) but SWFs ₹{swf_net:+,.0f} Cr — smart money buying the dip")
        divergence = True
    elif fii_net_5d > 5000 and swf_net < 0:
        signals.append(f"DIVERGENCE: FII ₹{fii_net_5d:+,.0f} Cr (5d) but SWFs ₹{swf_net:+,.0f} Cr — smart money distributing")
        divergence = True
    elif fii_net_5d > 0 and swf_net > 0:
        signals.append(f"ALIGNMENT: FII ₹{fii_net_5d:+,.0f} Cr (5d) + SWFs ₹{swf_net:+,.0f} Cr — strong consensus buy")
    elif fii_net_5d < 0 and swf_net < 0:
        signals.append(f"ALIGNMENT: FII ₹{fii_net_5d:+,.0f} Cr (5d) + SWFs ₹{swf_net:+,.0f} Cr — broad selling")

    return {
        "ok": True,
        "fii_net_5d": fii_net_5d,
        "swf_buy": swf_buy,
        "swf_sell": swf_sell,
        "swf_net": swf_net,
        "divergence": divergence,
        "signals": signals,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SMART FORMATTER
# ═══════════════════════════════════════════════════════════════════════════════

def _country_flag(country: str) -> str:
    flags = {
        "Japan": "🇯🇵", "UAE": "🇦🇪", "Singapore": "🇸🇬",
        "South Korea": "🇰🇷", "Norway": "🇳🇴", "Canada": "🇨🇦",
        "Saudi Arabia": "🇸🇦", "Kuwait": "🇰🇼", "Qatar": "🇶🇦",
        "US": "🇺🇸", "New Zealand": "🇳🇿", "Netherlands": "🇳🇱",
        "France": "🇫🇷", "Switzerland": "🇨🇭", "India": "🇮🇳",
    }
    return flags.get(country, "🏛️")


def format_smart_tracker(today_signals: List[Dict], patterns: Dict, divergence: Dict) -> str:
    """
    Smart formatter showing:
    - Today's institutional deals with buy/sell direction
    - 30-day pattern analysis (accumulation, distribution, frequency)
    - FII divergence signal
    - Sector concentration
    - New entrants and exits
    """
    lines = ["🏦 *Institutional Intelligence (Smart Tracker)*"]
    lines.append("━" * 30)

    # Today's deals
    if today_signals:
        lines.append("")
        lines.append("📋 *Today's Institutional Deals*")
        for sig in today_signals:
            flag = _country_flag(sig.get("country", ""))
            side_emoji = "🟢" if sig.get("side", "").upper() == "BUY" else "🔴"
            aum_label = f"${sig['aum_bn']:.0f}B" if sig.get("aum_bn") else ""
            lines.append(
                f"{flag} {side_emoji} *{sig['institution_name']}* {sig.get('side', '').upper()} "
                f"{sig.get('symbol', '')} — ₹{sig['value_cr']:.0f} Cr ({aum_label})"
            )

    # Pattern analysis
    if patterns.get("ok"):
        sigs = patterns.get("signals", {})

        # New entrants
        new_e = sigs.get("new_entrants", [])
        if new_e:
            lines.append("")
            lines.append("🆕 *New Entrants (last 30d, not in previous 60d)*")
            for ne in new_e:
                lines.append(f"  {ne['name']}: {ne['deals']} deals, ${ne['aum_bn']:.0f}B AUM")

        # Accelerating
        accel = sigs.get("accelerating", [])
        if accel:
            lines.append("")
            lines.append("📈 *Accelerating Activity (frequency up 2x+)*")
            for a in accel:
                lines.append(f"  {a['name']}: {a['ratio']}x frequency ({a['recent']} deals last 30d)")

        # Decelerating
        decel = sigs.get("decelerating", [])
        if decel:
            lines.append("")
            lines.append("📉 *Decelerating Activity*")
            for d in decel:
                lines.append(f"  {d['name']}: {d['ratio']}x decline")

        # Net accumulators
        accum = sigs.get("net_accumulators", [])
        if accum:
            lines.append("")
            lines.append("💰 *Net Accumulators (30d)*")
            for a in accum:
                lines.append(f"  {a['name']}: +₹{a['net_cr']:.0f} Cr ({a['deals']} deals)")

        # Net distributors
        dist = sigs.get("net_distributors", [])
        if dist:
            lines.append("")
            lines.append("💸 *Net Distributors (30d)*")
            for d in dist:
                lines.append(f"  {d['name']}: ₹{d['net_cr']:.0f} Cr ({d['deals']} deals)")

        # Exits
        exits = sigs.get("exits", [])
        if exits:
            lines.append("")
            lines.append("🚪 *Gone Silent (active in previous 60d, none in last 30d)*")
            for e in exits:
                lines.append(f"  {e['name']}: {e['old_deals']} deals previously")

    # FII divergence
    if divergence.get("ok") and divergence.get("signals"):
        lines.append("")
        lines.append("🔍 *FII vs SWF Signal*")
        for s in divergence["signals"]:
            lines.append(f"  ⚡ {s}")

    # Sector concentration from today's signals
    if today_signals:
        sectors = defaultdict(lambda: {"count": 0, "value_cr": 0})
        for sig in today_signals:
            # Map symbol to sector (simplified — use first known sector)
            sector = _guess_sector(sig.get("symbol", ""))
            sectors[sector]["count"] += 1
            sectors[sector]["value_cr"] += sig.get("value_cr", 0)

        if sectors:
            lines.append("")
            lines.append("📊 *Sector Concentration (today)*")
            total = sum(s["value_cr"] for s in sectors.values())
            for sector, data in sorted(sectors.items(), key=lambda x: -x[1]["value_cr"]):
                pct = (data["value_cr"] / total * 100) if total > 0 else 0
                lines.append(f"  {sector}: {pct:.0f}% (₹{data['value_cr']:.0f} Cr, {data['count']} deals)")

    return "\n".join(lines)


def _guess_sector(symbol: str) -> str:
    """Simple sector guess from symbol. Uses known sector suffixes."""
    s = symbol.upper().replace(".NS", "").replace(".BO", "")
    banking = {"HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "INDUSINDBK", "FEDERALBNK", "PNB", "BANKBARODA", "IDFCFIRSTB"}
    it = {"TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTIM", "MPHASIS", "PERSISTENT", "COFORGE"}
    pharma = {"SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "AUROPHARMA", "LUPIN", "ALKEM"}
    auto = {"MARUTI", "M&M", "TATAMOTORS", "BAJAJ-AUTO", "HEROMOTOCO", "EICHERMOT", "TVSMOTORS"}
    fmcg = {"HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR", "MARICO", "GODREJCP"}
    energy = {"RELIANCE", "ONGC", "NTPC", "POWERGRID", "ADANIENT", "ADANIGREEN", "TATAPOWER"}
    metal = {"TATASTEEL", "HINDALCO", "JSWSTEEL", "VEDL", "NMDC", "COALINDIA"}
    realty = {"DLF", "GODREJPROP", "OBEROIRLTY", "PRESTIGE", "BRIGADE", "SUNTV"}

    if s in banking:
        return "Banking"
    elif s in it:
        return "IT"
    elif s in pharma:
        return "Pharma"
    elif s in auto:
        return "Auto"
    elif s in fmcg:
        return "FMCG"
    elif s in energy:
        return "Energy"
    elif s in metal:
        return "Metal"
    elif s in realty:
        return "Realty"
    else:
        return "Other"


# ═══════════════════════════════════════════════════════════════════════════════
# CONTEXT ENGINE SIGNAL — feeds into Bull/Bear score
# ═══════════════════════════════════════════════════════════════════════════════

def compute_institutional_signal(today_signals: List[Dict], patterns: Dict, divergence: Dict) -> Dict:
    """
    Compute a bull/bear signal from institutional activity.
    Feeds into the context engine's Bull/Bear score.
    """
    score = 0
    signals = []

    # Today's net flow
    if today_signals:
        buy_count = sum(1 for s in today_signals if s.get("side", "").upper() == "BUY")
        sell_count = sum(1 for s in today_signals if s.get("side", "").upper() == "SELL")
        net_buy = sum(s["value_cr"] for s in today_signals if s.get("side", "").upper() == "BUY")
        net_sell = sum(s["value_cr"] for s in today_signals if s.get("side", "").upper() == "SELL")
        net = net_buy - net_sell

        if net > 500:
            score += 3
            signals.append(f"Institutional net buy: +₹{net:.0f} Cr ({buy_count}B/{sell_count}S)")
        elif net < -500:
            score -= 3
            signals.append(f"Institutional net sell: ₹{net:.0f} Cr ({buy_count}B/{sell_count}S)")

    # Pattern signals
    if patterns.get("ok"):
        sigs = patterns.get("signals", {})

        # New entrants = bullish (structural allocation increase)
        new_e = sigs.get("new_entrants", [])
        if new_e:
            score += 3
            names = ", ".join(ne["name"] for ne in new_e[:3])
            signals.append(f"New institutional entrants: {names}")

        # Accelerating = bullish
        accel = sigs.get("accelerating", [])
        if accel:
            score += 2
            signals.append(f"Institutional activity accelerating: {accel[0]['name']} {accel[0]['ratio']}x")

        # Exits = bearish
        exits = sigs.get("exits", [])
        if exits:
            score -= 2
            signals.append(f"Institutional exit: {exits[0]['name']} gone silent")

        # Net distributors = bearish
        dist = sigs.get("net_distributors", [])
        if dist:
            score -= 2
            signals.append(f"Institutional distribution: {dist[0]['name']} -₹{abs(dist[0]['net_cr']):.0f} Cr")

    # FII divergence
    if divergence.get("ok") and divergence.get("divergence"):
        # Divergence is already a signal — doesn't add to score, but is context
        signals.extend(divergence.get("signals", []))

    # Normalize: -10 to +10 range
    score = max(-10, min(10, score))

    if score >= 5:
        regime = "STRONG ACCUMULATION"
    elif score >= 2:
        regime = "ACCUMULATION"
    elif score <= -5:
        regime = "STRONG DISTRIBUTION"
    elif score <= -2:
        regime = "DISTRIBUTION"
    else:
        regime = "NEUTRAL"

    return {
        "ok": True,
        "score": score,
        "regime": regime,
        "signals": signals,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CONTEXT ENGINE INTEGRATION — lightweight signal from stored data
# ═══════════════════════════════════════════════════════════════════════════════

def get_institutional_context(days: int = 30) -> Dict:
    """
    Lightweight institutional signal for context engine.
    Queries stored fii_institution_tracker data, computes a signal.
    Called from run_contextualization() — no NSE API calls.
    """
    patterns = analyze_institutional_patterns(days=90)
    if not patterns.get("ok"):
        return {"ok": False}

    sigs = patterns.get("signals", {})
    score = 0
    signals = []

    # New entrants = bullish
    new_e = sigs.get("new_entrants", [])
    if new_e:
        score += 3
        names = ", ".join(ne["name"] for ne in new_e[:3])
        signals.append(f"New entrants: {names}")

    # Accelerating = bullish
    accel = sigs.get("accelerating", [])
    if accel:
        score += 2
        signals.append(f"Accelerating: {accel[0]['name']} {accel[0]['ratio']}x")

    # Exits = bearish
    exits = sigs.get("exits", [])
    if exits:
        score -= 2
        signals.append(f"Exit signal: {exits[0]['name']}")

    # Net distributors = bearish
    dist = sigs.get("net_distributors", [])
    if dist:
        score -= 2
        signals.append(f"Distribution: {dist[0]['name']}")

    # Net accumulators = bullish
    accum = sigs.get("net_accumulators", [])
    if accum:
        score += 2
        signals.append(f"Accumulation: {accum[0]['name']} +₹{accum[0]['net_cr']:.0f} Cr")

    score = max(-10, min(10, score))

    if score >= 5:
        regime = "STRONG ACCUMULATION"
    elif score >= 2:
        regime = "ACCUMULATION"
    elif score <= -5:
        regime = "STRONG DISTRIBUTION"
    elif score <= -2:
        regime = "DISTRIBUTION"
    else:
        regime = "NEUTRAL"

    return {
        "ok": True,
        "score": score,
        "regime": regime,
        "signals": signals,
        "new_entrants": len(new_e),
        "accelerating": len(accel),
        "exits": len(exits),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def run_fii_tracker(days: int = 7) -> str:
    """
    Smart institutional tracker. Fetches last 7 days of NSE deals,
    matches against full watchlist, analyzes patterns, computes FII divergence.
    Returns formatted string for block injection.
    """
    print(f"🏦 Smart institutional tracker (last {days} days)...")

    # Fetch historical deals
    deals = fetch_nse_deals(days=days)
    print(f"   → {len(deals)} deals fetched")

    # Scan for institutions
    today_signals = scan_deals_for_institutions(deals)
    print(f"   → {len(today_signals)} institutional deals matched")

    # Deduplicate (same institution + symbol + date)
    seen = set()
    unique_signals = []
    for sig in today_signals:
        key = (sig["institution_name"], sig.get("symbol", ""), sig.get("date", ""))
        if key not in seen:
            seen.add(key)
            unique_signals.append(sig)

    # Save to DB
    from src.db import save_fii_institution
    today = datetime.now().strftime("%Y-%m-%d")
    for sig in unique_signals:
        save_fii_institution(
            today, sig["institution_name"], sig["institution_type"],
            sig["country"], f"{sig.get('deal_type', '')}_{sig.get('side', '').lower()}",
            sig.get("value_cr"), f"{sig.get('side', '')} {sig.get('symbol', '')} ₹{sig.get('value_cr', 0):.0f}Cr",
            "NSE"
        )

    # Historical pattern analysis
    patterns = analyze_institutional_patterns(days=90)

    # FII divergence
    divergence = compute_fii_swf_divergence(unique_signals)

    # Context engine signal
    inst_signal = compute_institutional_signal(unique_signals, patterns, divergence)
    if inst_signal.get("signals"):
        for s in inst_signal["signals"]:
            print(f"   → {s}")

    # Format output
    if unique_signals or patterns.get("ok"):
        output = format_smart_tracker(unique_signals, patterns, divergence)
        return output
    else:
        print("   → No institutional activity detected")
        return ""
