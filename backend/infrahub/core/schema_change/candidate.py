from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.models import SchemaDiff, SchemaUpdateValidationResult
    from infrahub.core.schema import SchemaRoot
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.schema_change.applier import SchemaChangeApplier
    from infrahub.core.schema_change.operation_builder import SchemaOperationBuilder
    from infrahub.core.schema_change.operations import SchemaOperation
    from infrahub.core.schema_change.operations_check import SchemaOperationsCheck


@dataclass(frozen=True)
class SchemaCandidate:
    operations: list[SchemaOperation]
    schema: SchemaBranch
    """The processed candidate schema: the schema file laid over the branch schema, or the operations applied to it."""

    validation: SchemaUpdateValidationResult
    """The diff from the branch schema to `schema`, and the migrations, constraints and errors calculated from it."""


class SchemaCandidateBuilder:
    """Builds a candidate schema from user input.

    It has two entry methods because a candidate is built from a schema file or from operations, and both end with
    the same validation.
    """

    def __init__(
        self,
        operation_builder: SchemaOperationBuilder,
        applier: SchemaChangeApplier,
        operations_check: SchemaOperationsCheck,
    ) -> None:
        self.operation_builder = operation_builder
        self.applier = applier
        self.operations_check = operations_check

    def from_schema_root(
        self, *, branch_schema: SchemaBranch, schema_root: SchemaRoot, default_branch_schema: SchemaBranch
    ) -> SchemaCandidate:
        """Build the candidate of a schema file, processing the schema once; `branch_schema` is unchanged.

        Raises:
            ValueError: When the schema file cannot be laid over the branch schema, or when the candidate removes a
                kind that another kind still references.

        """
        build_result = self.operation_builder.build(
            branch_schema=branch_schema, schema_root=schema_root, default_branch_schema=default_branch_schema
        )
        self.operations_check.check(
            branch_schema=branch_schema,
            operations=build_result.operations,
            default_branch_schema=default_branch_schema,
            direct_load_schema=build_result.direct_load_schema,
        )
        return self._validate(
            branch_schema=branch_schema,
            operations=build_result.operations,
            schema=build_result.direct_load_schema,
            diff=build_result.diff,
        )

    def from_operations(
        self,
        *,
        branch_schema: SchemaBranch,
        operations: Sequence[SchemaOperation],
        default_branch_schema: SchemaBranch,
    ) -> SchemaCandidate:
        """Build the candidate of a list of operations by applying them; `branch_schema` is unchanged.

        Raises:
            ValueError: When the candidate removes a kind that another kind still references.
            SchemaOperationTargetNotFoundError: When an operation names a kind, attribute or relationship that the
                branch schema does not have.

        """
        schema = self.applier.apply(
            target_schema=branch_schema, operations=operations, default_branch_schema=default_branch_schema
        )
        return self._validate(
            branch_schema=branch_schema, operations=operations, schema=schema, diff=branch_schema.diff(other=schema)
        )

    @staticmethod
    def _validate(
        *, branch_schema: SchemaBranch, operations: Sequence[SchemaOperation], schema: SchemaBranch, diff: SchemaDiff
    ) -> SchemaCandidate:
        schema.validate_node_deletions(diff=diff)
        validation = branch_schema.validate_update(other=schema, diff=diff)
        return SchemaCandidate(operations=list(operations), schema=schema, validation=validation)
