from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub import config
from infrahub.auth.auth_groups.filter import ClaimFilter
from infrahub.auth.auth_groups.service import AutoCreatedGroupsService
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreAccount, CoreAccountGroup
from tests.adapters.event import RecordingAutoCreateEventEmitter

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

GROUP_NAME = "sso-group"


async def _assign_group_claim(db: InfrahubDatabase, account: CoreAccount) -> tuple[str, ...]:
    service = AutoCreatedGroupsService(
        db=db,
        account=account,
        provider_name="AzureAD-corp",
        max_per_login=10,
        emitter=RecordingAutoCreateEventEmitter(),
    )
    return await service.assign(
        claims=[f"LDAP/group/{GROUP_NAME}"],
        claim_filter=ClaimFilter(patterns=config.SETTINGS.security.auto_create_groups_filter_patterns),
    )


async def _members_on_branch(db: InfrahubDatabase, group_id: str, branch: Branch) -> set[str]:
    group = await NodeManager.get_one(db=db, id=group_id, kind=CoreAccountGroup, branch=branch, raise_on_error=True)
    members = await group.members.get_peers(db=db, peer_type=CoreAccount)
    return set(members)


class TestGroupMemberReads:
    @pytest.fixture(scope="class")
    async def account(self, db: InfrahubDatabase, register_core_models_schema_scope_class: SchemaBranch) -> CoreAccount:
        account = await Node.init(db=db, schema=CoreAccount)
        await account.new(db=db, name="Sam Sso", account_type="User", password="sam-password")
        await account.save(db=db)
        return account

    @pytest.fixture(scope="class")
    async def group(
        self, db: InfrahubDatabase, register_core_models_schema_scope_class: SchemaBranch
    ) -> CoreAccountGroup:
        group = await Node.init(db=db, schema=CoreAccountGroup)
        await group.new(db=db, name=GROUP_NAME)
        await group.save(db=db)
        return group

    async def test_group_members_skip_member_added_on_branch(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        account: CoreAccount,
        group: CoreAccountGroup,
        autocreate_filter_enabled: None,
    ) -> None:
        branch = await create_branch(db=db, branch_name="add-member-login")
        group_on_branch = await NodeManager.get_one(
            db=db, id=group.id, kind=CoreAccountGroup, branch=branch, raise_on_error=True
        )
        await group_on_branch.members.add(db=db, data={"id": account.id})
        await group_on_branch.members.save(db=db)

        granted = await _assign_group_claim(db=db, account=account)

        assert granted == (GROUP_NAME,)
        assert await _members_on_branch(db=db, group_id=group.id, branch=default_branch_scope_class) == {account.id}

    async def test_group_members_keep_member_removed_on_branch(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        account: CoreAccount,
        group: CoreAccountGroup,
        autocreate_filter_enabled: None,
    ) -> None:
        assert await _members_on_branch(db=db, group_id=group.id, branch=default_branch_scope_class) == {account.id}

        branch = await create_branch(db=db, branch_name="drop-member-login")
        group_on_branch = await NodeManager.get_one(
            db=db, id=group.id, kind=CoreAccountGroup, branch=branch, raise_on_error=True
        )
        await group_on_branch.members.update(db=db, data=[])
        await group_on_branch.members.save(db=db)

        granted = await _assign_group_claim(db=db, account=account)

        assert granted == (GROUP_NAME,)
        assert await _members_on_branch(db=db, group_id=group.id, branch=default_branch_scope_class) == {account.id}
        assert await _members_on_branch(db=db, group_id=group.id, branch=branch) == set()
