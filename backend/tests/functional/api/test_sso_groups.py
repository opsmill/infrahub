from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from infrahub import config
from infrahub.auth import signin_sso_account
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreAccountGroup

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class TestSSOAutoGroupCreation:
    @pytest.fixture
    async def existing_group(self, db: InfrahubDatabase) -> Node:
        """Create an existing group for testing."""
        group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
        await group.new(db=db, name="ExistingGroup")
        await group.save(db=db)
        return group

    async def test_auto_create_groups_when_enabled(self, db: InfrahubDatabase, existing_group: Node) -> None:
        """When sso_generate_groups is enabled, missing groups should be auto-created."""
        sso_groups = ["ExistingGroup", "NewGroup1", "NewGroup2"]

        with patch.object(config.SETTINGS.security, "sso_generate_groups", True):
            await signin_sso_account(db=db, account_name="testuser", sso_groups=sso_groups)

        # Verify all groups exist
        all_groups = await NodeManager.query(db=db, schema=CoreAccountGroup)
        group_names = {g.name.value for g in all_groups}

        assert "ExistingGroup" in group_names
        assert "NewGroup1" in group_names
        assert "NewGroup2" in group_names

    async def test_no_auto_create_groups_when_disabled(self, db: InfrahubDatabase, existing_group: Node) -> None:
        """When sso_generate_groups is disabled (default), missing groups should NOT be created."""
        sso_groups = ["ExistingGroup", "MissingGroup"]

        with patch.object(config.SETTINGS.security, "sso_generate_groups", False):
            await signin_sso_account(db=db, account_name="testuser2", sso_groups=sso_groups)

        # Verify only existing group exists
        all_groups = await NodeManager.query(db=db, schema=CoreAccountGroup)
        group_names = {g.name.value for g in all_groups}

        assert "ExistingGroup" in group_names
        assert "MissingGroup" not in group_names

    async def test_user_added_to_auto_created_groups(self, db: InfrahubDatabase, existing_group: Node) -> None:
        """User should be added to both existing and auto-created groups."""
        sso_groups = ["ExistingGroup", "AutoCreatedGroup"]

        with patch.object(config.SETTINGS.security, "sso_generate_groups", True):
            await signin_sso_account(db=db, account_name="testuser3", sso_groups=sso_groups)

        # Verify user is in both groups
        all_groups = await NodeManager.query(
            db=db,
            schema=CoreAccountGroup,
            filters={"name__values": sso_groups},
            prefetch_relationships=True,
        )

        for group in all_groups:
            members = await group.members.get_peers(db=db, branch_agnostic=True)
            member_names = [m.name.value for m in members.values()]
            assert "testuser3" in member_names, f"User not found in group {group.name.value}"

    async def test_auto_created_groups_have_no_roles(self, db: InfrahubDatabase, existing_group: Node) -> None:
        """Auto-created groups should have no roles assigned."""
        sso_groups = ["GroupWithNoRoles"]

        with patch.object(config.SETTINGS.security, "sso_generate_groups", True):
            await signin_sso_account(db=db, account_name="testuser4", sso_groups=sso_groups)

        # Verify the auto-created group has no roles
        groups = await NodeManager.query(
            db=db,
            schema=CoreAccountGroup,
            filters={"name__value": "GroupWithNoRoles"},
            prefetch_relationships=True,
        )

        assert len(groups) == 1
        roles = await groups[0].roles.get_peers(db=db, branch_agnostic=True)
        assert len(roles) == 0
