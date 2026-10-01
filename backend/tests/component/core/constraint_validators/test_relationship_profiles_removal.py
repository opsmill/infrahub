import copy
from collections import Counter
from collections.abc import Generator
from dataclasses import dataclass

import pytest

from infrahub import config
from infrahub.core.branch import Branch
from infrahub.core.constants import MetadataOptions
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.relationship import RelationshipGetPeerQuery
from infrahub.core.registry import registry
from infrahub.core.relationship.constraints.profiles_removal import RelationshipProfileRemovalConstraint
from infrahub.core.schema import ProfileSchema, SchemaRoot
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError
from infrahub.profiles.node_applier import NodeProfilesApplier
from tests.constants import TestKind
from tests.helpers.db_query_counter import CountingInfrahubDatabase
from tests.helpers.schema import load_schema
from tests.helpers.schema.child import CHILD
from tests.helpers.schema.thing import THING


async def test_constraint_allows_empty_profiles_relationship(db: InfrahubDatabase, branch: Branch) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[CHILD, THING]), branch_name=branch.name)

    child_schema = registry.schema.get_node_schema(name=TestKind.CHILD, branch=branch, duplicate=False)
    thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=branch, duplicate=False)

    child = await Node.init(db=db, branch=branch, schema=child_schema)
    await child.new(db=db, name="child-1")
    await child.save(db=db)

    thing = await Node.init(db=db, branch=branch, schema=thing_schema)
    await thing.new(db=db, name="thing-1", color="blue", owner=child)
    await thing.save(db=db)

    constraint = RelationshipProfileRemovalConstraint(db=db, branch=branch)
    await constraint.check(relm=thing.profiles, node_schema=thing_schema, node=thing)


async def test_constraint_allows_adding_profiles(db: InfrahubDatabase, branch: Branch) -> None:
    thing_optional = copy.deepcopy(THING)
    thing_optional.relationships[0].optional = True

    await load_schema(db=db, schema=SchemaRoot(nodes=[CHILD, thing_optional]), branch_name=branch.name)

    child_schema = registry.schema.get_node_schema(name=TestKind.CHILD, branch=branch, duplicate=False)
    thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=branch, duplicate=False)
    profile_schema = registry.schema.get_profile_schema(name=f"Profile{TestKind.THING}", branch=branch, duplicate=False)

    child = await Node.init(db=db, branch=branch, schema=child_schema)
    await child.new(db=db, name="child-1")
    await child.save(db=db)

    profile = await Node.init(db=db, branch=branch, schema=profile_schema)
    await profile.new(db=db, profile_name="thing-profile", profile_priority=1000, owner=child)
    await profile.save(db=db)

    thing = await Node.init(db=db, branch=branch, schema=thing_schema)
    await thing.new(db=db, name="thing-1", color="blue")
    await thing.save(db=db)

    await thing.profiles.update(db=db, data=[profile])

    constraint = RelationshipProfileRemovalConstraint(db=db, branch=branch)
    await constraint.check(relm=thing.profiles, node_schema=thing_schema, node=thing)


async def test_constraint_blocks_removing_profile_with_inherited_required_relationship(
    db: InfrahubDatabase, branch: Branch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[CHILD, THING]), branch_name=branch.name)

    child_schema = registry.schema.get_node_schema(name=TestKind.CHILD, branch=branch, duplicate=False)
    thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=branch, duplicate=False)
    profile_schema = registry.schema.get_profile_schema(name=f"Profile{TestKind.THING}", branch=branch, duplicate=False)

    child = await Node.init(db=db, branch=branch, schema=child_schema)
    await child.new(db=db, name="child-1")
    await child.save(db=db)

    profile = await Node.init(db=db, branch=branch, schema=profile_schema)
    await profile.new(db=db, profile_name="thing-profile", profile_priority=1000, owner=child)
    await profile.save(db=db)

    thing = await Node.init(db=db, branch=branch, schema=thing_schema)
    await thing.new(db=db, name="thing-1", color="blue", profiles=[profile])
    await thing.save(db=db)

    node_applier = NodeProfilesApplier(db=db, branch=branch)
    updated_fields = await node_applier.apply_profiles(node=thing)
    assert "owner" in updated_fields
    await thing.save(db=db)

    await load_schema(db=db, schema=SchemaRoot(nodes=[CHILD, THING]), branch_name=branch.name)
    thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=branch, duplicate=False)

    thing = await NodeManager.get_one(db=db, branch=branch, id=thing.id)
    await thing.profiles.resolve(db=db)
    await thing.profiles.update(db=db, data=[])

    constraint = RelationshipProfileRemovalConstraint(db=db, branch=branch)
    with pytest.raises(ValidationError) as exc:
        await constraint.check(relm=thing.profiles, node_schema=thing_schema, node=thing)

    assert exc.value.message == (
        f"Cannot remove profile '{profile.id}' because node 'TestingThing(ID: {thing.id})' (ID: {thing.id}) "
        "inherits required relationship 'owner' from this profile."
    )


