import hashlib
import json
from datetime import datetime, timezone
from types import TracebackType
from typing import Any

import httpx
import pytest
from typing_extensions import Self

from .constants import PERFORMANCE_TEST_KIND, PERFORMANCE_TEST_VERSION
from .helpers import InfrahubDockerCompose
from .host import get_system_stats
from .models import (
    ContextUnit,
    InfrahubActiveMeasurementItem,
    InfrahubMeasurementItem,
    InfrahubResultContext,
    MeasurementDefinition,
)


class InfrahubPerformanceTest:
    context: dict[str, InfrahubResultContext]
    measurements: list[InfrahubMeasurementItem]
    active_measurements: InfrahubActiveMeasurementItem | None = None

    def __init__(self, results_url: str) -> None:
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
        if self.initialized:
            self.end_time = datetime.now(timezone.utc)
            self.extract_test_session_information(session)
            self.send_results()

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
        **kwargs: str | float,
    ) -> None:
        self.measurements.append(
            InfrahubMeasurementItem(
                name=definition.name,
                value=value,
                unit=definition.unit,
                context=kwargs or {},
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

    def send_results(self) -> None:
        data = self._get_payload()

        payload = {
            "kind": PERFORMANCE_TEST_KIND,
            "payload_format": PERFORMANCE_TEST_VERSION,
            "data": data,
            "checksum": hashlib.sha256(json.dumps(data).encode()).hexdigest(),
        }

        with httpx.Client() as client:
            response = client.post(self.results_url, json=payload)
            response.raise_for_status()
