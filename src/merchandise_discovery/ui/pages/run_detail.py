"""Run detail page for the expandable workflow pipeline."""

import logging

import streamlit as st
from pymongo.errors import PyMongoError

from merchandise_discovery.application.discovery_service import DiscoveryService
from merchandise_discovery.domain.models.common import RunStatus
from merchandise_discovery.shared.errors import RepositoryError
from merchandise_discovery.ui.adapters import snapshot_to_fixture
from merchandise_discovery.ui.components.layout import PAGE_RUNS, navigate_to, render_run_header
from merchandise_discovery.ui.components.pipeline import render_pipeline
from merchandise_discovery.ui.fixtures import get_demo_run

logger = logging.getLogger(__name__)


def render_run_detail(
    run_id: str,
    discovery_service: DiscoveryService | None = None,
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
        return None

    if st.session_state.get("created_run_id") == run.run_id:
        if run.status.value == "paused":
            st.success(
                "Run created. Stage 1 completed and the pipeline is paused at the configured MVP "
                "boundary."
            )
        else:
            st.success("Run created and persisted.")
        del st.session_state["created_run_id"]

    if st.button("← Back to runs", key=f"back-to-runs-{run.run_id}"):
        navigate_to(PAGE_RUNS)

    render_run_header(run)
    st.divider()

    # The pipeline is the complete detail surface. Keeping it full-width gives each stage expander
    # enough room for its structured output and avoids maintaining a second selected-stage state.
    render_pipeline(run)
    return run.status


def render_run_detail_with_polling(
    run_id: str,
    discovery_service: DiscoveryService | None = None,
) -> None:
    """Refresh live MongoDB detail snapshots without moving durable state into Streamlit.

    Streamlit fragments provide the MVP's lightweight push-like experience by re-running only the
    detail view. The fallback keeps the same page usable on older Streamlit versions without
    exposing a second refresh control in the detail interface.
    """

    if discovery_service is None or not hasattr(st, "fragment"):
        render_run_detail(run_id, discovery_service)
        return

    # Completed and paused runs are immutable from the detail page's perspective. Avoid creating
    # a timer for them; this also lets an already-terminal run settle without repeated reruns.
    try:
        current_run = discovery_service.get_run(run_id)
    except (PyMongoError, RepositoryError):
        current_run = None
    if current_run is not None and current_run.status not in {RunStatus.PENDING, RunStatus.RUNNING}:
        render_run_detail(run_id, discovery_service)
        return

    @st.fragment(run_every="3s")
    def render_live_snapshot() -> None:
        status = render_run_detail(run_id, discovery_service)
        if status is not None and status not in {RunStatus.PENDING, RunStatus.RUNNING}:
            # The fragment discovered the terminal transition. Rebuild the page outside the
            # repeating fragment so the final snapshot remains static until the user navigates.
            st.rerun(scope="app")

    render_live_snapshot()
