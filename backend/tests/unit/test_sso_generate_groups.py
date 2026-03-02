import pytest

from infrahub import config
from infrahub.auth import signin_sso_account
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreAccountGroup
from infrahub.database import InfrahubDatabase


@pytest.fixture
async def existing_group(db: InfrahubDatabase, register_core_models_schema) -> Node:
    group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group.new(db=db, name="existing-group")
    await group.save(db=db)
    return group


class TestSSOGenerateGroups:
    async def test_groups_not_created_when_disabled(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema, existing_group
    ):
        """Verify that groups are NOT created when sso_generate_groups is disabled (default)"""
        original_value = config.SETTINGS.security.sso_generate_groups
        config.SETTINGS.security.sso_generate_groups = False

        try:
            await signin_sso_account(
                db=db, account_name="test-user", sso_groups=["existing-group", "new-group-1", "new-group-2"]
            )

            groups = await NodeManager.query(db=db, schema=CoreAccountGroup)
            group_names = {g.name.value for g in groups}

            assert "existing-group" in group_names
            assert "new-group-1" not in group_names
            assert "new-group-2" not in group_names
        finally:
            config.SETTINGS.security.sso_generate_groups = original_value

    async def test_groups_created_when_enabled(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema, existing_group
    ):
        """Verify that missing groups are created when sso_generate_groups is enabled"""
        original_value = config.SETTINGS.security.sso_generate_groups
        config.SETTINGS.security.sso_generate_groups = True

        try:
            await signin_sso_account(
                db=db, account_name="test-user-2", sso_groups=["existing-group", "auto-group-1", "auto-group-2"]
            )

            groups = await NodeManager.query(db=db, schema=CoreAccountGroup)
            group_names = {g.name.value for g in groups}

            assert "existing-group" in group_names
            assert "auto-group-1" in group_names
            assert "auto-group-2" in group_names
        finally:
            config.SETTINGS.security.sso_generate_groups = original_value


class TestSSOGenerateGroupsFilter:
    async def test_filter_allows_matching_groups(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema, existing_group
    ):
        """Verify that only groups matching the filter pattern are created"""
        original_generate = config.SETTINGS.security.sso_generate_groups
        original_filter = config.SETTINGS.security.sso_generate_groups_filter
        config.SETTINGS.security.sso_generate_groups = True
        config.SETTINGS.security.sso_generate_groups_filter = r"^team-.*"

        try:
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
        finally:
            config.SETTINGS.security.sso_generate_groups = original_generate
            config.SETTINGS.security.sso_generate_groups_filter = original_filter

    async def test_no_filter_allows_all_groups(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema, existing_group
    ):
        """Verify that all groups are created when filter is not set"""
        original_generate = config.SETTINGS.security.sso_generate_groups
        original_filter = config.SETTINGS.security.sso_generate_groups_filter
        config.SETTINGS.security.sso_generate_groups = True
        config.SETTINGS.security.sso_generate_groups_filter = None

        try:
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
        finally:
            config.SETTINGS.security.sso_generate_groups = original_generate
            config.SETTINGS.security.sso_generate_groups_filter = original_filter

    async def test_filter_with_complex_pattern(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema, existing_group
    ):
        """Verify that complex regex patterns work correctly"""
        original_generate = config.SETTINGS.security.sso_generate_groups
        original_filter = config.SETTINGS.security.sso_generate_groups_filter
        config.SETTINGS.security.sso_generate_groups = True
        config.SETTINGS.security.sso_generate_groups_filter = r"^(dev|prod)-.*-team$"

        try:
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
        finally:
            config.SETTINGS.security.sso_generate_groups = original_generate
            config.SETTINGS.security.sso_generate_groups_filter = original_filter


class TestSSOGenerateGroupsFilterValidation:
    def test_invalid_regex_pattern_raises_error(self):
        """Verify that invalid regex patterns raise a validation error"""
        from pydantic import ValidationError

        from infrahub.config import SecuritySettings

        with pytest.raises(ValidationError) as exc_info:
            SecuritySettings(sso_generate_groups_filter="[invalid(regex")

        assert "Invalid regex pattern" in str(exc_info.value)

    def test_valid_regex_pattern_accepted(self):
        """Verify that valid regex patterns are accepted"""
        from infrahub.config import SecuritySettings

        settings = SecuritySettings(sso_generate_groups_filter=r"^team-.*")
        assert settings.sso_generate_groups_filter == r"^team-.*"

    def test_none_filter_accepted(self):
        """Verify that None filter is accepted"""
        from infrahub.config import SecuritySettings

        settings = SecuritySettings(sso_generate_groups_filter=None)
        assert settings.sso_generate_groups_filter is None


