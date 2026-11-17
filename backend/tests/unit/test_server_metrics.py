from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from infrahub.server import app

if TYPE_CHECKING:
    from collections.abc import Iterator

REQUEST_DURATION = "infrahub_request_duration_seconds"


@pytest.fixture
def client() -> Iterator[TestClient]:
    """A client on the application without its startup, so admission is turned off by hand."""
    previous = getattr(app.state, "admission_enabled", None)
    app.state.admission_enabled = False
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        if previous is None:
            del app.state.admission_enabled
        else:
            app.state.admission_enabled = previous


def _recorded_request_count(method: str, path: str) -> float:
    return sum(
        sample.value
        for metric in REGISTRY.collect()
        if metric.name == REQUEST_DURATION
        for sample in metric.samples
        if sample.name == f"{REQUEST_DURATION}_count"
        and sample.labels["method"] == method
        and sample.labels["path"] == path
    )


def _bucket_bounds(method: str, path: str) -> list[str]:
    return [
        sample.labels["le"]
        for metric in REGISTRY.collect()
        if metric.name == REQUEST_DURATION
        for sample in metric.samples
        if sample.name == f"{REQUEST_DURATION}_bucket"
        and sample.labels["method"] == method
        and sample.labels["path"] == path
        and sample.labels["le"] != "+Inf"
    ]


@dataclass(frozen=True)
class RecordedRequestCase:
    name: str
    method: str
    url: str
    route: str


RECORDED_REQUEST_CASES: list[RecordedRequestCase] = [
    RecordedRequestCase(name="rest_api", method="GET", url="/api/config", route="/api/config"),
    RecordedRequestCase(name="graphql", method="POST", url="/graphql/main", route="/graphql/{branch_name:path}"),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in RECORDED_REQUEST_CASES])
def test_request_is_recorded_with_its_route_as_path(client: TestClient, case: RecordedRequestCase) -> None:
    count_before = _recorded_request_count(method=case.method, path=case.route)

    # The GraphQL request fails without a database, and a failed request must be recorded too.
    client.request(case.method, case.url, json={"query": "{ __typename }"} if case.method == "POST" else None)

    assert _recorded_request_count(method=case.method, path=case.route) == count_before + 1


def test_request_duration_is_recorded_up_to_twenty_minutes(client: TestClient) -> None:
    client.get("/metrics")

    assert _bucket_bounds(method="GET", path="/metrics") == [
        "0.1",
        "0.25",
        "0.5",
        "1.0",
        "2.5",
        "5.0",
        "10.0",
        "30.0",
        "60.0",
        "120.0",
        "300.0",
        "600.0",
        "1200.0",
    ]
