from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock

import pytest

from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m041_profile_attrs_in_db import Migration041
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.profiles.node_applier import NodeProfilesApplier
from tests.helpers.test_app import TestInfrahubApp


@dataclass
class AttributeProfileDetails:
    attribute_name: str
    value: Any
    is_default: bool
    source_id: str | None = None

    @property
    def is_from_profile(self) -> bool:
        return self.source_id is not None


class WrappedMigration041(Migration041):
    async def _get_profile_applier(self, db: InfrahubDatabase, branch_name: str) -> NodeProfilesApplier:
        profile_applier = await super()._get_profile_applier(db=db, branch_name=branch_name)
        if isinstance(profile_applier, AsyncMock):
            return profile_applier
        wrapped_profile_applier = AsyncMock(wraps=profile_applier)
        self._appliers_by_branch[branch_name] = wrapped_profile_applier
        return wrapped_profile_applier


@pytest.mark.skip(reason="Is flaky. And waiting on updates to the migration")
class TestMigration041(TestInfrahubApp):
    @pytest.fixture
    async def profile_1(self, db: InfrahubDatabase, default_branch: Branch, criticality_schema) -> Node:
        profile = await Node.init(db=db, schema="ProfileTestCriticality")
        await profile.new(db=db, profile_name="profile_1", is_true=True, color="profile1", profile_priority=1001)
        await profile.save(db=db)
        return profile

    @pytest.fixture
    async def profile_2(self, db: InfrahubDatabase, default_branch: Branch, criticality_schema) -> Node:
        profile = await Node.init(db=db, schema="ProfileTestCriticality")
        await profile.new(
            db=db,
            profile_name="profile_2",
            description="profile2",
            is_false=False,
            is_true=False,
            color="profile2",
            profile_priority=1002,
        )
        await profile.save(db=db)
        return profile

    @pytest.fixture
    async def value_branch(self, db: InfrahubDatabase, default_branch: Branch) -> Branch:
        return await create_branch(db=db, branch_name="value_branch")

    @pytest.fixture
    async def profile_1_value_update(self, db: InfrahubDatabase, value_branch: Branch, profile_1: Node) -> Node:
        profile = await NodeManager.get_one(db=db, branch=value_branch, id=profile_1.id)
        profile.description.value = "profile1_value_update"
        profile.is_true.value = False
        profile.color.value = "profile1_value_update"
        await profile.save(db=db)
        return profile

    @pytest.fixture
    async def priority_branch(self, db: InfrahubDatabase, default_branch: Branch) -> Branch:
        return await create_branch(db=db, branch_name="priority_branch")

    @pytest.fixture
    async def profile_2_priority_update(self, db: InfrahubDatabase, priority_branch: Branch, profile_2: Node) -> Node:
        profile = await NodeManager.get_one(db=db, branch=priority_branch, id=profile_2.id)
        profile.profile_priority.value = 999
        await profile.save(db=db)
        return profile

    @pytest.fixture
    async def deleted_profile_branch(self, db: InfrahubDatabase, default_branch: Branch) -> Branch:
        return await create_branch(db=db, branch_name="deleted_profile_branch")

    @pytest.fixture
    async def profile_2_deleted(self, db: InfrahubDatabase, deleted_profile_branch: Branch, profile_2: Node):
        profile = await NodeManager.get_one(db=db, branch=deleted_profile_branch, id=profile_2.id)
        await profile.delete(db=db)

    @pytest.fixture
    async def deleted_node_branch(self, db: InfrahubDatabase, default_branch: Branch) -> Branch:
        return await create_branch(db=db, branch_name="deleted_node_branch")

    @pytest.fixture
    async def criticality_low_deleted(self, db: InfrahubDatabase, deleted_node_branch: Branch, criticality_low: Node):
        profile = await NodeManager.get_one(db=db, branch=deleted_node_branch, id=criticality_low.id)
        await profile.delete(db=db)

    @pytest.fixture
    async def load_data(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        criticality_low: Node,
        criticality_medium: Node,
        criticality_high: Node,
        profile_1: Node,
        profile_2: Node,
    ):
        crit_low = await NodeManager.get_one(db=db, id=criticality_low.id)
        await crit_low.profiles.update(db=db, data=[profile_1])
        await crit_low.save(db=db)
        crit_medium = await NodeManager.get_one(db=db, id=criticality_medium.id)
        await crit_medium.profiles.update(db=db, data=[profile_1, profile_2])
        await crit_medium.save(db=db)
        crit_high = await NodeManager.get_one(db=db, id=criticality_high.id)
        await crit_high.profiles.update(db=db, data=[profile_2])
        await crit_high.save(db=db)

    @pytest.fixture
    async def load_branch_data(
        self,
        value_branch: Branch,
        profile_1_value_update: Node,
        priority_branch: Branch,
        profile_2_priority_update: Node,
        deleted_profile_branch: Branch,
        profile_2_deleted: Node,
        deleted_node_branch: Branch,
        criticality_low_deleted: Node,
    ):
        pass

    def validate_node(
        self,
        original_node: Node,
        updated_node: Node,
        expected_profile_attrs: list[AttributeProfileDetails],
    ):
        expected_profile_attrs_by_name = {attr.attribute_name: attr for attr in expected_profile_attrs}
        for attribute_name in updated_node._attributes:
            current_attribute = getattr(updated_node, attribute_name)
            if expected_profile_attr := expected_profile_attrs_by_name.get(attribute_name):
                assert current_attribute.value == expected_profile_attr.value
                assert current_attribute.is_default == expected_profile_attr.is_default
                assert current_attribute.is_from_profile == expected_profile_attr.is_from_profile
                assert current_attribute.source_id == expected_profile_attr.source_id
                continue
            original_attribute = getattr(original_node, attribute_name)
            assert current_attribute.value == original_attribute.value
            assert current_attribute.is_default == original_attribute.is_default
            assert current_attribute.is_from_profile == original_attribute.is_from_profile
            assert current_attribute.source_id == original_attribute.source_id

    async def test_migration_041(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        criticality_low: Node,
        criticality_medium: Node,
        criticality_high: Node,
        profile_1: Node,
        profile_2: Node,
        load_data,
        load_branch_data,
        value_branch: Branch,
        priority_branch: Branch,
        deleted_profile_branch: Branch,
        deleted_node_branch: Branch,
    ):
        migration = WrappedMigration041()
        execution_result = await migration.execute(db=db)
        assert not execution_result.errors
        validation_result = await migration.validate_migration(db=db)
        assert not validation_result.errors

        # validate node-level changes on main
        updated_criticality_low = await NodeManager.get_one(db=db, id=criticality_low.id, include_source=True)
        self.validate_node(
            original_node=criticality_low,
            updated_node=updated_criticality_low,
            expected_profile_attrs=[
                AttributeProfileDetails(
                    attribute_name="color",
                    value="profile1",
                    is_default=False,
                    source_id=profile_1.id,
                ),
                AttributeProfileDetails(
                    attribute_name="is_true",
                    value=True,
                    is_default=False,
                    source_id=profile_1.id,
                ),
            ],
        )
        updated_criticality_medium = await NodeManager.get_one(db=db, id=criticality_medium.id, include_source=True)
        self.validate_node(
            original_node=criticality_medium,
            updated_node=updated_criticality_medium,
            expected_profile_attrs=[
                AttributeProfileDetails(attribute_name="is_true", value=True, is_default=False, source_id=profile_1.id),
                AttributeProfileDetails(
                    attribute_name="is_false", value=False, is_default=False, source_id=profile_2.id
                ),
            ],
        )
        updated_criticality_high = await NodeManager.get_one(db=db, id=criticality_high.id, include_source=True)
        self.validate_node(
            original_node=criticality_high,
            updated_node=updated_criticality_high,
            expected_profile_attrs=[
                AttributeProfileDetails(
                    attribute_name="is_false", value=False, is_default=False, source_id=profile_2.id
                ),
                AttributeProfileDetails(
                    attribute_name="is_true", value=False, is_default=False, source_id=profile_2.id
                ),
            ],
        )

        # validate node-level changes on value branch
        updated_criticality_low = await NodeManager.get_one(
            db=db, branch=value_branch, id=criticality_low.id, include_source=True
        )
        self.validate_node(
            original_node=criticality_low,
            updated_node=updated_criticality_low,
            expected_profile_attrs=[
                AttributeProfileDetails(
                    attribute_name="description",
                    value="profile1_value_update",
                    is_default=False,
                    source_id=profile_1.id,
                ),
                AttributeProfileDetails(
                    attribute_name="color",
                    value="profile1_value_update",
                    is_default=False,
                    source_id=profile_1.id,
                ),
                AttributeProfileDetails(
                    attribute_name="is_true",
                    value=False,
                    is_default=False,
                    source_id=profile_1.id,
                ),
            ],
        )
        updated_criticality_medium = await NodeManager.get_one(
            db=db, branch=value_branch, id=criticality_medium.id, include_source=True
        )
        self.validate_node(
            original_node=criticality_medium,
            updated_node=updated_criticality_medium,
            expected_profile_attrs=[
                AttributeProfileDetails(
                    attribute_name="is_true", value=False, is_default=False, source_id=profile_1.id
                ),
                AttributeProfileDetails(
                    attribute_name="is_false", value=False, is_default=False, source_id=profile_2.id
                ),
            ],
        )
        updated_criticality_high = await NodeManager.get_one(
            db=db, branch=value_branch, id=criticality_high.id, include_source=True
        )
        self.validate_node(
            original_node=criticality_high,
            updated_node=updated_criticality_high,
            expected_profile_attrs=[],
        )

        # validate node-level changes on priority branch
        updated_criticality_low = await NodeManager.get_one(
            db=db, branch=priority_branch, id=criticality_low.id, include_source=True
        )
        self.validate_node(
            original_node=criticality_low,
            updated_node=updated_criticality_low,
            expected_profile_attrs=[],
        )
        updated_criticality_medium = await NodeManager.get_one(
            db=db, branch=priority_branch, id=criticality_medium.id, include_source=True
        )
        self.validate_node(
            original_node=criticality_medium,
            updated_node=updated_criticality_medium,
            expected_profile_attrs=[
                AttributeProfileDetails(
                    attribute_name="is_true", value=False, is_default=False, source_id=profile_2.id
                ),
                AttributeProfileDetails(
                    attribute_name="is_false", value=False, is_default=False, source_id=profile_2.id
                ),
            ],
        )
        updated_criticality_high = await NodeManager.get_one(
            db=db, branch=priority_branch, id=criticality_high.id, include_source=True
        )
        self.validate_node(
            original_node=criticality_high,
            updated_node=updated_criticality_high,
            expected_profile_attrs=[
                AttributeProfileDetails(
                    attribute_name="is_true", value=False, is_default=False, source_id=profile_2.id
                ),
                AttributeProfileDetails(
                    attribute_name="is_false", value=False, is_default=False, source_id=profile_2.id
                ),
            ],
        )

        # validate node-level changes on deleted profile branch
        updated_criticality_low = await NodeManager.get_one(
            db=db, branch=deleted_profile_branch, id=criticality_low.id, include_source=True
        )
        self.validate_node(
            original_node=criticality_low,
            updated_node=updated_criticality_low,
            # branch would need to be rebased to get profile updates applied on main
            expected_profile_attrs=[],
        )
        updated_criticality_medium = await NodeManager.get_one(
            db=db, branch=deleted_profile_branch, id=criticality_medium.id, include_source=True
        )
        self.validate_node(
            original_node=criticality_medium,
            updated_node=updated_criticality_medium,
            expected_profile_attrs=[
                AttributeProfileDetails(attribute_name="is_true", value=True, is_default=False, source_id=profile_1.id),
            ],
        )
        updated_criticality_high = await NodeManager.get_one(
            db=db, branch=deleted_profile_branch, id=criticality_high.id, include_source=True
        )
        self.validate_node(
            original_node=criticality_high,
            updated_node=updated_criticality_high,
            expected_profile_attrs=[],
        )

        # validate node-level changes on deleted node branch
        updated_criticality_medium = await NodeManager.get_one(
            db=db, branch=deleted_node_branch, id=criticality_medium.id, include_source=True
        )
        self.validate_node(
            original_node=criticality_medium,
            updated_node=updated_criticality_medium,
            # branch would need to be rebased to get profile updates applied on main
            expected_profile_attrs=[],
        )
        updated_criticality_high = await NodeManager.get_one(
            db=db, branch=deleted_node_branch, id=criticality_high.id, include_source=True
        )
        self.validate_node(
            original_node=criticality_high,
            updated_node=updated_criticality_high,
            expected_profile_attrs=[],
        )

        # validate apply_profiles is only called on the required nodes
        applier_branches = set(migration._appliers_by_branch.keys())
        assert applier_branches == {
            default_branch.name,
            value_branch.name,
            priority_branch.name,
            deleted_profile_branch.name,
            deleted_node_branch.name,
        }

        main_profile_applier = migration._appliers_by_branch[default_branch.name]
        assert main_profile_applier.apply_profiles.call_count == 3
        refreshed_node_uuids = {
            call_args[1]["node"].id for call_args in main_profile_applier.apply_profiles.call_args_list
        }
        assert refreshed_node_uuids == {criticality_low.id, criticality_medium.id, criticality_high.id}

        value_profile_applier = migration._appliers_by_branch[value_branch.name]
        assert value_profile_applier.apply_profiles.call_count == 2
        refreshed_node_uuids = {
            call_args[1]["node"].id for call_args in value_profile_applier.apply_profiles.call_args_list
        }
        assert refreshed_node_uuids == {criticality_low.id, criticality_medium.id}

        priority_profile_applier = migration._appliers_by_branch[priority_branch.name]
        assert priority_profile_applier.apply_profiles.call_count == 2
        refreshed_node_uuids = {
            call_args[1]["node"].id for call_args in priority_profile_applier.apply_profiles.call_args_list
        }
        assert refreshed_node_uuids == {criticality_medium.id, criticality_high.id}

        deleted_profile_profile_applier = migration._appliers_by_branch[deleted_profile_branch.name]
        assert deleted_profile_profile_applier.apply_profiles.call_count == 2
        refreshed_node_uuids = {
            call_args[1]["node"].id for call_args in deleted_profile_profile_applier.apply_profiles.call_args_list
        }
        assert refreshed_node_uuids == {criticality_medium.id, criticality_high.id}

        deleted_node_profile_applier = migration._appliers_by_branch[deleted_node_branch.name]
        assert deleted_node_profile_applier.apply_profiles.call_count == 0
