"""Async OpenAI client wrapper with retries, timeouts, and structured outputs."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, TypeVar

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, RateLimitError
from openai.types.chat import ChatCompletion
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import Settings
from app.core.logging import get_logger
from app.llm.errors import LLMResponseError, LLMTimeout

T = TypeVar("T", bound=BaseModel)

logger = get_logger(__name__)


class LLMProvider:
    """
    Thin abstraction over the OpenAI SDK.

    Keeps LangChain out of the hot path; swap `AsyncOpenAI` for tests via constructor.
    """

    def __init__(self, settings: Settings, client: AsyncOpenAI | None = None) -> None:
        self._settings = settings
        self._client = client or AsyncOpenAI(
            api_key=settings.openai_api_key or None,
            timeout=settings.openai_timeout_seconds,
        )

    @property
    def model(self) -> str:
        return self._settings.openai_model

    def _retry_decorator(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return retry(
            reraise=True,
            stop=stop_after_attempt(self._settings.llm_max_retries),
            wait=wait_exponential(
                multiplier=1,
                min=self._settings.llm_retry_min_wait_seconds,
                max=self._settings.llm_retry_max_wait_seconds,
            ),
            retry=retry_if_exception_type((RateLimitError, APIConnectionError, APITimeoutError)),
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
        """Call chat.completions.parse with a Pydantic schema."""

        use_model = model or self._settings.openai_model

        async def _call() -> T:
            start = time.perf_counter()
            try:
                completion = await self._client.beta.chat.completions.parse(
                    model=use_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format=response_model,
                )
            except APITimeoutError as e:
                raise LLMTimeout(str(e)) from e

            elapsed_ms = (time.perf_counter() - start) * 1000
            parsed = completion.choices[0].message.parsed
            if parsed is None:
                refusal = completion.choices[0].message.refusal
                raise LLMResponseError(
                    refusal or "Model returned no parsed content",
                )
            logger.debug(
                "llm_structured_complete",
                model=use_model,
                trace_id=trace_id,
                duration_ms=round(elapsed_ms, 2),
                schema=response_model.__name__,
            )
            return parsed

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
        """Plain text completion (aggregator narrative)."""

        use_model = model or self._settings.openai_model

        @self._retry_decorator()
        async def _call() -> ChatCompletion:
            start = time.perf_counter()
            try:
                out = await self._client.chat.completions.create(
                    model=use_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
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
            return out

        resp = await _call()
        content = resp.choices[0].message.content
        if not content:
            raise LLMResponseError("Empty text completion")
        return str(content)
