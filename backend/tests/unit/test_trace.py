from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter as GRPCSpanExporter,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as HTTPSpanExporter,
)
from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import Decision
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags, set_span_in_context, use_span

from infrahub.trace import (
    InsecureTLSSession,
    MaskingSpanExporter,
    RatioSampler,
    create_span_exporter,
    create_tracer_provider,
    get_traceid,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from opentelemetry.context import Context
    from opentelemetry.sdk.trace.sampling import Sampler
    from opentelemetry.util.types import AttributeValue


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


@dataclass
class SpanAttributeMaskingTestCase:
    name: str
    key: str
    value: AttributeValue
    expected: AttributeValue


SPAN_ATTRIBUTE_MASKING_TEST_CASES: list[SpanAttributeMaskingTestCase] = [
    SpanAttributeMaskingTestCase(
        name="client_ip_old_convention", key="net.peer.ip", value="203.0.113.7", expected="[MASKED]"
    ),
    SpanAttributeMaskingTestCase(
        name="client_ip_new_convention", key="client.address", value="203.0.113.7", expected="[MASKED]"
    ),
    SpanAttributeMaskingTestCase(
        name="full_url_keeps_scheme_host_and_path",
        key="http.url",
        value="https://infrahub.example.com/api/oidc/google/token?code=abc&state=xyz",
        expected="https://infrahub.example.com/api/oidc/google/token?[MASKED]",
    ),
    SpanAttributeMaskingTestCase(
        name="target_keeps_path",
        key="http.target",
        value="/api/oidc/google/token?code=abc&state=xyz",
        expected="/api/oidc/google/token?[MASKED]",
    ),
    SpanAttributeMaskingTestCase(
        name="new_convention_full_url_keeps_path",
        key="url.full",
        value="https://infrahub.example.com/api/oauth2/google/token?code=abc&state=xyz",
        expected="https://infrahub.example.com/api/oauth2/google/token?[MASKED]",
    ),
    SpanAttributeMaskingTestCase(
        name="new_convention_query_is_masked", key="url.query", value="code=abc&state=xyz", expected="[MASKED]"
    ),
    SpanAttributeMaskingTestCase(
        name="url_without_query_string_is_unchanged",
        key="http.url",
        value="https://infrahub.example.com/api/schema",
        expected="https://infrahub.example.com/api/schema",
    ),
    SpanAttributeMaskingTestCase(
        name="cypher_text_is_kept",
        key="query",
        value="MATCH (n:Node {uuid: $node_id}) RETURN n",
        expected="MATCH (n:Node {uuid: $node_id}) RETURN n",
    ),
    SpanAttributeMaskingTestCase(
        name="query_name_is_kept", key="query_name", value="NodeGetListQuery", expected="NodeGetListQuery"
    ),
    SpanAttributeMaskingTestCase(name="access_token", key="sso.access_token", value="eyJhbGciOi", expected="[MASKED]"),
    SpanAttributeMaskingTestCase(name="token_key_in_upper_case", key="API_TOKEN", value="abc123", expected="[MASKED]"),
    SpanAttributeMaskingTestCase(name="password", key="ldap.password", value="hunter2", expected="[MASKED]"),
    SpanAttributeMaskingTestCase(name="secret", key="client_secret", value="s3cr3t", expected="[MASKED]"),
    SpanAttributeMaskingTestCase(
        name="email_address", key="user.email", value="grace@example.com", expected="[MASKED]"
    ),
    SpanAttributeMaskingTestCase(name="user_name_with_underscore", key="user_name", value="Grace", expected="[MASKED]"),
    SpanAttributeMaskingTestCase(
        name="user_name_in_one_word", key="enduser.username", value="grace", expected="[MASKED]"
    ),
    SpanAttributeMaskingTestCase(name="non_string_value_is_masked", key="token_count", value=3, expected="[MASKED]"),
    SpanAttributeMaskingTestCase(
        name="graphql_query_is_kept", key="query", value="query { Tag }", expected="query { Tag }"
    ),
    SpanAttributeMaskingTestCase(name="operation_is_kept", key="operation", value="TagList", expected="TagList"),
    SpanAttributeMaskingTestCase(name="branch_is_kept", key="branch", value="main", expected="main"),
    SpanAttributeMaskingTestCase(name="sso_group_count_is_kept", key="sso_group_count", value=2, expected=2),
    SpanAttributeMaskingTestCase(
        name="url_path_naming_a_token_is_kept",
        key="http.url",
        value="https://infrahub.example.com/api/oidc/google/token",
        expected="https://infrahub.example.com/api/oidc/google/token",
    ),
]


class TestSpanAttributeMasking:
    @pytest.fixture
    def exported(self) -> InMemorySpanExporter:
        return InMemorySpanExporter()

    @pytest.fixture
    def tracer_provider(self, exported: InMemorySpanExporter) -> TracerProvider:
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(MaskingSpanExporter(exported)))
        return provider

    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in SPAN_ATTRIBUTE_MASKING_TEST_CASES])
    def test_exported_attribute(
        self,
        test_case: SpanAttributeMaskingTestCase,
        tracer_provider: TracerProvider,
        exported: InMemorySpanExporter,
    ) -> None:
        with tracer_provider.get_tracer(__name__).start_as_current_span("request") as span:
            span.set_attribute(test_case.key, test_case.value)

        (finished,) = exported.get_finished_spans()
        assert finished.attributes is not None
        assert finished.attributes[test_case.key] == test_case.expected

    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in SPAN_ATTRIBUTE_MASKING_TEST_CASES])
    def test_exported_event_attribute(
        self,
        test_case: SpanAttributeMaskingTestCase,
        tracer_provider: TracerProvider,
        exported: InMemorySpanExporter,
    ) -> None:
        with tracer_provider.get_tracer(__name__).start_as_current_span("request") as span:
            span.add_event("step", {test_case.key: test_case.value})

        (finished,) = exported.get_finished_spans()
        (event,) = finished.events
        assert event.name == "step"
        assert event.attributes is not None
        assert event.attributes[test_case.key] == test_case.expected

    def test_span_identity_is_kept(self, tracer_provider: TracerProvider, exported: InMemorySpanExporter) -> None:
        with tracer_provider.get_tracer(__name__).start_as_current_span("request") as span:
            span.set_attribute("net.peer.ip", "203.0.113.7")
            context = span.get_span_context()

        (finished,) = exported.get_finished_spans()
        assert finished.name == "request"
        assert finished.context == context

    def test_exception_message_keeps_the_url_path_and_masks_its_query_string(
        self, tracer_provider: TracerProvider, exported: InMemorySpanExporter
    ) -> None:
        error = RuntimeError(
            "Client error '400 Bad Request' for url 'https://idp.example.com/token?code=abc&state=xyz'"
        )
        with tracer_provider.get_tracer(__name__).start_as_current_span("request") as span:
            span.record_exception(error)

        (finished,) = exported.get_finished_spans()
        (event,) = finished.events
        assert event.name == "exception"
        assert event.attributes is not None
        assert event.attributes["exception.type"] == "RuntimeError"
        assert (
            event.attributes["exception.message"]
            == "Client error '400 Bad Request' for url 'https://idp.example.com/token?[MASKED]'"
        )
        exported_values = [str(value) for value in event.attributes.values()]
        assert not any("code=abc" in value or "state=xyz" in value for value in exported_values)

    def test_request_attributes_from_the_asgi_instrumentation_are_masked(
        self, tracer_provider: TracerProvider, exported: InMemorySpanExporter
    ) -> None:
        app = FastAPI()

        @app.get("/api/oidc/{provider_name}/token")
        async def sso_token(provider_name: str) -> dict[str, str]:
            return {"provider": provider_name}

        instrumented = OpenTelemetryMiddleware(app, tracer_provider=tracer_provider)
        with TestClient(instrumented) as client:
            response = client.get("/api/oidc/google/token?code=abc&state=xyz")
        assert response.status_code == 200

        server_spans = [
            span for span in exported.get_finished_spans() if span.attributes and "http.url" in span.attributes
        ]
        assert len(server_spans) == 1
        attributes = server_spans[0].attributes
        assert attributes is not None
        assert attributes["http.url"] == "http://testserver/api/oidc/google/token?[MASKED]"
        assert attributes["net.peer.ip"] == "[MASKED]"
        exported_values = [
            str(value) for span in exported.get_finished_spans() for value in (span.attributes or {}).values()
        ]
        assert not any("code=abc" in value or "state=xyz" in value for value in exported_values)


