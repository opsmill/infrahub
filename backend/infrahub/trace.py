import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
from grpc import ssl_channel_credentials
from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter as GRPCSpanExporter,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as HTTPSpanExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Event, ReadableSpan, TracerProvider
from opentelemetry.sdk.trace import Span as SDKSpan
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.sampling import ParentBased, Sampler, SamplingResult, TraceIdRatioBased
from opentelemetry.trace import Link, SpanKind, StatusCode
from opentelemetry.trace.span import TraceState
from opentelemetry.util.types import Attributes

from infrahub.masking import MASKING_RULES, MaskingRule, mask_mapping, replace_url_queries_in_text
from infrahub.worker import WORKER_IDENTITY

# Exception events repeat the exception message in their stack trace, so both carry the same URLs.
_EXCEPTION_TEXT_ATTRIBUTES = ("exception.message", "exception.stacktrace")


def get_current_span_with_context() -> trace.Span:
    return trace.get_current_span()


def get_traceid() -> str | None:
    current_span = get_current_span_with_context()
    trace_id = current_span.get_span_context().trace_id
    if trace_id == 0:
        return None
    return format(trace_id, "032x")


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


def _mask_attributes(attributes: Attributes, rules: Sequence[MaskingRule]) -> dict[str, Any]:
    masked = mask_mapping(data=attributes or {}, rules=rules)
    for key in _EXCEPTION_TEXT_ATTRIBUTES:
        value = masked.get(key)
        if isinstance(value, str):
            masked[key] = replace_url_queries_in_text(text=value)
    return masked


def _mask_event(event: Event, rules: Sequence[MaskingRule]) -> Event:
    attributes = _mask_attributes(attributes=event.attributes, rules=rules)
    if attributes == dict(event.attributes or {}):
        return event
    return Event(name=event.name, attributes=attributes, timestamp=event.timestamp)


def mask_span(span: ReadableSpan, rules: Sequence[MaskingRule] = MASKING_RULES) -> ReadableSpan:
    """Return the span with its attributes and the attributes of its events masked by `rules`.

    The span itself is returned when no value changes.
    """
    attributes = _mask_attributes(attributes=span.attributes, rules=rules)
    events = tuple(_mask_event(event=event, rules=rules) for event in span.events)
    if attributes == dict(span.attributes or {}) and all(
        masked is original for masked, original in zip(events, span.events, strict=True)
    ):
        return span
    return ReadableSpan(
        name=span.name,
        context=span.context,
        parent=span.parent,
        resource=span.resource,
        attributes=attributes,
        events=events,
        links=span.links,
        kind=span.kind,
        status=span.status,
        start_time=span.start_time,
        end_time=span.end_time,
        instrumentation_scope=span.instrumentation_scope,
    )


def mask_recording_span_attributes(span: trace.Span, rules: Sequence[MaskingRule] = MASKING_RULES) -> None:
    """Replace, on a span that is still recording, the attribute values that `rules` mask."""
    if not isinstance(span, SDKSpan) or not span.is_recording():
        return
    attributes = dict(span.attributes or {})
    for key, value in mask_mapping(data=attributes, rules=rules).items():
        if value != attributes[key]:
            span.set_attribute(key, value)


class MaskingSpanExporter(SpanExporter):
    """Mask span attributes on export, because the HTTP instrumentation sets them again after the span starts."""

    def __init__(self, exporter: SpanExporter, rules: Sequence[MaskingRule] = MASKING_RULES) -> None:
        self._exporter = exporter
        self._rules = rules

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        return self._exporter.export([mask_span(span=span, rules=self._rules) for span in spans])

    def shutdown(self) -> None:
        self._exporter.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self._exporter.force_flush(timeout_millis=timeout_millis)


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(frozen=True)
class SampleRatioState:
    """Sampling state of one process; `temporary_ratio` and `expires_at` are None when no temporary ratio is in force."""

    default_ratio: float
    ratio_in_force: float
    temporary_ratio: float | None = None
    expires_at: datetime | None = None


@dataclass(frozen=True)
class _TemporaryRatio:
    sampler: TraceIdRatioBased
    expires_at: datetime


