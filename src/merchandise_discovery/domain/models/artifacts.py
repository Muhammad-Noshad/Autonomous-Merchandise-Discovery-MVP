"""Typed records for stage artifacts stored outside the workflow aggregate."""

from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from merchandise_discovery.domain.models.common import (
    ApprovalDecision,
    ArtworkDecision,
    ConceptVerdict,
    SeedCategory,
)
from merchandise_discovery.domain.models.workflow import utc_now


class SeedItem(BaseModel):
    """A knowledge-base identity or relationship used as discovery input."""

    model_config = ConfigDict(extra="ignore")

    seed_id: str = Field(default_factory=lambda: str(uuid4()))
    category: SeedCategory
    name: str
    parent: str | None = None
    metadata: dict = Field(default_factory=dict)


class IdentityIntersection(BaseModel):
    """A proposed combination of identities and its initial experience hypothesis."""

    model_config = ConfigDict(extra="ignore")

    intersection_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    identities: list[str]
    source_seed_ids: list[str] = Field(default_factory=list)
    experience_hypotheses: list[str] = Field(default_factory=list)
    coherence_score: float | None = Field(default=None, ge=0, le=10)
    eligible_for_research: bool = False
    filter_reason: str | None = None
    metadata: dict = Field(default_factory=dict)


class Niche(BaseModel):
    """A candidate niche tracked through research and opportunity scoring."""

    model_config = ConfigDict(extra="ignore")

    niche_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    intersection_id: str
    name: str
    coherence_score: float | None = Field(default=None, ge=0, le=10)
    experience_summary: str | None = None
    opportunity_score: float | None = Field(default=None, ge=0, le=100)
    evidence_count: int = Field(default=0, ge=0)
    validated: bool = False


class ResearchEvidence(BaseModel):
    """A source-backed observation associated with a researched niche."""

    model_config = ConfigDict(extra="ignore")

    evidence_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    niche_id: str
    url: str
    title: str
    source: str
    excerpt: str
    retrieved_at: datetime = Field(default_factory=utc_now)
    evidence_type: str = "public_web"


class MerchandiseConcept(BaseModel):
    """An experience-led merchandise concept and its critique result."""

    model_config = ConfigDict(extra="ignore")

    concept_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    niche_id: str
    phrase: str
    description: str
    specific_audience: str = ""
    recognizable_moment: str = ""
    insider_behavior_or_language: str = ""
    emotional_tension: str = ""
    visual_hook: str = ""
    audience_identification_reason: str = ""
    specificity_score: float | None = Field(default=None, ge=0, le=10)
    scores: dict[str, float] = Field(default_factory=dict)
    overall_score: float | None = Field(default=None, ge=0, le=10)
    # Stage 10's critique score and Stage 12's finalist score answer different questions. Keeping
    # both prevents finalist selection from erasing the earlier concept-quality measurement.
    selection_score: float | None = Field(default=None, ge=0, le=10)
    verdict: ConceptVerdict | None = None
    critique: dict = Field(default_factory=dict)
    selected: bool = False
    rank: int | None = Field(default=None, ge=1)


class DesignBrief(BaseModel):
    """Structured visual instructions separating merchandise reasoning from image generation."""

    model_config = ConfigDict(extra="ignore")

    brief_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    concept_id: str
    target_audience: str
    core_concept: str = ""
    exact_phrase: str
    emotional_idea: str
    illustration_style: str
    main_subject: str
    supporting_elements: list[str] = Field(default_factory=list)
    composition: str
    typography_direction: str
    palette_direction: str
    detail_level: str = "moderate"
    intended_merchandise_type: str = "T-shirt or sweatshirt print"
    things_to_avoid: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


class Artwork(BaseModel):
    """Metadata for an image candidate stored in object storage."""

    model_config = ConfigDict(extra="ignore")

    artwork_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    concept_id: str
    brief_id: str
    prompt: str
    storage_key: str | None = None
    source_url: str | None = None
    decision: ArtworkDecision | None = None
    critique: dict = Field(default_factory=dict)
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    mime_type: str | None = None
    file_size_bytes: int | None = Field(default=None, ge=0)
    created_at: datetime = Field(default_factory=utc_now)


class HumanReview(BaseModel):
    """A reviewer decision that closes the human-in-the-loop workflow."""

    model_config = ConfigDict(extra="ignore")

    review_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    artwork_id: str
    decision: ApprovalDecision
    notes: str | None = None
    reviewer: str
    reviewed_at: datetime = Field(default_factory=utc_now)
