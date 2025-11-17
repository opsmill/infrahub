from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.database import InfrahubDatabase
from infrahub.profiles.node_applier import NodeProfilesApplier
from tests.helpers.schema import CHILD, THING, load_schema


@dataclass
class ExpectedProfileAttr:
    name: str
    value: Any
    source_uuid: str


async def _validate_node_profile_attrs(
    db: InfrahubDatabase,
    schema: NodeSchema,
    original_node: Node,
    updated_node: Node,
    expected_profile_attrs: list[ExpectedProfileAttr],
):
    expected_profile_attrs_by_name = {attr.name: attr for attr in expected_profile_attrs}
    for attr_name in schema.attribute_names:
        updated_node_attr = getattr(updated_node, attr_name)
        updated_source = await updated_node_attr.get_source(db=db)
        original_node_attr = getattr(original_node, attr_name)
        expected_profile_attr = expected_profile_attrs_by_name.get(attr_name)
        if expected_profile_attr:
            assert updated_node_attr.value == expected_profile_attr.value
            assert updated_source.id == expected_profile_attr.source_uuid
        else:
            assert updated_node_attr.value == original_node_attr.value
            assert updated_source is None


async def test_get_many_with_profile(
    db: InfrahubDatabase,
    criticality_schema: NodeSchema,
    criticality_low: Node,
    criticality_medium: Node,
    branch: Branch,
) -> None:
    profile_schema = registry.schema.get("ProfileTestCriticality", branch=branch)
    crit_profile_1 = await Node.init(db=db, branch=branch, schema=profile_schema)
    await crit_profile_1.new(db=db, profile_name="crit_profile_1", color="green", profile_priority=1001)
    await crit_profile_1.save(db=db)
    crit_profile_2 = await Node.init(db=db, branch=branch, schema=profile_schema)
    await crit_profile_2.new(db=db, profile_name="crit_profile_2", color="blue", profile_priority=1002)
    await crit_profile_2.save(db=db)
    crit_low = await NodeManager.get_one(db=db, id=criticality_low.id, branch=branch)
    await crit_low.profiles.update(db=db, data=[crit_profile_1, crit_profile_2])
    await crit_low.save(db=db)

    node_applier = NodeProfilesApplier(db=db, branch=branch)

    updated_field_names = await node_applier.apply_profiles(node=crit_low)
    assert updated_field_names == ["color"]
    await crit_low.save(db=db)
    updated_field_names = await node_applier.apply_profiles(node=criticality_medium)
    assert updated_field_names == []
    await criticality_medium.save(db=db)

    node_map = await NodeManager.get_many(
        db=db, branch=branch, ids=[criticality_low.id, criticality_medium.id], include_source=True
    )
    assert len(node_map) == 2
    expected_profile_attrs = [
        ExpectedProfileAttr(name="color", value="green", source_uuid=crit_profile_1.id),
    ]
    updated_crit_low = node_map[criticality_low.id]
    await _validate_node_profile_attrs(
        db=db,
        schema=criticality_schema,
        original_node=criticality_low,
        updated_node=updated_crit_low,
        expected_profile_attrs=expected_profile_attrs,
    )
    updated_crit_medium = node_map[criticality_medium.id]
    await _validate_node_profile_attrs(
        db=db,
        schema=criticality_schema,
        original_node=criticality_medium,
        updated_node=updated_crit_medium,
        expected_profile_attrs=[],
    )

    # make sure field names returned by apply_profiles is idempotent
    updated_field_names = await node_applier.apply_profiles(node=crit_low)
    assert updated_field_names == []
    updated_field_names = await node_applier.apply_profiles(node=updated_crit_low)
    assert updated_field_names == []


