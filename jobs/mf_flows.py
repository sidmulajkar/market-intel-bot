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
    mf_text = format_mf_message(summary)

    if summary["top_gainers"] or summary["top_losers"]:
        # Compute sector tilt from scheme name patterns
        SECTOR_GROUPS = {
            "LARGE CAP": ["large cap", "largecap", "nifty 50", "nifty50", "sensex"],
            "MID CAP": ["mid cap", "midcap", "mid-cap"],
            "SMALL CAP": ["small cap", "smallcap", "small-cap"],
            "BANKING": ["bank", "financial", "psu bank", "private bank"],
            "IT": ["it ", "tech", "digital", "infotech", "tmt"],
            "PHARMA": ["pharma", "healthcare", "health"],
            "ENERGY": ["energy", "oil", "power", "natural resource"],
            "FMCG": ["fmcg", "consumer"],
            "INFRA": ["infra", "construction"],
            "DEBT": ["debt", "bond", "income", "gilt", "corporate bond", "liquid", "money market"],
            "ELSS": ["elss", "tax saver", "taxsaving"],
            "THEMATIC": ["consumption", "manufacturing", "psu", "dividend", "value", "etf"],
        }
        gainer_sectors = {}
        all_schemes = (summary["top_gainers"] or []) + (summary["top_losers"] or [])
        for s in all_schemes:
            name = (s.get("display_name") or s.get("scheme_name", "")).lower()
            change = s.get("change_pct", 0)
            assigned = False
            for sector, keywords in SECTOR_GROUPS.items():
                if any(kw in name for kw in keywords):
                    if sector not in gainer_sectors:
                        gainer_sectors[sector] = {"count": 0, "total_change": 0.0, "gainers": 0, "losers": 0}
                    gainer_sectors[sector]["count"] += 1
                    gainer_sectors[sector]["total_change"] += change
                    if change > 0:
                        gainer_sectors[sector]["gainers"] += 1
                    else:
                        gainer_sectors[sector]["losers"] += 1
                    assigned = True
                    break
        sector_lines = []
        for sec, data in sorted(gainer_sectors.items(), key=lambda x: x[1]["count"], reverse=True):
            avg = data["total_change"] / data["count"]
            tilt = "🟢" if avg > 0.15 else "🔴" if avg < -0.15 else "🟡"
            sector_lines.append(f"{tilt} {sec}: {data['gainers']}/{data['losers']} schemes (avg {avg:+.2f}%)")
        if sector_lines:
            mf_text += "\n📊 *Sector Tilt:*\n" + "\n".join(sector_lines[:6])

    send_text(mf_text)

    print("✅ MF FLOWS COMPLETE")

if __name__ == "__main__":
    main()