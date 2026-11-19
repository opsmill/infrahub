import re
from collections.abc import Callable
from dataclasses import dataclass

import pytest

from infrahub.core.constants import HashableModelState
from infrahub.core.schema import AttributeSchema, DropdownChoice, NodeSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.schema_change.applier import SchemaChangeApplier
from infrahub.core.schema_change.candidate import SchemaCandidateBuilder
from infrahub.core.schema_change.candidate_comparer import SchemaCandidateComparer
from infrahub.core.schema_change.enums import SchemaOperationSection, SchemaOperationType
from infrahub.core.schema_change.factory import build_schema_candidate_builder
from infrahub.core.schema_change.operation_builder import SchemaOperationBuilder
from infrahub.core.schema_change.operations import SchemaOperation
from infrahub.exceptions import (
    SchemaNameReusedError,
    SchemaNotFoundError,
    SchemaOperationsRebuildError,
    SchemaOperationTargetExistsError,
    SchemaOperationTargetNotFoundError,
)
from tests.constants import TestKind
from tests.unit.core.schema_change.helpers import (
    TAG_STATUS_ATTRIBUTE,
    ApplierCall,
    FixedOperationsBuilder,
    RecordingSchemaChangeApplier,
    SchemaLoadResult,
    assert_same_load_result,
    base_node_definition,
    build_base_schema_root,
    build_direct_load_result,
    summarize_load_result,
)

UNKNOWN_KIND_ID = "0e7b5c2a-91d4-4f6e-b3a8-5d2c7f10e946"
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


RELABEL_ATTRIBUTE_OPERATIONS = [
    SchemaOperation(
        operation_type=SchemaOperationType.ELEMENT_PROPERTY,
        kind=TestKind.DEVICE,
        section=SchemaOperationSection.ATTRIBUTES,
        element_name="manufacturer",
        property_name="label",
        value="Maker",
        previous_value="Manufacturer",
    )
]


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
        operations=RELABEL_ATTRIBUTE_OPERATIONS,
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


def test_a_schema_file_gives_the_schema_that_its_operations_build(equivalence_base_schema: SchemaBranch) -> None:
    applier = RecordingSchemaChangeApplier()
    builder = SchemaCandidateBuilder(
        operation_builder=SchemaOperationBuilder(), applier=applier, comparer=SchemaCandidateComparer()
    )

    candidate = builder.from_schema_root(
        branch_schema=equivalence_base_schema,
        schema_root=_relabel_attribute(),
        default_branch_schema=equivalence_base_schema,
    )

    assert applier.calls == [
        ApplierCall(
            target_schema=equivalence_base_schema,
            operations=RELABEL_ATTRIBUTE_OPERATIONS,
            default_branch_schema=equivalence_base_schema,
        )
    ]
    assert candidate.operations == RELABEL_ATTRIBUTE_OPERATIONS
    direct_load = build_direct_load_result(
        branch_schema=equivalence_base_schema,
        schema_root=_relabel_attribute(),
        default_branch_schema=equivalence_base_schema,
    )
    assert_same_load_result(
        expected=direct_load, actual=SchemaLoadResult(schema=candidate.schema, validation=candidate.validation)
    )
    assert candidate.validation.diff.model_dump() == direct_load.validation.diff.model_dump()


@dataclass(frozen=True)
class RebuildFailureCase:
    name: str
    schema_file: Callable[[], SchemaRoot]
    operations: list[SchemaOperation]
    """The operations that the operation builder returns in place of those of the schema file."""

    expected_kinds: str
    expected_cause: type[Exception] | None


REBUILD_FAILURE_CASES = [
    RebuildFailureCase(
        name="operations_miss_a_change_of_the_file",
        schema_file=_relabel_attribute,
        operations=[],
        expected_kinds="ProfileTestingDevice, TemplateTestingDevice, TestingDevice",
        expected_cause=None,
    ),
    RebuildFailureCase(
        name="operation_names_a_missing_attribute",
        schema_file=build_base_schema_root,
        operations=[
            SchemaOperation(
                operation_type=SchemaOperationType.ELEMENT_REMOVE,
                kind=TestKind.TAG,
                section=SchemaOperationSection.ATTRIBUTES,
                element_name="missing",
            )
        ],
        expected_kinds="TestingTag",
        expected_cause=SchemaOperationTargetNotFoundError,
    ),
    RebuildFailureCase(
        name="operation_adds_an_existing_attribute",
        schema_file=build_base_schema_root,
        operations=[
            SchemaOperation(
                operation_type=SchemaOperationType.ELEMENT_ADD,
                kind=TestKind.DEVICE,
                section=SchemaOperationSection.ATTRIBUTES,
                element_name="weight",
                value={"name": "weight", "kind": "Number", "optional": True},
            )
        ],
        expected_kinds="TestingDevice",
        expected_cause=SchemaOperationTargetExistsError,
    ),
]


