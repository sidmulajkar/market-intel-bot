"""
💹 MUTUAL FUND FLOWS
Schedule: Friday 5:30 PM IST (12:00 PM UTC)
Workflow: .github/workflows/mf_flows.yml

What it does:
  1. Reads MF watchlist FROM SUPABASE
  2. Fetches NAV data for all tracked schemes
  3. Ranks top gainers and losers
  4. Sends AI-powered MF flow analysis
"""
import sys
sys.path.insert(0, ".")

from src.mf_flows        import get_mf_summary, format_mf_message
from src.ai_engine       import AIEngine
from src.telegram_sender import send_text
from src.db              import (
    get_mf_watchlist,        # ← READS FROM SUPABASE
    get_mf_scheme_codes,
)

def main():
    print("=" * 50)
    print("💹 MF FLOWS JOB STARTING")
    print("=" * 50)

    # ── STEP 1: Load MF watchlist from Supabase ───────────────
    mf_schemes = get_mf_watchlist()
    print(f"📋 MF watchlist loaded: {len(mf_schemes)} schemes")

    if not mf_schemes:
        send_text(
            "💹 *MF Flows*\n"
            "⚠️ MF watchlist is empty!\n"
            "Add schemes via: `/addmf AMFI_CODE`\n"
            "Find codes via: `/searchmf FUND_NAME`"
        )
        return

    # Log what we're tracking
    for s in mf_schemes[:5]:
        print(f"   • {s['scheme_code']}: {s['scheme_name'][:40]}")
    if len(mf_schemes) > 5:
        print(f"   ... and {len(mf_schemes) - 5} more")

    # ── STEP 2: Fetch MF performance data ────────────────────
    print("💹 Fetching MF NAV data...")

    # Pass scheme codes from Supabase to mf_flows module
    # The get_mf_summary() function internally calls get_mf_watchlist()
    # which reads from Supabase — already handled in src/mf_flows.py
    summary = get_mf_summary()
    print(f"   Tracked: {summary.get('total_tracked', 0)} schemes")
    print(f"   Gainers: {len(summary.get('top_gainers', []))}")
    print(f"   Losers:  {len(summary.get('top_losers', []))}")

    # ── STEP 3: Send formatted MF summary ────────────────────
    msg = format_mf_message(summary)
    send_text(msg)
    print("   ✅ MF summary sent")

    # ── STEP 4: AI MF flow interpretation ────────────────────
    gainers = summary.get("top_gainers", [])
    losers  = summary.get("top_losers",  [])

    if gainers or losers:
        print("🤖 Running AI MF flow analysis...")

        gainers_text = "\n".join([
            f"🟢 {s.get('display_name') or s.get('scheme_name', '')[:40]}: "
            f"{s.get('change_pct', 0):+.2f}%"
            for s in gainers[:3]
        ]) if gainers else "None"

        losers_text = "\n".join([
            f"🔴 {s.get('display_name') or s.get('scheme_name', '')[:40]}: "
            f"{s.get('change_pct', 0):+.2f}%"
            for s in losers[:3]
        ]) if losers else "None"

        prompt = f"""
Mutual Fund Performance Today ({len(mf_schemes)} schemes tracked):

Top Performing Schemes:
{gainers_text}

Worst Performing Schemes:
{losers_text}

Analyse for Indian retail investors:
1. Which sectors/themes are MFs favouring today?
2. Is there any category rotation happening?
3. What does MF activity suggest about market direction?
4. Should retail investors follow or fade this activity?
5. One actionable insight from this MF data

Under 200 words. Direct and actionable.
"""
        ai = AIEngine()
        try:
            analysis = ai.analyze("volume", prompt)
            send_text(
                "🤖 *AI — MF Flow Interpretation:*\n\n"
                + analysis
            )
            print("   ✅ AI MF analysis sent")
        except Exception as e:
            print(f"   ⚠️ AI MF analysis failed: {e}")

    # ── STEP 5: Your MF watchlist summary ────────────────────
    scheme_list = "\n".join([
        f"{i+1}. *{s['scheme_name'][:40]}*\n"
        f"   Code: `{s['scheme_code']}`"
        + (f" | {s.get('category', '')}" if s.get("category") else "")
        for i, s in enumerate(mf_schemes[:10])
    ])

    send_text(
        f"💹 *Your MF Watchlist ({len(mf_schemes)} schemes):*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        + scheme_list
        + "\n\n_/listmf to view all | /addmf CODE to add more_"
    )

    print("=" * 50)
    print("✅ MF FLOWS COMPLETE")
    print("=" * 50)

if __name__ == "__main__":
    main()