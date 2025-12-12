import copy

import pytest

from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.relationship.constraints.profiles_removal import RelationshipProfileRemovalConstraint
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError
from infrahub.profiles.node_applier import NodeProfilesApplier
from tests.constants import TestKind
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
    thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=branch, duplicate=False)

    thing = await NodeManager.get_one(db=db, branch=branch, id=thing.id)
    await thing.profiles.resolve(db=db)
    await thing.profiles.update(db=db, data=[])

    constraint = RelationshipProfileRemovalConstraint(db=db, branch=branch)
    with pytest.raises(ValidationError) as exc:
        await constraint.check(relm=thing.profiles, node_schema=thing_schema, node=thing)

    assert "Cannot remove profile" in str(exc.value)
    assert "inherits required relationship 'owner'" in str(exc.value)


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

    assert "Cannot remove profile" in str(exc.value)
    assert "inherits required relationship 'owner'" in str(exc.value)


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
    await constraint.check(relm=profile.related_nodes, node_schema=profile_schema, node=profile)


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

    assert "Cannot remove profile" in str(exc.value)
    assert "inherits required attribute 'color'" in str(exc.value)


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
    thing_schema = registry.schema.get_node_schema(name=TestKind.THING, branch=branch, duplicate=False)

    thing = await NodeManager.get_one(db=db, branch=branch, id=thing.id)
    await thing.color.from_graphql(data={"value": "user-set-green"}, db=db)
    await thing.save(db=db)

    thing = await NodeManager.get_one(db=db, branch=branch, id=thing.id)
    await thing.profiles.resolve(db=db)
    await thing.profiles.update(db=db, data=[])

    constraint = RelationshipProfileRemovalConstraint(db=db, branch=branch)
    await constraint.check(relm=thing.profiles, node_schema=thing_schema, node=thing)


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

    assert "Cannot remove profile" in str(exc.value)
    assert "inherits required attribute 'color'" in str(exc.value)


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
    await constraint.check(relm=profile.related_nodes, node_schema=profile_schema, node=profile)


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
    await constraint.check(relm=profile.related_nodes, node_schema=profile_schema, node=profile)
