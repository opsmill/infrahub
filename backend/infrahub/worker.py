import threading
import uuid

from prometheus_client import Gauge

from infrahub import __version__ as infrahub_version

# Process-level identity — used for the process-wide info metric and cosmetic
# logging/tracing. Under the embedded free-threaded backend the API server runs
# multiple worker THREADS in one process; per-worker resources (exclusive message
# bus queues, the primary-server election, heartbeats, lock ownership) must use a
# DISTINCT identity per worker thread, via get_worker_identity().
WORKER_IDENTITY = str(uuid.uuid4())

_worker_identity = threading.local()


def get_worker_identity() -> str:
    """Return an identity unique to the current worker thread.

    Subprocess backend: one worker per process, so this is effectively a
    per-process identity. Embedded backend: each worker thread (with its own event
    loop) gets its own identity, so exclusive broker queues don't collide and the
    primary-server election promotes exactly one worker thread.
    """
    identity = getattr(_worker_identity, "value", None)
    if identity is None:
        identity = str(uuid.uuid4())
        _worker_identity.value = identity
    return identity

INFO_METRIC = Gauge(
    "infrahub_info",
    "Information about this Infrahub instance",
    labelnames=["version", "worker_id"],
)
INFO_METRIC.labels(version=infrahub_version, worker_id=WORKER_IDENTITY).set(1)
