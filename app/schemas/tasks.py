"""Task and plan models for orchestration and worker I/O."""

from typing import Literal

from pydantic import BaseModel, Field


class WorkerTask(BaseModel):
    """A single unit of work produced by the orchestrator."""

    task_id: str = Field(..., description="Stable identifier for ordering and traceability.")
    title: str
    objective: str = Field(..., description="What the worker must achieve.")
    scope: str = Field(..., description="Boundaries: geography, timeframe, exclusions.")
    expected_output: str = Field(..., description="Structured description of deliverable fields.")


class OrchestrationPlan(BaseModel):
    """High-level plan and decomposition rationale."""

    summary: str = Field(..., description="Short summary of the user request interpretation.")
    decomposition_rationale: str = Field(
        ...,
        description="Why tasks were split this way (e.g. per country, per theme).",
    )
    tasks: list[WorkerTask] = Field(default_factory=list)


class WorkerStructuredOutput(BaseModel):
    """Structured result from a worker (parsed via OpenAI structured output)."""

    key_points: list[str] = Field(default_factory=list)
    analysis: str = Field(..., description="Scoped narrative for this task only.")
    caveats: list[str] = Field(
        default_factory=list,
        description="Uncertainties, data gaps, or scope limits.",
    )
    confidence: Literal["low", "medium", "high"] = "medium"


class WorkerResult(BaseModel):
    """Worker execution result stored in workflow state."""

    task_id: str
    task_title: str
    output: WorkerStructuredOutput
    model: str
    duration_seconds: float
    status: Literal["ok", "error"] = "ok"
    error_message: str | None = None
