import pytest

from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from tests.constants import TestKind
from tests.unit.core.schema_change.helpers import (
    assert_same_load_result,
    base_node_definition,
    build_base_schema_root,
    build_direct_load_result,
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
