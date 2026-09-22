"""Create Run page for starting a MongoDB-backed discovery workflow.

This page owns form input and run initiation only. Stage execution belongs to
``InlineRunManager`` so navigating away from this page cannot stop a UI-created run.
"""

import streamlit as st
from pymongo.errors import PyMongoError

from merchandise_discovery.application.discovery_service import DiscoveryService
from merchandise_discovery.application.runtime import ApplicationRuntime
from merchandise_discovery.domain.models.common import PipelineVariant, SocialSource
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
    pipeline_variant: PipelineVariant = PipelineVariant.BASELINE,
    social_sources: list[SocialSource] | None = None,
    social_query: str = "",
    social_candidate_count: int = 5,
) -> RunConfig:
    """Convert form primitives into the typed service contract used to create a run."""

    return RunConfig(
        seed_source=seed_source.lower().replace(" ", "_"),
        pipeline_variant=pipeline_variant,
        max_intersections=intersections,
        max_researched_niches=niches,
        concepts_per_niche=concepts,
        artwork_variants_per_concept=artwork_variants,
        enable_similarity_ip_check=similarity_check,
        social_sources=social_sources or [SocialSource.REDDIT],
        social_query=social_query.strip(),
        social_candidate_count=social_candidate_count,
    )


def render_run_create(
    runtime_or_service: ApplicationRuntime | DiscoveryService | None = None,
) -> None:
    """Render the form, persist a run, and launch its process-local background execution."""

    runtime: ApplicationRuntime | None = None
    discovery_service: DiscoveryService | None = None
    seed_libraries = []

    if isinstance(runtime_or_service, ApplicationRuntime):
        runtime = runtime_or_service
        discovery_service = runtime.discovery_service
    elif isinstance(runtime_or_service, DiscoveryService):
        discovery_service = runtime_or_service

    if runtime is None and discovery_service is None:
        runtime = st.session_state.get("application_runtime")
        if runtime is not None:
            discovery_service = runtime.discovery_service
        # Runtime construction belongs to the entrypoint. The page only consumes the injected
        # application boundary and never hides connection failures by rebuilding it.

    if runtime is not None:
        try:
            seed_libraries = runtime.seed_library_repository.list_active()
        except (PyMongoError, RepositoryError, RuntimeError) as error:
            st.error(f"Seed libraries could not be loaded: {error}")
            return
    if not seed_libraries:
        # This fallback keeps the isolated fixture/UI test path usable without inventing a
        # database-backed library. A configured runtime should always provide the Mongo catalog.
        seed_library_options = {"MVP Seed Library": "mvp_seed_library"}
    else:
        seed_library_options = {
            library.name: library.library_id for library in seed_libraries
        }

    st.markdown(
        '<div class="opus-breadcrumb">Workspace &nbsp;›&nbsp; New run</div>',
        unsafe_allow_html=True,
    )
    st.title("Create a discovery run")
    st.caption("Define a small, observable funnel for the client demo.")

    # This selector is intentionally outside the form. Streamlit batches all widgets inside a
    # form until submit, but the selected pipeline controls which fields should be visible now.
    pipeline_variant = st.selectbox(
        "Pipeline",
        options=[
            PipelineVariant.BASELINE,
            PipelineVariant.COMPACT_RESEARCH_FIRST,
            PipelineVariant.SOCIAL_BEHAVIOR_TEXT,
        ],
        format_func=lambda value: {
            PipelineVariant.BASELINE: "Baseline — staged research pipeline",
            PipelineVariant.COMPACT_RESEARCH_FIRST: "Compact — research-first concept pipeline",
            PipelineVariant.SOCIAL_BEHAVIOR_TEXT: "Social behavior — copy + Grok artwork",
        }[value],
        help="Choose a full discovery pipeline or the two-stage social behavior experiment.",
    )
    if (
        pipeline_variant == PipelineVariant.SOCIAL_BEHAVIOR_TEXT
        and runtime is not None
        and runtime.stop_after_stage < 2
    ):
        st.warning(
            "This environment is configured to stop after Stage 1. Set "
            "MVP_STOP_AFTER_STAGE=2 to also generate the Grok artwork."
        )

    with st.form("create-discovery-run"):
        title = st.text_input(
            "Run name",
            value="New merchandise discovery run",
            help="A human-readable name used in run history and review screens.",
        )

        # The social experiment does not consume seed libraries, intersections, niches, or image
        # variants. Keeping those controls out of the form prevents users from configuring values
        # that the selected pipeline will silently ignore.
        seed_source = "social_behavior"
        intersections = 10
        niches = 3
        concepts = 5
        artwork_variants = 2
        social_sources: list[SocialSource] = [SocialSource.REDDIT]
        social_query = ""
        social_candidate_count = 5
        if pipeline_variant == PipelineVariant.SOCIAL_BEHAVIOR_TEXT:
            st.markdown("### Social behavior search")
            social_sources = st.multiselect(
                "Public sources",
                options=[SocialSource.REDDIT, SocialSource.X],
                default=[SocialSource.REDDIT],
                format_func=lambda value: {
                    SocialSource.REDDIT: "Reddit",
                    SocialSource.X: "X / Twitter",
                }[value],
                help="The live pipeline searches public, indexed pages on these domains.",
            )
            social_query = st.text_area(
                "Behavior or topic to explore",
                placeholder=(
                    "For example: people trying to optimize sleep after doom-scrolling until 2 AM"
                ),
                help="Describe the behavior or tension. Avoid entering a broad product category.",
            )
            social_candidate_count = st.slider(
                "Text candidates",
                min_value=1,
                max_value=15,
                value=5,
                help="Maximum number of distinct source-backed merchandise lines to generate.",
            )
        else:
            st.markdown("### Funnel limits")
            seed_source_label = st.selectbox("Seed library", list(seed_library_options))
            seed_source = seed_library_options[seed_source_label]
            intersections = st.slider("Identity intersections", min_value=1, max_value=25, value=10)
            niches = st.slider("Niches to research", min_value=1, max_value=10, value=3)
            concepts = st.slider("Concepts per niche", min_value=1, max_value=10, value=5)
            artwork_variants = st.slider("Artwork variants per finalist", min_value=1, max_value=4, value=2)
        submitted = st.form_submit_button("Create demo run", width="stretch")

    if not submitted:
        return
    if discovery_service is None:
        st.error("MongoDB is required to create a persisted run.")
        return
    if not title.strip():
        st.error("Run name is required.")
        return
    if pipeline_variant == PipelineVariant.SOCIAL_BEHAVIOR_TEXT:
        if not social_sources:
            st.error("Select at least one public source.")
            return
        if not social_query.strip():
            st.error("Describe the behavior or topic to explore.")
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
                pipeline_variant=pipeline_variant,
                social_sources=social_sources,
                social_query=social_query,
                social_candidate_count=social_candidate_count,
            ),
            triggered_by="manual",
        )
    except (PyMongoError, RepositoryError, ValueError) as error:
        st.error(f"Run could not be created: {error}")
        return

    if runtime is None:
        st.session_state["created_run_id"] = run.run_id
        st.session_state["selected_run_id"] = run.run_id
        navigate_to("Runs")
        return

    try:
        runtime.inline_run_manager.start(run.run_id)
    except (PyMongoError, RepositoryError, RuntimeError, ValueError) as error:
        st.error(f"Run could not be started: {error}")
        return

    st.session_state["created_run_id"] = run.run_id
    st.session_state["selected_run_id"] = run.run_id
    # Detail is a read-only view over MongoDB; the manager continues independently after routing.
    navigate_to(PAGE_RUN_DETAIL, run.run_id)
