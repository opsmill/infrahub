import copy
from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import MetadataOptions
from infrahub.core.manager import NodeManager
from infrahub.core.metadata.model import MetadataQueryOptions
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
        # Skip if the attribute is not present on the node (e.g., not set on template)
        if not hasattr(updated_node, attr_name):
            continue
        updated_node_attr = getattr(updated_node, attr_name)
        updated_source = await updated_node_attr.get_source(db=db)
        original_node_attr = getattr(original_node, attr_name) if hasattr(original_node, attr_name) else None
        expected_profile_attr = expected_profile_attrs_by_name.get(attr_name)
        if expected_profile_attr:
            assert updated_node_attr.value == expected_profile_attr.value
            assert updated_source.id == expected_profile_attr.source_uuid
        elif original_node_attr is not None:
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
        db=db, branch=branch, ids=[criticality_low.id, criticality_medium.id], include_metadata=MetadataOptions.SOURCE
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
        db=db, branch=branch, ids=[criticality_low.id, criticality_medium.id], include_metadata=MetadataOptions.SOURCE
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
        db=db, branch=branch, ids=[criticality_low.id, criticality_medium.id], include_metadata=MetadataOptions.SOURCE
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
        updated_relationships = await updated_node_rel_manager.get_relationships(db=db)
        updated_peers = [await rel.get_peer(db=db) for rel in updated_relationships]
        for peer in updated_relationships:
            if source := await peer.get_source(db=db):
                updated_source.add(source.id)

        original_node_rel_manager = original_node.get_relationship(name=rel_name)
        original_peers = list((await original_node_rel_manager.get_peers(db=db)).values())
        expected_profile_relationship = expected_profile_relationships_by_name.get(rel_name)

        if expected_profile_relationship:
            assert {p.id for p in updated_peers} == {p.id for p in expected_profile_relationship.peers}
            if expected_profile_relationship.source_uuid or updated_source:
                assert updated_source == {expected_profile_relationship.source_uuid}
        else:
            assert {p.id for p in updated_peers} == {p.id for p in original_peers}
            assert updated_source == set()


@dataclass
class ChildThingFixtures:
    child_node_schema: NodeSchema
    thing_node_schema: NodeSchema
    child_nodes: list[Node]
    thing_nodes: list[Node]


@pytest.fixture
async def child_and_thing_schema(db: InfrahubDatabase, branch: Branch) -> None:
    thing_copy = copy.deepcopy(THING)
    thing_copy.relationships[0].optional = True
    schema_root = SchemaRoot(nodes=[CHILD, thing_copy])
    await load_schema(db=db, schema=schema_root, branch_name=branch.name)


