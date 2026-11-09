from __future__ import annotations

import pytest
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter as GRPCSpanExporter,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as HTTPSpanExporter,
)
from opentelemetry.sdk.trace.export import ConsoleSpanExporter

from infrahub.trace import TraceTLSSession, create_span_exporter


@pytest.mark.parametrize("verify", [False, "/etc/ssl/certs/collector.pem"])
class TestTraceTLSSession:
    def test_overrides_request_level_verify(self, verify: bool | str) -> None:
        session = TraceTLSSession(verify=verify)
        settings = session.merge_environment_settings(
            url="https://collector:4318/v1/traces", proxies={}, stream=None, verify=True, cert=None
        )
        assert settings["verify"] == verify

    def test_overrides_session_level_verify(self, verify: bool | str) -> None:
        session = TraceTLSSession(verify=verify)
        session.verify = True
        settings = session.merge_environment_settings(
            url="https://collector:4318/v1/traces", proxies={}, stream=None, verify=None, cert=None
        )
        assert settings["verify"] == verify


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

    @pytest.mark.parametrize("tls_insecure", [False, True])
    def test_http(self, tls_insecure: bool) -> None:
        exporter = create_span_exporter(
            exporter_type="otlp",
            insecure=True,
            tls_insecure=tls_insecure,
            exporter_endpoint="https://collector:4318/v1/traces",
            exporter_protocol="http/protobuf",
        )
        assert isinstance(exporter, HTTPSpanExporter)
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
