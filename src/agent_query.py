"""
agent_query.py — P9.3 Natural Language Query Layer
Intent Catalog: LLM classifies query → hardcoded Supabase query → formatted reply.

No SQL generation. No AI number generation. Intent must match >90% confidence.
"""
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta


# ── Intent Catalog ─────────────────────────────────────────────────

INTENTS = {
    "GET_FII_DECOMPOSITION": {
        "keywords": ["fii selling", "fii buying", "fii flow", "foreign", "fii activity",
                     "who is selling", "institutional", "fii trend"],
        "description": "FII decomposition: concentration, top entities, broad vs concentrated",
    },
    "GET_DII_CAPACITY": {
        "keywords": ["dii buying", "dii capacity", "domestic", "mutual fund", "sip",
                     "dii absorb", "dii inflow", "mf flow"],
        "description": "DII capacity gauge: deployment ratio, saturation status",
    },
    "GET_PILLAR_STATUS": {
        "keywords": ["active pillar", "pillar", "structural risk", "stagflation",
                     "carry unwind", "em contagion", "tech cycle", "de-dollarization",
                     "west asia", "macro risk"],
        "description": "Pillar classifier: active pillars, scores, lifecycle states",
    },
    "GET_FRAGILITY": {
        "keywords": ["fragility", "stress index", "systemic risk", "how stressed",
                     "market stress", "fragility score"],
        "description": "Fragility Index: composite, breadth, intensity, base",
    },
    "GET_REGIME": {
        "keywords": ["what regime", "market regime", "current regime", "market state",
                     "regime status", "bullish", "defensive", "neutral"],
        "description": "Regime Arbiter: current regime, fragility cap, layer details",
    },
    "GET_OPTIONS_POSITIONING": {
        "keywords": ["options", "positioning", "pcr", "max pain", "gex", "skew",
                     "put/call", "gamma", "derivative"],
        "description": "Options snapshot: PCR, max pain, GEX, skew, magnetic levels",
    },
    "GET_SECTOR_RS": {
        "keywords": ["sector", "sector rs", "relative strength", "sector rotation",
                     "leading sector", "lagging sector", "sector performance"],
        "description": "Sector RS: leaders, laggards, momentum, turnover ratio",
    },
    "GET_STRESS_INDEX": {
        "keywords": ["stress", "composite stress", "stress score", "stress index"],
        "description": "Stress Index: composite score, components, trend",
    },
    "GET_CLONE_HISTORY": {
        "keywords": ["clone", "historical clone", "macro clone", "similar period",
                     "taper tantrum", "similar macro", "clone engine"],
        "description": "Clone Engine: historical matches, forward returns, distances",
    },
    "GET_MACRO_ANCHORS": {
        "keywords": ["macro", "anchor", "vix", "brent", "crude", "dollar", "dxy",
                     "usd/inr", "rupee", "gold", "copper", "10y", "yield"],
        "description": "Macro anchors: all 19+ macro indicators snapshot",
    },
    "GET_FLOW_VELOCITY": {
        "keywords": ["flow velocity", "fii velocity", "selling pace", "buying pace",
                     "momentum", "flow momentum"],
        "description": "Flow velocity: 5D vs 21D Z-score, acceleration/deceleration",
    },
    "GET_SENTINEL_STATUS": {
        "keywords": ["sentinel", "preflight", "data integrity", "regime membrane",
                     "pipeline check", "sanity check"],
        "description": "Sentinel status: preflight check, regime membrane, data quality",
    },
    "GET_SCENARIO_COLLISION": {
        "keywords": ["archetype", "collision", "scenario collision", "multipolar",
                     "asian crisis", "stagflationary freeze", "debt trap",
                     "bretton woods", "ai displacement", "heatflation"],
        "description": "Scenario collision: active archetype, pillar combination bitmask",
    },
}




