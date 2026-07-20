from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

METRIC_PREFIX = "infrahub_db"

QUERY_EXECUTION_METRICS = Histogram(
    f"{METRIC_PREFIX}_query_execution_seconds",
    "Execution time to query the database",
    labelnames=["type", "query", "runtime", "context1", "context2"],
    buckets=[0.005, 0.01, 0.02, 0.03, 0.04, 0.05, 0.1, 0.5, 1],
)

QUERY_AVAILABLE_AFTER_METRICS = Histogram(
    f"{METRIC_PREFIX}_query_available_after_seconds",
    "Server-side time until the first record is available (Neo4j result_available_after)",
    labelnames=["type", "runtime", "query"],
    buckets=[0.001, 0.0025, 0.005, 0.01, 0.02, 0.03, 0.04, 0.05, 0.1, 0.2, 0.5, 1],
)

# The available-after histogram is scoped to the permission-check queries the request
# admission path depends on. Recording every query name would inflate label cardinality
# and dilute the signal used to gauge database health.
QUERY_AVAILABLE_AFTER_TRACKED_QUERIES: frozenset[str] = frozenset(
    {"account_global_permissions", "account_object_permissions"}
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
