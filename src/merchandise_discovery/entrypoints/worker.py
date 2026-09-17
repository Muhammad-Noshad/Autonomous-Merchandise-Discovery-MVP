"""Command-line entrypoint for the background workflow worker.

Both pipeline variants finish at a display-only artwork results stage. The worker owns execution
only; visual review can happen after a run is completed and never blocks automated progression.
"""

import argparse
import time
from uuid import uuid4

from merchandise_discovery.application.runtime import build_runtime
from merchandise_discovery.application.stage_executor import StageNotImplementedError
from merchandise_discovery.domain.models.common import RunStatus
from merchandise_discovery.domain.models.workflow import StageLog
from merchandise_discovery.shared.configuration import load_settings
from merchandise_discovery.shared.logging import (
    stage_ended,
    stage_error,
    stage_progress,
    stage_started,
)


def _log_event(runtime, run_id: str, message: str, *, stage=None, level: str = "info") -> None:
    """Best-effort persistence for operator context; a logging outage must not mask stage state."""

    try:
        runtime.stage_log_repository.save(
            StageLog(
                run_id=run_id,
                stage_number=stage.stage_number if stage else None,
                execution_id=stage.execution_id if stage else None,
                level=level,
                message=message,
            )
        )
    except Exception as error:  # noqa: BLE001  # Logging must not mask the workflow result.
        print(f"Could not persist worker log ({type(error).__name__}): {message}")


def _process_one(runtime, worker_id: str) -> bool:
    """Claim and process one run, returning whether a run was actually claimed."""

    run = runtime.workflow_orchestrator.claim_next_run(worker_id)
    if run is None:
        return False
    _log_event(runtime, run.run_id, f"Run claimed by {worker_id}.")
    print(f"\nRUN {run.run_id} | CLAIMED", flush=True)

    while True:
        execution = runtime.workflow_orchestrator.start_next_stage(
            run.run_id,
            max_attempts=runtime.max_stage_attempts,
        )
        if execution is None:
            if run.status.value == "failed":
                _log_event(
                    runtime,
                    run.run_id,
                    f"Retry limit reached ({runtime.max_stage_attempts} attempts); run remains failed.",
                    level="error",
                )
                print(f"Run remains failed after retry limit: {run.run_id}")
            else:
                message = (
                    f"No runnable stage found; expected Stage {run.current_stage_number or 'unknown'}."
                )
                _log_event(runtime, run.run_id, message, level="error")
                try:
                    runtime.run_repository.update_status(
                        run.run_id,
                        expected_version=run.version,
                        status=RunStatus.FAILED,
                        current_stage_number=run.current_stage_number,
                        last_error=message,
                        retry_exhausted=False,
                    )
                except Exception as state_error:  # noqa: BLE001  # Preserve the original failure context.
                    print(
                        f"[RUN {run.run_id}] ERROR | Could not persist recovery state: "
                        f"{type(state_error).__name__}: {state_error}",
                        flush=True,
                    )
                print(f"[RUN {run.run_id}] ERROR | {message}", flush=True)
            return True

        active_execution = execution
        _log_event(
            runtime,
            run.run_id,
            f"Stage {execution.stage_number} started (attempt {execution.attempt_number}).",
            stage=execution,
        )
        stage_started(execution, run.run_id)
        try:
            input_data = runtime.stage_executor.prepare(run, execution)
            stage_progress(execution, "Input prepared")
            active_execution = runtime.stage_repository.set_input_data(
                execution.execution_id,
                execution.version,
                input_data,
            )
            result = runtime.stage_executor.execute(run, active_execution, input_data)
            stage_progress(execution, f"Logic complete | {result.output_summary}")
            runtime.stage_repository.complete(
                active_execution.execution_id,
                active_execution.version,
                result.output_data,
                result.output_summary,
                input_data=result.input_data,
                usage=result.usage,
            )
            stage_progress(execution, "Output persisted")
            _log_event(
                runtime,
                run.run_id,
                f"Stage {active_execution.stage_number} completed: {result.output_summary}",
                stage=active_execution,
            )
            run = runtime.workflow_orchestrator.complete_stage_and_run(
                run,
                active_execution,
                stop_after_stage=runtime.stop_after_stage,
            )
            stage_ended(active_execution, result.output_summary)
            if run.status in {RunStatus.PAUSED, RunStatus.COMPLETED}:
                terminal_label = (
                    "PAUSED at configured MVP boundary"
                    if run.status == RunStatus.PAUSED
                    else "COMPLETED"
                )
                print(f"RUN {run.run_id} | {terminal_label}", flush=True)
                return True
        except (StageNotImplementedError, ValueError) as error:
            runtime.workflow_orchestrator.fail_stage_and_run(
                run,
                active_execution,
                str(error),
                max_attempts=runtime.max_stage_attempts,
            )
            _log_event(runtime, run.run_id, str(error), stage=active_execution, level="error")
            stage_error(active_execution, error)
            return True
        except Exception as error:  # noqa: BLE001  # Persist every unexpected stage failure.
            # Unexpected failures are still persisted as stage failures so a worker crash cannot
            # leave a run permanently in `running` with no actionable explanation.
            message = f"Unexpected stage failure: {type(error).__name__}: {error}"
            runtime.workflow_orchestrator.fail_stage_and_run(
                run,
                active_execution,
                message,
                max_attempts=runtime.max_stage_attempts,
            )
            _log_event(runtime, run.run_id, message, stage=active_execution, level="error")
            stage_error(active_execution, error)
            return True


def main() -> None:
    """Run one worker cycle or keep polling until interrupted by the operator."""

    parser = argparse.ArgumentParser(description="Run the merchandise discovery worker.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="Claim and dispatch one pending run.")
    mode.add_argument("--loop", action="store_true", help="Keep polling for pending runs.")
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Seconds to wait between empty queue polls in loop mode (default: 2).",
    )
    parser.add_argument(
        "--worker-id",
        default=f"worker-{uuid4().hex[:8]}",
        help="Stable worker identity used for an atomic run claim.",
    )
    args = parser.parse_args()
    if args.poll_interval <= 0:
        parser.error("--poll-interval must be greater than zero.")

    runtime = build_runtime(load_settings())
    try:
        while True:
            claimed = _process_one(runtime, args.worker_id)
            if args.once:
                print("No pending runs.") if not claimed else None
                return
            if not claimed:
                time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        print("Worker stopped.")
    finally:
        runtime.close()
