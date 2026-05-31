"""
Pipeline Adapters — wrap existing modules as DAG nodes (MarketState -> MarketState).

Each adapter function takes a MarketState, fetches/computes data using existing modules,
updates the appropriate sub-model, and returns the updated state.
"""
from __future__ import annotations

from src.state import MarketState
from src.pipeline import register_function


# ── Data Fetch Nodes ─────────────────────────────────────────────────────────

def fetch_macro(state: MarketState) -> MarketState:
    """Fetch 9 macro anchors and populate state.macro."""
    from src.data_fetcher import fetch_macro_anchors
    anchors = fetch_macro_anchors()
    if not anchors:
        state.missing_sources.append("macro_anchors")
        return state

    macro_data = {}
    for a in anchors:
        symbol = a.get("symbol", "")
        if a.get("ok") and a.get("price") is not None:
            name_map = {
                "^INDIAVIX": ("vix", "vix_change_pct"),
                "USDINR=X": ("usdinr", "usdinr_change_pct"),
                "BZ=F": ("brent", "brent_change_pct"),
                "GC=F": ("gold", "gold_change_pct"),
                "DX-Y.NYB": ("dxy", "dxy_change_pct"),
                "^TNX": ("us_10y", "us_10y_change_pct"),
                "^VIX": ("cboe_vix", "cboe_vix_change_pct"),
                "HYG": ("hyg", None),
                "CL=F": ("wti", None),
                "HG=F": ("copper", None),
                "LQD": ("lqd", None),
                "SOXX": ("soxx", None),
                "JPY=X": ("usd_jpy", None),
                "ES=F": ("es", None),
                "NQ=F": ("nq", None),
            }
            if symbol in name_map:
                field, change_field = name_map[symbol]
                macro_data[field] = a["price"]
                if change_field and a.get("change_pct") is not None:
                    macro_data[change_field] = a["change_pct"]

    state.macro.vix = macro_data.get("vix")
    state.macro.usdinr = macro_data.get("usdinr")
    state.macro.brent = macro_data.get("brent")
    state.macro.gold = macro_data.get("gold")
    state.macro.dxy = macro_data.get("dxy")
    state.macro.us_10y = macro_data.get("us_10y")
    state.macro.cboe_vix = macro_data.get("cboe_vix")
    state.macro.hyg = macro_data.get("hyg")
    state.macro.lqd = macro_data.get("lqd")
    state.macro.soxx = macro_data.get("soxx")
    state.macro.wti = macro_data.get("wti")
    state.macro.copper = macro_data.get("copper")
    state.macro.usd_jpy = macro_data.get("usd_jpy")
    state.macro.es = macro_data.get("es")
    state.macro.nq = macro_data.get("nq")
    state.macro.vix_change_pct = macro_data.get("vix_change_pct")
    state.macro.usdinr_change_pct = macro_data.get("usdinr_change_pct")
    state.macro.brent_change_pct = macro_data.get("brent_change_pct")
    state.macro.gold_change_pct = macro_data.get("gold_change_pct")
    state.macro.dxy_change_pct = macro_data.get("dxy_change_pct")
    state.macro.us_10y_change_pct = macro_data.get("us_10y_change_pct")
    state.macro.cboe_vix_change_pct = macro_data.get("cboe_vix_change_pct")

    # Store raw anchors for downstream modules that need them
    state.raw["macro_anchors"] = anchors
    return state


def fetch_flows(state: MarketState) -> MarketState:
    """Fetch FII/DII flows and populate state.flows."""
    from src.context_engine import get_fii_dii_context
    ctx = get_fii_dii_context(days=5)
    if not ctx.get("ok"):
        state.missing_sources.append("fii_dii_flows")
        # Still return state — compute_bull_bear_score handles empty ctx
        return state

    state.flows.fii_net = ctx.get("fii_net")
    state.flows.dii_net = ctx.get("dii_net")
    state.flows.fii_streak_days = ctx.get("fii_streak", 0)
    state.flows.fii_mood = "BUY" if (ctx.get("fii_net", 0) or 0) > 0 else "SELL"

    # Compute absorption ratio
    fii = ctx.get("fii_net", 0) or 0
    dii = ctx.get("dii_net", 0) or 0
    if fii < 0 and dii > 0:
        state.flows.absorption_ratio = round(dii / abs(fii), 2)

    # Store full FII context dict for downstream bull_bear computation
    state.raw["fii_context"] = ctx
    return state


def fetch_market_breadth(state: MarketState) -> MarketState:
    """Fetch market breadth (A/D) and populate feature vector."""
    from src.data_fetcher import fetch_market_breadth
    breadth = fetch_market_breadth()
    if not breadth:
        return state

    adv = breadth.get("advances", 0)
    dec = breadth.get("declines", 0)
    if dec > 0:
        ratio = adv / dec
        # Normalize to -1..1 range (ratio of 1 = 0, ratio of 2 = 0.33, ratio of 0.5 = -0.33)
        normalized = (ratio - 1) / (ratio + 1)
        state.features.breadth_score = round(normalized, 3)

    state.raw["breadth"] = breadth
    return state


