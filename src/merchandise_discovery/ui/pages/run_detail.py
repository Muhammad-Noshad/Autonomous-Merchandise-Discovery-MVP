"""Run detail page for the expandable workflow pipeline."""

import logging

import streamlit as st
from pymongo.errors import PyMongoError

from merchandise_discovery.application.discovery_service import DiscoveryService
from merchandise_discovery.shared.errors import RepositoryError
from merchandise_discovery.ui.adapters import snapshot_to_fixture
from merchandise_discovery.ui.components.details import render_detail_panel
from merchandise_discovery.ui.components.layout import PAGE_RUNS, navigate_to, render_run_header
from merchandise_discovery.ui.components.pipeline import render_pipeline
from merchandise_discovery.ui.fixtures import get_demo_run

logger = logging.getLogger(__name__)


def render_run_detail(
    run_id: str,
    discovery_service: DiscoveryService | None = None,
) -> None:
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
            return

        if snapshot is None:
            st.info("No active run selected or run was not found in MongoDB.")
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Browse all runs", use_container_width=True):
                    navigate_to(PAGE_RUNS)
            with col_b:
                if st.button("+ Create a run", use_container_width=True):
                    navigate_to("create_run")
            return
        run = snapshot_to_fixture(snapshot)
    elif run_id == "017":
        run = get_demo_run()
    else:
        run = None

    if run is None:
        st.markdown(f'<div class="opus-breadcrumb">Runs &nbsp;›&nbsp; #{run_id}</div>', unsafe_allow_html=True)
        st.title(f"Run #{run_id}")
        st.info("Historical run details are not available in fixture mode.")
        if st.button("Back to runs"):
            navigate_to(PAGE_RUNS)
        return

    if st.session_state.get("created_run_id") == run.run_id:
        if run.status.value == "paused":
            st.success(
                "Run created. Stage 1 completed and the pipeline is paused at the configured MVP "
                "boundary."
            )
        else:
            st.success("Run created and persisted.")
        del st.session_state["created_run_id"]

    render_run_header(run)
    st.divider()

    pipeline_column, detail_column = st.columns([1.62, 1.0], gap="large")
    with pipeline_column:
        render_pipeline(run)
    with detail_column:
        stage_numbers = [stage.number for stage in run.stages]
        completed = [s for s in run.stages if s.status.value == "completed"]
        default_stage = completed[-1].number if completed else run.current_stage_number

        session_key = f"inspect_stage_{run_id}"
        if session_key not in st.session_state or st.session_state[session_key] not in stage_numbers:
            st.session_state[session_key] = default_stage

        selected_stage_number = st.selectbox(
            "Inspect stage",
            options=stage_numbers,
            index=stage_numbers.index(st.session_state[session_key]),
            format_func=lambda num: f"Stage {num:02d} · {next(s.name for s in run.stages if s.number == num)} ({next(s.status.value.title() for s in run.stages if s.number == num)})",
            key=f"stage_select_box_{run_id}",
        )
        st.session_state[session_key] = selected_stage_number

        selected_stage = next(
            (stage for stage in run.stages if stage.number == selected_stage_number),
            run.stages[0],
        )
        render_detail_panel(selected_stage)


def render_run_detail_with_polling(
    run_id: str,
    discovery_service: DiscoveryService | None = None,
) -> None:
    """Refresh live MongoDB detail snapshots without moving durable state into Streamlit.

    Streamlit fragments provide the MVP's lightweight push-like experience by re-running only the
    detail view. The fallback keeps the same page usable on older Streamlit versions and exposes a
    manual refresh control instead of requiring an HTTP/SSE server.
    """

    if discovery_service is None or not hasattr(st, "fragment"):
        if st.button("Refresh now", key=f"refresh-run-{run_id}"):
            st.rerun()
        render_run_detail(run_id, discovery_service)
        return

    st.caption("Live status refreshes automatically every 3 seconds.")
    if st.button("Refresh now", key=f"refresh-run-{run_id}"):
        st.rerun()

    @st.fragment(run_every="3s")
    def render_live_snapshot() -> None:
        render_run_detail(run_id, discovery_service)

    render_live_snapshot()
