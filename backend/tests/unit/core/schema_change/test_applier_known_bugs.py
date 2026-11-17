import pytest

from infrahub.core.constants import RelationshipDeleteBehavior, RelationshipKind
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.schema_change.applier import SchemaChangeApplier
from infrahub.core.schema_change.operation_builder import SchemaOperationBuilder
from tests.constants import TestKind
from tests.unit.core.schema_change.helpers import (
    DEVICE_SPARE_SFPS_RELATIONSHIP,
    SchemaLoadResult,
    base_generic_definition,
    base_node_definition,
    schema_element_id,
    validate_candidate_schema,
)


def _load_through_operations(*, branch_schema: SchemaBranch, schema_root: SchemaRoot) -> SchemaLoadResult:
    build_result = SchemaOperationBuilder().build(
        branch_schema=branch_schema, schema_root=schema_root, default_branch_schema=branch_schema
    )
    applied_schema = SchemaChangeApplier().apply(
        target_schema=branch_schema, operations=build_result.operations, default_branch_schema=branch_schema
    )
    return validate_candidate_schema(branch_schema=branch_schema, candidate_schema=applied_schema)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "processing makes an attribute unique again from the uniqueness constraint and the human friendly ID "
        "that were calculated from it, so the processed diff is empty and the load records no change"
    ),
)
def test_turning_unique_off_removes_the_calculated_uniqueness_constraint(
    equivalence_base_schema: SchemaBranch,
) -> None:
    device_before = equivalence_base_schema.get(name=TestKind.DEVICE, duplicate=False)
    assert device_before.get_attribute(name="name").unique is True
    assert device_before.uniqueness_constraints == [["name__value"]]

    device = base_node_definition(TestKind.DEVICE)
    device.get_attribute(name="name").unique = False

    result = _load_through_operations(branch_schema=equivalence_base_schema, schema_root=SchemaRoot(nodes=[device]))

    device_after = result.schema.get(name=TestKind.DEVICE, duplicate=False)
    assert device_after.get_attribute(name="name").unique is False
    assert (device_after.uniqueness_constraints or []) == []


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "processing fills on_delete only when it is empty, and a relationship keeps the on_delete that was "
        "calculated for its earlier kind"
    ),
)
def test_a_relationship_changed_to_component_without_on_delete_cascades(
    equivalence_base_schema: SchemaBranch,
) -> None:
    relationship_before = equivalence_base_schema.get(name=TestKind.DEVICE, duplicate=False).get_relationship(
        name=DEVICE_SPARE_SFPS_RELATIONSHIP
    )
    assert relationship_before.kind == RelationshipKind.GENERIC
    assert relationship_before.on_delete == RelationshipDeleteBehavior.NO_ACTION

    device = base_node_definition(TestKind.DEVICE)
    device.get_relationship(name=DEVICE_SPARE_SFPS_RELATIONSHIP).kind = RelationshipKind.COMPONENT

    result = _load_through_operations(branch_schema=equivalence_base_schema, schema_root=SchemaRoot(nodes=[device]))

    relationship_after = result.schema.get(name=TestKind.DEVICE, duplicate=False).get_relationship(
        name=DEVICE_SPARE_SFPS_RELATIONSHIP
    )
    assert relationship_after.kind == RelationshipKind.COMPONENT
    assert relationship_after.on_delete == RelationshipDeleteBehavior.CASCADE


def test_a_relationship_changed_to_component_keeps_the_on_delete_of_the_file(
    equivalence_base_schema: SchemaBranch,
) -> None:
    device = base_node_definition(TestKind.DEVICE)
    spare_sfps = device.get_relationship(name=DEVICE_SPARE_SFPS_RELATIONSHIP)
    spare_sfps.kind = RelationshipKind.COMPONENT
    spare_sfps.on_delete = RelationshipDeleteBehavior.NO_ACTION

    result = _load_through_operations(branch_schema=equivalence_base_schema, schema_root=SchemaRoot(nodes=[device]))

    relationship_after = result.schema.get(name=TestKind.DEVICE, duplicate=False).get_relationship(
        name=DEVICE_SPARE_SFPS_RELATIONSHIP
    )
    assert relationship_after.kind == RelationshipKind.COMPONENT
    assert relationship_after.on_delete == RelationshipDeleteBehavior.NO_ACTION


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "a rename on a generic creates its migration on the generic only, and the profile nodes of the kinds "
        "that inherit the generic do not carry the label of the generic's profile kind"
    ),
)
def test_a_rename_on_a_generic_migrates_the_profiles_of_the_inheriting_kinds(
    equivalence_base_schema: SchemaBranch,
) -> None:
    interface = base_generic_definition(TestKind.INTERFACE)
    enabled = interface.get_attribute(name="enabled")
    enabled.id = schema_element_id(equivalence_base_schema, TestKind.INTERFACE, "enabled")
    enabled.name = "admin_enabled"

    result = _load_through_operations(
        branch_schema=equivalence_base_schema, schema_root=SchemaRoot(generics=[interface])
    )

    assert sorted(
        (migration.migration_name, migration.path.get_path()) for migration in result.validation.migrations
    ) == [
        ("attribute.name.update", "schema/ProfileTestingPhysicalInterface/admin_enabled/name"),
        ("attribute.name.update", "schema/ProfileTestingVirtualInterface/admin_enabled/name"),
        ("attribute.name.update", "schema/TestingInterface/admin_enabled/name"),
    ]


@pytest.mark.xfail(
    strict=True,
    raises=ValueError,
    reason=(
        "the inheritance check compares the generic's new kind with the old kind of the copy on each "
        "inheriting kind, so a kind change written on the generic alone is refused"
    ),
)
def test_an_attribute_kind_change_on_a_generic_alone_reaches_the_inheriting_kinds(
    equivalence_base_schema: SchemaBranch,
) -> None:
    interface = base_generic_definition(TestKind.INTERFACE)
    interface.get_attribute(name="name").kind = "TextArea"

    result = _load_through_operations(
        branch_schema=equivalence_base_schema, schema_root=SchemaRoot(generics=[interface])
    )

    assert {
        kind: result.schema.get(name=kind, duplicate=False).get_attribute(name="name").kind
        for kind in (TestKind.INTERFACE, TestKind.PHYSICAL_INTERFACE, TestKind.VIRTUAL_INTERFACE)
    } == {
        TestKind.INTERFACE: "TextArea",
        TestKind.PHYSICAL_INTERFACE: "TextArea",
        TestKind.VIRTUAL_INTERFACE: "TextArea",
    }
