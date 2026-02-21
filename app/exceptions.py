"""Typed exceptions for the Doculord pipeline."""


class DoculordError(Exception):
    """Base exception for all Doculord errors."""


class LLMError(DoculordError):
    """Error communicating with an LLM provider."""


class LLMResponseParseError(DoculordError):
    """Failed to parse a structured response from the LLM."""


class DoclingError(DoculordError):
    """Error communicating with the Docling conversion service."""


class StorageError(DoculordError):
    """Error communicating with Google Cloud Storage."""


class EmbeddingError(DoculordError):
    """Error generating vector embeddings."""


class PipelineError(DoculordError):
    """Error in the document processing pipeline."""


class CircuitBreakerOpenError(DoculordError):
    """The circuit breaker is open — calls are being rejected."""

    def __init__(self, service_name: str, retry_after: float = 0):
        self.service_name = service_name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker open for '{service_name}'. "
            f"Retry after {retry_after:.1f}s."
        )