async def test_get_many_with_profile_generic(
    db: InfrahubDatabase,
    criticality_schema: NodeSchema,
    criticality_low: Node,
    criticality_medium: Node,
    branch: Branch,
) -> None:
    generic_profile_schema = registry.schema.get("ProfileTestGenericCriticality", branch=branch)
    generic_profile = await Node.init(db=db, branch=branch, schema=generic_profile_schema)
    await generic_profile.new(
        db=db, profile_name="generic_profile", color="green", is_true=False, profile_priority=1001
    )
    await generic_profile.save(db=db)
    crit_profile_schema = registry.schema.get("ProfileTestCriticality", branch=branch)
    crit_profile = await Node.init(db=db, branch=branch, schema=crit_profile_schema)
    await crit_profile.new(
        db=db, profile_name="crit_profile", color="blue", description="more turquoise", profile_priority=1002
    )
    await crit_profile.save(db=db)
    crit_low = await NodeManager.get_one(db=db, branch=branch, id=criticality_low.id)
    await crit_low.profiles.update(db=db, data=[crit_profile, generic_profile])
    await crit_low.save(db=db)

    node_applier = NodeProfilesApplier(db=db, branch=branch)

    updated_field_names = await node_applier.apply_profiles(node=crit_low)
    assert set(updated_field_names) == {"color", "description", "is_true"}
    await crit_low.save(db=db)
    updated_field_names = await node_applier.apply_profiles(node=criticality_medium)
    assert updated_field_names == []
    await criticality_medium.save(db=db)

    node_map = await NodeManager.get_many(
        db=db, branch=branch, ids=[criticality_low.id, criticality_medium.id], include_source=True
    )
    assert len(node_map) == 2
    expected_profile_attrs = [
        ExpectedProfileAttr(name="color", value="green", source_uuid=generic_profile.id),
        ExpectedProfileAttr(name="is_true", value=False, source_uuid=generic_profile.id),
        ExpectedProfileAttr(name="description", value="more turquoise", source_uuid=crit_profile.id),
    ]
    updated_crit_low = node_map[criticality_low.id]
    await _validate_node_profile_attrs(
        db=db,
        schema=criticality_schema,
        original_node=criticality_low,
        updated_node=updated_crit_low,
        expected_profile_attrs=expected_profile_attrs,
    )
    updated_crit_medium = node_map[criticality_medium.id]
    await _validate_node_profile_attrs(
        db=db,
        schema=criticality_schema,
        original_node=criticality_medium,
        updated_node=updated_crit_medium,
        expected_profile_attrs=[],
    )

    # make sure field names returned by apply_profiles is idempotent
    updated_field_names = await node_applier.apply_profiles(node=crit_low)
    assert updated_field_names == []
    updated_field_names = await node_applier.apply_profiles(node=updated_crit_low)
    assert updated_field_names == []


async def test_get_many_with_multiple_profiles_same_priority(
    db: InfrahubDatabase,
    criticality_schema: NodeSchema,
    criticality_low: Node,
    criticality_medium: Node,
    branch: Branch,
) -> None:
    profile_schema = registry.schema.get("ProfileTestCriticality", branch=branch)
    crit_profiles = []
    for i in range(1, 10):
        crit_profile = await Node.init(db=db, branch=branch, schema=profile_schema)
        await crit_profile.new(db=db, profile_name=f"crit_profile_{i}", color=f"green{i}", profile_priority=1000)
        await crit_profile.save(db=db)
        crit_profiles.append(crit_profile)
    crit_low = await NodeManager.get_one(db=db, branch=branch, id=criticality_low.id)
    await crit_low.profiles.update(db=db, data=crit_profiles)
    await crit_low.save(db=db)

    node_applier = NodeProfilesApplier(db=db, branch=branch)
    updated_field_names = await node_applier.apply_profiles(node=crit_low)
    assert updated_field_names == ["color"]
    await crit_low.save(db=db)

    lowest_uuid_profile = sorted(crit_profiles, key=lambda p: p.id)[0]
    node_map = await NodeManager.get_many(
        db=db, branch=branch, ids=[criticality_low.id, criticality_medium.id], include_source=True
    )
    assert len(node_map) == 2
    updated_crit_low = node_map[criticality_low.id]
    expected_profile_attrs = [
        ExpectedProfileAttr(name="color", value=lowest_uuid_profile.color.value, source_uuid=lowest_uuid_profile.id),
    ]
    await _validate_node_profile_attrs(
        db=db,
        schema=criticality_schema,
        original_node=criticality_low,
        updated_node=updated_crit_low,
        expected_profile_attrs=expected_profile_attrs,
    )
    updated_crit_medium = node_map[criticality_medium.id]
    await _validate_node_profile_attrs(
        db=db,
        schema=criticality_schema,
        original_node=criticality_medium,
        updated_node=updated_crit_medium,
        expected_profile_attrs=[],
    )

    # make sure field names returned by apply_profiles is idempotent
    updated_field_names = await node_applier.apply_profiles(node=crit_low)
    assert updated_field_names == []
    updated_field_names = await node_applier.apply_profiles(node=updated_crit_low)
    assert updated_field_names == []


@dataclass
class ExpectedProfileRelationship:
    name: str
    peers: list[Node]
    source_uuid: str