# ── Computation Nodes ────────────────────────────────────────────────────────

def compute_vix_regime(state: MarketState) -> MarketState:
    """Compute VIX regime from context engine."""
    from src.context_engine import get_vix_regime
    regime = get_vix_regime(vix_price=state.macro.vix)
    state.macro.vix_regime = regime
    return state


def compute_dxy_signal(state: MarketState) -> MarketState:
    """Compute DXY directional signal."""
    from src.context_engine import get_dxy_signal
    dxy_data = get_dxy_signal(dxy_change_pct=state.macro.dxy_change_pct or 0.0)
    state.macro.dxy_signal = dxy_data.get("signal")
    return state


def compute_bull_bear(state: MarketState) -> MarketState:
    """Compute Bull/Bear score and market context."""
    from src.context_engine import compute_bull_bear_score

    # Use full FII context from fetch_flows (contains streak, z-score, etc.)
    fii_ctx = state.raw.get("fii_context", {})

    # Build macro context in the format compute_bull_bear_score expects
    # (nested dicts, not flat floats — matches what format_context_block produces)
    macro_ctx = {}

    # VIX regime
    vix_regime = state.macro.vix_regime or "UNKNOWN"
    macro_ctx["vix_regime"] = vix_regime
    macro_ctx["vix_price"] = state.macro.vix

    # DXY signal (nested dict)
    dxy_change = state.macro.dxy_change_pct or 0.0
    if dxy_change > 0.5:
        dxy_direction = "RISING"
    elif dxy_change < -0.5:
        dxy_direction = "FALLING"
    else:
        dxy_direction = "FLAT"
    macro_ctx["dxy"] = {"direction": dxy_direction, "change_pct": dxy_change}

    # Other macro values
    macro_ctx["usdinr"] = state.macro.usdinr
    macro_ctx["gold"] = state.macro.gold
    macro_ctx["brent"] = state.macro.brent
    macro_ctx["us_10y"] = state.macro.us_10y

    # Include extra signals from feature vector and derivatives
    extra = {}
    if state.features.breadth_score is not None:
        # Convert normalized breadth back to ratio approximation
        bs = state.features.breadth_score
        ratio = (1 + bs) / (1 - bs) if bs < 1 else 3.0
        extra["breadth_ratio"] = round(max(0.1, ratio), 2)
    if state.derivatives.pcr is not None:
        extra["pcr"] = state.derivatives.pcr
    if state.flows.fii_fno_net is not None:
        extra["fii_fno_net"] = state.flows.fii_fno_net

    anchors = state.raw.get("macro_anchors", [])
    bb = compute_bull_bear_score(fii_context=fii_ctx, macro_context=macro_ctx, extra_signals=extra, anchor_data=anchors)
    if bb.get("ok"):
        state.bull_bear_score = bb.get("raw_score")
        state.bull_bear_normalized = bb.get("normalized_score")
        state.bull_bear_confidence = bb.get("confidence")
        state.dominant_factor = bb.get("dominant_factor")

    # Store context dict for downstream nodes
    state.raw["context"] = bb
    return state


def compute_global_risk(state: MarketState) -> MarketState:
    """Compute global risk composite and cross-asset regime."""
    from src.context_engine import compute_global_risk_composite, run_contextualization

    anchors = state.raw.get("macro_anchors", [])
    if not anchors:
        return state

    risk = compute_global_risk_composite(anchors)
    if risk.get("ok"):
        state.add_narrative("global_risk", risk.get("formatted", ""))
        state.raw.setdefault("context", {})["global_risk"] = risk

    # Full contextualization for cross-asset regime
    ctx = run_contextualization(anchors)
    if ctx.get("cross_asset_regime", {}).get("ok"):
        state.cross_asset_regime = ctx["cross_asset_regime"].get("regime")

    return state


def compute_options(state: MarketState) -> MarketState:
    """Compute derivatives metrics (PCR, max pain, GEX, skew)."""
    from src.options_engine import (
        fetch_nse_options_chain, compute_max_pain, compute_pcr,
        compute_gex, compute_skew,
    )
    chain = fetch_nse_options_chain("NIFTY")
    if not chain:
        state.missing_sources.append("options_chain")
        return state

    spot = chain[0].get("_underlying") if chain else None
    state.derivatives.spot_price = spot

    pcr_data = compute_pcr(chain, spot)
    if pcr_data:
        state.derivatives.pcr = pcr_data.get("pcr")
        state.derivatives.pcr_signal = pcr_data.get("signal")

    mp = compute_max_pain(chain)
    if mp is not None:
        state.derivatives.max_pain = mp

    gex_data = compute_gex(chain, spot)
    if gex_data and gex_data.get("ok"):
        state.derivatives.gex = gex_data.get("net_gex_cr")

    skew_data = compute_skew(chain, spot)
    if skew_data and skew_data.get("ok"):
        state.derivatives.skew_25d = skew_data.get("skew_25d")

    state.raw["options_chain"] = chain
    return state


