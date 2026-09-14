"""MongoDB-backed niche page for inspecting and manually adding run-scoped candidates.

The page owns rendering and form input only. Niche validation and persistence stay in
``DiscoveryService`` so this UI cannot accidentally create records outside the repository boundary.
"""

import logging

import streamlit as st
from pymongo.errors import PyMongoError

from merchandise_discovery.application.discovery_service import DiscoveryService
from merchandise_discovery.domain.models.artifacts import Niche
from merchandise_discovery.shared.errors import RepositoryError

logger = logging.getLogger(__name__)


def _render_niche(niche: Niche) -> None:
    """Render one persisted niche with its validation and opportunity signals."""

    with st.container(border=True):
        st.markdown(f"**{niche.name}**")

        status = "Validated" if niche.validated else "Unvalidated"
        color = "#22C55E" if niche.validated else "#EAB308"
        st.markdown(
            f'<span style="color:{color}; font-weight:650;">●&nbsp; {status}</span>',
            unsafe_allow_html=True,
        )

        col1, col2 = st.columns(2)
        with col1:
            if niche.coherence_score is not None:
                st.caption(f"Coherence score: {niche.coherence_score:.2f} / 10")
        with col2:
            if niche.opportunity_score is not None:
                st.caption(f"Opportunity score: {niche.opportunity_score:.2f} / 100")

        if niche.experience_summary:
            st.write(niche.experience_summary)

        st.caption(f"Evidence count: {niche.evidence_count} · Niche ID: {niche.niche_id}")


def render_niches(discovery_service: DiscoveryService | None = None) -> None:
    """Render niches for a selected persisted run and handle manual niche creation."""

    st.markdown('<div class="opus-breadcrumb">Workspace</div>', unsafe_allow_html=True)
    st.title("Niches")
    st.caption("Inspect and add identity intersections backed by MongoDB.")

    if discovery_service is None:
        st.info("MongoDB is required to view and create persisted niches.")
        return

    try:
        runs = discovery_service.list_runs()
    except (PyMongoError, RepositoryError) as error:
        logger.warning("Could not load runs for niche selection (%s).", type(error).__name__)
        st.error("Niches could not be loaded because the run history is unavailable.")
        return

    if not runs:
        st.info("Create a discovery run before adding or reviewing niches.")
        return

    run_labels = {f"#{run.run_id[:8]} · {run.title}": run.run_id for run in runs}
    selected_run_id = st.session_state.get("selected_run_id")
    selected_label = next(
        (label for label, run_id in run_labels.items() if run_id == selected_run_id),
        next(iter(run_labels)),
    )
    selected_label = st.selectbox(
        "Run",
        list(run_labels),
        index=list(run_labels).index(selected_label),
    )
    selected_run_id = run_labels[selected_label]
    st.session_state["selected_run_id"] = selected_run_id

    try:
        niches = discovery_service.list_niches(selected_run_id)
    except (PyMongoError, RepositoryError) as error:
        logger.warning("Could not load niches for run (%s).", type(error).__name__)
        st.error("Niches could not be loaded from MongoDB.")
        return

    st.subheader("Add a new niche")
    with st.form("add_niche_form", clear_on_submit=True):
        name = st.text_input("Niche name", placeholder="Night shift ICU nurse + pit bull owner")
        experience = st.text_area("Experience summary")
        coherence = st.slider("Coherence score", 0.0, 10.0, 5.0, 0.1)
        opportunity = st.slider("Opportunity score", 0.0, 100.0, 50.0, 1.0)
        submitted = st.form_submit_button("Add niche")

    if submitted:
        if not name.strip():
            st.error("Niche name is required.")
        else:
            try:
                discovery_service.create_manual_niche(
                    selected_run_id,
                    name=name,
                    experience_summary=experience,
                    coherence_score=coherence,
                    opportunity_score=opportunity,
                )
            except (PyMongoError, RepositoryError, RuntimeError, ValueError) as error:
                logger.warning("Could not create manual niche (%s).", type(error).__name__)
                st.error(f"Niche could not be saved: {error}")
            else:
                st.success(f"Added niche: {name.strip()}")
                st.rerun()

    st.subheader("Available niches")
    if not niches:
        st.info("No niches have been persisted for this run yet.")
        return

    st.metric("Total niches", len(niches))
    for niche in niches:
        _render_niche(niche)
