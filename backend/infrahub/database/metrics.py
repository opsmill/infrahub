from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

METRIC_PREFIX = "infrahub_db"

QUERY_EXECUTION_METRICS = Histogram(
    f"{METRIC_PREFIX}_query_execution_seconds",
    "Execution time to query the database",
    labelnames=["type", "query", "runtime", "context1", "context2"],
    buckets=[0.005, 0.01, 0.02, 0.03, 0.04, 0.05, 0.1, 0.5, 1],
)

TRANSACTION_RETRIES = Counter(
    f"{METRIC_PREFIX}_transaction_retries",
    "Number of transaction that have been retried due to transcient error",
    labelnames=["name"],
)

CONNECTION_POOL_USAGE = Gauge(
    f"{METRIC_PREFIX}_last_connection_pool_usage",
    "Number of last known active connections in the pool",
    labelnames=["address"],
)
