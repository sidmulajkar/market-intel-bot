"""
Shareholding Pattern Tracker
Sources: yfinance institutional_holders + major_holders
         Supabase stores previous quarter for QoQ comparison
Tracks: Promoter %, FII %, DII %, Public % shifts
"""
import os
import json
import yfinance as yf
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
from src.db import get_client, today_str

def fetch_shareholding(symbol: str) -> Dict:
    """
    Fetch shareholding pattern for a stock using yfinance.
    Returns institutional, major holders, and computed breakdown.
    """
    try:
        t = yf.Ticker(symbol)

        # Major holders — gives % breakdown
        major = t.major_holders
        # Institutional holders — top institutions
        inst  = t.institutional_holders
        # Mutual fund holders
        mf    = t.mutualfund_holders

        breakdown = {}
        if major is not None and not major.empty:
            for _, row in major.iterrows():
                try:
                    val   = float(str(row.iloc[0]).replace("%", "").strip())
                    label = str(row.iloc[1]).strip()
                    breakdown[label] = round(val, 2)
                except Exception:
                    continue

        # Top institutional holders
        top_inst = []
        if inst is not None and not inst.empty:
            for _, row in inst.head(5).iterrows():
                try:
                    shares = int(row.get("Shares", 0))
                    val    = float(row.get("Value", 0))
                    pct    = float(row.get("% Out", 0))
                    name   = str(row.get("Holder", ""))
                    top_inst.append({
                        "holder":  name,
                        "shares":  shares,
                        "value":   val,
                        "pct_out": round(pct, 2),
                    })
                except Exception:
                    continue

        # Top mutual fund holders
        top_mf = []
        if mf is not None and not mf.empty:
            for _, row in mf.head(5).iterrows():
                try:
                    top_mf.append({
                        "holder":  str(row.get("Holder", "")),
                        "shares":  int(row.get("Shares", 0)),
                        "pct_out": round(float(row.get("% Out", 0)), 2),
                    })
                except Exception:
                    continue

        return {
            "symbol":       symbol,
            "breakdown":    breakdown,
            "institutions": top_inst,
            "mutual_funds": top_mf,
            "quarter":      _current_quarter(),
            "fetched_at":   datetime.now().isoformat(),
            "ok":           True,
        }

    except Exception as e:
        print(f"⚠️  Shareholding fetch failed for {symbol}: {e}")
        return {"symbol": symbol, "ok": False, "error": str(e)}

def _current_quarter() -> str:
    """Returns current quarter label like Q1FY26"""
    now = datetime.now()
    q   = (now.month - 1) // 3 + 1
    fy  = now.year + 1 if now.month >= 4 else now.year
    return f"Q{q}FY{str(fy)[-2:]}"

def _previous_quarter() -> str:
    """Returns previous quarter label"""
    now = datetime.now()
    q   = (now.month - 1) // 3 + 1
    fy  = now.year + 1 if now.month >= 4 else now.year
    pq  = q - 1 if q > 1 else 4
    pfy = fy if q > 1 else fy - 1
    return f"Q{pq}FY{str(pfy)[-2:]}"

def save_shareholding_snapshot(symbol: str, data: dict) -> None:
    """Save to Supabase for QoQ comparison"""
    db = get_client()
    if not db:
        return
    try:
        db.table("shareholding_snapshots").upsert({
            "symbol":  symbol,
            "quarter": data.get("quarter"),
            "data":    json.dumps(data),
            "date":    today_str(),
        }).execute()
    except Exception as e:
        print(f"⚠️  Shareholding save error: {e}")

def get_previous_snapshot(symbol: str) -> Optional[Dict]:
    """Get previous quarter snapshot for comparison"""
    db = get_client()
    if not db:
        return None
    try:
        prev_q = _previous_quarter()
        result = (
            db.table("shareholding_snapshots")
            .select("data")
            .eq("symbol",  symbol)
            .eq("quarter", prev_q)
            .limit(1)
            .execute()
        )
        if result.data:
            return json.loads(result.data[0]["data"])
    except Exception as e:
        print(f"⚠️  Previous snapshot fetch error: {e}")
    return None

def detect_significant_changes(
    current: Dict,
    previous: Dict,
    threshold: float = 2.0,   # 2% change = significant
) -> List[Dict]:
    """
    Compare current vs previous quarter shareholding.
    Returns list of significant changes detected.
    """
    changes = []
    if not current.get("ok") or not previous:
        return changes

    curr_bd = current.get("breakdown", {})
    prev_bd = previous.get("breakdown", {})

    for key in curr_bd:
        if key in prev_bd:
            curr_val = curr_bd[key]
            prev_val = prev_bd[key]
            delta    = curr_val - prev_val
            if abs(delta) >= threshold:
                changes.append({
                    "category": key,
                    "current":  curr_val,
                    "previous": prev_val,
                    "delta":    round(delta, 2),
                    "direction": "⬆️ Increased" if delta > 0 else "⬇️ Decreased",
                    "significant": abs(delta) >= 5.0,  # 5%+ = very significant
                })

    return sorted(changes, key=lambda x: abs(x["delta"]), reverse=True)

def format_shareholding_message(
    symbol: str,
    current: Dict,
    changes: List[Dict],
) -> str:
    """Format shareholding data for Telegram"""
    msg = f"📊 *SHAREHOLDING PATTERN — {symbol}*\n"
    msg += f"_{current.get('quarter', 'Current Quarter')}_\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    bd = current.get("breakdown", {})
    if bd:
        msg += "📈 *Holder Breakdown:*\n"
        for label, pct in bd.items():
            bar = "█" * int(pct // 5)
            msg += f"  {label[:35]}: *{pct:.2f}%* {bar}\n"
        msg += "\n"

    if changes:
        msg += "🔄 *QoQ Significant Changes:*\n"
        for c in changes[:5]:
            sig = "🚨" if c["significant"] else "⚠️"
            msg += (
                f"{sig} *{c['category'][:30]}*\n"
                f"   {c['direction']}: "
                f"{c['previous']:.2f}% → {c['current']:.2f}% "
                f"({c['delta']:+.2f}%)\n"
            )
        msg += "\n"

    inst = current.get("institutions", [])
    if inst:
        msg += "🏦 *Top Institutional Holders:*\n"
        for h in inst[:3]:
            msg += f"  • {h['holder'][:30]}: {h['pct_out']}%\n"

    return msg

def track_all_watchlist_shareholding(symbols: List[str]) -> List[Dict]:
    """Track shareholding for entire watchlist"""
    results = []
    for symbol in symbols:
        print(f"  📊 Shareholding: {symbol}")
        current  = fetch_shareholding(symbol)
        previous = get_previous_snapshot(symbol)
        changes  = detect_significant_changes(current, previous)

        if current.get("ok"):
            save_shareholding_snapshot(symbol, current)

        results.append({
            "symbol":  symbol,
            "current": current,
            "changes": changes,
            "has_significant_change": any(c["significant"] for c in changes),
        })
        import time
        time.sleep(1.5)  # Gentle rate limiting

    return results