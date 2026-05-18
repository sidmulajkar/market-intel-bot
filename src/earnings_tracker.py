"""
Earnings Surprise Tracker — Track Nifty 50 earnings releases.
Store actual vs expected EPS, compute surprise %, track stock move post-earnings.

After 1 quarter of data:
  "Infosys reports tomorrow. Historical 5% surprise = avg 3.2% stock move.
   Current IV implies 4.1% move. IV fairly priced."

Source: NSE corporate results API + yfinance (free).
"""
import requests
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import statistics


# ═══════════════════════════════════════════════════════════════════════════════
# NIFTY 50 CONSTITUENTS
# ═══════════════════════════════════════════════════════════════════════════════

NIFTY_50_SYMBOLS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "LT.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "HCLTECH.NS",
    "SUNPHARMA.NS", "TITAN.NS", "BAJFINANCE.NS", "WIPRO.NS", "ULTRACEMCO.NS",
    "ONGC.NS", "NTPC.NS", "TATAMOTORS.NS", "POWERGRID.NS", "M&M.NS",
    "JSWSTEEL.NS", "TATASTEEL.NS", "TECHM.NS", "ADANIENT.NS", "ADANIPORTS.NS",
    "INDUSINDBK.NS", "HDFCLIFE.NS", "DIVISLAB.NS", "BPCL.NS", "COALINDIA.NS",
    "GRASIM.NS", "BRITANNIA.NS", "CIPLA.NS", "DRREDDY.NS", "EICHERMOT.NS",
    "TRENT.NS", "APOLLOHOSP.NS", "NESTLEIND.NS", "SBILIFE.NS", "BAJAJFINSV.NS",
    "HINDALCO.NS", "HEROMOTOCO.NS", "BAJAJ-AUTO.NS", "TATACONSUM.NS", "LTIM.NS",
]

# NSE symbol mapping (yfinance .NS suffix)
NSE_SYMBOLS = [s.replace(".NS", "") for s in NIFTY_50_SYMBOLS]


# ═══════════════════════════════════════════════════════════════════════════════
# EARNINGS DATA FETCHING
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_earnings_calendar() -> List[Dict]:
    """
    Fetch upcoming earnings dates for Nifty 50 stocks.
    Uses yfinance earnings calendar.
    Returns list of {symbol, company, earnings_date, days_until}
    """
    upcoming = []
    today = datetime.now().date()

    for symbol in NIFTY_50_SYMBOLS[:20]:  # Top 20 to avoid rate limits
        try:
            ticker = yf.Ticker(symbol)
            cal = ticker.calendar
            if cal is None or cal.empty:
                continue

            # Get earnings date
            earnings_dates = cal.get("Earnings Date", [])
            if not earnings_dates:
                continue

            for date_val in earnings_dates:
                if isinstance(date_val, (datetime,)):
                    earnings_date = date_val.date()
                elif isinstance(date_val, str):
                    try:
                        earnings_date = datetime.strptime(date_val, "%Y-%m-%d").date()
                    except ValueError:
                        continue
                else:
                    continue

                # Only upcoming earnings (within next 30 days)
                days_until = (earnings_date - today).days
                if 0 <= days_until <= 30:
                    company_name = symbol.replace(".NS", "")
                    upcoming.append({
                        "symbol": symbol,
                        "company": company_name,
                        "earnings_date": earnings_date.strftime("%Y-%m-%d"),
                        "days_until": days_until,
                    })
                    break  # Only next earnings
        except Exception:
            continue

    return sorted(upcoming, key=lambda x: x["days_until"])


def fetch_earnings_history(symbol: str, quarters: int = 4) -> List[Dict]:
    """
    Fetch historical earnings for a stock (last N quarters).
    Returns list of {date, eps_estimate, eps_actual, surprise_pct}
    """
    try:
        ticker = yf.Ticker(symbol)
        earnings = ticker.earnings

        if earnings is None or earnings.empty:
            return []

        history = []
        for _, row in earnings.iterrows():
            date_str = str(row.get("Earnings Date", ""))
            eps_actual = row.get("Earnings", None)
            eps_estimate = row.get("Earnings Estimate", None)

            if eps_actual is not None and eps_estimate is not None and eps_estimate != 0:
                surprise_pct = round(((eps_actual - eps_estimate) / abs(eps_estimate)) * 100, 2)
            else:
                surprise_pct = None

            history.append({
                "date": date_str[:10] if date_str else "unknown",
                "eps_actual": eps_actual,
                "eps_estimate": eps_estimate,
                "surprise_pct": surprise_pct,
            })

        return history[-quarters:] if len(history) > quarters else history

    except Exception:
        return []


