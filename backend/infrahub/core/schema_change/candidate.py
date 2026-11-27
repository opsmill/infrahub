from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core.schema_change.constants import SCHEMA_ELEMENT_NAME_PROPERTY
from infrahub.core.schema_change.enums import SchemaOperationSection, SchemaOperationType
from infrahub.core.schema_change.operations import read_kind_name
from infrahub.exceptions import (
    SchemaNameReusedError,
    SchemaNotFoundError,
    SchemaOperationsRebuildError,
    SchemaOperationTargetExistsError,
    SchemaOperationTargetNotFoundError,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.models import SchemaUpdateValidationResult
    from infrahub.core.schema import SchemaRoot
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.schema_change.applier import SchemaChangeApplier
    from infrahub.core.schema_change.candidate_comparer import SchemaCandidateComparer
    from infrahub.core.schema_change.operation_builder import SchemaOperationBuilder
    from infrahub.core.schema_change.operations import SchemaOperation


@dataclass(frozen=True)
class SchemaCandidate:
    operations: list[SchemaOperation]
    schema: SchemaBranch
    """The processed candidate schema: the operations applied to the branch schema."""

    validation: SchemaUpdateValidationResult
    """The diff from the branch schema to `schema`, and the migrations, constraints and errors calculated from it."""


class SchemaCandidateBuilder:
    """Builds a candidate schema from user input by applying operations to the branch schema.

    It has two entry methods because the operations come from a schema file or are given, and both end with the
    same validation.
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
        self,
        *,
        branch_schema: SchemaBranch,
        schema_root: SchemaRoot,
        default_branch_schema: SchemaBranch,
        enforce_update_support: bool = True,
    ) -> SchemaCandidate:
        """Build the candidate of a schema file from the operations it makes; `branch_schema` is unchanged.

        The candidate schema is the operations applied to the branch schema, and it must equal the schema file laid
        over the branch schema, kind by kind. A schema file that changes nothing gives no operation, so its candidate
        is the schema file laid over the branch schema, with nothing applied or compared. With `enforce_update_support`
        off, a change to a property that has no migration is not an error, and it gets no migration and no constraint
        check.

        Raises:
            ValueError: When the schema file cannot be laid over the branch schema, or when the candidate removes a
                kind that another kind still references.
            ValidationError: When processing the schema file laid over the branch schema refuses it.
            SchemaNotFoundError: When the schema file gives a kind of the branch schema an ID that the branch schema
                does not hold.
            SchemaNameReusedError: When the schema file frees a kind and gives it to another kind, including a new
                kind, or frees an attribute name of a kind, including one the kind inherits from a generic, and gives
                it to another attribute of that kind.
            SchemaOperationsRebuildError: When the operations cannot be applied, including a malformed operation or
                a built schema that processing refuses, or when the schema they build differs from the schema file
                laid over the branch schema.

        """
        self._refuse_an_unknown_id_for_an_existing_kind(branch_schema=branch_schema, schema_root=schema_root)
        self._refuse_a_new_kind_under_a_renamed_kind(branch_schema=branch_schema, schema_root=schema_root)
        build_result = self.operation_builder.build(
            branch_schema=branch_schema, schema_root=schema_root, default_branch_schema=default_branch_schema
        )
        if not build_result.diff.all and not build_result.operations:
            # Applying no operation rebuilds the branch schema, which the direct load equals when the diff is empty.
            return self._validate(
                branch_schema=branch_schema,
                operations=[],
                schema=build_result.direct_load_schema,
                enforce_update_support=enforce_update_support,
            )
        self._refuse_a_reused_name(branch_schema=branch_schema, operations=build_result.operations)
        try:
            schema = self.applier.apply(
                target_schema=branch_schema,
                operations=build_result.operations,
                default_branch_schema=default_branch_schema,
            )
        except (SchemaOperationTargetNotFoundError, SchemaOperationTargetExistsError) as exc:
            raise SchemaOperationsRebuildError(kinds=[exc.kind]) from exc
        except ValueError as exc:
            # The operation builder already laid the same file over the branch schema and processed it without an error.
            raise SchemaOperationsRebuildError(
                kinds=sorted({operation.kind for operation in build_result.operations})
            ) from exc

        differing_kinds = self.comparer.differing_kinds(
            direct_load_schema=build_result.direct_load_schema, applied_schema=schema
        )
        if differing_kinds:
            raise SchemaOperationsRebuildError(kinds=differing_kinds)
        return self._validate(
            branch_schema=branch_schema,
            operations=build_result.operations,
            schema=schema,
            enforce_update_support=enforce_update_support,
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
            SchemaOperationTargetExistsError: When an operation adds a kind, attribute or relationship that the
                branch schema already has.

        """
        schema = self.applier.apply(
            target_schema=branch_schema, operations=operations, default_branch_schema=default_branch_schema
        )
        return self._validate(
            branch_schema=branch_schema, operations=operations, schema=schema, enforce_update_support=True
        )

    def _refuse_an_unknown_id_for_an_existing_kind(
        self, *, branch_schema: SchemaBranch, schema_root: SchemaRoot
    ) -> None:
        # Laying the file over the branch schema would replace the kind whole, which no operation states, and writing
        # the kind to the database refuses the ID with this same error.
        branch_kind_ids = branch_schema.get_all_kind_id_map(nodes_and_generics_only=True)
        known_ids = set(branch_kind_ids.values())
        for item in [*schema_root.generics, *schema_root.nodes]:
            if item.id is not None and item.kind in branch_kind_ids and item.id not in known_ids:
                raise SchemaNotFoundError(
                    branch_name=branch_schema.name,
                    identifier=item.id,
                    message=f"Unable to find the Schema associated with {item.id}, {item.kind}",
                )

    def _refuse_a_new_kind_under_a_renamed_kind(self, *, branch_schema: SchemaBranch, schema_root: SchemaRoot) -> None:
        # Laying the file over the branch schema and saving the schema both find a kind without an ID by its name, so
        # a new kind under the name of a renamed kind replaces that kind or is lost, depending on the order in the file.
        kinds_by_id = {
            kind_id: kind for kind, kind_id in branch_schema.get_all_kind_id_map(nodes_and_generics_only=True).items()
        }
        items = [*schema_root.generics, *schema_root.nodes]
        renamed_kinds = {
            kinds_by_id[item.id] for item in items if item.id in kinds_by_id and kinds_by_id[item.id] != item.kind
        }
        for item in items:
            if item.id is None and item.kind in renamed_kinds:
                raise SchemaNameReusedError(kind=item.kind)

    def _refuse_a_reused_name(self, *, branch_schema: SchemaBranch, operations: Sequence[SchemaOperation]) -> None:
        # Data migrations find attributes and the nodes of a kind by name in no fixed order, so a load must not free
        # and reuse an attribute name of the nodes of a kind, or a kind; relationship data is keyed by the identifier,
        # which a load cannot change.
        freed_kinds: set[str] = set()
        taken_kinds: set[str] = set()
        freed_attributes: dict[str, set[str]] = defaultdict(set)
        taken_attributes: dict[str, set[str]] = defaultdict(set)
        for operation in operations:
            match operation.operation_type:
                case SchemaOperationType.NODE_REMOVE:
                    freed_kinds.add(operation.kind)
                case SchemaOperationType.NODE_RENAME:
                    kind_name = read_kind_name(operation.value)
                    if kind_name is not None and kind_name.kind != operation.kind:
                        freed_kinds.add(operation.kind)
                        taken_kinds.add(kind_name.kind)
                case SchemaOperationType.ELEMENT_REMOVE if (
                    operation.section == SchemaOperationSection.ATTRIBUTES and operation.element_name
                ):
                    for kind in self._kinds_with_the_attributes_of(branch_schema=branch_schema, kind=operation.kind):
                        freed_attributes[kind].add(operation.element_name)
                case SchemaOperationType.ELEMENT_ADD if (
                    operation.section == SchemaOperationSection.ATTRIBUTES and operation.element_name
                ):
                    for kind in self._kinds_with_the_attributes_of(branch_schema=branch_schema, kind=operation.kind):
                        taken_attributes[kind].add(operation.element_name)
                case SchemaOperationType.ELEMENT_PROPERTY if (
                    operation.section == SchemaOperationSection.ATTRIBUTES
                    and operation.element_name
                    and operation.property_name == SCHEMA_ELEMENT_NAME_PROPERTY
                    and isinstance(operation.value, str)
                ):
                    for kind in self._kinds_with_the_attributes_of(branch_schema=branch_schema, kind=operation.kind):
                        freed_attributes[kind].add(operation.element_name)
                        taken_attributes[kind].add(operation.value)
                case _:
                    pass

        if reused_kinds := sorted(freed_kinds & taken_kinds):
            raise SchemaNameReusedError(kind=reused_kinds[0])
        for kind in sorted(freed_attributes):
            if reused_names := sorted(freed_attributes[kind] & taken_attributes[kind]):
                raise SchemaNameReusedError(kind=kind, section=SchemaOperationSection.ATTRIBUTES, name=reused_names[0])

    def _kinds_with_the_attributes_of(self, *, branch_schema: SchemaBranch, kind: str) -> list[str]:
        # The data migration of an attribute of a generic changes the attribute on the nodes of every inheriting kind.
        if kind in branch_schema.generics:
            return [kind, *branch_schema.get_generic(name=kind, duplicate=False).used_by]
        return [kind]

    def _validate(
        self,
        *,
        branch_schema: SchemaBranch,
        operations: Sequence[SchemaOperation],
        schema: SchemaBranch,
        enforce_update_support: bool,
    ) -> SchemaCandidate:
        diff = branch_schema.diff(other=schema)
        schema.validate_node_deletions(diff=diff)
        validation = branch_schema.validate_update(
            other=schema, diff=diff, enforce_update_support=enforce_update_support
        )
        return SchemaCandidate(operations=list(operations), schema=schema, validation=validation)
