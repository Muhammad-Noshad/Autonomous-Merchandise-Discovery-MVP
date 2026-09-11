"""Shared workflow values that must remain consistent across all stages."""

from enum import Enum


class RunStatus(str, Enum):
    """Lifecycle states for a complete discovery run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StageStatus(str, Enum):
    """Lifecycle states for one stage execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
