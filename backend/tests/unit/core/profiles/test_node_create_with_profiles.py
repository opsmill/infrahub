from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot
from infrahub.exceptions import ValidationError
from infrahub.profiles.node_applier import NodeProfilesApplier
from tests.constants import TestKind
from tests.helpers.schema import CHILD, THING, load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


@pytest.fixture
async def schema(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[CHILD, THING]), branch_name=default_branch.name)


class TestNodeCreateWithMandatoryAttributeFromProfile:
    """Tests for creating nodes with mandatory attributes provided by profiles."""

    async def test_create_without_mandatory_attr_fails(
        self, db: InfrahubDatabase, default_branch: Branch, schema: None
    ) -> None:
        """Creating a node without mandatory attributes should fail."""
        child_schema = registry.schema.get_node_schema(name=TestKind.CHILD, branch=default_branch)

        node = await Node.init(db=db, branch=default_branch, schema=child_schema)
        with pytest.raises(ValidationError) as exc:
            await node.new(db=db)

        assert "name" in str(exc.value.message)

    async def test_create_with_mandatory_attr_from_profile(
        self, db: InfrahubDatabase, default_branch: Branch, schema: None
    ) -> None:
        """Creating a node with mandatory attribute provided by profile should succeed."""
        child_schema = registry.schema.get_node_schema(name=TestKind.CHILD, branch=default_branch)
        profile_schema = registry.schema.get_profile_schema(f"Profile{TestKind.CHILD}", branch=default_branch)

        profile = await Node.init(db=db, branch=default_branch, schema=profile_schema)
        await profile.new(db=db, profile_name="child_profile", name="from_profile", profile_priority=1000)
        await profile.save(db=db)

        node = await Node.init(db=db, branch=default_branch, schema=child_schema)
        await node.new(db=db, profiles=[profile])
        await node.save(db=db)

        assert node.id

        applier = NodeProfilesApplier(db=db, branch=default_branch)
        await applier.apply_profiles(node)

        assert node.name.value == "from_profile"

    async def test_create_with_user_provided_overrides_profile(
        self, db: InfrahubDatabase, default_branch: Branch, schema: None
    ) -> None:
        """User-provided values should override profile values for mandatory check."""
        child_schema = registry.schema.get_node_schema(name=TestKind.CHILD, branch=default_branch)
        profile_schema = registry.schema.get_profile_schema(f"Profile{TestKind.CHILD}", branch=default_branch)

        profile = await Node.init(db=db, branch=default_branch, schema=profile_schema)
        await profile.new(db=db, profile_name="child_profile", name="from_profile", profile_priority=1000)
        await profile.save(db=db)

        node = await Node.init(db=db, branch=default_branch, schema=child_schema)
        await node.new(db=db, profiles=[profile], name="user_provided")
        await node.save(db=db)

        assert node.id
        assert node.name.value == "user_provided"


class TestNodeCreateWithMandatoryRelationshipFromProfile:
    """Tests for creating nodes with mandatory relationships provided by profiles."""

    async def test_create_without_mandatory_rel_fails(
        self, db: InfrahubDatabase, default_branch: Branch, schema: None
    ) -> None:
        """Creating a node without mandatory relationship should fail."""
        thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=default_branch)

        node = await Node.init(db=db, branch=default_branch, schema=thing_schema)
        with pytest.raises(ValidationError) as exc:
            await node.new(db=db, name="test_thing", color="blue")

        assert "owner" in str(exc.value.message)

    async def test_create_with_mandatory_rel_from_profile(
        self, db: InfrahubDatabase, default_branch: Branch, schema: None
    ) -> None:
        """Creating a node with mandatory relationship provided by profile should succeed."""
        child_schema = registry.schema.get_node_schema(name=TestKind.CHILD, branch=default_branch)
        thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=default_branch)

        child = await Node.init(db=db, branch=default_branch, schema=child_schema)
        await child.new(db=db, name="owner_child")
        await child.save(db=db)

        profile_schema = registry.schema.get_profile_schema(f"Profile{TestKind.THING}", branch=default_branch)
        profile = await Node.init(db=db, branch=default_branch, schema=profile_schema)
        await profile.new(db=db, profile_name="thing_profile", profile_priority=1000, owner=child)
        await profile.save(db=db)

        node = await Node.init(db=db, branch=default_branch, schema=thing_schema)
        await node.new(db=db, name="test_thing", color="red", profiles=[profile])
        await node.save(db=db)

        assert node.id
        assert node.name.value == "test_thing"


class TestNodeCreateWithMultipleProfiles:
    """Tests for creating nodes with multiple profiles providing mandatory fields."""

    async def test_create_with_multiple_profiles_combined(
        self, db: InfrahubDatabase, default_branch: Branch, schema: None
    ) -> None:
        """Multiple profiles together can satisfy all mandatory fields."""
        child_schema = registry.schema.get_node_schema(name=TestKind.CHILD, branch=default_branch)
        thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=default_branch)
        profile_schema = registry.schema.get_profile_schema(f"Profile{TestKind.THING}", branch=default_branch)

        child = await Node.init(db=db, branch=default_branch, schema=child_schema)
        await child.new(db=db, name="owner_child")
        await child.save(db=db)

        profile1 = await Node.init(db=db, branch=default_branch, schema=profile_schema)
        await profile1.new(db=db, profile_name="profile1", color="green", profile_priority=1000)
        await profile1.save(db=db)

        profile2 = await Node.init(db=db, branch=default_branch, schema=profile_schema)
        await profile2.new(db=db, profile_name="profile2", owner=child.id, profile_priority=2000)
        await profile2.save(db=db)

        node = await Node.init(db=db, branch=default_branch, schema=thing_schema)
        await node.new(db=db, name="test_thing", profiles=[profile1, profile2])
        await node.save(db=db)

        assert node.id

        applier = NodeProfilesApplier(db=db, branch=default_branch)
        await applier.apply_profiles(node)

        assert node.color.value == "green"

    async def test_create_with_dict_profile_format(
        self, db: InfrahubDatabase, default_branch: Branch, schema: None
    ) -> None:
        """Profile can be specified as dict."""
        child_schema = registry.schema.get_node_schema(name=TestKind.CHILD, branch=default_branch)
        profile_schema = registry.schema.get_profile_schema(f"Profile{TestKind.CHILD}", branch=default_branch)

        profile = await Node.init(db=db, branch=default_branch, schema=profile_schema)
        await profile.new(db=db, profile_name="dict_profile", name="from_profile", profile_priority=1000)
        await profile.save(db=db)

        node = await Node.init(db=db, branch=default_branch, schema=child_schema)
        await node.new(db=db, profiles=[{"id": profile.id}])
        await node.save(db=db)

        assert node.id

        applier = NodeProfilesApplier(db=db, branch=default_branch)
        await applier.apply_profiles(node)

        assert node.name.value == "from_profile"