async def test_constraint_allows_removing_profile_without_required_relationship_inheritance(
    db: InfrahubDatabase, branch: Branch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[CHILD, THING]), branch_name=branch.name)

    child_schema = registry.schema.get_node_schema(name=TestKind.CHILD, branch=branch, duplicate=False)
    thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=branch, duplicate=False)
    profile_schema = registry.schema.get_profile_schema(name=f"Profile{TestKind.THING}", branch=branch, duplicate=False)

    child = await Node.init(db=db, branch=branch, schema=child_schema)
    await child.new(db=db, name="child-1")
    await child.save(db=db)

    profile = await Node.init(db=db, branch=branch, schema=profile_schema)
    await profile.new(db=db, profile_name="thing-profile", profile_priority=1000)
    await profile.save(db=db)

    thing = await Node.init(db=db, branch=branch, schema=thing_schema)
    await thing.new(db=db, name="thing-1", color="blue", owner=child, profiles=[profile])
    await thing.save(db=db)

    node_applier = NodeProfilesApplier(db=db, branch=branch)
    updated_fields = await node_applier.apply_profiles(node=thing)
    assert "owner" not in updated_fields
    await thing.save(db=db)

    thing = await NodeManager.get_one(db=db, branch=branch, id=thing.id)
    await thing.profiles.resolve(db=db)
    await thing.profiles.update(db=db, data=[])

    constraint = RelationshipProfileRemovalConstraint(db=db, branch=branch)
    await constraint.check(relm=thing.profiles, node_schema=thing_schema, node=thing)


async def test_constraint_allows_removing_profile_when_user_set_required_relationship(
    db: InfrahubDatabase, branch: Branch
) -> None:
    thing_optional = copy.deepcopy(THING)
    thing_optional.relationships[0].optional = True
    await load_schema(db=db, schema=SchemaRoot(nodes=[CHILD, thing_optional]), branch_name=branch.name)

    child_schema = registry.schema.get_node_schema(name=TestKind.CHILD, branch=branch, duplicate=False)
    thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=branch, duplicate=False)
    profile_schema = registry.schema.get_profile_schema(name=f"Profile{TestKind.THING}", branch=branch, duplicate=False)

    child_from_profile = await Node.init(db=db, branch=branch, schema=child_schema)
    await child_from_profile.new(db=db, name="child-from-profile")
    await child_from_profile.save(db=db)

    child_from_user = await Node.init(db=db, branch=branch, schema=child_schema)
    await child_from_user.new(db=db, name="child-from-user")
    await child_from_user.save(db=db)

    profile = await Node.init(db=db, branch=branch, schema=profile_schema)
    await profile.new(db=db, profile_name="thing-profile", profile_priority=1000, owner=child_from_profile)
    await profile.save(db=db)

    thing = await Node.init(db=db, branch=branch, schema=thing_schema)
    await thing.new(db=db, name="thing-1", color="blue", profiles=[profile])
    await thing.save(db=db)

    node_applier = NodeProfilesApplier(db=db, branch=branch)
    updated_fields = await node_applier.apply_profiles(node=thing)
    assert "owner" in updated_fields
    await thing.save(db=db)

    await load_schema(db=db, schema=SchemaRoot(nodes=[CHILD, THING]), branch_name=branch.name)
    thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=branch, duplicate=False)

    thing = await NodeManager.get_one(db=db, branch=branch, id=thing.id)
    await thing.owner.update(db=db, data=child_from_user)
    await thing.save(db=db)

    thing = await NodeManager.get_one(db=db, branch=branch, id=thing.id)
    await thing.profiles.resolve(db=db)
    await thing.profiles.update(db=db, data=[])

    constraint = RelationshipProfileRemovalConstraint(db=db, branch=branch)
    await constraint.check(relm=thing.profiles, node_schema=thing_schema, node=thing)