async def _validate_node_profile_relationships(
    db: InfrahubDatabase,
    schema: NodeSchema,
    original_node: Node,
    updated_node: Node,
    expected_profile_relationships: list[ExpectedProfileRelationship],
):
    expected_profile_relationships_by_name = {r.name: r for r in expected_profile_relationships}
    for rel_name in schema.relationship_names:
        updated_node_rel_manager = updated_node.get_relationship(name=rel_name)
        updated_source = set()
        updated_peers = list((await updated_node_rel_manager.get_peers(db=db)).values())
        for peer in updated_peers:
            if source := peer._source:
                updated_source.add(source.id)

        original_node_rel_manager = original_node.get_relationship(name=rel_name)
        original_peers = list((await original_node_rel_manager.get_peers(db=db)).values())
        expected_profile_relationship = expected_profile_relationships_by_name.get(rel_name)

        if expected_profile_relationship:
            assert {p.id for p in updated_peers} == {p.id for p in expected_profile_relationship.peers}
            # assert updated_source == {expected_profile_relationship.source_uuid}
        else:
            assert {p.id for p in updated_peers} == {p.id for p in original_peers}
            # assert updated_source is None


@dataclass
class ChildThingFixtures:
    child_node_schema: NodeSchema
    thing_node_schema: NodeSchema
    child_nodes: list[Node]
    thing_nodes: list[Node]


@pytest.fixture
async def child_and_thing_schema(db: InfrahubDatabase, branch: Branch) -> SchemaRoot:
    THING.relationships[0].optional = True
    schema_root = SchemaRoot(nodes=[CHILD, THING])
    await load_schema(db=db, schema=schema_root, branch_name=branch.name)
    return schema_root


@pytest.fixture
async def child_and_thing_nodes(
    db: InfrahubDatabase, branch: Branch, child_and_thing_schema: SchemaRoot
) -> ChildThingFixtures:
    child_node_schema = registry.schema.get_node_schema(name=CHILD.kind, branch=branch, duplicate=False)
    thing_node_schema = registry.schema.get_node_schema(name=THING.kind, branch=branch, duplicate=False)

    child_one = await Node.init(db=db, branch=branch, schema=child_node_schema)
    await child_one.new(db=db, name="adam")
    await child_one.save(db=db)

    child_two = await Node.init(db=db, branch=branch, schema=child_node_schema)
    await child_two.new(db=db, name="megan")
    await child_two.save(db=db)

    thing_one = await Node.init(db=db, branch=branch, schema=thing_node_schema)
    await thing_one.new(db=db, name="Eye cover augmentation", color="black")
    await thing_one.save(db=db)

    thing_two = await Node.init(db=db, branch=branch, schema=thing_node_schema)
    await thing_two.new(db=db, name="Cybernetic arms", color="black")
    await thing_two.save(db=db)

    thing_three = await Node.init(db=db, branch=branch, schema=thing_node_schema)
    await thing_three.new(db=db, name="Pearl necklace", color="white")
    await thing_three.save(db=db)

    return ChildThingFixtures(
        child_node_schema=child_node_schema,
        thing_node_schema=thing_node_schema,
        child_nodes=[child_one, child_two],
        thing_nodes=[thing_one, thing_two, thing_three],
    )


async def test_get_many_with_profile_relationships_empty(
    db: InfrahubDatabase, branch: Branch, child_and_thing_nodes: ChildThingFixtures
) -> None:
    profile_schema = registry.schema.get_profile_schema(name=f"Profile{CHILD.kind}", branch=branch, duplicate=False)
    augmented_child_profile = await Node.init(db=db, branch=branch, schema=profile_schema)
    await augmented_child_profile.new(db=db, profile_name="mechanically_augmented", profile_priority=100)
    await augmented_child_profile.save(db=db)

    await child_and_thing_nodes.child_nodes[0].profiles.update(db=db, data=[augmented_child_profile])
    await child_and_thing_nodes.child_nodes[0].save(db=db)

    node_applier = NodeProfilesApplier(db=db, branch=branch)

    updated_field_names = await node_applier.apply_profiles(node=child_and_thing_nodes.child_nodes[0])
    assert updated_field_names == []
    await child_and_thing_nodes.child_nodes[0].save(db=db)

    node_map = await NodeManager.get_many(
        db=db, branch=branch, ids=[child_and_thing_nodes.child_nodes[0].id], include_source=True
    )
    assert len(node_map) == 1
    updated_child_one = node_map[child_and_thing_nodes.child_nodes[0].id]
    await _validate_node_profile_relationships(
        db=db,
        schema=child_and_thing_nodes.child_node_schema,
        original_node=child_and_thing_nodes.child_nodes[0],
        updated_node=updated_child_one,
        expected_profile_relationships=[ExpectedProfileRelationship(name="things", peers=[], source_uuid="")],
    )


