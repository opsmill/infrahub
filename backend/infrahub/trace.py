import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter as GRPCSpanExporter,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as HTTPSpanExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SpanExporter
from opentelemetry.trace import StatusCode

from infrahub.worker import WORKER_IDENTITY


def get_current_span_with_context() -> trace.Span:
    return trace.get_current_span()


def get_traceid() -> str | None:
    current_span = get_current_span_with_context()
    trace_id = current_span.get_span_context().trace_id
    if trace_id == 0:
        return None
    return hex(trace_id)


def set_span_status(status_code: StatusCode) -> None:
    current_span = get_current_span_with_context()
    if current_span.is_recording():
        status = StatusCode(status_code)
        current_span.set_status(status)
        # current_span.set_attribute("status_code", status)


def set_span_data(key: str, value: str) -> None:
    current_span = get_current_span_with_context()
    if current_span.is_recording():
        current_span.set_attribute(key, value)


def add_span_event(event_name: str, event_attributes: dict) -> None:
    current_span = get_current_span_with_context()
    if current_span.is_recording():
        current_span.add_event(event_name, event_attributes)


def add_span_exception(exception: Exception) -> None:
    set_span_status(StatusCode.ERROR)
    current_span = get_current_span_with_context()
    if current_span.is_recording():
        current_span.record_exception(exception)


def create_tracer_provider(
    service: str,
    version: str,
    exporter_type: str,
    exporter_endpoint: str | None = None,
    exporter_protocol: str | None = None,
) -> TracerProvider:
    # Create a BatchSpanProcessor exporter based on the type
    if exporter_type == "console":
        exporter: SpanExporter = ConsoleSpanExporter()
    elif exporter_type == "otlp":
        if not exporter_endpoint:
            raise ValueError("Exporter type is set to otlp but endpoint is not set")
        if exporter_protocol == "http/protobuf":
            exporter = HTTPSpanExporter(endpoint=exporter_endpoint)
        elif exporter_protocol == "grpc":
            exporter = GRPCSpanExporter(endpoint=exporter_endpoint)
    else:
        raise ValueError("Exporter type unsupported by Infrahub")

    extra_attributes = {}
    if os.getenv("OTEL_RESOURCE_ATTRIBUTES"):
        extra_attributes = dict(attr.split("=") for attr in os.getenv("OTEL_RESOURCE_ATTRIBUTES", "").split(","))

    # Resource can be required for some backends, e.g. Jaeger
    resource = Resource(
        attributes={
            "service.name": service,
            "service.version": version,
            "worker.id": WORKER_IDENTITY,
            **extra_attributes,
        }
    )
    span_processor = BatchSpanProcessor(exporter)
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(span_processor)

    return tracer_provider


def configure_trace(
    service: str,
    version: str,
    exporter_type: str,
    exporter_endpoint: str | None = None,
    exporter_protocol: str | None = None,
) -> None:
    # Create a trace provider with the exporter
    tracer_provider = create_tracer_provider(
        service=service,
        version=version,
        exporter_type=exporter_type,
        exporter_endpoint=exporter_endpoint,
        exporter_protocol=exporter_protocol,
    )

    # Register the trace provider
    trace.set_tracer_provider(tracer_provider)