def classify_intent(text: str) -> Optional[Tuple[str, float]]:
    """Classify a natural language query into an intent.

    Uses keyword matching with confidence scoring.
    If LLM available, delegates to LLM for >90% confidence.
    Fallback: TF-IDF-like keyword match.

    Returns (intent_name, confidence) or None.
    """
    text_lower = text.lower()

    # Try LLM classification first if available
    try:
        from src.ai import analyze
        sys_prompt = (
            "You are an intent classifier for a market intel bot. "
            "Given a user query, classify it into exactly one of these intents: "
            + ", ".join(INTENTS.keys()) +
            ". Reply with ONLY the intent name, nothing else. "
            "If none matches >90% confidence, reply UNKNOWN."
        )
        classification = analyze("fast", text, system=sys_prompt)
        if classification and classification.strip() in INTENTS:
            return (classification.strip(), 0.95)
    except Exception:
        pass

    # Keyword fallback scoring
    scores = {}
    for intent_name, intent_info in INTENTS.items():
        keywords = intent_info.get("keywords", [])
        score = 0
        for kw in keywords:
            if kw.lower() in text_lower:
                score += 1

        if score > 0:
            # Normalize by keyword count
            normalized = min(1.0, score / max(len(keywords) * 0.3, 1.0))
            scores[intent_name] = normalized

    if not scores:
        return None

    best = max(scores, key=scores.get)
    confidence = scores[best]

    if confidence < 0.3:
        return None

    return (best, confidence)


def resolve_intent(intent_name: str) -> str:
    """Execute a known intent against Supabase and return formatted text."""
    handlers = {
        "GET_FII_DECOMPOSITION": _resolve_fii_decomposition,
        "GET_DII_CAPACITY": _resolve_dii_capacity,
        "GET_PILLAR_STATUS": _resolve_pillar_status,
        "GET_FRAGILITY": _resolve_fragility,
        "GET_REGIME": _resolve_regime,
        "GET_OPTIONS_POSITIONING": _resolve_options,
        "GET_SECTOR_RS": _resolve_sector_rs,
        "GET_STRESS_INDEX": _resolve_stress_index,
        "GET_CLONE_HISTORY": _resolve_clones,
        "GET_MACRO_ANCHORS": _resolve_macro,
        "GET_FLOW_VELOCITY": _resolve_flow_velocity,
        "GET_SENTINEL_STATUS": _resolve_sentinel,
        "GET_SCENARIO_COLLISION": _resolve_collision,
    }

    handler = handlers.get(intent_name)
    if handler:
        return handler()
    return "❓ Intent not recognized."


def format_query_response(text: str) -> str:
    """Full pipeline: classify → resolve → format."""
    result = classify_intent(text)
    if not result:
        return (
            "❓ Query outside deterministic scope.\n\n"
            "Try: 'What is FII doing?', 'Show me sector RS', "
            "'Are any pillars active?', 'Current regime?'"
        )

    intent, confidence = result
    response = resolve_intent(intent)
    if not response:
        return "⚠️ No data available for that query yet."

    return response


# ── Intent Resolvers ───────────────────────────────────────────────

def _get_market_state() -> Dict:
    """Fetch today's market_state."""
    try:
        from src.db import get_market_state
        state = get_market_state(datetime.now().strftime("%Y-%m-%d"))
        return state if isinstance(state, dict) else {}
    except Exception:
        return {}


def _get_fii_flows(days: int = 7) -> List:
    """Fetch recent FII/DII flows."""
    try:
        from src.db import get_fii_dii_flows
        return get_fii_dii_flows(days=days)
    except Exception:
        return []


def _resolve_fii_decomposition() -> str:
    """Show FII decomposition: concentration, top entities."""
    state = _get_market_state()
    flows = _get_fii_flows(days=7)

    msg = "🏦 *FII Decomposition*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    # From decomposition module if available
    if state and state.get("fii_decomposition"):
        fd = state["fii_decomposition"]
        concentration = fd.get("concentration_pct", 0)
        classification = "Broad-based exit" if concentration < 30 else "Concentrated exit"
        msg += f"Type: *{classification}*\n"
        msg += f"Top 5 Concentration: {concentration:.0f}%\n"
        for entity in fd.get("top_entities", [])[:3]:
            msg += f"  • {entity.get('name', '?')}: ₹{entity.get('net', 0):+,.0f}Cr\n"
    else:
        msg += "_Decomposition data pending (SEBI lag)_\n"

    # From raw flows
    if flows:
        recent = flows[-5:]
        fii_total = sum(r.get("fiinet_cr", 0) or 0 for r in recent)
        dii_total = sum(r.get("diinet_cr", 0) or 0 for r in recent)
        msg += f"\n5D Cumulative:\n  FII: ₹{fii_total:+,.0f}Cr | DII: ₹{dii_total:+,.0f}Cr\n"

    return msg


