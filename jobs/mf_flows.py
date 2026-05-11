import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.mf_flows        import get_mf_summary, format_mf_message
from src.ai_engine       import AIEngine
from src.telegram_sender import send_text
from src.db              import get_mf_watchlist

def main():
    print("=" * 50)
    print("💹 MF FLOWS STARTING")
    print("=" * 50)

    mf_schemes = get_mf_watchlist()
    if not mf_schemes:
        send_text("💹 *MF Flows*\n⚠️ MF watchlist empty!\nUse `/addmf CODE`")
        return

    summary = get_mf_summary()
    send_text(format_mf_message(summary))

    if summary["top_gainers"] or summary["top_losers"]:
        gainers_text = "\n".join([f"🟢 {s.get('display_name','')[:35]}: {s.get('change_pct',0):+.2f}%"
                                   for s in summary["top_gainers"][:3]])
        losers_text  = "\n".join([f"🔴 {s.get('display_name','')[:35]}: {s.get('change_pct',0):+.2f}%"
                                   for s in summary["top_losers"][:3]])
        ai     = AIEngine()
        prompt = f"""
MF Performance Today:
Top Gainers: {gainers_text if gainers_text else 'None'}
Top Losers: {losers_text if losers_text else 'None'}

Analyse:
1. Which sectors/themes are MFs favouring?
2. Any category rotation?
3. Market direction signal?
4. Should retail follow or fade?

Under 150 words.
"""
        try:
            analysis = ai.analyze("volume", prompt)
            send_text(f"🤖 *AI — MF Flow Analysis:*\n\n{analysis}")
        except Exception as e:
            print(f"⚠️ AI failed: {e}")

    print("✅ MF FLOWS COMPLETE")

if __name__ == "__main__":
    main()