async def test_constraint_skips_non_profiles_relationships(db: InfrahubDatabase, branch: Branch) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[CHILD, THING]), branch_name=branch.name)

    child_schema = registry.schema.get_node_schema(name=TestKind.CHILD, branch=branch, duplicate=False)
    thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=branch, duplicate=False)

    child = await Node.init(db=db, branch=branch, schema=child_schema)
    await child.new(db=db, name="child-1")
    await child.save(db=db)

    thing = await Node.init(db=db, branch=branch, schema=thing_schema)
    await thing.new(db=db, name="thing-1", color="blue", owner=child)
    await thing.save(db=db)

    constraint = RelationshipProfileRemovalConstraint(db=db, branch=branch)
    await constraint.check(relm=thing.owner, node_schema=thing_schema, node=thing)


async def test_constraint_blocks_removing_node_from_profile_related_nodes_with_inherited_required_relationship(
    db: InfrahubDatabase, branch: Branch
) -> None:
    thing_optional = copy.deepcopy(THING)
    thing_optional.relationships[0].optional = True

    await load_schema(db=db, schema=SchemaRoot(nodes=[CHILD, thing_optional]), branch_name=branch.name)

    child_schema = registry.schema.get_node_schema(name=TestKind.CHILD, branch=branch, duplicate=False)
    thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=branch, duplicate=False)
    profile_schema = registry.schema.get_profile_schema(name=f"Profile{TestKind.THING}", branch=branch, duplicate=False)

    child = await Node.init(db=db, branch=branch, schema=child_schema)
    await child.new(db=db, name="child-1")
    await child.save(db=db)

    profile = await Node.init(db=db, branch=branch, schema=profile_schema)
    await profile.new(db=db, profile_name="thing-profile", profile_priority=1000, owner=child)
    await profile.save(db=db)

    thing = await Node.init(db=db, branch=branch, schema=thing_schema)
    await thing.new(db=db, name="thing-1", color="blue", profiles=[profile])
    await thing.save(db=db)

    node_applier = NodeProfilesApplier(db=db, branch=branch)
    updated_fields = await node_applier.apply_profiles(node=thing)
    assert "owner" in updated_fields
    await thing.save(db=db)

    await load_schema(db=db, schema=SchemaRoot(nodes=[CHILD, THING]), branch_name=branch.name)
    profile_schema = registry.schema.get_profile_schema(name=f"Profile{TestKind.THING}", branch=branch, duplicate=False)

    profile = await NodeManager.get_one(db=db, branch=branch, id=profile.id)
    await profile.related_nodes.resolve(db=db)
    await profile.related_nodes.update(db=db, data=[])

    constraint = RelationshipProfileRemovalConstraint(db=db, branch=branch)
    with pytest.raises(ValidationError) as exc:
        await constraint.check(relm=profile.related_nodes, node_schema=profile_schema, node=profile)

    assert exc.value.message == (
        f"Cannot remove profile '{profile.id}' because node 'TestingThing(ID: {thing.id})' (ID: {thing.id}) "
        "inherits required relationship 'owner' from this profile."
    )


async def test_constraint_allows_removing_node_from_profile_related_nodes_without_required_relationship_inheritance(
    db: InfrahubDatabase, branch: Branch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[CHILD, THING]), branch_name=branch.name)

    child_schema = registry.schema.get_node_schema(name=TestKind.CHILD, branch=branch, duplicate=False)
    thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=branch, duplicate=False)
    profile_schema = registry.schema.get_profile_schema(name=f"Profile{TestKind.THING}", branch=branch, duplicate=False)

    child = await Node.init(db=db, branch=branch, schema=child_schema)
    await child.new(db=db, name="child-1")
    await child.save(db=db)

    thing = await Node.init(db=db, branch=branch, schema=thing_schema)
    await thing.new(db=db, name="thing-1", color="blue", owner=child)
    await thing.save(db=db)

    profile = await Node.init(db=db, branch=branch, schema=profile_schema)
    await profile.new(db=db, profile_name="thing-profile", profile_priority=1000, related_nodes=[thing])
    await profile.save(db=db)

    node_applier = NodeProfilesApplier(db=db, branch=branch)
    updated_fields = await node_applier.apply_profiles(node=thing)
    assert "owner" not in updated_fields
    await thing.save(db=db)

    profile = await NodeManager.get_one(db=db, branch=branch, id=profile.id)
    await profile.related_nodes.resolve(db=db)
    await profile.related_nodes.update(db=db, data=[])

    constraint = RelationshipProfileRemovalConstraint(db=db, branch=branch)
    await constraint.validate_profile_deletion(profile=profile, profile_schema=profile_schema)


