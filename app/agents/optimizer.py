"""Optimizer: refine draft from evaluator feedback."""

from app.agents.evaluator import evaluation_to_prompt_json
from app.agents.prompts import load_prompt
from app.llm.provider import LLMProvider
from app.schemas.evaluation import EvaluationResult, RefinedOutput


async def run_optimizer(
    *,
    llm: LLMProvider,
    user_query: str,
    draft: str,
    evaluation: EvaluationResult,
    model: str | None,
    trace_id: str | None,
) -> RefinedOutput:
    prompts = load_prompt("optimizer")
    user = prompts["user"].format(
        user_query=user_query,
        draft=draft,
        evaluation_json=evaluation_to_prompt_json(evaluation),
    )
    return await llm.complete_structured(
        system_prompt=prompts["system"],
        user_prompt=user,
        response_model=RefinedOutput,
        model=model,
        trace_id=trace_id,
    )
