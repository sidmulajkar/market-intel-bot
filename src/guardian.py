"""Guardian 2.0 — 3-tier triage for graceful degradation.

Replaces binary P10 sentinel. Every fetcher reports source health;
Guardian finalizes triage after all fetches complete but before compute.

GREEN  → Full pipeline
YELLOW → Suppress options/GEX, append badge, deterministic AI stub
RED    → Halt, pre-canned alert
"""

from enum import Enum
from typing import Dict, List, Optional


class TriageLevel(Enum):
    GREEN = 1
    YELLOW = 2
    RED = 3


class Guardian:
    """Collect source health reports and finalize triage."""

    def __init__(self, manifest: Optional[dict] = None):
        self.manifest = manifest or {}
        self.issues: List[str] = []
        self._critical_anchors = {"BRENT", "USDINR", "VIX", "DXY"}

    def check_source(self, anchor: str, value, source: str, latency_ms: int) -> None:
        """Called by fetchers after each anchor fetch.

        Args:
            anchor: Anchor name (e.g. 'BRENT', 'USDINR', 'NIFTY')
            value: Parsed float price or None
            source: 'live', 'fallback', or 'cache'
            latency_ms: Time in ms for the fetch
        """
        if latency_ms > 10000 and source == "live":
            self.issues.append(f"{anchor}: timeout ({latency_ms}ms)")

        if value is None:
            self.issues.append(f"{anchor}: null")

        if source == "fallback" and anchor in self._critical_anchors:
            self.issues.append(f"{anchor}: delayed")

    def finalize(self, anchors: Dict[str, float]) -> TriageLevel:
        """Evaluate all source reports and return triage level.

        Args:
            anchors: Dict of anchor name → float price (may contain None for failures)

        Returns:
            TriageLevel.GREEN, YELLOW, or RED
        """
        if self._critical_glitch(anchors):
            return TriageLevel.RED

        total = len(anchors) or 1
        null_count = sum(1 for i in self.issues if "null" in i)
        delay_count = sum(1 for i in self.issues if "delayed" in i or "timeout" in i)
        null_pct = null_count / total

        if null_pct > 0.30:
            return TriageLevel.RED

        if delay_count >= 2 or null_pct > 0.20:
            return TriageLevel.YELLOW

        return TriageLevel.GREEN

    def _critical_glitch(self, a: Dict[str, float]) -> bool:
        """Detect API glitches that produce absurd daily changes."""
        if not a:
            return True

        for anchor in self._critical_anchors:
            cur = a.get(anchor)
            prev_key = f"PREV_{anchor}"
            prev = a.get(prev_key)

            if cur is not None and prev is not None and prev > 0:
                change_pct = abs(cur - prev) / prev * 100
                if anchor in ("BRENT", "USDINR", "DXY") and change_pct > 30:
                    self.issues.append(f"{anchor}: glitch ({change_pct:.0f}% daily change)")
                    return True

        return False

    def get_badge(self) -> str:
        """Return triage badge text for appending to regime line."""
        for issue in self.issues:
            if "delayed" in issue or "timeout" in issue:
                return "⚠️ Delayed/Partial"
        return ""
