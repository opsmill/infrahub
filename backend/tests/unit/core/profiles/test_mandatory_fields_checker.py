from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot
from infrahub.profiles.mandatory_fields_checker import (
    ProfileIdentifiers,
    _extract_profile_identifiers_from_input,
    get_mandatory_fields_from_profiles,
)
from tests.constants import TestKind
from tests.helpers.schema import CHILD, THING, load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


class TestExtractProfileIdentifiersFromInput:
    def test_none_input(self) -> None:
        result = _extract_profile_identifiers_from_input(profiles_data=None)
        assert result == ProfileIdentifiers(ids=[], hfids=[])

    def test_empty_list(self) -> None:
        result = _extract_profile_identifiers_from_input([])
        assert result == ProfileIdentifiers(ids=[], hfids=[])

    def test_list_of_dicts_with_id(self) -> None:
        profiles_data = [{"id": "id1"}, {"id": "id2"}]
        result = _extract_profile_identifiers_from_input(profiles_data=profiles_data)
        assert result.ids == ["id1", "id2"]
        assert result.hfids == []

    def test_list_of_dicts_with_hfid(self) -> None:
        profiles_data = [{"hfid": ["profile1"]}, {"hfid": ["profile2"]}]
        result = _extract_profile_identifiers_from_input(profiles_data=profiles_data)
        assert result.ids == []
        assert result.hfids == [["profile1"], ["profile2"]]

    def test_mixed_id_and_hfid(self) -> None:
        profiles_data = [{"id": "uuid1"}, {"hfid": ["profile_name"]}]
        result = _extract_profile_identifiers_from_input(profiles_data=profiles_data)
        assert result.ids == ["uuid1"]
        assert result.hfids == [["profile_name"]]

    def test_id_takes_precedence_over_hfid(self) -> None:
        profiles_data = [{"id": "uuid1", "hfid": ["profile_name"]}]
        result = _extract_profile_identifiers_from_input(profiles_data=profiles_data)
        assert result.ids == ["uuid1"]
        assert result.hfids == []  # hfid is ignored when id is present

    def test_list_of_strings(self) -> None:
        """Profiles can be specified as a list of UUID strings."""
        profiles_data = ["uuid1", "uuid2", "uuid3"]
        result = _extract_profile_identifiers_from_input(profiles_data=profiles_data)
        assert result.ids == ["uuid1", "uuid2", "uuid3"]
        assert result.hfids == []

    def test_mixed_strings_and_dicts(self) -> None:
        """Profiles can be a mix of UUID strings and dicts."""
        profiles_data = ["uuid1", {"id": "uuid2"}, {"hfid": ["profile_name"]}]
        result = _extract_profile_identifiers_from_input(profiles_data=profiles_data)
        assert result.ids == ["uuid1", "uuid2"]
        assert result.hfids == [["profile_name"]]

    def test_objects_with_id_attribute(self) -> None:
        """Profiles can be Node objects with an 'id' attribute."""

        node1 = MagicMock(spec=Node, id="uuid1")
        node2 = MagicMock(spec=Node, id="uuid2")

        result = _extract_profile_identifiers_from_input(profiles_data=[node1, node2])
        assert result.ids == ["uuid1", "uuid2"]
        assert result.hfids == []


@pytest.fixture
async def schema(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[CHILD, THING]), branch_name=default_branch.name)


