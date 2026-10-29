from __future__ import annotations

import logging
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from prefect.server.database import PrefectDBInterface
from prefect.server.database.configurations import AsyncPostgresConfiguration
from prefect.server.database.orm_models import AsyncPostgresORMConfiguration
from prefect.server.database.query_components import AsyncPostgresQueryComponents
from prefect.server.events.schemas.events import ReceivedEvent, Resource
from prefect.server.events.storage.database import write_events
from prefect.settings import temporary_settings
from sqlalchemy.exc import OperationalError
from tests.helpers.task_manager_seed import task_manager_database

from infrahub.prefect_server.app import warn_about_unlisted_prefect_event_types
from infrahub.prefect_server.database import read_stored_event_types
from infrahub.prefect_server.retention import PREFECT_EVENT_TYPES

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

APP_LOGGER = "infrahub.prefect_server.app"
LISTED_PREFECT_EVENT = "prefect.flow-run.Completed"
UNLISTED_PREFECT_EVENT = "prefect.work-pool.new-status"
UNLISTED_WARNING = (
    "Task manager retention: these stored Prefect event types have no per-type retention in "
    "PREFECT_SERVER_SERVICES_DB_VACUUM_EVENT_RETENTION_OVERRIDES, so they are kept for the activity log retention "
    f"(P365D): {UNLISTED_PREFECT_EVENT}"
)
STORED_EVENT_TYPES_NOT_READ = (
    "Task manager retention: could not read the stored event types, so the check for Prefect event types without a "
    "per-type retention was skipped"
)


@contextmanager
def _per_type_retention_in_effect() -> Generator[None]:
    # The component session turns Prefect's cleanups off, and the check reads the stored types only while a per-type
    # retention deletes events.
    with temporary_settings(
        updates={
            "server.events.retention_period": timedelta(days=365),
            "server.services.db_vacuum.enabled": {"events"},
            "server.services.db_vacuum.event_retention_overrides": dict.fromkeys(
                PREFECT_EVENT_TYPES, timedelta(days=7)
            ),
        }
    ):
        yield


@pytest.fixture
def database(task_manager_database_path: Path) -> Generator[PrefectDBInterface, None, None]:
    # Prefect picks how it writes events from the configured database, not from the session it is given.
    with temporary_settings(
        updates={"server.database.connection_url": f"sqlite+aiosqlite:///{task_manager_database_path}"}
    ):
        yield task_manager_database(task_manager_database_path)


async def _store_events(db: PrefectDBInterface, event_types: list[str]) -> None:
    events = [
        ReceivedEvent(
            id=uuid.uuid4(),
            occurred=datetime.now(UTC),
            event=event_type,
            resource=Resource({"prefect.resource.id": f"test.{uuid.uuid4()}"}),
        )
        for event_type in event_types
    ]
    async with db.session_context(begin_transaction=True) as session:
        await write_events(session=session, events=events)


def _app_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == APP_LOGGER and record.levelno == logging.WARNING
    ]


async def test_each_stored_event_type_is_read_once(database: PrefectDBInterface) -> None:
    await _store_events(
        db=database,
        event_types=[
            "infrahub.node.created",
            LISTED_PREFECT_EVENT,
            UNLISTED_PREFECT_EVENT,
            "infrahub.node.created",
            LISTED_PREFECT_EVENT,
            "custom.event",
        ],
    )

    async with database.session_context() as session:
        stored = await read_stored_event_types(session=session)

    assert sorted(stored) == ["custom.event", "infrahub.node.created", LISTED_PREFECT_EVENT, UNLISTED_PREFECT_EVENT]


async def test_a_stored_prefect_event_type_without_a_per_type_retention_is_logged(
    database: PrefectDBInterface, caplog: pytest.LogCaptureFixture
) -> None:
    await _store_events(
        db=database, event_types=["infrahub.node.created", LISTED_PREFECT_EVENT, UNLISTED_PREFECT_EVENT]
    )

    with _per_type_retention_in_effect(), caplog.at_level(logging.WARNING, logger=APP_LOGGER):
        await warn_about_unlisted_prefect_event_types(db=database)

    assert _app_warnings(caplog=caplog) == [UNLISTED_WARNING]


async def test_nothing_is_logged_when_every_stored_prefect_event_type_is_listed(
    database: PrefectDBInterface, caplog: pytest.LogCaptureFixture
) -> None:
    await _store_events(db=database, event_types=["infrahub.node.created", LISTED_PREFECT_EVENT, "custom.event"])

    with _per_type_retention_in_effect(), caplog.at_level(logging.WARNING, logger=APP_LOGGER):
        await warn_about_unlisted_prefect_event_types(db=database)

    assert _app_warnings(caplog=caplog) == []


