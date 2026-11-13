from __future__ import annotations

import gzip
import hashlib
import json
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import httpx
from typing_extensions import Self

from .constants import PERFORMANCE_TEST_KIND, PERFORMANCE_TEST_VERSION
from .host import get_system_stats

if TYPE_CHECKING:
    from pathlib import Path
    from types import TracebackType

    import pytest

    from .helpers import InfrahubDockerCompose
from .models import (
    ContextUnit,
    InfrahubActiveMeasurementItem,
    InfrahubMeasurementItem,
    InfrahubResultContext,
    MeasurementDefinition,
)

# Bounded so that a stalled endpoint cannot hold the session open indefinitely, while still
# allowing for a payload that grows with the length of the run.
RESULTS_UPLOAD_TIMEOUT = httpx.Timeout(30.0, connect=5.0)

DEFAULT_UPLOAD_RETRIES = 3
# Seconds to wait before each retry; retries past the last one wait as long as it does.
UPLOAD_RETRY_DELAYS = (5.0, 15.0, 30.0)
RETRIED_STATUS_CODES = {408, 429}


class ResultsUploadError(Exception):
    """The results could not be stored by the endpoint."""


class InfrahubPerformanceTest:
    context: dict[str, InfrahubResultContext]
    measurements: list[InfrahubMeasurementItem]
    active_measurements: InfrahubActiveMeasurementItem | None = None

    def __init__(
        self,
        results_url: str,
        *,
        compress: bool = False,
        retries: int = DEFAULT_UPLOAD_RETRIES,
        result_file: Path | None = None,
    ) -> None:
        self.name: str | None = None
        self.infrahub_version: str | None = None
        self.context = {}
        self.measurements = []
        self.metrics = {}
        self.host = get_system_stats()
        self.env_vars = {}
        self.project_name = ""
        self.test_info = {}
        self.start_time = datetime.now(timezone.utc)
        self.end_time: datetime | None = None
        self.results_url = results_url
        self.compress = compress
        self.retries = retries
        self.result_file = result_file
        self.report_error: str | None = None
        self.scraper_endpoint = ""
        self.initialized = False

    def initialize(
        self,
        name: str,
        compose: InfrahubDockerCompose | None = None,
        client: Any | None = None,  # noqa: ANN401
    ) -> None:
        self.name = name
        if client:
            self.infrahub_version = client.get_version()
        if compose:
            self.extract_compose_information(compose)

        self.initialized = True

    def finalize(self, session: pytest.Session) -> None:
        if not self.initialized:
            return

        try:
            self.end_time = datetime.now(timezone.utc)
            self.extract_test_session_information(session)
            self.send_results()
        except BaseException as exc:
            # Anything escaping here aborts the pytest session, skipping the remaining
            # teardown that stops the compose stack. That includes KeyboardInterrupt:
            # a cancelled CI job signals the process again while this is still running.
            self.report_error = str(exc) if isinstance(exc, ResultsUploadError) else repr(exc)
            print(f"Failed to report performance results: {self.report_error}")

    def extract_compose_information(self, compose: InfrahubDockerCompose) -> None:
        self.env_vars = compose.env_vars
        self.project_name = compose.project_name
        self.scraper_endpoint = (
            f"http://127.0.0.1:{compose.get_service_host_and_port(service_name='scraper')[1]}/api/v1/export"
        )

    def extract_test_session_information(self, session: pytest.Session) -> None:
        self.test_info = {
            "summary": {
                "exitstatus": session.exitstatus,
                "nbr_tests": session.testscollected,
                "nbr_errors": session.testsfailed,
            }
        }

    def add_context(self, name: str, value: float | str = 0, unit: ContextUnit = ContextUnit.COUNT) -> None:
        self.context[name] = InfrahubResultContext(name=name, value=value, unit=unit)

    def add_measurement(
        self,
        definition: MeasurementDefinition,
        value: float | str,
        context: dict[str, Any] | None = None,
        **kwargs: str | float,
    ) -> None:
        """Record a measurement.

        Context dimensions can be passed either as keyword arguments or as a `context` mapping.
        Either way they land flat on the recorded item, so every measurement of a definition
        carries the same shape and the whole set compares as a single series.
        """
        self.measurements.append(
            InfrahubMeasurementItem(
                name=definition.name,
                value=value,
                unit=definition.unit,
                context={**(context or {}), **kwargs},
            )
        )

    def start_measurement(self, definition: MeasurementDefinition, **kwargs: str | float) -> Self:
        self.active_measurements = InfrahubActiveMeasurementItem(definition=definition, context=kwargs or {})
        return self

    def fetch_metrics(self) -> None:
        with httpx.Client(timeout=30.0) as client:
            # Get Infrahub metrics
            response = client.post(
                url=self.scraper_endpoint,
                content='match[]={__name__=~"infrahub.*"}',
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            self.metrics = [json.loads(line) for line in response.text.splitlines()]

            # Get system metrics, filter by docker project name
            response = client.post(
                url=self.scraper_endpoint,
                content=f'match[]={{__name__=~"container.*", container_label_com_docker_compose_project="{self.project_name}"}}',
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            self.metrics += [json.loads(line) for line in response.text.splitlines()]

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if not exc_type and self.active_measurements:
            self.add_measurement(
                definition=self.active_measurements.definition,
                value=(datetime.now(timezone.utc) - self.active_measurements.start_time).total_seconds() * 1000,
                context=self.active_measurements.context,
            )

        # Don't record the measurement if the test failed
        self.active_measurements = None

    def _get_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "infrahub_version": self.infrahub_version,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": (self.end_time - self.start_time).total_seconds() * 1000 if self.end_time else None,
            "context": [item.model_dump() for item in self.context.values()],
            "measurements": [item.model_dump() for item in self.measurements],
            "metrics": self.metrics,
            "host": self.host,
            "env_vars": self.env_vars,
            "test_info": self.test_info,
        }

    def _serialize_request(self) -> bytes:
        """Encode the request body, hashing the encoded payload instead of re-encoding it.

        The payload embeds every metric series scraped over the run, which makes it the most
        expensive thing on the session-finish path. Encoding it once and wrapping the envelope
        around those bytes halves that cost, and leaves the checksum covering exactly the bytes
        that go on the wire.
        """
        data = json.dumps(self._get_payload(), separators=(",", ":")).encode()
        envelope = json.dumps(
            {
                "kind": PERFORMANCE_TEST_KIND,
                "payload_format": PERFORMANCE_TEST_VERSION,
                "checksum": hashlib.sha256(data).hexdigest(),
            },
            separators=(",", ":"),
        ).encode()

        return envelope.removesuffix(b"}") + b',"data":' + data + b"}"

    def send_results(self) -> None:
        """Write the payload to the result file, if any, then upload it.

        Connection errors, timeouts, 408, 429 and 5xx answers are retried; other answers are not,
        because sending the same payload again would get the same answer.

        Raises:
            ResultsUploadError: The endpoint did not store the results.
        """
        body = self._serialize_request()
        if self.result_file is not None:
            self.result_file.write_bytes(body)

        headers = {"Content-Type": "application/json"}
        if self.compress:
            body = gzip.compress(body, compresslevel=6)
            headers["Content-Encoding"] = "gzip"

        failure = ""
        with httpx.Client(timeout=RESULTS_UPLOAD_TIMEOUT) as client:
            for attempt in range(self.retries + 1):
                if attempt:
                    delay = UPLOAD_RETRY_DELAYS[min(attempt, len(UPLOAD_RETRY_DELAYS)) - 1]
                    print(f"Uploading the performance results failed ({failure}), retrying in {delay:.0f}s")
                    time.sleep(delay)
                try:
                    response = client.post(self.results_url, content=body, headers=headers)
                except httpx.TransportError as exc:
                    failure = f"{type(exc).__name__}: {exc}"
                    continue
                if response.is_success:
                    return
                failure = f"{response.status_code} {response.text[:200]}"
                if response.status_code not in RETRIED_STATUS_CODES and not response.is_server_error:
                    raise ResultsUploadError(f"{self.results_url} refused the results: {failure}")

        attempts = f"{self.retries + 1} attempt{'s' if self.retries else ''}"
        raise ResultsUploadError(f"{self.results_url} did not store the results after {attempts}: {failure}")