@pytest.mark.parametrize("test_case", REBUILD_FAILURE_CASES, ids=lambda case: case.name)
def test_a_schema_file_whose_operations_do_not_rebuild_its_schema_is_refused(
    equivalence_base_schema: SchemaBranch, test_case: RebuildFailureCase
) -> None:
    builder = SchemaCandidateBuilder(
        operation_builder=FixedOperationsBuilder(operations=test_case.operations),
        applier=SchemaChangeApplier(),
        comparer=SchemaCandidateComparer(),
    )

    with pytest.raises(
        SchemaOperationsRebuildError,
        match=(
            r"^The schema change cannot be built accurately, so the request was not completed\. This is an error in "
            r"Infrahub, not in the schema file: the operations built from the file do not rebuild its schema for the "
            rf"kinds {test_case.expected_kinds}\.$"
        ),
    ) as exc_info:
        builder.from_schema_root(
            branch_schema=equivalence_base_schema,
            schema_root=test_case.schema_file(),
            default_branch_schema=equivalence_base_schema,
        )

    cause = exc_info.value.__cause__
    assert (None if cause is None else type(cause)) is test_case.expected_cause


def _stated_node(schema: SchemaBranch, kind: str) -> NodeSchema:
    """Return a base node as a schema file states it, with the IDs that the branch schema holds for it and its fields."""
    stored = schema.get(name=kind, duplicate=False)
    node = base_node_definition(kind)
    node.id = stored.id
    for attribute in node.attributes:
        attribute.id = stored.get_attribute(name=attribute.name).id
    for relationship in node.relationships:
        relationship.id = stored.get_relationship(name=relationship.name).id
    return node


def _chain_attribute_renames(schema: SchemaBranch) -> SchemaRoot:
    tag = _stated_node(schema, TestKind.TAG)
    tag.get_attribute(name=TAG_STATUS_ATTRIBUTE).name = "state"
    tag.get_attribute(name="description").name = TAG_STATUS_ATTRIBUTE
    return SchemaRoot(nodes=[tag])


def _swap_attribute_names(schema: SchemaBranch) -> SchemaRoot:
    tag = _stated_node(schema, TestKind.TAG)
    status = tag.get_attribute(name=TAG_STATUS_ATTRIBUTE)
    description = tag.get_attribute(name="description")
    status.name, description.name = "description", TAG_STATUS_ATTRIBUTE
    return SchemaRoot(nodes=[tag])


def _rename_attribute_and_add_one_under_its_name(schema: SchemaBranch) -> SchemaRoot:
    tag = _stated_node(schema, TestKind.TAG)
    tag.get_attribute(name="description").name = "notes"
    tag.attributes.append(AttributeSchema(name="description", kind="TextArea", optional=True))
    return SchemaRoot(nodes=[tag])


def _remove_attribute_and_rename_another_onto_it(schema: SchemaBranch) -> SchemaRoot:
    tag = _stated_node(schema, TestKind.TAG)
    tag.get_attribute(name=TAG_STATUS_ATTRIBUTE).state = HashableModelState.ABSENT
    tag.get_attribute(name="description").name = TAG_STATUS_ATTRIBUTE
    return SchemaRoot(nodes=[tag])


def _swap_kind_names(schema: SchemaBranch) -> SchemaRoot:
    tag = _stated_node(schema, TestKind.TAG)
    sfp = _stated_node(schema, TestKind.SFP)
    tag.name, sfp.name = "Sfp", "Tag"
    return SchemaRoot(nodes=[tag, sfp])


@dataclass(frozen=True)
class ReusedNameCase:
    name: str
    schema_file: Callable[[SchemaBranch], SchemaRoot]
    expected_message: str


def _reused_field_name_message(field_type: str, name: str, kind: str) -> str:
    return (
        f"The schema load frees the {field_type} name '{name}' of the kind {kind} and gives it to another "
        f"{field_type}, which Infrahub cannot apply in one load. Load the changes in separate steps, so that no load "
        "both frees and reuses a name."
    )


REUSED_NAME_CASES = [
    ReusedNameCase(
        name="chained_attribute_renames",
        schema_file=_chain_attribute_renames,
        expected_message=_reused_field_name_message("attribute", TAG_STATUS_ATTRIBUTE, TestKind.TAG),
    ),
    ReusedNameCase(
        name="swapped_attribute_names",
        schema_file=_swap_attribute_names,
        expected_message=_reused_field_name_message("attribute", "description", TestKind.TAG),
    ),
    ReusedNameCase(
        name="attribute_renamed_and_another_added_under_its_name",
        schema_file=_rename_attribute_and_add_one_under_its_name,
        expected_message=_reused_field_name_message("attribute", "description", TestKind.TAG),
    ),
    ReusedNameCase(
        name="attribute_removed_and_another_renamed_onto_its_name",
        schema_file=_remove_attribute_and_rename_another_onto_it,
        expected_message=_reused_field_name_message("attribute", TAG_STATUS_ATTRIBUTE, TestKind.TAG),
    ),
    ReusedNameCase(
        name="swapped_kind_names",
        schema_file=_swap_kind_names,
        expected_message=(
            f"The schema load frees the kind {TestKind.SFP} and gives it to another kind, which Infrahub cannot apply "
            "in one load. Load the changes in separate steps, so that no load both frees and reuses a kind."
        ),
    ),
]


