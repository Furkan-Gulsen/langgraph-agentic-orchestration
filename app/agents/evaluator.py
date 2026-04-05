"""Evaluator: structured quality review."""

import json

from app.agents.prompts import load_prompt
from app.llm.provider import LLMProvider
from app.schemas.evaluation import EvaluationResult


async def run_evaluator(
    *,
    llm: LLMProvider,
    user_query: str,
    draft: str,
    model: str | None,
    trace_id: str | None,
) -> EvaluationResult:
    prompts = load_prompt("evaluator")
    # Evaluator uses structured output; free-form draft stays in user message.
    user = prompts["user"].format(user_query=user_query, draft=draft)
    return await llm.complete_structured(
        system_prompt=prompts["system"],
        user_prompt=user,
        response_model=EvaluationResult,
        model=model,
        trace_id=trace_id,
    )


def evaluation_to_prompt_json(evaluation: EvaluationResult) -> str:
    """Serialize evaluation for optimizer input (explicit, stable fields)."""
    return json.dumps(evaluation.model_dump(), ensure_ascii=False, indent=2)
