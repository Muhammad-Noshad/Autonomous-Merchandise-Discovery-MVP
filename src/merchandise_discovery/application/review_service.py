"""Application service for human approval and regeneration decisions.

This service owns the approval use case: it validates ownership, persists an immutable review, and
closes a run only when the Stage 17 decision rule says every artwork candidate is resolved. UI code
receives view state and never writes review or run records directly.
"""

from dataclasses import dataclass

from merchandise_discovery.domain.models.artifacts import Artwork, HumanReview
from merchandise_discovery.domain.models.common import ApprovalDecision, RunStatus
from merchandise_discovery.domain.models.workflow import WorkflowRun
from merchandise_discovery.domain.stages.stage_17_human_approval import (
    HumanApprovalInput,
    HumanApprovalOutput,
)
from merchandise_discovery.domain.stages.stage_17_human_approval import (
    execute as evaluate_approval,
)
from merchandise_discovery.infrastructure.mongo.repositories.artwork_repository import (
    ArtworkRepository,
)
from merchandise_discovery.infrastructure.mongo.repositories.review_repository import (
    ReviewRepository,
)
from merchandise_discovery.infrastructure.mongo.repositories.run_repository import RunRepository
from merchandise_discovery.shared.errors import RecordNotFoundError


@dataclass(frozen=True)
class ReviewState:
    """All data needed to render an approval queue without repository access in Streamlit."""

    run: WorkflowRun
    artworks: list[Artwork]
    latest_reviews: dict[str, HumanReview]
    summary: HumanApprovalOutput


@dataclass(frozen=True)
class ReviewSubmission:
    """Result of one persisted review action."""

    review: HumanReview
    state: ReviewState


class ReviewService:
    """Coordinate immutable human decisions and terminal run completion."""

    def __init__(
        self,
        run_repository: RunRepository,
        artwork_repository: ArtworkRepository,
        review_repository: ReviewRepository,
    ):
        self._runs = run_repository
        self._artworks = artwork_repository
        self._reviews = review_repository

    def get_state(self, run_id: str) -> ReviewState:
        """Assemble artwork candidates, latest decisions, and completion summary for the UI."""

        run = self._runs.get_by_id(run_id)
        if run is None:
            raise RecordNotFoundError(f"Run not found: {run_id}")
        artworks = self._artworks.list_for_run(run_id)
        reviews = self._reviews.list_for_run(run_id)
        latest_reviews = self._latest_reviews(reviews)
        summary = evaluate_approval(
            HumanApprovalInput(artworks=artworks, reviews=reviews)
        )
        return ReviewState(
            run=run,
            artworks=artworks,
            latest_reviews=latest_reviews,
            summary=summary,
        )

    def submit_review(
        self,
        run_id: str,
        artwork_id: str,
        decision: ApprovalDecision,
        *,
        reviewer: str,
        notes: str | None = None,
    ) -> ReviewSubmission:
        """Persist one review and close the run if all latest decisions are terminal."""

        if not reviewer.strip():
            raise ValueError("Reviewer name is required.")
        artwork = self._artworks.get_by_id(artwork_id)
        if artwork is None or artwork.run_id != run_id:
            raise RecordNotFoundError(f"Artwork not found for run: {artwork_id}")
        review = self._reviews.save(
            HumanReview(
                run_id=run_id,
                artwork_id=artwork_id,
                decision=decision,
                reviewer=reviewer.strip(),
                notes=notes.strip() if notes and notes.strip() else None,
            )
        )
        state = self.get_state(run_id)
        if state.summary.complete and state.run.status != RunStatus.COMPLETED:
            completed_run = self._runs.update_status(
                run_id,
                expected_version=state.run.version,
                status=RunStatus.COMPLETED,
                current_stage_number=None,
                last_error=None,
                completed_stages=state.run.total_stages,
            )
            state = ReviewState(
                run=completed_run,
                artworks=state.artworks,
                latest_reviews=state.latest_reviews,
                summary=state.summary,
            )
        return ReviewSubmission(review=review, state=state)

    @staticmethod
    def _latest_reviews(reviews: list[HumanReview]) -> dict[str, HumanReview]:
        """Select the newest immutable decision per artwork with a stable tie-breaker."""

        latest: dict[str, HumanReview] = {}
        for review in sorted(reviews, key=lambda item: (item.reviewed_at, item.review_id)):
            latest[review.artwork_id] = review
        return latest
