from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from prefect.settings import temporary_settings

from infrahub.prefect_server.app import warn_about_unlisted_prefect_event_types
from tests.helpers.task_manager_seed import task_manager_database

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class SkippedLookupCase:
    name: str
    vacuum_types: set[str]
    overrides: dict[str, timedelta]


SKIPPED_LOOKUP_CASES: list[SkippedLookupCase] = [
    SkippedLookupCase(name="no_overrides", vacuum_types={"events"}, overrides={}),
    SkippedLookupCase(
        name="override_equals_event_retention",
        vacuum_types={"events"},
        overrides={"prefect.flow-run.Completed": timedelta(days=7)},
    ),
    SkippedLookupCase(
        name="event_cleanup_disabled",
        vacuum_types={"flow_runs"},
        overrides={"prefect.flow-run.Completed": timedelta(days=1)},
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in SKIPPED_LOOKUP_CASES])
async def test_startup_skips_the_database_without_a_shorter_event_retention(
    case: SkippedLookupCase, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    database_path = tmp_path / "unused.db"
    database = task_manager_database(database_path)

    with (
        temporary_settings(
            updates={
                "server.events.retention_period": timedelta(days=7),
                "server.services.event_persister.enabled": True,
                "server.services.db_vacuum.enabled": case.vacuum_types,
                "server.services.db_vacuum.event_retention_overrides": case.overrides,
            }
        ),
        caplog.at_level(logging.WARNING, logger="infrahub.prefect_server.app"),
    ):
        await warn_about_unlisted_prefect_event_types(db=database)

    assert not database_path.exists()
    assert [record for record in caplog.records if record.name == "infrahub.prefect_server.app"] == []
