"""HTTP routes."""

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Request

from app.api.deps import bind_trace_id, get_analyze_service
from app.schemas.api import AnalyzeRequest, AnalyzeResponse
from app.services.analyze_service import AnalyzeService

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    body: AnalyzeRequest,
    request: Request,
    svc: Annotated[AnalyzeService, Depends(get_analyze_service)],
    trace_header: Annotated[str | None, Depends(bind_trace_id)],
) -> AnalyzeResponse:
    trace_id = trace_header or str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(trace_id=trace_id)
    return await svc.analyze(body, trace_id=trace_id)