async def test_constraint_blocks_removing_profile_with_inherited_required_attribute(
    db: InfrahubDatabase, branch: Branch
) -> None:
    thing_optional_attrs = copy.deepcopy(THING)
    thing_optional_attrs.attributes[1].optional = True
    thing_optional_attrs.relationships[0].optional = True

    await load_schema(db=db, schema=SchemaRoot(nodes=[CHILD, thing_optional_attrs]), branch_name=branch.name)

    child_schema = registry.schema.get_node_schema(name=TestKind.CHILD, branch=branch, duplicate=False)
    thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=branch, duplicate=False)
    profile_schema = registry.schema.get_profile_schema(name=f"Profile{TestKind.THING}", branch=branch, duplicate=False)

    child = await Node.init(db=db, branch=branch, schema=child_schema)
    await child.new(db=db, name="child-1")
    await child.save(db=db)

    profile = await Node.init(db=db, branch=branch, schema=profile_schema)
    await profile.new(db=db, profile_name="thing-profile", profile_priority=1000, color="red")
    await profile.save(db=db)

    thing = await Node.init(db=db, branch=branch, schema=thing_schema)
    await thing.new(db=db, name="thing-1", owner=child, profiles=[profile])
    await thing.save(db=db)

    node_applier = NodeProfilesApplier(db=db, branch=branch)
    updated_fields = await node_applier.apply_profiles(node=thing)
    assert "color" in updated_fields
    await thing.save(db=db)

    thing_required_color = copy.deepcopy(THING)
    thing_required_color.relationships[0].optional = True
    await load_schema(db=db, schema=SchemaRoot(nodes=[CHILD, thing_required_color]), branch_name=branch.name)
    thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=branch, duplicate=False)

    thing = await NodeManager.get_one(db=db, branch=branch, id=thing.id)
    await thing.profiles.resolve(db=db)
    await thing.profiles.update(db=db, data=[])

    constraint = RelationshipProfileRemovalConstraint(db=db, branch=branch)
    with pytest.raises(ValidationError) as exc:
        await constraint.check(relm=thing.profiles, node_schema=thing_schema, node=thing)

    assert exc.value.message == (
        f"Cannot remove profile '{profile.id}' because node 'TestingThing(ID: {thing.id})' (ID: {thing.id}) "
        "inherits required attribute 'color' from this profile."
    )


async def test_constraint_allows_removing_profile_without_required_attribute_inheritance(
    db: InfrahubDatabase, branch: Branch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[CHILD, THING]), branch_name=branch.name)

    child_schema = registry.schema.get_node_schema(name=TestKind.CHILD, branch=branch, duplicate=False)
    thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=branch, duplicate=False)
    profile_schema = registry.schema.get_profile_schema(name=f"Profile{TestKind.THING}", branch=branch, duplicate=False)

    child = await Node.init(db=db, branch=branch, schema=child_schema)
    await child.new(db=db, name="child-1")
    await child.save(db=db)

    profile = await Node.init(db=db, branch=branch, schema=profile_schema)
    await profile.new(db=db, profile_name="thing-profile", profile_priority=1000)
    await profile.save(db=db)

    thing = await Node.init(db=db, branch=branch, schema=thing_schema)
    await thing.new(db=db, name="thing-1", color="blue", owner=child, profiles=[profile])
    await thing.save(db=db)

    node_applier = NodeProfilesApplier(db=db, branch=branch)
    updated_fields = await node_applier.apply_profiles(node=thing)
    assert "color" not in updated_fields
    await thing.save(db=db)

    thing = await NodeManager.get_one(db=db, branch=branch, id=thing.id)
    await thing.profiles.resolve(db=db)
    await thing.profiles.update(db=db, data=[])

    constraint = RelationshipProfileRemovalConstraint(db=db, branch=branch)
    await constraint.check(relm=thing.profiles, node_schema=thing_schema, node=thing)


