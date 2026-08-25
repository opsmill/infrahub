"""TLS behavior of the OTLP span exporters, exercised against real local collectors.

These tests complete a real TLS handshake because the settings under test only take effect
there: an exporter can be constructed with the right arguments and still fail to deliver a
span. Everything runs in-process over loopback with certificates generated per session.
"""

from __future__ import annotations

import datetime
import ssl
import threading
from concurrent import futures
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING, Any

import grpc
import pytest
import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2, trace_service_pb2_grpc
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from infrahub.trace import create_span_exporter

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path


@dataclass(frozen=True)
class LocalPKI:
    ca_bundle: Path
    """Path to the PEM-encoded private CA certificate."""

    server_certificate: bytes
    """PEM-encoded server certificate issued by the private CA."""

    server_key: bytes
    """PEM-encoded private key for the server certificate."""


def _build_pki(directory: Path) -> LocalPKI:
    now = datetime.datetime.now(datetime.UTC)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Infrahub Test Private CA")])
    ca_certificate = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(hours=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        # OpenSSL rejects a trust anchor without keyCertSign, while gRPC's BoringSSL accepts it.
        .add_extension(
            x509.KeyUsage(
                digital_signature=False,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256())
    )

    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    server_certificate = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
        .issuer_name(ca_name)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(hours=1))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        # OpenSSL will not chain a leaf to its issuer without this extension.
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256())
    )

    ca_bundle = directory / "ca.pem"
    ca_bundle.write_bytes(ca_certificate.public_bytes(serialization.Encoding.PEM))
    return LocalPKI(
        ca_bundle=ca_bundle,
        server_certificate=server_certificate.public_bytes(serialization.Encoding.PEM),
        server_key=server_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ),
    )


@pytest.fixture(scope="module")
def pki(tmp_path_factory: pytest.TempPathFactory) -> LocalPKI:
    return _build_pki(tmp_path_factory.mktemp("trace-pki"))


class _GRPCTraceService(trace_service_pb2_grpc.TraceServiceServicer):
    def __init__(self) -> None:
        self.exported: list[int] = []

    def Export(self, request: Any, context: Any) -> Any:  # noqa: N802
        self.exported.append(len(request.resource_spans))
        return trace_service_pb2.ExportTraceServiceResponse()


@dataclass(frozen=True)
class RunningCollector:
    endpoint: str
    """Endpoint the exporter should be pointed at."""

    exported: list[int]
    """One entry per export request the collector accepted."""


def _serve_grpc(credentials: grpc.ServerCredentials | None) -> Iterator[RunningCollector]:
    """Run a gRPC trace collector, over TLS when credentials are given and in plaintext otherwise."""
    servicer = _GRPCTraceService()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    trace_service_pb2_grpc.add_TraceServiceServicer_to_server(servicer, server)
    port = (
        server.add_insecure_port("127.0.0.1:0")
        if credentials is None
        else server.add_secure_port("127.0.0.1:0", credentials)
    )
    server.start()
    try:
        yield RunningCollector(endpoint=f"localhost:{port}", exported=servicer.exported)
    finally:
        server.stop(grace=None)


@pytest.fixture
def grpc_collector(pki: LocalPKI) -> Iterator[RunningCollector]:
    yield from _serve_grpc(grpc.ssl_server_credentials([(pki.server_key, pki.server_certificate)]))


@pytest.fixture
def plaintext_grpc_collector() -> Iterator[RunningCollector]:
    yield from _serve_grpc(credentials=None)


@pytest.fixture
def http_collector(pki: LocalPKI) -> Iterator[RunningCollector]:
    exported: list[int] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            exported.append(1)
            self.send_response(200)
            self.send_header("Content-Type", "application/x-protobuf")
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:
            """Keep the collector quiet; the default handler writes to stderr."""

    certificate_file = pki.ca_bundle.parent / "server.pem"
    certificate_file.write_bytes(pki.server_certificate)
    key_file = pki.ca_bundle.parent / "server.key"
    key_file.write_bytes(pki.server_key)

    server = HTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=str(certificate_file), keyfile=str(key_file))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield RunningCollector(endpoint=f"https://localhost:{server.server_address[1]}/v1/traces", exported=exported)
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture(scope="module")
def span() -> ReadableSpan:
    provider = TracerProvider(resource=Resource(attributes={"service.name": "test"}))
    with provider.get_tracer("test").start_as_current_span("probe") as started_span:
        pass
    assert isinstance(started_span, ReadableSpan)
    return started_span


@pytest.fixture
def make_exporter() -> Iterator[Callable[..., SpanExporter]]:
    """Build span exporters and shut each one down once the test ends."""
    built: list[SpanExporter] = []

    def factory(**kwargs: Any) -> SpanExporter:
        exporter = create_span_exporter(**kwargs)
        built.append(exporter)
        return exporter

    yield factory
    for exporter in built:
        exporter.shutdown()


