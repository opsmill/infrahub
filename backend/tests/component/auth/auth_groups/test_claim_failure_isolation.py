from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

import pytest

from infrahub import config, lock
from infrahub.auth.auth import signin_sso_account
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreAccount, CoreAccountGroup
from infrahub.events.group_action import GroupAutoCreatedEvent, GroupAutoCreateRejectedEvent
from infrahub.lock import InfrahubLock, InfrahubLockRegistry
from tests.adapters.event import MemoryInfrahubEvent
from tests.helpers.identities import make_identity

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


class _ExplodingLock(InfrahubLock):
    """A lock whose acquisition always fails, simulating a transient distributed-lock error."""

    async def acquire(self) -> None:
        raise RuntimeError("simulated distributed lock acquisition failure")


class _PoisonLockRegistry(InfrahubLockRegistry):
    """Local-only registry that fails to acquire the auto-create lock for one designated name.

    Every other lock behaves like the local-only registry; the lock for the poison effective
    name raises on acquire so a single claim's persistence path fails deterministically.
    """

    def __init__(self, *, poison_name: str) -> None:
        super().__init__(local_only=True)
        self._poison_lock_key = f"auto-create-group:{poison_name}"

    def get(
        self,
        name: str,
        namespace: str | None = None,
        local: bool | None = None,
        in_multi: bool = False,
        metrics: bool = True,
    ) -> InfrahubLock:
        if name == self._poison_lock_key:
            return _ExplodingLock(name=name)
        return super().get(name=name, namespace=namespace, local=local, in_multi=in_multi, metrics=metrics)


@pytest.fixture
def autocreate_filter_enabled() -> Iterator[None]:
    """Enable the auto-creation filter for the duration of the test, restoring on teardown."""
    original_filter = config.SETTINGS.security.auto_create_groups_filter
    original_compiled = config.SETTINGS.security._auto_create_groups_filter_patterns

    config.SETTINGS.security.auto_create_groups_filter = r"^LDAP/group/(?P<name>.+)$"
    config.SETTINGS.security.recompile_auto_create_groups_filter_patterns()

    try:
        yield
    finally:
        config.SETTINGS.security.auto_create_groups_filter = original_filter
        config.SETTINGS.security._auto_create_groups_filter_patterns = original_compiled


@pytest.fixture
def poison_lock_for_one_group() -> Iterator[None]:
    """Swap the global lock registry for one that fails the auto-create lock of `poison-grp`."""
    original = lock.registry
    lock.registry = _PoisonLockRegistry(poison_name="poison-grp")
    try:
        yield
    finally:
        lock.registry = original


async def test_single_failing_claim_does_not_abort_login_and_emits_rejected_event(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    autocreate_filter_enabled: None,
    poison_lock_for_one_group: None,
) -> None:
    """A claim whose persistence raises is logged and skipped; the remaining claims still apply.

    The poison claim is processed first. The login completes, no group is created for the poison
    claim, the subsequent valid claim still produces its group and membership, and a
    `GroupAutoCreateRejectedEvent` is emitted for the failing claim.
    """
    recorder = MemoryInfrahubEvent()
    identity = make_identity(sub="sub-claim-failure-isolation", display_name="Pat Auto")

    auth_result = await signin_sso_account(
        db=db,
        external_identity=identity,
        sso_groups=["LDAP/group/poison-grp", "LDAP/group/good-grp"],
        event_service=recorder,
    )

    assert auth_result.token.access_token, "login must complete even though one claim failed to persist"

    poison_groups = await NodeManager.query(db=db, schema=CoreAccountGroup, filters={"name__value": "poison-grp"})
    assert poison_groups == [], "the failing claim must not have produced a group"

    good_groups = await NodeManager.query(db=db, schema=CoreAccountGroup, filters={"name__value": "good-grp"})
    assert len(good_groups) == 1, "the valid claim after the failure must still create its group"

    refreshed = await NodeManager.get_one(db=db, id=good_groups[0].id, prefetch_relationships=True)
    members = await refreshed.get_relationship(name="members").get_peers(
        db=db, branch_agnostic=True, peer_type=CoreAccount
    )
    accounts = await NodeManager.query(db=db, schema=InfrahubKind.ACCOUNT, filters={"name__value": "Pat Auto"})
    assert len(accounts) == 1
    assert accounts[0].id in members, "the account must be a member of the group from the valid claim"

    rejected_events = [event for event in recorder.events if isinstance(event, GroupAutoCreateRejectedEvent)]
    assert len(rejected_events) == 1, "exactly one rejected event must be emitted for the failing claim"
    assert rejected_events[0].rejected_claim_value == "LDAP/group/poison-grp"

    created_events = [event for event in recorder.events if isinstance(event, GroupAutoCreatedEvent)]
    assert [event.group_name for event in created_events] == ["good-grp"], (
        "only the valid claim must produce a created event"
    )