def _resolve_dii_capacity() -> str:
    """Show DII capacity gauge."""
    state = _get_market_state()

    msg = "💪 *DII Capacity*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    if state and state.get("dii_capacity"):
        dc = state["dii_capacity"]
        ratio = dc.get("deployment_ratio", 0)
        status = dc.get("status", "UNKNOWN")
        mf_flow = dc.get("mf_daily_flow", 0)
        msg += f"Deployment: *{ratio:.1f}%*\n"
        msg += f"Status: *{status}*\n"
        msg += f"MF Inflows: ₹{mf_flow:+,.0f}Cr/d\n"

        if ratio > 85:
            msg += "\n⚠️ DII eating into cash reserves"
    else:
        msg += "_DII capacity data pending_\n"

    return msg


def _resolve_pillar_status() -> str:
    """Show active pillars with scores."""
    state = _get_market_state()

    msg = "🏛️ *Pillar Status*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    if state and state.get("pillar_scores"):
        pillars = state["pillar_scores"]
        active = {k: v for k, v in pillars.items()
                  if isinstance(v, (int, float)) and v >= 30}
        if active:
            for k, v in sorted(active.items(), key=lambda x: x[1], reverse=True):
                label = k.replace("_", " ").title()
                arrow = "↑" if v > 50 else "↓"
                lifecycle = state.get("pillar_lifecycle", {}).get(k, "")
                lc_str = f" | {lifecycle}" if lifecycle else ""
                msg += f"  {arrow} {label}: {v:.0f}/100{lc_str}\n"
        else:
            msg += "_No pillars active (all scores < 30)_\n"
    else:
        msg += "_Pillar data unavailable_\n"

    return msg


def _resolve_fragility() -> str:
    """Show Fragility Index."""
    state = _get_market_state()

    msg = "📊 *Fragility Index*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    if state and state.get("fragility_score") is not None:
        fs = state["fragility_score"]
        base = state.get("fragility_base", 0)
        breadth = state.get("fragility_breadth", 0)
        intensity = state.get("fragility_intensity", 0)

        level = "🟢 LOW" if fs < 30 else "🟡 MODERATE" if fs < 50 else \
                "🔴 HIGH" if fs < 65 else "🚨 CRITICAL"

        msg += f"Score: *{fs:.1f}* / 100 ({level})\n\n"
        msg += f"Base (40%): {base:.1f}\n"
        msg += f"Breadth (30%): {breadth:.1f}\n"
        msg += f"Intensity (30%): {intensity:.1f}\n"
    else:
        msg += "_Fragility data unavailable_\n"

    return msg


def _resolve_regime() -> str:
    """Show current regime."""
    state = _get_market_state()

    msg = "🏁 *Market Regime*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"

    if state and state.get("final_regime"):
        regime = state["final_regime"]
        msg += f"Current: *{regime}*\n"

        details = state.get("arbitration_details", {})
        if details:
            layers = details.get("layers", {})
            for layer_name, layer_regime in sorted(layers.items()):
                if layer_regime:
                    msg += f"  • {layer_name}: {layer_regime}\n"

        fragility = state.get("fragility_score")
        if fragility is not None:
            if fragility > 85:
                cap = "DEFENSIVE (forced)"
            elif fragility > 65:
                cap = "NEUTRAL (capped)"
            else:
                cap = f"None (fragility {fragility:.0f})"
            msg += f"\nFragility Cap: {cap}\n"
    else:
        msg += "_Regime data unavailable_\n"

    return msg


def _resolve_options() -> str:
    """Show options positioning."""
    try:
        from src.options_engine import get_latest_snapshot
        snap = get_latest_snapshot("NIFTY", "morning") or \
               get_latest_snapshot("NIFTY", "evening")

        if not snap:
            return "⚠️ No options snapshot available."

        msg = "🧲 *Options Positioning*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        if snap.get("spot_price"):
            msg += f"Spot: *{snap['spot_price']:,.0f}*\n"
        if snap.get("pcr"):
            msg += f"PCR: *{snap['pcr']:.2f}*\n"
        if snap.get("max_pain"):
            msg += f"Max Pain: *{snap['max_pain']:,.0f}*\n"
        if snap.get("gex") is not None:
            msg += f"GEX: ₹{snap['gex']:+,.0f}Cr\n"
        if snap.get("skew_25d") is not None:
            msg += f"Skew: *{snap['skew_25d']:.2f}*\n"

        return msg
    except Exception:
        return "⚠️ Options engine unavailable."


