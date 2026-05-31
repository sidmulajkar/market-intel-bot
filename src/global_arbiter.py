"""
Global Regime Arbiter — 4-state classification from macro data.
Derives global risk regime from already-fetched macro anchors.
Zero AI, zero live API calls — pure threshold logic.

Hierarchy Rule (applied by regime_arbiter.py):
  - STAGFLATION or LIQUIDITY_DRAWDOWN → Force India to DEFENSIVE
  - RISK_OFF → Cap India at NEUTRAL (ban BULL)
  - RISK_ON → Allow full India regime range
"""

from typing import Dict, List, Optional


# ── Thresholds (calibrated for backtest 2020-2026) ────────────────
VIX_RISK_ON_THRESHOLD = 15      # VIX < 15 → risk-on
VIX_RISK_OFF_THRESHOLD = 20     # VIX > 20 → risk-off

DXY_STRONG = 104                 # DXY > 104 → strong dollar (EM stress)
DXY_WEAK = 96                    # DXY < 96 → weak dollar (EM tailwind)

HYG_STRESS_PRICE = 75           # HYG < 75 → junk bond stress
LQD_STRESS_PRICE = 100          # LQD < 100 → IG stress

CU_AU_BEAR_THRESHOLD = 0.0010   # Cu/Au below this → growth concern (normalized)
CU_AU_BULL_THRESHOLD = 0.0018   # Cu/Au above this → reflation

BRENT_STAGFLATION = 85          # Brent > 85 → stagflation input
GOLD_STAGFLATION = 2500         # Gold > 2500 → stagflation input (real rates falling)

US10Y_LIQUIDITY_STRESS = 4.25   # US 10Y > 4.25% + DXY > 104 → liquidity drain (calibrated: captures 2022 Fed)
US10Y_LIQUIDITY_ELEVATED = 4.0  # US 10Y > 4.0% → elevated


def _safe_float(val, default=0.0) -> float:
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def _find_anchor(anchors: List[Dict], name: str) -> Optional[Dict]:
    """Find a macro anchor by name."""
    for a in anchors:
        if a.get("name") == name or a.get("symbol") == name:
            return a
    return None


def _get_price(anchor: Optional[Dict]) -> Optional[float]:
    """Get price from anchor dict, respecting status."""
    if anchor and anchor.get("ok") and anchor.get("price") is not None:
        return _safe_float(anchor.get("price"))
    return None


def _get_change_pct(anchor: Optional[Dict]) -> Optional[float]:
    """Get daily change from anchor."""
    if anchor and anchor.get("change_pct") is not None:
        return _safe_float(anchor.get("change_pct"))
    return None


def _is_rising(anchor: Optional[Dict]) -> Optional[bool]:
    """Check if price is rising (positive change)."""
    chg = _get_change_pct(anchor)
    if chg is not None:
        return chg > 0.5
    return None


def _is_falling(anchor: Optional[Dict]) -> Optional[bool]:
    """Check if price is falling (negative change)."""
    chg = _get_change_pct(anchor)
    if chg is not None:
        return chg < -0.3
    return None


