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

QUERY_CONSUMED_AFTER_METRICS = Histogram(
    f"{METRIC_PREFIX}_query_consumed_after_seconds",
    "Server-side time to stream all records after the first (Neo4j result_consumed_after)",
    labelnames=["type", "runtime", "query"],
    buckets=[0.001, 0.0025, 0.005, 0.01, 0.02, 0.03, 0.04, 0.05, 0.1, 0.2, 0.5, 1],
)

# The available-after and consumed-after histograms are scoped to the permission-check queries
# the request admission path depends on. Recording every query name would inflate label
# cardinality and dilute the signal used to gauge database health.
QUERY_AVAILABLE_AFTER_TRACKED_QUERIES: frozenset[str] = frozenset(
    {"account_global_permissions", "account_object_permissions"}
)

# The single query used as the baseline reference for the database-stress signal. It runs
# once on essentially every authenticated request with no caching, so its execution time is an
# always-present proxy for overall database load.
REFERENCE_QUERY_NAME = "account_global_permissions"

# The database-stress gauges are per-worker figures. Under a MultiProcessCollector (enabled
# when PROMETHEUS_MULTIPROC_DIR is set) an explicit multiprocess_mode is required: the floor
# and window minimum aggregate as "min" to surface the true best-case across workers, and the
# stress ratios aggregate as "max" to surface the most-stressed worker.
REFERENCE_QUERY_FLOOR_SECONDS = Gauge(
    f"{METRIC_PREFIX}_reference_query_floor_seconds",
    "All-time minimum measured execution time for the reference permission query",
    multiprocess_mode="min",
)

REFERENCE_QUERY_WINDOW_MIN_SECONDS = Gauge(
    f"{METRIC_PREFIX}_reference_query_window_min_seconds",
    "Minimum reference-query measured execution time over the recent sliding window",
    multiprocess_mode="min",
)

REFERENCE_QUERY_STRESS_RATIO_MIN = Gauge(
    f"{METRIC_PREFIX}_reference_query_stress_ratio_min",
    "Recent-window minimum reference-query time divided by the all-time floor (1.0 = unstressed)",
    multiprocess_mode="max",
)

REFERENCE_QUERY_STRESS_RATIO_AVG = Gauge(
    f"{METRIC_PREFIX}_reference_query_stress_ratio_avg",
    "Recent-window average reference-query time divided by the all-time floor (1.0 = unstressed)",
    multiprocess_mode="max",
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