async def test_constraint_allows_removing_profile_when_user_set_required_attribute(
    db: InfrahubDatabase, branch: Branch
) -> None:
    thing_optional_attrs = copy.deepcopy(THING)
    thing_optional_attrs.attributes[1].optional = True
    thing_optional_attrs.relationships[0].optional = True
    await load_schema(db=db, schema=SchemaRoot(nodes=[CHILD, thing_optional_attrs]), branch_name=branch.name)

    child_schema = registry.schema.get_node_schema(name=TestKind.CHILD, branch=branch, duplicate=False)
    thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=branch, duplicate=False)
    profile_schema = registry.schema.get_profile_schema(name=f"Profile{TestKind.THING}", branch=branch, duplicate=False)

    child = await Node.init(db=db, branch=branch, schema=child_schema)
    await child.new(db=db, name="child-1")
    await child.save(db=db)

    profile = await Node.init(db=db, branch=branch, schema=profile_schema)
    await profile.new(db=db, profile_name="thing-profile", profile_priority=1000, color="red")
    await profile.save(db=db)

    thing = await Node.init(db=db, branch=branch, schema=thing_schema)
    await thing.new(db=db, name="thing-1", owner=child, profiles=[profile])
    await thing.save(db=db)

    node_applier = NodeProfilesApplier(db=db, branch=branch)
    updated_fields = await node_applier.apply_profiles(node=thing)
    assert "color" in updated_fields
    await thing.save(db=db)

    thing_required_color = copy.deepcopy(THING)
    thing_required_color.relationships[0].optional = True
    await load_schema(db=db, schema=SchemaRoot(nodes=[CHILD, thing_required_color]), branch_name=branch.name)

    thing = await NodeManager.get_one(db=db, branch=branch, id=thing.id)
    thing.color.value = "user-set-green"
    await thing.save(db=db)

    thing = await NodeManager.get_one(db=db, branch=branch, id=thing.id)
    await thing.profiles.resolve(db=db)
    await thing.profiles.update(db=db, data=[])

    constraint = RelationshipProfileRemovalConstraint(db=db, branch=branch)
    await constraint.validate_profile_deletion(profile=profile, profile_schema=profile_schema)


async def test_constraint_blocks_removing_node_from_profile_related_nodes_with_inherited_required_attribute(
    db: InfrahubDatabase, branch: Branch
) -> None:
    thing_optional_attrs = copy.deepcopy(THING)
    thing_optional_attrs.attributes[1].optional = True
    thing_optional_attrs.relationships[0].optional = True

    await load_schema(db=db, schema=SchemaRoot(nodes=[CHILD, thing_optional_attrs]), branch_name=branch.name)

    child_schema = registry.schema.get_node_schema(name=TestKind.CHILD, branch=branch, duplicate=False)
    thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=branch, duplicate=False)
    profile_schema = registry.schema.get_profile_schema(name=f"Profile{TestKind.THING}", branch=branch, duplicate=False)

    child = await Node.init(db=db, branch=branch, schema=child_schema)
    await child.new(db=db, name="child-1")
    await child.save(db=db)

    profile = await Node.init(db=db, branch=branch, schema=profile_schema)
    await profile.new(db=db, profile_name="thing-profile", profile_priority=1000, color="red")
    await profile.save(db=db)

    thing = await Node.init(db=db, branch=branch, schema=thing_schema)
    await thing.new(db=db, name="thing-1", owner=child, profiles=[profile])
    await thing.save(db=db)

    node_applier = NodeProfilesApplier(db=db, branch=branch)
    updated_fields = await node_applier.apply_profiles(node=thing)
    assert "color" in updated_fields
    await thing.save(db=db)

    thing_required_color = copy.deepcopy(THING)
    thing_required_color.relationships[0].optional = True
    await load_schema(db=db, schema=SchemaRoot(nodes=[CHILD, thing_required_color]), branch_name=branch.name)
    profile_schema = registry.schema.get_profile_schema(name=f"Profile{TestKind.THING}", branch=branch, duplicate=False)

    profile = await NodeManager.get_one(db=db, branch=branch, id=profile.id)
    await profile.related_nodes.resolve(db=db)
    await profile.related_nodes.update(db=db, data=[])

    constraint = RelationshipProfileRemovalConstraint(db=db, branch=branch)
    with pytest.raises(ValidationError) as exc:
        await constraint.check(relm=profile.related_nodes, node_schema=profile_schema, node=profile)

    assert exc.value.message == (
        f"Cannot remove profile '{profile.id}' because node 'TestingThing(ID: {thing.id})' (ID: {thing.id}) "
        "inherits required attribute 'color' from this profile."
    )


async def test_constraint_allows_removing_node_from_profile_related_nodes_without_required_attribute_inheritance(
    db: InfrahubDatabase, branch: Branch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[CHILD, THING]), branch_name=branch.name)

    child_schema = registry.schema.get_node_schema(name=TestKind.CHILD, branch=branch, duplicate=False)
    thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=branch, duplicate=False)
    profile_schema = registry.schema.get_profile_schema(name=f"Profile{TestKind.THING}", branch=branch, duplicate=False)

    child = await Node.init(db=db, branch=branch, schema=child_schema)
    await child.new(db=db, name="child-1")
    await child.save(db=db)

    thing = await Node.init(db=db, branch=branch, schema=thing_schema)
    await thing.new(db=db, name="thing-1", color="blue", owner=child)
    await thing.save(db=db)

    profile = await Node.init(db=db, branch=branch, schema=profile_schema)
    await profile.new(db=db, profile_name="thing-profile", profile_priority=1000, related_nodes=[thing])
    await profile.save(db=db)

    node_applier = NodeProfilesApplier(db=db, branch=branch)
    updated_fields = await node_applier.apply_profiles(node=thing)
    assert "color" not in updated_fields
    await thing.save(db=db)

    profile = await NodeManager.get_one(db=db, branch=branch, id=profile.id)
    await profile.related_nodes.resolve(db=db)
    await profile.related_nodes.update(db=db, data=[])

    constraint = RelationshipProfileRemovalConstraint(db=db, branch=branch)
    await constraint.validate_profile_deletion(profile=profile, profile_schema=profile_schema)


