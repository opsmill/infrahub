from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest
from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind

from infrahub.server import server_request_hook

if TYPE_CHECKING:
    from collections.abc import Iterator

CLIENT_IP = "192.0.2.10"
SECRETS = ("SECRETCODE", "SECRETSTATE")


@pytest.fixture
def exporter() -> InMemorySpanExporter:
    return InMemorySpanExporter()


@pytest.fixture
def instrumented_app(exporter: InMemorySpanExporter) -> Iterator[FastAPI]:
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
    app = FastAPI()

    @app.get("/api/oidc/{provider_name}/token")
    async def token(provider_name: str) -> dict[str, str]:
        return {"provider_name": provider_name}

    FastAPIInstrumentor().instrument_app(app, server_request_hook=server_request_hook, tracer_provider=tracer_provider)
    try:
        yield app
    finally:
        FastAPIInstrumentor().uninstrument_app(app)


async def test_request_span_holds_no_query_string_or_client_address(
    instrumented_app: FastAPI, exporter: InMemorySpanExporter
) -> None:
    transport = httpx.ASGITransport(app=instrumented_app, client=(CLIENT_IP, 50000))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/oidc/p1/token?code=SECRETCODE&state=SECRETSTATE")
    assert response.status_code == 200

    spans = exporter.get_finished_spans()
    (server_span,) = [span for span in spans if span.kind == SpanKind.SERVER]
    attributes = dict(server_span.attributes or {})
    assert attributes["http.url"] == "http://testserver/api/oidc/p1/token?[MASKED]"
    assert attributes["net.peer.ip"] == "[MASKED]"

    recorded_values = [str(value) for span in spans for value in (span.attributes or {}).values()]
    assert [value for value in recorded_values if any(secret in value for secret in (*SECRETS, CLIENT_IP))] == []
