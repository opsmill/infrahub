from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
import sqlalchemy as sa
from prefect.server.database import provide_database_interface
from prefect.server.services.db_vacuum import vacuum_events_with_retention_overrides, vacuum_old_events
from prefect.settings import temporary_settings
from prefect.settings.models.server.events import ServerEventsSettings
from prefect.settings.models.server.services import ServerServicesDBVacuumSettings
from tests.helpers.events import dummy_event_meta
from tests.helpers.task_manager_seed import seed_infrahub_event, seed_prefect_event

from infrahub.config import TaskManagerRetentionSettings
from infrahub.core.branch import Branch
from infrahub.events.branch_action import BranchCreatedEvent
from infrahub.prefect_server.retention import PREFECT_EVENT_TYPES, build_prefect_retention_env

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def year_of_activity_log(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Give Prefect's vacuum a 365-day activity log and 7 days for its own events, parsed from the derived variables."""
    retention = TaskManagerRetentionSettings(activity_log="365d", prefect_own_events="7d")
    for name, value in build_prefect_retention_env(settings=retention, event_types=PREFECT_EVENT_TYPES).items():
        monkeypatch.setenv(name, value)

    with temporary_settings(
        updates={
            "server.events.retention_period": ServerEventsSettings().retention_period,
            "server.services.db_vacuum.event_retention_overrides": (
                ServerServicesDBVacuumSettings().event_retention_overrides
            ),
        }
    ):
        yield


def _branch_created_event() -> BranchCreatedEvent:
    branch_id = uuid.uuid4()
    return BranchCreatedEvent(
        branch_name=f"branch-{branch_id}",
        branch_id=str(branch_id),
        sync_with_git=False,
        meta=dummy_event_meta(branch=Branch(name=f"branch-{branch_id}", uuid=branch_id)),
    )


@pytest.mark.usefixtures("year_of_activity_log")
async def test_prefect_own_events_expire_before_the_activity_log() -> None:
    """Listed Prefect events go after 7 days with their related items, Infrahub and unlisted events after a year."""
    now = datetime.now(UTC)
    kept = {
        await seed_infrahub_event(event=_branch_created_event(), occurred=now - timedelta(days=30)),
        await seed_prefect_event(event_name="prefect.flow-run.Completed", occurred=now - timedelta(days=1)),
        await seed_prefect_event(event_name="prefect.flow-run.Custom", occurred=now - timedelta(days=30)),
    }
    deleted = {
        await seed_infrahub_event(event=_branch_created_event(), occurred=now - timedelta(days=400)),
        await seed_prefect_event(event_name="prefect.flow-run.Completed", occurred=now - timedelta(days=8)),
        await seed_prefect_event(event_name="prefect.task-run.Running", occurred=now - timedelta(days=8)),
    }
    seeded = kept | deleted
    db = provide_database_interface()

    await vacuum_events_with_retention_overrides(db=db)
    await vacuum_old_events(db=db)

    async with db.session_context() as session:
        remaining_events = set(await session.scalars(sa.select(db.Event.id).where(db.Event.id.in_(seeded))))
        events_with_resources = set(
            await session.scalars(sa.select(db.EventResource.event_id).where(db.EventResource.event_id.in_(seeded)))
        )
    assert remaining_events == kept
    assert events_with_resources == kept
