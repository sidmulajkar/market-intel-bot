"""
Scenario Engine — Multi-variable pattern detection for market regimes.

Detects named scenarios from MarketState + flow metrics data.
Also finds historical clones: 3 closest dates matching current macro conditions.

All thresholds are data-anchored (yfinance, NSE, Supabase).
No AI speculation — purely deterministic.

Usage:
    detector = ScenarioDetector(state, flow_metrics=ctx.get("flow_metrics"))
    scenarios = detector.detect()
    state.active_scenarios = scenarios
    state.historical_clones = find_historical_clones(state)  # dynamic context
"""
from __future__ import annotations

from typing import Dict, List, Optional

from src.state import MarketState, Scenario


class ScenarioDetector:
    """Detects 5 named scenarios from market data.

    Each scenario combines 3-4 variables to reduce false positives.
    Thresholds calibrated for Indian market context (2025-26).
    """

    # ── Thresholds (data-anchored, tuned for Indian context) ─────────
    ASIAN_CONTAGION = {
        "usdinr_min": 87.0,
        "vix_min": 18.0,
        "dxy_min": 106.0,
        "fii_streak_min": 3,
    }

    GEOPOLITICAL = {
        "brent_min": 85.0,
        "gold_min": 2500.0,
        "vix_min": 22.0,
        "usdinr_min": 87.0,
    }

    FII_EXODUS = {
        "fii_net_max": -2000.0,
        "usdinr_min": 87.0,
        "dxy_min": 106.0,
        "fii_streak_min": 3,
    }

    USD_CRISIS = {
        "dxy_min": 108.0,
        "usdinr_min": 90.0,
    }

    OIL_SHOCK = {
        "brent_min": 90.0,
        "gold_min": 3000.0,
        "vix_min": 25.0,
    }

    def __init__(self, state: MarketState, flow_metrics: Optional[Dict] = None):
        self.state = state
        self.flow_metrics = flow_metrics or {}

    def detect(self) -> List[Scenario]:
        scenarios: List[Scenario] = []

        asian = self._check_asian_contagion()
        if asian:
            scenarios.append(asian)

        geo = self._check_geopolitical()
        if geo:
            scenarios.append(geo)

        exodus = self._check_fii_exodus()
        if exodus:
            scenarios.append(exodus)

        usd = self._check_usd_crisis()
        if usd:
            scenarios.append(usd)

        oil = self._check_oil_shock()
        if oil:
            scenarios.append(oil)

        return scenarios

    # ── Data access helpers ───────────────────────────────────────────

    @property
    def usdinr(self) -> Optional[float]:
        return self.state.macro.usdinr

    @property
    def brent(self) -> Optional[float]:
        return self.state.macro.brent

    @property
    def gold(self) -> Optional[float]:
        return self.state.macro.gold

    @property
    def dxy(self) -> Optional[float]:
        return self.state.macro.dxy

    @property
    def vix(self) -> Optional[float]:
        return self.state.macro.vix

    @property
    def cboe_vix(self) -> Optional[float]:
        return self.state.macro.cboe_vix

    @property
    def fii_net(self) -> Optional[float]:
        return self.state.flows.fii_net

    @property
    def fii_streak_days(self) -> int:
        return self.state.flows.fii_streak_days

    @property
    def fii_5d_total(self) -> Optional[float]:
        return self.flow_metrics.get("fii_5d_total")

    # ── Scenario checks ───────────────────────────────────────────────

    def _check_asian_contagion(self) -> Optional[Scenario]:
        """Pattern: USDINR pressure + VIX elevated + DXY strong + FII selling streak.

        Historical parallels: 2013 Taper Tantrum, 2020 COVID, 2022 Fed tightening.
        """
        t = self.ASIAN_CONTAGION
        if not all([self.usdinr, self.vix, self.dxy]):
            return None

        indicators = []
        if self.usdinr and self.usdinr >= t["usdinr_min"]:
            indicators.append(f"USDINR ≥{t['usdinr_min']} (₹{self.usdinr:.1f})")
        if self.vix and self.vix >= t["vix_min"]:
            indicators.append(f"India VIX ≥{t['vix_min']} ({self.vix:.1f})")
        if self.dxy and self.dxy >= t["dxy_min"]:
            indicators.append(f"DXY ≥{t['dxy_min']} ({self.dxy:.1f})")
        if self.fii_streak_days >= t["fii_streak_min"]:
            indicators.append(f"FII sell streak ≥{t['fii_streak_min']}d ({self.fii_streak_days}d)")

        if len(indicators) >= 3:
            return Scenario(
                name="asian_contagion",
                severity="ACTIVE",
                confidence="HIGH" if len(indicators) >= 4 else "MEDIUM",
                indicators=indicators,
            )
        return None

    def _check_geopolitical(self) -> Optional[Scenario]:
        """Pattern: Brent spike + Gold surge + VIX fear + INR pressure.

        Historical parallels: Russia-Ukraine (2022), Iran escalation, Gulf conflicts.
        """
        t = self.GEOPOLITICAL
        if not all([self.brent, self.gold]):
            return None

        use_vix = self.cboe_vix or self.vix

        indicators = []
        if self.brent and self.brent >= t["brent_min"]:
            indicators.append(f"Brent ≥${t['brent_min']} (${self.brent:.1f})")
        if self.gold and self.gold >= t["gold_min"]:
            indicators.append(f"Gold ≥${t['gold_min']} (${self.gold:.0f})")
        if use_vix and use_vix >= t["vix_min"]:
            name = "CBOE VIX" if self.cboe_vix else "India VIX"
            indicators.append(f"{name} ≥{t['vix_min']} ({use_vix:.1f})")
        if self.usdinr and self.usdinr >= t["usdinr_min"]:
            indicators.append(f"USDINR ≥{t['usdinr_min']} (₹{self.usdinr:.1f})")

        if len(indicators) >= 3:
            return Scenario(
                name="geopolitical",
                severity="ACTIVE",
                confidence="HIGH" if len(indicators) >= 4 else "MEDIUM",
                indicators=indicators,
            )
        return None

    def _check_fii_exodus(self) -> Optional[Scenario]:
        """Pattern: Heavy FII selling + INR depreciation + DXY strength.

        Historical parallels: 2020 COVID crash, 2022 rate hike exodus, 2024 election selloff.
        """
        t = self.FII_EXODUS
        if not all([self.usdinr, self.dxy]):
            return None

        # Check FII selling using best available data
        fii_selling = False
        fii_detail = ""
        if self.fii_5d_total is not None and self.fii_5d_total < t["fii_net_max"]:
            fii_selling = True
            fii_detail = f"FII 5d: ₹{self.fii_5d_total:+,.0f}Cr"
        elif self.fii_net is not None and self.fii_net < t["fii_net_max"]:
            fii_selling = True
            fii_detail = f"FII: ₹{self.fii_net:+,.0f}Cr"
        elif self.fii_streak_days >= t["fii_streak_min"]:
            fii_selling = True
            fii_detail = f"FII sell streak: {self.fii_streak_days}d"

        if not fii_selling:
            return None

        indicators = [fii_detail]

        if self.usdinr and self.usdinr >= t["usdinr_min"]:
            indicators.append(f"USDINR ≥{t['usdinr_min']} (₹{self.usdinr:.1f})")
        if self.dxy and self.dxy >= t["dxy_min"]:
            indicators.append(f"DXY ≥{t['dxy_min']} ({self.dxy:.1f})")

        confidence = "HIGH" if (self.fii_5d_total is not None and
                                 self.fii_5d_total < t["fii_net_max"] * 2) else "MEDIUM"
        return Scenario(
            name="fii_exodus",
            severity="ACTIVE",
            confidence=confidence,
            indicators=indicators,
        )

    def _check_usd_crisis(self) -> Optional[Scenario]:
        """Pattern: Extreme DXY + extreme USDINR + FII outflows.

        Historical parallels: 2013 Taper Tantrum, 2024-25 INR pressure.
        """
        t = self.USD_CRISIS
        if not all([self.dxy, self.usdinr]):
            return None

        indicators = []
        if self.dxy and self.dxy >= t["dxy_min"]:
            indicators.append(f"DXY ≥{t['dxy_min']} ({self.dxy:.1f})")
        if self.usdinr and self.usdinr >= t["usdinr_min"]:
            indicators.append(f"USDINR ≥{t['usdinr_min']} (₹{self.usdinr:.1f})")
        if self.fii_net is not None and self.fii_net < 0:
            indicators.append(f"FII outflow (₹{self.fii_net:+,.0f}Cr)")

        if len(indicators) >= 2:
            return Scenario(
                name="usd_crisis",
                severity="ACTIVE",
                confidence="HIGH" if len(indicators) >= 3 else "MEDIUM",
                indicators=indicators,
            )
        return None

    def _check_oil_shock(self) -> Optional[Scenario]:
        """Pattern: Brent spike + Gold flight + VIX panic.

        Historical parallels: 2022 Russia-Ukraine, 2008 oil spike.
        """
        t = self.OIL_SHOCK
        if not all([self.brent, self.gold]):
            return None

        use_vix = self.cboe_vix or self.vix

        indicators = []
        if self.brent and self.brent >= t["brent_min"]:
            indicators.append(f"Brent ≥${t['brent_min']} (${self.brent:.1f})")
        if self.gold and self.gold >= t["gold_min"]:
            indicators.append(f"Gold ≥${t['gold_min']} (${self.gold:.0f})")
        if use_vix and use_vix >= t["vix_min"]:
            name = "CBOE VIX" if self.cboe_vix else "India VIX"
            indicators.append(f"{name} ≥{t['vix_min']} ({use_vix:.1f})")

        if len(indicators) >= 2:
            return Scenario(
                name="oil_shock",
                severity="ACTIVE",
                confidence="HIGH" if len(indicators) >= 3 else "MEDIUM",
                indicators=indicators,
            )
        return None