@pytest.fixture
async def child_and_thing_nodes(
    db: InfrahubDatabase, branch: Branch, child_and_thing_schema: None
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
        db=db, branch=branch, ids=[child_and_thing_nodes.child_nodes[0].id], include_metadata=MetadataOptions.SOURCE
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
        db=db, branch=branch, ids=[child_and_thing_nodes.child_nodes[0].id], include_metadata=MetadataOptions.SOURCE
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
        db=db, branch=branch, ids=[child_and_thing_nodes.child_nodes[1].id], include_metadata=MetadataOptions.SOURCE
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

    node_map = await NodeManager.get_many(
        db=db, branch=branch, ids=[child_one.id], include_metadata=MetadataOptions.SOURCE
    )
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

    node_map = await NodeManager.get_many(
        db=db, branch=branch, ids=[child_two.id], include_metadata=MetadataOptions.SOURCE
    )
    assert len(node_map) == 1
    updated_child_two = node_map[child_two.id]
    await _validate_node_profile_relationships(
        db=db,
        schema=child_and_thing_nodes.child_node_schema,
        original_node=child_two,
        updated_node=updated_child_two,
        expected_profile_relationships=[
            ExpectedProfileRelationship(
                name="things",
                peers=[child_and_thing_nodes.thing_nodes[2]],
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
        db=db, branch=branch, ids=[child_and_thing_nodes.child_nodes[0].id], include_metadata=MetadataOptions.SOURCE
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

    node_applier = NodeProfilesApplier(db=db, branch=branch)

    # Clear profile for child one
    await updated_child_one.profiles.remove_locally(db=db, peer_id=augmented_child_profile.id)
    updated_field_names = await node_applier.apply_profiles(node=updated_child_one)
    assert updated_field_names == ["things"]
    await updated_child_one.save(db=db)

    node_map = await NodeManager.get_many(
        db=db, branch=branch, ids=[child_and_thing_nodes.child_nodes[0].id], include_metadata=MetadataOptions.SOURCE
    )
    assert len(node_map) == 1
    final_child_one = node_map[child_and_thing_nodes.child_nodes[0].id]
    await _validate_node_profile_relationships(
        db=db,
        schema=child_and_thing_nodes.child_node_schema,
        original_node=updated_child_one,
        updated_node=final_child_one,
        expected_profile_relationships=[ExpectedProfileRelationship(name="things", peers=[], source_uuid="")],
    )


async def test_get_many_with_profile_relationships_override(
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
        db=db, branch=branch, ids=[child_and_thing_nodes.child_nodes[0].id], include_metadata=MetadataOptions.SOURCE
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

    node_applier = NodeProfilesApplier(db=db, branch=branch)

    # Override the relationship profile
    await updated_child_one.things.add(db=db, data=child_and_thing_nodes.thing_nodes[2])
    updated_field_names = await node_applier.apply_profiles(node=updated_child_one)
    assert updated_field_names == ["things"]
    await updated_child_one.save(db=db)

    node_map = await NodeManager.get_many(
        db=db, branch=branch, ids=[child_and_thing_nodes.child_nodes[0].id], include_metadata=MetadataOptions.SOURCE
    )
    assert len(node_map) == 1
    final_child_one = node_map[child_and_thing_nodes.child_nodes[0].id]
    await _validate_node_profile_relationships(
        db=db,
        schema=child_and_thing_nodes.child_node_schema,
        original_node=updated_child_one,
        updated_node=final_child_one,
        expected_profile_relationships=[
            ExpectedProfileRelationship(name="things", peers=[child_and_thing_nodes.thing_nodes[2]], source_uuid="")
        ],
    )


@pytest.mark.xfail(reason="Depending on how we override the peers, it may or may not work")
async def test_get_many_with_profile_relationships_partial_override(
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

    await child_and_thing_nodes.child_nodes[0].profiles.update(db=db, data=[augmented_child_profile])
    await child_and_thing_nodes.child_nodes[0].save(db=db)

    node_applier = NodeProfilesApplier(db=db, branch=branch)

    updated_field_names = await node_applier.apply_profiles(node=child_and_thing_nodes.child_nodes[0])
    assert updated_field_names == ["things"]
    await child_and_thing_nodes.child_nodes[0].save(db=db)

    node_map = await NodeManager.get_many(
        db=db, branch=branch, ids=[child_and_thing_nodes.child_nodes[0].id], include_metadata=MetadataOptions.SOURCE
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

    # Removing the peers from the profile before adding them will work
    # for thing in {child_and_thing_nodes.thing_nodes[0], child_and_thing_nodes.thing_nodes[1]}:
    #    await updated_child_one.things.remove_locally(db=db, peer_id=thing.id)

    # Override with a peer that is also in the profile, by adding them won't work
    # for thing in {child_and_thing_nodes.thing_nodes[1], child_and_thing_nodes.thing_nodes[2]}:
    #    await updated_child_one.things.add(db=db, data=thing)

    # Updating by replacing all peers will work
    await updated_child_one.things.update(
        db=db, data=[child_and_thing_nodes.thing_nodes[1], child_and_thing_nodes.thing_nodes[2]]
    )

    updated_field_names = await node_applier.apply_profiles(node=updated_child_one)
    assert updated_field_names == ["things"]
    await updated_child_one.save(db=db)

    node_map = await NodeManager.get_many(
        db=db, branch=branch, ids=[child_and_thing_nodes.child_nodes[0].id], include_metadata=MetadataOptions.SOURCE
    )
    assert len(node_map) == 1
    final_child_one = node_map[child_and_thing_nodes.child_nodes[0].id]

    await _validate_node_profile_relationships(
        db=db,
        schema=child_and_thing_nodes.child_node_schema,
        original_node=updated_child_one,
        updated_node=final_child_one,
        expected_profile_relationships=[
            ExpectedProfileRelationship(
                name="things",
                peers=[child_and_thing_nodes.thing_nodes[1], child_and_thing_nodes.thing_nodes[2]],
                source_uuid="",
            )
        ],
    )


async def test_template_profile_application(
    db: InfrahubDatabase,
    criticality_schema: NodeSchema,
    criticality_low: Node,
    branch: Branch,
):
    profile_schema = registry.schema.get("ProfileTestCriticality", branch=branch)
    template_schema = registry.schema.get("TemplateTestCriticality", branch=branch)

    crit_profile_1 = await Node.init(db=db, branch=branch, schema=profile_schema)
    await crit_profile_1.new(db=db, profile_name="crit_profile_1", color="green", profile_priority=1001)
    await crit_profile_1.save(db=db)

    crit_template = await Node.init(db=db, branch=branch, schema=template_schema)
    await crit_template.new(db=db, template_name="crit_template", name="crit_template")
    await crit_template.save(db=db)

    await crit_template.profiles.update(db=db, data=[crit_profile_1])

    node_applier = NodeProfilesApplier(db=db, branch=branch)

    updated_template_field_names = await node_applier.apply_profiles(node=crit_template)
    assert updated_template_field_names == ["color"]
    await crit_template.save(db=db)

    node = await NodeManager.get_one(
        db=db,
        branch=branch,
        id=crit_template.id,
        include_metadata=MetadataQueryOptions(attribute_level=MetadataOptions.SOURCE),
    )
    assert node.id == crit_template.id
    expected_profile_attrs = [
        ExpectedProfileAttr(name="color", value="green", source_uuid=crit_profile_1.id),
    ]
    await _validate_node_profile_attrs(
        db=db,
        schema=criticality_schema,
        original_node=crit_template,
        updated_node=node,
        expected_profile_attrs=expected_profile_attrs,
    )

    # make sure field names returned by apply_profiles is idempotent for templates
    updated_field_names = await node_applier.apply_profiles(node=crit_template)
    assert updated_field_names == []


async def test_template_with_multiple_profiles(
    db: InfrahubDatabase,
    criticality_schema: NodeSchema,
    branch: Branch,
):
    """Test that templates can have multiple profiles with correct priority handling."""
    profile_schema = registry.schema.get("ProfileTestCriticality", branch=branch)
    template_schema = registry.schema.get("TemplateTestCriticality", branch=branch)

    # Create two profiles with different priorities
    crit_profile_high_priority = await Node.init(db=db, branch=branch, schema=profile_schema)
    await crit_profile_high_priority.new(
        db=db, profile_name="high_priority_profile", color="red", description="High priority", profile_priority=100
    )
    await crit_profile_high_priority.save(db=db)

    crit_profile_low_priority = await Node.init(db=db, branch=branch, schema=profile_schema)
    await crit_profile_low_priority.new(
        db=db, profile_name="low_priority_profile", color="blue", is_true=False, profile_priority=200
    )
    await crit_profile_low_priority.save(db=db)

    # Create template and assign both profiles
    crit_template = await Node.init(db=db, branch=branch, schema=template_schema)
    await crit_template.new(db=db, template_name="multi_profile_template", name="template_name")
    await crit_template.save(db=db)

    await crit_template.profiles.update(db=db, data=[crit_profile_high_priority, crit_profile_low_priority])

    node_applier = NodeProfilesApplier(db=db, branch=branch)

    updated_field_names = await node_applier.apply_profiles(node=crit_template)
    # Should update color (from high priority), description (from high priority), and is_true (from low priority)
    assert set(updated_field_names) == {"color", "description", "is_true"}
    await crit_template.save(db=db)

    # Verify the values - high priority profile should win for color
    node = await NodeManager.get_one(
        db=db,
        branch=branch,
        id=crit_template.id,
        include_metadata=MetadataQueryOptions(attribute_level=MetadataOptions.SOURCE),
    )
    expected_profile_attrs = [
        ExpectedProfileAttr(name="color", value="red", source_uuid=crit_profile_high_priority.id),
        ExpectedProfileAttr(name="description", value="High priority", source_uuid=crit_profile_high_priority.id),
        ExpectedProfileAttr(name="is_true", value=False, source_uuid=crit_profile_low_priority.id),
    ]
    await _validate_node_profile_attrs(
        db=db,
        schema=criticality_schema,
        original_node=crit_template,
        updated_node=node,
        expected_profile_attrs=expected_profile_attrs,
    )


async def test_template_profile_manual_values_precedence(
    db: InfrahubDatabase,
    criticality_schema: NodeSchema,
    branch: Branch,
):
    """Test that template's own values take precedence over profile values.

    When a template has a manually configured value, profile values should not override it.
    This ensures explicit template configuration is preserved.
    """
    profile_schema = registry.schema.get("ProfileTestCriticality", branch=branch)
    template_schema = registry.schema.get("TemplateTestCriticality", branch=branch)

    # Create a profile
    crit_profile = await Node.init(db=db, branch=branch, schema=profile_schema)
    await crit_profile.new(db=db, profile_name="override_profile", color="green", profile_priority=1001)
    await crit_profile.save(db=db)

    # Create template with its own color value
    crit_template = await Node.init(db=db, branch=branch, schema=template_schema)
    await crit_template.new(db=db, template_name="template_with_values", color="#FF0000")
    await crit_template.save(db=db)

    # Verify template has its own color initially
    assert crit_template.color.value == "#FF0000"

    # Now add profile to template
    await crit_template.profiles.update(db=db, data=[crit_profile])

    node_applier = NodeProfilesApplier(db=db, branch=branch)
    updated_field_names = await node_applier.apply_profiles(node=crit_template)
    # Template's own value should take precedence, so color should NOT be updated
    assert "color" not in updated_field_names
    await crit_template.save(db=db)

    # Template's own value should be preserved, not overridden by profile
    node = await NodeManager.get_one(
        db=db,
        branch=branch,
        id=crit_template.id,
        include_metadata=MetadataQueryOptions(attribute_level=MetadataOptions.SOURCE),
    )
    assert node.color.value == "#FF0000"
    # Source should be None since it's the template's own value
    color_source = await node.color.get_source(db=db)
    assert color_source is None


async def test_node_from_template_with_profile_precedence(
    db: InfrahubDatabase,
    criticality_schema: NodeSchema,
    branch: Branch,
):
    """Test that when creating a node from a template with profiles,
    template's manually defined values take precedence over profile values,
    while profile values are used for attributes not set on the template."""
    profile_schema = registry.schema.get("ProfileTestCriticality", branch=branch)
    template_schema = registry.schema.get("TemplateTestCriticality", branch=branch)

    # Create a profile with both color and description
    crit_profile = await Node.init(db=db, branch=branch, schema=profile_schema)
    await crit_profile.new(
        db=db, profile_name="node_profile", color="yellow", description="From profile", profile_priority=1001
    )
    await crit_profile.save(db=db)

    # Create template with only level and color (description not set, so it should come from profile)
    crit_template = await Node.init(db=db, branch=branch, schema=template_schema)
    await crit_template.new(
        db=db,
        template_name="template_for_node",
        level=5,
        color="#000000",  # Template has its own color - should take precedence over profile
    )
    await crit_template.save(db=db)

    # Assign profile to template
    await crit_template.profiles.update(db=db, data=[crit_profile])

    # Apply profiles to template
    node_applier = NodeProfilesApplier(db=db, branch=branch)
    await node_applier.apply_profiles(node=crit_template)
    await crit_template.save(db=db)

    # Create a node from this template
    node = await Node.init(db=db, branch=branch, schema=criticality_schema)
    await node.new(db=db, name="test_node", object_template={"id": crit_template.id})
    await node.save(db=db)

    # Reload node with source information
    node = await NodeManager.get_one(
        db=db, branch=branch, id=node.id, include_metadata=MetadataQueryOptions(attribute_level=MetadataOptions.SOURCE)
    )

    # Node should get level from template's manually defined value
    assert node.level.value == 5
    assert node.level.source_id == crit_template.id

    # Node should get color from template's manually defined value (not from profile)
    assert node.color.value == "#000000"
    assert node.color.source_id == crit_template.id

    # Node should get description from profile (template didn't define it)
    assert node.description.value == "From profile"
    assert node.description.source_id == crit_profile.id