async def test_constraint_allows_adding_nodes_to_profile_related_nodes(db: InfrahubDatabase, branch: Branch) -> None:
    thing_optional = copy.deepcopy(THING)
    thing_optional.relationships[0].optional = True

    await load_schema(db=db, schema=SchemaRoot(nodes=[CHILD, thing_optional]), branch_name=branch.name)

    child_schema = registry.schema.get_node_schema(name=TestKind.CHILD, branch=branch, duplicate=False)
    thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=branch, duplicate=False)
    profile_schema = registry.schema.get_profile_schema(name=f"Profile{TestKind.THING}", branch=branch, duplicate=False)

    child = await Node.init(db=db, branch=branch, schema=child_schema)
    await child.new(db=db, name="child-1")
    await child.save(db=db)

    thing = await Node.init(db=db, branch=branch, schema=thing_schema)
    await thing.new(db=db, name="thing-1", color="blue")
    await thing.save(db=db)

    profile = await Node.init(db=db, branch=branch, schema=profile_schema)
    await profile.new(db=db, profile_name="thing-profile", profile_priority=1000, owner=child)
    await profile.save(db=db)

    await profile.related_nodes.update(db=db, data=[thing])

    constraint = RelationshipProfileRemovalConstraint(db=db, branch=branch)
    await constraint.validate_profile_deletion(profile=profile, profile_schema=profile_schema)


async def _create_thing_from_profiles(
    db: InfrahubDatabase, branch: Branch, name: str, profiles: list[Node], **data: Node | str
) -> Node:
    thing = await Node.init(db=db, branch=branch, schema=TestKind.THING)
    await thing.new(db=db, name=name, profiles=profiles, **data)
    await thing.save(db=db)
    await NodeProfilesApplier(db=db, branch=branch).apply_profiles(node=thing)
    await thing.save(db=db)
    return thing


async def _load_thing_with_required_fields(db: InfrahubDatabase, branch: Branch) -> ProfileSchema:
    await load_schema(db=db, schema=SchemaRoot(nodes=[CHILD, THING]), branch_name=branch.name)
    return registry.schema.get_profile_schema(name=f"Profile{TestKind.THING}", branch=branch, duplicate=False)


@pytest.fixture
async def optional_thing_fields(db: InfrahubDatabase, branch: Branch) -> list[Node]:
    """Make the required fields of the thing optional, so that profiles can supply them. Return two children."""
    thing_optional = copy.deepcopy(THING)
    thing_optional.attributes[1].optional = True
    thing_optional.relationships[0].optional = True
    await load_schema(db=db, schema=SchemaRoot(nodes=[CHILD, thing_optional]), branch_name=branch.name)

    children = []
    for idx in range(2):
        child = await Node.init(db=db, branch=branch, schema=TestKind.CHILD)
        await child.new(db=db, name=f"child-{idx}")
        await child.save(db=db)
        children.append(child)
    return children


async def _create_profile(db: InfrahubDatabase, branch: Branch, name: str, priority: int, **data: Node | str) -> Node:
    profile = await Node.init(db=db, branch=branch, schema=f"Profile{TestKind.THING}")
    await profile.new(db=db, profile_name=name, profile_priority=priority, **data)
    await profile.save(db=db)
    return profile


async def test_profile_deletion_blocked_by_inherited_required_attribute(
    db: InfrahubDatabase, branch: Branch, optional_thing_fields: list[Node]
) -> None:
    profile = await _create_profile(db=db, branch=branch, name="thing-profile", priority=1000, color="red")
    thing = await _create_thing_from_profiles(
        db=db, branch=branch, name="thing-1", profiles=[profile], owner=optional_thing_fields[0]
    )
    profile_schema = await _load_thing_with_required_fields(db=db, branch=branch)
    profile = await NodeManager.get_one(db=db, branch=branch, id=profile.id, raise_on_error=True)

    constraint = RelationshipProfileRemovalConstraint(db=db, branch=branch)
    with pytest.raises(ValidationError) as exc:
        await constraint.validate_profile_deletion(profile=profile, profile_schema=profile_schema)

    assert exc.value.message == (
        f"Cannot remove profile '{profile.id}' because node 'TestingThing(ID: {thing.id})' (ID: {thing.id}) "
        "inherits required attribute 'color' from this profile."
    )


