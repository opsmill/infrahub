from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from prometheus_client import multiprocess

if TYPE_CHECKING:
    from gunicorn.arbiter import Arbiter

bind = "0.0.0.0:8000"
timeout = 90
workers = 4
worker_class = "infrahub.serve.worker.InfrahubUvicorn"

PROMETHEUS_MULTIPROC_DIR_ENV = "PROMETHEUS_MULTIPROC_DIR"


class WorkerProcess(Protocol):
    @property
    def pid(self) -> int: ...


def on_starting(_server: Arbiter | None) -> None:
    """Remove the metric files of a previous run, once, before any worker starts."""
    metric_dir = os.environ.get(PROMETHEUS_MULTIPROC_DIR_ENV)
    if not metric_dir:
        return
    for file_path in Path(metric_dir).iterdir():
        file_path.unlink()


def child_exit(_server: Arbiter | None, worker: WorkerProcess) -> None:
    """Drop the values of a stopped worker from the gauges that only count live processes."""
    metric_dir = os.environ.get(PROMETHEUS_MULTIPROC_DIR_ENV)
    if not metric_dir:
        return
    multiprocess.mark_process_dead(pid=worker.pid, path=metric_dir)
