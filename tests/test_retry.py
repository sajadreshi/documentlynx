"""Unit tests for app.retry.retry_with_backoff decorator."""

import time
from unittest.mock import patch, MagicMock

from app.retry import retry_with_backoff


class TestRetryWithBackoff:
    """Tests for the retry_with_backoff decorator."""

    def test_succeeds_on_first_try(self):
        """Function that succeeds immediately should be called exactly once."""
        call_count = 0

        @retry_with_backoff(max_retries=3)
        def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = succeed()

        assert result == "ok"
        assert call_count == 1

    @patch("app.retry.time.sleep", return_value=None)
    def test_retries_on_failure_then_succeeds(self, mock_sleep):
        """Function should retry on exception and return on eventual success."""
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=1.0)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("transient error")
            return "recovered"

        result = flaky()

        assert result == "recovered"
        assert call_count == 3
        # Two failures -> two sleeps (before retry 2 and retry 3)
        assert mock_sleep.call_count == 2

    @patch("app.retry.time.sleep", return_value=None)
    def test_exhausts_retries_and_raises(self, mock_sleep):
        """When all retries are exhausted, the last exception should be raised."""

        @retry_with_backoff(max_retries=2, base_delay=0.1)
        def always_fail():
            raise RuntimeError("permanent failure")

        try:
            always_fail()
            assert False, "Should have raised RuntimeError"
        except RuntimeError as exc:
            assert "permanent failure" in str(exc)

        # max_retries=2 means 3 total calls, 2 sleeps (after attempt 1 and 2)
        assert mock_sleep.call_count == 2

    @patch("app.retry.time.sleep", return_value=None)
    def test_exponential_backoff_timing(self, mock_sleep):
        """Sleep delays should follow exponential backoff: base * (exp_base ** attempt)."""

        @retry_with_backoff(
            max_retries=3,
            base_delay=1.0,
            exponential_base=2.0,
        )
        def always_fail():
            raise Exception("fail")

        try:
            always_fail()
        except Exception:
            pass

        # Delays: attempt 0 -> 1*2^0=1.0, attempt 1 -> 1*2^1=2.0, attempt 2 -> 1*2^2=4.0
        expected_delays = [1.0, 2.0, 4.0]
        actual_delays = [call.args[0] for call in mock_sleep.call_args_list]

        assert actual_delays == expected_delays

    @patch("app.retry.time.sleep", return_value=None)
    def test_only_retries_specified_exceptions(self, mock_sleep):
        """Non-retryable exceptions should propagate immediately without retry."""
        call_count = 0

        @retry_with_backoff(
            max_retries=3,
            base_delay=0.1,
            retryable_exceptions=(ValueError,),
        )
        def raise_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("not retryable")

        try:
            raise_type_error()
            assert False, "Should have raised TypeError"
        except TypeError as exc:
            assert "not retryable" in str(exc)

        # Should have been called only once -- no retries for TypeError
        assert call_count == 1
        assert mock_sleep.call_count == 0
