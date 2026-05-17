"""
CFTC Commitment of Traders — USD futures positioning data.
Shows WHO is driving DXY moves: speculators vs commercials.
Free API, weekly Friday release.

Source: CFTC historical data (https://www.cftc.gov/dea/futures/other_lf.htm)
"""
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import statistics


# ═══════════════════════════════════════════════════════════════════════════════
# CFTC DATA FETCHING
# ═══════════════════════════════════════════════════════════════════════════════

# Key contracts to track (DXY components + related)
CONTRACTS = {
    "USD_LONG": {"code": "098662", "name": "US Dollar Index (Long)"},
    "EURO_LONG": {"code": "099741", "name": "Euro (Long)"},
    "JPY_LONG": {"code": "097741", "name": "Japanese Yen (Long)"},
    "GBP_LONG": {"code": "099741", "name": "British Pound (Long)"},
    "GOLD_LONG": {"code": "088691", "name": "Gold (Long)"},
    "CRUDE_LONG": {"code": "067651", "name": "Crude Oil (Long)"},
}

# Simplified: track USD composite + Gold + Crude
TRACKED = [
    {"name": "US Dollar Index", "cftc_code": "098662", "impact": "DXY direction"},
    {"name": "Euro FX", "cftc_code": "099741", "impact": "EUR/USD (DXY inverse)"},
    {"name": "Japanese Yen", "cftc_code": "097741", "impact": "JPY/USD"},
    {"name": "Gold", "cftc_code": "088691", "impact": "Risk-off / inflation hedge"},
    {"name": "Crude Oil", "cftc_code": "067651", "impact": "Inflation / growth proxy"},
]


def fetch_cftc_data(contract_code: str, weeks: int = 52) -> List[Dict]:
    """
    Fetch CFTC positioning data for a contract.
    Uses CFTC public CSV endpoint.
    Returns list of weekly positioning snapshots.
    """
    try:
        # CFTC legacy format CSV
        url = f"https://www.cftc.gov/dea/newcot/fin_futw.txt"
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            # Try alternative endpoint
            url = f"https://www.cftc.gov/dea/newcot/f_disagg.txt"
            resp = requests.get(url, timeout=15)

        if resp.status_code != 200:
            return []

        lines = resp.text.strip().split("\n")
        if len(lines) < 2:
            return []

        # Parse header
        header = lines[0].split(",")
        results = []

        for line in lines[1:]:
            parts = line.split(",")
            if len(parts) < 10:
                continue

            try:
                # Find contract name match
                name_field = parts[1].strip() if len(parts) > 1 else ""
                code_field = parts[2].strip() if len(parts) > 2 else ""

                if contract_code not in code_field and contract_code not in name_field:
                    continue

                date_str = parts[0].strip()
                try:
                    date = datetime.strptime(date_str, "%m/%d/%Y")
                except ValueError:
                    continue

                # Extract positioning data
                def safe_int(val):
                    try:
                        return int(val.strip().replace(",", "").replace('"', ''))
                    except (ValueError, AttributeError):
                        return 0

                def safe_float(val):
                    try:
                        return float(val.strip().replace(",", "").replace('"', ''))
                    except (ValueError, AttributeError):
                        return 0.0

                # Open interest, non-commercial long/short, commercial long/short
                oi = safe_int(parts[5]) if len(parts) > 5 else 0
                non_comm_long = safe_int(parts[6]) if len(parts) > 6 else 0
                non_comm_short = safe_int(parts[7]) if len(parts) > 7 else 0
                non_comm_spread = safe_int(parts[8]) if len(parts) > 8 else 0
                comm_long = safe_int(parts[9]) if len(parts) > 9 else 0
                comm_short = safe_int(parts[10]) if len(parts) > 10 else 0

                if oi > 0:
                    results.append({
                        "date": date.strftime("%Y-%m-%d"),
                        "open_interest": oi,
                        "speculator_long": non_comm_long,
                        "speculator_short": non_comm_short,
                        "speculator_spread": non_comm_spread,
                        "commercial_long": comm_long,
                        "commercial_short": comm_short,
                        "speculator_net": non_comm_long - non_comm_short,
                        "commercial_net": comm_long - comm_short,
                    })
            except Exception:
                continue

        return results[-weeks:] if len(results) > weeks else results

    except Exception as e:
        print(f"⚠️ CFTC fetch error for {contract_code}: {e}")
        return []


