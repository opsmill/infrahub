import uuid
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import ANY, AsyncMock, Mock, PropertyMock, patch

import pytest
from pydantic import ValidationError

from infrahub import config
from infrahub.auth import _extract_effective_sso_group_names, signin_sso_account
from infrahub.config import SecuritySettings
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreAccountGroup
from infrahub.core.registry import registry
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase


@pytest.fixture
async def existing_group(db: InfrahubDatabase, register_core_models_schema: SchemaBranch) -> Node:
    group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group.new(db=db, name="existing-group")
    await group.save(db=db)
    return group


class _DummyMembers:
    def __init__(self) -> None:
        self.add = AsyncMock()
        self.save = AsyncMock()

    async def get_peers(
        self, db: InfrahubDatabase, branch_agnostic: bool = True, peer_type: object = None
    ) -> dict[str, object]:
        return {}


class _DummyGroup:
    def __init__(self, name: str) -> None:
        self.name = SimpleNamespace(value=name)
        self.members = _DummyMembers()


class TestExtractEffectiveSSOGroupNames:
    def test_optional_first_capture_group_falls_back_to_original_name(self) -> None:
        group_names = _extract_effective_sso_group_names(["bar"], r"^(foo)?(bar)$")

        assert group_names == {"bar"}


class TestSSOGenerateGroupsCreationPath:
    async def test_signin_uses_safe_create_path_for_missing_groups(self) -> None:
        fake_account = SimpleNamespace(id="account-1")
        fake_branch = SimpleNamespace(name="main")
        fake_group = _DummyGroup(name="new-group")
        fake_new_group = AsyncMock()
        fake_db = SimpleNamespace(schema=SimpleNamespace(get_node_schema=Mock(return_value=InfrahubKind.ACCOUNTGROUP)))

        query_calls = 0

        async def query_side_effect(*args: Any, **kwargs: Any) -> list[_DummyGroup]:
            nonlocal query_calls
            query_calls += 1
            if query_calls <= 2:
                return []
            return [fake_group]

        with (
            patch("infrahub.auth.NodeManager.get_one_by_default_filter", AsyncMock(return_value=fake_account)),
            patch("infrahub.auth.NodeManager.query", side_effect=query_side_effect),
            patch("infrahub.auth.Node.init", AsyncMock(return_value=fake_new_group)),
            patch.object(type(registry), "default_branch", new_callable=PropertyMock, return_value="main"),
            patch("infrahub.auth.registry.get_branch", AsyncMock(return_value=fake_branch)),
            patch("infrahub.auth.create_node", AsyncMock(return_value=fake_group), create=True) as safe_create,
            patch("infrahub.auth.create_db_refresh_token", AsyncMock(return_value=uuid.uuid4())),
            patch("infrahub.auth.generate_access_token", return_value="access-token"),
            patch("infrahub.auth.generate_refresh_token", return_value="refresh-token"),
            patch.object(config.SETTINGS.security, "sso_generate_groups", True),
            patch.object(config.SETTINGS.security, "sso_generate_groups_filter", None),
        ):
            await signin_sso_account(
                db=cast("InfrahubDatabase", fake_db), account_name="test-user", sso_groups=["new-group"]
            )

        safe_create.assert_awaited_once_with(data={"name": "new-group"}, db=fake_db, branch=ANY, schema=ANY)
        assert fake_db.schema.get_node_schema.call_count == 1


class TestSSOGenerateGroups:
    async def test_groups_not_created_when_disabled(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        existing_group: Node,
    ) -> None:
        """Verify that groups are NOT created when sso_generate_groups is disabled (default)"""
        with patch.object(config.SETTINGS.security, "sso_generate_groups", False):
            await signin_sso_account(
                db=db, account_name="test-user", sso_groups=["existing-group", "new-group-1", "new-group-2"]
            )

            groups = await NodeManager.query(db=db, schema=CoreAccountGroup)
            group_names = {g.name.value for g in groups}

            assert "existing-group" in group_names
            assert "new-group-1" not in group_names
            assert "new-group-2" not in group_names

    async def test_groups_created_when_enabled(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        existing_group: Node,
    ) -> None:
        """Verify that missing groups are created when sso_generate_groups is enabled"""
        with patch.object(config.SETTINGS.security, "sso_generate_groups", True):
            await signin_sso_account(
                db=db, account_name="test-user-2", sso_groups=["existing-group", "auto-group-1", "auto-group-2"]
            )

            groups = await NodeManager.query(db=db, schema=CoreAccountGroup)
            group_names = {g.name.value for g in groups}

            assert "existing-group" in group_names
            assert "auto-group-1" in group_names
            assert "auto-group-2" in group_names


