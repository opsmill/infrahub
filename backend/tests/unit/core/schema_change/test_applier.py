from dataclasses import dataclass

import pytest

from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.schema_change.applier import SchemaChangeApplier
from infrahub.core.schema_change.constants import SchemaOperationSection, SchemaOperationType
from infrahub.core.schema_change.operations import SchemaOperation
from infrahub.exceptions import SchemaOperationTargetNotFoundError
from tests.constants import TestKind
from tests.unit.core.schema_change.helpers import TAG_STATUS_ATTRIBUTE, schema_content_hashes

RELABEL_TAG = SchemaOperation(
    operation_type=SchemaOperationType.NODE_PROPERTY,
    kind=TestKind.TAG,
    property_name="label",
    value="Label",
    previous_value="Tag",
)

CHANGES_TO_THE_BASE_SCHEMA: list[SchemaOperation] = [
    RELABEL_TAG,
    SchemaOperation(
        operation_type=SchemaOperationType.ELEMENT_REMOVE,
        kind=TestKind.DEVICE,
        section=SchemaOperationSection.ATTRIBUTES,
        element_name="part_number",
    ),
    SchemaOperation(
        operation_type=SchemaOperationType.ELEMENT_ADD,
        kind=TestKind.DEVICE,
        section=SchemaOperationSection.ATTRIBUTES,
        element_name="serial",
        value={"name": "serial", "kind": "Text", "optional": True},
    ),
    SchemaOperation(
        operation_type=SchemaOperationType.ELEMENT_PROPERTY,
        kind=TestKind.DEVICE,
        section=SchemaOperationSection.ATTRIBUTES,
        element_name="weight",
        property_name="name",
        value="mass",
        previous_value="weight",
    ),
]


@pytest.fixture(scope="module", autouse=True)
def shared_schema_hashes_before_the_module(equivalence_base_schema: SchemaBranch) -> dict[str, str]:
    return schema_content_hashes(equivalence_base_schema)


@dataclass(frozen=True)
class MissingTargetCase:
    name: str
    operation: SchemaOperation
    message: str


MISSING_TARGET_CASES: list[MissingTargetCase] = [
    MissingTargetCase(
        name="property_of_a_missing_kind",
        operation=SchemaOperation(
            operation_type=SchemaOperationType.NODE_PROPERTY,
            kind="TestingMissing",
            property_name="label",
            value="Missing",
            previous_value=None,
        ),
        message=(
            r"^Schema operation 1 \(node_property\) names the kind TestingMissing, "
            r"which the schema does not have\.$"
        ),
    ),
    MissingTargetCase(
        name="removal_of_a_missing_kind",
        operation=SchemaOperation(operation_type=SchemaOperationType.NODE_REMOVE, kind="TestingMissing"),
        message=(
            r"^Schema operation 1 \(node_remove\) names the kind TestingMissing, which the schema does not have\.$"
        ),
    ),
    MissingTargetCase(
        name="attribute_added_to_a_missing_kind",
        operation=SchemaOperation(
            operation_type=SchemaOperationType.ELEMENT_ADD,
            kind="TestingMissing",
            section=SchemaOperationSection.ATTRIBUTES,
            element_name="serial",
            value={"name": "serial", "kind": "Text"},
        ),
        message=(
            r"^Schema operation 1 \(element_add\) names the kind TestingMissing, which the schema does not have\.$"
        ),
    ),
    MissingTargetCase(
        name="property_of_a_missing_attribute",
        operation=SchemaOperation(
            operation_type=SchemaOperationType.ELEMENT_PROPERTY,
            kind=TestKind.DEVICE,
            section=SchemaOperationSection.ATTRIBUTES,
            element_name="serial_number",
            property_name="label",
            value="Serial",
            previous_value="Serial Number",
        ),
        message=(
            r"^Schema operation 1 \(element_property\) names 'serial_number' in the attributes of the kind "
            r"TestingDevice, which the schema does not have\.$"
        ),
    ),
    MissingTargetCase(
        name="removal_of_a_missing_relationship",
        operation=SchemaOperation(
            operation_type=SchemaOperationType.ELEMENT_REMOVE,
            kind=TestKind.DEVICE,
            section=SchemaOperationSection.RELATIONSHIPS,
            element_name="cables",
        ),
        message=(
            r"^Schema operation 1 \(element_remove\) names 'cables' in the relationships of the kind "
            r"TestingDevice, which the schema does not have\.$"
        ),
    ),
    MissingTargetCase(
        name="relationship_named_as_an_attribute",
        operation=SchemaOperation(
            operation_type=SchemaOperationType.ELEMENT_PROPERTY,
            kind=TestKind.DEVICE,
            section=SchemaOperationSection.ATTRIBUTES,
            element_name="spare_sfps",
            property_name="label",
            value="Spares",
            previous_value=None,
        ),
        message=(
            r"^Schema operation 1 \(element_property\) names 'spare_sfps' in the attributes of the kind "
            r"TestingDevice, which the schema does not have\.$"
        ),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in MISSING_TARGET_CASES])
