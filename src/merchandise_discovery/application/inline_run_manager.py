"""Process-local background execution for runs created from the Streamlit UI.

The UI is a view over durable MongoDB state; it must not own the stage loop. This manager starts one
daemon thread per UI-created run so navigation, detail-page polling, and browser reconnects do not
cancel the workflow. A production deployment should replace this process-local manager with the
existing worker entrypoint or a queue-backed job runner.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from merchandise_discovery.domain.models.common import RunStatus
from merchandise_discovery.domain.models.workflow import StageLog, WorkflowRun
from merchandise_discovery.shared.logging import stage_waiting_for_review

if TYPE_CHECKING:
    from merchandise_discovery.application.runtime import ApplicationRuntime


class InlineRunManager:
    """Own background stage loops launched by the Create Run use case."""

    WORKER_ID = "ui-inline-runner"

    def __init__(self, runtime: ApplicationRuntime):
        self._runtime = runtime
        self._lock = threading.Lock()
        self._active_runs: dict[str, threading.Thread] = {}

    def start(self, run_id: str) -> WorkflowRun:
        """Claim a run and start it once, returning the claimed durable aggregate."""

        with self._lock:
            active_thread = self._active_runs.get(run_id)
            if active_thread is not None and active_thread.is_alive():
                current = self._runtime.discovery_service.get_run(run_id)
                if current is None:
                    raise RuntimeError(f"Inline run disappeared before it could continue: {run_id}")
                return current

            claimed_run = self._runtime.workflow_orchestrator.claim_run(
                run_id,
                worker_id=self.WORKER_ID,
            )
            if claimed_run is None:
                raise RuntimeError(f"Run could not be claimed for inline execution: {run_id}")

            thread = threading.Thread(
                target=self._run_until_boundary,
                args=(claimed_run,),
                name=f"inline-run-{run_id[:8]}",
                daemon=True,
            )
            self._active_runs[run_id] = thread
            thread.start()
            print(
                f"RUN {run_id} | BACKGROUND | started; target Stage "
                f"{self._runtime.stop_after_stage}",
                flush=True,
            )
            return claimed_run

    def resume_active_runs(self) -> None:
        """Reattach threads to active UI-owned runs after a Streamlit process restart."""

        try:
            runs = self._runtime.discovery_service.list_runs()
        except Exception as error:  # noqa: BLE001  # Startup recovery must not hide the dashboard.
            print(
                f"INLINE RUN RECOVERY | unavailable ({type(error).__name__})",
                flush=True,
            )
            return

        for run in runs:
            if run.status != RunStatus.RUNNING or run.claimed_by != self.WORKER_ID:
                continue
            with self._lock:
                active_thread = self._active_runs.get(run.run_id)
                if active_thread is not None and active_thread.is_alive():
                    continue
                thread = threading.Thread(
                    target=self._run_until_boundary,
                    args=(run,),
                    name=f"inline-resume-{run.run_id[:8]}",
                    daemon=True,
                )
                self._active_runs[run.run_id] = thread
                thread.start()
            print(
                f"RUN {run.run_id} | BACKGROUND | reattached active run at Stage "
                f"{run.current_stage_number or 'unknown'}",
                flush=True,
            )

    def _run_until_boundary(self, initial_run: WorkflowRun) -> None:
        """Advance one claimed run until the configured demo boundary or human approval."""

        # Import at execution time because stage_runner type-checks against ApplicationRuntime,
        # while runtime composes this manager. Delaying this import keeps the composition root
        # acyclic without weakening the concrete runtime contract.
        from merchandise_discovery.application.stage_runner import execute_stage

        run = initial_run
        try:
            while True:
                next_execution = self._runtime.workflow_orchestrator.next_runnable_stage(
                    run.run_id,
                    max_attempts=self._runtime.max_stage_attempts,
                )
                if next_execution is not None and next_execution.stage_number == run.total_stages:
                    stage_waiting_for_review(next_execution)
                    self._save_log(
                        run.run_id,
                        "Automated stages complete; awaiting human approval.",
                        stage=next_execution,
                    )
                    return

                execution = self._runtime.workflow_orchestrator.start_next_stage(
                    run.run_id,
                    max_attempts=self._runtime.max_stage_attempts,
                )
                if execution is None:
                    latest = self._runtime.discovery_service.get_run(run.run_id)
                    if latest is None or latest.status in {
                        RunStatus.PAUSED,
                        RunStatus.COMPLETED,
                        RunStatus.FAILED,
                    }:
                        return
                    message = (
                        f"No runnable stage found; expected Stage "
                        f"{latest.current_stage_number or 'unknown'}."
                    )
                    self._mark_failed(latest, message)
                    print(f"[RUN {run.run_id}] ERROR | {message}", flush=True)
                    return

                print(
                    f"RUN {run.run_id} | BACKGROUND | dispatching Stage "
                    f"{execution.stage_number:02d} {execution.stage_name}",
                    flush=True,
                )
                try:
                    run, _, _ = execute_stage(self._runtime, run, execution)
                except Exception as error:  # noqa: BLE001  # execute_stage persists stage failure.
                    print(
                        f"[RUN {run.run_id}] ERROR | Stage {execution.stage_number:02d} "
                        f"ended with {type(error).__name__}: {error}",
                        flush=True,
                    )
                    return

                if run.status in {RunStatus.PAUSED, RunStatus.COMPLETED}:
                    print(
                        f"RUN {run.run_id} | BACKGROUND | ended with status={run.status.value} "
                        f"at Stage {run.completed_stages}",
                        flush=True,
                    )
                    return
        finally:
            with self._lock:
                self._active_runs.pop(initial_run.run_id, None)

    def _mark_failed(self, run: WorkflowRun, message: str) -> None:
        """Persist an orchestration failure when no next stage can be dispatched."""

        try:
            self._runtime.run_repository.update_status(
                run.run_id,
                expected_version=run.version,
                status=RunStatus.FAILED,
                current_stage_number=run.current_stage_number,
                last_error=message,
                retry_exhausted=False,
            )
        except Exception as error:  # noqa: BLE001  # Preserve the original terminal diagnosis.
            print(
                f"[RUN {run.run_id}] ERROR | Could not persist failure state: "
                f"{type(error).__name__}: {error}",
                flush=True,
            )

    def _save_log(self, run_id: str, message: str, *, stage=None) -> None:
        """Persist a best-effort lifecycle event without masking workflow progress."""

        try:
            self._runtime.stage_log_repository.save(
                StageLog(
                    run_id=run_id,
                    stage_number=stage.stage_number if stage else None,
                    execution_id=stage.execution_id if stage else None,
                    level="info",
                    message=message,
                )
            )
        except Exception as error:  # noqa: BLE001  # Logging must never stop the run.
            print(
                f"[RUN {run_id}] WARNING | Could not persist background log: "
                f"{type(error).__name__}",
                flush=True,
            )
