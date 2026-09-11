"""Persistence operations for stage execution history and retry metadata."""


class StageExecutionRepository:
    """Owns MongoDB queries for stage status, attempts, errors, usage, and versioning."""

