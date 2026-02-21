"""Simple circuit breaker for external service calls."""

import logging
import threading
import time
from enum import Enum

from app.exceptions import CircuitBreakerOpenError

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Track failures per service and reject calls when too many failures occur.

    States:
        CLOSED   — normal operation, failures are counted.
        OPEN     — calls are rejected immediately after ``failure_threshold``
                   consecutive failures. Transitions to HALF_OPEN after
                   ``recovery_timeout`` seconds.
        HALF_OPEN — one trial call is allowed through. Success → CLOSED,
                    failure → OPEN (timer restarts).
    """

    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
    ):
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                elapsed = time.monotonic() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    logger.info(
                        "Circuit breaker for '%s' moved to HALF_OPEN after %.1fs",
                        self.service_name,
                        elapsed,
                    )
            return self._state

    def record_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            if self._state != CircuitState.CLOSED:
                logger.info(
                    "Circuit breaker for '%s' is now CLOSED (success recorded)",
                    self.service_name,
                )
            self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker for '%s' is now OPEN after %d failures",
                    self.service_name,
                    self._failure_count,
                )

    def check(self) -> None:
        """Raise ``CircuitBreakerOpenError`` if the circuit is OPEN."""
        current_state = self.state  # triggers OPEN → HALF_OPEN transition
        if current_state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            retry_after = max(0.0, self.recovery_timeout - elapsed)
            raise CircuitBreakerOpenError(self.service_name, retry_after)


# Global registry of circuit breakers keyed by service name.
_breakers: dict[str, CircuitBreaker] = {}
_registry_lock = threading.Lock()


def get_breaker(
    service_name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
) -> CircuitBreaker:
    """Return (or create) the circuit breaker for *service_name*."""
    with _registry_lock:
        if service_name not in _breakers:
            _breakers[service_name] = CircuitBreaker(
                service_name, failure_threshold, recovery_timeout
            )
        return _breakers[service_name]
