"""LangChain ChatOpenAI wrapper with retries, timeouts, and structured outputs."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, TypeVar

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from openai import APIConnectionError, APITimeoutError, RateLimitError
from pydantic import BaseModel, SecretStr
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import Settings
from app.core.logging import get_logger
from app.llm.errors import LLMResponseError, LLMTimeout

T = TypeVar("T", bound=BaseModel)

logger = get_logger(__name__)


def _text_from_ai_message(msg: AIMessage) -> str:
    raw: object = msg.content
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        return "".join(_coerce_content_part(p) for p in raw)
    return str(raw)


def _coerce_content_part(part: object) -> str:
    if isinstance(part, str):
        return part
    if isinstance(part, dict) and part.get("type") == "text":
        return str(part.get("text", ""))
    return str(part)


def _retryable_openai_error(exc: BaseException) -> bool:
    e: BaseException | None = exc
    while e is not None:
        if isinstance(e, (RateLimitError, APIConnectionError, APITimeoutError)):
            return True
        e = e.__cause__
    return False


class LLMProvider:
    def __init__(self, settings: Settings, chat_model: BaseChatModel | None = None) -> None:
        self._settings = settings
        self._llm: BaseChatModel = chat_model or ChatOpenAI(
            model=settings.openai_model,
            api_key=SecretStr(settings.openai_api_key) if settings.openai_api_key else None,
            timeout=settings.openai_timeout_seconds,
            max_retries=0,
        )

    @property
    def model(self) -> str:
        return self._settings.openai_model

    def _bound(self, model: str | None) -> BaseChatModel:
        """Per-call model override (e.g. request `settings.model` vs default)."""
        use_model = model or self._settings.openai_model
        if use_model == self._settings.openai_model:
            return self._llm
        return self._llm.bind(model=use_model)  # type: ignore[return-value]

    def _retry_decorator(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return retry(
            reraise=True,
            stop=stop_after_attempt(self._settings.llm_max_retries),
            wait=wait_exponential(
                multiplier=1,
                min=self._settings.llm_retry_min_wait_seconds,
                max=self._settings.llm_retry_max_wait_seconds,
            ),
            retry=retry_if_exception(_retryable_openai_error),
        )

    async def complete_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        model: str | None = None,
        trace_id: str | None = None,
    ) -> T:
        """Structured output via LangChain `with_structured_output` (Pydantic schema)."""

        use_model = model or self._settings.openai_model
        llm = self._bound(model)

        async def _call() -> T:
            start = time.perf_counter()
            try:
                structured = llm.with_structured_output(response_model)
                result = await structured.ainvoke(
                    [
                        SystemMessage(content=system_prompt),
                        HumanMessage(content=user_prompt),
                    ],
                )
            except APITimeoutError as e:
                raise LLMTimeout(str(e)) from e

            elapsed_ms = (time.perf_counter() - start) * 1000
            if result is None:
                raise LLMResponseError("Model returned no structured content")
            if isinstance(result, dict):
                result = response_model.model_validate(result)
            elif not isinstance(result, response_model):
                raise LLMResponseError(
                    f"Expected {response_model.__name__}, got {type(result).__name__}",
                )
            logger.debug(
                "llm_structured_complete",
                model=use_model,
                trace_id=trace_id,
                duration_ms=round(elapsed_ms, 2),
                schema=response_model.__name__,
            )
            return result

        wrapped = self._retry_decorator()(_call)
        try:
            out: T = await wrapped()
            return out
        except TimeoutError as e:
            raise LLMTimeout() from e

    async def complete_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        trace_id: str | None = None,
    ) -> str:
        """Plain text completion (e.g. aggregator narrative)."""

        use_model = model or self._settings.openai_model
        llm = self._bound(model)

        @self._retry_decorator()
        async def _call() -> AIMessage:
            start = time.perf_counter()
            try:
                out = await llm.ainvoke(
                    [
                        SystemMessage(content=system_prompt),
                        HumanMessage(content=user_prompt),
                    ],
                )
            except APITimeoutError as e:
                raise LLMTimeout(str(e)) from e
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.debug(
                "llm_text_complete",
                model=use_model,
                trace_id=trace_id,
                duration_ms=round(elapsed_ms, 2),
            )
            if not isinstance(out, AIMessage):
                raise LLMResponseError("Unexpected message type from chat model")
            return out

        resp = await _call()
        text = _text_from_ai_message(resp)
        if not text.strip():
            raise LLMResponseError("Empty text completion")
        return text
