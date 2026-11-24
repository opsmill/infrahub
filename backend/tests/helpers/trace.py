"""Helpers for asserting on the spans the code under test records."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_OFF, ALWAYS_ON, Sampler, SamplingResult
from opentelemetry.util._once import Once

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from opentelemetry.context import Context
    from opentelemetry.trace import Link, SpanKind
    from opentelemetry.trace.span import TraceState
    from opentelemetry.util.types import Attributes


class _SwitchableSampler(Sampler):
    def __init__(self) -> None:
        self.enabled = False

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
        sampler = ALWAYS_ON if self.enabled else ALWAYS_OFF
        return sampler.should_sample(
            parent_context=parent_context,
            trace_id=trace_id,
            name=name,
            kind=kind,
            attributes=attributes,
            links=links,
            trace_state=trace_state,
        )

    def get_description(self) -> str:
        return "SwitchableSampler"


_SAMPLER = _SwitchableSampler()
_EXPORTER = InMemorySpanExporter()
_PROVIDER = TracerProvider(sampler=_SAMPLER)
_PROVIDER.add_span_processor(SimpleSpanProcessor(_EXPORTER))


@contextmanager
def recorded_spans() -> Iterator[InMemorySpanExporter]:
    """Record every span started through the global tracer provider in memory, then restore the previous provider.

    Every block shares one test provider, because a tracer keeps the first provider it resolves for the rest of
    the process; its sampler drops every span outside a block.
    """
    _EXPORTER.clear()

    # The OpenTelemetry API lets a process set the global tracer provider only once.
    previous_provider = trace._TRACER_PROVIDER
    previous_set_once = trace._TRACER_PROVIDER_SET_ONCE
    trace._TRACER_PROVIDER_SET_ONCE = Once()
    trace._TRACER_PROVIDER = None
    trace.set_tracer_provider(_PROVIDER)
    _SAMPLER.enabled = True
    try:
        yield _EXPORTER
    finally:
        _SAMPLER.enabled = False
        trace._TRACER_PROVIDER = previous_provider
        trace._TRACER_PROVIDER_SET_ONCE = previous_set_once
