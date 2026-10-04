"""Prefect variable names written as literals, so a misspelled name in the code under test fails the tests.

The context manager isolates a test from the settings that applying the task manager retention changes.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import TYPE_CHECKING

import prefect.context

from infrahub import config

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    import pytest

VACUUM_ENABLED = "PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED"
VACUUM_RETENTION_PERIOD = "PREFECT_SERVER_SERVICES_DB_VACUUM_RETENTION_PERIOD"
EVENTS_RETENTION_PERIOD = "PREFECT_SERVER_EVENTS_RETENTION_PERIOD"
LEGACY_EVENTS_RETENTION_PERIOD = "PREFECT_EVENTS_RETENTION_PERIOD"
EVENT_RETENTION_OVERRIDES = "PREFECT_SERVER_SERVICES_DB_VACUUM_EVENT_RETENTION_OVERRIDES"
WEBSERVER_ONLY = "PREFECT__SERVER_WEBSERVER_ONLY"

PREFECT_RETENTION_VARIABLES = (
    VACUUM_ENABLED,
    VACUUM_RETENTION_PERIOD,
    EVENTS_RETENTION_PERIOD,
    LEGACY_EVENTS_RETENTION_PERIOD,
    EVENT_RETENTION_OVERRIDES,
)

# Prefect skips the profile while any of these is set.
PREFECT_TEST_MODE_VARIABLES = (
    "PREFECT_TEST_MODE",
    "PREFECT_UNIT_TEST_MODE",
    "PREFECT_TESTING_UNIT_TEST_MODE",
    "PREFECT_TESTING_TEST_MODE",
)


@contextmanager
def unloaded_task_manager_retention(monkeypatch: pytest.MonkeyPatch, directory: Path) -> Iterator[None]:
    """Start with no configuration loaded and no Prefect setting from any source, then restore the process state.

    Args:
        monkeypatch: The test's monkeypatch, which puts back every value it changes.
        directory: An empty directory the test runs in, where neither Infrahub nor Prefect finds a settings file.

    """
    monkeypatch.setattr(config.SETTINGS, "settings", None)
    monkeypatch.setattr(prefect.context, "GLOBAL_SETTINGS_CONTEXT", prefect.context.GLOBAL_SETTINGS_CONTEXT)
    monkeypatch.chdir(directory)
    monkeypatch.setenv("INFRAHUB_CONFIG", str(directory / "absent.toml"))
    monkeypatch.setenv("PREFECT_PROFILES_PATH", str(directory / "profiles.toml"))
    for name in (
        "INFRAHUB_TASK_MANAGER_RETENTION_TASK_HISTORY",
        "INFRAHUB_TASK_MANAGER_RETENTION_ACTIVITY_LOG",
        "INFRAHUB_TASK_MANAGER_RETENTION_PREFECT_OWN_EVENTS",
        "PREFECT_API_BLOCKS_REGISTER_ON_START",
        "PREFECT_API_DATABASE_MIGRATE_ON_START",
        WEBSERVER_ONLY,
        *PREFECT_TEST_MODE_VARIABLES,
        *PREFECT_RETENTION_VARIABLES,
    ):
        monkeypatch.delenv(name, raising=False)

    try:
        yield
    finally:
        # The code under test writes these directly, and pytest puts back only the values set before the test.
        for name in PREFECT_RETENTION_VARIABLES:
            os.environ.pop(name, None)
