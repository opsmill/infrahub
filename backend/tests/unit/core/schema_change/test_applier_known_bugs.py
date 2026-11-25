import pytest

from infrahub.core.constants import RelationshipDeleteBehavior, RelationshipKind
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.schema_change.applier import SchemaChangeApplier
from infrahub.core.schema_change.operation_builder import SchemaOperationBuilder
from tests.constants import TestKind
from tests.unit.core.schema_change.equivalence_cases import (
    CHANGE_RELATIONSHIP_TO_COMPONENT,
    CHANGE_RELATIONSHIP_TO_COMPONENT_WITH_ON_DELETE,
    RENAME_ATTRIBUTE_ON_GENERIC_WITH_PROFILES,
    TURN_UNIQUE_OFF,
)
from tests.unit.core.schema_change.helpers import (
    DEVICE_SPARE_SFPS_RELATIONSHIP,
    CombinedLoad,
    SchemaLoadResult,
    base_generic_definition,
    summarize_load_result,
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
def test_turning_unique_off_removes_the_calculated_uniqueness_constraint(combined_load: CombinedLoad) -> None:
    device_kind = TURN_UNIQUE_OFF.scope.kind(TestKind.DEVICE)
    device_before = combined_load.base.get(name=device_kind, duplicate=False)
    assert device_before.get_attribute(name="name").unique is True
    assert device_before.uniqueness_constraints == [["name__value"]]

    device_after = combined_load.actual.schema.get(name=device_kind, duplicate=False)
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
def test_a_relationship_changed_to_component_without_on_delete_cascades(combined_load: CombinedLoad) -> None:
    device_kind = CHANGE_RELATIONSHIP_TO_COMPONENT.scope.kind(TestKind.DEVICE)
    relationship_before = combined_load.base.get(name=device_kind, duplicate=False).get_relationship(
        name=DEVICE_SPARE_SFPS_RELATIONSHIP
    )
    assert relationship_before.kind == RelationshipKind.GENERIC
    assert relationship_before.on_delete == RelationshipDeleteBehavior.NO_ACTION

    relationship_after = combined_load.actual.schema.get(name=device_kind, duplicate=False).get_relationship(
        name=DEVICE_SPARE_SFPS_RELATIONSHIP
    )
    assert relationship_after.kind == RelationshipKind.COMPONENT
    assert relationship_after.on_delete == RelationshipDeleteBehavior.CASCADE


def test_a_relationship_changed_to_component_keeps_the_on_delete_of_the_file(combined_load: CombinedLoad) -> None:
    device_kind = CHANGE_RELATIONSHIP_TO_COMPONENT_WITH_ON_DELETE.scope.kind(TestKind.DEVICE)

    relationship_after = combined_load.actual.schema.get(name=device_kind, duplicate=False).get_relationship(
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
def test_a_rename_on_a_generic_migrates_the_profiles_of_the_inheriting_kinds(combined_load: CombinedLoad) -> None:
    case = RENAME_ATTRIBUTE_ON_GENERIC_WITH_PROFILES
    owned_kinds = case.owned_kinds(base_schema=combined_load.base, result_schema=combined_load.actual.schema)

    assert summarize_load_result(combined_load.actual, kinds=owned_kinds).migrations == [
        ("attribute.name.update", "schema/ProfileInheritedrenamePhysicalInterface/admin_enabled/name"),
        ("attribute.name.update", "schema/ProfileInheritedrenameVirtualInterface/admin_enabled/name"),
        ("attribute.name.update", "schema/InheritedrenameInterface/admin_enabled/name"),
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
