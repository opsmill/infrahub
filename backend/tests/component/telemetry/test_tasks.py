"""Component tests for the telemetry gather flow and payload resilience."""

import hashlib
import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Generator

import pytest
from prefect.client.orchestration import get_client

from infrahub import __version__, config
from infrahub.components import ComponentType
from infrahub.core import registry
from infrahub.core.constants import AccountStatus, InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.events.account_action import AccountLoggedInEvent
from infrahub.telemetry.constants import TELEMETRY_KIND, TELEMETRY_VERSION, RemoteSendStatus
from infrahub.telemetry.models import TelemetryAccountData, TelemetryActivity24hData, TelemetryData
from infrahub.telemetry.repository import TelemetrySnapshotRepository
from infrahub.telemetry.snapshot import TelemetrySnapshot
from infrahub.telemetry.task_manager import (
    count_webhook_runs,
    count_windowed_event,
    count_windowed_unique_resources,
)
from infrahub.telemetry.tasks import (
    count_active_branches,
    gather_account_information,
    gather_anonymous_telemetry_data,
)
from infrahub.workers.dependencies import build_component, clear_singletons, set_component_type
from tests.adapters.cache import MemoryCache
from tests.adapters.message_bus import BusSimulator

# A calendar day far enough in the past that no test in any session has seeded an event into it;
# used to prove the genuine-empty -> 0 contract independent of shared Prefect server state.
_EMPTY_WINDOW_START = datetime(2000, 1, 1, tzinfo=UTC)
_EMPTY_WINDOW_END = datetime(2000, 1, 2, tzinfo=UTC)

_ACTIVITY_FIELDS = (
    "logins",
    "unique_logins",
    "checks_started",
    "checks_passed",
    "checks_failed",
    "artifacts_created",
    "artifacts_updated",
    "branches_created",
    "branches_merged",
    "branches_deleted",
    "webhooks_fired_success",
    "webhooks_fired_failure",
)


async def _create_account(db: InfrahubDatabase, name: str, status: str) -> None:
    account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await account.new(db=db, name=name, account_type="User", password=" accountPassword123", status=status)
    await account.save(db=db)


async def _create_account_group(db: InfrahubDatabase, name: str) -> None:
    group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group.new(db=db, name=name)
    await group.save(db=db)


async def _store_snapshot(db: InfrahubDatabase, data: TelemetryData) -> TelemetrySnapshot:
    """Persist a telemetry payload exactly as the send flow does, returning the saved snapshot."""
    data_dict = data.model_dump(mode="json")
    checksum = hashlib.sha256(json.dumps(data_dict).encode()).hexdigest()
    snapshot = TelemetrySnapshot(
        kind=TELEMETRY_KIND,
        payload_format=TELEMETRY_VERSION,
        deployment_id=str(registry.id) if registry.id else "",
        infrahub_version=__version__,
        data=data_dict,
        checksum=checksum,
        remote_send_status=RemoteSendStatus.PENDING,
    )
    repository = TelemetrySnapshotRepository(db=db)
    await repository.save(snapshot)
    return snapshot


async def test_gather_account_information_counts(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch
) -> None:
    # Two active + one inactive account, and two account groups.
    await _create_account(db=db, name="active-one", status=AccountStatus.ACTIVE.value)
    await _create_account(db=db, name="active-two", status=AccountStatus.ACTIVE.value)
    await _create_account(db=db, name="inactive-one", status=AccountStatus.INACTIVE.value)
    await _create_account_group(db=db, name="group-one")
    await _create_account_group(db=db, name="group-two")

    data = await gather_account_information.fn(db=db)

    # Only the two active accounts are counted; the inactive one is excluded.
    assert data.active == 2
    assert data.groups == 2


async def test_active_branches_excludes_default_and_global(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch
) -> None:
    # The registry already holds the default (main) and global (-global-) branches. Add two
    # open branches; only those two must be counted as active.
    await create_branch(branch_name="feature-a", db=db)
    await create_branch(branch_name="feature-b", db=db)

    # The default and global branches are present and excluded by the active count.
    assert any(branch.is_default for branch in registry.branch.values())
    assert any(branch.is_global for branch in registry.branch.values())

    assert await count_active_branches() == 2


@pytest.fixture
async def telemetry_environment(
    db: InfrahubDatabase,
    register_core_models_schema: SchemaBranch,
    prefect_test_fixture: Generator[None, None, None],
) -> AsyncGenerator[InfrahubDatabase, None]:
    """Wire the real in-memory collaborators the gather orchestrator depends on, no mocks.

    ``gather_anonymous_telemetry_data`` resolves a cache- and message-bus-backed component plus
    a Prefect client. The cache and bus are the project's in-memory adapters (the sanctioned
    test doubles), set through the dependency-override hooks the builders already honor; the
    component type is set so a worker heartbeat key exists. Singletons are cleared on both sides
    so the wiring does not leak into or out of this module.
    """
    previous_cache = config.OVERRIDE.cache
    previous_message_bus = config.OVERRIDE.message_bus
    previous_registry_id = registry.id
    clear_singletons()
    config.OVERRIDE.cache = MemoryCache()
    config.OVERRIDE.message_bus = BusSimulator()
    registry.id = "test-deployment"
    set_component_type(ComponentType.API_SERVER)
    # Build the component once so it heartbeats into the in-memory cache before list_workers.
    await build_component()
    try:
        yield db
    finally:
        config.OVERRIDE.cache = previous_cache
        config.OVERRIDE.message_bus = previous_message_bus
        registry.id = previous_registry_id
        clear_singletons()