async def test_nothing_is_logged_when_no_per_type_retention_is_in_effect(
    database: PrefectDBInterface, caplog: pytest.LogCaptureFixture
) -> None:
    await _store_events(
        db=database, event_types=["infrahub.node.created", LISTED_PREFECT_EVENT, UNLISTED_PREFECT_EVENT]
    )

    # Prefect merges a mapping into the overrides in effect, so they are emptied outside the per-type retention.
    with (
        temporary_settings(
            updates={
                "server.events.retention_period": timedelta(days=365),
                "server.services.db_vacuum.enabled": {"events"},
                "server.services.db_vacuum.event_retention_overrides": {},
            }
        ),
        caplog.at_level(logging.WARNING, logger=APP_LOGGER),
    ):
        await warn_about_unlisted_prefect_event_types(db=database)

    assert _app_warnings(caplog=caplog) == []


async def test_nothing_is_logged_when_no_per_type_retention_is_shorter_than_the_event_retention(
    database: PrefectDBInterface, caplog: pytest.LogCaptureFixture
) -> None:
    await _store_events(
        db=database, event_types=["infrahub.node.created", LISTED_PREFECT_EVENT, UNLISTED_PREFECT_EVENT]
    )

    with (
        _per_type_retention_in_effect(),
        temporary_settings(updates={"server.events.retention_period": timedelta(days=7)}),
        caplog.at_level(logging.WARNING, logger=APP_LOGGER),
    ):
        await warn_about_unlisted_prefect_event_types(db=database)

    assert _app_warnings(caplog=caplog) == []


async def test_nothing_is_logged_when_prefect_deletes_no_events(
    database: PrefectDBInterface, caplog: pytest.LogCaptureFixture
) -> None:
    await _store_events(
        db=database, event_types=["infrahub.node.created", LISTED_PREFECT_EVENT, UNLISTED_PREFECT_EVENT]
    )

    with (
        _per_type_retention_in_effect(),
        temporary_settings(updates={"server.services.db_vacuum.enabled": {"flow_runs"}}),
        caplog.at_level(logging.WARNING, logger=APP_LOGGER),
    ):
        await warn_about_unlisted_prefect_event_types(db=database)

    assert _app_warnings(caplog=caplog) == []


def _database_without_tables(directory: Path) -> PrefectDBInterface:
    return task_manager_database(directory / "unmigrated.db")


def _unreachable_postgres(_directory: Path) -> PrefectDBInterface:
    # A socket directory that does not exist makes the driver fail at once without a network connection, and a path
    # at the root stays under the Unix socket path length limit, which a long temporary directory can exceed.
    socket_directory = Path("/") / f"infrahub-no-socket-{uuid.uuid4().hex}"
    return PrefectDBInterface(
        database_config=AsyncPostgresConfiguration(
            connection_url=f"postgresql+asyncpg://prefect:prefect@/prefect?host={socket_directory}"
        ),
        query_components=AsyncPostgresQueryComponents(),
        orm=AsyncPostgresORMConfiguration(),
    )


@dataclass
class FailedReadTestCase:
    name: str
    database: Callable[[Path], PrefectDBInterface]
    expected_error: type[Exception]


FAILED_READ_TEST_CASES: list[FailedReadTestCase] = [
    FailedReadTestCase(
        name="database_without_the_events_table",
        database=_database_without_tables,
        expected_error=OperationalError,
    ),
    FailedReadTestCase(name="unreachable_postgres", database=_unreachable_postgres, expected_error=FileNotFoundError),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in FAILED_READ_TEST_CASES])
async def test_a_failed_read_of_the_stored_event_types_is_logged_without_stopping_the_startup(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, test_case: FailedReadTestCase
) -> None:
    db = test_case.database(tmp_path)

    with _per_type_retention_in_effect(), caplog.at_level(logging.WARNING, logger=APP_LOGGER):
        await warn_about_unlisted_prefect_event_types(db=db)

    records = [record for record in caplog.records if record.name == APP_LOGGER]
    assert [(record.levelno, record.getMessage()) for record in records] == [
        (logging.WARNING, STORED_EVENT_TYPES_NOT_READ)
    ]
    assert records[0].exc_info is not None
    assert type(records[0].exc_info[1]) is test_case.expected_error