async def test_get_many_with_profile_relationships(
    db: InfrahubDatabase, branch: Branch, child_and_thing_nodes: ChildThingFixtures
) -> None:
    profile_schema = registry.schema.get_profile_schema(name=f"Profile{CHILD.kind}", branch=branch, duplicate=False)
    augmented_child_profile = await Node.init(db=db, branch=branch, schema=profile_schema)
    await augmented_child_profile.new(
        db=db,
        profile_name="mechanically_augmented",
        things=[child_and_thing_nodes.thing_nodes[0], child_and_thing_nodes.thing_nodes[1]],
        profile_priority=100,
    )
    await augmented_child_profile.save(db=db)
    missing_child_profile = await Node.init(db=db, branch=branch, schema=profile_schema)
    await missing_child_profile.new(
        db=db, profile_name="missing", things=[child_and_thing_nodes.thing_nodes[2]], profile_priority=200
    )
    await missing_child_profile.save(db=db)

    await child_and_thing_nodes.child_nodes[0].profiles.update(db=db, data=[augmented_child_profile])
    await child_and_thing_nodes.child_nodes[0].save(db=db)

    await child_and_thing_nodes.child_nodes[1].profiles.update(db=db, data=[missing_child_profile])
    await child_and_thing_nodes.child_nodes[1].save(db=db)

    node_applier = NodeProfilesApplier(db=db, branch=branch)

    updated_field_names = await node_applier.apply_profiles(node=child_and_thing_nodes.child_nodes[0])
    assert updated_field_names == ["things"]
    await child_and_thing_nodes.child_nodes[0].save(db=db)

    node_map = await NodeManager.get_many(
        db=db, branch=branch, ids=[child_and_thing_nodes.child_nodes[0].id], include_source=True
    )
    assert len(node_map) == 1
    updated_child_one = node_map[child_and_thing_nodes.child_nodes[0].id]
    await _validate_node_profile_relationships(
        db=db,
        schema=child_and_thing_nodes.child_node_schema,
        original_node=child_and_thing_nodes.child_nodes[0],
        updated_node=updated_child_one,
        expected_profile_relationships=[
            ExpectedProfileRelationship(
                name="things",
                peers=[child_and_thing_nodes.thing_nodes[0], child_and_thing_nodes.thing_nodes[1]],
                source_uuid=augmented_child_profile.id,
            ),
        ],
    )

    updated_field_names = await node_applier.apply_profiles(node=child_and_thing_nodes.child_nodes[1])
    assert updated_field_names == ["things"]
    await child_and_thing_nodes.child_nodes[1].save(db=db)

    node_map = await NodeManager.get_many(
        db=db, branch=branch, ids=[child_and_thing_nodes.child_nodes[1].id], include_source=True
    )
    assert len(node_map) == 1
    updated_child_two = node_map[child_and_thing_nodes.child_nodes[1].id]
    await _validate_node_profile_relationships(
        db=db,
        schema=child_and_thing_nodes.child_node_schema,
        original_node=child_and_thing_nodes.child_nodes[1],
        updated_node=updated_child_two,
        expected_profile_relationships=[
            ExpectedProfileRelationship(
                name="things", peers=[child_and_thing_nodes.thing_nodes[2]], source_uuid=missing_child_profile.id
            ),
        ],
    )


async def test_get_many_with_profile_relationships_existing_peers(
    db: InfrahubDatabase, branch: Branch, child_and_thing_nodes: ChildThingFixtures
) -> None:
    child_one = await Node.init(db=db, branch=branch, schema=child_and_thing_nodes.child_node_schema)
    await child_one.new(db=db, name="adam", things=[child_and_thing_nodes.thing_nodes[0]])
    await child_one.save(db=db)

    child_two = await Node.init(db=db, branch=branch, schema=child_and_thing_nodes.child_node_schema)
    await child_two.new(db=db, name="megan", things=[child_and_thing_nodes.thing_nodes[2]])
    await child_two.save(db=db)

    profile_schema = registry.schema.get_profile_schema(name=f"Profile{CHILD.kind}", branch=branch, duplicate=False)
    augmented_child_profile = await Node.init(db=db, branch=branch, schema=profile_schema)
    await augmented_child_profile.new(
        db=db,
        profile_name="mechanically_augmented",
        things=[child_and_thing_nodes.thing_nodes[0], child_and_thing_nodes.thing_nodes[1]],
        profile_priority=100,
    )
    await augmented_child_profile.save(db=db)
    missing_child_profile = await Node.init(db=db, branch=branch, schema=profile_schema)
    await missing_child_profile.new(
        db=db, profile_name="missing", things=[child_and_thing_nodes.thing_nodes[2]], profile_priority=200
    )
    await missing_child_profile.save(db=db)

    await child_one.profiles.update(db=db, data=[augmented_child_profile])
    await child_one.save(db=db)

    await child_two.profiles.update(db=db, data=[missing_child_profile])
    await child_two.save(db=db)

    node_applier = NodeProfilesApplier(db=db, branch=branch)

    updated_field_names = await node_applier.apply_profiles(node=child_one)
    assert updated_field_names == []
    await child_one.save(db=db)

    node_map = await NodeManager.get_many(db=db, branch=branch, ids=[child_one.id], include_source=True)
    assert len(node_map) == 1
    updated_child_one = node_map[child_one.id]
    await _validate_node_profile_relationships(
        db=db,
        schema=child_and_thing_nodes.child_node_schema,
        original_node=child_one,
        updated_node=updated_child_one,
        expected_profile_relationships=[
            ExpectedProfileRelationship(
                name="things",
                peers=[child_and_thing_nodes.thing_nodes[0]],
                source_uuid="",
            )
        ],
    )


