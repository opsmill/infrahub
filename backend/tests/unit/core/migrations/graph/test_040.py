from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock

import pytest

from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m040_profile_attrs_in_db import Migration040
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.profiles.node_applier import NodeProfilesApplier


@dataclass
class AttributeProfileDetails:
    attribute_name: str
    value: Any
    is_default: bool
    source_id: str | None = None

    @property
    def is_from_profile(self) -> bool:
        return self.source_id is not None


class WrappedMigration040(Migration040):
    async def _get_profile_applier(self, db: InfrahubDatabase, branch_name: str) -> NodeProfilesApplier:
        profile_applier = await super()._get_profile_applier(db=db, branch_name=branch_name)
        if isinstance(profile_applier, AsyncMock):
            return profile_applier
        wrapped_profile_applier = AsyncMock(wraps=profile_applier)
        self._appliers_by_branch[branch_name] = wrapped_profile_applier
        return wrapped_profile_applier


class TestMigration040:
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
            color="profile2",
            profile_priority=1002,
        )
        await profile.save(db=db)
        return profile

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

    async def test_migration_040(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        criticality_low: Node,
        criticality_medium: Node,
        criticality_high: Node,
        profile_1: Node,
        profile_2: Node,
        load_data,
    ):
        migration = WrappedMigration040()
        execution_result = await migration.execute(db=db)
        assert not execution_result.errors
        validation_result = await migration.validate_migration(db=db)
        assert not validation_result.errors

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
            ],
        )

        wrapped_profile_applier = migration._appliers_by_branch[default_branch.name]
        assert wrapped_profile_applier.apply_profiles.call_count == 3
        refreshed_node_uuids = {
            call_args[1]["node"].id for call_args in wrapped_profile_applier.apply_profiles.call_args_list
        }
        assert refreshed_node_uuids == {criticality_low.id, criticality_medium.id, criticality_high.id}


# TODO:
# add testing for profile value update on branch
# add testing for profile relationship updated on branch
