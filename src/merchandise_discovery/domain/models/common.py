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
    SOCIAL_BEHAVIOR_IDENTITY = "social_behavior_identity"
    SOCIAL_IDENTITY_FOCUSED = "social_identity_focused"
    SOCIAL_IDENTITY_V2 = "social_identity_v2"


class SocialSource(str, Enum):
    """Public social platforms that the social discovery pipelines may search."""

    REDDIT = "reddit"
    X = "x"


class IdentityType(str, Enum):
    """A useful lens for describing the audience represented by a merchandise candidate."""

    OCCUPATION = "occupation"
    ROLE = "role"
    COMMUNITY = "community"
    LIFESTYLE = "lifestyle"
    LIFE_STAGE = "life_stage"
    RELATIONSHIP = "relationship"
    INTEREST = "interest"
    PLACE_BASED = "place_based"
    OTHER = "other"

    @property
    def display_name(self) -> str:
        """Return a human-readable label for the identity-type selector."""

        return {
            IdentityType.OCCUPATION: "Occupation",
            IdentityType.ROLE: "Role",
            IdentityType.COMMUNITY: "Community",
            IdentityType.LIFESTYLE: "Lifestyle",
            IdentityType.LIFE_STAGE: "Life stage",
            IdentityType.RELATIONSHIP: "Relationship / family role",
            IdentityType.INTEREST: "Interest / hobby",
            IdentityType.PLACE_BASED: "Place-based identity",
            IdentityType.OTHER: "Other",
        }[self]

    @property
    def description(self) -> str:
        """Explain which audience identities belong in this category."""

        return {
            IdentityType.OCCUPATION: "a job or profession, such as nurses or teachers",
            IdentityType.ROLE: "a responsibility or position, such as caregiver or volunteer coach",
            IdentityType.COMMUNITY: "membership in a group, such as a local club or mutual-aid group",
            IdentityType.LIFESTYLE: "a recurring way or rhythm of life, such as vanlife or night-shift living",
            IdentityType.LIFE_STAGE: "a period or transition, such as new parenthood, college, or retirement",
            IdentityType.RELATIONSHIP: "an identity shaped by a relationship, such as older sibling or long-distance partner",
            IdentityType.INTEREST: "a sustained hobby or interest, such as birding or tabletop gaming",
            IdentityType.PLACE_BASED: "a shared connection to a place, such as newcomers to a city or longtime residents",
            IdentityType.OTHER: "a well-supported identity that does not fit the categories above",
        }[self]


def identity_type_guidance() -> str:
    """Return the shared identity taxonomy for prompts and UI guidance."""

    return "; ".join(
        f"{identity_type.value}: {identity_type.description}" for identity_type in IdentityType
    )


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
