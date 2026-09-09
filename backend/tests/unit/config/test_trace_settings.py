from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from infrahub.config import TraceExporterType, TraceSettings, TraceTransportProtocol

# Any PEM that loads as a trust store; this one is expired, which only matters when verifying.
LOADABLE_CA_BUNDLE = str(Path(__file__).parent.parent.parent / "helpers" / "expired_self_signed_cert.pem")


class TestTraceSettings:
    def test_defaults(self) -> None:
        settings = TraceSettings()
        assert settings.enable is False
        assert settings.insecure is True
        assert settings.tls_insecure is False
        assert settings.tls_ca_bundle is None
        assert settings.exporter_protocol is TraceTransportProtocol.GRPC

    def test_tls_insecure_with_grpc_is_rejected(self) -> None:
        expected = (
            "trace.tls_insecure is not supported with the grpc exporter protocol, because the gRPC client "
            "cannot skip certificate validation. Set trace.tls_ca_bundle to the collector's CA instead, "
            "or use the http/protobuf protocol."
        )
        with pytest.raises(ValidationError, match=re.escape(expected)):
            TraceSettings(tls_insecure=True, exporter_protocol=TraceTransportProtocol.GRPC)

    def test_tls_insecure_with_http_protobuf_is_accepted(self) -> None:
        settings = TraceSettings(tls_insecure=True, exporter_protocol=TraceTransportProtocol.HTTP_PROTOBUF)
        assert settings.tls_insecure is True
        assert settings.tls_ca_bundle is None

    def test_tls_insecure_with_ca_bundle_is_rejected(self) -> None:
        expected = "trace.tls_insecure cannot be combined with trace.tls_ca_bundle; pick one."
        with pytest.raises(ValidationError, match=re.escape(expected)):
            TraceSettings(
                tls_insecure=True,
                tls_ca_bundle=LOADABLE_CA_BUNDLE,
                exporter_protocol=TraceTransportProtocol.HTTP_PROTOBUF,
            )

    def test_ca_bundle_is_accepted_for_grpc(self) -> None:
        settings = TraceSettings(tls_ca_bundle=LOADABLE_CA_BUNDLE, exporter_protocol=TraceTransportProtocol.GRPC)
        assert settings.tls_ca_bundle == LOADABLE_CA_BUNDLE

    def test_missing_ca_bundle_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"Unable to load trace CA bundle from /does/not/exist/ca\.pem"):
            TraceSettings(tls_ca_bundle="/does/not/exist/ca.pem")

    def test_malformed_ca_bundle_is_rejected(self, tmp_path: Path) -> None:
        bundle = tmp_path / "broken.pem"
        bundle.write_text("-----BEGIN CERTIFICATE-----\nnot a real certificate\n-----END CERTIFICATE-----\n")
        with pytest.raises(ValidationError, match=rf"Unable to load trace CA bundle from {re.escape(str(bundle))}"):
            TraceSettings(tls_ca_bundle=str(bundle))

    def test_ca_bundle_with_plaintext_http_endpoint_is_rejected(self) -> None:
        expected = "trace.tls_ca_bundle cannot be combined with a trace.exporter_endpoint that is not https://"
        with pytest.raises(ValidationError, match=re.escape(expected)):
            TraceSettings(
                tls_ca_bundle=LOADABLE_CA_BUNDLE,
                exporter_type=TraceExporterType.OTLP,
                exporter_protocol=TraceTransportProtocol.HTTP_PROTOBUF,
                exporter_endpoint="http://collector.example.com:4318/v1/traces",
            )

    def test_tls_insecure_with_plaintext_http_endpoint_is_rejected(self) -> None:
        expected = "trace.tls_insecure cannot be combined with a trace.exporter_endpoint that is not https://"
        with pytest.raises(ValidationError, match=re.escape(expected)):
            TraceSettings(
                tls_insecure=True,
                exporter_type=TraceExporterType.OTLP,
                exporter_protocol=TraceTransportProtocol.HTTP_PROTOBUF,
                exporter_endpoint="http://collector.example.com:4318/v1/traces",
            )

    def test_ca_bundle_with_https_endpoint_is_accepted(self) -> None:
        settings = TraceSettings(
            tls_ca_bundle=LOADABLE_CA_BUNDLE,
            exporter_type=TraceExporterType.OTLP,
            exporter_protocol=TraceTransportProtocol.HTTP_PROTOBUF,
            exporter_endpoint="https://collector.example.com:4318/v1/traces",
        )
        assert settings.tls_ca_bundle == LOADABLE_CA_BUNDLE

    def test_ca_bundle_with_scheme_less_grpc_endpoint_is_accepted(self) -> None:
        # grpc endpoints carry no scheme; the bundle itself selects TLS there.
        settings = TraceSettings(
            tls_ca_bundle=LOADABLE_CA_BUNDLE,
            exporter_type=TraceExporterType.OTLP,
            exporter_protocol=TraceTransportProtocol.GRPC,
            exporter_endpoint="collector.example.com:4317",
        )
        assert settings.tls_ca_bundle == LOADABLE_CA_BUNDLE
