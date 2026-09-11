"""Artwork review page entrypoint."""

import streamlit as st
from pymongo.errors import PyMongoError

from merchandise_discovery.application.discovery_service import DiscoveryService
from merchandise_discovery.domain.models.artifacts import Artwork
from merchandise_discovery.shared.errors import RepositoryError
from merchandise_discovery.ui.pages.placeholder import render_placeholder_page


def _render_artwork(artwork: Artwork) -> None:
    """Render artwork metadata and QA results without pretending fixture URLs are viewable images."""

    decision = artwork.decision.value.title() if artwork.decision else "Pending QA"
    color = "#22C55E" if decision == "Accept" else "#F59E0B"
    with st.container(border=True):
        st.markdown(f"**Artwork candidate · {artwork.artwork_id[:8]}**")
        st.markdown(
            f'<span style="color:{color}; font-weight:650;">{decision}</span>',
            unsafe_allow_html=True,
        )
        st.caption(f"Concept: {artwork.concept_id} · Storage: {artwork.storage_key or 'Not stored'}")
        metadata = {
            "Format": artwork.mime_type or "Unknown",
            "Dimensions": f"{artwork.width} × {artwork.height}" if artwork.width and artwork.height else "Unknown",
            "File size": f"{artwork.file_size_bytes:,} bytes" if artwork.file_size_bytes else "Unknown",
        }
        columns = st.columns(len(metadata))
        for column, (label, value) in zip(columns, metadata.items()):
            column.metric(label, value)
        if artwork.source_url:
            st.caption(f"Provider reference: {artwork.source_url}")
        issues = artwork.critique.get("issues", [])
        if issues:
            st.warning("QA issues: " + "; ".join(str(issue) for issue in issues))
        elif artwork.critique:
            st.success("All configured MVP artwork checks passed.")


def render_artwork_review(discovery_service: DiscoveryService | None = None) -> None:
    """Render persisted artwork candidates or an explicit fixture-mode placeholder."""

    if discovery_service is None:
        render_placeholder_page(
            "Artwork Review",
            "Review generated artwork candidates and record the final human decision.",
            [
                ("Candidates", "Artwork variants and generation metadata will appear here."),
                ("QA results", "Readability, composition, and format checks will appear here."),
                ("Approval queue", "Approve, reject, regenerate, and request adjustments here."),
            ],
        )
        return

    run_id = st.session_state.get("selected_run_id")
    st.markdown('<div class="opus-breadcrumb">Workspace</div>', unsafe_allow_html=True)
    st.title("Artwork Review")
    st.caption("Inspect generated candidates and the deterministic MVP quality checks.")
    if not run_id:
        st.info("Open a run first to inspect its artwork.")
        return
    try:
        artworks = discovery_service.list_artworks(run_id)
    except (PyMongoError, RepositoryError):
        st.error("Artwork candidates could not be loaded from MongoDB.")
        return
    if not artworks:
        st.info("No artwork candidates are available until Stages 13-16 complete.")
        return
    accepted = sum(
        item.decision is not None and item.decision.value == "accept" for item in artworks
    )
    metric_left, metric_right = st.columns(2)
    metric_left.metric("Candidates", len(artworks))
    metric_right.metric("Passed QA", accepted)
    for artwork in artworks:
        _render_artwork(artwork)
