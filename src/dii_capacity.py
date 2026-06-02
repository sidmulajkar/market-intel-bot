"""
DII Capacity Gauge — Predict when the "DII Put" will fail.
DII absorption is not infinite. It relies on continuous MF SIP inflows.
This module tracks deployment ratio, saturation, and cushion erosion.

Data sources:
- fii_dii_flows table (daily DII net buy)
- mf_flows table (monthly MF net inflows)

Computation:
1. Deployment Ratio = DII Net Buy / (DII Net Buy + MF Net New Flows)
2. DEPLOYMENT SATURATION: Ratio > 85% for 5+ consecutive days
3. CUSHION ERODING: MF flows near zero while FII selling persists
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional


def _safe_float(val, default=0.0) -> float:
    try:
        return float(val) if val else default
    except (ValueError, TypeError):
        return default


def compute_dii_capacity(days: int = 5) -> Dict:
    """
    Compute DII capacity gauge from available data.

    Steps:
    1. Get last N days of FII/DII flows from Supabase.
    2. Get latest monthly MF net inflows.
    3. Compute per-day deployment ratio.
    4. Detect saturation and cushion erosion.
    """
    from src.db import get_fii_dii_flows, get_mf_flows

    # ── Daily FII/DII data ──
    flow_rows = get_fii_dii_flows(days=days + 5)
    if not flow_rows:
        return {"ok": False, "message": "No FII/DII flow data"}

    # Filter to last 5 trading days with DII data
    dii_days = []
    for r in flow_rows:
        dii = _safe_float(r.get("diinet_cr", 0))
        fii = _safe_float(r.get("fiinet_cr", 0))
        date = r.get("date", "")
        if dii != 0 or fii != 0:
            dii_days.append({"date": date, "dii_cr": dii, "fii_cr": fii})

    dii_days = dii_days[-days:]
    if not dii_days:
        return {"ok": False, "message": "No DII flow data in period"}

    # ── Monthly MF data ──
    mf_rows = get_mf_flows(months=4)
    mf_total_monthly = 0.0
    mf_month = ""
    if mf_rows:
        # Aggregate total net equity flows for latest month
        month_groups = {}
        for r in mf_rows:
            m = r.get("month", "")[:7]
            amt = _safe_float(r.get("amount_cr", 0))
            if m:
                month_groups.setdefault(m, 0.0)
                month_groups[m] += amt

        if month_groups:
            latest_month = max(month_groups.keys())
            mf_total_monthly = month_groups[latest_month]
            mf_month = latest_month

    # Daily MF inflow estimate (22 trading days per month)
    mf_daily_avg = mf_total_monthly / 22.0 if mf_total_monthly > 0 else 0

    # ── Compute deployment ratio per day ──
    days_analysis = []
    consecutive_saturated = 0
    max_consecutive = 0

    for d in dii_days:
        dii_net = d["dii_cr"]
        # Only count DII buying (positive = net buy)
        dii_buy = max(dii_net, 0)

        denominator = dii_buy + mf_daily_avg
        if denominator > 0 and dii_buy > 0:
            ratio = dii_buy / denominator
        else:
            ratio = 0.0

        saturated = ratio > 0.85

        if saturated:
            consecutive_saturated += 1
            max_consecutive = max(max_consecutive, consecutive_saturated)
        else:
            consecutive_saturated = 0

        days_analysis.append({
            "date": d["date"],
            "dii_cr": round(dii_net),
            "fii_cr": round(d["fii_cr"]),
            "ratio_pct": round(ratio * 100, 1),
            "saturated": saturated,
        })

    # ── CUSHION ERODING check ──
    # FII selling persists? Check if total FII selling > threshold
    total_fii_selling = sum(abs(min(d["fii_cr"], 0)) for d in dii_days)
    cushion_eroding = False
    cushion_detail = ""

    if mf_daily_avg <= 0:
        cushion_eroding = True
        cushion_detail = "MF inflows near zero — cushion depleted"
    elif mf_daily_avg < 100 and total_fii_selling > 2000:
        # MF inflows insufficient to offset FII selling
        cushion_eroding = True
        cushion_detail = f"MF inflows ₹{mf_daily_avg:.0f}Cr/day insufficient vs FII selling ₹{total_fii_selling:,.0f}Cr (5d)"
    elif total_fii_selling > 5000 and max_consecutive >= 3:
        cushion_eroding = True
        cushion_detail = f"Heavy FII selling (₹{total_fii_selling:,.0f}Cr) + high DII deployment ({max_consecutive}d)"

    # ── State guards (Analyst 1: handle negative DII, zero MF flows) ──
    latest_dii = dii_days[-1]["dii_cr"] if dii_days else 0

    # Guard 1: DII flipped to net selling → absorption broken
    if latest_dii < 0:
        status = "CRITICAL"
        detail = f"DII flipped to distribution (₹{latest_dii:+,}Cr) — absorption broken"
    # Guard 2: MF flows <= 0 while DII buying → SUPER_SATURATED
    elif mf_daily_avg <= 0 and max_consecutive >= 1:
        status = "SUPER_SATURATED"
        detail = f"MF inflows depleted (₹{mf_daily_avg:.0f}Cr/day) — DII eating into reserves"
    else:
        latest_ratio = days_analysis[-1]["ratio_pct"] if days_analysis else 0

        if max_consecutive >= 5:
            status = "SATURATED"
            detail = "DII eating into cash reserves — unsustainable"
        elif max_consecutive >= 3:
            status = "ELEVATED"
            detail = "DII deployment elevated — watch next 2 sessions"
        elif cushion_eroding:
            status = "CUSHION ERODING"
            detail = cushion_detail
        elif latest_ratio > 70:
            status = "ACTIVE"
            detail = "DII actively deploying — within sustainable range"
        else:
            status = "NORMAL"
            detail = "DII deployment healthy — ample cushion"

    return {
        "ok": True,
        "status": status,
        "detail": detail,
        "days_analyzed": len(days_analysis),
        "latest_dii_cr": round(dii_days[-1]["dii_cr"]) if dii_days else 0,
        "latest_ratio_pct": latest_ratio,
        "consecutive_saturated_days": max_consecutive,
        "mf_daily_avg_cr": round(mf_daily_avg),
        "mf_month": mf_month,
        "mf_total_monthly_cr": round(mf_total_monthly),
        "total_fii_selling_5d": round(total_fii_selling),
        "cushion_eroding": cushion_eroding,
        "days": days_analysis,
    }


def format_dii_capacity(cap: Dict) -> str:
    """Compact 1-2 line DII capacity gauge for Telegram.

    Full breakdown moved to /flows Telegram command context.
    """
    if not cap.get("ok"):
        return ""

    status = cap['status']
    detail = cap['detail']
    ratio = cap.get('latest_ratio_pct', 0)
    mf_daily = cap.get('mf_daily_avg_cr', 0)
    fii_5d = cap.get('total_fii_selling_5d', 0)

    # Sufficiency label
    if mf_daily <= 0:
        sufficiency = "zero MF inflows"
    elif mf_daily < 200:
        sufficiency = "insufficient"
    elif mf_daily < 500:
        sufficiency = "moderate"
    else:
        sufficiency = "adequate"

    mf_str = f"₹{mf_daily:+,}Cr/d" if mf_daily != 0 else "₹0Cr/d"
    fii_str = f"₹{fii_5d:,}Cr" if fii_5d != 0 else "₹0Cr"

    return (f"📊 DII Capacity: {ratio:.1f}% deployed (5D avg) "
            f"| Status: {status} ({detail}) "
            f"| MF Inflows: {mf_str} ({sufficiency}) "
            f"| FII 5D Sell: {fii_str}")


if __name__ == "__main__":
    result = compute_dii_capacity(days=5)
    print(format_dii_capacity(result))