async def test_gather_full_payload_fields_present(telemetry_environment: InfrahubDatabase) -> None:
    """A healthy gather populates every new field on the payload (presence, not exact values)."""
    data = await gather_anonymous_telemetry_data.fn()

    assert isinstance(data, TelemetryData)

    # Accounts adoption metrics are present.
    assert data.accounts.active is not None
    assert data.accounts.groups is not None

    # Active branch count is present.
    assert data.branches.active is not None

    # Branch-correct managed-node count is present inside node_count.
    assert "corenode" in data.database.node_count
    assert data.database.node_count["corenode"] is not None

    # Every activity_24h field is present (an empty window is 0, not null).
    for field in _ACTIVITY_FIELDS:
        assert getattr(data.activity_24h, field) is not None, field


async def _empty_window_activity_gatherer() -> TelemetryActivity24hData:
    """Assemble activity_24h over a deterministically empty far-past window via real counters.

    Reuses the production windowed counters against a window no test ever seeds, so the sources
    succeed but legitimately count nothing. This isolates the genuine-empty -> 0 contract from
    the session-shared Prefect event store, which other modules populate around the live window.
    """
    async with get_client(sync_client=False) as client:
        logins = await count_windowed_event.fn(
            client=client,
            event_name=AccountLoggedInEvent.event_name,
            window_start=_EMPTY_WINDOW_START,
            window_end=_EMPTY_WINDOW_END,
        )
        unique_logins = await count_windowed_unique_resources.fn(
            client=client,
            event_name=AccountLoggedInEvent.event_name,
            window_start=_EMPTY_WINDOW_START,
            window_end=_EMPTY_WINDOW_END,
        )
        webhook_success, webhook_failure = await count_webhook_runs.fn(
            client=client, window_start=_EMPTY_WINDOW_START, window_end=_EMPTY_WINDOW_END
        )
    return TelemetryActivity24hData(
        logins=logins,
        unique_logins=unique_logins,
        checks_started=0,
        checks_passed=0,
        checks_failed=0,
        artifacts_created=0,
        artifacts_updated=0,
        branches_created=0,
        branches_merged=0,
        branches_deleted=0,
        webhooks_fired_success=webhook_success,
        webhooks_fired_failure=webhook_failure,
    )


async def test_gather_genuine_empty_activity_is_zero(telemetry_environment: InfrahubDatabase) -> None:
    """A window with no seeded events yields 0 on the activity counts, never null.

    The activity source is gathered over a far-past window via the real production counters, so
    the sources genuinely succeed with nothing to count. The result must be 0 (a successful
    empty), never None (which would mean the source failed) — the core of the degradation
    contract.
    """
    data = await gather_anonymous_telemetry_data.fn(activity_gatherer=_empty_window_activity_gatherer)

    # Each windowed count is a genuine empty: 0, distinguishing "succeeded with nothing to
    # count" from "source failed" (which would be None).
    assert data.activity_24h.logins == 0
    assert data.activity_24h.unique_logins == 0
    assert data.activity_24h.webhooks_fired_success == 0
    assert data.activity_24h.webhooks_fired_failure == 0


async def _boom_accounts(_db: InfrahubDatabase) -> TelemetryAccountData:
    raise RuntimeError("accounts source unavailable")


async def _boom_activity() -> TelemetryActivity24hData:
    raise RuntimeError("activity source unavailable")


async def _boom_active_branches() -> int:
    raise RuntimeError("branch source unavailable")


async def test_gather_one_source_fails_others_populated_and_stored(
    telemetry_environment: InfrahubDatabase,
) -> None:
    """One failing source nulls only its own field(s); the rest is populated and storable.

    The failing collaborator is a real coroutine that raises — the adapter pattern, not a mock.
    The orchestrator isolates it through the degradation helper, so the accounts object comes
    back fully null while every other metric (branches, corenode, the whole activity_24h
    object) is still populated, and the resulting snapshot still persists to the repository.
    """
    db = telemetry_environment

    data = await gather_anonymous_telemetry_data.fn(account_gatherer=_boom_accounts)

    # The failed source is null on both its fields.
    assert data.accounts.active is None
    assert data.accounts.groups is None

    # Every other new metric is still populated.
    assert data.branches.active is not None
    assert data.database.node_count["corenode"] is not None
    for field in _ACTIVITY_FIELDS:
        assert getattr(data.activity_24h, field) is not None, field

    # The payload is still storable end to end despite the failed source.
    snapshot = await _store_snapshot(db=db, data=data)
    repository = TelemetrySnapshotRepository(db=db)
    stored = await repository.get_list(limit=1)
    assert stored
    assert str(stored[0].uuid) == str(snapshot.uuid)


async def test_gather_activity_source_fails_only_activity_null(
    telemetry_environment: InfrahubDatabase,
) -> None:
    """A failing activity source nulls the whole activity_24h object, leaving the rest intact."""
    data = await gather_anonymous_telemetry_data.fn(activity_gatherer=_boom_activity)

    for field in _ACTIVITY_FIELDS:
        assert getattr(data.activity_24h, field) is None, field

    # Accounts and the active-branch count are unaffected.
    assert data.accounts.active is not None
    assert data.branches.active is not None
    assert data.database.node_count["corenode"] is not None


async def test_gather_branch_source_fails_only_branch_active_null(
    telemetry_environment: InfrahubDatabase,
) -> None:
    """A failing active-branch counter nulls only branches.active; branches.total is intact."""
    data = await gather_anonymous_telemetry_data.fn(active_branch_counter=_boom_active_branches)

    assert data.branches.active is None
    # branches.total is computed directly from the registry and is never nullable.
    assert isinstance(data.branches.total, int)
    assert data.accounts.active is not None
