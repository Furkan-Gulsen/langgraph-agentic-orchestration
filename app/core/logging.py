"""Structured logging with optional JSON output and trace/request correlation."""

import logging
import sys
from collections.abc import Mapping, MutableMapping
from typing import Any, cast

import structlog
from structlog.types import Processor

from app.core.config import Settings


def _add_trace_id(
    logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
) -> Mapping[str, Any]:
    """Ensure trace_id appears in every log line when bound."""
    return event_dict


def configure_logging(settings: Settings) -> None:
    """Configure stdlib logging + structlog for the process."""
    log_level = getattr(logging, settings.log_level, logging.INFO)

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_trace_id,
    ]

    if settings.log_json:
        processors: list[Processor] = [
            *shared_processors,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(level=log_level, format="%(message)s", stream=sys.stdout)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger for the given module name."""
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
