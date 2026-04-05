"""Workflow state mirrors graph channels; API models live in `api.py`."""

import operator
from typing import Annotated, Literal

from typing_extensions import TypedDict

from app.schemas.evaluation import EvaluationResult
from app.schemas.tasks import OrchestrationPlan, WorkerResult, WorkerTask


def merge_timings(
    left: dict[str, float] | None, right: dict[str, float] | None
) -> dict[str, float]:
    """Reducer for per-node timing maps (merge keys from parallel/sequential updates)."""
    out: dict[str, float] = {}
    if left:
        out.update(left)
    if right:
        out.update(right)
    return out


class WorkerPayload(TypedDict, total=False):
    """Merged into graph state for a single `Send` to the worker node."""

    current_task: WorkerTask


class GraphState(TypedDict, total=False):
    """
    LangGraph state schema.

    `worker_results` uses a list reducer so parallel worker nodes can append safely.
    """

    trace_id: str
    user_query: str
    max_refinement_loops: int
    refinement_iteration: int

    plan: OrchestrationPlan | None
    worker_tasks: list[WorkerTask]
    current_task: WorkerTask | None  # set by Send() for worker node

    worker_results: Annotated[list[WorkerResult], operator.add]

    draft_answer: str | None
    evaluation: EvaluationResult | None
    improved_answer: str | None

    error: str | None
    error_stage: str | None

    node_timings_ms: Annotated[dict[str, float], merge_timings]
    model_name: str


ExecutionStatus = Literal["completed", "failed", "partial"]
