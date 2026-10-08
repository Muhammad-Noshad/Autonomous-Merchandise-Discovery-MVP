"""Create Run page for starting a MongoDB-backed discovery workflow.

This page owns form input and run initiation only. Stage execution belongs to
``InlineRunManager`` so navigating away from this page cannot stop a UI-created run.
"""

import streamlit as st
from pymongo.errors import PyMongoError

from merchandise_discovery.application.discovery_service import DiscoveryService
from merchandise_discovery.application.runtime import ApplicationRuntime
from merchandise_discovery.domain.models.common import (
    IdentityType,
    PipelineVariant,
    SocialSource,
    identity_type_guidance,
)
from merchandise_discovery.domain.models.workflow import RunConfig
from merchandise_discovery.shared.errors import RepositoryError
from merchandise_discovery.ui.adapters import pipeline_display_name
from merchandise_discovery.ui.components.layout import PAGE_RUN_DETAIL, navigate_to


def build_run_config(
    seed_source: str,
    intersections: int,
    niches: int,
    concepts: int,
    artwork_variants: int,
    similarity_check: bool = False,
    pipeline_variant: PipelineVariant = PipelineVariant.SOCIAL_IDENTITY_V2,
    social_sources: list[SocialSource] | None = None,
    social_query: str = "",
    social_auto_topic: bool = False,
    social_candidate_count: int = 5,
    social_identity: str = "",
    social_identity_type: IdentityType | None = None,
    social_auto_identity: bool = False,
    social_manual_artwork_selection: bool = False,
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
        social_auto_topic=social_auto_topic,
        social_candidate_count=social_candidate_count,
        social_identity=social_identity.strip(),
        social_identity_type=social_identity_type,
        social_auto_identity=social_auto_identity,
        social_manual_artwork_selection=social_manual_artwork_selection,
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
    st.title("Create a discovery run!")
    st.caption("Define a small, observable funnel for the client demo.")

    # This selector is intentionally outside the form. Streamlit batches all widgets inside a
    # form until submit, but the selected pipeline controls which fields should be visible now.
    show_legacy_pipelines = st.checkbox(
        "Show legacy pipelines",
        value=False,
        help="Reveal the older Baseline and Compact pipelines for comparison runs.",
    )
    pipeline_options = [
        PipelineVariant.SOCIAL_IDENTITY_V2,
        PipelineVariant.SOCIAL_BEHAVIOR_IDENTITY,
        PipelineVariant.SOCIAL_BEHAVIOR_TEXT,
    ]
    if show_legacy_pipelines:
        pipeline_options.extend(
            [PipelineVariant.BASELINE, PipelineVariant.COMPACT_RESEARCH_FIRST]
        )
    pipeline_variant = st.selectbox(
        "Pipeline",
        options=pipeline_options,
        index=0,
        format_func=pipeline_display_name,
        help="Choose a research pipeline or one of three social-merchandise approaches.",
    )
    is_social_pipeline = pipeline_variant in {
        PipelineVariant.SOCIAL_BEHAVIOR_TEXT,
        PipelineVariant.SOCIAL_BEHAVIOR_IDENTITY,
        PipelineVariant.SOCIAL_IDENTITY_V2,
    }
    is_identity_pipeline = pipeline_variant in {
        PipelineVariant.SOCIAL_IDENTITY_V2,
    }
    if (
        is_social_pipeline
        and runtime is not None
        and runtime.stop_after_stage < 2
    ):
        st.warning(
            "This environment is configured to stop after Stage 1. Set "
            "MVP_STOP_AFTER_STAGE=2 to also generate the Grok artwork."
        )
    auto_topic = False
    auto_identity = False
    manual_artwork_selection = False
    if is_social_pipeline:
        auto_topic = st.checkbox(
            "Let AI choose the behavior or topic",
            value=False,
            help="OpenAI will choose a narrow, source-backed behavior before searching in Stage 1.",
        )
        if is_identity_pipeline:
            auto_identity = st.checkbox(
                "Let AI choose the identity and identity type",
                value=False,
                help=(
                    "OpenAI will select one concrete, non-sensitive audience identity and classify "
                    "it using the supported identity taxonomy: "
                    + identity_type_guidance()
                ),
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
        social_identity = ""
        social_identity_type: IdentityType | None = None
        if is_social_pipeline:
            st.markdown("### Social behavior search")
            if is_identity_pipeline:
                st.markdown("#### Identity anchor")
                if auto_identity:
                    st.info("AI will select the identity and identity type from the public discussions.")
                else:
                    social_identity_type = st.selectbox(
                        "Identity type",
                        options=list(IdentityType),
                        index=0,
                        format_func=lambda value: value.display_name,
                        help=(
                            "Describe the audience explicitly. The pipeline uses this as a hard anchor "
                            "and does not infer sensitive traits. Categories: "
                            + identity_type_guidance()
                        ),
                    )
                    social_identity = st.text_input(
                        "Target identity",
                        placeholder="For example: night-shift nurses",
                        help="The audience the merchandise should make feel immediately recognized.",
                    )
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
                disabled=auto_topic,
            )
            social_candidate_count = st.slider(
                "Text candidates",
                min_value=1,
                max_value=15,
                value=5,
                help="Maximum number of distinct source-backed merchandise lines to generate.",
            )
            manual_artwork_selection = st.checkbox(
                "Let me choose which texts get artwork",
                value=False,
                disabled=runtime is not None and runtime.stop_after_stage < 2,
                help=(
                    "After Stage 1, pause the run so you can review the generated text candidates. "
                    "Stage 2 will generate artwork only for the candidates you select. This requires "
                    "MVP_STOP_AFTER_STAGE to be at least 2."
                ),
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
    if is_social_pipeline:
        if not social_sources:
            st.error("Select at least one public source.")
            return
        if not auto_topic and not social_query.strip():
            st.error("Describe the behavior or topic to explore.")
            return
        if (
            is_identity_pipeline
            and not auto_identity
            and not social_identity.strip()
        ):
            st.error("Enter the target identity for the identity-focused pipeline.")
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
                social_auto_topic=auto_topic,
                social_candidate_count=social_candidate_count,
                social_identity=social_identity,
                social_identity_type=social_identity_type,
                social_auto_identity=auto_identity,
                social_manual_artwork_selection=manual_artwork_selection,
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
