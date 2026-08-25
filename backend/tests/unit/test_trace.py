from __future__ import annotations

import pytest
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as HTTPSpanExporter,
)
from opentelemetry.sdk.trace.export import ConsoleSpanExporter

from infrahub.trace import InsecureTLSSession, create_span_exporter


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
