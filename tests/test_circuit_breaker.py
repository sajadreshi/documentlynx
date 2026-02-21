"""Unit tests for app.circuit_breaker module."""

import time
from unittest.mock import patch

from app.circuit_breaker import CircuitBreaker, CircuitState, get_breaker, _breakers
from app.exceptions import CircuitBreakerOpenError


class TestCircuitBreaker:
    """Tests for the CircuitBreaker class."""

    def test_starts_closed(self):
        """A new circuit breaker should start in the CLOSED state."""
        cb = CircuitBreaker("test-service")

        assert cb.state == CircuitState.CLOSED

    def test_opens_after_threshold_failures(self):
        """Circuit should transition to OPEN after failure_threshold consecutive failures."""
        cb = CircuitBreaker("test-service", failure_threshold=3)

        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_rejects_when_open(self):
        """check() should raise CircuitBreakerOpenError when the circuit is OPEN."""
        cb = CircuitBreaker("test-service", failure_threshold=2, recovery_timeout=60.0)

        # Drive to OPEN
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        try:
            cb.check()
            assert False, "Should have raised CircuitBreakerOpenError"
        except CircuitBreakerOpenError as exc:
            assert exc.service_name == "test-service"
            assert exc.retry_after > 0

    @patch("app.circuit_breaker.time.monotonic")
    def test_transitions_to_half_open_after_timeout(self, mock_monotonic):
        """After recovery_timeout elapses the circuit should move to HALF_OPEN."""
        cb = CircuitBreaker("test-service", failure_threshold=2, recovery_timeout=30.0)

        # Time when failures happen
        mock_monotonic.return_value = 100.0
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Advance time past recovery_timeout
        mock_monotonic.return_value = 131.0  # 100 + 31 > 30
        assert cb.state == CircuitState.HALF_OPEN

    @patch("app.circuit_breaker.time.monotonic")
    def test_closes_on_success_from_half_open(self, mock_monotonic):
        """A success recorded in HALF_OPEN should transition back to CLOSED."""
        cb = CircuitBreaker("test-service", failure_threshold=2, recovery_timeout=10.0)

        # Open the circuit
        mock_monotonic.return_value = 100.0
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Move to HALF_OPEN
        mock_monotonic.return_value = 111.0
        assert cb.state == CircuitState.HALF_OPEN

        # Record success -> should go back to CLOSED
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_get_breaker_returns_same_instance(self):
        """get_breaker() should return the same instance for the same service_name."""
        # Use a unique name to avoid collisions with other tests
        name = "__test_singleton__"

        # Clean up in case a previous test run left it around
        _breakers.pop(name, None)

        breaker_a = get_breaker(name)
        breaker_b = get_breaker(name)

        assert breaker_a is breaker_b

        # Cleanup
        _breakers.pop(name, None)