class TestGetMandatoryFieldsFromProfiles:
    async def test_no_profiles_returns_empty(self, db: InfrahubDatabase, default_branch: Branch, schema: None) -> None:
        """When no profiles are provided, returns empty sets"""
        thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=default_branch)

        provided_attrs, provided_rels = await get_mandatory_fields_from_profiles(
            db=db,
            branch=default_branch,
            schema=thing_schema,
            profiles_data=None,
            mandatory_attr_names=["color"],
            mandatory_rel_names=[],
        )

        assert not provided_attrs
        assert not provided_rels

    async def test_profile_provides_mandatory_attribute(
        self, db: InfrahubDatabase, default_branch: Branch, schema: None
    ) -> None:
        """Profile providing mandatory attribute should be detected"""
        thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=default_branch)
        profile_schema = registry.schema.get_profile_schema(f"Profile{TestKind.THING}", branch=default_branch)

        profile = await Node.init(db=db, branch=default_branch, schema=profile_schema)
        await profile.new(db=db, profile_name="test_profile", color="blue", profile_priority=1000)
        await profile.save(db=db)

        provided_attrs, provided_rels = await get_mandatory_fields_from_profiles(
            db=db,
            branch=default_branch,
            schema=thing_schema,
            profiles_data=[{"id": profile.id}],
            mandatory_attr_names=["color"],
            mandatory_rel_names=[],
        )

        assert provided_attrs == {"color"}
        assert not provided_rels

    async def test_profile_does_not_provide_attribute(
        self, db: InfrahubDatabase, default_branch: Branch, schema: None
    ) -> None:
        """Profile not providing the attribute should not be in the result"""
        thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=default_branch)
        profile_schema = registry.schema.get_profile_schema(f"Profile{TestKind.THING}", branch=default_branch)

        profile = await Node.init(db=db, branch=default_branch, schema=profile_schema)
        await profile.new(db=db, profile_name="test_profile", profile_priority=1000)
        await profile.save(db=db)

        provided_attrs, provided_rels = await get_mandatory_fields_from_profiles(
            db=db,
            branch=default_branch,
            schema=thing_schema,
            profiles_data=[{"id": profile.id}],
            mandatory_attr_names=["color"],
            mandatory_rel_names=[],
        )
        assert not provided_attrs
        assert not provided_rels

    async def test_profile_provides_mandatory_relationship(
        self, db: InfrahubDatabase, default_branch: Branch, schema: None
    ) -> None:
        """Profile providing mandatory relationship should be detected"""
        child_schema = registry.schema.get_node_schema(name=TestKind.CHILD, branch=default_branch)
        thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=default_branch)

        child = await Node.init(db=db, branch=default_branch, schema=child_schema)
        await child.new(db=db, name="child_owner")
        await child.save(db=db)

        profile_schema = registry.schema.get_profile_schema(f"Profile{TestKind.THING}", branch=default_branch)
        profile = await Node.init(db=db, branch=default_branch, schema=profile_schema)
        await profile.new(db=db, profile_name="test_profile", profile_priority=1000, owner=child.id)
        await profile.save(db=db)

        provided_attrs, provided_rels = await get_mandatory_fields_from_profiles(
            db=db,
            branch=default_branch,
            schema=thing_schema,
            profiles_data=[{"id": profile.id}],
            mandatory_attr_names=[],
            mandatory_rel_names=["owner"],
        )

        assert not provided_attrs
        assert provided_rels == {"owner"}

    async def test_multiple_profiles_aggregate(
        self, db: InfrahubDatabase, default_branch: Branch, schema: None
    ) -> None:
        """Multiple profiles should aggregate their provided fields"""
        thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=default_branch)
        profile_schema = registry.schema.get_profile_schema(f"Profile{TestKind.THING}", branch=default_branch)

        profile1 = await Node.init(db=db, branch=default_branch, schema=profile_schema)
        await profile1.new(db=db, profile_name="profile1", color="red", profile_priority=1000)
        await profile1.save(db=db)

        profile2 = await Node.init(db=db, branch=default_branch, schema=profile_schema)
        await profile2.new(db=db, profile_name="profile2", profile_priority=2000)
        await profile2.save(db=db)

        provided_attrs, provided_rels = await get_mandatory_fields_from_profiles(
            db=db,
            branch=default_branch,
            schema=thing_schema,
            profiles_data=[{"id": profile1.id}, {"id": profile2.id}],
            mandatory_attr_names=["color"],
            mandatory_rel_names=[],
        )

        assert provided_attrs == {"color"}
        assert not provided_rels

    async def test_profile_lookup_by_hfid(self, db: InfrahubDatabase, default_branch: Branch, schema: None) -> None:
        """Profile can be looked up by HFID"""
        thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=default_branch)
        profile_schema = registry.schema.get_profile_schema(f"Profile{TestKind.THING}", branch=default_branch)
        profile = await Node.init(db=db, branch=default_branch, schema=profile_schema)
        await profile.new(db=db, profile_name="my_profile", color="green", profile_priority=1000)
        await profile.save(db=db)

        provided_attrs, provided_rels = await get_mandatory_fields_from_profiles(
            db=db,
            branch=default_branch,
            schema=thing_schema,
            profiles_data=[{"hfid": ["my_profile"]}],
            mandatory_attr_names=["color"],
            mandatory_rel_names=[],
        )
        assert provided_attrs == {"color"}
        assert not provided_rels