def compute_global_regime(macro_anchors: List[Dict]) -> Dict:
    """
    Compute global regime from macro anchors data.

    Returns:
        regime: str — one of GLOBAL_RISK_ON, GLOBAL_RISK_OFF,
                       GLOBAL_STAGFLATION, GLOBAL_LIQUIDITY_DRAWDOWN, GLOBAL_NEUTRAL
        label: str — human-readable label
        signals: list — contributing signals
    """
    if not macro_anchors:
        return {"regime": "GLOBAL_NEUTRAL", "label": "Neutral (no data)", "signals": []}

    # Extract key data
    dxy = _find_anchor(macro_anchors, "Dollar Index")
    vix = _find_anchor(macro_anchors, "CBOE VIX")
    hy_g = _find_anchor(macro_anchors, "US High Yield")
    lqd = _find_anchor(macro_anchors, "IG Corp Bonds")
    copper = _find_anchor(macro_anchors, "Copper")
    gold = _find_anchor(macro_anchors, "Gold")
    brent = _find_anchor(macro_anchors, "Brent Crude")
    us10y = _find_anchor(macro_anchors, "US 10Y Yield")
    usd_jpy = _find_anchor(macro_anchors, "USD/JPY")
    nq = _find_anchor(macro_anchors, "Nasdaq Futures")
    es = _find_anchor(macro_anchors, "S&P 500 Futures")

    dxy_price = _get_price(dxy)
    vix_price = _get_price(vix)
    hy_price = _get_price(hy_g)
    lqd_price = _get_price(lqd)
    cu_price = _get_price(copper)
    au_price = _get_price(gold)
    brent_price = _get_price(brent)
    us10y_price = _get_price(us10y)
    jpy_price = _get_price(usd_jpy)
    nq_price = _get_price(nq)
    es_price = _get_price(es)

    dxy_rising = _is_rising(dxy)
    dxy_falling = _is_falling(dxy)

    signals = []

    # ── Check Stagflation ──────────────────────────────────────────
    stagflation_signals = 0
    if brent_price is not None and brent_price >= BRENT_STAGFLATION:
        stagflation_signals += 1
        signals.append(f"Brent ${brent_price:.0f} (stagflation threshold)")
    if au_price is not None and au_price >= GOLD_STAGFLATION:
        stagflation_signals += 1
        signals.append(f"Gold ${au_price:.0f} (safe haven bid)")
    if cu_price is not None:
        cu_chg = _get_change_pct(copper)
        if cu_chg is not None and cu_chg < -0.5:
            stagflation_signals += 1
            signals.append(f"Copper {cu_chg:+.1f}% (growth concern)")

    if stagflation_signals >= 2:
        if dxy_rising:
            signals.append("DXY rising (confirms stagflation)")
            return {
                "regime": "GLOBAL_STAGFLATION",
                "label": "Stagflation — commodities up, growth down",
                "signals": signals,
            }

    # ── Check Liquidity Drawdown ──────────────────────────────────
    if dxy_price is not None and us10y_price is not None:
        if dxy_price >= DXY_STRONG and us10y_price >= US10Y_LIQUIDITY_STRESS:
            signals.append(f"DXY {dxy_price:.1f} + US10Y {us10y_price:.2f}%")
            return {
                "regime": "GLOBAL_LIQUIDITY_DRAWDOWN",
                "label": "Liquidity drawdown — USD strength + rising yields",
                "signals": signals,
            }
        if dxy_price >= DXY_STRONG and us10y_price >= US10Y_LIQUIDITY_ELEVATED:
            signals.append(f"DXY {dxy_price:.1f} + US10Y {us10y_price:.2f}% (elevated)")
            # Not strong enough alone — needs another signal
            pass

    # ── Check Risk-Off ────────────────────────────────────────────
    risk_off_signals = 0
    if dxy_price is not None and dxy_price >= DXY_STRONG:
        risk_off_signals += 1
        signals.append(f"DXY {dxy_price:.1f} (strong dollar — EM stress)")
    if vix_price is not None and vix_price >= VIX_RISK_OFF_THRESHOLD:
        risk_off_signals += 1
        signals.append(f"VIX {vix_price:.1f} (elevated fear)")
    if hy_price is not None and hy_price <= HYG_STRESS_PRICE:
        risk_off_signals += 1
        signals.append(f"HYG ${hy_price:.1f} (credit stress)")
    if lqd_price is not None and lqd_price <= LQD_STRESS_PRICE:
        risk_off_signals += 1
        signals.append(f"LQD ${lqd_price:.1f} (IG credit stress)")
    if jpy_price is not None and jpy_price < 140:
        risk_off_signals += 1
        signals.append(f"USD/JPY {jpy_price:.0f} (carry unwind)")
    if nq_price is not None and es_price is not None:
        nq_chg = _get_change_pct(nq)
        es_chg = _get_change_pct(es)
        if nq_chg is not None and es_chg is not None:
            if nq_chg < -1.0 and es_chg < -1.0:
                risk_off_signals += 1
                signals.append(f"US futures negative (ES {es_chg:+.1f}%, NQ {nq_chg:+.1f}%)")

    if risk_off_signals >= 2:
        return {
            "regime": "GLOBAL_RISK_OFF",
            "label": "Risk-off — elevated fear, broad EM stress",
            "signals": signals,
        }

    # ── Check Risk-On ────────────────────────────────────────────
    risk_on_signals = 0
    if dxy_price is not None and dxy_price <= DXY_WEAK:
        risk_on_signals += 1
        signals.append(f"DXY {dxy_price:.1f} (weak dollar — EM tailwind)")
    if vix_price is not None and vix_price < VIX_RISK_ON_THRESHOLD:
        risk_on_signals += 1
        signals.append(f"VIX {vix_price:.1f} (low fear)")
    if hy_price is not None and hy_price > 90:
        risk_on_signals += 1
        signals.append(f"HYG ${hy_price:.1f} (credit healthy)")
    if lqd_price is not None and lqd_price > 108:
        risk_on_signals += 1
        signals.append(f"LQD ${lqd_price:.1f} (IG firm)")
    if cu_price is not None and au_price is not None and au_price > 0:
        cu_au = cu_price / au_price
        if cu_au >= CU_AU_BULL_THRESHOLD:
            risk_on_signals += 1
            signals.append(f"Cu/Au {cu_au:.4f} (reflation signal)")
    if nq_price is not None and es_price is not None:
        nq_chg = _get_change_pct(nq)
        es_chg = _get_change_pct(es)
        if nq_chg is not None and es_chg is not None:
            if nq_chg > 0.5 and es_chg > 0.5:
                risk_on_signals += 1
                signals.append(f"US futures positive (ES {es_chg:+.1f}%, NQ {nq_chg:+.1f}%)")

    if risk_on_signals >= 2:
        return {
            "regime": "GLOBAL_RISK_ON",
            "label": "Risk-on — weak dollar, low fear, growth supportive",
            "signals": signals,
        }

    return {
        "regime": "GLOBAL_NEUTRAL",
        "label": "Neutral — no dominant global regime",
        "signals": signals,
    }


def format_global_regime(result: Dict) -> str:
    """Format global regime for Telegram output."""
    regime = result.get("regime", "GLOBAL_NEUTRAL")

    emoji_map = {
        "GLOBAL_RISK_ON": "🟢",
        "GLOBAL_RISK_OFF": "🔴",
        "GLOBAL_STAGFLATION": "⚠️",
        "GLOBAL_LIQUIDITY_DRAWDOWN": "🚨",
        "GLOBAL_NEUTRAL": "⚪",
    }
    emoji = emoji_map.get(regime, "⚪")

    label = result.get("label", "Neutral")
    signals = result.get("signals", [])

    line = f"{emoji} Global: {label}"
    if signals:
        line += " | " + " | ".join(signals[:3])

    return line
