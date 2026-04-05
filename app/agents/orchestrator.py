"""Orchestrator: decompose user request into worker tasks."""

from app.agents.prompts import load_prompt
from app.llm.provider import LLMProvider
from app.schemas.tasks import OrchestrationPlan


async def run_orchestrator(
    *,
    llm: LLMProvider,
    user_query: str,
    model: str | None,
    trace_id: str | None,
) -> OrchestrationPlan:
    prompts = load_prompt("orchestrator")
    system = prompts["system"]
    user = prompts["user"].format(user_query=user_query)
    return await llm.complete_structured(
        system_prompt=system,
        user_prompt=user,
        response_model=OrchestrationPlan,
        model=model,
        trace_id=trace_id,
    )
