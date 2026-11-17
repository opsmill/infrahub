from __future__ import annotations

import os
import sqlite3
import subprocess  # noqa: S404 - Prefect migrates only the database of its process
import sys
from contextlib import closing
from typing import TYPE_CHECKING

from prefect.server.database import provide_database_interface
from prefect.server.events.schemas.events import ReceivedEvent, RelatedResource, Resource
from prefect.server.events.storage.database import write_events
from pydantic_core import to_jsonable_python

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path
    from uuid import UUID

    from infrahub.events.models import InfrahubEvent


async def seed_infrahub_event(event: InfrahubEvent, occurred: datetime) -> UUID:
    """Store an Infrahub event in the task manager's database as if it had occurred at the given time."""
    received = ReceivedEvent(
        id=event.meta.id,
        event=event.event_name,
        occurred=occurred,
        resource=Resource(event.get_resource()),
        related=[RelatedResource(item) for item in event.get_related()],
        payload=to_jsonable_python(event.get_event_payload()),
    )
    await _store(events=[received])
    return received.id


async def _store(events: list[ReceivedEvent]) -> None:
    db = provide_database_interface()
    # Takes the SQLite write lock up front, so a concurrent writer makes the insert wait rather than fail as locked.
    async with db.session_context(begin_transaction=True, with_for_update=True) as session:
        await write_events(session=session, events=events)


def migrate_task_manager_database(path: Path) -> None:
    """Create a SQLite database at the path with Prefect's migrations applied.

    The migrations run in a subprocess, because Prefect binds its migrations to the process-wide database settings.

    Raises:
        RuntimeError: When the migrations fail.

    """
    environment = {name: value for name, value in os.environ.items() if not name.endswith("DATABASE_CONNECTION_URL")}
    environment["PREFECT_SERVER_DATABASE_CONNECTION_URL"] = f"sqlite+aiosqlite:///{path}"
    result = subprocess.run(
        args=[
            sys.executable,
            "-c",
            "import asyncio; from prefect.server.database import provide_database_interface; "
            "asyncio.run(provide_database_interface().create_db())",
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Migrating the task manager database at {path} failed:\n{result.stderr}")


def copy_task_manager_database(source: Path, target: Path) -> None:
    """Copy a SQLite task manager database, including the writes still held in its write-ahead log."""
    with closing(sqlite3.connect(source)) as source_connection, closing(sqlite3.connect(target)) as target_connection:
        source_connection.backup(target_connection)
