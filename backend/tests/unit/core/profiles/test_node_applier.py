from dataclasses import dataclass
from typing import Any

from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.database import InfrahubDatabase
from infrahub.profiles.node_applier import NodeProfilesApplier


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
):
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
):
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
):
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

    # TODO: Fix profile assignment to template
    await crit_template.profiles.update(db=db, data=[crit_profile_1])

    node_applier = NodeProfilesApplier(db=db, branch=branch)

    updated_template_field_names = await node_applier.apply_profiles(node=crit_template)
    assert updated_template_field_names == ["color"]
    await crit_template.save(db=db)

    node = await NodeManager.get_one(db=db, branch=branch, id=crit_template.id, include_source=True)
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
