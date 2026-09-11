"""Artwork review page for persisted human approval decisions."""

import json

import streamlit as st
from pymongo.errors import PyMongoError

from merchandise_discovery.application.discovery_service import DiscoveryService
from merchandise_discovery.application.review_service import ReviewService, ReviewState
from merchandise_discovery.domain.models.artifacts import Artwork, HumanReview
from merchandise_discovery.domain.models.common import ApprovalDecision
from merchandise_discovery.shared.errors import RepositoryError
from merchandise_discovery.ui.pages.placeholder import render_placeholder_page

DECISION_LABELS = {
    ApprovalDecision.APPROVE: "Approve",
    ApprovalDecision.REJECT: "Reject",
    ApprovalDecision.REGENERATE: "Request regeneration",
    ApprovalDecision.REQUEST_ADJUSTMENT: "Request adjustment",
}


def _qa_value(artwork: Artwork, key: str) -> str:
    """Return one QA score without coupling the page to the critique dictionary shape."""

    value = artwork.critique.get(key)
    return f"{float(value):.1f}" if isinstance(value, (float, int)) else "—"


def _render_artwork_card(
    artwork: Artwork,
    current_review: HumanReview | None,
    review_service: ReviewService,
) -> None:
    """Render one candidate and persist its latest reviewer decision from a scoped form."""

    decision = current_review.decision.value.replace("_", " ").title() if current_review else "Awaiting review"
    decision_color = "#22C55E" if current_review and current_review.decision == ApprovalDecision.APPROVE else "#F59E0B"
    with st.container(border=True):
        st.markdown(f"**Artwork candidate · {artwork.artwork_id[:8]}**")
        st.markdown(
            f'<span style="color:{decision_color}; font-weight:650;">{decision}</span>',
            unsafe_allow_html=True,
        )
        st.caption(
            f"Concept {artwork.concept_id} · {artwork.mime_type or 'Unknown format'} · "
            f"{artwork.width or '—'} × {artwork.height or '—'}"
        )
        if artwork.source_url:
            # Hosted provider URLs make real images inspectable during the demo; a broken URL must
            # not prevent the reviewer from seeing metadata and recording a decision.
            try:
                st.image(artwork.source_url, caption="Generated artwork", width=420)
            except (OSError, RuntimeError, ValueError):
                st.warning("The provider image could not be previewed; use the reference link below.")
        metrics = [
            ("Readability", _qa_value(artwork, "readability")),
            ("Composition", _qa_value(artwork, "composition")),
            ("Quality", _qa_value(artwork, "quality")),
            ("Alignment", _qa_value(artwork, "alignment")),
        ]
        columns = st.columns(len(metrics))
        for column, (label, value) in zip(columns, metrics):
            column.metric(label, value)
        if artwork.source_url:
            st.markdown(f"[Open provider reference]({artwork.source_url})")
        issues = artwork.critique.get("issues", [])
        if issues:
            st.warning("QA issues: " + "; ".join(str(issue) for issue in issues))
        if current_review:
            st.caption(
                f"Last reviewed by {current_review.reviewer} on "
                f"{current_review.reviewed_at.astimezone().strftime('%Y-%m-%d %H:%M')}"
            )
            if current_review.notes:
                st.write(current_review.notes)

        with st.form(f"review-{artwork.artwork_id}"):
            options = list(DECISION_LABELS.values())
            current_label = DECISION_LABELS.get(current_review.decision) if current_review else options[0]
            selected_label = st.selectbox(
                "Decision",
                options,
                index=options.index(current_label),
                key=f"decision-{artwork.artwork_id}",
            )
            notes = st.text_area(
                "Notes",
                value=current_review.notes or "" if current_review else "",
                key=f"notes-{artwork.artwork_id}",
                placeholder="Explain the decision or requested change.",
            )
            submitted = st.form_submit_button("Save decision", use_container_width=True)
        if submitted:
            try:
                selected_decision = next(
                    decision for decision, label in DECISION_LABELS.items() if label == selected_label
                )
                submission = review_service.submit_review(
                    run_id=artwork.run_id,
                    artwork_id=artwork.artwork_id,
                    decision=selected_decision,
                    reviewer=st.session_state.get("reviewer_name", ""),
                    notes=notes,
                )
                st.session_state["review_saved"] = submission.review.artwork_id
                st.rerun()
            except (PyMongoError, RepositoryError, ValueError) as error:
                st.error(f"Review could not be saved: {error}")


def _render_queue(state: ReviewState, review_service: ReviewService) -> None:
    """Render review progress and every artwork candidate in a stable order."""

    summary = state.summary
    _columns = st.columns(4)
    _columns[0].metric("Candidates", summary.required_count)
    _columns[1].metric("Reviewed", summary.reviewed_count)
    _columns[2].metric("Approved", summary.approved_count)
    _columns[3].metric("Rejected", summary.rejected_count)
    if summary.complete:
        st.success("All artwork candidates have terminal decisions. This run is complete.")
    else:
        remaining = len(summary.pending_artwork_ids) + len(summary.open_artwork_ids)
        st.info(f"{remaining} artwork decision(s) still require review or follow-up.")
    approved = [
        {
            "artwork": artwork.model_dump(mode="json"),
            "review": state.latest_reviews[artwork.artwork_id].model_dump(mode="json"),
        }
        for artwork in state.artworks
        if artwork.artwork_id in state.latest_reviews
        and state.latest_reviews[artwork.artwork_id].decision == ApprovalDecision.APPROVE
    ]
    if approved:
        # Export is metadata-only in the MVP because fixture/object-storage binaries are not local
        # files. The payload still preserves the references needed by a downstream handoff.
        st.download_button(
            "Download approved metadata",
            data=json.dumps({"run_id": state.run.run_id, "approved": approved}, indent=2),
            file_name=f"{state.run.run_id}-approved-artwork.json",
            mime="application/json",
            use_container_width=True,
        )
    for artwork in state.artworks:
        _render_artwork_card(artwork, state.latest_reviews.get(artwork.artwork_id), review_service)


def render_artwork_review(
    discovery_service: DiscoveryService | None = None,
    review_service: ReviewService | None = None,
) -> None:
    """Render the persisted approval queue or the explicit fixture-mode placeholder."""

    if discovery_service is None or review_service is None:
        render_placeholder_page(
            "Artwork Review",
            "Review generated artwork candidates and record the final human decision.",
            [
                ("Candidates", "Artwork variants and generation metadata will appear here."),
                ("QA results", "Readability, composition, and format checks will appear here."),
                ("Approval queue", "Connect MongoDB to record approve, reject, regenerate, and adjustment decisions."),
            ],
        )
        return

    run_id = st.session_state.get("selected_run_id")
    st.markdown('<div class="opus-breadcrumb">Workspace</div>', unsafe_allow_html=True)
    st.title("Artwork Review")
    st.caption("Review QA-passed candidates and persist the final human decision.")
    if not run_id:
        st.info("Open a run first to inspect its artwork.")
        return
    st.text_input("Reviewer name", key="reviewer_name", placeholder="Who is making this decision?")
    try:
        state = review_service.get_state(run_id)
    except (PyMongoError, RepositoryError, ValueError) as error:
        st.error(f"Artwork review could not be loaded: {error}")
        return
    if not state.artworks:
        st.info("No artwork candidates are available until Stages 13-16 complete.")
        return
    if st.session_state.pop("review_saved", None):
        st.success("Review decision saved.")
    _render_queue(state, review_service)
