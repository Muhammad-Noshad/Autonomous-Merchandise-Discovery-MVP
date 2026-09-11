"""Detailed stage inspection panel for the selected workflow stage."""

import streamlit as st

from merchandise_discovery.domain.models.common import StageStatus
from merchandise_discovery.ui.fixtures import StageFixture


def render_detail_panel(stage: StageFixture) -> None:
    """Render inputs, summarized output, evidence, artifacts, and prototype actions."""

    status_color = {
        StageStatus.COMPLETED: "#22C55E",
        StageStatus.RUNNING: "#8B5CF6",
        StageStatus.FAILED: "#EF4444",
        StageStatus.SKIPPED: "rgba(255,255,255,0.50)",
        StageStatus.PENDING: "rgba(255,255,255,0.50)",
    }[stage.status]
    st.markdown(f"### Stage {stage.number}")
    st.markdown(f"## {stage.name}")
    st.markdown(
        f'<span class="opus-status" style="border-color:{status_color}; color:{status_color};">'
        f'●&nbsp; {stage.status.value.title()}</span>',
        unsafe_allow_html=True,
    )
    st.caption(stage.summary)
    if stage.error_message:
        st.error(stage.error_message)

    details_tab, evidence_tab, artifacts_tab = st.tabs(["Details", "Evidence", "Artifacts"])
    with details_tab:
        st.markdown("**What this stage does**")
        st.write(stage.summary)

        st.markdown("**Input summary**")
        for label, value in stage.inputs.items():
            st.write(f"**{label}:** {value}")
        if not stage.inputs and not stage.input_payload:
            st.info("No input snapshot was persisted for this stage.")

        st.markdown("**Output summary**")
        st.info(stage.output_summary)

        if not stage.output_payload:
            st.info("No output snapshot is available until this stage executes.")

        if stage.input_payload or stage.output_payload:
            # Raw payloads remain available for audit/debug work, but they are intentionally
            # collapsed so the client-facing details panel leads with human-readable decisions.
            with st.expander("Audit payload · raw", expanded=False):
                if stage.input_payload:
                    st.markdown("**Input snapshot**")
                    st.json(stage.input_payload, expanded=False)
                if stage.output_payload:
                    st.markdown("**Output snapshot**")
                    st.json(stage.output_payload, expanded=False)

        if stage.metrics:
            st.markdown("**Decision signals**")
            for label, value in stage.metrics.items():
                st.write(f"`{label}`  {value}")

    with evidence_tab:
        if not stage.evidence:
            st.info("Evidence will appear when this stage has executed.")
        for evidence in stage.evidence:
            st.markdown(
                f'<div class="opus-evidence"><strong>{evidence.title}</strong><br/>'
                f'<span class="opus-muted">{evidence.source} · {evidence.date}</span><br/>'
                f'{evidence.excerpt}</div>',
                unsafe_allow_html=True,
            )

    with artifacts_tab:
        if not stage.artifacts:
            st.info("Artifacts will appear when this stage produces a persisted output.")
        for artifact in stage.artifacts:
            st.markdown(f'<div class="opus-artifact">▣ {artifact}</div>', unsafe_allow_html=True)

    st.divider()
    action_left, action_right = st.columns(2)
    with action_left:
        if st.button("↻  Retry stage", use_container_width=True, disabled=stage.status == StageStatus.PENDING):
            st.toast("Retry action will connect to the worker in a later chunk.")
    with action_right:
        if st.button("⋯  View logs", use_container_width=True):
            st.toast("Stage logs will be connected to persisted executions in a later chunk.")
