"""LangGraph node callables; dependencies captured via closures (explicit factories)."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from app.agents.aggregator import run_aggregator
from app.agents.evaluator import run_evaluator
from app.agents.optimizer import run_optimizer
from app.agents.orchestrator import run_orchestrator
from app.agents.worker import run_worker
from app.core.config import Settings
from app.llm.errors import LLMError
from app.llm.provider import LLMProvider
from app.schemas.evaluation import EvaluationResult
from app.schemas.tasks import OrchestrationPlan, WorkerResult, WorkerStructuredOutput, WorkerTask
from app.schemas.workflow import GraphState


def _worker_structured_fallback(msg: str) -> WorkerStructuredOutput:
    return WorkerStructuredOutput(
        key_points=[],
        analysis=f"Worker failed: {msg}",
        caveats=["Task execution error; see logs."],
        confidence="low",
    )


def _timed(name: str) -> tuple[float, Callable[[], dict[str, float]]]:
    start = time.perf_counter()

    def finish() -> dict[str, float]:
        return {name: (time.perf_counter() - start) * 1000}

    return start, finish


def _resolve_model(state: GraphState, settings: Settings) -> str:
    return state.get("model_name") or settings.openai_model


def _current_draft_text(state: GraphState) -> str:
    """Latest narrative for evaluate/refine: optimizer output if any, else aggregate draft."""
    improved = state.get("improved_answer")
    if improved:
        return str(improved)
    return str(state.get("draft_answer") or "")


async def orchestrate_node(
    state: GraphState,
    *,
    llm: LLMProvider,
    settings: Settings,
    config: Any = None,
) -> dict[str, object]:
    """Decompose user query into tasks; ensure at least one task exists."""
    _, finish = _timed("orchestrate")
    trace_id = state.get("trace_id")
    user_query = state["user_query"]
    model = _resolve_model(state, settings)
    try:
        plan = await run_orchestrator(
            llm=llm,
            user_query=user_query,
            model=model,
            trace_id=trace_id,
        )
        tasks = _ensure_tasks(plan, user_query)
        plan = plan.model_copy(update={"tasks": tasks})
        return {
            "plan": plan,
            "worker_tasks": tasks,
            "node_timings_ms": finish(),
        }
    except LLMError as e:
        return {
            "error": str(e),
            "error_stage": "orchestrate",
            "node_timings_ms": finish(),
        }
    except Exception as e:  # noqa: BLE001 — surface unexpected failures in state
        return {
            "error": repr(e),
            "error_stage": "orchestrate",
            "node_timings_ms": finish(),
        }


def _ensure_tasks(plan: OrchestrationPlan, user_query: str) -> list[WorkerTask]:
    if plan.tasks:
        fixed: list[WorkerTask] = []
        for i, t in enumerate(plan.tasks):
            tid = t.task_id.strip() if t.task_id else f"task_{i + 1:03d}"
            fixed.append(t.model_copy(update={"task_id": tid}))
        return fixed
    return [
        WorkerTask(
            task_id="task_001",
            title="Primary analysis scope",
            objective="Address the user request with best-effort structured analysis.",
            scope="Global to the question; no narrower decomposition was returned.",
            expected_output="Key points, analysis narrative, caveats, confidence.",
        )
    ]


async def worker_node(
    state: GraphState,
    *,
    llm: LLMProvider,
    settings: Settings,
    config: Any = None,
) -> dict[str, object]:
    """Execute one worker task (invoked via `Send` with `current_task`)."""
    task = state.get("current_task")
    if task is None:
        return {
            "error": "worker missing current_task",
            "error_stage": "worker",
            "worker_results": [],
            "node_timings_ms": {"worker:unknown": 0.0},
        }
    key = f"worker:{task.task_id}"
    _, finish = _timed(key)
    trace_id = state.get("trace_id")
    user_query = state["user_query"]
    model = _resolve_model(state, settings)
    try:
        out = await run_worker(
            llm=llm,
            user_query=user_query,
            task=task,
            model=model,
            trace_id=trace_id,
        )
        result = WorkerResult(
            task_id=task.task_id,
            task_title=task.title,
            output=out,
            model=model,
            duration_seconds=0.0,
            status="ok",
        )
        timing = finish()
        # attach wall duration on result for API consumers
        result = result.model_copy(
            update={"duration_seconds": round(timing[key] / 1000.0, 4)}
        )
        return {"worker_results": [result], "node_timings_ms": timing}
    except LLMError as e:
        err = WorkerResult(
            task_id=task.task_id,
            task_title=task.title,
            output=_worker_structured_fallback(str(e)),
            model=model,
            duration_seconds=0.0,
            status="error",
            error_message=str(e),
        )
        return {"worker_results": [err], "node_timings_ms": finish()}
    except Exception as e:  # noqa: BLE001
        err = WorkerResult(
            task_id=task.task_id,
            task_title=task.title,
            output=_worker_structured_fallback(repr(e)),
            model=model,
            duration_seconds=0.0,
            status="error",
            error_message=repr(e),
        )
        return {"worker_results": [err], "node_timings_ms": finish()}


async def aggregate_node(
    state: GraphState,
    *,
    llm: LLMProvider,
    settings: Settings,
    config: Any = None,
) -> dict[str, object]:
    _, finish = _timed("aggregate")
    trace_id = state.get("trace_id")
    raw_plan = state.get("plan")
    if raw_plan is None:
        return {
            "error": "aggregate ran without plan",
            "error_stage": "aggregate",
            "node_timings_ms": finish(),
        }
    plan = (
        OrchestrationPlan.model_validate(raw_plan)
        if isinstance(raw_plan, dict)
        else raw_plan
    )
    raw_results = list(state.get("worker_results") or [])
    results: list[WorkerResult] = []
    for r in raw_results:
        if isinstance(r, WorkerResult):
            results.append(r)
        else:
            results.append(WorkerResult.model_validate(r))
    user_query = state["user_query"]
    model = _resolve_model(state, settings)
    try:
        draft = await run_aggregator(
            llm=llm,
            user_query=user_query,
            plan=plan,
            worker_results=results,
            model=model,
            trace_id=trace_id,
        )
        return {"draft_answer": draft, "node_timings_ms": finish()}
    except LLMError as e:
        return {
            "error": str(e),
            "error_stage": "aggregate",
            "node_timings_ms": finish(),
        }
    except Exception as e:  # noqa: BLE001
        return {
            "error": repr(e),
            "error_stage": "aggregate",
            "node_timings_ms": finish(),
        }


async def evaluate_node(
    state: GraphState,
    *,
    llm: LLMProvider,
    settings: Settings,
    config: Any = None,
) -> dict[str, object]:
    _, finish = _timed("evaluate")
    trace_id = state.get("trace_id")
    user_query = state["user_query"]
    draft = _current_draft_text(state)
    model = _resolve_model(state, settings)
    try:
        evaluation = await run_evaluator(
            llm=llm,
            user_query=user_query,
            draft=draft,
            model=model,
            trace_id=trace_id,
        )
        return {"evaluation": evaluation, "node_timings_ms": finish()}
    except LLMError as e:
        return {
            "error": str(e),
            "error_stage": "evaluate",
            "node_timings_ms": finish(),
        }
    except Exception as e:  # noqa: BLE001
        return {
            "error": repr(e),
            "error_stage": "evaluate",
            "node_timings_ms": finish(),
        }


async def refine_node(
    state: GraphState,
    *,
    llm: LLMProvider,
    settings: Settings,
    config: Any = None,
) -> dict[str, object]:
    _, finish = _timed("refine")
    trace_id = state.get("trace_id")
    user_query = state["user_query"]
    draft = _current_draft_text(state)
    evaluation = state.get("evaluation")
    model = _resolve_model(state, settings)
    iteration = int(state.get("refinement_iteration") or 0)
    raw_ev = evaluation
    if raw_ev is None:
        return {
            "error": "refine without evaluation",
            "error_stage": "refine",
            "node_timings_ms": finish(),
        }
    if isinstance(raw_ev, dict):
        ev_model = EvaluationResult.model_validate(raw_ev)
    elif isinstance(raw_ev, EvaluationResult):
        ev_model = raw_ev
    else:
        return {
            "error": "refine: invalid evaluation shape",
            "error_stage": "refine",
            "node_timings_ms": finish(),
        }
    try:
        refined = await run_optimizer(
            llm=llm,
            user_query=user_query,
            draft=draft,
            evaluation=ev_model,
            model=model,
            trace_id=trace_id,
        )
        return {
            "improved_answer": refined.revised_answer,
            "refinement_iteration": iteration + 1,
            "node_timings_ms": finish(),
        }
    except LLMError as e:
        return {
            "error": str(e),
            "error_stage": "refine",
            "node_timings_ms": finish(),
        }
    except Exception as e:  # noqa: BLE001
        return {
            "error": repr(e),
            "error_stage": "refine",
            "node_timings_ms": finish(),
        }


def _state_to_send_payload(state: GraphState, **updates: object) -> dict[str, object]:
    """Build a mergeable dict for `Send` (runtime state is a plain dict)."""
    base: dict[str, object] = dict(state)
    base.update(updates)
    return base


def route_after_orchestrate(state: GraphState) -> object:
    """Fan-out to workers or skip to aggregate if no tasks (defensive)."""
    from langgraph.graph import END
    from langgraph.types import Send

    if state.get("error"):
        return END
    tasks = state.get("worker_tasks") or []
    if not tasks:
        return [Send("aggregate", _state_to_send_payload(state))]
    return [Send("worker", _state_to_send_payload(state, current_task=t)) for t in tasks]


def route_after_evaluate(state: GraphState) -> object:
    """Decide whether to refine or finish (`END` sentinel or `"refine"`)."""
    from langgraph.graph import END

    if state.get("error"):
        return END
    raw_ev = state.get("evaluation")
    ev: EvaluationResult | None
    if raw_ev is None:
        return END
    if isinstance(raw_ev, EvaluationResult):
        ev = raw_ev
    elif isinstance(raw_ev, dict):
        ev = EvaluationResult.model_validate(raw_ev)
    else:
        return END
    max_loops = int(state.get("max_refinement_loops") or 0)
    iteration = int(state.get("refinement_iteration") or 0)
    if ev.should_refine and max_loops > 0 and iteration < max_loops:
        return "refine"
    return END
