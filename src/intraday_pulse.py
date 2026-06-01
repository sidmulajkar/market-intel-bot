"""
Intraday Pulse Scanner — 30-min Nifty + VIX scanner during market hours.

Deterministic, zero AI. Checks Nifty spot + IndiaVIX every 30 min.
Compares against session open + previous pulse values. Only sends on changes.
Goal: detect sudden VIX spikes, Nifty momentum shifts before they compound.

Data sources:
  - Nifty spot: yfinance ^NSEI (period="1d", interval="5m")
  - India VIX: yfinance ^INDIAVIX (period="1d", interval="5m")
  - Session open: Supabase intraday_pulse table (first row of day)
"""

from datetime import datetime, time as dtime
from typing import Dict, Optional


# Market hours in UTC (09:15-15:30 IST = 03:45-10:00 UTC)
MARKET_OPEN_UTC = dtime(3, 45)
MARKET_CLOSE_UTC = dtime(10, 0)


def _within_market_hours(utc_now: datetime = None) -> bool:
    """Check if current UTC time is within Indian market hours."""
    if utc_now is None:
        utc_now = datetime.utcnow()
    t = utc_now.time()
    if utc_now.weekday() >= 5:
        return False
    return MARKET_OPEN_UTC <= t <= MARKET_CLOSE_UTC


def _fetch_nifty_vix() -> Dict:
    """Fetch latest Nifty + VIX from yfinance. Returns {} on failure."""
    import yfinance as yf
    try:
        nifty = yf.Ticker("^NSEI")
        nifty_hist = nifty.history(period="1d", interval="5m")
        vix = yf.Ticker("^INDIAVIX")
        vix_hist = vix.history(period="1d", interval="5m")

        if nifty_hist.empty:
            return {}

        latest_nifty = nifty_hist.iloc[-1]
        latest_vix = vix_hist.iloc[-1] if not vix_hist.empty else None

        nifty_price = float(latest_nifty["Close"])
        nifty_open = float(nifty_hist.iloc[0]["Open"])
        nifty_change_pct = round((nifty_price - nifty_open) / nifty_open * 100, 1)

        result = {
            "nifty_price": nifty_price,
            "nifty_high": float(latest_nifty["High"]),
            "nifty_low": float(latest_nifty["Low"]),
            "nifty_change_pct": nifty_change_pct,
            "nifty_volume": int(latest_nifty.get("Volume", 0)),
            "vix": float(latest_vix["Close"]) if latest_vix is not None else None,
            "vix_prev": float(vix_hist.iloc[-2]["Close"]) if latest_vix is not None and len(vix_hist) >= 2 else None,
        }

        if result["vix"] and result["vix_prev"] and result["vix_prev"] != 0:
            result["vix_change_pct"] = round((result["vix"] - result["vix_prev"]) / result["vix_prev"] * 100, 1)
        else:
            result["vix_change_pct"] = 0.0

        return result
    except Exception:
        return {}


def _get_session_open(supabase, trade_date: str) -> Optional[Dict]:
    """Get first intraday_pulse row for today (session open fingerprint)."""
    if not supabase:
        return None
    try:
        resp = supabase.table("intraday_pulse") \
            .select("*") \
            .eq("trade_date", trade_date) \
            .order("pulse_time") \
            .limit(1) \
            .execute()
        if resp.data:
            return resp.data[0]
    except Exception:
        pass
    return None


def _classify_pulse(nifty_change: float, vix_change: float) -> str:
    """Classify intraday market condition into CALM / WATCH / ALERT.

    Uses velocity thresholds (not absolute levels) to detect acceleration.
    """
    if abs(vix_change) >= 8 or abs(nifty_change) >= 1.5:
        return "ALERT"
    if abs(vix_change) >= 4 or abs(nifty_change) >= 0.8:
        return "WATCH"
    return "CALM"


def run_pulse(supabase) -> Dict:
    """Run a single intraday pulse scan.

    Returns pulse result dict. Persists to Supabase.
    Sends Telegram only if pulse_label != previous pulse_label.
    """
    if not _within_market_hours():
        return {"ok": False, "reason": "Outside market hours"}

    data = _fetch_nifty_vix()
    if not data:
        return {"ok": False, "reason": "No Nifty data"}

    trade_date = datetime.utcnow().strftime("%Y-%m-%d")
    pulse_time = datetime.utcnow().strftime("%H:%M:%S")

    pulse_label = _classify_pulse(data["nifty_change_pct"], data.get("vix_change_pct", 0))

    # Build pulse record
    record = {
        "trade_date": trade_date,
        "pulse_time": pulse_time,
        "nifty_price": data["nifty_price"],
        "nifty_change_pct": data["nifty_change_pct"],
        "india_vix": data.get("vix"),
        "vix_change_pct": data.get("vix_change_pct", 0),
        "pulse_label": pulse_label,
    }

    # Check if pulse_label changed from last
    last_label = None
    if supabase:
        try:
            last = supabase.table("intraday_pulse") \
                .select("pulse_label") \
                .eq("trade_date", trade_date) \
                .order("pulse_time", desc=True) \
                .limit(1) \
                .execute()
            if last.data:
                last_label = last.data[0]["pulse_label"]
        except Exception:
            pass

    # Save to Supabase
    if supabase:
        try:
            supabase.table("intraday_pulse").insert(record).execute()
        except Exception as e:
            record["save_error"] = str(e)

    formatted = _format_pulse(record, previous_label=last_label)
    label_changed = last_label is not None and last_label != pulse_label

    return {
        "ok": True,
        "record": record,
        "formatted": formatted,
        "label_changed": label_changed,
    }


def _format_pulse(record: Dict, previous_label: Optional[str] = None) -> str:
    """Format pulse scan for Telegram. Only sent if label changed."""
    emoji = {"ALERT": "🔴", "WATCH": "🟡", "CALM": "🟢"}.get(record.get("pulse_label", "CALM"), "⚪")
    nifty_str = f"{record['nifty_price']:,.0f}"
    nifty_pct = record.get("nifty_change_pct", 0)
    sign = "+" if nifty_pct >= 0 else ""
    nifty_str += f" ({sign}{nifty_pct:.1f}%)"

    vix_str = ""
    if record.get("india_vix"):
        vix_pct = record.get("vix_change_pct", 0)
        vix_sign = "+" if vix_pct >= 0 else ""
        vix_str = f" | VIX {record['india_vix']:.1f} ({vix_sign}{vix_pct:.1f}%)"

    transition = ""
    if previous_label and previous_label != record.get("pulse_label"):
        transition = f" [was {previous_label}]"

    return f"{emoji} *Intraday Pulse*{transition}: Nifty {nifty_str}{vix_str}"


def get_session_open(supabase, trade_date: str) -> Optional[Dict]:
    """Get session open values for use by other jobs (e.g., market_close,
    midday_scan). Returns {nifty_open, vix_open}."""
    row = _get_session_open(supabase, trade_date)
    if row:
        return {
            "nifty_open": row.get("nifty_price"),
            "vix_open": row.get("india_vix"),
        }
    return None
