"""Worker: execute a single scoped task."""

from app.agents.prompts import load_prompt
from app.llm.provider import LLMProvider
from app.schemas.tasks import WorkerStructuredOutput, WorkerTask


async def run_worker(
    *,
    llm: LLMProvider,
    user_query: str,
    task: WorkerTask,
    model: str | None,
    trace_id: str | None,
) -> WorkerStructuredOutput:
    prompts = load_prompt("worker")
    system = prompts["system"]
    user = prompts["user"].format(
        user_query=user_query,
        task_title=task.title,
        objective=task.objective,
        scope=task.scope,
        expected_output=task.expected_output,
    )
    return await llm.complete_structured(
        system_prompt=system,
        user_prompt=user,
        response_model=WorkerStructuredOutput,
        model=model,
        trace_id=trace_id,
    )
