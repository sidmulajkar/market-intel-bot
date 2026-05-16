"""
Options Engine — NSE Options Chain Analysis
Single fetch per job execution. Stores snapshots to Supabase for shift detection.

Morning job: fetch → compute → store snapshot
Evening job: fetch → diff vs morning → compute shifts
"""
import requests
import os
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


# ═══════════════════════════════════════════════════════════════════════════════
# FETCH: NSE Options Chain
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_nse_options_chain(symbol: str = "NIFTY") -> List[Dict]:
    """
    Fetch NSE options chain for given symbol.
    Selects expiry: nearest expiry, but if <3 days to expiry → use next expiry.
    Returns list of strike-wise OI data.
    
    Note: Uses session to maintain cookies - hits homepage first.
    """
    from datetime import datetime, timedelta
    import requests
    
    # Create session and hit homepage first to get cookies
    session = requests.Session()
    homepage = "https://www.nseindia.com/"
    try:
        session.get(homepage, headers=NSE_HEADERS, timeout=10)
    except:
        pass  # Continue even if homepage fails
    
    url = f"https://www.nseindia.com/api/option-chain-equities?symbol={symbol}"
    try:
        # Retry once on 403 (session cookie expired)
        resp = session.get(url, headers=NSE_HEADERS, timeout=20)
        if resp.status_code == 403:
            # Retry with fresh session
            session = requests.Session()
            session.get("https://www.nseindia.com/", headers=NSE_HEADERS, timeout=10)
            resp = session.get(url, headers=NSE_HEADERS, timeout=20)
        
        if resp.status_code != 200:
            print(f"⚠️  Options API returned {resp.status_code}")
            return []

        data = resp.json()
        records = data.get("records", [])
        if not records:
            return []

        # Get expiries from data
        expiries = data.get("expiryList", [])
        if not expiries:
            # Fallback: extract unique expiries from records
            expiries = list(set(r.get("expiryDate", "") for r in records if r.get("expiryDate")))
        
        # Select appropriate expiry
        selected_expiry = None
        today = datetime.now().date()
        
        for exp in expiries:
            try:
                exp_date = datetime.strptime(exp, "%d %b %Y").date()
                days_to_expiry = (exp_date - today).days
                
                if selected_expiry is None:
                    selected_expiry = exp
                    selected_days = days_to_expiry
                elif days_to_expiry >= 0 and days_to_expiry < selected_days:
                    # Found closer expiry
                    if selected_days < 3 and days_to_expiry >= 3:
                        # Current is too close (<3 days), use next
                        selected_expiry = exp
                        selected_days = days_to_expiry
                    elif selected_days >= 3:
                        selected_expiry = exp
                        selected_days = days_to_expiry
            except:
                continue
        
        if not selected_expiry:
            # Fallback: use any available expiry
            selected_expiry = expiries[0] if expiries else ""
        
        print(f"   📅 Using expiry: {selected_expiry}")

        # Extract relevant fields from selected expiry only
        results = []
        for rec in records:
            # Filter by selected expiry
            if rec.get("expiryDate") != selected_expiry:
                continue
                
            results.append({
                "strike": rec.get("strikePrice", 0),
                "call_oi": rec.get("CE", {}).get("openInterest", 0) or 0,
                "call_change_oi": rec.get("CE", {}).get("changeinOpenInterest", 0) or 0,
                "call_volume": rec.get("CE", {}).get("totalTradedVolume", 0) or 0,
                "put_oi": rec.get("PE", {}).get("openInterest", 0) or 0,
                "put_change_oi": rec.get("PE", {}).get("changeinOpenInterest", 0) or 0,
                "put_volume": rec.get("PE", {}).get("totalTradedVolume", 0) or 0,
                "expiry": selected_expiry,
            })

        # Sort by strike price
        results.sort(key=lambda x: x["strike"])
        return results

    except Exception as e:
        print(f"⚠️  Options fetch error: {e}")
        return []


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
    Full options analysis — fetch + compute all metrics.
    """
    options_data = fetch_nse_options_chain(symbol)
    if not options_data:
        return {"ok": False, "message": "No options data"}

    # If no spot provided, estimate from ATM strike
    if not spot_price:
        spot_price = options_data[len(options_data)//2]["strike"]

    max_pain = compute_max_pain(options_data, spot_price)
    pcr = compute_pcr(options_data, spot_price)
    zones = compute_oi_zones(options_data, spot_price)

    return {
        "ok": True,
        "symbol": symbol,
        "spot_price": spot_price,
        "max_pain": max_pain,
        "pcr": pcr,
        "zones": zones,
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
            "support_zone": analysis.get("zones", {}).get("support_zone", []),
            "resistance_zone": analysis.get("zones", {}).get("resistance_zone", []),
        }

        client.table("options_snapshots").insert(data).execute()
        print(f"✅ Options snapshot stored: {run}")
        return True

    except Exception as e:
        print(f"⚠️  Store snapshot error: {e}")
        return False


def get_latest_snapshot(symbol: str, run: str) -> Optional[Dict]:
    """
    Retrieve last snapshot for comparison (evening job compares to morning).
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
            .order("created_at", descending=True)
            .limit(1)
            .execute()
        )

        if result.data:
            return result.data[0]
    except Exception as e:
        print(f"⚠️  Get snapshot error: {e}")

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# EVENING ONLY: Compute OI shifts vs morning snapshot
# ═══════════════════════════════════════════════════════════════════════════════

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
    
    for o in evening_data:
        strike = o.get("strike", 0)
        
        # Call OI changes at higher strikes (resistance area)
        call_change = o.get("call_change_oi", 0)
        if call_change > 50000 and strike > 22000:  # Resistance area
            call_shifts.append({
                "strike": strike,
                "change": call_change,
                "type": "CALL OI RISING",
                "signal": f"Shorts building at {strike}, resistance strengthening"
            })
        elif call_change < -50000 and strike > 22000:
            call_shifts.append({
                "strike": strike,
                "change": call_change,
                "type": "CALL OI FALLING", 
                "signal": f"Shorts covering, breakout watch above {strike}"
            })
        
        # Put OI changes at lower strikes (support area)
        put_change = o.get("put_change_oi", 0)
        if put_change > 50000 and strike < 23000:  # Support area
            put_shifts.append({
                "strike": strike,
                "change": put_change,
                "type": "PUT OI RISING",
                "signal": f"Hedges building at {strike}, support strengthening"
            })
        elif put_change < -50000 and strike < 23000:
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


if __name__ == "__main__":
    print("Options engine loaded.")