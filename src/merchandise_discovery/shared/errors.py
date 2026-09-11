"""Application-specific error types used for predictable failure handling."""


class RepositoryError(RuntimeError):
    """Base error for persistence failures that should be visible to the workflow layer."""


class DuplicateRecordError(RepositoryError):
    """Raised when an idempotency key already exists."""


class RecordNotFoundError(RepositoryError):
    """Raised when a required persisted record does not exist."""


class ConcurrencyError(RepositoryError):
    """Raised when an optimistic-locking update loses a race with another worker."""


class ConfigurationError(RuntimeError):
    """Raised when a required runtime setting is missing or malformed."""
