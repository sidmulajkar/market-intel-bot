"""
🏦 CREDIT MONITOR — Daily at 6:00 PM IST
Scans for credit rating changes across all sources
"""
import sys
import json
sys.path.insert(0, ".")

from src.credit_monitor  import get_all_rating_events, format_credit_alerts_message
from src.ai_engine       import AIEngine
from src.telegram_sender import send_text
from src.db              import was_alert_sent, log_alert_sent

def main():
    print("=" * 50)
    print("🏦 CREDIT MONITOR STARTING")
    print("=" * 50)

    with open("config/watchlist.json") as f:
        config = json.load(f)
    symbols = config.get("stocks", [])

    events = get_all_rating_events(symbols)
    msg    = format_credit_alerts_message(events)
    send_text(msg)

    # Alert on critical downgrades/defaults only
    critical = [e for e in events
                if "DOWNGRADED" in e.get("action", "")
                or "DEFAULTED"  in e.get("action", "")]

    for e in critical[:3]:
        sym  = e.get("symbol", e.get("source", "MARKET"))
        key  = f"credit_{sym}_{e['action']}"
        if not was_alert_sent(sym, key):
            ai     = AIEngine()
            prompt = f"""
URGENT: Credit rating event detected:
{e['subject']}
Agency: {e['agency']}
Action: {e['action']}

Quick 3-point impact analysis:
1. Immediate market impact (bonds/equity)
2. Contagion risk to sector?
3. Investor action needed?

Under 80 words. Very direct.
"""
            analysis = ai.analyze("fast", prompt)
            send_text(
                f"🚨 *CRITICAL RATING ALERT*\n\n"
                f"{e['action']} — {e['agency']}\n"
                f"{e['subject'][:150]}\n\n"
                f"🤖 *Impact:*\n{analysis}"
            )
            log_alert_sent(sym, key)

    print("✅ Credit monitor complete!")

if __name__ == "__main__":
    main()