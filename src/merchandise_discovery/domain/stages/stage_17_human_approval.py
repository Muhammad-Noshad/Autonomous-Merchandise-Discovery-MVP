"""Stage 17: evaluate human approval state for final artwork candidates.

The browser submits immutable review records through the application service. This stage module
owns only the pure decision rule that determines whether the run is still awaiting input or can be
closed, which keeps workflow completion testable without Streamlit or MongoDB.
"""

from pydantic import BaseModel, Field

from merchandise_discovery.domain.models.artifacts import Artwork, HumanReview
from merchandise_discovery.domain.models.common import ApprovalDecision


class HumanApprovalInput(BaseModel):
    """Artwork candidates and all review records for one workflow run."""

    artworks: list[Artwork]
    reviews: list[HumanReview]


class HumanApprovalOutput(BaseModel):
    """Latest decision state used by the review UI and run-completion service."""

    reviewed_count: int = Field(ge=0)
    required_count: int = Field(ge=0)
    approved_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    pending_artwork_ids: list[str] = Field(default_factory=list)
    open_artwork_ids: list[str] = Field(default_factory=list)
    complete: bool


TERMINAL_DECISIONS = {ApprovalDecision.APPROVE, ApprovalDecision.REJECT}


def execute(input_data: HumanApprovalInput) -> HumanApprovalOutput:
    """Use the newest review per artwork to determine whether human work is complete."""

    latest: dict[str, HumanReview] = {}
    for review in sorted(input_data.reviews, key=lambda item: (item.reviewed_at, item.review_id)):
        latest[review.artwork_id] = review
    pending = [artwork.artwork_id for artwork in input_data.artworks if artwork.artwork_id not in latest]
    open_decisions = [
        artwork.artwork_id
        for artwork in input_data.artworks
        if artwork.artwork_id in latest and latest[artwork.artwork_id].decision not in TERMINAL_DECISIONS
    ]
    approved = sum(
        review.decision == ApprovalDecision.APPROVE
        for review in latest.values()
    )
    rejected = sum(
        review.decision == ApprovalDecision.REJECT
        for review in latest.values()
    )
    return HumanApprovalOutput(
        reviewed_count=len(latest),
        required_count=len(input_data.artworks),
        approved_count=approved,
        rejected_count=rejected,
        pending_artwork_ids=pending,
        open_artwork_ids=open_decisions,
        complete=bool(input_data.artworks) and not pending and not open_decisions,
    )
