import uuid

from prometheus_client import Gauge

from infrahub import __version__ as infrahub_version

WORKER_IDENTITY = str(uuid.uuid4())

INFO_METRIC = Gauge(
    "infrahub_info",
    "Information about this Infrahub instance",
    labelnames=["version", "worker_id"],
)
INFO_METRIC.labels(version=infrahub_version, worker_id=WORKER_IDENTITY).set(1)
