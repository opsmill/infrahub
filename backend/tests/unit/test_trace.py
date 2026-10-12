from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter as GRPCSpanExporter,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as HTTPSpanExporter,
)
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_ON, Decision, ParentBased
from opentelemetry.trace import SpanKind

from infrahub.trace import (
    ExcludeServerPathsSampler,
    InsecureTLSSession,
    create_span_exporter,
    create_tracer_provider,
)


class TestExcludeServerPathsSampler:
    def test_drops_server_span_for_excluded_path(self) -> None:
        sampler = ExcludeServerPathsSampler(delegate=ALWAYS_ON, paths=frozenset({"/health"}))
        result = sampler.should_sample(
            parent_context=None, trace_id=1, name="GET", kind=SpanKind.SERVER, attributes={"url.path": "/health"}
        )
        assert result.decision == Decision.DROP

    def test_delegates_server_span_for_other_path(self) -> None:
        sampler = ExcludeServerPathsSampler(delegate=ALWAYS_ON, paths=frozenset({"/health"}))
        result = sampler.should_sample(
            parent_context=None, trace_id=1, name="GET", kind=SpanKind.SERVER, attributes={"url.path": "/api/schema"}
        )
        assert result.decision == Decision.RECORD_AND_SAMPLE

    def test_delegates_non_server_span_on_excluded_path(self) -> None:
        sampler = ExcludeServerPathsSampler(delegate=ALWAYS_ON, paths=frozenset({"/health"}))
        result = sampler.should_sample(
            parent_context=None, trace_id=1, name="GET", kind=SpanKind.CLIENT, attributes={"url.path": "/health"}
        )
        assert result.decision == Decision.RECORD_AND_SAMPLE

    def test_drops_every_span_of_an_excluded_fastapi_request(self) -> None:
        exporter = InMemorySpanExporter()
        provider = TracerProvider(
            sampler=ExcludeServerPathsSampler(delegate=ParentBased(root=ALWAYS_ON), paths=frozenset({"/health"}))
        )
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        app = FastAPI(telemetry={"tracer_provider": provider})

        @app.get("/health")
        def health() -> dict[str, str]:
            return {"message": "OK"}

        @app.get("/ping")
        def ping() -> dict[str, str]:
            return {"message": "OK"}

        client = TestClient(app)
        assert client.get("/health").status_code == 200
        assert exporter.get_finished_spans() == ()

        assert client.get("/ping").status_code == 200
        assert [span.name for span in exporter.get_finished_spans() if span.kind == SpanKind.SERVER] == ["GET /ping"]
        provider.shutdown()


class TestCreateTracerProvider:
    def test_excluded_paths_wrap_the_sampler_from_the_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OTEL_TRACES_SAMPLER", "always_off")
        provider = create_tracer_provider(
            service="infrahub-task-worker",
            version="1.0.0",
            exporter_type="console",
            excluded_server_paths=frozenset({"/health"}),
        )
        assert provider.sampler.get_description() == "ExcludeServerPathsSampler{/health}/AlwaysOffSampler"
        provider.shutdown()

    def test_no_excluded_paths_keeps_the_sampler_from_the_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OTEL_TRACES_SAMPLER", "always_off")
        provider = create_tracer_provider(service="infrahub-server", version="1.0.0", exporter_type="console")
        assert provider.sampler.get_description() == "AlwaysOffSampler"
        provider.shutdown()


class TestInsecureTLSSession:
    def test_overrides_request_level_verify(self) -> None:
        session = InsecureTLSSession()
        settings = session.merge_environment_settings(
            url="https://collector:4318/v1/traces", proxies={}, stream=None, verify=True, cert=None
        )
        assert settings["verify"] is False

    def test_overrides_session_level_verify(self) -> None:
        session = InsecureTLSSession()
        session.verify = "/etc/ssl/certs/collector.pem"
        settings = session.merge_environment_settings(
            url="https://collector:4318/v1/traces", proxies={}, stream=None, verify=None, cert=None
        )
        assert settings["verify"] is False


class TestCreateSpanExporter:
    def test_console(self) -> None:
        exporter = create_span_exporter(exporter_type="console", insecure=True, tls_insecure=False)
        assert isinstance(exporter, ConsoleSpanExporter)

    def test_unsupported_type_is_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"^Exporter type unsupported by Infrahub$"):
            create_span_exporter(exporter_type="jaeger", insecure=True, tls_insecure=False)

    def test_otlp_without_endpoint_is_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"^Exporter type is set to otlp but endpoint is not set$"):
            create_span_exporter(exporter_type="otlp", insecure=True, tls_insecure=False)

    def test_otlp_with_unsupported_protocol_is_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"^Exporter protocol unsupported by Infrahub$"):
            create_span_exporter(
                exporter_type="otlp",
                insecure=True,
                tls_insecure=False,
                exporter_endpoint="collector:4317",
                exporter_protocol="http/json",
            )

    def test_http_with_tls_insecure_skips_certificate_verification(self) -> None:
        exporter = create_span_exporter(
            exporter_type="otlp",
            insecure=True,
            tls_insecure=True,
            exporter_endpoint="https://collector:4318/v1/traces",
            exporter_protocol="http/protobuf",
        )
        assert isinstance(exporter, HTTPSpanExporter)
        assert isinstance(exporter._session, InsecureTLSSession)
        exporter.shutdown()

    def test_http_verifies_certificates_by_default(self) -> None:
        exporter = create_span_exporter(
            exporter_type="otlp",
            insecure=True,
            tls_insecure=False,
            exporter_endpoint="https://collector:4318/v1/traces",
            exporter_protocol="http/protobuf",
        )
        assert isinstance(exporter, HTTPSpanExporter)
        assert not isinstance(exporter._session, InsecureTLSSession)
        exporter.shutdown()

    def test_grpc_insecure_enables_plaintext(self) -> None:
        exporter = create_span_exporter(
            exporter_type="otlp",
            insecure=True,
            tls_insecure=False,
            exporter_endpoint="collector:4317",
            exporter_protocol="grpc",
        )
        assert isinstance(exporter, GRPCSpanExporter)
        assert exporter._insecure is True
        exporter.shutdown()

    def test_grpc_secure_uses_tls(self) -> None:
        exporter = create_span_exporter(
            exporter_type="otlp",
            insecure=False,
            tls_insecure=False,
            exporter_endpoint="collector:4317",
            exporter_protocol="grpc",
        )
        assert isinstance(exporter, GRPCSpanExporter)
        assert exporter._insecure is False
        exporter.shutdown()
