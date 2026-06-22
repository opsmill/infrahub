from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub import config
from infrahub.auth.auth_groups.filter import ClaimFilter
from infrahub.auth.auth_groups.service import AutoCreatedGroupsService
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreAccount, CoreAccountGroup
from tests.adapters.event import RecordingAutoCreateEventEmitter

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

CONTESTED_NAME = "ops-admins"


class _LookupMissesOnceNodeManager(NodeManager):
    """Returns no match on the first lookup of the contested name, then delegates.

    Forces the create-race branch of find-or-create deterministically: the first lookup misses,
    creation raises on the row that already exists, and the re-lookup finds it. Every other call
    (the re-lookup, membership reads) goes to the real manager.
    """

    first_lookup_done = False

    @classmethod
    async def query(cls, *args: Any, **kwargs: Any) -> Any:
        filters = kwargs.get("filters")
        if filters and filters.get("name__value") == CONTESTED_NAME and not cls.first_lookup_done:
            cls.first_lookup_done = True
            return []
        return await super().query(*args, **kwargs)


async def test_create_race_reuses_winning_group_without_emitting_a_second_event(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    autocreate_filter_enabled: None,
) -> None:
    """A group created between this login's existence check and its create is reused, not duplicated.

    Reproduces the window where a competing creation of the same name (a concurrent SSO login or a
    GraphQL/API mutation) commits after the initial, unlocked existence check but before this
    login's own create. The check misses, the create then raises a uniqueness violation against the
    now-existing group, and it is reused: no duplicate row, no second creation event, and the
    account is added to the existing group.
    """
    winner = await Node.init(db=db, schema=CoreAccountGroup)
    await winner.new(db=db, name=CONTESTED_NAME, origin="OktaProd")
    await winner.save(db=db)

    account = await Node.init(db=db, schema=CoreAccount)
    await account.new(db=db, name="Pat Auto", account_type="User", password="pat-password")
    await account.save(db=db)

    _LookupMissesOnceNodeManager.first_lookup_done = False
    emitter = RecordingAutoCreateEventEmitter()
    service = AutoCreatedGroupsService(
        db=db,
        account=account,
        provider_name="AzureAD-corp",
        max_per_login=10,
        emitter=emitter,
        node_manager=_LookupMissesOnceNodeManager,
    )

    granted = await service.assign(
        claims=[f"LDAP/group/{CONTESTED_NAME}"],
        claim_filter=ClaimFilter(patterns=config.SETTINGS.security.auto_create_groups_filter_patterns),
    )

    assert granted == (CONTESTED_NAME,), "the contested claim must still grant membership via reuse"

    groups = await NodeManager.query(db=db, schema=CoreAccountGroup, filters={"name__value": CONTESTED_NAME})
    assert len(groups) == 1, "the create race must not produce a duplicate group"
    assert groups[0].id == winner.id, "the existing group must be reused, not replaced"
    assert groups[0].origin.value == "OktaProd", "reuse must not overwrite the winning group's origin"

    assert emitter.created_groups == [], "reuse on a create race must not emit a created event"

    refreshed = await NodeManager.get_one(db=db, id=winner.id, prefetch_relationships=True)
    members = await refreshed.get_relationship(name="members").get_peers(
        db=db, branch_agnostic=True, peer_type=CoreAccount
    )
    assert account.id in members, "the account must be added to the reused group"
