"""
NOVA — Centralized Logging Configuration
Wires structlog into stdlib logging so uvicorn, SQLAlchemy, and application
loggers all emit through the same processor pipeline (JSON in production,
readable console output in development).
"""

import logging
import sys

import structlog
from opentelemetry import trace

from app.config import Settings


def _add_trace_context(logger, method_name, event_dict):
    """
    Binds the active OpenTelemetry span's trace_id/span_id into every log
    line emitted while that span is active — the join key between "find
    this request/task in the logs" and "find this request/task in Tempo/
    Jaeger". A no-op (both fields simply absent) outside any span, or
    wherever `app.core.telemetry.setup_telemetry` hasn't been called
    (tracing is disabled) — never raises either way.
    """
    span = trace.get_current_span()
    if span is None:
        return event_dict
    context = span.get_span_context()
    if context is None or not context.is_valid:
        return event_dict
    event_dict["trace_id"] = format(context.trace_id, "032x")
    event_dict["span_id"] = format(context.span_id, "016x")
    return event_dict


def configure_logging(settings: Settings) -> None:
    """
    Call once at process startup, before any logger is used.

    - development: colored, human-readable console renderer
    - production:  structured JSON renderer (safe for log aggregators)
    """
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _add_trace_context,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer = (
        structlog.dev.ConsoleRenderer(colors=True)
        if settings.app_env != "production"
        else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)

    # Quiet down noisy third-party loggers unless we're actively debugging.
    for noisy in ("uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING if not settings.debug else logging.INFO)
