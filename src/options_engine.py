"""
Options Engine — NSE Options Chain Analysis
Single fetch per job execution. Stores snapshots to Supabase for shift detection.

Includes: Max Pain, PCR, OI Zones, GEX, Skew, Advanced OI, Rollover

Morning job: fetch → compute → store snapshot
Evening job: fetch → diff vs morning → compute shifts
"""
import requests
import os
import math
from datetime import datetime
from typing import Dict, List, Optional

# Supabase config
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.nseindia.com/",
    "Accept": "application/json",
}

# Index symbols use different endpoint
INDEX_SYMBOLS = {"NIFTY", "BANKNIFTY", "NIFTY BANK", "FINNIFTY", "MIDCPNIFTY"}


# ═══════════════════════════════════════════════════════════════════════════════
# FETCH: NSE Options Chain
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_nse_options_chain(symbol: str = "NIFTY") -> List[Dict]:
    """
    Fetch NSE options chain for given symbol.
    Selects expiry: nearest expiry, but if <3 days to expiry → use next expiry.
    Returns list of strike-wise OI data including IV.

    Uses shared NSE session from nse_session.py for cookie management.
    Circuit breaker: trips after 3 failures, skips for 5 minutes.
    """
    from datetime import datetime, timedelta
    from src.nse_session import nse_get

    # Circuit breaker check
    try:
        from src.circuit_breaker import CircuitBreaker
        _options_breaker = CircuitBreaker(
            name="nse_options", failure_threshold=3, recovery_timeout=300,
        )
        if _options_breaker.state == "OPEN":
            return []
    except Exception:
        _options_breaker = None

    # Use correct endpoint based on symbol type
    # v3 API requires expiry param; prefetch expiry dates from contract-info
    try:
        contract = nse_get(
            f"https://www.nseindia.com/api/option-chain-contract-info?symbol={symbol}",
            timeout=15, retries=1,
        )
        if contract.status_code != 200:
            print(f"⚠️  Contract info API returned {contract.status_code}")
            return []
        contract_data = contract.json()
        expiry_dates = contract_data.get("expiryDates", [])
        if not expiry_dates:
            print("⚠️  No expiry dates from contract-info")
            return []
    except Exception as e:
        print(f"⚠️  Contract info fetch error: {e}")
        return []

    # Select appropriate expiry
    selected_expiry = None
    today = datetime.now().date()

    for exp in expiry_dates:
        try:
            exp_date = datetime.strptime(exp, "%d-%b-%Y").date()
            days_to_expiry = (exp_date - today).days
            if days_to_expiry < 0:
                continue
            if selected_expiry is None or days_to_expiry < selected_expiry[1]:
                if days_to_expiry >= 3 or selected_expiry is None:
                    selected_expiry = (exp, days_to_expiry)
        except:
            continue

    if not selected_expiry:
        selected_expiry = (expiry_dates[0], 0) if expiry_dates else ("", 0)

    expiry_str = selected_expiry[0]
    days_to_exp = selected_expiry[1]
    print(f"   📅 Using expiry: {expiry_str} ({days_to_exp}d)")

    _CACHE_FILE = "/tmp/nse_options_chain_cache.json"

    # Now fetch actual chain data with the selected expiry
    if symbol.upper() in INDEX_SYMBOLS:
        chain_type = "Indices"
    else:
        chain_type = "Equity"
    url = f"https://www.nseindia.com/api/option-chain-v3?symbol={symbol}&type={chain_type}&expiry={expiry_str}"

    results = []
    try:
        resp = nse_get(url, timeout=20, retries=1)
        if resp.status_code == 200:
            data = resp.json()
            chain_data = data.get("records", {}).get("data", [])
            if chain_data:
                results = _extract_chain_rows(chain_data, expiry_str, days_to_exp)
                if results:
                    underlying = data["records"].get("underlyingValue", 0)
                    results[0]["_underlying"] = underlying
                    results[0]["_days_to_expiry"] = days_to_exp
                    results.sort(key=lambda x: x["strike"])
                    _write_chain_cache(_CACHE_FILE, expiry_str, results)
                    if _options_breaker:
                        _options_breaker.record_success()
                    return results
        else:
            print(f"⚠️  Options v3 API returned {resp.status_code}")
    except Exception as e:
        print(f"⚠️  Options v3 fetch error: {e}")

    # Fallback: file cache (populated by earlier successful fetch)
    cached = _read_chain_cache(_CACHE_FILE)
    if cached:
        print(f"   📦 Using cached options data (expiry {cached['expiry']})")
        if _options_breaker:
            _options_breaker.record_success()
        return cached["data"]

    print("   ⚠️ No options data from any source")
    if _options_breaker:
        _options_breaker.record_failure()
    return []


def _extract_chain_rows(chain_data: List[Dict], expiry_str: str, days_to_exp: int) -> List[Dict]:
    """Extract strike-wise OI/IV data from raw chain records for a given expiry."""
    results = []
    for rec in chain_data:
        if rec.get("expiryDate") != expiry_str:
            continue
        ce = rec.get("CE", {})
        pe = rec.get("PE", {})
        results.append({
            "strike": rec.get("strikePrice", 0),
            "call_oi": ce.get("openInterest", 0) or 0,
            "call_change_oi": ce.get("changeinOpenInterest", 0) or 0,
            "call_volume": ce.get("totalTradedVolume", 0) or 0,
            "call_iv": ce.get("impliedVolatility", 0) or 0,
            "call_last": ce.get("lastPrice", 0) or 0,
            "put_oi": pe.get("openInterest", 0) or 0,
            "put_change_oi": pe.get("changeinOpenInterest", 0) or 0,
            "put_volume": pe.get("totalTradedVolume", 0) or 0,
            "put_iv": pe.get("impliedVolatility", 0) or 0,
            "put_last": pe.get("lastPrice", 0) or 0,
            "expiry": expiry_str,
            "days_to_expiry": days_to_exp,
        })
    return results


