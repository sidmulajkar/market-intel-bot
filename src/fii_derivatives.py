"""
FII/DII Derivatives Positioning — F&O Participant Data
Shows institutional INTENT: are FIIs hedging, going directional, or unwinding?
Data: NSE F&O participant-wise open interest (long/short positions)
"""
import math
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.nseindia.com/reports-fo-participant",
    "Accept": "application/json, text/plain, */*",
}


def _safe_float(val, default=0.0) -> float:
    """Convert to float, handle NaN/Inf."""
    try:
        f = float(val or 0)
        return default if math.isnan(f) or math.isinf(f) else f
    except (ValueError, TypeError):
        return default


def fetch_fno_participant_oi(date: str = None) -> Optional[Dict]:
    """
    Fetch F&O participant-wise open interest data from NSE.
    Returns: dict with FII/DII/Client long/short positions for index/stock futures and options.
    """
    if date is None:
        date = datetime.now().strftime("%d-%m-%Y")

    url = f"https://www.nseindia.com/api/fodash-tl?dt={date}"

    try:
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=NSE_HEADERS, timeout=10)
        resp = session.get(url, headers=NSE_HEADERS, timeout=15)

        if resp.status_code != 200:
            # Try previous trading days
            for delta in range(1, 5):
                prev_date = (datetime.now() - timedelta(days=delta)).strftime("%d-%m-%Y")
                prev_url = f"https://www.nseindia.com/api/fodash-tl?dt={prev_date}"
                resp = session.get(prev_url, headers=NSE_HEADERS, timeout=15)
                if resp.status_code == 200:
                    break
            else:
                return None

        data = resp.json()

        if not data or "data" not in data:
            return None

        return _parse_participant_data(data)

    except Exception as e:
        print(f"⚠️ F&O participant fetch: {e}")
        return None


def _parse_participant_data(data: Dict) -> Dict:
    """
    Parse NSE F&O participant OI data into structured format.
    Returns: {fii: {long, short, net}, dii: {long, short, net}, client: {long, short, net}}
    """
    result = {
        "date": data.get("date", ""),
        "fii": {"long": 0, "short": 0, "net": 0},
        "dii": {"long": 0, "short": 0, "net": 0},
        "client": {"long": 0, "short": 0, "net": 0},
        "pro": {"long": 0, "short": 0, "net": 0},
    }

    rows = data.get("data", [])
    if not rows:
        return result

    for row in rows:
        category = row.get("category", "").upper()
        client_type = row.get("clientType", "").upper()

        long_oi = _safe_float(row.get("grossLongOI", 0))
        short_oi = _safe_float(row.get("grossShortOI", 0))

        if "FII" in category or "FPI" in category:
            result["fii"]["long"] += long_oi
            result["fii"]["short"] += short_oi
        elif "DII" in category:
            result["dii"]["long"] += long_oi
            result["dii"]["short"] += short_oi
        elif "CLIENT" in client_type or "RETAIL" in client_type:
            result["client"]["long"] += long_oi
            result["client"]["short"] += short_oi
        elif "PRO" in client_type or "PROPRIETARY" in client_type:
            result["pro"]["long"] += long_oi
            result["pro"]["short"] += short_oi

    # Compute net positions
    for cat in ["fii", "dii", "client", "pro"]:
        result[cat]["net"] = result[cat]["long"] - result[cat]["short"]

    return result


