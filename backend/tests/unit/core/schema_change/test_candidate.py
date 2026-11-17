from collections.abc import Callable
from dataclasses import dataclass

import pytest

from infrahub.core.constants import HashableModelState
from infrahub.core.schema import DropdownChoice, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.schema_change.constants import SchemaOperationSection, SchemaOperationType
from infrahub.core.schema_change.factory import build_schema_candidate_builder
from infrahub.core.schema_change.operations import SchemaOperation
from tests.constants import TestKind
from tests.unit.core.schema_change.helpers import (
    TAG_STATUS_ATTRIBUTE,
    SchemaLoadResult,
    base_node_definition,
    build_base_schema_root,
    summarize_load_result,
)

TAG_STATUS_CHOICES_BEFORE: list[dict[str, str]] = [
    {"name": "active", "color": "#2e7d32"},
    {"name": "reserved", "color": "#f9a825"},
    {"name": "retired", "color": "#c62828"},
]
DEVICE_AIRFLOW_ENUM_BEFORE = [
    "Front to rear",
    "Rear to front",
    "Left to right",
    "Right to left",
    "Side to rear",
    "Rear to side",
    "Bottom to top",
    "Top to bottom",
    "Passive",
    "Mixed",
]


@dataclass(frozen=True)
class CandidateCase:
    name: str
    schema_file: Callable[[], SchemaRoot]
    operations: list[SchemaOperation]
    """The operations of the same change, written by hand."""

    expected_changed_kinds: list[str]
    expected_migrations: list[tuple[str, str]]
    expected_constraints: list[tuple[str, str]]


def _add_dropdown_choice() -> SchemaRoot:
    tag = base_node_definition(TestKind.TAG)
    status = tag.get_attribute(name=TAG_STATUS_ATTRIBUTE)
    status.choices = [*(status.choices or []), DropdownChoice(name="planned", color="#1565c0")]
    return SchemaRoot(nodes=[tag])


def _add_enum_value() -> SchemaRoot:
    device = base_node_definition(TestKind.DEVICE)
    device.get_attribute(name="airflow").enum = [*DEVICE_AIRFLOW_ENUM_BEFORE, "Unknown"]
    return SchemaRoot(nodes=[device])


def _relabel_attribute() -> SchemaRoot:
    device = base_node_definition(TestKind.DEVICE)
    device.get_attribute(name="manufacturer").label = "Maker"
    return SchemaRoot(nodes=[device])


def _remove_attribute() -> SchemaRoot:
    device = base_node_definition(TestKind.DEVICE)
    device.get_attribute(name="weight").state = HashableModelState.ABSENT
    return SchemaRoot(nodes=[device])


CANDIDATE_CASES = [
    CandidateCase(
        name="dropdown_choice_added",
        schema_file=_add_dropdown_choice,
        operations=[
            SchemaOperation(
                operation_type=SchemaOperationType.ELEMENT_PROPERTY,
                kind=TestKind.TAG,
                section=SchemaOperationSection.ATTRIBUTES,
                element_name=TAG_STATUS_ATTRIBUTE,
                property_name="choices",
                value=[*TAG_STATUS_CHOICES_BEFORE, {"name": "planned", "color": "#1565c0"}],
                previous_value=TAG_STATUS_CHOICES_BEFORE,
            )
        ],
        expected_changed_kinds=[TestKind.TAG],
        expected_migrations=[],
        expected_constraints=[("attribute.choices.update", "schema/TestingTag/status/choices")],
    ),
    CandidateCase(
        name="enum_value_added",
        schema_file=_add_enum_value,
        operations=[
            SchemaOperation(
                operation_type=SchemaOperationType.ELEMENT_PROPERTY,
                kind=TestKind.DEVICE,
                section=SchemaOperationSection.ATTRIBUTES,
                element_name="airflow",
                property_name="enum",
                value=[*DEVICE_AIRFLOW_ENUM_BEFORE, "Unknown"],
                previous_value=DEVICE_AIRFLOW_ENUM_BEFORE,
            )
        ],
        expected_changed_kinds=[TestKind.DEVICE],
        expected_migrations=[],
        expected_constraints=[("attribute.enum.update", "schema/TestingDevice/airflow/enum")],
    ),
    CandidateCase(
        name="attribute_label_changed",
        schema_file=_relabel_attribute,
        operations=[
            SchemaOperation(
                operation_type=SchemaOperationType.ELEMENT_PROPERTY,
                kind=TestKind.DEVICE,
                section=SchemaOperationSection.ATTRIBUTES,
                element_name="manufacturer",
                property_name="label",
                value="Maker",
                previous_value="Manufacturer",
            )
        ],
        expected_changed_kinds=[TestKind.DEVICE],
        expected_migrations=[],
        expected_constraints=[],
    ),
    CandidateCase(
        name="attribute_removed",
        schema_file=_remove_attribute,
        operations=[
            SchemaOperation(
                operation_type=SchemaOperationType.ELEMENT_REMOVE,
                kind=TestKind.DEVICE,
                section=SchemaOperationSection.ATTRIBUTES,
                element_name="weight",
            )
        ],
        expected_changed_kinds=[TestKind.DEVICE],
        expected_migrations=[("node.attribute.remove", "schema/TestingDevice/weight")],
        expected_constraints=[("node.attribute.remove", "schema/TestingDevice/weight")],
    ),
]


@pytest.mark.parametrize("test_case", CANDIDATE_CASES, ids=lambda case: case.name)
def test_a_schema_file_and_its_operations_give_the_same_candidate(
    equivalence_base_schema: SchemaBranch, test_case: CandidateCase
) -> None:
    builder = build_schema_candidate_builder()

    from_file = builder.from_schema_root(
        branch_schema=equivalence_base_schema,
        schema_root=test_case.schema_file(),
        default_branch_schema=equivalence_base_schema,
    )
    from_operations = builder.from_operations(
        branch_schema=equivalence_base_schema,
        operations=test_case.operations,
        default_branch_schema=equivalence_base_schema,
    )

    file_summary = summarize_load_result(SchemaLoadResult(schema=from_file.schema, validation=from_file.validation))
    operations_summary = summarize_load_result(
        SchemaLoadResult(schema=from_operations.schema, validation=from_operations.validation)
    )
    assert from_operations.validation.diff.model_dump() == from_file.validation.diff.model_dump()
    assert sorted(from_file.validation.diff.changed) == test_case.expected_changed_kinds
    assert (file_summary.migrations, file_summary.constraints) == (
        test_case.expected_migrations,
        test_case.expected_constraints,
    )
    assert (operations_summary.migrations, operations_summary.constraints) == (
        test_case.expected_migrations,
        test_case.expected_constraints,
    )
    assert operations_summary.kind_hashes == file_summary.kind_hashes
    assert (from_file.validation.errors, from_operations.validation.errors) == ([], [])


def test_a_file_that_changes_nothing_gives_an_empty_diff_and_no_operation(
    equivalence_base_schema: SchemaBranch,
) -> None:
    candidate = build_schema_candidate_builder().from_schema_root(
        branch_schema=equivalence_base_schema,
        schema_root=build_base_schema_root(),
        default_branch_schema=equivalence_base_schema,
    )

    assert candidate.operations == []
    assert candidate.validation.diff.all == []
    assert (candidate.validation.migrations, candidate.validation.constraints) == ([], [])
