"""ASGI entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.llm.provider import LLMProvider
from app.services.analyze_service import AnalyzeService

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings)
    llm = LLMProvider(settings)
    app.state.llm = llm
    app.state.analyze_service = AnalyzeService(settings, llm)
    logger.info("application_startup", model=settings.openai_model)
    yield
    logger.info("application_shutdown")


app = FastAPI(title="Agentic Orchestration", lifespan=lifespan)
app.include_router(router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "agentic-orchestration", "docs": "/docs"}
