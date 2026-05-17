"""
Options Multi-Expiry Analysis — Fetch 3 expiries for term structure.
Compute gamma concentration, IV term structure, pinning strength.

Why multi-expiry matters:
  - Near expiry: high gamma → pinning, tight range
  - Far expiry: low gamma → directional bets
  - Term structure: backwardation (near > far) = fear, contango (far > near) = calm
"""
from typing import Dict, List, Optional
import statistics
import math


# ═══════════════════════════════════════════════════════════════════════════════
# BLACK-SCHOLES HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _norm_cdf(x: float) -> float:
    """Standard normal CDF approximation."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _bs_gamma(spot: float, strike: float, expiry_years: float,
              volatility: float, r: float = 0.06) -> float:
    """Black-Scholes gamma for European option."""
    if expiry_years <= 0 or volatility <= 0:
        return 0.0
    d1 = (math.log(spot / strike) + (r + 0.5 * volatility**2) * expiry_years) / (volatility * math.sqrt(expiry_years))
    n_d1 = math.exp(-0.5 * d1**2) / math.sqrt(2 * math.pi)
    return n_d1 / (spot * volatility * math.sqrt(expiry_years))


# ═══════════════════════════════════════════════════════════════════════════════
# MULTI-EXPIRY ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_multi_expiry(chain_data: List[Dict], spot_price: float) -> Dict:
    """
    Analyze options across multiple expiries.
    chain_data: list of option records with expiry, strike, OI, IV, etc.
    spot_price: current underlying price

    Returns term structure, gamma analysis, and pinning assessment.
    """
    if not chain_data or not spot_price:
        return {"ok": False, "message": "No options data"}

    # Group by expiry
    expiry_groups = {}
    for opt in chain_data:
        exp = opt.get("expiry")
        if not exp:
            continue
        if exp not in expiry_groups:
            expiry_groups[exp] = []
        expiry_groups[exp].append(opt)

    if len(expiry_groups) < 1:
        return {"ok": False, "message": "No expiry groups found"}

    # Sort expiries by date
    sorted_expiries = sorted(expiry_groups.keys())

    # Analyze each expiry
    expiry_analysis = []
    today = __import__('datetime').datetime.now().date()

    for exp_date in sorted_expiries:
        try:
            exp = __import__('datetime').datetime.strptime(exp_date, "%Y-%m-%d").date()
        except (ValueError, AttributeError):
            try:
                exp = __import__('datetime').datetime.strptime(exp_date, "%d-%b-%Y").date()
            except (ValueError, AttributeError):
                continue

        days_to_expiry = (exp - today).days
        if days_to_expiry < 0:
            continue

        options = expiry_groups[exp_date]

        # Compute total OI by side
        call_oi = sum(o.get("call_oi", 0) or 0 for o in options)
        put_oi = sum(o.get("put_oi", 0) or 0 for o in options)

        # PCR for this expiry
        pcr = put_oi / call_oi if call_oi > 0 else 1.0

        # Average IV
        call_ivs = [o.get("call_iv", 0) for o in options if o.get("call_iv")]
        put_ivs = [o.get("put_iv", 0) for o in options if o.get("put_iv")]
        avg_call_iv = statistics.mean(call_ivs) if call_ivs else 0
        avg_put_iv = statistics.mean(put_ivs) if put_ivs else 0

        # Max pain for this expiry
        min_loss = float('inf')
        max_pain_strike = spot_price
        for opt in options:
            strike = opt.get("strike", 0)
            if strike <= 0:
                continue
            call_oi_at = opt.get("call_oi", 0) or 0
            put_oi_at = opt.get("put_oi", 0) or 0
            loss = sum(max(strike - spot_price, 0) * call_oi_at for _ in [1]) + \
                   sum(max(spot_price - strike, 0) * put_oi_at for _ in [1])
            # Simplified: find strike with highest total OI
            total_oi = call_oi_at + put_oi_at
            if total_oi > 0:
                # Max pain approximation: strike closest to heaviest OI
                pass

        # Gamma concentration: compute total gamma near ATM (±2%)
        total_gamma = 0
        atm_gamma = 0
        for opt in options:
            strike = opt.get("strike", 0)
            if strike <= 0:
                continue
            call_oi_at = opt.get("call_oi", 0) or 0
            put_oi_at = opt.get("put_oi", 0) or 0
            iv = (opt.get("call_iv", 20) or 20) / 100  # Convert from %
            expiry_years = days_to_expiry / 365.0

            gamma = _bs_gamma(spot_price, strike, expiry_years, iv)
            total_gamma += gamma * (call_oi_at + put_oi_at)

            # ATM gamma (within 2% of spot)
            if abs(strike - spot_price) / spot_price < 0.02:
                atm_gamma += gamma * (call_oi_at + put_oi_at)

        expiry_analysis.append({
            "expiry": exp_date,
            "days_to_expiry": days_to_expiry,
            "call_oi": call_oi,
            "put_oi": put_oi,
            "pcr": round(pcr, 2),
            "avg_call_iv": round(avg_call_iv, 1),
            "avg_put_iv": round(avg_put_iv, 1),
            "total_gamma": round(total_gamma, 4),
            "atm_gamma": round(atm_gamma, 4),
        })

    if len(expiry_analysis) < 1:
        return {"ok": False, "message": "Could not analyze expiries"}

    # Term structure analysis
    ivs = [e["avg_call_iv"] for e in expiry_analysis if e["avg_call_iv"] > 0]
    if len(ivs) >= 2:
        if ivs[0] > ivs[-1] * 1.1:
            term_structure = "BACKWARDATION — near IV > far IV (fear/complacency trap)"
        elif ivs[-1] > ivs[0] * 1.1:
            term_structure = "CONTANGO — far IV > near IV (normal, calm)"
        else:
            term_structure = "FLAT — no term structure signal"
    else:
        term_structure = "INSUFFICIENT DATA"

    # Gamma concentration
    nearest = expiry_analysis[0]
    gamma_ratio = nearest["atm_gamma"] / nearest["total_gamma"] if nearest["total_gamma"] > 0 else 0

    if gamma_ratio > 0.5:
        gamma_concentration = "HIGH — gamma concentrated near ATM (pinning risk)"
    elif gamma_ratio > 0.3:
        gamma_concentration = "MODERATE — some pinning effect"
    else:
        gamma_concentration = "LOW — gamma distributed (directional bets)"

    # Pinning strength
    days_to_nearest = nearest["days_to_expiry"]
    if days_to_nearest <= 2:
        pinning = "VERY STRONG — expiry in ≤2 days, max pain gravity strongest"
    elif days_to_nearest <= 5:
        pinning = "STRONG — expiry within 5 days, pinning active"
    elif days_to_nearest <= 7:
        pinning = "MODERATE — expiry this week"
    else:
        pinning = "WEAK — expiry > 7 days out"

    return {
        "ok": True,
        "expiries": expiry_analysis,
        "term_structure": term_structure,
        "gamma_concentration": gamma_concentration,
        "pinning_strength": pinning,
        "nearest_expiry": nearest,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# FORMATTING
# ═══════════════════════════════════════════════════════════════════════════════

def format_multi_expiry(analysis: Dict) -> str:
    """Format multi-expiry analysis for AI prompt injection."""
    if not analysis.get("ok"):
        return ""

    lines = ["[Options Multi-Expiry Analysis — Term Structure + Gamma]"]

    for exp in analysis.get("expiries", []):
        lines.append(f"\n  📅 {exp['expiry']} ({exp['days_to_expiry']} days):")
        lines.append(f"    OI: Call {exp['call_oi']:,} | Put {exp['put_oi']:,} | PCR: {exp['pcr']}")
        lines.append(f"    IV: Call {exp['avg_call_iv']:.1f}% | Put {exp['avg_put_iv']:.1f}%")
        lines.append(f"    Gamma: {exp['total_gamma']:.4f} (ATM: {exp['atm_gamma']:.4f})")

    lines.append(f"\n  Term Structure: {analysis['term_structure']}")
    lines.append(f"  Gamma Concentration: {analysis['gamma_concentration']}")
    lines.append(f"  Pinning: {analysis['pinning_strength']}")

    # Insight
    nearest = analysis.get("nearest_expiry", {})
    if nearest.get("days_to_expiry", 99) <= 3:
        lines.append(f"\n  ⚡ Near expiry ({nearest['days_to_expiry']}d): Expect pinning around max pain.")
        lines.append(f"  Post-expiry directional move likely. Watch for gamma unwind.")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def run_multi_expiry_analysis(chain_data: List[Dict], spot_price: float) -> Dict:
    """Full multi-expiry analysis pipeline."""
    analysis = analyze_multi_expiry(chain_data, spot_price)
    formatted = format_multi_expiry(analysis)

    return {
        "ok": analysis.get("ok", False),
        "analysis": analysis,
        "formatted": formatted,
    }


if __name__ == "__main__":
    # Test with dummy data
    from datetime import datetime, timedelta
    today = datetime.now().date()
    exp1 = (today + timedelta(days=3)).strftime("%Y-%m-%d")
    exp2 = (today + timedelta(days=10)).strftime("%Y-%m-%d")

    test_chain = [
        {"expiry": exp1, "strike": 25400, "call_oi": 100000, "put_oi": 80000, "call_iv": 18, "put_iv": 20},
        {"expiry": exp1, "strike": 25500, "call_oi": 150000, "put_oi": 50000, "call_iv": 20, "put_iv": 22},
        {"expiry": exp1, "strike": 25300, "call_oi": 80000, "put_oi": 120000, "call_iv": 16, "put_iv": 18},
        {"expiry": exp2, "strike": 25400, "call_oi": 120000, "put_oi": 90000, "call_iv": 15, "put_iv": 17},
        {"expiry": exp2, "strike": 25500, "call_oi": 180000, "put_oi": 60000, "call_iv": 17, "put_iv": 19},
    ]

    result = run_multi_expiry_analysis(test_chain, 25400)
    if result["ok"]:
        print(result["formatted"])
    else:
        print(f"No data: {result.get('message')}")