def fetch_post_earnings_move(symbol: str, earnings_date: str, days_before: int = 5,
                              days_after: int = 5) -> Dict:
    """
    Compute stock price move around earnings date.
    Returns move from 5 days before to 5 days after earnings.
    """
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="3mo", interval="1d")

        if hist is None or len(hist) < 10:
            return {"ok": False}

        # Find closest trading day to earnings date
        target_date = datetime.strptime(earnings_date, "%Y-%m-%d").date()
        dates = [d.date() for d in hist.index]

        # Find pre-earnings price (5 trading days before)
        pre_dates = [d for d in dates if d < target_date]
        if len(pre_dates) < days_before:
            return {"ok": False}
        pre_price = float(hist.loc[hist.index[-(len(pre_dates)-days_before+1):][0], "Close"])

        # Find post-earnings price (5 trading days after)
        post_dates = [d for d in dates if d > target_date]
        if len(post_dates) < days_after:
            return {"ok": False}
        post_price = float(hist.loc[hist.index[:days_after][-1], "Close"])

        move_pct = round(((post_price / pre_price) - 1) * 100, 2)

        return {
            "ok": True,
            "pre_price": round(pre_price, 2),
            "post_price": round(post_price, 2),
            "move_pct": move_pct,
            "direction": "UP" if move_pct > 0 else "DOWN",
        }

    except Exception:
        return {"ok": False}


# ═══════════════════════════════════════════════════════════════════════════════
# EARNINGS ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

def compute_surprise_stats(history: List[Dict]) -> Dict:
    """
    Compute average move per surprise magnitude from historical earnings.
    Returns buckets: {surprise_range: avg_move, count}
    """
    if not history or len(history) < 2:
        return {"ok": False, "message": "Insufficient earnings history"}

    # Compute moves for each quarter
    moves = []
    for q in history:
        if q.get("surprise_pct") is not None and q.get("move_pct") is not None:
            moves.append({
                "surprise_pct": q["surprise_pct"],
                "move_pct": q["move_pct"],
            })

    if len(moves) < 2:
        return {"ok": False, "message": "Insufficient move data"}

    # Compute stats
    surprise_pcts = [m["surprise_pct"] for m in moves]
    move_pcts = [m["move_pct"] for m in moves]

    # Positive surprise vs negative surprise
    pos_surprises = [m for m in moves if m["surprise_pct"] > 0]
    neg_surprises = [m for m in moves if m["surprise_pct"] < 0]

    avg_move_positive_surprise = statistics.mean([m["move_pct"] for m in pos_surprises]) if pos_surprises else 0
    avg_move_negative_surprise = statistics.mean([m["move_pct"] for m in neg_surprises]) if neg_surprises else 0

    # Overall average absolute move
    avg_abs_move = statistics.mean([abs(m["move_pct"]) for m in moves])

    return {
        "ok": True,
        "quarters": len(moves),
        "avg_surprise_pct": round(statistics.mean(surprise_pcts), 2),
        "avg_abs_move": round(avg_abs_move, 2),
        "avg_move_positive_surprise": round(avg_move_positive_surprise, 2),
        "avg_move_negative_surprise": round(avg_move_negative_surprise, 2),
        "hit_rate": round(len(pos_surprises) / len(moves) * 100, 1) if moves else 0,
        "moves": moves,
    }


