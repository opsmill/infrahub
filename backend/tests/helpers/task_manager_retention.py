"""Isolate a test from the configuration and Prefect settings that applying the task manager retention changes."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import TYPE_CHECKING

import prefect.context

from infrahub import config
from infrahub.prefect_server.retention import (
    EVENT_RETENTION_OVERRIDES,
    EVENTS_RETENTION_PERIOD,
    VACUUM_ENABLED,
    VACUUM_RETENTION_PERIOD,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    import pytest

LEGACY_EVENTS_RETENTION_PERIOD = "PREFECT_EVENTS_RETENTION_PERIOD"
PREFECT_RETENTION_VARIABLES = (
    VACUUM_ENABLED,
    VACUUM_RETENTION_PERIOD,
    EVENTS_RETENTION_PERIOD,
    LEGACY_EVENTS_RETENTION_PERIOD,
    EVENT_RETENTION_OVERRIDES,
)


@contextmanager
def unloaded_task_manager_retention(monkeypatch: pytest.MonkeyPatch, config_file: Path) -> Iterator[None]:
    """Start from an unloaded configuration and no retention variable, and put the process state back afterwards."""
    monkeypatch.setattr(config.SETTINGS, "settings", None)
    monkeypatch.setattr(prefect.context, "GLOBAL_SETTINGS_CONTEXT", prefect.context.GLOBAL_SETTINGS_CONTEXT)
    monkeypatch.setenv("INFRAHUB_CONFIG", str(config_file))
    for name in (
        "INFRAHUB_TASK_MANAGER_RETENTION_TASK_HISTORY",
        "INFRAHUB_TASK_MANAGER_RETENTION_ACTIVITY_LOG",
        "INFRAHUB_TASK_MANAGER_RETENTION_PREFECT_OWN_EVENTS",
        "PREFECT_API_BLOCKS_REGISTER_ON_START",
        "PREFECT_API_DATABASE_MIGRATE_ON_START",
    ):
        monkeypatch.delenv(name, raising=False)
    # The code under test writes these straight into the environment, which monkeypatch cannot undo for an absent name.
    saved = {name: os.environ.pop(name, None) for name in PREFECT_RETENTION_VARIABLES}

    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