def _write_chain_cache(path: str, expiry: str, data: List[Dict]) -> None:
    """Persist options chain to local file for after-hours fallback."""
    try:
        import json
        with open(path, "w") as f:
            json.dump({"expiry": expiry, "data": data}, f)
    except Exception:
        pass


def _read_chain_cache(path: str) -> Optional[Dict]:
    """Read cached options chain from local file."""
    import os
    if not os.path.exists(path):
        return None
    try:
        import json
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# COMPUTE: Max Pain, PCR, OI Zones
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# BLACK-SCHOLES HELPERS — for GEX and Skew computation
# ═══════════════════════════════════════════════════════════════════════════════

def _norm_cdf(x: float) -> float:
    """Standard normal CDF using math.erfc."""
    return 0.5 * (1 + math.erfc(x / math.sqrt(2)))

def _norm_pdf(x: float) -> float:
    """Standard normal PDF."""
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)

def _bs_gamma(spot: float, strike: float, iv_pct: float, days: int, r: float = 0.07) -> float:
    """Black-Scholes gamma for a European option."""
    if spot <= 0 or strike <= 0 or iv_pct <= 0 or days <= 0:
        return 0
    sigma = iv_pct / 100
    T = days / 365
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    return _norm_pdf(d1) / (spot * sigma * math.sqrt(T))

def _bs_delta(spot: float, strike: float, iv_pct: float, days: int, r: float = 0.07, is_call: bool = True) -> float:
    """Black-Scholes delta."""
    if spot <= 0 or strike <= 0 or iv_pct <= 0 or days <= 0:
        return 0
    sigma = iv_pct / 100
    T = days / 365
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    if is_call:
        return _norm_cdf(d1)
    return _norm_cdf(d1) - 1


# ═══════════════════════════════════════════════════════════════════════════════
# COMPUTE: Gamma Exposure (GEX)
# ═══════════════════════════════════════════════════════════════════════════════

