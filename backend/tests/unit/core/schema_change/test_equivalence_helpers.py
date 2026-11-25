from dataclasses import dataclass

import pytest

from infrahub.core.constants import HashableModelState
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from tests.constants import TestKind
from tests.unit.core.schema_change.helpers import (
    CaseScope,
    CombinedLoadCase,
    assert_same_load_result,
    base_node_definition,
    build_base_schema_root,
    build_direct_load_result,
    summarize_load_result,
    validate_candidate_schema,
)


def test_direct_load_of_the_base_schema_file_changes_nothing(equivalence_base_schema: SchemaBranch) -> None:
    unchanged = validate_candidate_schema(
        branch_schema=equivalence_base_schema, candidate_schema=equivalence_base_schema.duplicate()
    )

    reloaded = build_direct_load_result(
        branch_schema=equivalence_base_schema,
        schema_root=build_base_schema_root(),
        default_branch_schema=equivalence_base_schema,
    )

    assert reloaded.validation.diff.all == []
    assert_same_load_result(expected=unchanged, actual=reloaded)


def test_comparison_names_the_kind_whose_hash_differs(equivalence_base_schema: SchemaBranch) -> None:
    unchanged = validate_candidate_schema(
        branch_schema=equivalence_base_schema, candidate_schema=equivalence_base_schema.duplicate()
    )
    tag = base_node_definition(TestKind.TAG)
    tag.label = "Label"

    relabelled = build_direct_load_result(
        branch_schema=equivalence_base_schema,
        schema_root=SchemaRoot(nodes=[tag]),
        default_branch_schema=equivalence_base_schema,
    )

    with pytest.raises(AssertionError, match=r"^kinds with a different hash: \['nodes:TestingTag'\]$"):
        assert_same_load_result(expected=unchanged, actual=relabelled)


def test_comparison_with_a_kind_filter_ignores_the_kinds_outside_it(equivalence_base_schema: SchemaBranch) -> None:
    unchanged = validate_candidate_schema(
        branch_schema=equivalence_base_schema, candidate_schema=equivalence_base_schema.duplicate()
    )
    tag = base_node_definition(TestKind.TAG)
    tag.label = "Label"

    relabelled = build_direct_load_result(
        branch_schema=equivalence_base_schema,
        schema_root=SchemaRoot(nodes=[tag]),
        default_branch_schema=equivalence_base_schema,
    )

    assert_same_load_result(expected=unchanged, actual=relabelled, kinds={TestKind.DEVICE})
    with pytest.raises(AssertionError, match=r"^kinds with a different hash: \['nodes:TestingTag'\]$"):
        assert_same_load_result(expected=unchanged, actual=relabelled, kinds={TestKind.DEVICE, TestKind.TAG})


def test_summary_with_a_kind_filter_keeps_the_migrations_and_constraints_of_its_kinds(
    equivalence_base_schema: SchemaBranch,
) -> None:
    device = base_node_definition(TestKind.DEVICE)
    device.get_attribute(name="weight").state = HashableModelState.ABSENT
    tag = base_node_definition(TestKind.TAG)
    tag.get_attribute(name="description").state = HashableModelState.ABSENT

    result = build_direct_load_result(
        branch_schema=equivalence_base_schema,
        schema_root=SchemaRoot(nodes=[device, tag]),
        default_branch_schema=equivalence_base_schema,
    )
    summary = summarize_load_result(result, kinds={TestKind.TAG})

    assert summary.migrations == [("node.attribute.remove", "schema/TestingTag/description")]
    assert summary.constraints == [("node.attribute.remove", "schema/TestingTag/description")]


def _empty_schema_file(_: CaseScope, __: SchemaBranch) -> SchemaRoot:
    return SchemaRoot()


@dataclass(frozen=True)
class InvalidBaseFileCase:
    name: str
    case: CombinedLoadCase
    error: str


INVALID_BASE_FILE_CASES = [
    InvalidBaseFileCase(
        name="peer_and_generic_left_out",
        case=CombinedLoadCase(
            name="device_alone", namespace="Alone", base_kinds=(TestKind.DEVICE,), schema_file=_empty_schema_file
        ),
        error=r"^device_alone: base_kinds must also name \['AloneInterfaceHolder', 'AloneSfp'\]$",
    ),
    InvalidBaseFileCase(
        name="kind_too_long_for_its_profile",
        case=CombinedLoadCase(
            name="long_namespace",
            namespace="Anamespacelongerthanthirtychars",
            base_kinds=(TestKind.TAG,),
            schema_file=_empty_schema_file,
        ),
        error=r"^long_namespace: \['AnamespacelongerthanthirtycharsTag'\] are longer than 32 characters$",
    ),
    InvalidBaseFileCase(
        name="base_file_without_the_base_kinds",
        case=CombinedLoadCase(
            name="empty_base",
            namespace="Empty",
            base_kinds=(TestKind.TAG,),
            schema_file=_empty_schema_file,
            base_file=lambda _: SchemaRoot(),
        ),
        error=r"^empty_base: the base file defines \[\], not \['EmptyTag'\]$",
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in INVALID_BASE_FILE_CASES])
def test_base_file_of_a_case_names_the_case_when_it_is_invalid(test_case: InvalidBaseFileCase) -> None:
    with pytest.raises(ValueError, match=test_case.error):
        test_case.case.build_base_file()