def analyze_fno_positioning(data: Dict) -> Dict:
    """
    Analyze F&O positioning data for actionable signals.
    Returns: analysis with signals, regime indicators, and narrative.
    """
    if not data or not data.get("fii"):
        return {"ok": False}

    fii = data["fii"]
    dii = data["dii"]
    client = data["client"]

    analysis = {
        "ok": True,
        "date": data.get("date", ""),
        "fii": fii,
        "dii": dii,
        "client": client,
        "signals": [],
    }

    # ── FII Net Position ──
    fii_net = fii["net"]
    if fii_net > 0:
        analysis["fii_position"] = "NET LONG"
        analysis["fii_bias"] = "BULLISH"
    elif fii_net < 0:
        analysis["fii_position"] = "NET SHORT"
        analysis["fii_bias"] = "BEARISH"
    else:
        analysis["fii_position"] = "FLAT"
        analysis["fii_bias"] = "NEUTRAL"

    # ── DII Net Position ──
    dii_net = dii["net"]
    if dii_net > 0:
        analysis["dii_position"] = "NET LONG"
    elif dii_net < 0:
        analysis["dii_position"] = "NET SHORT"
    else:
        analysis["dii_position"] = "FLAT"

    # ── Key Signal: FII Long/Short Ratio ──
    if fii["short"] > 0:
        fii_ls_ratio = fii["long"] / fii["short"]
        analysis["fii_long_short_ratio"] = round(fii_ls_ratio, 2)

        if fii_ls_ratio > 1.5:
            analysis["signals"].append({
                "type": "BULLISH",
                "signal": f"FII long/short ratio: {fii_ls_ratio:.2f} (strongly long)",
                "detail": "FIIs positioned for upside in derivatives"
            })
        elif fii_ls_ratio < 0.7:
            analysis["signals"].append({
                "type": "BEARISH",
                "signal": f"FII long/short ratio: {fii_ls_ratio:.2f} (heavily short)",
                "detail": "FIIs hedged or positioned for downside"
            })

    # ── Key Signal: FII vs DII Divergence ──
    if fii["net"] < 0 and dii["net"] > 0:
        divergence = abs(fii["net"]) + abs(dii["net"])
        analysis["signals"].append({
            "type": "DIVERGENCE",
            "signal": "FII short + DII long — institutional disagreement",
            "detail": f"FII net: {fii['net']:+,.0f} | DII net: {dii['net']:+,.0f}",
            "historical": "Historically, DII absorption of FII selling provides a floor"
        })
    elif fii["net"] > 0 and dii["net"] < 0:
        analysis["signals"].append({
            "type": "DIVERGENCE",
            "signal": "FII long + DII short — rare institutional disagreement",
            "detail": f"FII net: {fii['net']:+,.0f} | DII net: {dii['net']:+,.0f}",
        })

    # ── Key Signal: Hedging vs Directional ──
    # If FII cash market selling + FII futures long = hedging (bullish underneath)
    # If FII cash market selling + FII futures short = directional bearish
    analysis["positioning_type"] = "unknown"  # Will be enriched by context_engine

    return analysis


def format_fno_positioning(analysis: Dict) -> str:
    """
    Format F&O positioning analysis for AI prompt injection.
    Returns: concise positioning summary with signals.
    """
    if not analysis.get("ok"):
        return ""

    lines = ["[F&O Participant Positioning]"]

    # FII positioning
    fii = analysis["fii"]
    lines.append(f"FII: Long {fii['long']:,.0f} | Short {fii['short']:,.0f} | "
                 f"Net {fii['net']:+,.0f} ({analysis['fii_position']})")

    if "fii_long_short_ratio" in analysis:
        lines.append(f"FII L/S Ratio: {analysis['fii_long_short_ratio']}")

    # DII positioning
    dii = analysis["dii"]
    lines.append(f"DII: Long {dii['long']:,.0f} | Short {dii['short']:,.0f} | "
                 f"Net {dii['net']:+,.0f} ({analysis['dii_position']})")

    # Client positioning
    client = analysis["client"]
    lines.append(f"Client: Long {client['long']:,.0f} | Short {client['short']:,.0f} | "
                 f"Net {client['net']:+,.0f}")

    # Signals
    for signal in analysis.get("signals", []):
        emoji = {"BULLISH": "🟢", "BEARISH": "🔴", "DIVERGENCE": "⚡"}.get(signal["type"], "⚪")
        lines.append(f"{emoji} {signal['signal']}")

    return "\n".join(lines)


def run_fno_analysis() -> str:
    """
    Full pipeline: fetch → analyze → format.
    Returns: formatted F&O positioning string for the prompt.
    """
    print("📡 Fetching F&O participant data...")
    data = fetch_fno_participant_oi()

    if not data:
        print("   ⚠️ No F&O participant data available")
        return ""

    analysis = analyze_fno_positioning(data)
    if not analysis.get("ok"):
        return ""

    output = format_fno_positioning(analysis)
    print(f"   → F&O positioning: {len(output)} chars")
    return output


def run_fno_analysis_with_data() -> tuple:
    """
    Full pipeline: fetch → analyze → format.
    Returns: (formatted_string, analysis_dict) for downstream use.
    analysis_dict includes fii.net for cross-reference.
    """
    print("📡 Fetching F&O participant data...")
    data = fetch_fno_participant_oi()

    if not data:
        print("   ⚠️ No F&O participant data available")
        return "", {}

    analysis = analyze_fno_positioning(data)
    if not analysis.get("ok"):
        return "", {}

    output = format_fno_positioning(analysis)
    print(f"   → F&O positioning: {len(output)} chars")
    return output, analysis