async def test_get_many_with_profile_relationships_clear(
    db: InfrahubDatabase, branch: Branch, child_and_thing_nodes: ChildThingFixtures
) -> None:
    profile_schema = registry.schema.get_profile_schema(name=f"Profile{CHILD.kind}", branch=branch, duplicate=False)
    augmented_child_profile = await Node.init(db=db, branch=branch, schema=profile_schema)
    await augmented_child_profile.new(
        db=db,
        profile_name="mechanically_augmented",
        things=[child_and_thing_nodes.thing_nodes[0], child_and_thing_nodes.thing_nodes[1]],
        profile_priority=100,
    )
    await augmented_child_profile.save(db=db)
    missing_child_profile = await Node.init(db=db, branch=branch, schema=profile_schema)
    await missing_child_profile.new(
        db=db, profile_name="missing", things=[child_and_thing_nodes.thing_nodes[2]], profile_priority=200
    )
    await missing_child_profile.save(db=db)

    # Set profile for child one
    await child_and_thing_nodes.child_nodes[0].profiles.update(db=db, data=[augmented_child_profile])
    await child_and_thing_nodes.child_nodes[0].save(db=db)

    node_applier = NodeProfilesApplier(db=db, branch=branch)

    updated_field_names = await node_applier.apply_profiles(node=child_and_thing_nodes.child_nodes[0])
    assert updated_field_names == ["things"]
    await child_and_thing_nodes.child_nodes[0].save(db=db)

    node_map = await NodeManager.get_many(
        db=db, branch=branch, ids=[child_and_thing_nodes.child_nodes[0].id], include_source=True
    )
    assert len(node_map) == 1
    updated_child_one = node_map[child_and_thing_nodes.child_nodes[0].id]
    await _validate_node_profile_relationships(
        db=db,
        schema=child_and_thing_nodes.child_node_schema,
        original_node=child_and_thing_nodes.child_nodes[0],
        updated_node=updated_child_one,
        expected_profile_relationships=[
            ExpectedProfileRelationship(
                name="things",
                peers=[child_and_thing_nodes.thing_nodes[0], child_and_thing_nodes.thing_nodes[1]],
                source_uuid=augmented_child_profile.id,
            ),
        ],
    )

    # Clear profile for child one
    await updated_child_one.profiles.delete(db=db)
    await updated_child_one.save(db=db)

    node_map = await NodeManager.get_many(
        db=db, branch=branch, ids=[child_and_thing_nodes.child_nodes[0].id], include_source=True
    )
    assert len(node_map) == 1
    updated_child_one = node_map[child_and_thing_nodes.child_nodes[0].id]
    assert not len(await updated_child_one.profiles.get_relationships(db=db))

    node_applier = NodeProfilesApplier(db=db, branch=branch)

    updated_field_names = await node_applier.apply_profiles(node=updated_child_one)
    assert updated_field_names == []
    await updated_child_one.save(db=db)

    node_map = await NodeManager.get_many(
        db=db, branch=branch, ids=[child_and_thing_nodes.child_nodes[0].id], include_source=True
    )
    assert len(node_map) == 1
    updated_child_one = node_map[child_and_thing_nodes.child_nodes[0].id]
    await _validate_node_profile_relationships(
        db=db,
        schema=child_and_thing_nodes.child_node_schema,
        original_node=child_and_thing_nodes.child_nodes[0],
        updated_node=updated_child_one,
        expected_profile_relationships=[ExpectedProfileRelationship(name="things", peers=[], source_uuid="")],
    )
