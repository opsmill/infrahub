from __future__ import annotations

from prometheus_client import REGISTRY

from infrahub.graphql.metrics import GRAPHQL_DURATION_METRICS
from tests.helpers.metrics import bucket_bounds

QUERY_LABELS = {"type": "query", "operation": "query", "branch": "main", "name": "bucket_bounds_probe", "query_id": ""}


def test_graphql_duration_is_recorded_up_to_twenty_minutes() -> None:
    GRAPHQL_DURATION_METRICS.labels(**QUERY_LABELS).observe(300)

    assert bucket_bounds(GRAPHQL_DURATION_METRICS, labels=QUERY_LABELS) == [
        "0.01",
        "0.025",
        "0.05",
        "0.1",
        "0.5",
        "1.0",
        "5.0",
        "10.0",
        "60.0",
        "120.0",
        "300.0",
        "600.0",
        "1200.0",
    ]
    assert REGISTRY.get_sample_value("infrahub_graphql_duration_seconds_bucket", {**QUERY_LABELS, "le": "120.0"}) == 0
    assert REGISTRY.get_sample_value("infrahub_graphql_duration_seconds_bucket", {**QUERY_LABELS, "le": "300.0"}) == 1
