from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

METRIC_PREFIX = "infrahub_admission"

# Multiprocess note: admission state (slots, waiters, CoDel controllers) is per worker
# process by design, and each gunicorn/uvicorn worker serves its own /metrics from its
# own default registry. The InfrahubUvicorn worker wipes the PROMETHEUS_MULTIPROC_DIR
# contents on init, so these gauges are read per worker and no cross-worker aggregation
# is attempted in v1. If the API process ever runs with PROMETHEUS_MULTIPROC_DIR set and
# aggregation is wanted, IN_FLIGHT/WAITERS would need multiprocess_mode="livesum" and
# MAX_CONCURRENCY multiprocess_mode="max"; that is intentionally deferred, not overlooked.

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
)

WAITERS = Gauge(
    f"{METRIC_PREFIX}_waiters",
    "Requests currently queued waiting for a slot, per priority class",
    labelnames=["priority"],
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
)

MISSING_PRIORITY_TOTAL = Counter(
    f"{METRIC_PREFIX}_missing_priority_total",
    "Requests arriving with no or invalid X-Priority header",
)