class TestSSOGenerateGroupsFilter:
    async def test_filter_allows_matching_groups(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        existing_group: Node,
    ) -> None:
        """Verify that only groups matching the filter pattern are created"""
        with (
            patch.object(config.SETTINGS.security, "sso_generate_groups", True),
            patch.object(config.SETTINGS.security, "sso_generate_groups_filter", r"^team-.*"),
        ):
            await signin_sso_account(
                db=db,
                account_name="test-user-3",
                sso_groups=["existing-group", "team-alpha", "team-beta", "other-group"],
            )

            groups = await NodeManager.query(db=db, schema=CoreAccountGroup)
            group_names = {g.name.value for g in groups}

            assert "existing-group" in group_names
            assert "team-alpha" in group_names
            assert "team-beta" in group_names
            assert "other-group" not in group_names

    async def test_no_filter_allows_all_groups(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        existing_group: Node,
    ) -> None:
        """Verify that all groups are created when filter is not set"""
        with (
            patch.object(config.SETTINGS.security, "sso_generate_groups", True),
            patch.object(config.SETTINGS.security, "sso_generate_groups_filter", None),
        ):
            await signin_sso_account(
                db=db,
                account_name="test-user-4",
                sso_groups=["existing-group", "any-group-1", "any-group-2", "random-group"],
            )

            groups = await NodeManager.query(db=db, schema=CoreAccountGroup)
            group_names = {g.name.value for g in groups}

            assert "existing-group" in group_names
            assert "any-group-1" in group_names
            assert "any-group-2" in group_names
            assert "random-group" in group_names

    async def test_filter_with_complex_pattern(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        existing_group: Node,
    ) -> None:
        """Verify that complex regex patterns work correctly"""
        with (
            patch.object(config.SETTINGS.security, "sso_generate_groups", True),
            patch.object(config.SETTINGS.security, "sso_generate_groups_filter", r"^(?:dev|prod)-.*-team$"),
        ):
            await signin_sso_account(
                db=db,
                account_name="test-user-5",
                sso_groups=["existing-group", "dev-api-team", "prod-web-team", "staging-api-team", "dev-frontend"],
            )

            groups = await NodeManager.query(db=db, schema=CoreAccountGroup)
            group_names = {g.name.value for g in groups}

            assert "existing-group" in group_names
            assert "dev-api-team" in group_names
            assert "prod-web-team" in group_names
            assert "staging-api-team" not in group_names
            assert "dev-frontend" not in group_names


class TestSSOGenerateGroupsFilterValidation:
    def test_invalid_regex_pattern_raises_error(self) -> None:
        """Verify that invalid regex patterns raise a validation error"""
        with pytest.raises(ValidationError) as exc_info:
            SecuritySettings(sso_generate_groups_filter="[invalid(regex")

        assert "Invalid regex pattern" in str(exc_info.value)

    def test_valid_regex_pattern_accepted(self) -> None:
        """Verify that valid regex patterns are accepted"""
        settings = SecuritySettings(sso_generate_groups_filter=r"^team-.*")
        assert settings.sso_generate_groups_filter == r"^team-.*"

    def test_valid_regex_pattern_list_accepted(self) -> None:
        """Verify that valid regex pattern lists are accepted"""
        patterns = [r"^team-.*", r"ldap/groups/(\w+)"]
        settings = SecuritySettings(sso_generate_groups_filter=patterns)
        assert settings.sso_generate_groups_filter == patterns

    def test_none_filter_accepted(self) -> None:
        """Verify that None filter is accepted"""
        settings = SecuritySettings(sso_generate_groups_filter=None)
        assert settings.sso_generate_groups_filter is None

    def test_invalid_regex_pattern_in_list_raises_error(self) -> None:
        """Verify that invalid regex in list raises a validation error"""
        with pytest.raises(ValidationError) as exc_info:
            SecuritySettings(sso_generate_groups_filter=[r"^team-.*", "[invalid(regex"])

        assert "Invalid regex pattern" in str(exc_info.value)