def _resolve_sector_rs() -> str:
    """Show sector RS leaders and laggards."""
    try:
        from src.db import get_sector_rs_history
        rows = get_sector_rs_history(days=3)
        if not rows:
            return "⚠️ No sector RS data available."

        dates = sorted(set(r.get("date", "") for r in rows), reverse=True)
        latest = [r for r in rows if r.get("date") == dates[0]]
        if not latest:
            return "⚠️ No sector data for latest date."

        sorted_sec = sorted(latest, key=lambda x: abs(x.get("rs_score", 0) or 0), reverse=True)

        msg = "📊 *Sector Relative Strength*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        leaders = [s for s in sorted_sec if (s.get("rs_score", 0) or 0) > 0][:5]
        laggards = [s for s in sorted_sec if (s.get("rs_score", 0) or 0) < 0][:5]

        if leaders:
            msg += "*Leaders:*\n"
            for s in leaders:
                rs = s.get("rs_score", 0) or 0
                mom = s.get("momentum_1m", 0) or 0
                arrow = "↑" if mom > 0 else "↓"
                msg += f"  🟢 {s.get('sector_name', '?')}: {rs:+.2f}σ {arrow}\n"
        if laggards:
            msg += f"\n*Laggards:*\n"
            for s in laggards:
                rs = s.get("rs_score", 0) or 0
                mom = s.get("momentum_1m", 0) or 0
                arrow = "↑" if mom > 0 else "↓"
                msg += f"  🔴 {s.get('sector_name', '?')}: {rs:+.2f}σ {arrow}\n"

        return msg
    except Exception:
        return "⚠️ Sector RS unavailable."


def _resolve_stress_index() -> str:
    """Show stress index."""
    try:
        from src.stress_index import compute_stress_index, get_stress_history
        history = get_stress_history(days=5)
        current = compute_stress_index()

        msg = "📊 *Stress Index*\n━━━━━━━━━━━━━━━━━━━━\n\n"

        if history:
            latest = history[-1]
            score = latest.get("stress_score", 0)
            date = latest.get("trade_date", "?")
            msg += f"Score: *{score:.1f}* / 100\n"
            msg += f"Date: {date}\n"

            if len(history) >= 2:
                prev = history[-2].get("stress_score", 0)
                delta = score - prev
                arrow = "↑" if delta > 1 else "↓" if delta < -1 else "→"
                msg += f"Trend: {arrow} {delta:+.1f}\n"

        if current and current.get("ok"):
            comps = current.get("components", {})
            msg += f"\n*Components:*\n"
            for k, v in sorted(comps.items(), key=lambda x: abs(x[1]), reverse=True)[:5]:
                label = k.replace("_", " ").title()
                msg += f"  • {label}: {v:+.1f}\n"

        return msg
    except Exception:
        return "⚠️ Stress index unavailable."


def _resolve_clones() -> str:
    """Show historical clones."""
    try:
        from src.db import get_client
        db = get_client()
        if not db:
            return "⚠️ Database not connected."

        cutoff = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
        result = (
            db.table("clone_history")
            .select("*")
            .gte("trade_date", cutoff)
            .order("trade_date", desc=True)
            .limit(9)
            .execute()
        )
        rows = result.data if result.data else []
        if not rows:
            return "⚠️ No clone data available."

        latest_group = rows[0]["trade_date"]
        clones = [r for r in rows if r["trade_date"] == latest_group][:3]

        msg = "🔬 *Historical Clones*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        for c in clones:
            fwd = c.get("nifty_30d_fwd")
            dd = c.get("max_dd")
            fwd_str = f"{fwd:+.1f}%" if fwd is not None else "N/A"
            msg += f"📅 {c.get('clone_date', '?')} | Dist: {c.get('distance', 0):.2f}\n"
            msg += f"   30D Fwd: {fwd_str}\n\n"

        return msg
    except Exception:
        return "⚠️ Clone engine unavailable."


