from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

METRIC_PREFIX = "infrahub_admission"

# Admission state is per worker process, and the API server combines its workers' values in one
# /metrics response, so counts and slot limits are summed over live workers to compare usage with capacity.

OFFERED_TOTAL = Counter(
    f"{METRIC_PREFIX}_offered_total",
    "Requests entering the admission layer, per priority class",
    labelnames=["priority"],
)

ADMITTED_TOTAL = Counter(
    f"{METRIC_PREFIX}_admitted_total",
    "Requests admitted by the admission layer, per priority class",
    labelnames=["priority"],
)

REJECTED_TOTAL = Counter(
    f"{METRIC_PREFIX}_rejected_total",
    "Requests shed by the admission layer, per priority class and reason",
    labelnames=["priority", "reason"],
)

IN_FLIGHT = Gauge(
    f"{METRIC_PREFIX}_in_flight",
    "Currently-running admitted requests, per priority class",
    labelnames=["priority"],
    multiprocess_mode="livesum",
)

WAITERS = Gauge(
    f"{METRIC_PREFIX}_waiters",
    "Requests currently queued waiting for a slot, per priority class",
    labelnames=["priority"],
    multiprocess_mode="livesum",
)

SOJOURN_SECONDS = Histogram(
    f"{METRIC_PREFIX}_sojourn_seconds",
    "Slot-wait (sojourn) time per priority class, in seconds",
    labelnames=["priority"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 5],
)

MAX_CONCURRENCY = Gauge(
    f"{METRIC_PREFIX}_max_concurrency",
    "Effective derived per-worker admission slot cap",
    multiprocess_mode="livesum",
)

MISSING_PRIORITY_TOTAL = Counter(
    f"{METRIC_PREFIX}_missing_priority_total",
    "Requests arriving with no or invalid X-Priority header",
)

SUSTAINED_LOAD_SECONDS = Gauge(
    f"{METRIC_PREFIX}_sustained_load_seconds",
    "Seconds the worker has continuously observed database stress at or above the significant-load ratio (0 below it)",
    # Each worker runs its own clock, so one series per live worker is kept.
    multiprocess_mode="liveall",
)
