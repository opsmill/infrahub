import os
from pathlib import Path
from typing import Any

import requests
from grpc import ssl_channel_credentials
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


class InsecureTLSSession(requests.Session):
    """Session that never verifies TLS certificates, overriding any per-request `verify` value."""

    def merge_environment_settings(self, *args: Any, **kwargs: Any) -> Any:
        settings = super().merge_environment_settings(*args, **kwargs)
        settings["verify"] = False
        return settings


def create_span_exporter(
    exporter_type: str,
    insecure: bool,
    tls_insecure: bool,
    exporter_endpoint: str | None = None,
    exporter_protocol: str | None = None,
    tls_ca_bundle: str | None = None,
) -> SpanExporter:
    if exporter_type == "console":
        return ConsoleSpanExporter()
    if exporter_type != "otlp":
        raise ValueError("Exporter type unsupported by Infrahub")
    if not exporter_endpoint:
        raise ValueError("Exporter type is set to otlp but endpoint is not set")
    if exporter_protocol == "http/protobuf":
        session = InsecureTLSSession() if tls_insecure else None
        return HTTPSpanExporter(endpoint=exporter_endpoint, certificate_file=tls_ca_bundle, session=session)
    if exporter_protocol == "grpc":
        if tls_ca_bundle:
            # A CA bundle is only meaningful over TLS, so it overrides the plaintext default.
            credentials = ssl_channel_credentials(root_certificates=Path(tls_ca_bundle).read_bytes())
            return GRPCSpanExporter(endpoint=exporter_endpoint, insecure=False, credentials=credentials)
        return GRPCSpanExporter(endpoint=exporter_endpoint, insecure=insecure)
    raise ValueError("Exporter protocol unsupported by Infrahub")


def create_tracer_provider(
    service: str,
    version: str,
    exporter_type: str,
    exporter_endpoint: str | None = None,
    exporter_protocol: str | None = None,
    insecure: bool = True,
    tls_insecure: bool = False,
    tls_ca_bundle: str | None = None,
) -> TracerProvider:
    exporter = create_span_exporter(
        exporter_type=exporter_type,
        insecure=insecure,
        tls_insecure=tls_insecure,
        exporter_endpoint=exporter_endpoint,
        exporter_protocol=exporter_protocol,
        tls_ca_bundle=tls_ca_bundle,
    )

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
    insecure: bool = True,
    tls_insecure: bool = False,
    tls_ca_bundle: str | None = None,
) -> None:
    # Create a trace provider with the exporter
    tracer_provider = create_tracer_provider(
        service=service,
        version=version,
        exporter_type=exporter_type,
        exporter_endpoint=exporter_endpoint,
        exporter_protocol=exporter_protocol,
        insecure=insecure,
        tls_insecure=tls_insecure,
        tls_ca_bundle=tls_ca_bundle,
    )

    # Register the trace provider
    trace.set_tracer_provider(tracer_provider)
