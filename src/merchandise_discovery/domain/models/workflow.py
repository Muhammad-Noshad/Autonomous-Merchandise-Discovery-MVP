"""Typed records for durable workflow and stage execution state.

These models are the contract between application services, repositories, workers, and the UI.
Persisted records intentionally keep raw input/output payloads so a run can be audited or resumed
without reconstructing what an external model returned.
"""

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from merchandise_discovery.domain.models.common import RunStatus, StageStatus


def utc_now() -> datetime:
    """Return timezone-aware UTC timestamps for consistent cross-machine ordering."""

    return datetime.now(timezone.utc)


class RunConfig(BaseModel):
    """Small, configurable funnel limits used by the MVP demo run."""

    max_intersections: int = Field(default=10, ge=1, le=5000)
    max_researched_niches: int = Field(default=3, ge=1, le=100)
    concepts_per_niche: int = Field(default=5, ge=1, le=50)
    artwork_variants_per_concept: int = Field(default=2, ge=1, le=10)
    enable_similarity_ip_check: bool = False


class WorkflowRun(BaseModel):
    """Durable aggregate representing one complete discovery run."""

    model_config = ConfigDict(extra="ignore")

    run_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    status: RunStatus = RunStatus.PENDING
    config: RunConfig = Field(default_factory=RunConfig)
    completed_stages: int = Field(default=0, ge=0, le=17)
    total_stages: int = Field(default=17, ge=1, le=17)
    current_stage_number: int | None = Field(default=None, ge=1, le=17)
    triggered_by: str = "system"
    claimed_by: str | None = None
    version: int = Field(default=0, ge=0)
    last_error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class StageExecution(BaseModel):
    """Durable record for one attemptable stage within a workflow run."""

    model_config = ConfigDict(extra="ignore")

    execution_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    stage_number: int = Field(ge=1, le=17)
    stage_name: str
    status: StageStatus = StageStatus.PENDING
    stage_version: str = "0.1.0"
    attempt_number: int = Field(default=0, ge=0)
    progress_current: int = Field(default=0, ge=0)
    progress_total: int = Field(default=1, ge=1)
    progress_message: str | None = None
    input_data: dict = Field(default_factory=dict)
    output_data: dict = Field(default_factory=dict)
    output_summary: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    version: int = Field(default=0, ge=0)

