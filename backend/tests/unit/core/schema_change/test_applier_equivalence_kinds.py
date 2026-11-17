import pytest

from infrahub.core.constants import HashableModelState, InfrahubKind
from infrahub.core.schema import SchemaRoot
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


def _rename_kind(schema: SchemaBranch) -> SchemaRoot:
    tag = base_node_definition(TestKind.TAG)
    tag.id = schema_element_id(schema, TestKind.TAG)
    tag.name = "Label"
    return SchemaRoot(nodes=[tag])


def _change_kind_namespace(schema: SchemaBranch) -> SchemaRoot:
    tag = base_node_definition(TestKind.TAG)
    tag.id = schema_element_id(schema, TestKind.TAG)
    tag.namespace = "Inventory"
    return SchemaRoot(nodes=[tag])


def _add_generic_to_inherit_from(_: SchemaBranch) -> SchemaRoot:
    virtual_interface = base_node_definition(TestKind.VIRTUAL_INTERFACE)
    virtual_interface.inherit_from = [*virtual_interface.inherit_from, InfrahubKind.LINEAGESOURCE]
    return SchemaRoot(nodes=[virtual_interface])


def _remove_generic(_: SchemaBranch) -> SchemaRoot:
    interface_holder = base_generic_definition(TestKind.INTERFACE_HOLDER)
    interface_holder.state = HashableModelState.ABSENT
    interface = base_generic_definition(TestKind.INTERFACE)
    interface.get_relationship(name="device").peer = TestKind.DEVICE
    device = base_node_definition(TestKind.DEVICE)
    device.inherit_from = []
    return SchemaRoot(generics=[interface_holder, interface], nodes=[device])


KIND_EQUIVALENCE_CASES: list[EquivalenceCase] = [
    EquivalenceCase(name="rename_kind", schema_file=_rename_kind),
    EquivalenceCase(name="change_kind_namespace", schema_file=_change_kind_namespace),
    EquivalenceCase(name="add_generic_to_inherit_from", schema_file=_add_generic_to_inherit_from),
    EquivalenceCase(name="remove_generic", schema_file=_remove_generic),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in KIND_EQUIVALENCE_CASES])
def test_applied_kind_operations_give_the_direct_load_result(
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