def test_tracer_provider_masks_spans_before_the_exporter() -> None:
    provider = create_tracer_provider(service="infrahub-test", version="1.0", exporter_type="console", sample_ratio=1.0)
    try:
        (span_processor,) = provider._active_span_processor._span_processors
        assert isinstance(span_processor, BatchSpanProcessor)
        assert isinstance(span_processor.span_exporter, MaskingSpanExporter)
    finally:
        provider.shutdown()


RATIO = 0.5
RATIO_LIMIT = int(RATIO * 2**64)
TRACE_ID_BELOW_LIMIT = (0xABCDEF << 64) | (RATIO_LIMIT - 1)
TRACE_ID_AT_LIMIT = (0xABCDEF << 64) | RATIO_LIMIT


def _decision(sampler: Sampler, trace_id: int, parent_context: Context | None = None) -> Decision:
    return sampler.should_sample(parent_context=parent_context, trace_id=trace_id, name="request").decision


def _parent_context(sampled: bool) -> Context:
    flags = TraceFlags(TraceFlags.SAMPLED if sampled else TraceFlags.DEFAULT)
    parent = SpanContext(trace_id=TRACE_ID_AT_LIMIT, span_id=1, is_remote=True, trace_flags=flags)
    return set_span_in_context(NonRecordingSpan(parent))


