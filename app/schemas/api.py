"""HTTP request and response models."""

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.evaluation import EvaluationResult
from app.schemas.tasks import OrchestrationPlan, WorkerResult, WorkerTask


class AnalyzeSettings(BaseModel):
    """Optional execution controls for a single request."""

    max_refinement_loops: int | None = Field(
        default=None,
        ge=0,
        le=10,
        description="Override default max evaluator/refinement cycles.",
    )
    model: str | None = Field(
        default=None,
        description="Override default OpenAI model for this run.",
    )


class AnalyzeRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=16_000)
    settings: AnalyzeSettings | None = None


class ExecutionMetadata(BaseModel):
    trace_id: str
    status: str
    refinement_iterations: int
    max_refinement_loops: int
    model: str
    node_timings_ms: dict[str, float]
    total_duration_ms: float | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class AnalyzeResponse(BaseModel):
    plan: OrchestrationPlan
    worker_tasks: list[WorkerTask]
    worker_results: list[WorkerResult]
    draft_answer: str
    evaluation: EvaluationResult | None
    improved_final_answer: str
    execution: ExecutionMetadata