def run_earnings_analysis(upcoming_limit: int = 5) -> Dict:
    """
    Full earnings analysis pipeline.
    1. Fetch upcoming earnings
    2. For each, compute historical surprise stats
    3. Format for AI prompt
    """
    upcoming = fetch_earnings_calendar()

    if not upcoming:
        return {"ok": False, "message": "No upcoming earnings found"}

    analyzed = []
    for stock in upcoming[:upcoming_limit]:
        symbol = stock["symbol"]
        history = fetch_earnings_history(symbol, quarters=8)

        if not history:
            continue

        stats = compute_surprise_stats(history)
        if not stats.get("ok"):
            continue

        analyzed.append({
            **stock,
            "history": history,
            "stats": stats,
        })

    return {
        "ok": bool(analyzed),
        "upcoming": analyzed,
        "total_upcoming": len(upcoming),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# FORMATTING
# ═══════════════════════════════════════════════════════════════════════════════

def format_earnings(analysis: Dict) -> str:
    """Format earnings analysis for AI prompt injection."""
    if not analysis.get("ok"):
        return ""

    lines = ["[Upcoming Earnings — Historical Surprise Analysis]"]
    lines.append(f"Found {analysis['total_upcoming']} stocks with upcoming earnings")
    lines.append("")

    for stock in analysis.get("upcoming", []):
        stats = stock.get("stats", {})
        lines.append(f"  📊 {stock['company']} — Reports in {stock['days_until']} days ({stock['earnings_date']})")
        lines.append(f"    Historical ({stats.get('quarters', 0)}Q): avg surprise {stats.get('avg_surprise_pct', 0):+.1f}%")
        lines.append(f"    Avg move on +surprise: {stats.get('avg_move_positive_surprise', 0):+.1f}%")
        lines.append(f"    Avg move on -surprise: {stats.get('avg_move_negative_surprise', 0):+.1f}%")
        lines.append(f"    Avg absolute move: ±{stats.get('avg_abs_move', 0):.1f}%")

        # Last quarter
        if stock.get("history"):
            last = stock["history"][-1]
            if last.get("surprise_pct") is not None:
                lines.append(f"    Last quarter: surprise {last['surprise_pct']:+.1f}%")
        lines.append("")

    lines.append("  Use this to calibrate expectations: if current IV implies ±3% move")
    lines.append("  but historical avg is ±1.5%, the market is pricing MORE uncertainty.")
    lines.append("  If IV implies ±1% but historical avg is ±3%, IV is cheap — options mispriced.")

    return "\n".join(lines)


def compute_earnings_regime() -> Dict:
    """
    Detect if we're in earnings season and how heavy it is.
    Classifies: PEAK_WEEK (5+ stocks), ACTIVE (2-4), APPROACHING (1), QUIET (0).

    Returns regime label + list of upcoming earnings for context.
    """
    try:
        upcoming = fetch_earnings_calendar()
    except Exception as e:
        return {"ok": False, "message": f"Failed to fetch: {e}"}

    if not upcoming:
        return {
            "ok": True,
            "regime": "QUIET",
            "label": "No major earnings expected in next 30 days",
            "count_this_week": 0,
            "count_next_7d": 0,
            "upcoming": [],
        }

    # Count earnings in next 7 days
    from datetime import datetime, timedelta
    today = datetime.now()
    week_from_now = today + timedelta(days=7)

    this_week = []
    next_7d = []
    for stock in upcoming:
        days = stock.get("days_until", 99)
        if days <= 3:
            this_week.append(stock)
        if days <= 7:
            next_7d.append(stock)

    count_week = len(this_week)
    count_7d = len(next_7d)

    if count_week >= 5:
        regime = "PEAK_WEEK"
        label  = f"Peak earnings week — {count_week} Nifty 50 stocks reporting. Expect stock-specific moves overriding index signals."
    elif count_week >= 2:
        regime = "ACTIVE"
        label  = f"Earnings season active — {count_week} stocks reporting this week. Sector RS may be noisy."
    elif count_7d >= 1:
        regime = "APPROACHING"
        label  = f"Earnings approaching — {count_7d} stock(s) in next 7 days. Expect positioning, not conviction."
    else:
        regime = "QUIET"
        label  = "No major earnings this week — normal signal environment"

    return {
        "ok": True,
        "regime": regime,
        "label": label,
        "count_this_week": count_week,
        "count_next_7d": count_7d,
        "upcoming": upcoming[:5],
    }


if __name__ == "__main__":
    result = run_earnings_analysis()
    if result["ok"]:
        print(format_earnings(result))
    else:
        print(f"No data: {result.get('message')}")