def fetch_cftc_summary() -> Dict:
    """
    Fetch CFTC data for all tracked contracts and compute positioning signals.
    Returns structured analysis for AI prompt injection.
    """
    results = {}

    for contract in TRACKED:
        data = fetch_cftc_data(contract["cftc_code"], weeks=52)
        if not data or len(data) < 10:
            continue

        latest = data[-1]
        spec_net = latest["speculator_net"]
        comm_net = latest["commercial_net"]
        oi = latest["open_interest"]

        # Compute percentile of speculator net position (1-year)
        spec_nets = [d["speculator_net"] for d in data]
        if len(spec_nets) >= 20:
            sorted_nets = sorted(spec_nets)
            below = sum(1 for v in sorted_nets if v < spec_net)
            spec_percentile = round((below / len(sorted_nets)) * 100)
        else:
            spec_percentile = None

        # Compute percentile of commercial net position
        comm_nets = [d["commercial_net"] for d in data]
        if len(comm_nets) >= 20:
            sorted_comm = sorted(comm_nets)
            below_comm = sum(1 for v in sorted_comm if v < comm_net)
            comm_percentile = round((below_comm / len(sorted_comm)) * 100)
        else:
            comm_percentile = None

        # Trend: 4-week average vs 13-week average
        spec_4w = statistics.mean(spec_nets[-4:]) if len(spec_nets) >= 4 else spec_net
        spec_13w = statistics.mean(spec_nets[-13:]) if len(spec_nets) >= 13 else spec_net

        if spec_4w > spec_13w * 1.1:
            trend = "INCREASING"
        elif spec_4w < spec_13w * 0.9:
            trend = "DECREASING"
        else:
            trend = "STABLE"

        # Contrarian signal
        if spec_percentile and spec_percentile > 90:
            signal = "EXTREMELY BULLISH positioning → contrarian BEARISH risk"
        elif spec_percentile and spec_percentile > 75:
            signal = "BULLISH positioning — watch for reversal"
        elif spec_percentile and spec_percentile < 10:
            signal = "EXTREMELY BEARISH positioning → contrarian BULLISH potential"
        elif spec_percentile and spec_percentile < 25:
            signal = "BEARISH positioning — potential bottoming"
        else:
            signal = "NEUTRAL positioning"

        results[contract["name"]] = {
            "speculator_net": spec_net,
            "speculator_percentile": spec_percentile,
            "commercial_net": comm_net,
            "commercial_percentile": comm_percentile,
            "open_interest": oi,
            "trend": trend,
            "signal": signal,
            "impact": contract["impact"],
            "latest_date": latest["date"],
            "weeks_of_data": len(data),
        }

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# FORMATTING
# ═══════════════════════════════════════════════════════════════════════════════

def format_cftc_summary(summary: Dict) -> str:
    """Format CFTC COT data for AI prompt injection."""
    if not summary:
        return ""

    lines = ["[CFTC Commitment of Traders — Weekly Positioning]"]

    for name, data in summary.items():
        pctile = data.get("speculator_percentile")
        pct_str = f" ({pctile}th percentile)" if pctile else ""

        lines.append(f"\n  {name}:")
        lines.append(f"    Speculators: ₹{data['speculator_net']:+,} contracts{pct_str}")
        lines.append(f"    Commercials: ₹{data['commercial_net']:+,} contracts")
        lines.append(f"    Trend: {data['trend']} | OI: {data['open_interest']:,}")
        lines.append(f"    Signal: {data['signal']}")

    lines.append(f"\n  Key insight: Commercials are 'smart money' — their positioning")
    lines.append(f"  tends to lead reversals. Speculators are trend-followers.")
    lines.append(f"  When speculators are at extremes (>{80}th or <{20}th percentile),")
    lines.append(f"  mean reversion is statistically likely.")

    return "\n".join(lines)


def run_cftc_analysis() -> Dict:
    """
    Full CFTC analysis pipeline.
    Returns formatted block for AI prompt + structured data.
    """
    summary = fetch_cftc_summary()
    formatted = format_cftc_summary(summary)

    return {
        "ok": bool(summary),
        "summary": summary,
        "formatted": formatted,
    }


if __name__ == "__main__":
    result = run_cftc_analysis()
    if result["ok"]:
        print(result["formatted"])
    else:
        print("No CFTC data available")