async def test_profile_deletion_blocked_by_inherited_required_relationship(
    db: InfrahubDatabase, branch: Branch, optional_thing_fields: list[Node]
) -> None:
    profile = await _create_profile(
        db=db, branch=branch, name="thing-profile", priority=1000, owner=optional_thing_fields[0]
    )
    thing = await _create_thing_from_profiles(db=db, branch=branch, name="thing-1", profiles=[profile], color="blue")
    profile_schema = await _load_thing_with_required_fields(db=db, branch=branch)
    profile = await NodeManager.get_one(db=db, branch=branch, id=profile.id, raise_on_error=True)

    constraint = RelationshipProfileRemovalConstraint(db=db, branch=branch)
    with pytest.raises(ValidationError) as exc:
        await constraint.validate_profile_deletion(profile=profile, profile_schema=profile_schema)

    assert exc.value.message == (
        f"Cannot remove profile '{profile.id}' because node 'TestingThing(ID: {thing.id})' (ID: {thing.id}) "
        "inherits required relationship 'owner' from this profile."
    )


@pytest.fixture
def restore_query_size_limit() -> Generator[None, None, None]:
    original = config.SETTINGS.database.query_size_limit
    yield
    config.SETTINGS.database.query_size_limit = original


@pytest.mark.parametrize("inheriting_index", range(10))
async def test_profile_deletion_blocked_when_the_relationship_read_spans_several_pages(
    db: InfrahubDatabase,
    branch: Branch,
    optional_thing_fields: list[Node],
    restore_query_size_limit: None,
    inheriting_index: int,
) -> None:
    """All the nodes share the required peer, but only one node gets it from the profile, at each position in turn."""
    owner = optional_thing_fields[0]
    profile = await _create_profile(db=db, branch=branch, name="thing-profile", priority=1000, owner=owner)
    things = []
    for idx in range(10):
        user_owner = {} if idx == inheriting_index else {"owner": owner}
        things.append(
            await _create_thing_from_profiles(
                db=db, branch=branch, name=f"thing-{idx}", profiles=[profile], color="blue", **user_owner
            )
        )
    inheriting = things[inheriting_index]
    profile_schema = await _load_thing_with_required_fields(db=db, branch=branch)
    profile = await NodeManager.get_one(db=db, branch=branch, id=profile.id, raise_on_error=True)

    # Pages smaller than the number of nodes, so that the read of the shared peer spans several pages.
    config.SETTINGS.database.query_size_limit = 2
    constraint = RelationshipProfileRemovalConstraint(db=db, branch=branch)
    with pytest.raises(ValidationError) as exc:
        await constraint.validate_profile_deletion(profile=profile, profile_schema=profile_schema)

    assert exc.value.message == (
        f"Cannot remove profile '{profile.id}' because node 'TestingThing(ID: {inheriting.id})' "
        f"(ID: {inheriting.id}) inherits required relationship 'owner' from this profile."
    )


@dataclass(frozen=True)
class OverriddenProfiles:
    profile_schema: ProfileSchema
    winning: Node
    """Supplies the required fields of every thing."""

    few_nodes: Node
    many_nodes: Node


@pytest.fixture
async def overridden_profiles(
    db: InfrahubDatabase, branch: Branch, optional_thing_fields: list[Node]
) -> OverriddenProfiles:
    """Each thing links to a profile that supplies its required fields, and to a profile with a lower priority."""
    winning = await _create_profile(
        db=db, branch=branch, name="winning", priority=1, color="blue", owner=optional_thing_fields[0]
    )
    overridden = {}
    for name, linked_nodes in (("few-nodes", 2), ("many-nodes", 6)):
        overridden[name] = await _create_profile(
            db=db, branch=branch, name=name, priority=2, color="red", owner=optional_thing_fields[1]
        )
        for idx in range(linked_nodes):
            await _create_thing_from_profiles(
                db=db, branch=branch, name=f"{name}-{idx}", profiles=[overridden[name], winning]
            )
    profile_schema = await _load_thing_with_required_fields(db=db, branch=branch)
    return OverriddenProfiles(
        profile_schema=profile_schema,
        winning=winning,
        few_nodes=overridden["few-nodes"],
        many_nodes=overridden["many-nodes"],
    )