class TestGRPCExporterTLS:
    def test_insecure_delivers_to_plaintext_collector(
        self,
        plaintext_grpc_collector: RunningCollector,
        span: ReadableSpan,
        make_exporter: Callable[..., SpanExporter],
    ) -> None:
        exporter = make_exporter(
            exporter_type="otlp",
            exporter_protocol="grpc",
            exporter_endpoint=plaintext_grpc_collector.endpoint,
            insecure=True,
            tls_insecure=False,
        )
        result = exporter.export([span])

        assert result is SpanExportResult.SUCCESS
        assert plaintext_grpc_collector.exported == [1]

    def test_without_insecure_the_plaintext_collector_is_unreachable(
        self,
        plaintext_grpc_collector: RunningCollector,
        span: ReadableSpan,
        monkeypatch: pytest.MonkeyPatch,
        make_exporter: Callable[..., SpanExporter],
    ) -> None:
        # Cap the export deadline so the failure path does not sit in gRPC's retry backoff.
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_TIMEOUT", "1")
        exporter = make_exporter(
            exporter_type="otlp",
            exporter_protocol="grpc",
            exporter_endpoint=plaintext_grpc_collector.endpoint,
            insecure=False,
            tls_insecure=False,
        )
        result = exporter.export([span])

        assert result is SpanExportResult.FAILURE
        assert plaintext_grpc_collector.exported == []

    def test_ca_bundle_delivers_to_collector_with_private_certificate(
        self,
        grpc_collector: RunningCollector,
        pki: LocalPKI,
        span: ReadableSpan,
        make_exporter: Callable[..., SpanExporter],
    ) -> None:
        exporter = make_exporter(
            exporter_type="otlp",
            exporter_protocol="grpc",
            exporter_endpoint=grpc_collector.endpoint,
            insecure=True,
            tls_insecure=False,
            tls_ca_bundle=str(pki.ca_bundle),
        )
        result = exporter.export([span])

        assert result is SpanExportResult.SUCCESS
        assert grpc_collector.exported == [1]

    def test_without_ca_bundle_the_private_certificate_is_rejected(
        self,
        grpc_collector: RunningCollector,
        span: ReadableSpan,
        monkeypatch: pytest.MonkeyPatch,
        make_exporter: Callable[..., SpanExporter],
    ) -> None:
        # Cap the export deadline so the failure path does not sit in gRPC's retry backoff.
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_TIMEOUT", "1")
        exporter = make_exporter(
            exporter_type="otlp",
            exporter_protocol="grpc",
            exporter_endpoint=grpc_collector.endpoint,
            insecure=False,
            tls_insecure=False,
        )
        result = exporter.export([span])

        assert result is SpanExportResult.FAILURE
        assert grpc_collector.exported == []


class TestHTTPExporterTLS:
    def test_ca_bundle_delivers_to_collector_with_private_certificate(
        self,
        http_collector: RunningCollector,
        pki: LocalPKI,
        span: ReadableSpan,
        make_exporter: Callable[..., SpanExporter],
    ) -> None:
        exporter = make_exporter(
            exporter_type="otlp",
            exporter_protocol="http/protobuf",
            exporter_endpoint=http_collector.endpoint,
            insecure=True,
            tls_insecure=False,
            tls_ca_bundle=str(pki.ca_bundle),
        )
        result = exporter.export([span])

        assert result is SpanExportResult.SUCCESS
        assert http_collector.exported == [1]

    def test_tls_insecure_delivers_without_validating_the_certificate(
        self, http_collector: RunningCollector, span: ReadableSpan, make_exporter: Callable[..., SpanExporter]
    ) -> None:
        exporter = make_exporter(
            exporter_type="otlp",
            exporter_protocol="http/protobuf",
            exporter_endpoint=http_collector.endpoint,
            insecure=True,
            tls_insecure=True,
        )
        result = exporter.export([span])

        assert result is SpanExportResult.SUCCESS
        assert http_collector.exported == [1]

    def test_without_ca_bundle_the_private_certificate_is_rejected(
        self,
        http_collector: RunningCollector,
        span: ReadableSpan,
        monkeypatch: pytest.MonkeyPatch,
        make_exporter: Callable[..., SpanExporter],
    ) -> None:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_TIMEOUT", "1")
        exporter = make_exporter(
            exporter_type="otlp",
            exporter_protocol="http/protobuf",
            exporter_endpoint=http_collector.endpoint,
            insecure=True,
            tls_insecure=False,
        )
        # This exporter version lets the verification failure escape export() instead of reporting
        # it as SpanExportResult.FAILURE; BatchSpanProcessor logs whatever export() raises.
        with pytest.raises(requests.exceptions.SSLError):
            exporter.export([span])

        assert http_collector.exported == []
