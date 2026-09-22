"""Shared workflow values that must remain consistent across all stages."""

from enum import Enum


class RunStatus(str, Enum):
    """Lifecycle states for a complete discovery run."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineVariant(str, Enum):
    """Selectable discovery strategies used for controlled pipeline comparisons."""

    BASELINE = "baseline"
    COMPACT_RESEARCH_FIRST = "compact_research_first"
    SOCIAL_BEHAVIOR_TEXT = "social_behavior_text"


class SocialSource(str, Enum):
    """Public social platforms that the one-stage behavior pipeline may search."""

    REDDIT = "reddit"
    X = "x"


class SeedCategory(str, Enum):
    """The three controlled axes used to build discovery intersections."""

    AUDIENCE = "audience"
    INTEREST = "interest"
    VALUE = "value"


class StageStatus(str, Enum):
    """Lifecycle states for one stage execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ConceptVerdict(str, Enum):
    """Allowed outcomes from the concept critique stage."""

    KEEP = "keep"
    REJECT = "reject"


class ArtworkDecision(str, Enum):
    """Allowed outcomes from artwork quality assurance."""

    ACCEPT = "accept"
    REJECT = "reject"
    REGENERATE = "regenerate"


class ApprovalDecision(str, Enum):
    """Allowed final human-review decisions."""

    APPROVE = "approve"
    REJECT = "reject"
    REGENERATE = "regenerate"
    REQUEST_ADJUSTMENT = "request_adjustment"