@pytest.mark.parametrize("test_case", REUSED_NAME_CASES, ids=lambda case: case.name)
def test_a_schema_file_that_frees_and_reuses_a_name_is_refused_before_any_operation_is_applied(
    equivalence_base_schema: SchemaBranch, test_case: ReusedNameCase
) -> None:
    applier = RecordingSchemaChangeApplier()
    builder = SchemaCandidateBuilder(
        operation_builder=SchemaOperationBuilder(), applier=applier, comparer=SchemaCandidateComparer()
    )

    with pytest.raises(SchemaNameReusedError, match=rf"^{re.escape(test_case.expected_message)}$"):
        builder.from_schema_root(
            branch_schema=equivalence_base_schema,
            schema_root=test_case.schema_file(equivalence_base_schema),
            default_branch_schema=equivalence_base_schema,
        )

    assert applier.calls == []


def test_a_schema_file_that_gives_an_existing_kind_an_unknown_id_is_refused_before_any_operation_is_applied(
    equivalence_base_schema: SchemaBranch,
) -> None:
    applier = RecordingSchemaChangeApplier()
    builder = SchemaCandidateBuilder(
        operation_builder=SchemaOperationBuilder(), applier=applier, comparer=SchemaCandidateComparer()
    )
    tag = base_node_definition(TestKind.TAG)
    tag.id = UNKNOWN_KIND_ID

    with pytest.raises(SchemaNotFoundError) as exc_info:
        builder.from_schema_root(
            branch_schema=equivalence_base_schema,
            schema_root=SchemaRoot(nodes=[tag]),
            default_branch_schema=equivalence_base_schema,
        )

    assert (exc_info.value.message, exc_info.value.identifier, exc_info.value.branch_name) == (
        f"Unable to find the Schema associated with {UNKNOWN_KIND_ID}, {TestKind.TAG}",
        UNKNOWN_KIND_ID,
        equivalence_base_schema.name,
    )
    assert applier.calls == []


def test_operations_are_applied_once(equivalence_base_schema: SchemaBranch) -> None:
    applier = RecordingSchemaChangeApplier()
    builder = SchemaCandidateBuilder(
        operation_builder=SchemaOperationBuilder(), applier=applier, comparer=SchemaCandidateComparer()
    )

    candidate = builder.from_operations(
        branch_schema=equivalence_base_schema,
        operations=RELABEL_ATTRIBUTE_OPERATIONS,
        default_branch_schema=equivalence_base_schema,
    )

    assert applier.calls == [
        ApplierCall(
            target_schema=equivalence_base_schema,
            operations=RELABEL_ATTRIBUTE_OPERATIONS,
            default_branch_schema=equivalence_base_schema,
        )
    ]
    assert sorted(candidate.validation.diff.changed) == [TestKind.DEVICE]


USER_GIVEN_ID = "3f8d2b61-0c4e-4a97-9b15-7e2a6c0d8f43"
CABLE_KIND = "TestingCable"


def _new_kind_with_an_id() -> SchemaRoot:
    cable = NodeSchema(
        id=USER_GIVEN_ID,
        name="Cable",
        namespace="Testing",
        label="Cable",
        attributes=[AttributeSchema(name="length", kind="Number", optional=True)],
    )
    return SchemaRoot(nodes=[cable])


def _new_attribute_with_an_id() -> SchemaRoot:
    tag = base_node_definition(TestKind.TAG)
    tag.attributes.append(AttributeSchema(id=USER_GIVEN_ID, name="code", kind="Text", optional=True))
    return SchemaRoot(nodes=[tag])


@dataclass(frozen=True)
class UserGivenIdCase:
    name: str
    schema_file: Callable[[], SchemaRoot]
    kind: str
    element_name: str | None
    """The new attribute that the file gives an ID, or `None` when the file gives the new kind an ID."""


@pytest.mark.parametrize(
    "test_case",
    [
        pytest.param(
            UserGivenIdCase(name="new_kind", schema_file=_new_kind_with_an_id, kind=CABLE_KIND, element_name=None),
            id="new_kind",
        ),
        pytest.param(
            UserGivenIdCase(
                name="new_attribute_of_an_existing_kind",
                schema_file=_new_attribute_with_an_id,
                kind=TestKind.TAG,
                element_name="code",
            ),
            id="new_attribute_of_an_existing_kind",
        ),
    ],
)
def test_an_id_that_a_file_gives_a_new_kind_or_attribute_is_left_out(
    equivalence_base_schema: SchemaBranch, test_case: UserGivenIdCase
) -> None:
    candidate = build_schema_candidate_builder().from_schema_root(
        branch_schema=equivalence_base_schema,
        schema_root=test_case.schema_file(),
        default_branch_schema=equivalence_base_schema,
    )

    kind = candidate.schema.get(name=test_case.kind, duplicate=False)
    target = kind if test_case.element_name is None else kind.get_attribute(name=test_case.element_name)
    assert target.id is None
    assert [operation.operation_type for operation in candidate.operations] == [
        SchemaOperationType.NODE_ADD if test_case.element_name is None else SchemaOperationType.ELEMENT_ADD
    ]
