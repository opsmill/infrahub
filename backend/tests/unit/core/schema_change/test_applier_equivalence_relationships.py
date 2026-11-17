import pytest

from infrahub.core.constants import HashableModelState, RelationshipCardinality, RelationshipKind
from infrahub.core.schema import RelationshipSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.schema_change.applier import SchemaChangeApplier
from infrahub.core.schema_change.operation_builder import SchemaOperationBuilder
from tests.constants import TestKind
from tests.unit.core.schema_change.helpers import (
    DEVICE_SPARE_SFPS_RELATIONSHIP,
    EquivalenceCase,
    assert_same_load_result,
    base_node_definition,
    build_direct_load_result,
    schema_element_id,
    validate_candidate_schema,
)


def _add_relationship(_: SchemaBranch) -> SchemaRoot:
    virtual_interface = base_node_definition(TestKind.VIRTUAL_INTERFACE)
    virtual_interface.relationships.append(
        RelationshipSchema(
            name="parent_interface",
            peer=TestKind.PHYSICAL_INTERFACE,
            kind=RelationshipKind.GENERIC,
            cardinality=RelationshipCardinality.ONE,
            optional=True,
        )
    )
    return SchemaRoot(nodes=[virtual_interface])


def _remove_relationship(_: SchemaBranch) -> SchemaRoot:
    sfp = base_node_definition(TestKind.SFP)
    sfp.get_relationship(name="interface").state = HashableModelState.ABSENT
    return SchemaRoot(nodes=[sfp])


def _rename_relationship(schema: SchemaBranch) -> SchemaRoot:
    physical_interface = base_node_definition(TestKind.PHYSICAL_INTERFACE)
    sfp = physical_interface.get_relationship(name="sfp")
    sfp.id = schema_element_id(schema, TestKind.PHYSICAL_INTERFACE, "sfp")
    sfp.name = "transceiver"
    return SchemaRoot(nodes=[physical_interface])


def _change_relationship_peer(_: SchemaBranch) -> SchemaRoot:
    sfp = base_node_definition(TestKind.SFP)
    sfp.get_relationship(name="interface").peer = TestKind.INTERFACE
    return SchemaRoot(nodes=[sfp])


def _change_relationship_cardinality(_: SchemaBranch) -> SchemaRoot:
    physical_interface = base_node_definition(TestKind.PHYSICAL_INTERFACE)
    physical_interface.get_relationship(name="sfp").cardinality = RelationshipCardinality.MANY
    return SchemaRoot(nodes=[physical_interface])


def _change_relationship_optional(_: SchemaBranch) -> SchemaRoot:
    device = base_node_definition(TestKind.DEVICE)
    device.get_relationship(name=DEVICE_SPARE_SFPS_RELATIONSHIP).optional = False
    return SchemaRoot(nodes=[device])


def _change_relationship_kind(_: SchemaBranch) -> SchemaRoot:
    physical_interface = base_node_definition(TestKind.PHYSICAL_INTERFACE)
    physical_interface.get_relationship(name="sfp").kind = RelationshipKind.GENERIC
    return SchemaRoot(nodes=[physical_interface])


RELATIONSHIP_EQUIVALENCE_CASES: list[EquivalenceCase] = [
    EquivalenceCase(name="add_relationship", schema_file=_add_relationship),
    EquivalenceCase(name="remove_relationship", schema_file=_remove_relationship),
    EquivalenceCase(name="rename_relationship", schema_file=_rename_relationship),
    EquivalenceCase(name="change_relationship_peer", schema_file=_change_relationship_peer),
    EquivalenceCase(name="change_relationship_cardinality", schema_file=_change_relationship_cardinality),
    EquivalenceCase(name="change_relationship_optional", schema_file=_change_relationship_optional),
    EquivalenceCase(name="change_relationship_kind", schema_file=_change_relationship_kind),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in RELATIONSHIP_EQUIVALENCE_CASES])
def test_applied_relationship_operations_give_the_direct_load_result(
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
