from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterator

import pytest

from infrahub import config
from infrahub.auth.auth_groups.emitter import AutoCreateEventEmitter
from infrahub.auth.auth_groups.filter import ClaimFilter
from infrahub.auth.auth_groups.service import AutoCreatedGroupsService
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreAccount, CoreAccountGroup

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

POISON_NAME = "poison-grp"


class _FailLookupNodeManager(NodeManager):
    """NodeManager that raises while looking up one designated name; delegates everything else.

    Simulates a transient failure isolated to a single claim, independent of how creation is
    locked or persisted.
    """

    @classmethod
    async def query(cls, *args: Any, **kwargs: Any) -> Any:
        filters = kwargs.get("filters")
        if filters and filters.get("name__value") == POISON_NAME:
            raise RuntimeError("simulated lookup failure for one claim")
        return await super().query(*args, **kwargs)


class _RecordingEmitter(AutoCreateEventEmitter):
    """Adapter emitter that records the audit events emitted during one assignment."""

    def __init__(self) -> None:
        self.created_groups: list[str] = []
        self.rejected_claims: list[str] = []
        self.cap_values: list[int] = []

    async def created(self, *, group: CoreAccountGroup, source_pattern: str) -> None:
        self.created_groups.append(group.name.value)

    async def claim_rejected(self, *, claim: str) -> None:
        self.rejected_claims.append(claim)

    async def cap_breached(self, *, cap_value: int, dropped_claims: list[str]) -> None:
        self.cap_values.append(cap_value)


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


async def test_single_failing_claim_does_not_abort_assignment_and_emits_rejected_event(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    autocreate_filter_enabled: None,
) -> None:
    """A claim whose processing raises is logged and skipped; the remaining claims still apply.

    The poison claim is processed first. Its lookup raises, the assignment continues, the
    subsequent valid claim still produces its group and membership, and a rejected event is
    recorded for the failing claim only.
    """
    account = await Node.init(db=db, schema=CoreAccount)
    await account.new(db=db, name="Pat Auto", account_type="User", password="pat-password")
    await account.save(db=db)

    emitter = _RecordingEmitter()
    service = AutoCreatedGroupsService(
        db=db,
        account=account,
        provider_name="AzureAD-corp",
        max_per_login=10,
        emitter=emitter,
        node_manager=_FailLookupNodeManager,
    )

    granted = await service.assign(
        claims=["LDAP/group/poison-grp", "LDAP/group/good-grp"],
        claim_filter=ClaimFilter(patterns=config.SETTINGS.security.auto_create_groups_filter_patterns),
    )

    assert granted == ("good-grp",), "the valid claim must still be granted after the failing one"

    poison_groups = await NodeManager.query(db=db, schema=CoreAccountGroup, filters={"name__value": "poison-grp"})
    assert poison_groups == [], "the failing claim must not have produced a group"

    good_groups = await NodeManager.query(db=db, schema=CoreAccountGroup, filters={"name__value": "good-grp"})
    assert len(good_groups) == 1, "the valid claim after the failure must still create its group"

    refreshed = await NodeManager.get_one(db=db, id=good_groups[0].id, prefetch_relationships=True)
    members = await refreshed.get_relationship(name="members").get_peers(
        db=db, branch_agnostic=True, peer_type=CoreAccount
    )
    assert account.id in members, "the account must be a member of the group from the valid claim"

    assert emitter.rejected_claims == ["LDAP/group/poison-grp"], "only the failing claim must be rejected"
    assert emitter.created_groups == ["good-grp"], "only the valid claim must produce a created event"
