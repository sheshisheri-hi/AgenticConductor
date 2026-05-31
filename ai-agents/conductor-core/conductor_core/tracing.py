"""OpenTelemetry tracing helpers for Conductor.

Provides a lightweight span wrapper so orchestrator/runner can emit traces
without hard-coupling to any specific exporter.

Default behaviour (no config):
  - Uses OTEL NoopTracerProvider → zero overhead, zero side effects
  - Set CONDUCTOR_OTEL_ENDPOINT to enable OTLP export (e.g. Jaeger, Honeycomb, Datadog)

Usage in framework code:
    from conductor_core.tracing import get_tracer, record_agent_span

    with get_tracer().start_as_current_span("stage:triage") as span:
        span.set_attribute("agent", "triage")
        ...
"""

from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME

_CONFIGURED = False
_SERVICE = "conductor"


def configure_tracing(service_name: str = "conductor", endpoint: str | None = None) -> None:
    """Configure global OTEL tracer. Call once at application startup.

    Args:
        service_name: Service name shown in OTEL UIs (e.g. "my-security-bot")
        endpoint: OTLP gRPC endpoint (e.g. "http://localhost:4317").
                  If None, reads CONDUCTOR_OTEL_ENDPOINT from env.
                  If still None, installs a no-op provider (no spans exported).
    """
    global _CONFIGURED, _SERVICE
    _SERVICE = service_name

    endpoint = endpoint or os.environ.get("CONDUCTOR_OTEL_ENDPOINT", "")
    if not endpoint:
        # No-op — OTEL instrumentation exists in code but nothing is exported
        trace.set_tracer_provider(trace.NoOpTracerProvider())
        _CONFIGURED = True
        return

    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter(endpoint=endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    except ImportError:
        # opentelemetry-exporter-otlp-proto-grpc not installed — fall back silently
        pass

    trace.set_tracer_provider(provider)
    _CONFIGURED = True


def get_tracer(name: str = "conductor") -> trace.Tracer:
    """Return the global tracer. Auto-configures no-op if not already set up."""
    if not _CONFIGURED:
        configure_tracing()
    return trace.get_tracer(name)
