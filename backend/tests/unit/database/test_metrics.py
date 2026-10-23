from __future__ import annotations

from prometheus_client import REGISTRY

from infrahub.database.metrics import CONNECTION_WAIT_METRICS, QUERY_EXECUTION_METRICS
from tests.helpers.metrics import bucket_bounds

QUERY_LABELS = {"type": "read", "query": "bucket_bounds_probe", "runtime": "default", "context1": "", "context2": ""}


def test_query_duration_is_recorded_up_to_five_minutes() -> None:
    QUERY_EXECUTION_METRICS.labels(**QUERY_LABELS).observe(30)

    assert bucket_bounds(QUERY_EXECUTION_METRICS, labels=QUERY_LABELS) == [
        "0.005",
        "0.01",
        "0.02",
        "0.03",
        "0.04",
        "0.05",
        "0.1",
        "0.5",
        "1.0",
        "2.5",
        "5.0",
        "10.0",
        "30.0",
        "60.0",
        "120.0",
        "300.0",
    ]
    assert REGISTRY.get_sample_value("infrahub_db_query_execution_seconds_bucket", {**QUERY_LABELS, "le": "10.0"}) == 0
    assert REGISTRY.get_sample_value("infrahub_db_query_execution_seconds_bucket", {**QUERY_LABELS, "le": "30.0"}) == 1


def test_connection_wait_is_recorded_up_to_one_minute() -> None:
    assert bucket_bounds(CONNECTION_WAIT_METRICS) == [
        "0.001",
        "0.01",
        "0.1",
        "0.5",
        "1.0",
        "5.0",
        "10.0",
        "30.0",
        "60.0",
    ]
