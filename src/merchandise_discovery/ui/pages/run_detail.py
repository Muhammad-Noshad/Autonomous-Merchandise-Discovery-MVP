"""Run detail page for the expandable workflow pipeline."""

import logging

import streamlit as st
from pymongo.errors import PyMongoError

from merchandise_discovery.application.discovery_service import DiscoveryService
from merchandise_discovery.application.inline_run_manager import InlineRunManager
from merchandise_discovery.domain.models.common import RunStatus
from merchandise_discovery.domain.models.workflow import StageExecution, WorkflowRun
from merchandise_discovery.shared.errors import RepositoryError
from merchandise_discovery.ui.adapters import snapshot_to_fixture
from merchandise_discovery.ui.components.layout import PAGE_RUNS, navigate_to, render_run_header
from merchandise_discovery.ui.components.pipeline import render_pipeline
from merchandise_discovery.ui.fixtures import get_demo_run

logger = logging.getLogger(__name__)


def _render_manual_artwork_selection(
    workflow_run: WorkflowRun,
    stage_one: StageExecution | None,
    discovery_service: DiscoveryService,
    inline_run_manager: InlineRunManager | None,
) -> None:
    """Let the client choose which completed Stage 1 texts proceed into Stage 2."""

    if not workflow_run.config.social_manual_artwork_selection:
        return
    if workflow_run.status != RunStatus.PAUSED or workflow_run.current_stage_number != 2:
        return
    candidates = stage_one.output_data.get("candidates", []) if stage_one else []
    if not candidates:
        st.error("Stage 1 has no text candidates available for artwork selection.")
        return

    st.subheader("Choose text candidates for artwork")
    st.caption(
        "Stage 1 is complete. Review the candidate copy and select only the texts you want "
        "Grok to turn into artwork."
    )
    saved_indices = set(workflow_run.config.social_selected_candidate_indices)
    with st.form(f"manual-artwork-selection-{workflow_run.run_id}"):
        selected_indices = []
        for index, candidate in enumerate(candidates):
            with st.container(border=True):
                st.markdown(f"#### Candidate {index + 1}")
                st.write(f"**Text:** {candidate.get('artwork_text', 'Text not recorded')}")
                if candidate.get("identity"):
                    identity_type = candidate.get("identity_type", "other")
                    identity_type = getattr(identity_type, "value", identity_type)
                    st.caption(f"Audience: {candidate['identity']} · {identity_type}")
                if candidate.get("behavior"):
                    st.write(f"**Behavior:** {candidate['behavior']}")
                if candidate.get("friction_or_pressure"):
                    st.write(f"**Tension:** {candidate['friction_or_pressure']}")
                if st.checkbox(
                    "Generate artwork for this text",
                    value=index in saved_indices,
                    key=f"manual-artwork-{workflow_run.run_id}-{index}",
                ):
                    selected_indices.append(index)
        submitted = st.form_submit_button(
            "Generate artwork for selected texts",
            width="stretch",
        )

    if not submitted:
        return
    if not selected_indices:
        st.error("Select at least one text candidate before continuing.")
        return
    if inline_run_manager is None:
        st.error("The run manager is unavailable; the selected candidates were not started.")
        return

    try:
        discovery_service.save_social_artwork_selection(workflow_run.run_id, selected_indices)
        inline_run_manager.resume_manual_artwork_run(workflow_run.run_id)
    except (PyMongoError, RepositoryError, RuntimeError, ValueError) as error:
        st.error(f"Stage 2 could not be started: {error}")
        return
    st.success(f"Saved {len(selected_indices)} text selection(s). Stage 2 is starting.")
    st.rerun()


