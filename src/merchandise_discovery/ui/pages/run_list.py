"""Run listing page with navigation and explicit destructive cleanup controls.

This page owns list presentation and navigation into a run. It receives the application service as a
dependency for deletion; MongoDB access and cascade rules remain outside the UI layer.
"""

import streamlit as st
from pymongo.errors import PyMongoError

from merchandise_discovery.application.discovery_service import DiscoveryService
from merchandise_discovery.domain.models.common import RunStatus
from merchandise_discovery.domain.models.workflow import WorkflowRun
from merchandise_discovery.shared.errors import RepositoryError
from merchandise_discovery.ui.adapters import workflow_to_list_item
from merchandise_discovery.ui.components.layout import PAGE_RUN_DETAIL, navigate_to
from merchandise_discovery.ui.fixtures import RunListItemFixture, get_demo_runs


def _status_color(status: RunStatus) -> str:
    """Map a run status to the established Planet Opus semantic color."""

    return {
        RunStatus.COMPLETED: "#22C55E",
        RunStatus.RUNNING: "#8B5CF6",
        RunStatus.PAUSED: "#F59E0B",
        RunStatus.FAILED: "#EF4444",
        RunStatus.PENDING: "rgba(255,255,255,0.50)",
        RunStatus.CANCELLED: "rgba(255,255,255,0.50)",
    }[status]


def _render_run_row(
    run: RunListItemFixture,
    discovery_service: DiscoveryService | None = None,
) -> None:
    """Render one run summary with detail navigation and an optional delete request."""

    with st.container(border=True):
        identity, status_column, progress_column, action_column, delete_column = st.columns(
            [0.34, 0.16, 0.23, 0.14, 0.13]
        )
        with identity:
            st.markdown(f"**#{run.run_id} · {run.title}**")
            st.caption(
                f"Triggered by {run.triggered_by} · Updated {run.updated} · "
                f"Selection seed: {run.selection_seed if run.selection_seed is not None else 'not recorded'}"
            )
        with status_column:
            color = _status_color(run.status)
            st.markdown(
                f'<span style="color:{color}; font-weight:650;">●&nbsp; '
                f"{run.status.value.title()}</span>",
                unsafe_allow_html=True,
            )
        with progress_column:
            st.progress(run.progress / 100, text=f"{run.progress}% complete")
        with action_column:
            if st.button("Open", key=f"open-run-{run.run_id}", width="stretch"):
                navigate_to(PAGE_RUN_DETAIL, run.run_id)
        with delete_column:
            if discovery_service is not None and st.button(
                "Delete run",
                key=f"delete-run-{run.run_id}",
                width="stretch",
                type="secondary",
            ):
                st.session_state["pending_delete_run_id"] = run.run_id


def _render_delete_confirmation(
    run_items: list[RunListItemFixture],
    discovery_service: DiscoveryService,
) -> None:
    """Confirm and execute a run-scoped cascade, keeping the irreversible action deliberate."""

    pending_id = st.session_state.get("pending_delete_run_id")
    if not pending_id:
        return
    target = next((run for run in run_items if run.run_id == pending_id), None)
    if target is None:
        st.session_state.pop("pending_delete_run_id", None)
        return

    with st.container(border=True):
        st.warning(
            f"Delete run #{target.run_id} ({target.title}) permanently? "
            "This removes its stages, logs, intersections, research, concepts, artwork, and reviews."
        )
        confirm_column, cancel_column = st.columns(2)
        with confirm_column:
            if st.button(
                "Delete permanently",
                key=f"confirm-delete-run-{target.run_id}",
                width="stretch",
                type="primary",
            ):
                try:
                    summary = discovery_service.delete_run(target.run_id)
                except (PyMongoError, RepositoryError, ValueError, RuntimeError):
                    st.error("The run could not be deleted. It may no longer exist or the database may be unavailable.")
                else:
                    st.session_state["run_delete_notice"] = (
                        f"Deleted run #{target.run_id} and {summary.total_deleted} associated database records."
                    )
                    st.session_state.pop("pending_delete_run_id", None)
                    st.session_state.pop("selected_run_id", None)
                    st.rerun()
        with cancel_column:
            if st.button("Cancel", key=f"cancel-delete-run-{target.run_id}", width="stretch"):
                st.session_state.pop("pending_delete_run_id", None)
                st.rerun()


def render_run_list(
    runs: list[WorkflowRun] | None = None,
    discovery_service: DiscoveryService | None = None,
) -> None:
    """Render run history from persisted aggregates or an explicit fixture fallback."""

    st.markdown('<div class="opus-breadcrumb">Workspace</div>', unsafe_allow_html=True)
    st.title("Runs")
    st.caption("Review discovery runs, inspect their pipeline progress, or start a new run.")

    toolbar_left, toolbar_right = st.columns([0.76, 0.24])
    with toolbar_left:
        st.markdown("### Run history")
    with toolbar_right:
        selected_filter = st.selectbox(
            "Filter",
            ["All runs", "In progress", "Paused", "Completed", "Failed"],
            label_visibility="collapsed",
        )

    run_items = get_demo_runs() if runs is None else [workflow_to_list_item(run) for run in runs]
    all_run_items = list(run_items)
    if selected_filter != "All runs":
        status = selected_filter.lower().replace(" ", "_")
        run_items = [run for run in run_items if run.status.value == status]

    for run in run_items:
        _render_run_row(run, discovery_service)

    if discovery_service is not None:
        notice = st.session_state.pop("run_delete_notice", None)
        if notice:
            st.success(notice)
        _render_delete_confirmation(all_run_items, discovery_service)

    if runs is None:
        st.info("These are demo runs for the MVP shell. Live run history will be loaded from MongoDB in a later chunk.")
    elif not runs:
        st.info("No discovery runs created yet. Click '+ New run' in the sidebar to create one.")
    elif not run_items:
        st.info("No runs match the selected filter.")
