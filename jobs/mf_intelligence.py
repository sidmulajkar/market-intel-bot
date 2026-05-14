import sys
import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db       import save_mf_flows, get_mf_flows_dict
from src.telegram_sender import send_text


# ── AMFI NAVAll.txt Fetcher ────────────────────────────────────────
AMFI_URL = "https://www.amfiindia.com/spages/NAVAll.txt"

# ── Category Mapping ────────────────────────────────────────────────
CATEGORY_KEYWORDS = {
    "Large Cap":        ["large cap", "largecap", "bluechip", "blue chip",
                         "nifty 50", "nifty 100", "bse 100", "sensex 30"],
    "Mid Cap":          ["mid cap", "midcap", "nifty midcap", "bse midcap"],
    "Small Cap":        ["small cap", "smallcap", "nifty smallcap", "bse small cap"],
    "Flexi Cap":        ["flexi cap", "flexicap", "multi cap", "multicap",
                         "all cap", "balanced cap"],
    "ELSS":             ["tax saver", "elss", "equity linked", "section 80"],
    "Sector - Infrastructure": ["infrastructure", "infra", "power", "roads"],
    "Sector - IT":       ["it services", "information technology", "software",
                          "it sector", "technology"],
    "Sector - Banking":  ["banking", "bank", "financial services"],
    "Sector - Pharma":   ["pharma", "pharmaceutical", "healthcare"],
    "Sector - FMCG":     ["fmcg", "consumer goods", "consumer staples"],
    "Sector - PSU":      ["psu", "public sector"],
    "Debt":             ["debt", "income", "gilt", "bond", "corporate bond"],
    "Liquid":           ["liquid", "money market", "overnight", "ultra short"],
    "Hybrid":           ["hybrid", "balanced fund"],
    "Gold ETF":         ["gold", "sovereign gold"],
    "International":    ["global", "international", "overseas", "foreign",
                         "us equity", "nasdaq", "s&p"],
}


def _infer_category(scheme_name: str) -> str:
    """Infer category from scheme name keywords."""
    name_lower = scheme_name.lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in name_lower:
                return cat
    return "Other"


# ── Fetch AMFI ──────────────────────────────────────────────────────
def fetch_nav_all() -> pd.DataFrame:
    """
    Download and parse AMFI NAVAll.txt into DataFrame.
    """
    print("📥 Downloading AMFI NAVAll.txt...")
    try:
        resp = requests.get(AMFI_URL, timeout=30)
        if resp.status_code != 200:
            return pd.DataFrame()

        schemes = []
        current_category = ""

        for line in resp.text.split("\n"):
            line = line.strip()
            if not line:
                continue
            if ";" not in line:
                current_category = line
                continue
            parts = line.split(";")
            if len(parts) < 5:
                continue
            try:
                code    = parts[0].strip()
                name    = parts[3].strip()
                nav_str = parts[4].strip()
                if not nav_str or nav_str in ["N.A.", "NA", "-", ""]:
                    continue
                if not code.isdigit():
                    continue
                schemes.append({
                    "scheme_code": code,
                    "scheme_name": name,
                    "category":    current_category,
                    "nav":         float(nav_str),
                    "nav_date":    parts[5].strip() if len(parts) > 5 else "",
                })
            except (ValueError, IndexError):
                continue

        print(f"  ✅ AMFI: {len(schemes)} schemes")
        return pd.DataFrame(schemes)

    except Exception as e:
        print(f"⚠️  AMFI fetch: {e}")
        return pd.DataFrame()


# ── Compute Category Flows ─────────────────────────────────────────
def compute_category_flows(df: pd.DataFrame) -> dict:
    """
    Compute category-level AUM snapshots and MoM changes.
    Flow = (this_month_total - prior_month_total) per category.
    Requires stored prior-month data in mf_flows table.

    Returns dict:
      {
        "month": "2026-05-01",
        "categories": [
          {"name": "Large Cap", "amount_cr": 620, "flow_cr": 45, "direction": "inflow"},
          ...
        ],
        "sip_cr": None
      }
    """
    today = datetime.now()
    current_month_str = today.strftime("%Y-%m-01")

    # Get previous month's stored data
    prev_month = (today - timedelta(days=35)).replace(day=1).strftime("%Y-%m-01")
    prior_data = get_mf_flows_dict(months=3)

    # Build prior_df safely
    prior_rows = []
    for month, rows in prior_data.items():
        for r in rows:
            prior_rows.append({"month": month, "category": r.get("category"), "amount_cr": r.get("amount_cr", 0)})

    if prior_rows:
        prior_df = pd.DataFrame(prior_rows)
    else:
        prior_df = pd.DataFrame(columns=["month", "category", "amount_cr"])

    # Build current-month AUM snapshot by category
    df["cat_inferred"] = df["scheme_name"].apply(_infer_category)
    current_aum = (
        df.groupby("cat_inferred")
        .agg(total_aum=("nav", "sum"), count=("scheme_name", "count"))
        .reset_index()
    )
    current_aum.columns = ["category", "total_aum", "scheme_count"]

    # Convert to Cr (NAV is per unit, so this is AUM proxy in Cr)
    current_aum["amount_cr"] = (current_aum["total_aum"] / 1_00_000).round(1)

    # Compute flow vs prior month
    results = []
    for _, row in current_aum.iterrows():
        cat  = row["category"]
        amt  = row["amount_cr"]

        if not prior_df.empty:
            prior_cat = prior_df[prior_df["category"] == cat]
            if not prior_cat.empty:
                prev_amt = float(prior_cat.iloc[0].get("amount_cr", 0))
                flow = amt - prev_amt
                direction = "inflow" if flow > 0 else ("outflow" if flow < 0 else "flat")
            else:
                flow = None
                direction = "new"
        else:
            flow = None
            direction = "new"

        results.append({
            "name":       cat,
            "amount_cr":  amt,
            "flow_cr":    flow,
            "direction":  direction,
            "scheme_count": row["scheme_count"],
        })

    results.sort(key=lambda x: x["amount_cr"], reverse=True)
    return {"month": current_month_str, "categories": results, "sip_cr": None}


# ── Main ───────────────────────────────────────────────────────────
def main():
    print("=" * 50)
    print("💹 MF INTELLIGENCE STARTING")
    print("=" * 50)

    if datetime.now().weekday() >= 5:
        print("⏭ Weekend — skipping")
        return

    df = fetch_nav_all()
    if df.empty:
        print("⚠️ No AMFI data")
        send_text("⚠️ *MF Intelligence Failed*\nNo data from AMFI.")
        return

    data = compute_category_flows(df)

    if not data["categories"]:
        print("⚠️ No category aggregates")
        return

    saved = 0
    for cat in data["categories"]:
        sip = data["sip_cr"]  # AMFI NAVAll doesn't include SIP — leave None
        result = save_mf_flows(data["month"], cat["name"], cat["amount_cr"], sip_amount_cr=sip)
        if result:
            saved += 1

    saved = 0
    for cat in data["categories"]:
        sip = data["sip_cr"]  # AMFI NAVAll doesn't include SIP — leave None
        if save_mf_flows(data["month"], cat["name"], cat["amount_cr"], sip_amount_cr=sip):
            saved += 1

    print(f"✅ MF Intelligence: {saved}/{len(data['categories'])} categories saved")
    print("=" * 50)


if __name__ == "__main__":
    main()