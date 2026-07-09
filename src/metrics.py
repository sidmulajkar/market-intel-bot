"""
Canonical metric computation functions — single source of truth.

Each function takes raw inputs and returns a structured dict.
No DB calls, no NSE calls — pure computation only.
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════════
# FII/DII FLOW METRICS
# ═══════════════════════════════════════════════════════════════════════

def compute_flow_metrics(rows: List[Dict]) -> Dict:
    """
    Compute all FII/DII flow metrics from raw fii_dii_flows rows.
    Combines logic from context_engine.get_fii_dii_context() AND
    formatters.format_flows() into a single canonical computation.

    Args:
        rows: List of dicts with keys {date, fiinet_cr, diinet_cr}
              from get_fii_dii_flows()

    Returns:
        Structured dict with all flow metrics, or {"ok": False, ...} on failure.
    """
    import pandas as pd

    if not rows or len(rows) < 3:
        return {"ok": False, "message": "Insufficient FII/DII data (<3 rows)"}

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df["fiinet_cr"] = df["fiinet_cr"].astype(float)
    df["diinet_cr"] = df["diinet_cr"].astype(float)
    df = df.sort_values("date")

    # Latest values
    latest = df.iloc[-1]
    fii_current = latest["fiinet_cr"]
    dii_current = latest["diinet_cr"]
    net_current = fii_current + dii_current

    # 4-week rolling average
    df["fii_4w_avg"] = df["fiinet_cr"].rolling(20, min_periods=5).mean()
    df["dii_4w_avg"] = df["diinet_cr"].rolling(20, min_periods=5).mean()
    prev_avg_fii = df["fii_4w_avg"].iloc[-1] if pd.notna(df["fii_4w_avg"].iloc[-1]) else 0
    prev_avg_dii = df["dii_4w_avg"].iloc[-1] if pd.notna(df["dii_4w_avg"].iloc[-1]) else 0

    # Z-score vs 20-day avg
    fii_std = df["fiinet_cr"].tail(20).std()
    fii_z_score = (fii_current - prev_avg_fii) / fii_std if fii_std and fii_std > 0 else 0

    # Streak detection (sell)
    fii_sell_streak = 0
    for i in range(len(df) - 1, -1, -1):
        if df.iloc[i]["fiinet_cr"] < 0:
            fii_sell_streak += 1
        else:
            break

    # Streak detection (buy)
    fii_buy_streak = 0
    for i in range(len(df) - 1, -1, -1):
        if df.iloc[i]["fiinet_cr"] > 0:
            fii_buy_streak += 1
        else:
            break

    # Overall streak direction
    if fii_sell_streak >= fii_buy_streak:
        fii_streak = fii_sell_streak
        fii_streak_direction = "negative"
    else:
        fii_streak = fii_buy_streak
        fii_streak_direction = "positive"

    # DII absorption — use compute_absorption for percentage + label
    from src.formatters import compute_absorption
    absorption_pct, absorption_label = compute_absorption(fii_current, dii_current)

    # DII absorption ratio (context_engine style, capped at 2.0)
    ratio = abs(dii_current) / abs(fii_current) if fii_current != 0 else 0
    dii_absorbed = min(ratio, 2.0)

    # 5-day FII stats
    last_5 = df.tail(5)
    fii_5d_total = last_5["fiinet_cr"].sum()
    fii_5d_avg = last_5["fiinet_cr"].mean()
    largest_sell_day = last_5["fiinet_cr"].min()
    largest_buy_day = last_5["fiinet_cr"].max()

    # Weekly grouping for 4-week trend
    df["year"] = df["date"].dt.isocalendar().year
    df["week"] = df["date"].dt.isocalendar().week
    df["yw"] = df["year"].astype(str) + "_" + df["week"].astype(str)

    weekly = df.groupby("yw").agg(
        date_start=("date", "min"),
        fiinet_cr=("fiinet_cr", "sum"),
        diinet_cr=("diinet_cr", "sum")
    ).reset_index().sort_values("date_start")

    valid_weeks = []
    for yw in weekly["yw"].values:
        count = len(df[df["yw"] == yw])
        if count >= 3:
            valid_weeks.append(yw)

    fii_4w_trend = None
    fii_4w_weekly = []
    if valid_weeks:
        recent_yws = valid_weeks[-4:]
        fii_weekly_nets = []
        for yw in recent_yws:
            w = weekly[weekly["yw"] == yw].iloc[0]
            fii_weekly_nets.append(w["fiinet_cr"])
        fii_4w_weekly = fii_weekly_nets

        if len(fii_weekly_nets) >= 4:
            import statistics
            neg_count = sum(1 for x in fii_weekly_nets if x < 0)
            pos_count = sum(1 for x in fii_weekly_nets if x > 0)
            avg = statistics.mean(fii_weekly_nets)
            stdev = statistics.stdev(fii_weekly_nets) if len(fii_weekly_nets) > 1 else 0
            cv = stdev / abs(avg) if avg != 0 else 999

            if neg_count == 4 and cv < 0.15:
                fii_4w_trend = "persistent outflows"
            elif pos_count == 4 and cv < 0.15:
                fii_4w_trend = "persistent inflows"
            elif neg_count >= 3 and fii_weekly_nets[-1] < fii_weekly_nets[-2]:
                fii_4w_trend = "deteriorating"
            elif neg_count >= 3 and fii_weekly_nets[-1] > fii_weekly_nets[-2]:
                fii_4w_trend = "outflows moderating"
            elif pos_count >= 3 and fii_weekly_nets[-1] > fii_weekly_nets[-2]:
                fii_4w_trend = "improving"
            elif pos_count >= 3 and fii_weekly_nets[-1] < fii_weekly_nets[-2]:
                fii_4w_trend = "inflows moderating"
            else:
                fii_4w_trend = "mixed"

    # Confidence
    row_count = len(df)
    confidence = "HIGH" if row_count >= 20 else "MEDIUM" if row_count >= 10 else "LOW"

    return {
        "ok": True,
        "fii_net": fii_current,
        "dii_net": dii_current,
        "net": net_current,
        "fii_4w_avg": round(prev_avg_fii, 1),
        "dii_4w_avg": round(prev_avg_dii, 1),
        "fii_z_score": round(fii_z_score, 2),
        "fii_streak": fii_streak,
        "fii_streak_direction": fii_streak_direction,
        "fii_sell_streak": fii_sell_streak,
        "fii_buy_streak": fii_buy_streak,
        "fii_5d_total": round(fii_5d_total, 1),
        "fii_5d_avg": round(fii_5d_avg, 1),
        "largest_sell_day": round(largest_sell_day, 1),
        "largest_buy_day": round(largest_buy_day, 1),
        "dii_absorbed": dii_absorbed,
        "dii_absorption_pct": absorption_pct,
        "dii_absorption_label": absorption_label,
        "fii_4w_trend": fii_4w_trend,
        "fii_4w_weekly": fii_4w_weekly,
        "confidence": confidence,
        "date": latest["date"].strftime("%d %b"),
        "date_full": latest["date"].strftime("%Y-%m-%d"),
        "data_points": row_count,
    }


# ═══════════════════════════════════════════════════════════════════════
# VIX CONTEXT
# ═══════════════════════════════════════════════════════════════════════

def compute_vix_context(vix_price: float, vix_percentile: Optional[float] = None) -> Dict:
    """
    Compute VIX regime with percentile-aware classification.
    Unifies context_engine.get_vix_regime() + dashboard VIX display logic.

    Args:
        vix_price: Current India VIX value
        vix_percentile: Optional 1Y percentile (0-100) from pre-computed ctx

    Returns:
        Dict with vix_regime, vix_label, vix_icon, vix_percentile.
    """
    if vix_price is None or vix_price <= 0:
        return {"ok": False, "message": "VIX data unavailable"}

    # Regime (context_engine style — used for scoring)
    if vix_price > 20:
        vix_regime = "HIGH"
    elif vix_price < 15:
        vix_regime = "LOW"
    else:
        vix_regime = "NORMAL"

    # Label (dashboard style — percentile-aware for display)
    if vix_percentile is not None and vix_percentile >= 85:
        vix_label = "EXTREME"
    elif vix_percentile is not None and vix_percentile >= 70:
        vix_label = "ELEVATED"
    elif vix_price > 25:
        vix_label = "HIGH"
    elif vix_percentile is not None and vix_percentile <= 15:
        vix_label = "COMPLACENT"
    elif vix_price < 15:
        vix_label = "LOW"
    else:
        vix_label = "NORMAL"

    # Icon (for signal display)
    if vix_price > 20:
        vix_icon = "\U0001f534"  # red
    elif vix_price < 15:
        vix_icon = "\U0001f7e2"  # green
    else:
        vix_icon = "\U0001f7e1"  # yellow

    return {
        "ok": True,
        "vix_price": vix_price,
        "vix_regime": vix_regime,
        "vix_label": vix_label,
        "vix_icon": vix_icon,
        "vix_percentile": vix_percentile,
    }


# ═══════════════════════════════════════════════════════════════════════
# VALUATION METRICS
# ═══════════════════════════════════════════════════════════════════════

def compute_vix_interpretation(vix_ctx: Dict, macro_ctx: Dict = None, ctx: Dict = None) -> Dict:
    """
    Pre-computed VIX interpretation — tells AI what the VIX means, not just its value.
    Combines regime, percentile, temporal context, and cross-signal contradictions.

    Args:
        vix_ctx: output from compute_vix_context()
        macro_ctx: macro_context from run_contextualization (for vix_price, vix_change)
        ctx: full context dict (for phase, cross_asset_regime, etc.)

    Returns:
        Dict with interpretation string, risk_level, contradictions.
    """
    if not vix_ctx or not vix_ctx.get("ok"):
        return {"ok": False, "message": "VIX context unavailable"}

    vix_price = vix_ctx.get("vix_price", 0)
    vix_regime = vix_ctx.get("vix_regime", "NORMAL")
    vix_label = vix_ctx.get("vix_label", "NORMAL")
    vix_pctile = vix_ctx.get("vix_percentile")

    mp = (ctx or {}).get("market_phase", {})
    phase = mp.get("phase", "NEUTRAL")

    # Core interpretation — what the VIX is saying
    interpretations = []

    if vix_label == "EXTREME":
        interpretations.append(
            f"VIX {vix_price:.1f} at extreme — panic pricing. "
            f"{'Historically, extreme VIX marks near-term bottoms — fear is the signal.' if vix_pctile and vix_pctile >= 85 else 'Fear elevated.'}"
        )
    elif vix_label == "ELEVATED":
        interpretations.append(
            f"VIX {vix_price:.1f} elevated — caution warranted. "
            f"{'Premium prices rising, hedging costly.' if vix_pctile and vix_pctile >= 70 else 'Above-normal fear.'}"
        )
    elif vix_label == "COMPLACENT":
        if phase in ("EXPANSION", "RECOVERY"):
            interpretations.append(
                f"VIX {vix_price:.1f} complacent — market not pricing risk. "
                f"Low VIX at market highs = crowded longs. First crack triggers sharp VIX spike."
            )
        else:
            interpretations.append(
                f"VIX {vix_price:.1f} complacent — calm before storm risk. "
                f"Low VIX doesn't mean safe — means no hedging."
            )
    elif vix_label == "HIGH":
        interpretations.append(
            f"VIX {vix_price:.1f} high — elevated fear. "
            f"Option premiums 15-25% above normal. Risk-off environment."
        )
    elif vix_regime == "LOW":
        interpretations.append(
            f"VIX {vix_price:.1f} low — risk-on environment. "
            f"Low volatility supports higher valuations."
        )
    else:
        interpretations.append(
            f"VIX {vix_price:.1f} normal — no volatility signal."
        )

    # Cross-signal contradictions
    contradictions = []
    car = (ctx or {}).get("cross_asset_regime", {})
    if car.get("regime") == "RISK_ON" and vix_label in ("ELEVATED", "HIGH"):
        contradictions.append("VIX elevated but cross-asset regime is RISK_ON — VIX may be overstating fear")
    if car.get("regime") == "RISK_OFF" and vix_label == "COMPLACENT":
        contradictions.append("VIX complacent but cross-asset regime is RISK_OFF — VIX understating risk")

    # Streak/duration context
    vix_temporal = (ctx or {}).get("vix_temporal", {})
    if vix_temporal.get("streak_days", 0) >= 5:
        avg_dur = vix_temporal.get("avg_historical_duration", 0)
        if avg_dur > 0:
            interpretations.append(
                f"VIX in {vix_regime.lower()} regime for {vix_temporal['streak_days']} days "
                f"(historical avg: {avg_dur:.0f}d) — regime shift likely"
            )
        else:
            interpretations.append(
                f"VIX in {vix_regime.lower()} regime for {vix_temporal['streak_days']} consecutive days — persistent"
            )

    # Risk level
    if vix_label in ("EXTREME",):
        risk_level = "HIGH"
    elif vix_label in ("ELEVATED", "HIGH"):
        risk_level = "ELEVATED"
    elif vix_label == "COMPLACENT":
        risk_level = "HIDDEN"  # hidden risk — complacency
    else:
        risk_level = "NORMAL"

    return {
        "ok": True,
        "interpretation": " ".join(interpretations),
        "risk_level": risk_level,
        "contradictions": contradictions,
        "vix_price": vix_price,
        "vix_regime": vix_regime,
        "vix_label": vix_label,
    }


def compute_fii_interpretation(flow_metrics: Dict, ctx: Dict = None) -> Dict:
    """
    Pre-computed FII regime interpretation — tells AI what flows mean, not just numbers.
    Combines streak, z-score, 4-week trend, and cross-signal context.

    Args:
        flow_metrics: output from compute_flow_metrics()
        ctx: full context dict (for cross_asset_regime, bull_bear, etc.)

    Returns:
        Dict with interpretation string, regime, transition_signal.
    """
    if not flow_metrics or not flow_metrics.get("ok"):
        return {"ok": False, "message": "Flow metrics unavailable"}

    fm = flow_metrics
    fii_net = fm.get("fii_net", 0)
    fii_streak = fm.get("fii_streak", 0)
    streak_dir = fm.get("fii_streak_direction", "neutral")
    fii_z = fm.get("fii_z_score", 0)
    fii_4w_trend = fm.get("fii_4w_trend")
    fii_4w_avg = fm.get("fii_4w_avg", 0)

    interpretations = []

    # Core regime based on streak + trend
    if streak_dir == "negative" and fii_streak >= 5:
        if fii_4w_trend == "persistent outflows":
            interpretations.append(
                f"FII persistent outflows — {fii_streak}-day selling streak, all 4 weeks negative. "
                f"This is structural selling, not tactical. Pattern only breaks on external catalyst."
            )
        elif fii_4w_trend == "outflows moderating":
            interpretations.append(
                f"FII selling {fii_streak} days but 4-week trend moderating. "
                f"Outflows decelerating — selling pressure easing but not yet reversed."
            )
        else:
            interpretations.append(
                f"FII extended selling — {fii_streak}-day streak. "
                f"{'Persistent outflows averaging ₹' + f'{abs(fii_4w_avg):,.0f}Cr/week.' if fii_4w_avg != 0 else 'Selling accelerating.'}"
            )
    elif streak_dir == "positive" and fii_streak >= 3:
        if fii_4w_trend == "persistent inflows":
            interpretations.append(
                f"FII persistent inflows — {fii_streak}-day buying streak, all 4 weeks positive. "
                f"Structural accumulation in progress."
            )
        elif fii_4w_trend == "improving":
            interpretations.append(
                f"FII buying {fii_streak} days and accelerating. "
                f"Inflows gaining momentum."
            )
        else:
            interpretations.append(
                f"FII buying — {fii_streak}-day streak. "
                f"Flows turning positive."
            )
    elif fii_net < -2000:
        interpretations.append(
            f"FII heavy single-day selling (₹{fii_net:,.0f}Cr). "
            f"{'Sharp outflow' if fii_z < -1.5 else 'Moderate selling'}. "
            f"Watch if this starts a streak."
        )
    elif fii_net > 2000:
        interpretations.append(
            f"FII strong single-day buying (₹{fii_net:,.0f}Cr). "
            f"{'Sharp inflow' if fii_z > 1.5 else 'Moderate buying'}. "
            f"Watch for follow-through."
        )
    else:
        interpretations.append(
            f"FII flows muted (₹{fii_net:,.0f}Cr) — no directional conviction."
        )

    # Transition detection — key signal
    transition_signal = None
    if (fii_4w_trend == "outflows moderating" and
        fm.get("fii_5d_total", 0) > 0 and
        streak_dir == "negative"):
        transition_signal = (
            "TRANSITION SIGNAL: 4-week outflows moderating + 5-day net positive = "
            "selling pressure peaking. First sign of reversal."
        )
    elif (fii_4w_trend == "inflows moderating" and
          fm.get("fii_5d_total", 0) < 0):
        transition_signal = (
            "TRANSITION SIGNAL: 4-week inflows moderating + 5-day net negative = "
            "buying momentum fading. Caution on new longs."
        )

    # Z-score context
    if abs(fii_z) > 2.0:
        interpretations.append(
            f"Z-score {fii_z:+.2f} — extreme {'selling' if fii_z < 0 else 'buying'} "
            f"(>2σ from 20-day average). Mean reversion likely."
        )

    # Cross-signal contradiction
    car = (ctx or {}).get("cross_asset_regime", {})
    bb = (ctx or {}).get("bull_bear", {})
    if fii_net < -1000 and bb.get("score", 50) > 65:
        interpretations.append(
            "Note: FII selling but Bull/Bear score bullish — DII or other signals offsetting FII pressure"
        )

    # Regime label
    if streak_dir == "negative" and fii_streak >= 5:
        regime = "PERSISTENT_SELLING"
    elif streak_dir == "positive" and fii_streak >= 3:
        regime = "PERSISTENT_BUYING"
    elif abs(fii_net) > 2000:
        regime = "SHARP_MOVE"
    else:
        regime = "MUTED"

    result = {
        "ok": True,
        "interpretation": " ".join(interpretations),
        "regime": regime,
        "fii_net": fii_net,
        "fii_streak": fii_streak,
        "streak_direction": streak_dir,
        "fii_z_score": fii_z,
        "fii_4w_trend": fii_4w_trend,
    }
    if transition_signal:
        result["transition_signal"] = transition_signal
    return result


def compute_absorption_interpretation(flow_metrics: Dict, ctx: Dict = None) -> Dict:
    """
    Pre-computed DII absorption interpretation — tells AI what absorption means.
    Combines absorption %, FII/DII direction, and sustainability assessment.

    Args:
        flow_metrics: output from compute_flow_metrics()
        ctx: full context dict

    Returns:
        Dict with interpretation string, sustainability, warning.
    """
    if not flow_metrics or not flow_metrics.get("ok"):
        return {"ok": False, "message": "Flow metrics unavailable"}

    fm = flow_metrics
    fii_net = fm.get("fii_net", 0)
    dii_net = fm.get("dii_net", 0)
    absorb_pct = fm.get("dii_absorption_pct")
    absorb_label = fm.get("dii_absorption_label", "")
    net = fm.get("net", 0)

    interpretations = []

    if fii_net < 0 and dii_net > 0 and absorb_pct is not None:
        if absorb_pct >= 100:
            interpretations.append(
                f"DII absorbing {absorb_pct:.0f}% of FII outflow — more than offsetting. "
                f"Net positive (₹{net:+,.0f}Cr). DII is the market floor right now."
            )
        elif absorb_pct >= 80:
            interpretations.append(
                f"DII absorbing {absorb_pct:.0f}% of FII outflow — strong floor. "
                f"Selling pressure significantly muted. Market resilience depends on DII continuation."
            )
        elif absorb_pct >= 50:
            interpretations.append(
                f"DII absorbing {absorb_pct:.0f}% of FII outflow — partial cushion. "
                f"Net negative (₹{net:+,.0f}Cr). DII softens blow but doesn't prevent decline."
            )
        else:
            interpretations.append(
                f"DII absorbing only {absorb_pct:.0f}% of FII outflow — weak support. "
                f"Net negative (₹{net:+,.0f}Cr). Genuine selling pressure, minimal DII defense."
            )

        # Sustainability warning
        if absorb_pct >= 80:
            # Check if DII has been consistently buying
            dii_4w_avg = fm.get("dii_4w_avg", 0)
            if dii_4w_avg > 0 and dii_net > dii_4w_avg * 1.5:
                interpretations.append(
                    f"Warning: DII buying today (₹{dii_net:,.0f}Cr) well above 4-week avg (₹{dii_4w_avg:,.0f}Cr). "
                    f"Unsustainable pace — DII fatigue risk if this continues."
                )
    elif fii_net < 0 and dii_net <= 0:
        interpretations.append(
            f"FII selling (₹{fii_net:,.0f}Cr) with NO DII offset (₹{dii_net:,.0f}Cr). "
            f"Both foreign and domestic institutions selling — rare and bearish."
        )
    elif fii_net > 0 and dii_net > 0:
        interpretations.append(
            f"Both FII (₹{fii_net:,.0f}Cr) and DII (₹{dii_net:,.0f}Cr) buying — "
            f"broad institutional accumulation. Strong positive signal."
        )
    elif fii_net > 0:
        interpretations.append(
            f"FII buying (₹{fii_net:,.0f}Cr), DII {'selling' if dii_net < 0 else 'neutral'} "
            f"(₹{dii_net:,.0f}Cr). Foreign-led rally, domestic participation absent."
        )
    else:
        interpretations.append(
            f"FII/DII flows inconclusive — no absorption signal."
        )

    # Determine sustainability
    if fii_net < 0 and dii_net > 0 and absorb_pct is not None:
        if absorb_pct >= 100:
            sustainability = "STRONG"
        elif absorb_pct >= 80:
            sustainability = "MODERATE"
        elif absorb_pct >= 50:
            sustainability = "WEAK"
        else:
            sustainability = "INSUFFICIENT"
    elif fii_net > 0 and dii_net > 0:
        sustainability = "BROAD_ACCUMULATION"
    elif fii_net < 0 and dii_net <= 0:
        sustainability = "BROAD_DISTRIBUTION"
    else:
        sustainability = "NEUTRAL"

    return {
        "ok": True,
        "interpretation": " ".join(interpretations),
        "sustainability": sustainability,
        "absorption_pct": absorb_pct,
        "absorption_label": absorb_label,
        "fii_net": fii_net,
        "dii_net": dii_net,
        "net": net,
    }


def compute_valuation_metrics(
    pe: float,
    pb: Optional[float] = None,
    earnings_yield: Optional[float] = None,
    g_sec_yield: float = 7.1,
    historical_pe: Optional[List[float]] = None,
) -> Dict:
    """
    Compute all valuation metrics from raw NSE data.
    Wraps valuation_engine functions into a single dict.

    Args:
        pe: Nifty P/E from NSE
        pb: Nifty P/B from NSE
        earnings_yield: (1/pe * 100) — computed if not provided
        g_sec_yield: 10Y G-Sec yield
        historical_pe: Optional list of historical P/E values for percentile

    Returns:
        Dict with pe, pb, earnings_yield, erp_premium, erp_label,
        reverse_dcf, pe_percentile, erp_pe_bridge_note.
    """
    from src.valuation_engine import (
        compute_equity_risk_premium,
        compute_reverse_dcf,
    )
    from src.formatters import _ordinal

    # Derived earnings yield
    if earnings_yield is None:
        earnings_yield = (1 / pe * 100) if pe > 0 else 0

    # ERP
    erp = compute_equity_risk_premium(earnings_yield, g_sec_yield)

    # Reverse DCF
    rdcf = compute_reverse_dcf(pe)

    # P/E percentile
    pe_percentile = None
    pe_percentile_label = None
    if historical_pe and len(historical_pe) >= 5:
        try:
            from src.quant_enrichment import compute_percentile
            pct = compute_percentile(pe, historical_pe)
            if pct.get("percentile") is not None:
                pe_percentile = pct["percentile"]
                pe_percentile_label = _ordinal(int(pe_percentile))
        except Exception:
            pass

    # ERP vs P/E bridge note (conflict explanation)
    erp_pe_bridge_note = None
    if pe_percentile is not None and pe_percentile < 40 and erp["premium"] < 0:
        erp_pe_bridge_note = "P/E historically cheap but ERP negative — bonds more attractive than equities at current rates"

    return {
        "ok": True,
        "pe": round(pe, 2),
        "pb": round(pb, 2) if pb else None,
        "earnings_yield": round(earnings_yield, 2),
        "erp_premium": erp.get("premium"),
        "erp_label": erp.get("label"),
        "reverse_dcf": rdcf,
        "pe_percentile": pe_percentile,
        "pe_percentile_label": pe_percentile_label,
        "erp_pe_bridge_note": erp_pe_bridge_note,
    }
