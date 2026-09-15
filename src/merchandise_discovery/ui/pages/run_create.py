"""Run creation page for the persisted discovery workflow.

The form owns input collection only. Inline execution is a small resumable state machine: one
stage is executed per Streamlit rerun while MongoDB owns the authoritative workflow state.
"""

import logging

import streamlit as st
from pymongo.errors import PyMongoError

from merchandise_discovery.application.discovery_service import DiscoveryService
from merchandise_discovery.application.runtime import ApplicationRuntime
from merchandise_discovery.application.stage_runner import execute_stage
from merchandise_discovery.domain.models.common import RunStatus
from merchandise_discovery.domain.models.workflow import RunConfig, WorkflowRun
from merchandise_discovery.shared.errors import RepositoryError
from merchandise_discovery.ui.components.layout import PAGE_RUNS, navigate_to

logger = logging.getLogger(__name__)

INLINE_RUN_ID_KEY = "inline_run_id"
INLINE_STOP_AFTER_KEY = "inline_stop_after"


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


def _clear_inline_run_state() -> None:
    """Remove transient UI state after an inline run reaches a terminal UI outcome."""

    st.session_state.pop(INLINE_RUN_ID_KEY, None)
    st.session_state.pop(INLINE_STOP_AFTER_KEY, None)


def _inline_log(run_id: str, message: str) -> None:
    """Emit compact continuation diagnostics without dumping provider payloads to the terminal."""

    print(f"RUN {run_id} | INLINE | {message}", flush=True)


def _mark_inline_run_failed(runtime: ApplicationRuntime, run: WorkflowRun, message: str) -> None:
    """Persist a clear run-level failure when orchestration cannot find the expected next stage."""

    try:
        runtime.run_repository.update_status(
            run.run_id,
            expected_version=run.version,
            status=RunStatus.FAILED,
            current_stage_number=run.current_stage_number,
            last_error=message,
            retry_exhausted=False,
        )
    except Exception as state_error:  # noqa: BLE001  # Recovery must not hide the original issue.
        logger.warning(
            "Could not persist inline runner recovery state (%s).",
            type(state_error).__name__,
        )


def _finish_inline_run(run_id: str) -> None:
    """Select the newly created run and route through the normal Runs page."""

    _clear_inline_run_state()
    st.session_state["created_run_id"] = run_id
    st.session_state["selected_run_id"] = run_id
    # Run detail remains reachable only after selecting a run from Runs.
    navigate_to(PAGE_RUNS)


def _continue_inline_run(runtime: ApplicationRuntime, run_id: str, stop_after: int) -> None:
    """Execute one durable stage, then schedule the next stage on a fresh Streamlit rerun.

    A Streamlit script run is a request-like execution boundary. Keeping a multi-stage loop inside
    one request can leave a run active if the browser, websocket, or script reruns between loops.
    MongoDB lets the next request skip completed work, while session state only identifies the UI
    run that should continue.
    """

    try:
        run = runtime.discovery_service.get_run(run_id)
    except (PyMongoError, RepositoryError, ValueError) as error:
        _clear_inline_run_state()
        st.error(f"Inline run could not be loaded: {error}")
        return

    if run is None:
        _clear_inline_run_state()
        st.error(f"Inline run {run_id} no longer exists in MongoDB.")
        return

    _inline_log(
        run_id,
        f"CONTINUE | persisted status={run.status.value}, completed={run.completed_stages}, "
        f"current Stage {run.current_stage_number or 'unknown'}, version={run.version}",
    )

    # A rerun may arrive after the boundary was already persisted. Do not start more work.
    if run.completed_stages >= stop_after or run.status in {RunStatus.PAUSED, RunStatus.COMPLETED}:
        _finish_inline_run(run_id)
        return

    execution = runtime.workflow_orchestrator.start_next_stage(
        run.run_id,
        max_attempts=runtime.max_stage_attempts,
    )
    if execution is None:
        message = (
            f"No runnable stage found after {run.completed_stages} completed stage(s); "
            f"expected Stage {run.current_stage_number or 'unknown'}."
        )
        print(f"[RUN {run_id}] ERROR | {message}", flush=True)
        _mark_inline_run_failed(runtime, run, message)
        _clear_inline_run_state()
        st.error(f"Pipeline stopped: {message}")
        return

    stage_num = execution.stage_number
    _inline_log(
        run_id,
        f"DISPATCH | Stage {stage_num:02d} {execution.stage_name} "
        f"claimed attempt={execution.attempt_number}, version={execution.version}",
    )
    print(
        f"RUN {run_id} | NEXT | Stage {stage_num:02d} {execution.stage_name}",
        flush=True,
    )
    with st.status(f"Stage {stage_num:02d}: {execution.stage_name}", expanded=True) as status_box:
        st.write(f"Workflow run #{run_id} is executing.")
        try:
            updated_run, _, result = execute_stage(runtime, run, execution)
        except Exception as error:  # noqa: BLE001  # Stage runner persists and labels the failure.
            st.error(f"Stage {stage_num:02d} execution failed: {error}")
            status_box.update(label=f"Stage {stage_num:02d} failed", state="error")
            _clear_inline_run_state()
            return

        st.write(f"Stage {stage_num:02d} completed: {result.output_summary}")
        status_box.update(label=f"Stage {stage_num:02d} completed", state="complete")
        _inline_log(
            run_id,
            f"COMMITTED | Stage {stage_num:02d} complete; run status={updated_run.status.value}, "
            f"completed={updated_run.completed_stages}, next Stage "
            f"{updated_run.current_stage_number or 'none'}, version={updated_run.version}",
        )

    if stage_num >= stop_after or updated_run.status in {RunStatus.PAUSED, RunStatus.COMPLETED}:
        _finish_inline_run(run_id)
        return

    # The stage is persisted before this rerun, so a rerun cannot duplicate this stage.
    _inline_log(run_id, f"RERUN | scheduling continuation at Stage {updated_run.current_stage_number or 'unknown'}")
    st.rerun()


