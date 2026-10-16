from __future__ import annotations

import os
import subprocess  # noqa: S404
import sys
import textwrap
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.serve.gunicorn_config import child_exit, on_starting

if TYPE_CHECKING:
    from pathlib import Path

WORKER_PID = 4242


@dataclass(frozen=True)
class StoppedWorker:
    pid: int


@pytest.fixture
def metric_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(tmp_path))
    return tmp_path


def test_starting_a_worker_keeps_the_metric_files_of_running_workers(metric_dir: Path) -> None:
    (metric_dir / "counter_101.db").touch()
    (metric_dir / "histogram_101.db").touch()

    # Building the worker reconfigures process-wide logging, so it runs in its own interpreter.
    script = textwrap.dedent(
        """
        import os

        from gunicorn.config import Config
        from gunicorn.glogging import Logger

        from infrahub.serve.worker import InfrahubUvicorn

        cfg = Config()
        InfrahubUvicorn(1, os.getpid(), [], None, 30, cfg, Logger(cfg))
        """
    )
    subprocess.run([sys.executable, "-c", script], check=True, env=os.environ.copy(), timeout=60)  # noqa: S603

    assert sorted(path.name for path in metric_dir.iterdir()) == ["counter_101.db", "histogram_101.db"]


def test_server_start_empties_the_metric_directory(metric_dir: Path) -> None:
    (metric_dir / "counter_101.db").touch()
    (metric_dir / "gauge_livesum_101.db").touch()

    on_starting(None)

    assert list(metric_dir.iterdir()) == []


def test_server_start_without_a_metric_directory_does_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    (tmp_path / "counter_101.db").touch()

    on_starting(None)

    assert [path.name for path in tmp_path.iterdir()] == ["counter_101.db"]


def test_stopped_worker_is_dropped_from_live_gauges_only(metric_dir: Path) -> None:
    for name in (
        f"gauge_livesum_{WORKER_PID}.db",
        f"gauge_liveall_{WORKER_PID}.db",
        f"gauge_max_{WORKER_PID}.db",
        f"counter_{WORKER_PID}.db",
        "gauge_livesum_7.db",
    ):
        (metric_dir / name).touch()

    child_exit(None, StoppedWorker(pid=WORKER_PID))

    assert sorted(path.name for path in metric_dir.iterdir()) == [
        f"counter_{WORKER_PID}.db",
        "gauge_livesum_7.db",
        f"gauge_max_{WORKER_PID}.db",
    ]


def test_stopped_worker_without_a_metric_directory_does_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    (tmp_path / f"gauge_livesum_{WORKER_PID}.db").touch()

    child_exit(None, StoppedWorker(pid=WORKER_PID))

    assert [path.name for path in tmp_path.iterdir()] == [f"gauge_livesum_{WORKER_PID}.db"]
