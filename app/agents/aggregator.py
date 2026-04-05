"""Aggregator: merge worker outputs into a draft."""

import json

from app.agents.prompts import load_prompt
from app.llm.provider import LLMProvider
from app.schemas.tasks import OrchestrationPlan, WorkerResult


async def run_aggregator(
    *,
    llm: LLMProvider,
    user_query: str,
    plan: OrchestrationPlan,
    worker_results: list[WorkerResult],
    model: str | None,
    trace_id: str | None,
) -> str:
    prompts = load_prompt("aggregator")
    blobs: list[dict[str, object]] = []
    for r in sorted(worker_results, key=lambda x: x.task_id):
        blobs.append(
            {
                "task_id": r.task_id,
                "title": r.task_title,
                "key_points": r.output.key_points,
                "analysis": r.output.analysis,
                "caveats": r.output.caveats,
                "confidence": r.output.confidence,
            }
        )
    user = prompts["user"].format(
        user_query=user_query,
        plan_summary=plan.summary,
        worker_blobs=json.dumps(blobs, ensure_ascii=False, indent=2),
    )
    return await llm.complete_text(
        system_prompt=prompts["system"],
        user_prompt=user,
        model=model,
        trace_id=trace_id,
    )
