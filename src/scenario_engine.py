"""
Scenario Engine — Multi-variable pattern detection for market regimes.

Detects named scenarios from MarketState + flow metrics data.
All thresholds are data-anchored (yfinance, NSE, Supabase).
No AI speculation — purely deterministic.

Usage:
    detector = ScenarioDetector(state, flow_metrics=ctx.get("flow_metrics"))
    scenarios = detector.detect()
    state.active_scenarios = scenarios
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