class TestSSOGenerateGroupsFilterCaptureGroup:
    async def test_filter_does_not_duplicate_existing_extracted_group(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema, existing_group
    ):
        """Verify that extracted names do not create duplicates when group already exists"""
        preexisting_group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
        await preexisting_group.new(db=db, name="network_automation")
        await preexisting_group.save(db=db)

        original_generate = config.SETTINGS.security.sso_generate_groups
        original_filter = config.SETTINGS.security.sso_generate_groups_filter
        config.SETTINGS.security.sso_generate_groups = True
        config.SETTINGS.security.sso_generate_groups_filter = r"ldap/groups/(\w+)"

        try:
            await signin_sso_account(
                db=db,
                account_name="test-user-existing-transformed",
                sso_groups=["ldap/groups/network_automation"],
            )

            groups = await NodeManager.query(db=db, schema=CoreAccountGroup)
            group_names = [g.name.value for g in groups]

            assert group_names.count("network_automation") == 1
            assert "ldap/groups/network_automation" not in group_names
        finally:
            config.SETTINGS.security.sso_generate_groups = original_generate
            config.SETTINGS.security.sso_generate_groups_filter = original_filter

    async def test_filter_extracts_group_name_from_capture_group(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema, existing_group
    ):
        """Verify that the first capture group is used as the group name"""
        original_generate = config.SETTINGS.security.sso_generate_groups
        original_filter = config.SETTINGS.security.sso_generate_groups_filter
        config.SETTINGS.security.sso_generate_groups = True
        config.SETTINGS.security.sso_generate_groups_filter = r"ldap/groups/(\w+)"

        try:
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
        finally:
            config.SETTINGS.security.sso_generate_groups = original_generate
            config.SETTINGS.security.sso_generate_groups_filter = original_filter

    async def test_filter_without_capture_group_uses_original_name(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema, existing_group
    ):
        """Verify that when pattern has no capture group, the original name is used"""
        original_generate = config.SETTINGS.security.sso_generate_groups
        original_filter = config.SETTINGS.security.sso_generate_groups_filter
        config.SETTINGS.security.sso_generate_groups = True
        config.SETTINGS.security.sso_generate_groups_filter = r"^team-.*"

        try:
            await signin_sso_account(
                db=db,
                account_name="test-user-no-capture",
                sso_groups=["team-alpha", "team-beta"],
            )

            groups = await NodeManager.query(db=db, schema=CoreAccountGroup)
            group_names = {g.name.value for g in groups}

            assert "team-alpha" in group_names
            assert "team-beta" in group_names
        finally:
            config.SETTINGS.security.sso_generate_groups = original_generate
            config.SETTINGS.security.sso_generate_groups_filter = original_filter

    async def test_filter_deduplicates_extracted_names(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema, existing_group
    ):
        """Verify that duplicate extracted names only create one group"""
        original_generate = config.SETTINGS.security.sso_generate_groups
        original_filter = config.SETTINGS.security.sso_generate_groups_filter
        config.SETTINGS.security.sso_generate_groups = True
        config.SETTINGS.security.sso_generate_groups_filter = r".*/(\w+)$"

        try:
            await signin_sso_account(
                db=db,
                account_name="test-user-dedup",
                sso_groups=["ldap/groups/admins", "azure/groups/admins", "okta/groups/admins"],
            )

            groups = await NodeManager.query(db=db, schema=CoreAccountGroup)
            group_names = [g.name.value for g in groups]

            assert group_names.count("admins") == 1
        finally:
            config.SETTINGS.security.sso_generate_groups = original_generate
            config.SETTINGS.security.sso_generate_groups_filter = original_filter

    async def test_filter_skips_non_matching_groups(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema, existing_group
    ):
        """Verify that groups not matching the pattern are skipped"""
        original_generate = config.SETTINGS.security.sso_generate_groups
        original_filter = config.SETTINGS.security.sso_generate_groups_filter
        config.SETTINGS.security.sso_generate_groups = True
        config.SETTINGS.security.sso_generate_groups_filter = r"ldap/groups/(\w+)"

        try:
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
        finally:
            config.SETTINGS.security.sso_generate_groups = original_generate
            config.SETTINGS.security.sso_generate_groups_filter = original_filter