def test_an_operation_on_a_missing_target_is_refused(
    test_case: MissingTargetCase, equivalence_base_schema: SchemaBranch
) -> None:
    hashes_before = schema_content_hashes(equivalence_base_schema)

    with pytest.raises(SchemaOperationTargetNotFoundError, match=test_case.message):
        SchemaChangeApplier().apply(
            target_schema=equivalence_base_schema,
            operations=[RELABEL_TAG, test_case.operation],
            default_branch_schema=equivalence_base_schema,
        )

    assert schema_content_hashes(equivalence_base_schema) == hashes_before


def test_an_element_removed_by_an_earlier_operation_is_missing_for_a_later_one(
    equivalence_base_schema: SchemaBranch,
) -> None:
    operations = [
        SchemaOperation(
            operation_type=SchemaOperationType.ELEMENT_REMOVE,
            kind=TestKind.DEVICE,
            section=SchemaOperationSection.ATTRIBUTES,
            element_name="weight",
        ),
        SchemaOperation(
            operation_type=SchemaOperationType.ELEMENT_PROPERTY,
            kind=TestKind.DEVICE,
            section=SchemaOperationSection.ATTRIBUTES,
            element_name="weight",
            property_name="label",
            value="Mass",
            previous_value="Weight",
        ),
    ]

    with pytest.raises(
        SchemaOperationTargetNotFoundError,
        match=(
            r"^Schema operation 1 \(element_property\) names 'weight' in the attributes of the kind "
            r"TestingDevice, which the schema does not have\.$"
        ),
    ):
        SchemaChangeApplier().apply(
            target_schema=equivalence_base_schema, operations=operations, default_branch_schema=equivalence_base_schema
        )


def test_apply_leaves_the_target_schema_unchanged(equivalence_base_schema: SchemaBranch) -> None:
    hashes_before = schema_content_hashes(equivalence_base_schema)

    applied = SchemaChangeApplier().apply(
        target_schema=equivalence_base_schema,
        operations=CHANGES_TO_THE_BASE_SCHEMA,
        default_branch_schema=equivalence_base_schema,
    )

    assert applied.get(name=TestKind.TAG, duplicate=False).label == "Label"
    assert equivalence_base_schema.get(name=TestKind.TAG, duplicate=False).label == "Tag"
    assert equivalence_base_schema.get(name=TestKind.DEVICE, duplicate=False).local_attribute_names == [
        "name",
        "manufacturer",
        "height",
        "weight",
        "airflow",
        "part_number",
    ]
    assert schema_content_hashes(equivalence_base_schema) == hashes_before


def test_properties_that_no_operation_names_keep_their_value(equivalence_base_schema: SchemaBranch) -> None:
    operations = [
        RELABEL_TAG,
        SchemaOperation(
            operation_type=SchemaOperationType.ELEMENT_PROPERTY,
            kind=TestKind.TAG,
            section=SchemaOperationSection.ATTRIBUTES,
            element_name=TAG_STATUS_ATTRIBUTE,
            property_name="label",
            value="State",
            previous_value="Status",
        ),
    ]

    applied = SchemaChangeApplier().apply(
        target_schema=equivalence_base_schema, operations=operations, default_branch_schema=equivalence_base_schema
    )

    tag = applied.get_node(name=TestKind.TAG, duplicate=False)
    assert (tag.label, tag.generate_profile, tag.order_by, tag.default_filter) == (
        "Label",
        False,
        ["name__value"],
        "name__value",
    )
    status = tag.get_attribute(name=TAG_STATUS_ATTRIBUTE)
    assert (status.label, status.kind, status.optional) == ("State", "Dropdown", True)
    choices = status.choices or []
    assert len(choices) == 3
    assert {choice.name: choice.color for choice in choices} == {
        "active": "#2e7d32",
        "reserved": "#f9a825",
        "retired": "#c62828",
    }


def test_the_same_target_and_operations_give_the_same_hash(equivalence_base_schema: SchemaBranch) -> None:
    applier = SchemaChangeApplier()

    first = applier.apply(
        target_schema=equivalence_base_schema,
        operations=CHANGES_TO_THE_BASE_SCHEMA,
        default_branch_schema=equivalence_base_schema,
    )
    second = applier.apply(
        target_schema=equivalence_base_schema,
        operations=CHANGES_TO_THE_BASE_SCHEMA,
        default_branch_schema=equivalence_base_schema,
    )

    assert first.get_hash() != equivalence_base_schema.get_hash()
    assert second.get_hash() == first.get_hash()
    assert second.to_dict() == first.to_dict()


def test_the_shared_schema_is_unchanged_after_the_module(
    shared_schema_hashes_before_the_module: dict[str, str], equivalence_base_schema: SchemaBranch
) -> None:
    """Runs last in the module, because the tests of a module run in the order they are defined."""
    assert schema_content_hashes(equivalence_base_schema) == shared_schema_hashes_before_the_module
