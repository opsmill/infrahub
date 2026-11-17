import pytest

from infrahub.core.constants import HashableModelState, RelationshipCardinality, RelationshipKind
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.schema_change.applier import SchemaChangeApplier
from infrahub.core.schema_change.operation_builder import SchemaOperationBuilder
from tests.constants import TestKind
from tests.unit.core.schema_change.helpers import (
    EquivalenceCase,
    assert_same_load_result,
    base_generic_definition,
    base_node_definition,
    build_direct_load_result,
    schema_element_id,
    validate_candidate_schema,
)


def _add_attribute_to_generic(_: SchemaBranch) -> SchemaRoot:
    interface = base_generic_definition(TestKind.INTERFACE)
    interface.attributes.append(AttributeSchema(name="mtu", kind="Number", optional=True))
    return SchemaRoot(generics=[interface])


def _turn_on_generate_profile(_: SchemaBranch) -> SchemaRoot:
    tag = base_node_definition(TestKind.TAG)
    tag.generate_profile = True
    return SchemaRoot(nodes=[tag])


def _make_attribute_unique(_: SchemaBranch) -> SchemaRoot:
    device = base_node_definition(TestKind.DEVICE)
    device.get_attribute(name="part_number").unique = True
    return SchemaRoot(nodes=[device])


def _remove_attribute(_: SchemaBranch) -> SchemaRoot:
    device = base_node_definition(TestKind.DEVICE)
    device.get_attribute(name="weight").state = HashableModelState.ABSENT
    return SchemaRoot(nodes=[device])


def _rename_attribute_on_node(schema: SchemaBranch) -> SchemaRoot:
    device = base_node_definition(TestKind.DEVICE)
    weight = device.get_attribute(name="weight")
    weight.id = schema_element_id(schema, TestKind.DEVICE, "weight")
    weight.name = "mass"
    return SchemaRoot(nodes=[device])


def _rename_attribute_on_generic(schema: SchemaBranch) -> SchemaRoot:
    interface = base_generic_definition(TestKind.INTERFACE)
    enabled = interface.get_attribute(name="enabled")
    enabled.id = schema_element_id(schema, TestKind.INTERFACE, "enabled")
    enabled.name = "admin_enabled"
    return SchemaRoot(generics=[interface])


def _add_node(_: SchemaBranch) -> SchemaRoot:
    cable = NodeSchema(
        name="Cable",
        namespace="Testing",
        label="Cable",
        human_friendly_id=["label__value"],
        attributes=[
            AttributeSchema(name="label", kind="Text", unique=True),
            AttributeSchema(name="length", kind="Number", optional=True),
        ],
        relationships=[
            RelationshipSchema(
                name="endpoints",
                peer=TestKind.PHYSICAL_INTERFACE,
                kind=RelationshipKind.GENERIC,
                cardinality=RelationshipCardinality.MANY,
                optional=True,
            )
        ],
    )
    return SchemaRoot(nodes=[cable])


APPLIER_EQUIVALENCE_CASES: list[EquivalenceCase] = [
    EquivalenceCase(name="add_attribute_to_generic", schema_file=_add_attribute_to_generic),
    EquivalenceCase(name="turn_on_generate_profile", schema_file=_turn_on_generate_profile),
    EquivalenceCase(name="make_attribute_unique", schema_file=_make_attribute_unique),
    EquivalenceCase(name="remove_attribute", schema_file=_remove_attribute),
    EquivalenceCase(name="rename_attribute_on_node", schema_file=_rename_attribute_on_node),
    EquivalenceCase(name="rename_attribute_on_generic", schema_file=_rename_attribute_on_generic),
    EquivalenceCase(name="add_node", schema_file=_add_node),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in APPLIER_EQUIVALENCE_CASES])
def test_applied_operations_give_the_direct_load_result(
    test_case: EquivalenceCase, equivalence_base_schema: SchemaBranch
) -> None:
    expected = build_direct_load_result(
        branch_schema=equivalence_base_schema,
        schema_root=test_case.schema_file(equivalence_base_schema),
        default_branch_schema=equivalence_base_schema,
    )
    assert expected.validation.diff.all, "the schema file of the case must change the schema"

    build_result = SchemaOperationBuilder().build(
        branch_schema=equivalence_base_schema,
        schema_root=test_case.schema_file(equivalence_base_schema),
        default_branch_schema=equivalence_base_schema,
    )
    applied_schema = SchemaChangeApplier().apply(
        target_schema=equivalence_base_schema,
        operations=build_result.operations,
        default_branch_schema=equivalence_base_schema,
    )
    actual = validate_candidate_schema(branch_schema=equivalence_base_schema, candidate_schema=applied_schema)

    assert_same_load_result(expected=expected, actual=actual)
