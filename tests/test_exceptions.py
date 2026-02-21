"""Unit tests for app.exceptions -- typed exception hierarchy."""

import pytest

from app.exceptions import (
    DoculordError,
    LLMError,
    LLMResponseParseError,
    DoclingError,
    StorageError,
    EmbeddingError,
    PipelineError,
    CircuitBreakerOpenError,
)


# All concrete exception classes that should inherit from DoculordError
_EXCEPTION_CLASSES = [
    LLMError,
    LLMResponseParseError,
    DoclingError,
    StorageError,
    EmbeddingError,
    PipelineError,
    CircuitBreakerOpenError,
]


class TestExceptionHierarchy:
    """Verify the Doculord exception type hierarchy."""

    @pytest.mark.parametrize("exc_cls", _EXCEPTION_CLASSES, ids=lambda c: c.__name__)
    def test_all_exceptions_inherit_from_doculord_error(self, exc_cls):
        """Every typed exception must be a subclass of DoculordError."""
        assert issubclass(exc_cls, DoculordError), (
            f"{exc_cls.__name__} does not inherit from DoculordError"
        )

    def test_circuit_breaker_open_error_has_service_name(self):
        """CircuitBreakerOpenError should store service_name and retry_after."""
        exc = CircuitBreakerOpenError("my-service", retry_after=42.5)

        assert exc.service_name == "my-service"
        assert exc.retry_after == 42.5

    @pytest.mark.parametrize(
        "exc_cls, args, expected_fragment",
        [
            (LLMError, ("provider timeout",), "provider timeout"),
            (LLMResponseParseError, ("bad json",), "bad json"),
            (DoclingError, ("conversion failed",), "conversion failed"),
            (StorageError, ("bucket not found",), "bucket not found"),
            (EmbeddingError, ("dimension mismatch",), "dimension mismatch"),
            (PipelineError, ("step crashed",), "step crashed"),
            (
                CircuitBreakerOpenError,
                ("llm-service", 10.0),
                "Circuit breaker open for 'llm-service'",
            ),
        ],
        ids=lambda x: x.__name__ if isinstance(x, type) else str(x),
    )
    def test_exception_messages(self, exc_cls, args, expected_fragment):
        """Exception str() should contain the expected message fragment."""
        exc = exc_cls(*args)
        assert expected_fragment in str(exc)
