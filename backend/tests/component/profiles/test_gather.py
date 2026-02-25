from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType
from infrahub.core.initialization import create_branch
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.events.node_action import NodeUpdatedEvent
from infrahub.profiles.gather import gather_trigger_profile_refresh


async def test_gather_trigger_profile_refresh_core_models(
    register_core_models_schema: SchemaBranch, default_branch: Branch
) -> None:
    """Test that triggers are created for core model profiles that have trigger fields."""
    triggers = await gather_trigger_profile_refresh()

    # We have builtin kinds that have corresponding profiles
    assert [t.profile_kind for t in triggers] == [
        "ProfileBuiltinTag",
        "ProfileIpamNamespace",
        "ProfileBuiltinIPPrefix",
        "ProfileBuiltinIPAddress",
    ]

    trigger_events: set[str] = set()
    for trigger in triggers:
        trigger_events.update(trigger.trigger.events)
    assert trigger_events == {NodeUpdatedEvent.event_name}


async def test_gather_trigger_profile_refresh_with_attributes(
    db: InfrahubDatabase, default_branch: Branch, profile_schema_with_attributes: None
) -> None:
    """Test that triggers are created for profile schemas with attributes."""
    triggers = await gather_trigger_profile_refresh()

    profile_triggers = [t for t in triggers if t.profile_kind == "ProfileTestDevice"]
    assert len(profile_triggers) == 1

    trigger = profile_triggers[0]
    assert trigger.name == "ProfileTestDevice::refresh"
    assert trigger.generate_name() == "profile::main::ProfileTestDevice::refresh"
    assert trigger.trigger.events == {NodeUpdatedEvent.event_name}
    assert trigger.trigger.match == {"infrahub.node.kind": "ProfileTestDevice"}

    assert "infrahub.field.name" in trigger.trigger.match_related
    trigger_fields = trigger.trigger.match_related["infrahub.field.name"]
    assert "description" in trigger_fields
    assert "status" in trigger_fields
    assert "profile_priority" in trigger_fields
    assert "profile_name" not in trigger_fields
    assert "related_nodes" not in trigger_fields

    assert "prefect.resource.role" in trigger.trigger.match_related
    assert "infrahub.node.attribute_update" in trigger.trigger.match_related["prefect.resource.role"]
    assert "infrahub.node.relationship_update" in trigger.trigger.match_related["prefect.resource.role"]

    assert "infrahub.branch.name" not in trigger.trigger.match


async def test_gather_trigger_profile_refresh_with_generic_relationship(
    db: InfrahubDatabase, default_branch: Branch, profile_schema_with_generic_relationship: None
) -> None:
    """Test that triggers include generic relationships."""
    triggers = await gather_trigger_profile_refresh()

    profile_triggers = [t for t in triggers if t.profile_kind == "ProfileTestDevice"]
    assert len(profile_triggers) == 1

    trigger = profile_triggers[0]
    trigger_fields = trigger.trigger.match_related["infrahub.field.name"]

    assert "role" in trigger_fields
    assert "description" in trigger_fields
    assert "related_nodes" not in trigger_fields


async def test_gather_trigger_profile_refresh_with_attribute_relationship(
    db: InfrahubDatabase, default_branch: Branch, profile_schema_with_attribute_relationship: None
) -> None:
    """Test that triggers include attribute relationships."""
    triggers = await gather_trigger_profile_refresh()

    profile_triggers = [t for t in triggers if t.profile_kind == "ProfileTestDevice"]
    assert len(profile_triggers) == 1

    trigger = profile_triggers[0]
    trigger_fields = trigger.trigger.match_related["infrahub.field.name"]

    assert "location" in trigger_fields
    assert "description" in trigger_fields


async def test_gather_trigger_profile_refresh_different_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    data_schema: None,
    node_group_schema: None,
) -> None:
    """Test that branch-specific triggers are created when schema differs across branches."""
    SCHEMA = SchemaRoot(
        nodes=[
            NodeSchema(
                name="Device",
                namespace="Test",
                branch=BranchSupportType.AWARE.value,
                attributes=[
                    AttributeSchema(name="name", kind="Text", unique=True),
                    AttributeSchema(name="description", kind="Text", optional=True),
                ],
            ),
        ]
    )

    registry.schema.register_schema(schema=SCHEMA, branch=default_branch.name)
    registry.schema.process_schema_branch(name=default_branch.name)
    default_branch.update_schema_hash()
    await default_branch.save(db=db)

    branch = await create_branch(branch_name="branch2", db=db)

    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    device_schema = schema_branch.get_node("TestDevice")

    device_schema.attributes.append(AttributeSchema(name="status", kind="Text", optional=True))
    schema_branch.set(name="TestDevice", schema=device_schema)
    registry.schema.set_schema_branch(name=branch.name, schema=schema_branch)
    branch.update_schema_hash()
    schema_branch.process()
    await branch.save(db=db)

    name_main = "profile::main::ProfileTestDevice::refresh"
    name_branch = "profile::branch2::ProfileTestDevice::refresh"

    triggers = await gather_trigger_profile_refresh()
    triggers_by_name = {trigger.generate_name(): trigger for trigger in triggers}

    assert name_main in triggers_by_name
    assert name_branch in triggers_by_name

    trigger_main = triggers_by_name[name_main]
    assert "infrahub.branch.name" in trigger_main.trigger.match
    assert trigger_main.trigger.match["infrahub.branch.name"] == ["!branch2"]

    trigger_branch = triggers_by_name[name_branch]
    assert "infrahub.branch.name" in trigger_branch.trigger.match
    assert trigger_branch.trigger.match["infrahub.branch.name"] == "branch2"
