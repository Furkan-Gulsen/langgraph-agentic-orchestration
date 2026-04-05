"""Compile the LangGraph `StateGraph` for the orchestrator–workers–evaluator workflow."""

from __future__ import annotations

from typing import Any

from langgraph.graph import START, StateGraph

from app.core.config import Settings
from app.graph import nodes
from app.llm.provider import LLMProvider
from app.schemas.workflow import GraphState


def build_analysis_graph(llm: LLMProvider, settings: Settings) -> Any:
    """
    Wire nodes and conditional edges.

    `route_after_orchestrate` may return `END` (orchestration failure), `Send` workers,
    or `Send` to aggregate when there are zero tasks.
    """
    g: StateGraph[GraphState] = StateGraph(GraphState)

    async def _orchestrate(state: GraphState) -> dict[str, object]:
        return await nodes.orchestrate_node(state, llm=llm, settings=settings)

    async def _worker(state: GraphState) -> dict[str, object]:
        return await nodes.worker_node(state, llm=llm, settings=settings)

    async def _aggregate(state: GraphState) -> dict[str, object]:
        return await nodes.aggregate_node(state, llm=llm, settings=settings)

    async def _evaluate(state: GraphState) -> dict[str, object]:
        return await nodes.evaluate_node(state, llm=llm, settings=settings)

    async def _refine(state: GraphState) -> dict[str, object]:
        return await nodes.refine_node(state, llm=llm, settings=settings)

    g.add_node("orchestrate", _orchestrate)
    g.add_node("worker", _worker)
    g.add_node("aggregate", _aggregate)
    g.add_node("evaluate", _evaluate)
    g.add_node("refine", _refine)

    g.add_edge(START, "orchestrate")
    # Return value may be `END`, or a list of `Send` (workers / aggregate skip).
    g.add_conditional_edges("orchestrate", nodes.route_after_orchestrate)
    g.add_edge("worker", "aggregate")
    g.add_edge("aggregate", "evaluate")
    g.add_conditional_edges("evaluate", nodes.route_after_evaluate)
    g.add_edge("refine", "evaluate")

    return g.compile()
