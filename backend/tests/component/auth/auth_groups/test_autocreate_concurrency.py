from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from infrahub import lock
from infrahub.auth.auth import signin_sso_account
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreAccount, CoreAccountGroup
from infrahub.events.group_action import GroupAutoCreatedEvent
from tests.adapters.event import MemoryInfrahubEvent
from tests.helpers.identities import make_identity

if TYPE_CHECKING:
    from collections.abc import Iterator

    from infrahub.auth.auth import ExternalIdentity
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


@pytest.fixture(autouse=True)
def _local_lock_registry() -> Iterator[None]:
    """Use a local (in-process) lock registry so concurrent tasks serialize without Redis."""
    original = lock.registry
    lock.initialize_lock(local_only=True)
    try:
        yield
    finally:
        lock.registry = original


class TestConcurrentFirstLoginSameClaim:
    """Two first-logins for the same brand-new claim must produce exactly one group.

    This pins down the concurrency contract of the find-or-create path: the per-name lock plus
    the in-lock re-lookup guarantee that simultaneous first-logins converge on a single
    `CoreAccountGroup` — both logins succeed, no duplicate row, and exactly one creation event.
    """

    async def test_concurrent_logins_create_single_group_and_single_event(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        autocreate_filter_enabled: None,
    ) -> None:
        recorder = MemoryInfrahubEvent()
        identity_a = make_identity(
            sub="sub-concurrent-a", provider_name="AzureAD-corp", display_name="Concurrent UserA"
        )
        identity_b = make_identity(
            sub="sub-concurrent-b", provider_name="AzureAD-corp", display_name="Concurrent UserB"
        )

        async def login(identity: ExternalIdentity) -> None:
            async with db.start_session() as session:
                await signin_sso_account(
                    db=session,
                    external_identity=identity,
                    sso_groups=["LDAP/group/concurrent-team"],
                    event_service=recorder,
                )

        results = await asyncio.gather(login(identity_a), login(identity_b), return_exceptions=True)

        errors = [r for r in results if isinstance(r, Exception)]
        assert errors == [], f"both concurrent first-logins must succeed, got: {errors}"

        groups = await NodeManager.query(db=db, schema=CoreAccountGroup, filters={"name__value": "concurrent-team"})
        assert len(groups) == 1, "concurrent first-logins must produce exactly one group, not a duplicate"
        assert groups[0].origin.value == "AzureAD-corp"

        refreshed = await NodeManager.get_one(db=db, id=groups[0].id, prefetch_relationships=True)
        members = await refreshed.get_relationship(name="members").get_peers(
            db=db, branch_agnostic=True, peer_type=CoreAccount
        )
        accounts = await NodeManager.query(
            db=db, schema=InfrahubKind.ACCOUNT, filters={"name__values": ["Concurrent UserA", "Concurrent UserB"]}
        )
        assert len(accounts) == 2, "both accounts must have been created"
        for account in accounts:
            assert account.id in members, "both users must be members of the single group"

        created_events = [event for event in recorder.events if isinstance(event, GroupAutoCreatedEvent)]
        assert len(created_events) == 1, (
            f"exactly one GroupAutoCreatedEvent must be emitted across concurrent first-logins, "
            f"got {len(created_events)}"
        )
        assert str(created_events[0].group_id) == groups[0].id, "the event must reference the surviving group"
