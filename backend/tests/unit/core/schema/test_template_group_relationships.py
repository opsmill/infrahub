import pytest

from infrahub.core.constants import InfrahubKind, RelationshipCardinality, RelationshipKind
from infrahub.core.schema import SchemaRoot, core_models
from infrahub.core.schema.schema_branch import SchemaBranch
from tests.constants import TestKind
from tests.helpers.schema.device import DEVICE, INTERFACE, INTERFACE_HOLDER


@pytest.fixture
def device_schema_branch() -> SchemaBranch:
    schema_branch = SchemaBranch(cache={}, name="test")
    schema = SchemaRoot(generics=[INTERFACE_HOLDER, INTERFACE], nodes=[DEVICE])
    schema_branch.load_schema(schema=SchemaRoot(**core_models).merge(schema=schema))
    schema_branch.process()
    return schema_branch


async def test_template_keeps_member_of_groups(device_schema_branch: SchemaBranch) -> None:
    device_template = device_schema_branch.get_template(name=f"Template{TestKind.DEVICE}", duplicate=False)

    member_rel = device_template.get_relationship(name="member_of_groups")
    assert member_rel.kind == RelationshipKind.GROUP
    assert member_rel.identifier == "group_member"

    subscriber_rel = device_template.get_relationship(name="subscriber_of_groups")
    assert subscriber_rel.kind == RelationshipKind.GROUP
    assert subscriber_rel.identifier == "group_subscriber"


async def test_template_gets_for_instances_group_relationships(device_schema_branch: SchemaBranch) -> None:
    device_template = device_schema_branch.get_template(name=f"Template{TestKind.DEVICE}", duplicate=False)

    member_rel = device_template.get_relationship(name="member_of_groups_for_instances")
    assert member_rel.peer == InfrahubKind.GENERICGROUP
    assert member_rel.kind == RelationshipKind.GENERIC
    assert member_rel.cardinality == RelationshipCardinality.MANY
    assert member_rel.optional is True

    subscriber_rel = device_template.get_relationship(name="subscriber_of_groups_for_instances")
    assert subscriber_rel.peer == InfrahubKind.GENERICGROUP
    assert subscriber_rel.kind == RelationshipKind.GENERIC
    assert subscriber_rel.cardinality == RelationshipCardinality.MANY
    assert subscriber_rel.optional is True


async def test_regular_node_does_not_get_for_instances_relationships(device_schema_branch: SchemaBranch) -> None:
    device = device_schema_branch.get_node(name=TestKind.DEVICE, duplicate=False)
    assert "member_of_groups" in device.relationship_names
    assert "subscriber_of_groups" in device.relationship_names
    assert "member_of_groups_for_instances" not in device.relationship_names
    assert "subscriber_of_groups_for_instances" not in device.relationship_names
