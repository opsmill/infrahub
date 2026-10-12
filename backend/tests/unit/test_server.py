from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_ON
from opentelemetry.trace import ProxyTracer, SpanKind
from opentelemetry.util._once import Once
from starlette.middleware.errors import ServerErrorMiddleware

from infrahub.server import app

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass
class RequestCase:
    name: str
    path: str
    status_code: int


REQUEST_CASES = [
    RequestCase(name="openapi-route", path="/api/openapi.json", status_code=200),
    RequestCase(name="no-route", path="/api/no-such-route", status_code=404),
]


@pytest.fixture
def span_exporter(monkeypatch: pytest.MonkeyPatch) -> Iterator[InMemorySpanExporter]:
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    exporter = InMemorySpanExporter()
    provider = TracerProvider(sampler=ALWAYS_ON)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(trace, "_TRACER_PROVIDER_SET_ONCE", Once())
    monkeypatch.setattr(trace, "_TRACER_PROVIDER", None)
    trace.set_tracer_provider(provider)

    # The contrib middleware's ProxyTracer binds to the first global provider it uses and keeps it,
    # so build the stack here and reset that binding when the test ends.
    stack = app.build_middleware_stack()
    assert isinstance(stack, ServerErrorMiddleware)
    assert isinstance(stack.app, OpenTelemetryMiddleware)
    assert isinstance(stack.app.tracer, ProxyTracer)
    monkeypatch.setattr(app, "middleware_stack", stack)
    monkeypatch.setattr(stack.app.tracer, "_real_tracer", None)
    monkeypatch.setattr(app.state, "admission_enabled", False, raising=False)

    yield exporter
    provider.shutdown()


def _server_span_scope_names(exporter: InMemorySpanExporter) -> list[str | None]:
    return [
        span.instrumentation_scope.name if span.instrumentation_scope else None
        for span in exporter.get_finished_spans()
        if span.kind == SpanKind.SERVER
    ]


@pytest.mark.parametrize("case", [pytest.param(tc, id=tc.name) for tc in REQUEST_CASES])
def test_one_request_records_one_server_span(span_exporter: InMemorySpanExporter, case: RequestCase) -> None:
    response = TestClient(app).get(case.path)

    assert response.status_code == case.status_code
    assert _server_span_scope_names(span_exporter) == ["opentelemetry.instrumentation.fastapi"]


def test_plain_fastapi_app_records_a_native_server_span(span_exporter: InMemorySpanExporter) -> None:
    """Control: FastAPI's built-in tracing is active in this setup, so the single span above is not a vacuous pass."""
    plain_app = FastAPI()

    @plain_app.get("/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    response = TestClient(plain_app).get("/ping")

    assert response.status_code == 200
    assert _server_span_scope_names(span_exporter) == ["fastapi"]