class TestSSOGenerateGroupsFilterCaptureGroup:
    async def test_filter_does_not_duplicate_existing_extracted_group(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        existing_group: Node,
    ) -> None:
        """Verify that extracted names do not create duplicates when group already exists"""
        preexisting_group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
        await preexisting_group.new(db=db, name="network_automation")
        await preexisting_group.save(db=db)

        with (
            patch.object(config.SETTINGS.security, "sso_generate_groups", True),
            patch.object(config.SETTINGS.security, "sso_generate_groups_filter", r"ldap/groups/(\w+)"),
        ):
            await signin_sso_account(
                db=db,
                account_name="test-user-existing-transformed",
                sso_groups=["ldap/groups/network_automation"],
            )

            groups = await NodeManager.query(db=db, schema=CoreAccountGroup)
            group_names = [g.name.value for g in groups]

            assert group_names.count("network_automation") == 1
            assert "ldap/groups/network_automation" not in group_names

    async def test_filter_extracts_group_name_from_capture_group(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        existing_group: Node,
    ) -> None:
        """Verify that the first capture group is used as the group name"""
        with (
            patch.object(config.SETTINGS.security, "sso_generate_groups", True),
            patch.object(config.SETTINGS.security, "sso_generate_groups_filter", r"ldap/groups/(\w+)"),
        ):
            await signin_sso_account(
                db=db,
                account_name="test-user-capture",
                sso_groups=["ldap/groups/network_automation", "ldap/groups/security_team"],
            )

            groups = await NodeManager.query(db=db, schema=CoreAccountGroup)
            group_names = {g.name.value for g in groups}

            assert "network_automation" in group_names
            assert "security_team" in group_names
            assert "ldap/groups/network_automation" not in group_names
            assert "ldap/groups/security_team" not in group_names

    async def test_filter_without_capture_group_uses_original_name(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        existing_group: Node,
    ) -> None:
        """Verify that when pattern has no capture group, the original name is used"""
        with (
            patch.object(config.SETTINGS.security, "sso_generate_groups", True),
            patch.object(config.SETTINGS.security, "sso_generate_groups_filter", r"^team-.*"),
        ):
            await signin_sso_account(
                db=db,
                account_name="test-user-no-capture",
                sso_groups=["team-alpha", "team-beta"],
            )

            groups = await NodeManager.query(db=db, schema=CoreAccountGroup)
            group_names = {g.name.value for g in groups}

            assert "team-alpha" in group_names
            assert "team-beta" in group_names

    async def test_filter_deduplicates_extracted_names(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        existing_group: Node,
    ) -> None:
        """Verify that duplicate extracted names only create one group"""
        with (
            patch.object(config.SETTINGS.security, "sso_generate_groups", True),
            patch.object(config.SETTINGS.security, "sso_generate_groups_filter", r".*/(\w+)$"),
        ):
            await signin_sso_account(
                db=db,
                account_name="test-user-dedup",
                sso_groups=["ldap/groups/admins", "azure/groups/admins", "okta/groups/admins"],
            )

            groups = await NodeManager.query(db=db, schema=CoreAccountGroup)
            group_names = [g.name.value for g in groups]

            assert group_names.count("admins") == 1

    async def test_filter_skips_non_matching_groups(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        existing_group: Node,
    ) -> None:
        """Verify that groups not matching the pattern are skipped"""
        with (
            patch.object(config.SETTINGS.security, "sso_generate_groups", True),
            patch.object(config.SETTINGS.security, "sso_generate_groups_filter", r"ldap/groups/(\w+)"),
        ):
            await signin_sso_account(
                db=db,
                account_name="test-user-skip",
                sso_groups=["ldap/groups/network", "azure/groups/other", "random-group"],
            )

            groups = await NodeManager.query(db=db, schema=CoreAccountGroup)
            group_names = {g.name.value for g in groups}

            assert "network" in group_names
            assert "other" not in group_names
            assert "azure/groups/other" not in group_names
            assert "random-group" not in group_names
