"""Retry decorator with exponential backoff for external service calls."""

import functools
import logging
import time
from typing import Sequence, Type

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    exponential_base: float = 2.0,
    retryable_exceptions: Sequence[Type[BaseException]] = (Exception,),
):
    """Decorator that retries a function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts (total calls = max_retries + 1).
        base_delay: Initial delay in seconds before the first retry.
        exponential_base: Multiplier applied to the delay after each retry.
        retryable_exceptions: Tuple of exception types that trigger a retry.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except tuple(retryable_exceptions) as exc:
                    last_exception = exc
                    if attempt < max_retries:
                        delay = base_delay * (exponential_base ** attempt)
                        logger.warning(
                            "Attempt %d/%d for %s failed: %s — retrying in %.1fs",
                            attempt + 1,
                            max_retries + 1,
                            func.__qualname__,
                            exc,
                            delay,
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            "All %d attempts for %s exhausted. Last error: %s",
                            max_retries + 1,
                            func.__qualname__,
                            exc,
                        )
            raise last_exception  # type: ignore[misc]

        return wrapper

    return decorator
