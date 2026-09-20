"""Unit tests for the defensive worker/server resource-block construction.

``_build_worker_data``/``_build_server_data`` are the last step before a fleet
resource aggregate reaches the final payload. A healthy aggregate always has
every figure already validated non-negative where the underlying reading was
read back out of the cache, but these two functions are the safety net for
when that is not true — an aggregate assembled from bad inputs, or a future
stricter constraint on the payload model itself — so that block degrades to
null instead of aborting the whole gather.
"""

import logging

import pytest

from infrahub.telemetry.models import TelemetryServerData, TelemetryWorkerData
from infrahub.telemetry.resources import ResourceAggregate
from infrahub.telemetry.tasks import _build_server_data, _build_worker_data

_LOGGER_NAME = "infrahub.tasks"


def test_build_worker_data_populates_resources_from_a_healthy_aggregate() -> None:
    resources = ResourceAggregate(
        processor_available=8, processor_assigned=None, memory_total=16_000_000_000, memory_available=10_000_000_000
    )

    data = _build_worker_data(total=3, active=2, resources=resources)

    assert data == TelemetryWorkerData(
        total=3,
        active=2,
        processor_available=8,
        processor_assigned=None,
        memory_total=16_000_000_000,
        memory_available=10_000_000_000,
    )


def test_build_worker_data_with_no_aggregate_yields_null_resource_fields() -> None:
    data = _build_worker_data(total=0, active=0, resources=None)

    assert data == TelemetryWorkerData(total=0, active=0)


def test_build_worker_data_degrades_resources_to_null_on_an_invalid_aggregate(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An aggregate the payload model itself rejects still nulls only its own resource block.

    ``ResourceAggregate`` carries no validation of its own, so a negative figure here
    stands in for a bug in the aggregation math rather than a bad cache entry, which
    is already excluded before this point.
    """
    resources = ResourceAggregate(processor_available=-4, memory_total=8, memory_available=6)

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        data = _build_worker_data(total=3, active=2, resources=resources)

    # The worker count is unaffected; only the resource figures are dropped.
    assert data == TelemetryWorkerData(total=3, active=2)
    assert any("Worker resource figures failed validation" in record.getMessage() for record in caplog.records)


def test_build_server_data_populates_resources_from_a_healthy_aggregate() -> None:
    resources = ResourceAggregate(processor_available=4, processor_assigned=4, memory_total=8, memory_available=6)

    data = _build_server_data(resources=resources)

    assert data == TelemetryServerData(processor_available=4, processor_assigned=4, memory_total=8, memory_available=6)


def test_build_server_data_with_no_aggregate_yields_null_resource_fields() -> None:
    data = _build_server_data(resources=None)

    assert data == TelemetryServerData()


def test_build_server_data_degrades_to_null_on_an_invalid_aggregate(caplog: pytest.LogCaptureFixture) -> None:
    resources = ResourceAggregate(memory_total=-1)

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        data = _build_server_data(resources=resources)

    assert data == TelemetryServerData()
    assert any("Server resource figures failed validation" in record.getMessage() for record in caplog.records)
