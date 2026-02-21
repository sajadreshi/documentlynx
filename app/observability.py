"""Observability utilities for LangSmith tracing.

Provides a safe @traceable decorator that falls back to a no-op
if langsmith is not installed or not configured.
"""

import logging

logger = logging.getLogger(__name__)

try:
    from langsmith import traceable  # type: ignore[import-untyped]
except ImportError:
    logger.debug("langsmith not installed — @traceable will be a no-op")

    def traceable(func=None, *, name=None, tags=None, metadata=None, **kwargs):
        """No-op fallback when langsmith is not installed."""
        if func is not None:
            return func

        def decorator(fn):
            return fn

        return decorator
