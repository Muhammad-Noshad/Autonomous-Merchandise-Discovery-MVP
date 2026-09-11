"""Merchandise concept page entrypoint."""

import streamlit as st
from pymongo.errors import PyMongoError

from merchandise_discovery.application.discovery_service import DiscoveryService
from merchandise_discovery.domain.models.artifacts import MerchandiseConcept
from merchandise_discovery.domain.models.common import ConceptVerdict
from merchandise_discovery.shared.errors import RepositoryError
from merchandise_discovery.ui.pages.placeholder import render_placeholder_page


def _render_concept(concept: MerchandiseConcept) -> None:
    """Render one concept's score, verdict, weaknesses, and finalist state."""

    color = "#22C55E" if concept.verdict == ConceptVerdict.KEEP else "#EF4444"
    with st.container(border=True):
        label = "Finalist" if concept.selected else concept.verdict.value.title() if concept.verdict else "Pending critique"
        st.markdown(f"**{concept.phrase}**")
        st.markdown(
            f'<span style="color:{color}; font-weight:650;">{label}</span>',
            unsafe_allow_html=True,
        )
        if concept.overall_score is not None:
            st.progress(concept.overall_score / 10, text=f"Overall score: {concept.overall_score:.2f} / 10")
        st.write(concept.description)
        if concept.scores:
            columns = st.columns(len(concept.scores))
            for column, (name, score) in zip(columns, concept.scores.items()):
                column.metric(name.replace("_", " ").title(), f"{score:.1f}")
        weaknesses = concept.critique.get("weaknesses", [])
        if weaknesses:
            st.warning("Weaknesses: " + " ".join(str(item) for item in weaknesses))


def render_concepts(discovery_service: DiscoveryService | None = None) -> None:
    """Render persisted concepts or the explicit fixture-mode placeholder."""

    if discovery_service is None:
        render_placeholder_page(
            "Concepts",
            "Inspect experience-led merchandise concepts, critiques, and finalist rankings.",
            [
                ("Generated concepts", "Concept cards and source niches will appear here."),
                ("Critique signals", "Authenticity, wearability, and commercial scores will appear here."),
                ("Finalists", "Selected concepts will move into design-brief generation."),
            ],
        )
        return

    run_id = st.session_state.get("selected_run_id")
    st.markdown('<div class="opus-breadcrumb">Workspace</div>', unsafe_allow_html=True)
    st.title("Concepts")
    st.caption("Review experience-led candidates, critique signals, and selected finalists.")
    if not run_id:
        st.info("Open a run first to inspect its concepts.")
        return
    try:
        concepts = discovery_service.list_concepts(run_id)
    except (PyMongoError, RepositoryError):
        st.error("Concepts could not be loaded from MongoDB.")
        return
    if not concepts:
        st.info("No concepts are available until Stages 9-12 complete.")
        return
    finalists = sum(concept.selected for concept in concepts)
    metric_left, metric_right = st.columns(2)
    metric_left.metric("Concepts", len(concepts))
    metric_right.metric("Finalists", finalists)
    for concept in concepts:
        _render_concept(concept)
