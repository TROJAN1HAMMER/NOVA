"""
NOVA — OpenTelemetry Tracing

One setup function called from both entry points that need it: the
FastAPI app (`app/main.py`) and the Celery worker process
(`app/workers/celery_app.py`) — a trace started by an API request that
enqueues a scan continues, via Celery's built-in trace-context
propagation (`CeleryInstrumentor`), into the worker process that actually
runs the scan, giving one continuous trace across the process boundary
instead of two disconnected ones.

Exporter target is the standard `OTEL_EXPORTER_OTLP_ENDPOINT` /
`OTEL_EXPORTER_OTLP_PROTOCOL` / `OTEL_SERVICE_NAME` environment variables
that every OTel SDK reads natively — deliberately not reinvented as
NOVA-specific settings, so this points at whatever OTLP collector
(Grafana Tempo, Jaeger, an OTel Collector, ...) the deployment already
has configured for every other service, the same way any other
OTel-instrumented app in the same cluster would be configured. If
`OTEL_EXPORTER_OTLP_ENDPOINT` isn't set, tracing is set up with a
no-op/console exporter — instrumentation stays active (so span context
still flows into structlog, see `app/core/logging.py`) but nothing is
shipped anywhere, which is the safe default for local dev.
"""

import os

import structlog
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

logger = structlog.get_logger(__name__)

_configured = False


def setup_telemetry(*, service_name: str) -> None:
    """
    Idempotent — safe to call from both `app/main.py` and
    `app/workers/celery_app.py` even if a process somehow imports both
    (it won't in practice, but this makes the function safe regardless).
    """
    global _configured
    if _configured:
        return
    _configured = True

    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)

    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        logger.info("telemetry.otlp_exporter_configured", endpoint=otlp_endpoint, service=service_name)
    else:
        # No collector configured — keep instrumentation active (spans
        # still exist, still bind trace_id into structlog) without
        # spamming stdout with every span in a real deployment; only
        # actually render them to the console in debug mode, where seeing
        # them inline is useful.
        from app.config import get_settings

        if get_settings().debug:
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        logger.info("telemetry.no_otlp_endpoint_configured", service=service_name)

    trace.set_tracer_provider(provider)


def instrument_fastapi(app) -> None:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app)


def instrument_sqlalchemy(engine) -> None:
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)


def instrument_celery() -> None:
    from opentelemetry.instrumentation.celery import CeleryInstrumentor

    CeleryInstrumentor().instrument()


def instrument_httpx() -> None:
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    HTTPXClientInstrumentor().instrument()


def instrument_redis() -> None:
    from opentelemetry.instrumentation.redis import RedisInstrumentor

    RedisInstrumentor().instrument()