class RatioSampler(Sampler):
    """Record a share of new root traces: a temporary ratio until it expires, the default ratio otherwise."""

    def __init__(self, default_ratio: float, clock: Callable[[], datetime] = _utc_now) -> None:
        self._default = TraceIdRatioBased(rate=default_ratio)
        self._temporary: _TemporaryRatio | None = None
        self._clock = clock

    @property
    def ratio(self) -> float:
        """The ratio in force for a new root trace."""
        return self._sampler_in_force().rate

    def set_temporary_ratio(self, ratio: float, expires_at: datetime) -> None:
        """Use `ratio` instead of the default ratio until `expires_at`, replacing any previous temporary ratio.

        Raises:
            ValueError: If `ratio` is not between 0 and 1.

        """
        self._temporary = _TemporaryRatio(sampler=TraceIdRatioBased(rate=ratio), expires_at=expires_at)

    def clear_temporary_ratio(self) -> None:
        self._temporary = None

    def state(self) -> SampleRatioState:
        default_ratio = self._default.rate
        temporary = self._temporary_in_force()
        if temporary is None:
            return SampleRatioState(default_ratio=default_ratio, ratio_in_force=default_ratio)
        return SampleRatioState(
            default_ratio=default_ratio,
            ratio_in_force=temporary.sampler.rate,
            temporary_ratio=temporary.sampler.rate,
            expires_at=temporary.expires_at,
        )

    def should_sample(
        self,
        parent_context: Context | None,
        trace_id: int,
        name: str,
        kind: SpanKind | None = None,
        attributes: Attributes = None,
        links: Sequence[Link] | None = None,
        trace_state: TraceState | None = None,
    ) -> SamplingResult:
        return self._sampler_in_force().should_sample(
            parent_context=parent_context,
            trace_id=trace_id,
            name=name,
            kind=kind,
            attributes=attributes,
            links=links,
            trace_state=trace_state,
        )

    def get_description(self) -> str:
        return f"RatioSampler{{{self.ratio}}}"

    def _sampler_in_force(self) -> TraceIdRatioBased:
        temporary = self._temporary_in_force()
        return temporary.sampler if temporary is not None else self._default

    def _temporary_in_force(self) -> _TemporaryRatio | None:
        # Read once, because a message handler can replace or clear the temporary ratio at any time.
        temporary = self._temporary
        if temporary is not None and self._clock() < temporary.expires_at:
            return temporary
        return None


_process_sampler: RatioSampler | None = None


def set_temporary_sample_ratio(ratio: float, expires_at: datetime) -> None:
    """Use `ratio` for new root traces of this process until `expires_at`; does nothing when tracing is off.

    Raises:
        ValueError: If `ratio` is not between 0 and 1.

    """
    if _process_sampler is not None:
        _process_sampler.set_temporary_ratio(ratio=ratio, expires_at=expires_at)


def clear_temporary_sample_ratio() -> None:
    """Go back to the default ratio for new root traces of this process; does nothing when tracing is off."""
    if _process_sampler is not None:
        _process_sampler.clear_temporary_ratio()


def get_sample_ratio_state() -> SampleRatioState | None:
    """Return the sampling state of this process, or None when tracing is off."""
    if _process_sampler is None:
        return None
    return _process_sampler.state()


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
    sample_ratio: float,
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
    global _process_sampler
    _process_sampler = RatioSampler(default_ratio=sample_ratio)

    span_processor = BatchSpanProcessor(MaskingSpanExporter(exporter))
    tracer_provider = TracerProvider(resource=resource, sampler=ParentBased(root=_process_sampler))
    tracer_provider.add_span_processor(span_processor)

    return tracer_provider


def configure_trace(
    service: str,
    version: str,
    exporter_type: str,
    sample_ratio: float,
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
        sample_ratio=sample_ratio,
        exporter_endpoint=exporter_endpoint,
        exporter_protocol=exporter_protocol,
        insecure=insecure,
        tls_insecure=tls_insecure,
        tls_ca_bundle=tls_ca_bundle,
    )

    # Register the trace provider
    trace.set_tracer_provider(tracer_provider)
