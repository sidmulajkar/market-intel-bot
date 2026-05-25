import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.credit_monitor  import get_all_rating_events, format_credit_alerts_message
from src.ai_engine       import AIEngine
from src.telegram_sender import send_text
from src.db              import was_alert_sent, log_alert_sent, get_watchlist

def main():
    print("=" * 50)
    print("🏦 CREDIT MONITOR STARTING")
    print("=" * 50)

    symbols = get_watchlist()
    events  = get_all_rating_events(symbols)
    send_text(format_credit_alerts_message(events))

    critical = [e for e in events
                if "DOWNGRADED" in e.get("action", "")
                or "DEFAULTED"  in e.get("action", "")]

    for e in critical[:3]:
        sym = e.get("symbol", "MARKET")
        key = f"credit_{sym}_{e['action'][:10]}"
        if not was_alert_sent(sym, key):
            ai     = AIEngine()
            prompt = f"""
URGENT: Credit rating event:
{e['subject']}
Agency: {e['agency']} | Action: {e['action']}

Quick 3-point impact analysis:
1. Immediate market impact
2. Contagion risk?
3. Investor action needed?

Under 80 words.
"""
            try:
                analysis = ai.analyze("fast", prompt)
                # Basic validation: length check + no advice
                if analysis and len(analysis.split()) >= 20:
                    text_lower = analysis.lower()
                    advice_kw = ['buy ', 'sell ', 'go long', 'go short', 'recommend']
                    has_advice = any(kw in text_lower for kw in advice_kw)
                    if has_advice:
                        analysis = analysis + "\n\n[Note: Trade recommendations removed — structural analysis only]"
                    send_text(f"🚨 *CRITICAL RATING ALERT*\n\n{e['action']} — {e['agency']}\n{e['subject'][:150]}\n\n🤖 *Impact:*\n{analysis}")
                log_alert_sent(sym, key)
            except Exception as ex:
                print(f"⚠️ AI failed: {ex}")

    print("✅ CREDIT MONITOR COMPLETE")

if __name__ == "__main__":
    main()