def compute_gex(options_data: List[Dict], spot_price: float = None, lot_size: int = 25) -> Dict:
    """
    Compute dealer Gamma Exposure (GEX) from options chain.
    Convention: dealers are short options (retail buys).
    - Call OI short by dealers → NEGATIVE gamma contribution
    - Put OI short by dealers → POSITIVE gamma contribution

    Returns: net_gex (per 1% move), gex_flip_level, regime
    """
    if not options_data or not spot_price:
        return {"ok": False}

    days = options_data[0].get("days_to_expiry", 7) or 7
    net_gex = 0
    gex_by_strike = []

    for o in options_data:
        strike = o["strike"]
        call_oi = o.get("call_oi", 0)
        put_oi = o.get("put_oi", 0)
        call_iv = o.get("call_iv", 0) or 15  # Default 15% if missing
        put_iv = o.get("put_iv", 0) or 15

        # Gamma for calls and puts (same gamma for both in BS)
        call_gamma = _bs_gamma(spot_price, strike, call_iv, days)
        put_gamma = _bs_gamma(spot_price, strike, put_iv, days)

        # GEX per strike = gamma * OI * lot_size * spot * 0.01 (per 1% move)
        # Dealers short calls (negative gamma), short puts (positive gamma)
        call_gex = -1 * call_gamma * call_oi * lot_size * spot_price * 0.01
        put_gex = +1 * put_gamma * put_oi * lot_size * spot_price * 0.01

        strike_gex = call_gex + put_gex
        net_gex += strike_gex

        gex_by_strike.append({
            "strike": strike,
            "call_gex": round(call_gex / 1e7, 2),  # In crores
            "put_gex": round(put_gex / 1e7, 2),
            "net_gex": round(strike_gex / 1e7, 2),
        })

    # Find GEX flip level (where cumulative GEX crosses zero)
    cumulative = 0
    flip_level = spot_price
    for g in sorted(gex_by_strike, key=lambda x: x["strike"]):
        cumulative += g["net_gex"]
        if cumulative >= 0 and cumulative - g["net_gex"] < 0:
            flip_level = g["strike"]
            break

    net_gex_cr = round(net_gex / 1e7, 2)

    if net_gex_cr > 50:
        regime = "LONG GAMMA (stable, mean-reverting)"
    elif net_gex_cr < -50:
        regime = "SHORT GAMMA (unstable, trending)"
    else:
        regime = "NEUTRAL GAMMA"

    # Full strike-level data (for magnetic level computation)
    gex_by_strike_sorted = sorted(gex_by_strike, key=lambda x: x["strike"])

    return {
        "ok": True,
        "net_gex_cr": net_gex_cr,
        "regime": regime,
        "flip_level": flip_level,
        "top_strikes": sorted(gex_by_strike, key=lambda x: abs(x["net_gex"]), reverse=True)[:5],
        "gex_by_strike": gex_by_strike_sorted,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# COMPUTE: 25-Delta Risk Reversal (Volatility Skew)
# ═══════════════════════════════════════════════════════════════════════════════

def compute_skew(options_data: List[Dict], spot_price: float = None) -> Dict:
    """
    Compute 25-delta risk reversal and butterfly from options chain.
    25RR = IV(25d call) - IV(25d put)
    25BF = [IV(25d call) + IV(25d put)] / 2 - IV(ATM)
    """
    if not options_data or not spot_price:
        return {"ok": False}

    days = options_data[0].get("days_to_expiry", 7) or 7

    # Compute delta for each strike and find 25-delta options
    call_deltas = []
    put_deltas = []
    atm_iv = None
    closest_to_spot = None

    for o in options_data:
        strike = o["strike"]
        call_iv = o.get("call_iv", 0)
        put_iv = o.get("put_iv", 0)

        if call_iv > 0:
            cd = _bs_delta(spot_price, strike, call_iv, days, is_call=True)
            call_deltas.append({"strike": strike, "delta": cd, "iv": call_iv})

        if put_iv > 0:
            pd = _bs_delta(spot_price, strike, put_iv, days, is_call=False)
            put_deltas.append({"strike": strike, "delta": pd, "iv": put_iv})

        # Track ATM IV
        if closest_to_spot is None or abs(strike - spot_price) < abs(closest_to_spot - spot_price):
            closest_to_spot = strike
            atm_iv = (call_iv + put_iv) / 2 if call_iv > 0 and put_iv > 0 else (call_iv or put_iv)

    # Find 25-delta call (delta ~ +0.25) and 25-delta put (delta ~ -0.25)
    target_25d_call = min(call_deltas, key=lambda x: abs(x["delta"] - 0.25)) if call_deltas else None
    target_25d_put = min(put_deltas, key=lambda x: abs(x["delta"] - (-0.25))) if put_deltas else None

    if not target_25d_call or not target_25d_put or not atm_iv:
        return {"ok": False, "message": "Insufficient IV data for skew"}

    rr_25 = target_25d_call["iv"] - target_25d_put["iv"]
    bf_25 = (target_25d_call["iv"] + target_25d_put["iv"]) / 2 - atm_iv

    # Interpretation
    if rr_25 > 2:
        rr_label = "CALL SKEW (bullish breakout priced)"
    elif rr_25 < -2:
        rr_label = "PUT SKEW (crash protection priced)"
    elif rr_25 < -5:
        rr_label = "EXTREME PUT SKEW (capitulation or bottom signal)"
    else:
        rr_label = "BALANCED SKEW"

    if bf_25 > 3:
        bf_label = "HIGH convexity (event premium)"
    elif bf_25 < 1:
        bf_label = "FLAT smile (complacency)"
    else:
        bf_label = "NORMAL"

    return {
        "ok": True,
        "risk_reversal_25d": round(rr_25, 2),
        "butterfly_25d": round(bf_25, 2),
        "rr_label": rr_label,
        "bf_label": bf_label,
        "atm_iv": round(atm_iv, 1),
        "call_25d_strike": target_25d_call["strike"],
        "put_25d_strike": target_25d_put["strike"],
        "call_25d_iv": round(target_25d_call["iv"], 1),
        "put_25d_iv": round(target_25d_put["iv"], 1),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# COMPUTE: Advanced OI Signals
# ═══════════════════════════════════════════════════════════════════════════════

def compute_advanced_oi(options_data: List[Dict], spot_price: float = None) -> Dict:
    """
    Compute 6 advanced OI-based signals beyond PCR and max pain.
    """
    if not options_data or not spot_price:
        return {"ok": False}

    # 1. OI Velocity — strikes with >10% OI change rate
    oi_velocity = []
    for o in options_data:
        for side in ["call", "put"]:
            oi = o.get(f"{side}_oi", 0)
            change = o.get(f"{side}_change_oi", 0)
            if oi > 10000 and abs(change) > 0:
                velocity = abs(change) / oi * 100
                if velocity > 10:
                    oi_velocity.append({
                        "strike": o["strike"],
                        "side": side.upper(),
                        "velocity": round(velocity, 1),
                        "change": change,
                    })

    # 2. OI Concentration — top 3 strikes as % of total
    total_oi = sum(o["call_oi"] + o["put_oi"] for o in options_data)
    strike_totals = [(o["strike"], o["call_oi"] + o["put_oi"]) for o in options_data]
    top3 = sorted(strike_totals, key=lambda x: x[1], reverse=True)[:3]
    top3_oi = sum(t[1] for t in top3)
    concentration = round(top3_oi / total_oi * 100, 1) if total_oi > 0 else 0

    # 3. OI-Price Matrix — classify build-up pattern
    near_money = [o for o in options_data if abs(o["strike"] - spot_price) / spot_price < 0.03]
    if near_money:
        avg_call_change = sum(o["call_change_oi"] for o in near_money) / len(near_money)
        avg_put_change = sum(o["put_change_oi"] for o in near_money) / len(near_money)
    else:
        avg_call_change = avg_put_change = 0

    # 4. OI Weighted Average Strike (OWAS)
    total_weighted = sum(o["strike"] * (o["call_oi"] + o["put_oi"]) for o in options_data)
    owas = round(total_weighted / total_oi, 0) if total_oi > 0 else spot_price
    owas_bias = "BULLISH" if owas > spot_price * 1.01 else "BEARISH" if owas < spot_price * 0.99 else "NEUTRAL"

    # 5. OI Imbalance at top strikes
    top_imbalances = []
    for o in options_data:
        total = o["call_oi"] + o["put_oi"]
        if total > 50000:  # Only significant strikes
            imbalance = (o["call_oi"] - o["put_oi"]) / total
            if abs(imbalance) > 0.4:
                top_imbalances.append({
                    "strike": o["strike"],
                    "imbalance": round(imbalance, 2),
                    "type": "RESISTANCE" if imbalance > 0.4 else "SUPPORT",
                })
    top_imbalances.sort(key=lambda x: abs(x["imbalance"]), reverse=True)

    # 6. Unusual Activity — volume spikes with OI change
    unusual = []
    for o in options_data:
        for side in ["call", "put"]:
            vol = o.get(f"{side}_volume", 0)
            oi = o.get(f"{side}_oi", 0)
            change = o.get(f"{side}_change_oi", 0)
            if oi > 50000 and vol > oi * 0.3 and abs(change) > 20000:
                unusual.append({
                    "strike": o["strike"],
                    "side": side.upper(),
                    "volume": vol,
                    "oi_change": change,
                    "signal": "INSTITUTIONAL" if abs(change) > 50000 else "ACTIVE",
                })

    return {
        "ok": True,
        "oi_velocity": sorted(oi_velocity, key=lambda x: x["velocity"], reverse=True)[:5],
        "concentration": concentration,
        "concentration_strikes": [t[0] for t in top3],
        "owas": int(owas),
        "owas_bias": owas_bias,
        "owas_distance_pct": round((owas - spot_price) / spot_price * 100, 2),
        "oi_imbalances": top_imbalances[:5],
        "unusual_activity": unusual[:5],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# COMPUTE: Max Pain, PCR, OI Zones
# ═══════════════════════════════════════════════════════════════════════════════

def compute_max_pain(options_data: List[Dict], spot_price: float) -> Dict:
    """
    Calculate Max Pain — strike where most total value expires.
    Max Pain = strike where sum(OTM call value + OTM put value) is minimum.
    """
    if not options_data:
        return {"max_pain": 0, "max_pain_distance": 0}

    # Find strike with highest total OI as proxy for max pain
    max_oi_strike = 0
    max_total_oi = 0
    for o in options_data:
        total = o["call_oi"] + o["put_oi"]
        if total > max_total_oi:
            max_total_oi = total
            max_oi_strike = o["strike"]

    # Distance from spot
    distance_pct = ((max_oi_strike - spot_price) / spot_price * 100) if spot_price > 0 else 0

    return {
        "max_pain": max_oi_strike,
        "max_pain_distance": round(distance_pct, 2),
    }


def compute_pcr(options_data: List[Dict], spot_price: float = None) -> Dict:
    """
    Compute Put-Call Ratio and interpret.
    PCR computed for near-money strikes only (±10% of spot).
    PCR < 0.7: PUT side building (support, bullish)
    PCR > 1.3: CALL side building (resistance, bearish)
    PCR 0.7-1.3: Neutral
    """
    if not options_data:
        return {"pcr": 0, "interpretation": "No data"}

    # Filter to near-money strikes only (±10% of spot)
    if spot_price:
        min_spot = spot_price * 0.90
        max_spot = spot_price * 1.10
        near_money = [o for o in options_data if min_spot <= o.get("strike", 0) <= max_spot]
        if near_money:
            options_data = near_money
            print(f"   📊 PCR computed on {len(near_money)} near-money strikes (±10%)")

    total_call_oi = sum(o["call_oi"] for o in options_data)
    total_put_oi = sum(o["put_oi"] for o in options_data)

    pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 0

    if pcr < 0.7:
        interpretation = "PUT building (support)"
        signal = "BULLISH"
    elif pcr > 1.3:
        interpretation = "CALL building (resistance)"
        signal = "BEARISH"
    else:
        interpretation = "Balanced"
        signal = "NEUTRAL"

    return {
        "pcr": round(pcr, 2),
        "interpretation": interpretation,
        "signal": signal,
    }


def compute_oi_zones(options_data: List[Dict], spot_price: float = None) -> Dict:
    """
    Identify support and resistance zones based on OI buildup.
    Only within ±5% of spot for relevance.
    """
    if not options_data:
        return {"support_zone": [], "resistance_zone": []}

    # Filter to near-money (±5% of spot) for relevant zones
    if spot_price:
        min_spot = spot_price * 0.95
        max_spot = spot_price * 1.05
        options_data = [o for o in options_data if min_spot <= o.get("strike", 0) <= max_spot]

    # Sort by OI for PUTs (support) and CALLs (resistance)
    puts = sorted(options_data, key=lambda x: x["put_oi"], reverse=True)[:5]
    calls = sorted(options_data, key=lambda x: x["call_oi"], reverse=True)[:5]

    support_zone = [int(p["strike"]) for p in puts if p["put_oi"] > 100000]
    resistance_zone = [int(c["strike"]) for c in calls if c["call_oi"] > 100000]

    # Also compute PUT/CALL build-up (change in OI)
    put_buildup = [o for o in options_data if o.get("put_change_oi", 0) > 50000]
    call_buildup = [o for o in options_data if o.get("call_change_oi", 0) > 50000]

    return {
        "support_zone": support_zone[:3],
        "resistance_zone": resistance_zone[:3],
        "put_buildup_strikes": [int(o["strike"]) for o in put_buildup[:3]],
        "call_buildup_strikes": [int(o["strike"]) for o in call_buildup[:3]],
    }


def analyze_options_chain(symbol: str = "NIFTY", spot_price: float = None) -> Dict:
    """
    Full options analysis — fetch + compute all metrics including GEX, skew, advanced OI.
    """
    options_data = fetch_nse_options_chain(symbol)
    if not options_data:
        return {"ok": False, "message": "No options data"}

    # Use underlying value from API if available, else estimate from ATM
    underlying = options_data[0].get("_underlying", 0)
    if not spot_price:
        spot_price = underlying if underlying else options_data[len(options_data)//2]["strike"]

    max_pain = compute_max_pain(options_data, spot_price)
    pcr = compute_pcr(options_data, spot_price)
    zones = compute_oi_zones(options_data, spot_price)

    # New metrics — GEX, Skew, Advanced OI
    gex = compute_gex(options_data, spot_price)
    skew = compute_skew(options_data, spot_price)
    advanced = compute_advanced_oi(options_data, spot_price)

    return {
        "ok": True,
        "symbol": symbol,
        "spot_price": spot_price,
        "max_pain": max_pain,
        "pcr": pcr,
        "zones": zones,
        "gex": gex,
        "skew": skew,
        "advanced_oi": advanced,
        "timestamp": datetime.now().isoformat(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# STORE: Snapshot to Supabase
# ═══════════════════════════════════════════════════════════════════════════════

def store_options_snapshot(symbol: str, run: str, analysis: Dict) -> bool:
    """
    Store morning/evening snapshot to Supabase for shift detection.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("⚠️  Supabase not configured — skipping snapshot")
        return False

    try:
        from supabase import create_client
        client = create_client(SUPABASE_URL, SUPABASE_KEY)

        data = {
            "symbol": symbol,
            "run": run,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "spot_price": analysis.get("spot_price"),
            "max_pain": analysis.get("max_pain", {}).get("max_pain"),
            "pcr": analysis.get("pcr", {}).get("pcr"),
            "pcr_signal": analysis.get("pcr", {}).get("signal"),
            "gex": analysis.get("gex", {}).get("net_gex_cr"),
            "skew_25d": analysis.get("skew", {}).get("risk_reversal_25d"),
            "support_zone": analysis.get("zones", {}).get("support_zone", []),
            "resistance_zone": analysis.get("zones", {}).get("resistance_zone", []),
        }

        client.table("options_snapshots").insert(data).execute()
        print(f"✅ Options snapshot stored: {run}")
        return True

    except Exception as e:
        print(f"⚠️  Store snapshot error: {e}")
        return False


def get_latest_snapshot(symbol: str, run: str = "morning") -> Optional[Dict]:
    """
    Retrieve last snapshot for comparison (evening job compares to morning).
    Default run is 'morning' for convenience at EOD.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None

    try:
        from supabase import create_client
        client = create_client(SUPABASE_URL, SUPABASE_KEY)

        result = (
            client.table("options_snapshots")
            .select("*")
            .eq("symbol", symbol)
            .eq("run", run)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if result.data:
            return result.data[0]
        else:
            print(f"⚠️  Options snapshot: no rows for {symbol}/{run}")
    except Exception as e:
        print(f"⚠️  Get snapshot error: {e}")

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# EVENING ONLY: Compute OI shifts vs morning snapshot
# ═══════════════════════════════════════════════════════════════════════════════

def get_snapshot_history(symbol: str, days: int = 5) -> List[Dict]:
    """
    Get recent options snapshots for rolling average computation.
    Returns list of dicts sorted by date ascending, oldest first.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []

    try:
        from supabase import create_client
        client = create_client(SUPABASE_URL, SUPABASE_KEY)

        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days + 2)).strftime("%Y-%m-%d")

        result = (
            client.table("options_snapshots")
            .select("date, pcr, skew_25d, run")
            .eq("symbol", symbol)
            .gte("date", cutoff)
            .order("date", desc=False)
            .execute()
        )
        return result.data if result.data else []
    except Exception as e:
        print(f"⚠️  Get snapshot history error: {e}")
        return []


def detect_pre_event_positioning(
    symbol: str = "NIFTY",
    event_label: str = "",
    lookback_days: int = 5,
    run: str = "morning",
    existing_snapshot: Optional[Dict] = None,
) -> Dict:
    """
    Detect aggressive hedging before high-impact events.

    Compares current options readings (PCR, Skew) to their
    rolling average to identify pre-event positioning.

    Signals (Analyst 1 correction):
    - PCR spikes > +0.15 in 3 days → Aggressive Put Hedging (put OI ↑)
    - PCR drops > -0.15 in 3 days → Call Speculation / Put Unwinding
    - Skew spikes > +15 points from 5D average → Tail Risk Pricing

    Args:
        existing_snapshot: Optional pre-fetched snapshot (e.g., stale Supabase row)
                          used when live NSE API is unavailable at 08:00.
    """
    from statistics import mean

    history = get_snapshot_history(symbol, days=lookback_days)
    if not history:
        return {"ok": False, "message": "No historical snapshot data"}

    # Get current snapshot: use caller-provided stale data first, then live DB, then history fallback
    current = existing_snapshot or get_latest_snapshot(symbol, run)
    if not current:
        current = history[-1] if history else None
    if not current:
        return {"ok": False, "message": "No current snapshot"}

    current_pcr = current.get("pcr")
    current_skew = current.get("skew_25d")

    # Compute rolling averages from history (exclude current)
    hist_values = history[:-1] if history and history[-1].get("date") == current.get("date") else history

    pcr_values = [h["pcr"] for h in hist_values if h.get("pcr") is not None]
    skew_values = [h["skew_25d"] for h in hist_values if h.get("skew_25d") is not None]

    # PCR change in last 3 days (positive = spike = put OI increasing)
    pcr_3d_ago = pcr_values[-3] if len(pcr_values) >= 3 else None
    pcr_change = (current_pcr - pcr_3d_ago) if (pcr_3d_ago is not None and current_pcr is not None) else None

    # Skew vs 5D average
    skew_5d_avg = mean(skew_values) if len(skew_values) >= 3 else None
    skew_spike = (current_skew - skew_5d_avg) if (current_skew is not None and skew_5d_avg is not None) else None

    signals = []

    # CORRECTED: PCR spikes > +0.15 → Aggressive Put Hedging (Put OI↑)
    # PCR drops > -0.15 → Call Speculation / Put Unwinding
    put_hedging = False
    call_speculation = False
    if pcr_change is not None:
        if pcr_change > 0.15:
            put_hedging = True
            signals.append(
                f"Aggressive put hedging: PCR {pcr_3d_ago:.2f} → {current_pcr:.2f} (Δ+{pcr_change:.2f})"
            )
        elif pcr_change < -0.15:
            call_speculation = True
            signals.append(
                f"Call speculation / put unwinding: PCR {pcr_3d_ago:.2f} → {current_pcr:.2f} (Δ{pcr_change:.2f})"
            )

    # Tail Risk Pricing: Skew spike > +15 from 5D avg
    tail_risk = False
    if skew_spike is not None and skew_spike > 15:
        tail_risk = True
        signals.append(
            f"Tail risk pricing: Skew {skew_5d_avg:.1f} → {current_skew:.1f} (Δ+{skew_spike:.1f} from 5D avg)"
        )

    # Detailed breakdown
    details = []
    if current_pcr is not None:
        details.append(f"Current PCR: {current_pcr:.2f}")
    if pcr_3d_ago is not None and current_pcr is not None:
        details.append(f"3D PCR change: {pcr_change:+.2f}")
    if current_skew is not None:
        details.append(f"Current 25D Skew: {current_skew:+.1f}")
    if skew_5d_avg is not None and current_skew is not None:
        details.append(f"Skew vs 5D avg: {skew_spike:+.1f}")

    # Overall assessment
    active_signals = len(signals)
    if active_signals >= 2:
        assessment = f"Elevated pre-{event_label or 'event'} hedging detected"
    elif active_signals >= 1:
        assessment = f"Moderate pre-{event_label or 'event'} positioning detected"
    else:
        assessment = f"No significant pre-{event_label or 'event'} positioning"

    return {
        "ok": True,
        "event_label": event_label,
        "assessment": assessment,
        "signals": signals,
        "put_hedging": put_hedging,
        "call_speculation": call_speculation,
        "tail_risk": tail_risk,
        "current_pcr": round(current_pcr, 2) if current_pcr is not None else None,
        "current_skew": round(current_skew, 1) if current_skew is not None else None,
        "pcr_3d_change": round(pcr_change, 2) if pcr_change is not None else None,
        "skew_vs_5d_avg": round(skew_spike, 1) if skew_spike is not None else None,
        "sample_size": min(len(pcr_values), len(skew_values)),
        "details": " | ".join(details),
    }


def compute_oi_shifts(evening_data: List[Dict], symbol: str = "NIFTY") -> Dict:
    """
    Compare evening options data vs morning snapshot from Supabase.
    Returns shift signals for evening report.
    
    Shift signals:
    - CALL OI rising at resistance → "Shorts building at {strike}"
    - CALL OI falling at resistance → "Shorts covering, breakout watch"  
    - PUT OI rising at support → "Hedges building at {strike}"
    - PUT OI falling at support → "Hedges unwinding, breakdown risk"
    """
    # Get morning snapshot
    morning = get_latest_snapshot(symbol, "morning")
    
    if not morning:
        return {
            "ok": False,
            "message": "No morning snapshot found - skipping shift detection",
            "shifts": []
        }
    
    # We need to re-fetch morning data or store it in snapshot
    # For now, we'll compute shift signals from current evening data
    # A more complete solution would store strike-level OI in snapshot
    
    # Compute shift from evening data perspective
    # Look for big OI changes (>50k change threshold)
    call_shifts = []
    put_shifts = []
    
    # Get spot price from morning snapshot for dynamic thresholds
    spot = morning.get("spot_price", 0) if morning else 0
    if not spot and evening_data:
        spot = evening_data[len(evening_data) // 2]["strike"]  # ATM estimate

    resistance_threshold = spot * 1.02  # 2% above spot
    support_threshold = spot * 0.98     # 2% below spot

    for o in evening_data:
        strike = o.get("strike", 0)

        # Call OI changes at higher strikes (resistance area)
        call_change = o.get("call_change_oi", 0)
        if call_change > 50000 and strike > resistance_threshold:
            call_shifts.append({
                "strike": strike,
                "change": call_change,
                "type": "CALL OI RISING",
                "signal": f"Shorts building at {strike}, resistance strengthening"
            })
        elif call_change < -50000 and strike > resistance_threshold:
            call_shifts.append({
                "strike": strike,
                "change": call_change,
                "type": "CALL OI FALLING",
                "signal": f"Shorts covering, breakout watch above {strike}"
            })

        # Put OI changes at lower strikes (support area)
        put_change = o.get("put_change_oi", 0)
        if put_change > 50000 and strike < support_threshold:
            put_shifts.append({
                "strike": strike,
                "change": put_change,
                "type": "PUT OI RISING",
                "signal": f"Hedges building at {strike}, support strengthening"
            })
        elif put_change < -50000 and strike < support_threshold:
            put_shifts.append({
                "strike": strike,
                "change": put_change,
                "type": "PUT OI FALLING",
                "signal": f"Hedges unwinding, breakdown risk below {strike}"
            })
    
    # Sort by magnitude and take top 3
    all_shifts = sorted(call_shifts + put_shifts, key=lambda x: abs(x["change"]), reverse=True)[:3]
    
    # Format signals for output
    signal_text = []
    if all_shifts:
        signal_text.append("📊 *OI Shift Signals:*")
        for s in all_shifts:
            emoji = "🔴" if "RISING" in s["type"] else "🟢"
            signal_text.append(f"{emoji} {s['signal']}")
    else:
        signal_text.append("📊 *OI Shifts:* No significant changes detected")
    
    return {
        "ok": True,
        "morning_snapshot_time": morning.get("created_at"),
        "shift_count": len(all_shifts),
        "shifts": all_shifts,
        "signal_text": "\n".join(signal_text)
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN: Run options analysis for a job execution
# ═══════════════════════════════════════════════════════════════════════════════

def run_options_analysis(symbol: str = "NIFTY", store: bool = True, run_label: str = "morning") -> Dict:
    """
    Execute full options pipeline for a job run.
    """
    print(f"📊 Running options analysis ({run_label})...")

    analysis = analyze_options_chain(symbol)
    if not analysis.get("ok"):
        return analysis

    if store:
        store_options_snapshot(symbol, run_label, analysis)

    return analysis


# ═══════════════════════════════════════════════════════════════════════════════
# FORMAT: Derivatives intelligence for AI prompt
# ═══════════════════════════════════════════════════════════════════════════════

def format_derivatives_intel(analysis: Dict) -> str:
    """
    Format GEX, skew, and advanced OI signals for AI prompt injection.
    """
    if not analysis or not analysis.get("ok"):
        return ""

    lines = []

    # GEX
    gex = analysis.get("gex", {})
    if gex.get("ok"):
        lines.append(f"GEX: {gex['net_gex_cr']:+.0f} Cr per 1% move — {gex['regime']}")
        lines.append(f"GEX Flip Level: {gex['flip_level']}")
        gex_levels = format_gex_levels(gex, analysis.get("spot_price"))
        if gex_levels:
            lines.append(gex_levels)

    # Skew
    skew = analysis.get("skew", {})
    if skew.get("ok"):
        lines.append(f"25D Risk Reversal: {skew['risk_reversal_25d']:+.1f} — {skew['rr_label']}")
        lines.append(f"25D Butterfly: {skew['butterfly_25d']:.1f} — {skew['bf_label']}")
        lines.append(f"ATM IV: {skew['atm_iv']}% | 25D Call IV: {skew['call_25d_iv']}% | 25D Put IV: {skew['put_25d_iv']}%")

    # Advanced OI
    adv = analysis.get("advanced_oi", {})
    if adv.get("ok"):
        lines.append(f"OWAS: {adv['owas']} ({adv['owas_bias']}, {adv['owas_distance_pct']:+.1f}% from spot)")
        lines.append(f"OI Concentration: {adv['concentration']}% in top 3 strikes {adv['concentration_strikes']}")

        if adv.get("oi_velocity"):
            vel = adv["oi_velocity"][0]
            lines.append(f"Fastest OI: {vel['side']} {vel['strike']} ({vel['velocity']}% velocity)")

        if adv.get("oi_imbalances"):
            imb = adv["oi_imbalances"][0]
            lines.append(f"Strongest OI wall: {imb['strike']} ({imb['type']}, imbalance {imb['imbalance']:+.2f})")

        if adv.get("unusual_activity"):
            ua = adv["unusual_activity"][0]
            lines.append(f"Unusual: {ua['side']} {ua['strike']} — {ua['signal']} (vol {ua['volume']:,}, OI chg {ua['oi_change']:+,})")

    return "\n".join(lines)


def format_gex_levels(gex_data: Dict, spot_price: float = None) -> str:
    """
    Compute magnetic support/resistance/pin from full strike-level GEX data.
    Returns formatted string or empty string if data insufficient.

    - Magnetic support: highest positive net GEX below spot
    - Magnetic resistance: highest negative net GEX above spot
    - Pin: strike where cumulative GEX crosses zero (from flip_level)
    """
    if not gex_data or not gex_data.get("ok"):
        return ""

    gex_by_strike = gex_data.get("gex_by_strike", [])
    if not gex_by_strike:
        return ""

    if spot_price is None:
        return ""

    support = None
    resistance = None
    for g in gex_by_strike:
        strike = g["strike"]
        net = g["net_gex"]
        if strike < spot_price and net > 0:
            if support is None or net > support["net_gex"]:
                support = g
        elif strike > spot_price and net < 0:
            if resistance is None or abs(net) > abs(resistance["net_gex"]):
                resistance = g

    def _strength_label(val: float) -> str:
        if val is None:
            return ""
        abs_val = abs(val)
        if abs_val > 100:
            return "Strong"
        elif abs_val > 40:
            return "Moderate"
        return "Weak"

    parts = []
    if support:
        strength = _strength_label(support["net_gex"])
        parts.append(f"Support {support['strike']:,.0f} ({strength})")
    if resistance:
        strength = _strength_label(resistance["net_gex"])
        parts.append(f"Resistance {resistance['strike']:,.0f} ({strength})")

    flip = gex_data.get("flip_level")
    if flip and spot_price:
        parts.append(f"Pin {flip:,.0f}")

    if parts:
        return f"🧲 GEX Levels: {' | '.join(parts)}"
    return ""


# ═══════════════════════════════════════════════════════════════════════════════
# OPTIONS FLOW INFERENCE — "Who is buying vs selling options?"
# Uses OI + price movement to infer flow direction (no flow data needed)
# ═══════════════════════════════════════════════════════════════════════════════

def infer_options_flow(options_data: List[Dict], spot_price: float = None) -> Dict:
    """
    Infer options flow direction from OI changes + price movement.
    No real flow data needed — pure inference from OI + IV + price.

    Flow classification per strike:
      OI increases + price increases = BUYERS dominant (new longs)
      OI increases + price decreases = SELLERS dominant (new shorts)
      OI decreases + price increases = SHORT COVERING
      OI decreases + price decreases = LONG LIQUIDATION

    Returns: flow classification, institutional activity, unusual strikes.
    """
    if not options_data:
        return {"ok": False, "message": "No options data"}

    if not spot_price and options_data:
        spot_price = options_data[0].get("_underlying", 0)

    flows = []
    institutional_flows = []
    unusual_strikes = []

    for o in options_data:
        strike = o["strike"]
        call_oi_chg = o.get("call_change_oi", 0) or 0
        put_oi_chg = o.get("put_change_oi", 0) or 0
        call_iv = o.get("call_iv", 0) or 0
        put_iv = o.get("put_iv", 0) or 0
        call_vol = o.get("call_volume", 0) or 0
        put_vol = o.get("put_volume", 0) or 0

        # Skip strikes with negligible activity
        if abs(call_oi_chg) < 1000 and abs(put_oi_chg) < 1000:
            continue

        # --- CALL SIDE FLOW ---
        if abs(call_oi_chg) > 1000:
            # Price proxy: if call IV is rising, price is likely rising
            iv_rising = call_iv > 15  # Above ATM baseline

            if call_oi_chg > 0 and iv_rising:
                call_flow = "BUYERS_DOMINANT"
                call_signal = "New long positions — institutional buying pressure"
            elif call_oi_chg > 0 and not iv_rising:
                call_flow = "SELLERS_DOMINANT"
                call_signal = "Selling premium — institutions capping upside"
            elif call_oi_chg < 0 and iv_rising:
                call_flow = "SHORT_COVERING"
                call_signal = "Shorts unwinding — potential breakout"
            else:
                call_flow = "LONG_LIQUIDATION"
                call_signal = "Longs exiting — reduce risk"

            # Institutional detection (large OI change + high volume)
            if abs(call_oi_chg) > 50000 and call_vol > 50000:
                institutional_flows.append({
                    "strike": strike, "side": "CALL", "flow": call_flow,
                    "oi_change": call_oi_chg, "volume": call_vol,
                    "signal": call_signal,
                })

            # Unusual activity (volume > 3x OI)
            if call_vol > 0 and o.get("call_oi", 0) > 0:
                vol_oi_ratio = call_vol / o["call_oi"]
                if vol_oi_ratio > 3:
                    unusual_strikes.append({
                        "strike": strike, "side": "CALL",
                        "vol_oi_ratio": round(vol_oi_ratio, 1),
                        "volume": call_vol, "oi_change": call_oi_chg,
                        "interpretation": "UNUSUAL — new positioning today",
                    })

        # --- PUT SIDE FLOW ---
        if abs(put_oi_chg) > 1000:
            iv_rising = put_iv > 15

            if put_oi_chg > 0 and iv_rising:
                put_flow = "BUYERS_DOMINANT"
                put_signal = "New put positions — hedging or bearish bets"
            elif put_oi_chg > 0 and not iv_rising:
                put_flow = "SELLERS_DOMINANT"
                put_signal = "Selling puts — institutions expect support"
            elif put_oi_chg < 0 and iv_rising:
                put_flow = "SHORT_COVERING"
                put_signal = "Put shorts unwinding — support may break"
            else:
                put_flow = "LONG_LIQUIDATION"
                put_signal = "Put holders exiting — bullish signal"

            if abs(put_oi_chg) > 50000 and put_vol > 50000:
                institutional_flows.append({
                    "strike": strike, "side": "PUT", "flow": put_flow,
                    "oi_change": put_oi_chg, "volume": put_vol,
                    "signal": put_signal,
                })

            if put_vol > 0 and o.get("put_oi", 0) > 0:
                vol_oi_ratio = put_vol / o["put_oi"]
                if vol_oi_ratio > 3:
                    unusual_strikes.append({
                        "strike": strike, "side": "PUT",
                        "vol_oi_ratio": round(vol_oi_ratio, 1),
                        "volume": put_vol, "oi_change": put_oi_chg,
                        "interpretation": "UNUSUAL — new positioning today",
                    })

    # Aggregate flow summary
    call_buyers = sum(1 for f in institutional_flows if f["side"] == "CALL" and "BUYERS" in f["flow"])
    call_sellers = sum(1 for f in institutional_flows if f["side"] == "CALL" and "SELLERS" in f["flow"])
    put_buyers = sum(1 for f in institutional_flows if f["side"] == "PUT" and "BUYERS" in f["flow"])
    put_sellers = sum(1 for f in institutional_flows if f["side"] == "PUT" and "SELLERS" in f["flow"])

    if call_buyers > call_sellers and put_sellers > put_buyers:
        overall = "INSTITUTIONAL BULLISH — call buying + put selling"
    elif call_sellers > call_buyers and put_buyers > put_sellers:
        overall = "INSTITUTIONAL BEARISH — call selling + put buying"
    else:
        overall = "MIXED — no clear institutional direction"

    return {
        "ok": True,
        "overall_flow": overall,
        "institutional_flows": sorted(institutional_flows, key=lambda x: abs(x["oi_change"]), reverse=True)[:5],
        "unusual_strikes": sorted(unusual_strikes, key=lambda x: x["vol_oi_ratio"], reverse=True)[:5],
        "call_buyers": call_buyers,
        "call_sellers": call_sellers,
        "put_buyers": put_buyers,
        "put_sellers": put_sellers,
    }


def format_options_flow(flow: Dict) -> str:
    """Format options flow inference for AI prompt."""
    if not flow.get("ok"):
        return ""

    lines = [f"[Options Flow Inference — {flow['overall_flow']}]"]

    for f in flow.get("institutional_flows", [])[:3]:
        emoji = "🟢" if "BUYERS" in f["flow"] else "🔴" if "SELLERS" in f["flow"] else "⚪"
        lines.append(f"  {emoji} {f['side']} {f['strike']}: {f['signal']} (OI chg: {f['oi_change']:+,}, vol: {f['volume']:,})")

    for u in flow.get("unusual_strikes", [])[:2]:
        lines.append(f"  ⚡ UNUSUAL: {u['side']} {u['strike']} — vol/OI ratio {u['vol_oi_ratio']}x ({u['interpretation']})")

    return "\n".join(lines)


if __name__ == "__main__":
    print("Options engine loaded.")