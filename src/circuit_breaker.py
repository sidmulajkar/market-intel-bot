"""
Circuit Breaker — prevents cascading failures from degraded external services.

Three states: CLOSED (normal) → OPEN (tripped) → HALF_OPEN (testing recovery).

Usage:
    breaker = CircuitBreaker(name="options_api", failure_threshold=3, recovery_timeout=300)

    @breaker
    def fetch_options_data():
        ...

Or manually:
    with breaker:
        fetch_options_data()

When OPEN, decorated functions return the default_return value immediately
without executing the body.
"""
import time
import functools
from typing import Any, Callable, Optional


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is tripped."""
    pass


class CircuitBreaker:
    """Three-state circuit breaker with automatic recovery testing."""

    _instances: dict = {}  # singleton per name

    def __new__(cls, name: str, **kwargs):
        if name in cls._instances:
            return cls._instances[name]
        instance = super().__new__(cls)
        cls._instances[name] = instance
        return instance

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 300,  # 5 minutes
        default_return: Any = None,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.default_return = default_return

        self._failure_count = 0
        self._state = "CLOSED"
        self._last_failure_time: Optional[float] = None

    @property
    def state(self) -> str:
        if self._state == "OPEN" and self._last_failure_time:
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = "HALF_OPEN"
                print(f"   ⚡ Circuit breaker '{self.name}': HALF_OPEN (testing recovery)")
        return self._state

    def record_success(self) -> None:
        if self._state == "HALF_OPEN":
            print(f"   ✅ Circuit breaker '{self.name}': CLOSED (recovered)")
        self._failure_count = 0
        self._state = "CLOSED"

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self.failure_threshold:
            if self._state != "OPEN":
                print(f"   🚨 Circuit breaker '{self.name}': OPEN ({self._failure_count} failures)")
            self._state = "OPEN"

    def __call__(self, func: Callable) -> Callable:
        """Decorate a function with circuit breaker protection."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if self.state == "OPEN":
                print(f"   ⚡ Circuit breaker '{self.name}': OPEN — skipping {func.__name__}")
                return self.default_return
            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                self.record_failure()
                raise
        return wrapper

    def __enter__(self):
        if self.state == "OPEN":
            raise CircuitBreakerOpen(f"Circuit breaker '{self.name}' is open")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.record_failure()
        else:
            self.record_success()
        return False

    def reset(self) -> None:
        """Force reset to CLOSED state."""
        self._failure_count = 0
        self._state = "CLOSED"
        self._last_failure_time = None

    def status(self) -> dict:
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self._failure_count,
            "threshold": self.failure_threshold,
        }