def compute_valuation(state: MarketState) -> MarketState:
    """Compute valuation metrics (P/E, P/B, ERP)."""
    try:
        from src.valuation_engine import get_latest_valuations
        val = get_latest_valuations()
        if val:
            state.raw["valuation"] = val
    except Exception:
        pass
    return state


def compute_market_phase(state: MarketState) -> MarketState:
    """Compute market phase from context."""
    from src.context_engine import compute_market_phase as _compute_phase
    ctx = state.raw.get("context", {})
    market_phase = _compute_phase(ctx)
    state.market_phase = market_phase.get("phase")
    return state


# ── Pipeline Registration ────────────────────────────────────────────────────

def register_all_adapters():
    """Register all pipeline adapter functions."""
    from src.pipeline import register_pipeline, register_function

    # Register individual functions
    adapters = [
        ("fetch_macro", fetch_macro),
        ("fetch_flows", fetch_flows),
        ("fetch_market_breadth", fetch_market_breadth),
        ("compute_vix_regime", compute_vix_regime),
        ("compute_dxy_signal", compute_dxy_signal),
        ("compute_bull_bear", compute_bull_bear),
        ("compute_global_risk", compute_global_risk),
        ("compute_options", compute_options),
        ("compute_valuation", compute_valuation),
        ("compute_market_phase", compute_market_phase),
    ]
    for name, fn in adapters:
        register_function(name, fn)

    # Register morning_brief pipeline
    register_pipeline("morning_brief", [
        {"name": "fetch_macro", "dependencies": [], "fn": "fetch_macro", "description": "Fetch 9 macro anchors"},
        {"name": "fetch_flows", "dependencies": ["fetch_macro"], "fn": "fetch_flows", "description": "Fetch FII/DII flows"},
        {"name": "fetch_breadth", "dependencies": [], "fn": "fetch_market_breadth", "description": "Fetch market breadth A/D"},
        {"name": "compute_vix", "dependencies": ["fetch_macro"], "fn": "compute_vix_regime", "description": "VIX regime classification"},
        {"name": "compute_dxy", "dependencies": ["fetch_macro"], "fn": "compute_dxy_signal", "description": "DXY directional signal"},
        {"name": "compute_bull_bear", "dependencies": ["fetch_flows", "compute_vix", "compute_dxy"], "fn": "compute_bull_bear", "description": "Bull/Bear 8-signal score"},
        {"name": "compute_global_risk", "dependencies": ["fetch_macro"], "fn": "compute_global_risk", "description": "Global risk composite"},
        {"name": "compute_options", "dependencies": [], "fn": "compute_options", "description": "Options chain analysis"},
        {"name": "compute_valuation", "dependencies": [], "fn": "compute_valuation", "description": "Nifty P/E, P/B, ERP"},
        {"name": "compute_phase", "dependencies": ["compute_bull_bear", "compute_global_risk"], "fn": "compute_market_phase", "description": "Market phase classifier"},
    ])

    # Register market_intel morning pipeline (lighter version)
    register_pipeline("market_intel_morning", [
        {"name": "fetch_macro", "dependencies": [], "fn": "fetch_macro"},
        {"name": "fetch_flows", "dependencies": ["fetch_macro"], "fn": "fetch_flows"},
        {"name": "fetch_breadth", "dependencies": [], "fn": "fetch_market_breadth"},
        {"name": "compute_bull_bear", "dependencies": ["fetch_flows"], "fn": "compute_bull_bear"},
        {"name": "compute_options", "dependencies": [], "fn": "compute_options"},
    ])

    # Register market_intel evening pipeline (full)
    register_pipeline("market_intel_evening", [
        {"name": "fetch_macro", "dependencies": [], "fn": "fetch_macro"},
        {"name": "fetch_flows", "dependencies": ["fetch_macro"], "fn": "fetch_flows"},
        {"name": "fetch_breadth", "dependencies": [], "fn": "fetch_market_breadth"},
        {"name": "compute_vix", "dependencies": ["fetch_macro"], "fn": "compute_vix_regime"},
        {"name": "compute_dxy", "dependencies": ["fetch_macro"], "fn": "compute_dxy_signal"},
        {"name": "compute_bull_bear", "dependencies": ["fetch_flows", "compute_vix", "compute_dxy"], "fn": "compute_bull_bear"},
        {"name": "compute_global_risk", "dependencies": ["fetch_macro"], "fn": "compute_global_risk"},
        {"name": "compute_options", "dependencies": [], "fn": "compute_options"},
        {"name": "compute_valuation", "dependencies": [], "fn": "compute_valuation"},
        {"name": "compute_phase", "dependencies": ["compute_bull_bear", "compute_global_risk"], "fn": "compute_market_phase"},
    ])