class TestRatioSampler:
    def test_records_trace_ids_below_the_ratio_limit_only(self) -> None:
        sampler = RatioSampler(default_ratio=RATIO)

        assert _decision(sampler=sampler, trace_id=TRACE_ID_BELOW_LIMIT) is Decision.RECORD_AND_SAMPLE
        assert _decision(sampler=sampler, trace_id=TRACE_ID_AT_LIMIT) is Decision.DROP

    def test_new_sampler_uses_the_default_ratio(self) -> None:
        assert RatioSampler(default_ratio=RATIO).ratio == RATIO


class TestTracerProviderSampler:
    @pytest.fixture
    def provider_sampler(self) -> Iterator[Callable[[float], Sampler]]:
        """Build tracer providers the way the server and the task worker do, and shut them down after."""
        providers: list[TracerProvider] = []

        def build(sample_ratio: float) -> Sampler:
            provider = create_tracer_provider(
                service="infrahub-test", version="1.0", exporter_type="console", sample_ratio=sample_ratio
            )
            providers.append(provider)
            return provider.sampler

        yield build
        for provider in providers:
            provider.shutdown()

    def test_sampled_parent_is_always_followed(self, provider_sampler: Callable[[float], Sampler]) -> None:
        sampler = provider_sampler(0.0)

        decision = _decision(sampler=sampler, trace_id=TRACE_ID_AT_LIMIT, parent_context=_parent_context(sampled=True))

        assert decision is Decision.RECORD_AND_SAMPLE

    def test_unsampled_parent_is_never_recorded(self, provider_sampler: Callable[[float], Sampler]) -> None:
        sampler = provider_sampler(1.0)

        decision = _decision(
            sampler=sampler, trace_id=TRACE_ID_BELOW_LIMIT, parent_context=_parent_context(sampled=False)
        )

        assert decision is Decision.DROP

    def test_root_trace_uses_the_configured_ratio(self, provider_sampler: Callable[[float], Sampler]) -> None:
        sampler = provider_sampler(RATIO)

        assert _decision(sampler=sampler, trace_id=TRACE_ID_BELOW_LIMIT) is Decision.RECORD_AND_SAMPLE
        assert _decision(sampler=sampler, trace_id=TRACE_ID_AT_LIMIT) is Decision.DROP


@dataclass
class TraceIdFormatTestCase:
    name: str
    trace_id: int
    expected: str


TRACE_ID_FORMAT_TEST_CASES: list[TraceIdFormatTestCase] = [
    TraceIdFormatTestCase(
        name="leading_zero_is_kept",
        trace_id=0x0AF7651916CD43DD8448EB211C80319C,
        expected="0af7651916cd43dd8448eb211c80319c",
    ),
    TraceIdFormatTestCase(
        name="small_trace_id_is_padded_to_32_characters",
        trace_id=0x1,
        expected="00000000000000000000000000000001",
    ),
    TraceIdFormatTestCase(
        name="largest_trace_id",
        trace_id=2**128 - 1,
        expected="ffffffffffffffffffffffffffffffff",
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in TRACE_ID_FORMAT_TEST_CASES])
def test_trace_id_is_32_lowercase_hexadecimal_characters(test_case: TraceIdFormatTestCase) -> None:
    span = NonRecordingSpan(SpanContext(trace_id=test_case.trace_id, span_id=1, is_remote=False))

    with use_span(span):
        assert get_traceid() == test_case.expected


def test_no_trace_id_outside_a_span() -> None:
    assert get_traceid() is None
