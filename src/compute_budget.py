"""
Compute Budget & Graceful Degradation — progressive block dropping when time runs out.

GitHub Actions runners have a hard 3-4 minute limit. This module tracks elapsed time
and provides:
  1. Time budget with per-stage warnings
  2. Progressive block priority ranking (drop lowest-priority first)
  3. Fallback messages for skipped blocks

Usage:
    budget = ComputeBudget(max_seconds=180)
    budget.start_stage("data_fetch")
    ... fetch data ...
    budget.end_stage("data_fetch")
    if budget.should_skip_block("block_9"):
        # Use fallback instead of computing
        ...
"""
import time
from typing import Dict, List, Optional


# Block priority ranking — lower number = higher priority (computed first, dropped last)
# Core blocks always computed; peripheral blocks dropped when time is tight
BLOCK_PRIORITY: Dict[str, int] = {
    # Core — never dropped
    "block_0": 1,   # Market Posture (bull/bear score)
    "block_1": 2,   # Global Indices + Breadth
    "block_2": 3,   # Macro + Valuation (9 anchors)
    "block_4": 4,   # FII/DII Flows
    "block_5": 5,   # Derivatives (PCR, GEX, OI)
    "block_6": 6,   # News (with AI sentiment)

    # Important — dropped only when very tight
    "block_3": 7,   # Sector FPI
    "block_7": 8,   # Insider Activity
    "block_8": 9,   # Watchlist + TA
    "block_10": 10, # MF Flows

    # Peripheral — dropped first
    "block_9": 11,  # Macro Calendar (static dates)
}

STAGE_ORDER = [
    "data_fetch",
    "context_engine",
    "formatters",
    "ai_generation",
    "validation",
    "telegram_send",
]

STAGE_DEADLINE_FRAC = {
    "data_fetch":      0.30,  # Must finish by 30% of budget
    "context_engine":  0.50,  # 50%
    "formatters":      0.75,  # 75%
    "ai_generation":   0.90,  # 90%
    "validation":      0.95,  # 95%
    "telegram_send":   1.00,  # 100%
}


class ComputeBudget:
    """Track compute time and provide degradation decisions."""

    def __init__(self, max_seconds: int = 180):
        self.max_seconds = max_seconds
        self.start_time: Optional[float] = None
        self.current_stage: Optional[str] = None
        self.stage_times: Dict[str, float] = {}
        self._started = False

    # ── Lifecycle ───────────────────────────────────────────────

    def start(self):
        """Start overall budget timer."""
        self.start_time = time.time()
        self._started = True

    @property
    def elapsed(self) -> float:
        """Seconds elapsed since start."""
        if not self._started:
            return 0
        return time.time() - self.start_time

    @property
    def remaining(self) -> float:
        """Seconds remaining in budget."""
        return max(0, self.max_seconds - self.elapsed)

    @property
    def pct_used(self) -> float:
        """Percentage of budget consumed."""
        return min(100, (self.elapsed / self.max_seconds) * 100) if self.max_seconds else 0

    # ── Stage tracking ──────────────────────────────────────────

    def start_stage(self, stage: str):
        self.current_stage = stage
        self.stage_times[stage] = time.time()

    def end_stage(self, stage: str):
        if stage in self.stage_times:
            elapsed = time.time() - self.stage_times[stage]
            self.stage_times[stage] = elapsed
        self.current_stage = None

    # ── Degradation decisions ───────────────────────────────────

    def should_skip_block(self, block_name: str) -> bool:
        """
        Should this block be skipped given current time budget?
        Uses stage-based + absolute thresholds:
          - Past 75%: drop peripheral blocks (priority >= 10)
          - Past 90%: drop all non-core blocks (priority >= 7)
          - Past 95%: only send core blocks (priority <= 3)
        """
        pct = self.pct_used
        priority = BLOCK_PRIORITY.get(block_name, 99)

        if pct >= 95:
            return priority > 3  # Only blocks 0,1,2
        elif pct >= 90:
            return priority >= 7  # Drop block_3 and below
        elif pct >= 75:
            return priority >= 10  # Drop only block_9, block_10
        return False

    def get_skippable_blocks(self) -> List[str]:
        """Return list of blocks that should be skipped right now."""
        return [b for b in BLOCK_PRIORITY if self.should_skip_block(b)]

    # ── Warnings ────────────────────────────────────────────────

    def check_budget_health(self) -> Optional[str]:
        """
        Return a warning string if budget is tight, None otherwise.
        Called at key checkpoints to decide whether to accelerate.
        """
        pct = self.pct_used
        remaining = self.remaining

        if pct >= 90:
            return f"CRITICAL: {remaining:.0f}s remaining — sending core blocks only"
        elif pct >= 75:
            skipped = self.get_skippable_blocks()
            if skipped:
                return f"WARNING: {remaining:.0f}s remaining — dropping {', '.join(skipped)}"
        elif pct >= 60:
            return f"Caution: {remaining:.0f}s remaining ({pct:.0f}% used)"
        return None

    def get_status(self) -> Dict:
        """Budget status dict for logging/AI prompt injection."""
        return {
            "elapsed": round(self.elapsed, 1),
            "remaining": round(self.remaining, 1),
            "pct_used": round(self.pct_used, 0),
            "current_stage": self.current_stage,
            "stage_times": {k: round(v, 1) if isinstance(v, (int, float)) else v
                           for k, v in self.stage_times.items()},
            "skippable": self.get_skippable_blocks(),
            "health": self.check_budget_health(),
        }

    def format_budget_for_prompt(self) -> str:
        """Format budget status for AI prompt injection."""
        s = self.get_status()
        health = s.get("health", "")
        if not health:
            return ""
        lines = [
            f"\n[COMPUTE BUDGET: {s['elapsed']:.0f}s elapsed, {s['remaining']:.0f}s remaining]",
        ]
        if s["skippable"]:
            lines.append(f"  Dropped blocks: {', '.join(s['skippable'])}")
        return "\n".join(lines)


def get_block_fallback(block_name: str) -> str:
    """Return a fallback string for a skipped block."""
    fallbacks = {
        "block_3": "Sector FPI: Data unavailable — compute budget exceeded",
        "block_7": "Insider Activity: Data unavailable — compute budget exceeded",
        "block_8": "Watchlist + TA: Technical analysis skipped — compute budget exceeded",
        "block_9": "Macro Calendar: Upcoming events skipped — compute budget exceeded",
        "block_10": "MF Flows: Mutual fund flows skipped — compute budget exceeded",
    }
    return fallbacks.get(block_name, f"{block_name}: Skipped — compute budget exceeded")
