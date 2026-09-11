"""Niche and intermediate discovery-candidate page entrypoint."""

import streamlit as st
from pymongo.errors import PyMongoError

from merchandise_discovery.application.discovery_service import DiscoveryService
from merchandise_discovery.domain.models.artifacts import IdentityIntersection
from merchandise_discovery.shared.errors import RepositoryError
from merchandise_discovery.ui.pages.placeholder import render_placeholder_page


def _render_intersection(intersection: IdentityIntersection) -> None:
    """Render one candidate with its score, hypothesis, and deterministic filter outcome."""

    accepted = intersection.eligible_for_research
    status = "Accepted for research" if accepted else "Rejected"
    color = "#22C55E" if accepted else "#EF4444"
    with st.container(border=True):
        st.markdown(f"**{' + '.join(intersection.identities)}**")
        st.markdown(
            f'<span style="color:{color}; font-weight:650;">●&nbsp; {status}</span>',
            unsafe_allow_html=True,
        )
        if intersection.coherence_score is not None:
            st.caption(f"Coherence score: {intersection.coherence_score:.2f} / 10")
        for hypothesis in intersection.experience_hypotheses:
            st.write(hypothesis)
        if intersection.filter_reason:
            st.warning(intersection.filter_reason)


def render_niches(discovery_service: DiscoveryService | None = None) -> None:
    """Render persisted Stage 5 candidates or the future research placeholder."""

    if discovery_service is None:
        render_placeholder_page(
            "Niches",
            "Compare researched opportunities and trace each signal back to public evidence.",
            [
                ("Validated niches", "Research-backed niches will be ranked here."),
                ("Evidence", "Citations, excerpts, and retrieval timestamps will appear here."),
                ("Opportunity scores", "Reproducible score breakdowns will appear here."),
            ],
        )
        return

    run_id = st.session_state.get("selected_run_id")
    st.markdown('<div class="opus-breadcrumb">Workspace</div>', unsafe_allow_html=True)
    st.title("Niches")
    st.caption("Inspect the identity intersections that passed the deterministic pre-research filter.")
    if not run_id:
        st.info("Open a run first to inspect its discovery candidates.")
        return

    try:
        intersections = discovery_service.list_intersections(run_id)
    except (PyMongoError, RepositoryError):
        st.error("Discovery candidates could not be loaded from MongoDB.")
        return
    if not intersections:
        st.info("No persisted discovery candidates are available for this run yet.")
        return

    accepted = sum(intersection.eligible_for_research for intersection in intersections)
    metric_left, metric_right = st.columns(2)
    metric_left.metric("Accepted", accepted)
    metric_right.metric("Rejected", len(intersections) - accepted)
    for intersection in intersections:
        _render_intersection(intersection)
