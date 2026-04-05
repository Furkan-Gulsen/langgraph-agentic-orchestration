"""High-level service: invoke compiled graph and map to API models."""

from __future__ import annotations

import time
import uuid
from typing import Any, cast

from app.core.config import Settings
from app.core.logging import get_logger
from app.graph.builder import build_analysis_graph
from app.llm.provider import LLMProvider
from app.schemas.api import AnalyzeRequest, AnalyzeResponse, ExecutionMetadata
from app.schemas.evaluation import EvaluationResult
from app.schemas.tasks import OrchestrationPlan, WorkerResult, WorkerTask

logger = get_logger(__name__)


class AnalyzeService:
    """Application service for `/analyze` — owns graph compilation and execution."""

    def __init__(self, settings: Settings, llm: LLMProvider) -> None:
        self._settings = settings
        self._llm = llm
        self._graph = build_analysis_graph(llm, settings)

    async def analyze(self, req: AnalyzeRequest, *, trace_id: str | None = None) -> AnalyzeResponse:
        tid = trace_id or str(uuid.uuid4())
        max_loops = (
            req.settings.max_refinement_loops
            if req.settings and req.settings.max_refinement_loops is not None
            else self._settings.default_max_refinement_loops
        )
        if req.settings and req.settings.model:
            model_name = req.settings.model
        else:
            model_name = self._settings.openai_model

        initial: dict[str, Any] = {
            "trace_id": tid,
            "user_query": req.query,
            "max_refinement_loops": max_loops,
            "refinement_iteration": 0,
            "worker_tasks": [],
            "worker_results": [],
            "node_timings_ms": {},
            "model_name": model_name,
        }

        t0 = time.perf_counter()
        final: dict[str, Any] = cast(dict[str, Any], await self._graph.ainvoke(initial))
        total_ms = (time.perf_counter() - t0) * 1000

        plan = final.get("plan")
        if not isinstance(plan, OrchestrationPlan):
            plan = OrchestrationPlan(
                summary="",
                decomposition_rationale="",
                tasks=[],
            )

        tasks = final.get("worker_tasks") or []
        if tasks and not isinstance(tasks[0], WorkerTask):
            tasks = [WorkerTask.model_validate(x) for x in tasks]

        results = final.get("worker_results") or []
        if results and not isinstance(results[0], WorkerResult):
            results = [WorkerResult.model_validate(x) for x in results]

        draft = str(final.get("draft_answer") or "")
        improved = final.get("improved_answer")
        evaluation = final.get("evaluation")
        if isinstance(evaluation, dict):
            evaluation = EvaluationResult.model_validate(evaluation)
        err = final.get("error")

        refinement_iterations = int(final.get("refinement_iteration") or 0)
        status = "failed" if err else "completed"

        final_text = str(improved) if improved else draft

        exec_meta = ExecutionMetadata(
            trace_id=tid,
            status=status,
            refinement_iterations=refinement_iterations,
            max_refinement_loops=max_loops,
            model=model_name,
            node_timings_ms=dict(final.get("node_timings_ms") or {}),
            total_duration_ms=round(total_ms, 2),
            extra={"error": err, "error_stage": final.get("error_stage")}
            if err
            else {},
        )

        if err:
            logger.warning("analyze_finished_with_error", trace_id=tid, error=err)

        return AnalyzeResponse(
            plan=plan,
            worker_tasks=list(tasks),
            worker_results=list(results),
            draft_answer=draft,
            evaluation=evaluation if isinstance(evaluation, EvaluationResult) else None,
            improved_final_answer=final_text,
            execution=exec_meta,
        )
