"""
Unified NSE Session Manager — shared session with TTL
Reduces redundant session creation across multiple modules.
Single session is reused for up to 5 minutes.
"""
import requests
from datetime import datetime
from typing import Optional

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.nseindia.com/",
    "Accept": "application/json",
}

# Module-level state
_session: Optional[requests.Session] = None
_session_time: Optional[datetime] = None
_session_ttl_seconds = 300  # 5 minutes


def get_nse_session() -> requests.Session:
    """Get or create a shared NSE session with fresh cookies."""
    global _session, _session_time

    now = datetime.now()

    # Reuse if fresh
    if _session and _session_time:
        age = (now - _session_time).total_seconds()
        if age < _session_ttl_seconds:
            return _session

    # Create new session
    _session = requests.Session()
    _session.headers.update(NSE_HEADERS)
    try:
        _session.get("https://www.nseindia.com", timeout=10)
    except Exception:
        pass  # Continue even if homepage fails
    _session_time = now

    return _session


def reset_nse_session():
    """Force-reset the session (e.g., after 403 errors)."""
    global _session, _session_time
    _session = None
    _session_time = None


import time

from src.circuit_breaker import CircuitBreaker

_nse_breaker = CircuitBreaker(name="nse_api", failure_threshold=3, recovery_timeout=300, default_return=None)


def nse_get(url: str, timeout: int = 15, retries: int = 1) -> Optional[requests.Response]:
    """
    Make a GET request to NSE API with automatic session management.
    Retries once on 403 (session expired). Circuit breaker trips after 3 failures.
    """
    @_nse_breaker
    def _do_get():
        session = get_nse_session()
        for attempt in range(retries + 1):
            resp = session.get(url, timeout=timeout)
            if resp.status_code == 200:
                return resp
            elif resp.status_code == 403 and attempt < retries:
                reset_nse_session()
                session = get_nse_session()
                continue
            else:
                return resp
        return resp

    result = _do_get()
    if result is None:
        return None  # circuit breaker open
    if not isinstance(result, requests.Response):
        return None
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# FAIL-FAST ERROR BUDGET
# ═══════════════════════════════════════════════════════════════════════════════

import time

class ErrorBudget:
    """
    Fail-fast error budget for job execution.
    Stops trying after max failures or time limit.
    Usage:
        budget = ErrorBudget(max_failures=3, max_time_seconds=180)
        if not budget.can_continue():
            print("Budget exhausted, skipping remaining blocks")
    """
    def __init__(self, max_failures: int = 3, max_time_seconds: int = 180):
        self.failures = 0
        self.max_failures = max_failures
        self.start_time = time.time()
        self.max_time = max_time_seconds

    def can_continue(self) -> bool:
        elapsed = time.time() - self.start_time
        return self.failures < self.max_failures and elapsed < self.max_time

    def record_failure(self):
        self.failures += 1

    def record_success(self):
        pass

    def status(self) -> str:
        elapsed = round(time.time() - self.start_time, 1)
        return f"failures={self.failures}/{self.max_failures}, elapsed={elapsed}s/{self.max_time}s"
