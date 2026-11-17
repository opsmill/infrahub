import pytest

from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.schema_change.enums import SchemaOperationSection, SchemaOperationType
from infrahub.core.schema_change.operation_builder import SchemaOperationBuilder
from infrahub.core.schema_change.operations import SchemaOperation
from infrahub.core.schema_change.operations_check import NoSchemaOperationsCheck
from tests.constants import TestKind
from tests.helpers.schema_change import SchemaOperationsRebuildError, build_replay_schema_operations_check
from tests.unit.core.schema_change.helpers import base_node_definition

RELABELED_TAG = "Relabeled tag"
UNKNOWN_KIND_ID = "0e7b5c2a-91d4-4f6e-b3a8-5d2c7f10e946"
TAG_LABEL_OPERATION = SchemaOperation(
    operation_type=SchemaOperationType.NODE_PROPERTY,
    kind=TestKind.TAG,
    property_name="label",
    value=RELABELED_TAG,
    previous_value="Tag",
)


def _with_relabeled_tag(schema: SchemaBranch) -> SchemaBranch:
    changed = schema.duplicate()
    tag = changed.get(name=TestKind.TAG)
    tag.label = RELABELED_TAG
    changed.set(name=TestKind.TAG, schema=tag)
    changed.process(default_branch_schema=schema)
    return changed


def test_the_check_that_checks_nothing_accepts_operations_that_do_not_rebuild_the_schema(
    equivalence_base_schema: SchemaBranch,
) -> None:
    NoSchemaOperationsCheck().check(
        branch_schema=equivalence_base_schema,
        operations=[],
        default_branch_schema=equivalence_base_schema,
        direct_load_schema=_with_relabeled_tag(equivalence_base_schema),
    )


def test_the_replay_check_accepts_operations_that_rebuild_the_schema(equivalence_base_schema: SchemaBranch) -> None:
    build_replay_schema_operations_check().check(
        branch_schema=equivalence_base_schema,
        operations=[TAG_LABEL_OPERATION],
        default_branch_schema=equivalence_base_schema,
        direct_load_schema=_with_relabeled_tag(equivalence_base_schema),
    )


def test_the_replay_check_names_the_kinds_that_the_operations_do_not_rebuild(
    equivalence_base_schema: SchemaBranch,
) -> None:
    with pytest.raises(
        SchemaOperationsRebuildError,
        match=r"^The operations built from the schema file do not rebuild its schema; kinds that differ: TestingTag$",
    ):
        build_replay_schema_operations_check().check(
            branch_schema=equivalence_base_schema,
            operations=[],
            default_branch_schema=equivalence_base_schema,
            direct_load_schema=_with_relabeled_tag(equivalence_base_schema),
        )


def test_the_replay_check_names_an_operation_that_the_applier_refuses(equivalence_base_schema: SchemaBranch) -> None:
    missing_attribute_operation = SchemaOperation(
        operation_type=SchemaOperationType.ELEMENT_REMOVE,
        kind=TestKind.TAG,
        section=SchemaOperationSection.ATTRIBUTES,
        element_name="missing",
    )

    with pytest.raises(
        SchemaOperationsRebuildError,
        match=(
            r"^The operations built from the schema file cannot be applied to the branch schema: Schema operation 0 "
            r"\(element_remove\) names 'missing' in the attributes of the kind TestingTag, which the schema does not "
            r"have\.$"
        ),
    ):
        build_replay_schema_operations_check().check(
            branch_schema=equivalence_base_schema,
            operations=[missing_attribute_operation],
            default_branch_schema=equivalence_base_schema,
            direct_load_schema=equivalence_base_schema,
        )


def test_the_replay_check_accepts_a_file_that_gives_an_existing_kind_an_unknown_id(
    equivalence_base_schema: SchemaBranch,
) -> None:
    tag = base_node_definition(TestKind.TAG)
    tag.id = UNKNOWN_KIND_ID
    build_result = SchemaOperationBuilder().build(
        branch_schema=equivalence_base_schema,
        schema_root=SchemaRoot(nodes=[tag]),
        default_branch_schema=equivalence_base_schema,
    )

    build_replay_schema_operations_check().check(
        branch_schema=equivalence_base_schema,
        operations=build_result.operations,
        default_branch_schema=equivalence_base_schema,
        direct_load_schema=build_result.direct_load_schema,
    )