def render_run_detail(
    run_id: str,
    discovery_service: DiscoveryService | None = None,
    inline_run_manager: InlineRunManager | None = None,
) -> RunStatus | None:
    """Render a persisted snapshot when available, or the demo detail in fixture mode."""

    if discovery_service is not None:
        target_id = run_id
        if target_id == "017" or not target_id:
            # When connected to MongoDB, resolve to the latest real run rather than fake demo run 017
            try:
                runs = discovery_service.list_runs()
                if runs:
                    target_id = runs[0].run_id
                    st.session_state["selected_run_id"] = target_id
            except (PyMongoError, RepositoryError) as error:
                logger.warning("Could not resolve the latest run (%s).", type(error).__name__)

        try:
            snapshot = discovery_service.get_run_snapshot(target_id)
        except (PyMongoError, RepositoryError):
            st.error("Run details could not be loaded from MongoDB.")
            return None

        if snapshot is None:
            st.info("No active run selected or run was not found in MongoDB.")
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Browse all runs", width="stretch"):
                    navigate_to(PAGE_RUNS)
            with col_b:
                if st.button("+ Create a run", width="stretch"):
                    navigate_to("create_run")
            return None
        workflow_run = snapshot.run
        run = snapshot_to_fixture(snapshot)
        stage_one = max(
            (stage for stage in snapshot.stages if stage.stage_number == 1),
            key=lambda stage: stage.attempt_number,
            default=None,
        )
    elif run_id == "017":
        run = get_demo_run()
        workflow_run = None
        stage_one = None
    else:
        run = None
        workflow_run = None
        stage_one = None

    if run is None:
        st.markdown(f'<div class="opus-breadcrumb">Runs &nbsp;›&nbsp; #{run_id}</div>', unsafe_allow_html=True)
        st.title(f"Run #{run_id}")
        st.info("Historical run details are not available in fixture mode.")
        if st.button("Back to runs"):
            navigate_to(PAGE_RUNS)
        return None

    if st.session_state.get("created_run_id") == run.run_id:
        if run.status.value == "paused" and workflow_run is not None:
            if workflow_run.config.social_manual_artwork_selection:
                st.success("Stage 1 is complete. Review the texts below to choose artwork candidates.")
            else:
                st.success(
                    "Run created. Stage 1 completed and the pipeline is paused at the configured "
                    "MVP boundary."
                )
        else:
            st.success("Run created and persisted.")
        del st.session_state["created_run_id"]

    if st.button("← Back to runs", key=f"back-to-runs-{run.run_id}"):
        navigate_to(PAGE_RUNS)

    render_run_header(run)
    st.divider()

    if workflow_run is not None and discovery_service is not None:
        _render_manual_artwork_selection(
            workflow_run,
            stage_one,
            discovery_service,
            inline_run_manager,
        )

    # The pipeline is the complete detail surface. Keeping it full-width gives each stage expander
    # enough room for its structured output and avoids maintaining a second selected-stage state.
    render_pipeline(run)
    return run.status


def render_run_detail_with_polling(
    run_id: str,
    discovery_service: DiscoveryService | None = None,
    inline_run_manager: InlineRunManager | None = None,
) -> None:
    """Refresh live MongoDB detail snapshots without moving durable state into Streamlit.

    Streamlit fragments provide the MVP's lightweight push-like experience by re-running only the
    detail view. The fallback keeps the same page usable on older Streamlit versions without
    exposing a second refresh control in the detail interface.
    """

    if discovery_service is None or not hasattr(st, "fragment"):
        render_run_detail(run_id, discovery_service, inline_run_manager)
        return

    # Completed and paused runs are immutable from the detail page's perspective. Avoid creating
    # a timer for them; this also lets an already-terminal run settle without repeated reruns.
    try:
        current_run = discovery_service.get_run(run_id)
    except (PyMongoError, RepositoryError):
        current_run = None
    if current_run is not None and current_run.status not in {RunStatus.PENDING, RunStatus.RUNNING}:
        render_run_detail(run_id, discovery_service, inline_run_manager)
        return

    @st.fragment(run_every="3s")
    def render_live_snapshot() -> None:
        status = render_run_detail(run_id, discovery_service, inline_run_manager)
        if status is not None and status not in {RunStatus.PENDING, RunStatus.RUNNING}:
            # The fragment discovered the terminal transition. Rebuild the page outside the
            # repeating fragment so the final snapshot remains static until the user navigates.
            st.rerun(scope="app")

    render_live_snapshot()