async def test_profile_deletion_allowed_when_another_profile_supplies_required_fields(
    db: InfrahubDatabase, branch: Branch, overridden_profiles: OverriddenProfiles
) -> None:
    profile = await NodeManager.get_one(db=db, branch=branch, id=overridden_profiles.many_nodes.id, raise_on_error=True)
    related_ids = [rel.peer_id for rel in await profile.related_nodes.get_relationships(db=db)]
    things = await NodeManager.get_many(db=db, branch=branch, ids=related_ids, include_metadata=MetadataOptions.SOURCE)
    assert len(things) == 6
    for thing in things.values():
        assert thing.color.source_id == overridden_profiles.winning.id
        assert [rel.profile_id for rel in await thing.owner.get_relationships(db=db)] == [
            overridden_profiles.winning.id
        ]

    constraint = RelationshipProfileRemovalConstraint(db=db, branch=branch)
    await constraint.validate_profile_deletion(profile=profile, profile_schema=overridden_profiles.profile_schema)


async def test_removing_nodes_from_profile_allowed_when_another_profile_supplies_required_fields(
    db: InfrahubDatabase, branch: Branch, overridden_profiles: OverriddenProfiles
) -> None:
    profile = await NodeManager.get_one(db=db, branch=branch, id=overridden_profiles.many_nodes.id, raise_on_error=True)
    await profile.related_nodes.resolve(db=db)
    await profile.related_nodes.update(db=db, data=[])

    constraint = RelationshipProfileRemovalConstraint(db=db, branch=branch)
    await constraint.check(relm=profile.related_nodes, node_schema=overridden_profiles.profile_schema, node=profile)


async def _count_profile_deletion_queries(
    db: InfrahubDatabase, branch: Branch, profile_id: str, profile_schema: ProfileSchema
) -> Counter[str]:
    profile = await NodeManager.get_one(db=db, branch=branch, id=profile_id, raise_on_error=True)
    counting_db = CountingInfrahubDatabase.from_db(db=db)
    constraint = RelationshipProfileRemovalConstraint(db=counting_db, branch=branch)
    await constraint.validate_profile_deletion(profile=profile, profile_schema=profile_schema)
    return counting_db.query_counts


async def test_profile_deletion_queries_do_not_grow_with_linked_nodes(
    db: InfrahubDatabase, branch: Branch, overridden_profiles: OverriddenProfiles
) -> None:
    few = await _count_profile_deletion_queries(
        db=db,
        branch=branch,
        profile_id=overridden_profiles.few_nodes.id,
        profile_schema=overridden_profiles.profile_schema,
    )
    many = await _count_profile_deletion_queries(
        db=db,
        branch=branch,
        profile_id=overridden_profiles.many_nodes.id,
        profile_schema=overridden_profiles.profile_schema,
    )

    assert many == few
    # One read for the linked nodes of the profile, and one read for the required relationship of all the nodes.
    assert few[RelationshipGetPeerQuery.name] == 2


async def _count_related_nodes_removal_queries(
    db: InfrahubDatabase, branch: Branch, profile_id: str, profile_schema: ProfileSchema
) -> Counter[str]:
    profile = await NodeManager.get_one(db=db, branch=branch, id=profile_id, raise_on_error=True)
    await profile.related_nodes.resolve(db=db)
    await profile.related_nodes.update(db=db, data=[])
    counting_db = CountingInfrahubDatabase.from_db(db=db)
    constraint = RelationshipProfileRemovalConstraint(db=counting_db, branch=branch)
    await constraint.check(relm=profile.related_nodes, node_schema=profile_schema, node=profile)
    return counting_db.query_counts


async def test_related_nodes_removal_queries_do_not_grow_with_removed_nodes(
    db: InfrahubDatabase, branch: Branch, overridden_profiles: OverriddenProfiles
) -> None:
    few = await _count_related_nodes_removal_queries(
        db=db,
        branch=branch,
        profile_id=overridden_profiles.few_nodes.id,
        profile_schema=overridden_profiles.profile_schema,
    )
    many = await _count_related_nodes_removal_queries(
        db=db,
        branch=branch,
        profile_id=overridden_profiles.many_nodes.id,
        profile_schema=overridden_profiles.profile_schema,
    )

    assert many == few
    # The constraint knows the removed nodes already, so it reads only the required relationship of all of them.
    assert few[RelationshipGetPeerQuery.name] == 1
