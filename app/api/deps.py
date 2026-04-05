"""FastAPI dependencies."""


from fastapi import Request

from app.core.config import Settings, get_settings
from app.llm.provider import LLMProvider
from app.services.analyze_service import AnalyzeService


def get_app_settings() -> Settings:
    return get_settings()


def get_llm(request: Request) -> LLMProvider:
    return request.app.state.llm  # type: ignore[no-any-return]


def get_analyze_service(request: Request) -> AnalyzeService:
    return request.app.state.analyze_service  # type: ignore[no-any-return]


async def bind_trace_id(request: Request) -> str | None:
    """Prefer client-provided request id header."""
    return request.headers.get("x-request-id") or request.headers.get("x-trace-id")