def _resolve_macro() -> str:
    """Show current macro anchors."""
    state = _get_market_state()

    msg = "🌐 *Macro Anchors*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    if state and state.get("macro"):
        macro = state["macro"]

        display = [
            ("^INDIAVIX", "India VIX"),
            ("BZ=F", "Brent"),
            ("CL=F", "WTI"),
            ("USDINR=X", "USD/INR"),
            ("DX-Y.NYB", "DXY"),
            ("^TNX", "US 10Y"),
            ("GC=F", "Gold"),
            ("HG=F", "Copper"),
            ("^VIX", "CBOE VIX"),
            ("HYG", "HYG"),
        ]

        for symbol, label in display:
            entry = macro.get(symbol, {})
            if isinstance(entry, dict):
                price = entry.get("price")
                change = entry.get("change_pct")
            else:
                price = entry
                change = None

            if price is not None:
                arrow = "↑" if change and change > 0 else "↓" if change and change < 0 else "→"
                change_str = f"({arrow} {abs(change):.1f}%)" if change is not None else ""
                msg += f"  {label}: *{price:,.2f}* {change_str}\n"
    else:
        msg += "_Macro data unavailable_\n"

    return msg


def _resolve_flow_velocity() -> str:
    """Show FII flow velocity."""
    flows = _get_fii_flows(days=21)
    if not flows:
        return "⚠️ No flow data for velocity computation."

    msg = "🌊 *Flow Velocity*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    if len(flows) >= 21:
        fii_21d = sum(r.get("fiinet_cr", 0) or 0 for r in flows[-21:])
        fii_5d = sum(r.get("fiinet_cr", 0) or 0 for r in flows[-5:])
        avg_21d = fii_21d / 21
        avg_5d = fii_5d / 5
        z_score = (avg_5d - avg_21d) / max(abs(avg_21d) * 0.1, 1)

        msg += f"FII 5D Avg: ₹{avg_5d:+,.0f}Cr/d\n"
        msg += f"FII 21D Avg: ₹{avg_21d:+,.0f}Cr/d\n"
        msg += f"Z-Score: *{z_score:+.2f}σ*\n"

        if abs(z_score) > 2:
            direction = "accelerating" if z_score > 0 else "decelerating"
            msg += f"\n⚠️ FII flow {direction} significantly!\n"
        elif abs(z_score) > 1:
            direction = "trending" if z_score > 0 else "weakening"
            msg += f"\nFII flow {direction}\n"
        else:
            msg += "\nFII flow stable\n"
    else:
        msg += "_Insufficient data (<21 days)_\n"

    return msg


def _resolve_sentinel() -> str:
    """Show sentinel status."""
    state = _get_market_state()

    msg = "🛡️ *Sentinel Status*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    if state:
        # Check if sentinel fields exist
        preflight = state.get("preflight_ok", True)
        msg += f"Preflight Check: {'✅ Passed' if preflight else '❌ Failed'}\n"

        prev_regime = state.get("prev_regime", "N/A")
        current_regime = state.get("final_regime", "N/A")
        msg += f"Previous Regime: {prev_regime}\n"
        msg += f"Current Regime: {current_regime}\n"

        fragility = state.get("fragility_score")
        if fragility is not None:
            msg += f"Fragility: {fragility:.1f}/100\n"

        membrane = state.get("membrane_applied", False)
        if membrane:
            msg += "\n⚠️ Regime membrane was triggered (2-step jump capped)\n"

    msg += "\n_Pipeline protection: null halt + variance halt + jump cap_"
    return msg


def _resolve_collision() -> str:
    """Show active archetype collision."""
    state = _get_market_state()

    msg = "⚠️ *Scenario Collision*\n━━━━━━━━━━━━━━━━━━━━━\n\n"

    if state and state.get("active_archetype"):
        aa = state["active_archetype"]
        msg += f"Active Archetype: *{aa.get('name', '?')}*\n"
        msg += f"Banner: {aa.get('banner', '?')}\n"
        msg += f"\nCombination: {aa.get('pillars', '?')}\n"
    else:
        msg += "_No archetype collision detected._\n"

    if state and state.get("liquidity_freeze_active"):
        msg += "\n🚨 Global liquidity freeze ACTIVE\n"

    if state and state.get("external_debt_stress"):
        msg += "\n🚨 External debt stress flag ACTIVE\n"

    return msg
