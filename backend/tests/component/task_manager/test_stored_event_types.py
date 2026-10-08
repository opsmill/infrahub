from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from prefect.server.events.schemas.events import ReceivedEvent, Resource
from prefect.server.events.storage.database import write_events
from prefect.settings import temporary_settings
from tests.helpers.task_manager_seed import task_manager_database

from infrahub.prefect_server.app import warn_about_unlisted_prefect_event_types
from infrahub.prefect_server.database import read_stored_event_types

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from prefect.server.database import PrefectDBInterface

APP_LOGGER = "infrahub.prefect_server.app"
LISTED_PREFECT_EVENT = "prefect.flow-run.Completed"
UNLISTED_PREFECT_EVENT = "prefect.work-pool.new-status"


@pytest.fixture
def database(task_manager_database_path: Path) -> Generator[PrefectDBInterface, None, None]:
    # Prefect picks how it writes events from the configured database, not from the session it is given.
    with temporary_settings(
        updates={
            "server.database.connection_url": f"sqlite+aiosqlite:///{task_manager_database_path}",
            "server.events.retention_period": timedelta(days=365),
        }
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


async def test_a_stored_prefect_event_type_missing_from_the_list_is_logged(
    database: PrefectDBInterface, caplog: pytest.LogCaptureFixture
) -> None:
    await _store_events(
        db=database, event_types=["infrahub.node.created", LISTED_PREFECT_EVENT, UNLISTED_PREFECT_EVENT]
    )

    with caplog.at_level(logging.WARNING, logger=APP_LOGGER):
        await warn_about_unlisted_prefect_event_types(db=database)

    assert _app_warnings(caplog=caplog) == [
        "Task manager retention: Infrahub does not list these Prefect event types, so they are kept for the activity "
        f"log retention (365 days) instead of prefect_own_events: {UNLISTED_PREFECT_EVENT}"
    ]


async def test_nothing_is_logged_when_every_stored_prefect_event_type_is_listed(
    database: PrefectDBInterface, caplog: pytest.LogCaptureFixture
) -> None:
    await _store_events(db=database, event_types=["infrahub.node.created", LISTED_PREFECT_EVENT, "custom.event"])

    with caplog.at_level(logging.WARNING, logger=APP_LOGGER):
        await warn_about_unlisted_prefect_event_types(db=database)

    assert _app_warnings(caplog=caplog) == []