def _find_orphaned_inline_run(runtime: ApplicationRuntime) -> WorkflowRun | None:
    """Find a UI-created run left active when a Streamlit rerun was interrupted or lost."""

    try:
        runs = runtime.discovery_service.list_runs()
    except (PyMongoError, RepositoryError):
        return None
    return next(
        (
            run
            for run in runs
            if run.status == RunStatus.RUNNING and run.claimed_by == "ui-inline-runner"
        ),
        None,
    )


def render_run_create(
    runtime_or_service: ApplicationRuntime | DiscoveryService | None = None,
) -> None:
    """Render the form and create a persisted run when a service is available."""

    runtime: ApplicationRuntime | None = None
    discovery_service: DiscoveryService | None = None

    if isinstance(runtime_or_service, ApplicationRuntime):
        runtime = runtime_or_service
        discovery_service = runtime.discovery_service
    elif isinstance(runtime_or_service, DiscoveryService):
        discovery_service = runtime_or_service

    if runtime is None and discovery_service is None:
        runtime = st.session_state.get("application_runtime")
        if runtime is not None:
            discovery_service = runtime.discovery_service
        # Runtime construction belongs to the entrypoint. This page only consumes the injected
        # application boundary and therefore cannot hide connection failures by rebuilding it.

    inline_run_id = st.session_state.get(INLINE_RUN_ID_KEY)
    if runtime is not None and not inline_run_id:
        # Session state can disappear after a websocket reconnect even though MongoDB correctly
        # retains the active run. Recover only the explicit UI-owned runner marker; background
        # worker runs must remain the worker's responsibility.
        orphaned_run = _find_orphaned_inline_run(runtime)
        if orphaned_run is not None:
            stop_after = max(1, int(getattr(runtime, "stop_after_stage", 1)))
            _inline_log(
                orphaned_run.run_id,
                f"RESUME | recovered active UI run at Stage "
                f"{orphaned_run.current_stage_number or 'unknown'}",
            )
            st.session_state[INLINE_RUN_ID_KEY] = orphaned_run.run_id
            st.session_state[INLINE_STOP_AFTER_KEY] = stop_after
            _continue_inline_run(runtime, orphaned_run.run_id, stop_after)
            return
    if runtime is not None and inline_run_id:
        _continue_inline_run(
            runtime,
            inline_run_id,
            max(1, int(st.session_state.get(INLINE_STOP_AFTER_KEY, runtime.stop_after_stage))),
        )
        return

    st.markdown("<div class=\"opus-breadcrumb\">Workspace &nbsp;›&nbsp; New run</div>", unsafe_allow_html=True)
    st.title("Create a discovery run")
    st.caption("Define a small, observable funnel for the client demo.")

    with st.form("create-discovery-run"):
        title = st.text_input(
            "Run name",
            value="New merchandise discovery run",
            help="A human-readable name used in run history and review screens.",
        )
        seed_source = st.selectbox("Seed source", ["MVP seed library"])

        st.markdown("### Funnel limits")
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

    if runtime is None:
        _finish_inline_run(run.run_id)
        return

    stop_after = max(1, int(getattr(runtime, "stop_after_stage", 1)))
    claimed_run = runtime.workflow_orchestrator.claim_run(
        run.run_id,
        worker_id="ui-inline-runner",
    )
    if claimed_run is None:
        st.error(f"Run #{run.run_id} could not be claimed for inline execution.")
        return

    _inline_log(run.run_id, f"START | target Stage {stop_after}")
    st.session_state[INLINE_RUN_ID_KEY] = claimed_run.run_id
    st.session_state[INLINE_STOP_AFTER_KEY] = stop_after
    # Start execution in a separate request. This boundary lets each stage commit durable state
    # before the UI schedules the following stage.
    st.rerun()
