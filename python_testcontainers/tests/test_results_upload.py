from __future__ import annotations

import gzip
import hashlib
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING

import pytest

from infrahub_testcontainers import performance_test as performance_test_module
from infrahub_testcontainers.measurements import BRANCH_MERGE_TIME
from infrahub_testcontainers.performance_test import InfrahubPerformanceTest, ResultsUploadError

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


class Endpoint:
    """A local results endpoint that answers with the queued statuses, then with 200."""

    def __init__(self) -> None:
        self.requests: list[tuple[dict[str, str], bytes]] = []
        self.statuses: list[int] = []
        endpoint = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                body = self.rfile.read(int(self.headers["Content-Length"]))
                endpoint.requests.append((dict(self.headers), body))
                self.send_response(endpoint.statuses.pop(0) if endpoint.statuses else 200)
                self.end_headers()

            def log_message(self, *args: object) -> None:
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/"


@pytest.fixture
def endpoint() -> Iterator[Endpoint]:
    endpoint = Endpoint()
    thread = threading.Thread(target=endpoint.server.serve_forever, daemon=True)
    thread.start()
    yield endpoint
    endpoint.server.shutdown()
    endpoint.server.server_close()


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(performance_test_module, "UPLOAD_RETRY_DELAYS", (0.0,))


@pytest.fixture
def closed_port_url() -> str:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return f"http://127.0.0.1:{port}/"


def performance_test(url: str, **options: object) -> InfrahubPerformanceTest:
    test = InfrahubPerformanceTest(results_url=url, **options)  # type: ignore[arg-type]
    test.initialize(name="test_results_upload")
    test.add_measurement(BRANCH_MERGE_TIME, value=100)
    return test


def test_results_are_sent_as_json_by_default(endpoint: Endpoint) -> None:
    test = performance_test(endpoint.url)

    test.send_results()

    [(headers, body)] = endpoint.requests
    assert headers["Content-Type"] == "application/json"
    assert "Content-Encoding" not in headers
    assert body == test._serialize_request()  # noqa: SLF001


def test_compressed_results_decompress_to_the_payload_and_its_checksum(endpoint: Endpoint) -> None:
    test = performance_test(endpoint.url, compress=True)

    test.send_results()

    [(headers, body)] = endpoint.requests
    assert headers["Content-Encoding"] == "gzip"
    payload = gzip.decompress(body)
    assert payload == test._serialize_request()  # noqa: SLF001
    data = payload[payload.index(b',"data":') + len(b',"data":') : -1]
    assert json.loads(payload)["checksum"] == hashlib.sha256(data).hexdigest()


def test_server_errors_are_retried(endpoint: Endpoint) -> None:
    failures = [503, 502, 429]
    endpoint.statuses.extend(failures)
    test = performance_test(endpoint.url)

    test.send_results()

    assert len(endpoint.requests) == len(failures) + 1


def test_a_refused_payload_is_not_retried(endpoint: Endpoint) -> None:
    endpoint.statuses.append(400)
    test = performance_test(endpoint.url)

    with pytest.raises(ResultsUploadError, match="refused the results: 400"):
        test.send_results()
    assert len(endpoint.requests) == 1


def test_retries_stop_after_the_configured_count(endpoint: Endpoint) -> None:
    endpoint.statuses.extend([503, 503, 503])
    retries = 1
    test = performance_test(endpoint.url, retries=retries)

    with pytest.raises(ResultsUploadError, match="after 2 attempts: 503"):
        test.send_results()
    assert len(endpoint.requests) == retries + 1


def test_connection_errors_are_retried_then_reported(closed_port_url: str) -> None:
    test = performance_test(closed_port_url, retries=2)

    with pytest.raises(ResultsUploadError, match="after 3 attempts: ConnectError"):
        test.send_results()


def test_the_result_file_is_written_even_when_the_upload_fails(closed_port_url: str, tmp_path: Path) -> None:
    result_file = tmp_path / "results.json"
    test = performance_test(closed_port_url, retries=0, result_file=result_file, compress=True)

    with pytest.raises(ResultsUploadError):
        test.send_results()
    assert result_file.read_bytes() == test._serialize_request()  # noqa: SLF001


def test_finalize_records_why_the_results_were_not_stored(endpoint: Endpoint, request: pytest.FixtureRequest) -> None:
    endpoint.statuses.append(413)
    test = performance_test(endpoint.url)

    test.finalize(session=request.session)

    assert test.report_error is not None
    assert "refused the results: 413" in test.report_error


INNER_TEST = """
from infrahub_testcontainers.measurements import BRANCH_MERGE_TIME


def test_measures(perf_test):
    perf_test.initialize(name="inner")
    perf_test.fetch_metrics = lambda: None
    perf_test.add_measurement(BRANCH_MERGE_TIME, value=100)
"""


@pytest.mark.parametrize(
    ("required_option", "expected"),
    [(["--performance-result-required"], pytest.ExitCode.TESTS_FAILED), ([], pytest.ExitCode.OK)],
    ids=["required", "not-required"],
)
def test_a_required_upload_fails_a_passing_session(
    pytester: pytest.Pytester, closed_port_url: str, required_option: list[str], expected: pytest.ExitCode
) -> None:
    pytester.makepyfile(INNER_TEST)
    options = ["--performance-report", f"--performance-result-address={closed_port_url}"]
    options += ["--performance-result-retries=0", *required_option]

    result = pytester.runpytest_subprocess(*options)

    assert result.ret == expected
    result.stdout.fnmatch_lines(["*Performance results were not stored: *after 1 attempt: ConnectError*", "*1 passed*"])


def test_retries_cannot_be_negative(pytester: pytest.Pytester) -> None:
    pytester.makepyfile("def test_nothing(): pass")

    result = pytester.runpytest_subprocess("--performance-result-retries=-1")

    assert result.ret == pytest.ExitCode.USAGE_ERROR
