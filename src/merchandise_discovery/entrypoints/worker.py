"""Command-line entrypoint for the background workflow worker.

The worker executes automated stages and stops cleanly at Stage 17, where the browser owns human
approval. This prevents a pending reviewer decision from being misreported as an unavailable stage.
"""

import argparse
from uuid import uuid4

from merchandise_discovery.application.runtime import build_runtime
from merchandise_discovery.application.stage_executor import StageNotImplementedError
from merchandise_discovery.shared.configuration import load_settings


def main() -> None:
    """Claim and dispatch one pending run, recording unavailable stage work as a failure."""

    parser = argparse.ArgumentParser(description="Run the merchandise discovery worker.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Claim and dispatch one pending run.",
    )
    parser.add_argument(
        "--worker-id",
        default=f"worker-{uuid4().hex[:8]}",
        help="Stable worker identity used for an atomic run claim.",
    )
    args = parser.parse_args()
    if not args.once:
        parser.error("--once is required until the continuous worker loop is implemented.")

    runtime = build_runtime(load_settings())
    try:
        run = runtime.workflow_orchestrator.claim_next_run(args.worker_id)
        if run is None:
            print("No pending runs.")
            return

        while True:
            next_execution = runtime.workflow_orchestrator.next_runnable_stage(run.run_id)
            if next_execution is not None and next_execution.stage_number == 17:
                print(f"Run awaiting human approval: {run.run_id}")
                return
            execution = runtime.workflow_orchestrator.start_next_stage(run.run_id)
            if execution is None:
                print(f"Run completed all automated stages: {run.run_id}")
                return

            active_execution = execution
            try:
                input_data = runtime.stage_executor.prepare(run, execution)
                active_execution = runtime.stage_repository.set_input_data(
                    execution.execution_id,
                    execution.version,
                    input_data,
                )
                result = runtime.stage_executor.execute(run, active_execution, input_data)
                runtime.stage_repository.complete(
                    active_execution.execution_id,
                    active_execution.version,
                    result.output_data,
                    result.output_summary,
                    input_data=result.input_data,
                )
                run = runtime.workflow_orchestrator.complete_stage_and_run(run, active_execution)
                print(f"Stage {active_execution.stage_number} completed for run {run.run_id}.")
            except (StageNotImplementedError, ValueError) as error:
                runtime.workflow_orchestrator.fail_stage_and_run(
                    run,
                    active_execution,
                    str(error),
                )
                print(f"Run failed explicitly: {run.run_id} — {error}")
                return
    finally:
        runtime.close()
