from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.models import SchemaUpdateValidationResult
    from infrahub.core.schema import SchemaRoot
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.schema_change.applier import SchemaChangeApplier
    from infrahub.core.schema_change.candidate_comparer import SchemaCandidateComparer
    from infrahub.core.schema_change.operation_builder import SchemaOperationBuilder
    from infrahub.core.schema_change.operations import SchemaOperation

log = get_logger()


@dataclass(frozen=True)
class SchemaCandidate:
    operations: list[SchemaOperation]
    schema: SchemaBranch
    """The processed schema that the applier built from the operations."""

    validation: SchemaUpdateValidationResult
    """The diff from the branch schema to `schema`, and the migrations, constraints and errors calculated from it."""


class SchemaCandidateBuilder:
    """Builds a candidate schema from user input by applying its operations to the branch schema.

    It has two entry methods because a candidate is built from a schema file or from operations, and both end with
    the same validation.
    """

    def __init__(
        self,
        operation_builder: SchemaOperationBuilder,
        applier: SchemaChangeApplier,
        comparer: SchemaCandidateComparer,
    ) -> None:
        self.operation_builder = operation_builder
        self.applier = applier
        self.comparer = comparer

    def from_schema_root(
        self, *, branch_schema: SchemaBranch, schema_root: SchemaRoot, default_branch_schema: SchemaBranch
    ) -> SchemaCandidate:
        """Build the candidate of a schema file; `branch_schema` is unchanged.

        Raises:
            ValueError: When the schema file cannot be laid over the branch schema, or when the candidate removes a
                kind that another kind still references.
            SchemaOperationTargetNotFoundError: When an operation names a kind, attribute or relationship that the
                branch schema does not have.

        """
        build_result = self.operation_builder.build(
            branch_schema=branch_schema, schema_root=schema_root, default_branch_schema=default_branch_schema
        )
        candidate = self._apply(
            branch_schema=branch_schema,
            operations=build_result.operations,
            default_branch_schema=default_branch_schema,
        )
        differing_kinds = self.comparer.differing_kinds(
            direct_load_schema=build_result.direct_load_schema, applied_schema=candidate.schema
        )
        if differing_kinds:
            log.warning(
                "The schema built from the operations differs from the schema of the file laid over the branch schema",
                branch=branch_schema.name,
                kinds=differing_kinds,
            )
        return candidate

    def from_operations(
        self,
        *,
        branch_schema: SchemaBranch,
        operations: Sequence[SchemaOperation],
        default_branch_schema: SchemaBranch,
    ) -> SchemaCandidate:
        """Build the candidate of a list of operations; `branch_schema` is unchanged.

        Raises:
            ValueError: When the candidate removes a kind that another kind still references.
            SchemaOperationTargetNotFoundError: When an operation names a kind, attribute or relationship that the
                branch schema does not have.

        """
        return self._apply(
            branch_schema=branch_schema, operations=operations, default_branch_schema=default_branch_schema
        )

    def _apply(
        self,
        *,
        branch_schema: SchemaBranch,
        operations: Sequence[SchemaOperation],
        default_branch_schema: SchemaBranch,
    ) -> SchemaCandidate:
        schema = self.applier.apply(
            target_schema=branch_schema, operations=operations, default_branch_schema=default_branch_schema
        )
        diff = branch_schema.diff(other=schema)
        schema.validate_node_deletions(diff=diff)
        validation = branch_schema.validate_update(other=schema, diff=diff)
        return SchemaCandidate(operations=list(operations), schema=schema, validation=validation)
