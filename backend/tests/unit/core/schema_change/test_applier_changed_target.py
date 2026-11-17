from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.schema_change.applier import SchemaChangeApplier
from infrahub.core.schema_change.operation_builder import SchemaOperationBuilder
from tests.constants import TestKind
from tests.unit.core.schema_change.helpers import (
    base_generic_definition,
    base_node_definition,
    validate_candidate_schema,
)

LOOPBACK_INTERFACE_KIND = "TestingLoopbackInterface"


def _changed_separately(*, base_schema: SchemaBranch, schema_root: SchemaRoot) -> SchemaBranch:
    target = base_schema.duplicate()
    target.load_schema(schema=schema_root)
    target.process(default_branch_schema=base_schema)
    return target


def test_an_attribute_added_to_a_generic_reaches_a_kind_that_the_target_gained(
    equivalence_base_schema: SchemaBranch,
) -> None:
    loopback_interface = NodeSchema(
        name="LoopbackInterface", namespace="Testing", label="Loopback Interface", inherit_from=[TestKind.INTERFACE]
    )
    target = _changed_separately(
        base_schema=equivalence_base_schema, schema_root=SchemaRoot(nodes=[loopback_interface])
    )
    interface = base_generic_definition(TestKind.INTERFACE)
    interface.attributes.append(AttributeSchema(name="mtu", kind="Number", optional=True))
    operations = (
        SchemaOperationBuilder()
        .build(
            branch_schema=equivalence_base_schema,
            schema_root=SchemaRoot(generics=[interface]),
            default_branch_schema=equivalence_base_schema,
        )
        .operations
    )

    applied = SchemaChangeApplier().apply(
        target_schema=target, operations=operations, default_branch_schema=equivalence_base_schema
    )

    loopback_mtu = applied.get(name=LOOPBACK_INTERFACE_KIND, duplicate=False).get_attribute(name="mtu")
    assert (loopback_mtu.kind, loopback_mtu.optional, loopback_mtu.inherited) == ("Number", True, True)
    result = validate_candidate_schema(branch_schema=target, candidate_schema=applied)
    assert sorted(
        (migration.migration_name, migration.path.get_path()) for migration in result.validation.migrations
    ) == [
        ("node.attribute.add", "schema/TestingInterface/mtu"),
        ("node.attribute.add", "schema/TestingLoopbackInterface/mtu"),
        ("node.attribute.add", "schema/TestingPhysicalInterface/mtu"),
        ("node.attribute.add", "schema/TestingVirtualInterface/mtu"),
    ]


def test_a_label_change_keeps_a_change_that_the_target_made_to_the_same_kind(
    equivalence_base_schema: SchemaBranch,
) -> None:
    relabelled_device = base_node_definition(TestKind.DEVICE)
    relabelled_device.label = "Chassis"
    target = _changed_separately(base_schema=equivalence_base_schema, schema_root=SchemaRoot(nodes=[relabelled_device]))
    device = base_node_definition(TestKind.DEVICE)
    device.get_attribute(name="manufacturer").label = "Maker"
    operations = (
        SchemaOperationBuilder()
        .build(
            branch_schema=equivalence_base_schema,
            schema_root=SchemaRoot(nodes=[device]),
            default_branch_schema=equivalence_base_schema,
        )
        .operations
    )

    applied = SchemaChangeApplier().apply(
        target_schema=target, operations=operations, default_branch_schema=equivalence_base_schema
    )

    applied_device = applied.get(name=TestKind.DEVICE, duplicate=False)
    assert (applied_device.label, applied_device.get_attribute(name="manufacturer").label) == ("Chassis", "Maker")