# ═════════════════════════════════════════════════════════════════════
# HISTORICAL CLONE LOOKUP — Dynamic nearest-neighbor matching
# ═════════════════════════════════════════════════════════════════════

def find_historical_clones(state: MarketState, max_clones: int = 3) -> List[Dict]:
    """
    Find historical dates with macro conditions closest to current state.

    Queries Supabase market_state table for historical records, computes
    normalized Euclidean distance across key variables (USDINR, Brent,
    VIX, DXY, Gold), and returns the closest matches with forward context.

    Returns list of dicts (one per clone) with:
      - date, similarity, macro snapshot, regime, confidence

    Falls back to empty list if DB unavailable — caller should suppress
    the clones section entirely in that case.
    """
    try:
        from src.db import get_market_state
        from datetime import datetime, timedelta

        current = {
            "usdinr": state.macro.usdinr,
            "brent": state.macro.brent,
            "vix": state.macro.vix,
            "dxy": state.macro.dxy,
            "gold": state.macro.gold,
        }

        # Skip if essential data missing
        if not all([current["usdinr"], current["brent"], current["vix"], current["dxy"]]):
            return []

        # Fetch historical states (last 3 years)
        today = datetime.now()
        candidates = []
        for d in range(1, 1095):  # ~3 years
            ts = (today - timedelta(days=d)).strftime("%Y-%m-%d")
            ms = get_market_state(ts)
            if ms and ms.get("macro"):
                m = ms["macro"]
                h_usdinr = m.get("usdinr")
                h_brent = m.get("brent")
                h_vix = m.get("vix")
                h_dxy = m.get("dxy")
                h_gold = m.get("gold")
                if h_usdinr and h_brent and h_vix and h_dxy:
                    # Normalized Euclidean distance (weights: USDINR 0.3, Brent 0.3, VIX 0.2, DXY 0.2)
                    d_usdinr = ((current["usdinr"] - h_usdinr) / max(h_usdinr, 1)) ** 2 * 0.3
                    d_brent = ((current["brent"] - h_brent) / max(h_brent, 1)) ** 2 * 0.3
                    d_vix = ((current["vix"] - h_vix) / max(h_vix, 1)) ** 2 * 0.2
                    d_dxy = ((current["dxy"] - h_dxy) / max(h_dxy, 1)) ** 2 * 0.2
                    distance = (d_usdinr + d_brent + d_vix + d_dxy) ** 0.5
                    candidates.append({
                        "date": ts,
                        "distance": distance,
                        "usdinr": h_usdinr,
                        "brent": h_brent,
                        "vix": h_vix,
                        "dxy": h_dxy,
                        "gold": h_gold,
                        "regime": ms.get("final_regime"),
                        "bull_bear_score": ms.get("bull_bear_normalized"),
                    })

        if not candidates:
            return []

        # Sort by distance (lowest = closest match)
        candidates.sort(key=lambda x: x["distance"])

        # Return top N, excluding same-week dates to avoid clustering
        selected = []
        seen_weeks = set()
        for c in candidates:
            week_key = c["date"][:7]  # YYYY-MM
            if week_key not in seen_weeks:
                c["similarity"] = round((1 - c["distance"]) * 100, 1)
                del c["distance"]
                selected.append(c)
                seen_weeks.add(week_key)
            if len(selected) >= max_clones:
                break

        return selected

    except Exception as e:
        print(f"⚠️ Historical clone lookup failed: {e}")
        return []
