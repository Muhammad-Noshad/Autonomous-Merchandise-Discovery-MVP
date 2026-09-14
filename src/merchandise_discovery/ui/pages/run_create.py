"""Run creation page for the persisted discovery workflow.

The form owns input collection only. It converts validated values into `RunConfig` and delegates run
creation to `DiscoveryService`, keeping persistence and stage initialization outside Streamlit.
"""

import streamlit as st
from pymongo.errors import PyMongoError

from merchandise_discovery.application.discovery_service import DiscoveryService
from merchandise_discovery.application.runtime import ApplicationRuntime
from merchandise_discovery.application.stage_runner import execute_stage
from merchandise_discovery.domain.models.workflow import RunConfig
from merchandise_discovery.shared.errors import RepositoryError
from merchandise_discovery.ui.components.layout import PAGE_RUN_DETAIL, navigate_to


def build_run_config(
    seed_source: str,
    intersections: int,
    niches: int,
    concepts: int,
    artwork_variants: int,
    similarity_check: bool = False,
) -> RunConfig:
    """Convert form primitives into the typed service contract used to create a run."""

    return RunConfig(
        seed_source=seed_source.lower().replace(" ", "_"),
        max_intersections=intersections,
        max_researched_niches=niches,
        concepts_per_niche=concepts,
        artwork_variants_per_concept=artwork_variants,
        enable_similarity_ip_check=similarity_check,
    )


def render_run_create(
    runtime_or_service: ApplicationRuntime | DiscoveryService | None = None,
) -> None:
    """Render a configuration form and create a persisted run when a service is available."""

    runtime: ApplicationRuntime | None = None
    discovery_service: DiscoveryService | None = None

    if isinstance(runtime_or_service, ApplicationRuntime):
        runtime = runtime_or_service
        discovery_service = runtime.discovery_service
    elif isinstance(runtime_or_service, DiscoveryService):
        discovery_service = runtime_or_service

    st.markdown('<div class="opus-breadcrumb">Workspace &nbsp;›&nbsp; New run</div>', unsafe_allow_html=True)
    st.title("Create a discovery run")
    st.caption("Define a small, observable funnel for the client demo.")

    with st.form("create-discovery-run"):
        title = st.text_input(
            "Run name",
            value="New merchandise discovery run",
            help="A human-readable name used in run history and review screens.",
        )
        seed_source = st.selectbox(
            "Seed source",
            ["MVP seed library"],
        )

        st.markdown("### Funnel limits")
        intersections = st.slider("Identity intersections", min_value=1, max_value=25, value=10)
        niches = st.slider("Niches to research", min_value=1, max_value=10, value=3)
        concepts = st.slider("Concepts per niche", min_value=1, max_value=10, value=5)
        artwork_variants = st.slider("Artwork variants per finalist", min_value=1, max_value=4, value=2)

        submitted = st.form_submit_button("Create demo run", use_container_width=True)

    if not submitted:
        return
    if discovery_service is None:
        st.error("MongoDB is required to create a persisted run.")
        return
    if not title.strip():
        st.error("Run name is required.")
        return

    try:
        run = discovery_service.create_run(
            title=title.strip(),
            config=build_run_config(
                seed_source,
                intersections,
                niches,
                concepts,
                artwork_variants,
            ),
            triggered_by="manual",
        )
    except (PyMongoError, RepositoryError, ValueError) as error:
        st.error(f"Run could not be created: {error}")
        return

    # Execute Stage 1 inline so actual data is generated and visible immediately
    if runtime is not None:
        try:
            claimed_run = runtime.workflow_orchestrator.claim_run(run.run_id, worker_id="ui-inline-runner")
            if claimed_run is None:
                claimed_run = run
            execution = runtime.workflow_orchestrator.start_next_stage(
                claimed_run.run_id,
                max_attempts=runtime.max_stage_attempts,
            )
            if execution is not None:
                execute_stage(runtime, claimed_run, execution)
        except Exception as error:
            st.error(f"Stage 1 execution failed: {error}")
            return

    st.session_state["created_run_id"] = run.run_id
    navigate_to(PAGE_RUN_DETAIL, run.run_id)
