"""Component tests for the telemetry gather flow and payload resilience."""

import hashlib
import json
import logging
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Generator
from uuid import uuid4

import httpx
import pytest
from fast_depends import Provider
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
from infrahub.license.models import License, LicenseState, LicenseStatus
from infrahub.license.service import LicenseService
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
    AnonymousTelemetryGatherer,
    DefaultAccountGatherer,
    DefaultActiveBranchCounter,
    DefaultActivityGatherer,
    GathererInterface,
    build_anonymous_telemetry_gatherer,
    count_active_branches,
    gather_account_information,
    send_telemetry_push,
)
from infrahub.workers.dependencies import (
    build_component,
    build_http_service,
    clear_singletons,
    get_component,
    get_database,
    get_license_service,
    set_component_type,
)
from tests.adapters.cache import MemoryCache
from tests.adapters.http import MemoryHTTP
from tests.adapters.license import RecordingLicenseService
from tests.adapters.message_bus import BusSimulator
from tests.helpers.dependency_override import override_dependency

# A far-past day no test ever seeds into: proves genuine-empty -> 0 without shared server state.
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
    """Persist a telemetry payload and return the saved snapshot."""
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

    assert await count_active_branches(db=db) == 2


@pytest.fixture
async def telemetry_environment(
    db: InfrahubDatabase,
    register_core_models_schema: SchemaBranch,
    prefect_test_fixture: Generator[None, None, None],
) -> AsyncGenerator[InfrahubDatabase, None]:
    """Wire the in-memory cache and message-bus adapters and a heartbeating component.

    Overrides are restored and singletons cleared on teardown so nothing leaks between modules.
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


async def _build_gatherer(
    account_gatherer: GathererInterface[TelemetryAccountData] | None = None,
    activity_gatherer: GathererInterface[TelemetryActivity24hData] | None = None,
    active_branch_counter: GathererInterface[int] | None = None,
    license_service: LicenseService | None = None,
) -> AnonymousTelemetryGatherer:
    """Build the gatherer with real collaborators, overriding any one with an injected double."""
    database = await get_database()
    component = await get_component()
    return AnonymousTelemetryGatherer(
        database=database,
        component=component,
        account_gatherer=account_gatherer or DefaultAccountGatherer(db=database),
        activity_gatherer=activity_gatherer or DefaultActivityGatherer(),
        active_branch_counter=active_branch_counter or DefaultActiveBranchCounter(db=database),
        license_service=license_service or get_license_service(),
    )


async def test_gather_full_payload_fields_present(telemetry_environment: InfrahubDatabase) -> None:
    """A healthy gather populates every new field on the payload (presence, not exact values)."""
    gatherer = await build_anonymous_telemetry_gatherer()
    data = await gatherer.gather()

    assert isinstance(data, TelemetryData)

    assert data.accounts.active is not None
    assert data.accounts.groups is not None

    assert data.branches.active is not None

    assert "corenode" in data.database.node_count
    assert data.database.node_count["corenode"] is not None

    assert "user" in data.database.node_count
    assert data.database.node_count["user"] is not None

    # An empty window is 0, not null, so every field is populated.
    for field in _ACTIVITY_FIELDS:
        assert getattr(data.activity_24h, field) is not None, field


class EmptyWindowActivityGatherer:
    """Assemble activity_24h over a far-past window no test seeds, via the real counters.

    The sources succeed but legitimately count nothing, isolating the empty -> 0 case from the
    session-shared event store other modules populate around the live window.
    """

    async def gather(self) -> TelemetryActivity24hData:
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
    """An empty window yields 0 on the activity counts, never null (a succeeded-but-empty source)."""
    gatherer = await _build_gatherer(activity_gatherer=EmptyWindowActivityGatherer())
    data = await gatherer.gather()

    assert data.activity_24h.logins == 0
    assert data.activity_24h.unique_logins == 0
    assert data.activity_24h.webhooks_fired_success == 0
    assert data.activity_24h.webhooks_fired_failure == 0


class BoomAccountGatherer:
    async def gather(self) -> TelemetryAccountData:
        raise RuntimeError("accounts source unavailable")


class BoomActivityGatherer:
    async def gather(self) -> TelemetryActivity24hData:
        raise RuntimeError("activity source unavailable")


class BoomActiveBranchCounter:
    async def gather(self) -> int:
        raise RuntimeError("branch source unavailable")


async def test_gather_one_source_fails_others_populated_and_stored(
    telemetry_environment: InfrahubDatabase,
) -> None:
    """One failing source nulls only its own fields; the rest is populated and still storable."""
    db = telemetry_environment

    gatherer = await _build_gatherer(account_gatherer=BoomAccountGatherer())
    data = await gatherer.gather()

    assert data.accounts.active is None
    assert data.accounts.groups is None

    assert data.branches.active is not None
    assert data.database.node_count["corenode"] is not None
    for field in _ACTIVITY_FIELDS:
        assert getattr(data.activity_24h, field) is not None, field

    # The payload still persists end to end despite the failed source.
    snapshot = await _store_snapshot(db=db, data=data)
    repository = TelemetrySnapshotRepository(db=db)
    stored = await repository.get_list(limit=1)
    assert stored
    assert str(stored[0].uuid) == str(snapshot.uuid)


async def test_gather_activity_source_fails_only_activity_null(
    telemetry_environment: InfrahubDatabase,
) -> None:
    """A failing activity source nulls the whole activity_24h object, leaving the rest intact."""
    gatherer = await _build_gatherer(activity_gatherer=BoomActivityGatherer())
    data = await gatherer.gather()

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
    gatherer = await _build_gatherer(active_branch_counter=BoomActiveBranchCounter())
    data = await gatherer.gather()

    assert data.branches.active is None
    # branches.total is computed directly from the registry and is never nullable.
    assert isinstance(data.branches.total, int)
    assert data.accounts.active is not None


TELEMETRY_ENDPOINT = "https://telemetry.example.com/snapshots"
LICENSE_CLAIMS: dict[str, Any] = {
    "license_id": "lic-0042",
    "customer_name": "Example Networks",
    "license_type": "commercial",
    "product_tier": "enterprise",
    "support_tier": "premium",
    "starts_at": datetime(2026, 1, 1, tzinfo=UTC),
    "ends_at": datetime(2027, 1, 1, tzinfo=UTC),
    "issued_at": datetime(2025, 12, 15, tzinfo=UTC),
    "issuer": "opsmill-test",
}
VALID = LicenseStatus(state=LicenseState.VALID, license=License(**LICENSE_CLAIMS), days_remaining=200)
STORED_LICENSE_BLOCK = {
    "state": "valid",
    "license_id": "lic-0042",
    "license_type": "commercial",
    "product_tier": "enterprise",
    "support_tier": "premium",
    "starts_at": "2026-01-01T00:00:00Z",
    "ends_at": "2027-01-01T00:00:00Z",
    "issuer": "opsmill-test",
}


@pytest.fixture
def telemetry_sent(monkeypatch: pytest.MonkeyPatch, dependency_provider: Provider) -> Generator[None, None, None]:
    """Send telemetry to an in-memory endpoint that accepts every snapshot."""
    http = MemoryHTTP()
    http.add_post_response(
        url=TELEMETRY_ENDPOINT,
        response=httpx.Response(status_code=200, request=httpx.Request(method="POST", url=TELEMETRY_ENDPOINT)),
    )
    monkeypatch.setattr(config.SETTINGS.main, "telemetry_optout", False)
    monkeypatch.setattr(config.SETTINGS.main, "telemetry_endpoint", TELEMETRY_ENDPOINT)
    with override_dependency(build_http_service, lambda: http, dependency_provider=dependency_provider):
        yield


@pytest.fixture
def telemetry_opted_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config.SETTINGS.main, "telemetry_optout", True)


async def _run_telemetry_flow(db: InfrahubDatabase) -> TelemetrySnapshot:
    """Run the daily telemetry flow and return the one snapshot it stored."""
    repository = TelemetrySnapshotRepository(db=db)
    stored_before = await repository.count()

    await send_telemetry_push()

    assert await repository.count() == stored_before + 1
    newest = await repository.get_list(limit=1)
    return newest[0]


async def test_stored_snapshot_carries_the_license_block_without_the_customer_name(
    telemetry_environment: InfrahubDatabase,
    telemetry_sent: None,
    use_license_service: Callable[[LicenseService], None],
) -> None:
    use_license_service(RecordingLicenseService(status=VALID))

    stored = await _run_telemetry_flow(db=telemetry_environment)

    assert stored.remote_send_status == RemoteSendStatus.SENT
    assert stored.payload_format == TELEMETRY_VERSION
    assert stored.data["license"] == STORED_LICENSE_BLOCK
    assert "Example Networks" not in json.dumps(stored.data)


async def test_stored_snapshot_has_a_null_license_when_no_license_is_required(
    telemetry_environment: InfrahubDatabase, telemetry_sent: None
) -> None:
    stored = await _run_telemetry_flow(db=telemetry_environment)

    assert stored.remote_send_status == RemoteSendStatus.SENT
    assert stored.data["license"] is None


async def test_stored_snapshot_carries_the_license_block_when_sending_is_turned_off(
    telemetry_environment: InfrahubDatabase,
    telemetry_opted_out: None,
    use_license_service: Callable[[LicenseService], None],
) -> None:
    use_license_service(RecordingLicenseService(status=VALID))

    stored = await _run_telemetry_flow(db=telemetry_environment)

    assert stored.remote_send_status == RemoteSendStatus.SKIPPED
    assert stored.data["license"] == STORED_LICENSE_BLOCK


LICENSE_KEY = f"leak-sentinel-{uuid4()}"


@dataclass
class LicenseKeyLeakCase:
    name: str
    replacement_status: LicenseStatus | None
    """Status of a service swapped in for the community default, which stays in place when None."""

    stored_license_block: dict[str, Any] | None


LICENSE_KEY_LEAK_CASES: list[LicenseKeyLeakCase] = [
    LicenseKeyLeakCase(name="community_default", replacement_status=None, stored_license_block=None),
    LicenseKeyLeakCase(
        name="replaced_service_with_a_valid_license",
        replacement_status=VALID,
        stored_license_block=STORED_LICENSE_BLOCK,
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in LICENSE_KEY_LEAK_CASES])
async def test_stored_snapshot_never_carries_the_license_key(
    telemetry_environment: InfrahubDatabase,
    telemetry_opted_out: None,
    use_license_service: Callable[[LicenseService], None],
    monkeypatch: pytest.MonkeyPatch,
    test_case: LicenseKeyLeakCase,
) -> None:
    monkeypatch.setattr(config.SETTINGS.license, "key", LICENSE_KEY)
    if test_case.replacement_status is not None:
        use_license_service(RecordingLicenseService(status=test_case.replacement_status))

    stored = await _run_telemetry_flow(db=telemetry_environment)

    assert stored.data["license"] == test_case.stored_license_block
    assert LICENSE_KEY not in stored.model_dump_json()


async def test_gather_license_block_that_cannot_be_built_is_null_and_logged(
    telemetry_environment: InfrahubDatabase, caplog: pytest.LogCaptureFixture
) -> None:
    """A license the block cannot hold nulls only the license field and leaves the rest of the payload intact."""
    malformed = License(**LICENSE_CLAIMS)
    # The constructor rejects a number in a text field, so the defect is planted after construction.
    vars(malformed)["product_tier"] = 3
    gatherer = await _build_gatherer(
        license_service=RecordingLicenseService(
            status=LicenseStatus(state=LicenseState.VALID, license=malformed, days_remaining=200)
        )
    )

    with caplog.at_level(logging.WARNING, logger="infrahub.tasks"):
        data = await gatherer.gather()

    assert data.license is None
    assert data.accounts.active is not None
    assert data.branches.active is not None
    license_warnings = [
        record.getMessage()
        for record in caplog.records
        if record.name == "infrahub.tasks" and "TelemetryLicenseData" in record.getMessage()
    ]
    assert len(license_warnings) == 1
    assert license_warnings[0].startswith("Telemetry metric collection failed; reporting null for this field: ")
    assert "product_tier" in license_warnings[0]
