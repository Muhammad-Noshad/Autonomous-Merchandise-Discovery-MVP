"""Tests for the human approval decision rule and application service."""

from unittest.mock import Mock

from merchandise_discovery.application.review_service import ReviewService
from merchandise_discovery.domain.models.artifacts import Artwork, HumanReview
from merchandise_discovery.domain.models.common import ApprovalDecision, ArtworkDecision, RunStatus
from merchandise_discovery.domain.models.workflow import WorkflowRun
from merchandise_discovery.domain.stages.stage_17_human_approval import HumanApprovalInput
from merchandise_discovery.domain.stages.stage_17_human_approval import (
    execute as evaluate_approval,
)


def _artwork(artwork_id: str) -> Artwork:
    """Return a QA-passed candidate for approval tests."""

    return Artwork(
        artwork_id=artwork_id,
        run_id="run-test",
        concept_id="concept-1",
        brief_id="brief-1",
        prompt='Exact text: "Reset Mode".',
        decision=ArtworkDecision.ACCEPT,
    )


def test_approval_requires_terminal_decisions_for_every_candidate() -> None:
    """Approval remains open while any artwork is missing or awaiting follow-up."""

    artwork = [_artwork("artwork-1"), _artwork("artwork-2")]
    review = HumanReview(
        run_id="run-test",
        artwork_id="artwork-1",
        decision=ApprovalDecision.APPROVE,
        reviewer="Reviewer",
    )

    pending = evaluate_approval(HumanApprovalInput(artworks=artwork, reviews=[review]))
    assert pending.complete is False
    assert pending.pending_artwork_ids == ["artwork-2"]

    resolved = evaluate_approval(
        HumanApprovalInput(
            artworks=artwork,
            reviews=[
                review,
                HumanReview(
                    run_id="run-test",
                    artwork_id="artwork-2",
                    decision=ApprovalDecision.REJECT,
                    reviewer="Reviewer",
                ),
            ],
        )
    )
    assert resolved.complete is True
    assert resolved.approved_count == 1
    assert resolved.rejected_count == 1


def test_review_service_persists_review_and_completes_resolved_run() -> None:
    """A final terminal decision updates the run to completed through the repository boundary."""

    run = WorkflowRun(
        run_id="run-test",
        title="Approval test",
        status=RunStatus.RUNNING,
        completed_stages=16,
        current_stage_number=17,
    )
    artwork = _artwork("artwork-1")
    runs = Mock()
    runs.get_by_id.return_value = run
    completed_run = run.model_copy(
        update={"status": RunStatus.COMPLETED, "completed_stages": 17, "current_stage_number": None}
    )
    runs.update_status.return_value = completed_run
    artworks = Mock()
    artworks.get_by_id.return_value = artwork
    artworks.list_for_run.return_value = [artwork]
    reviews = Mock()
    reviews.list_for_run.return_value = []
    service = ReviewService(runs, artworks, reviews)

    review = HumanReview(
        run_id="run-test",
        artwork_id="artwork-1",
        decision=ApprovalDecision.APPROVE,
        reviewer="Reviewer",
    )
    reviews.save.return_value = review
    reviews.list_for_run.return_value = [review]

    submission = service.submit_review(
        "run-test",
        "artwork-1",
        ApprovalDecision.APPROVE,
        reviewer="Reviewer",
    )

    reviews.save.assert_called_once()
    runs.update_status.assert_called_once()
    assert submission.state.summary.complete is True
    assert submission.state.run.status == RunStatus.COMPLETED
    assert submission.state.run.completed_stages == 17
