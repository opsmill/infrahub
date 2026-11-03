from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from infrahub.exceptions import SchemaNotFoundError

from ..interface import ConstraintCheckerInterface

if TYPE_CHECKING:
    from collections.abc import Iterable

    from infrahub.core.path import GroupedDataPaths
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.pools.scoped_number_pool_reader import ScopedNumberPool

    from ..model import SchemaConstraintValidatorRequest
    from .scope_dependency import ScopeViolationBuilder


class SchemaBranchSource(Protocol):
    def get_schema_branch(self, name: str) -> SchemaBranch: ...


class NumberPoolSource(Protocol):
    async def get_attached_to_kinds(self, kinds: Iterable[str]) -> list[ScopedNumberPool]: ...


KIND_NAME_CONSTRAINT = "node.name.update"
KIND_NAMESPACE_CONSTRAINT = "node.namespace.update"

KIND_RENAME_REASON = "a kind cannot be renamed while a number pool allocates numbers for it"


class NumberPoolRenameChecker(ConstraintCheckerInterface):
    """Refuses a schema change that renames a kind that a number pool allocates numbers for.

    A number pool names its kind and serves every branch, so a rename would leave the pool naming a kind that the
    schema no longer has.
    """

    # Only a schema change can rename a kind, so a data change never needs this checker.
    triggered_by_data_change = False

    def __init__(
        self, pool_source: NumberPoolSource, schema_source: SchemaBranchSource, violation_builder: ScopeViolationBuilder
    ) -> None:
        self.pool_source = pool_source
        self.schema_source = schema_source
        self.violation_builder = violation_builder

    @property
    def name(self) -> str:
        return "number_pool.rename"

    def supports(self, request: SchemaConstraintValidatorRequest) -> bool:
        return request.constraint_name in {KIND_NAME_CONSTRAINT, KIND_NAMESPACE_CONSTRAINT}

    async def check(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]:
        """Return one violation per number pool that allocates numbers for the kind the change renames.

        A kind keeps its id when it is renamed, so a kind without an id is new and renames nothing.

        Raises:
            ValueError: When the request names no field.

        """
        field_name = request.schema_path.field_name
        if not field_name:
            raise ValueError("field_name is not defined")
        kind = request.schema_path.schema_kind
        if not request.schema_branch.has(name=kind):
            return []
        kind_schema = request.schema_branch.get(name=kind, duplicate=False)
        if not kind_schema.id:
            return []

        previous_kinds = self._previous_kinds(request=request, kind_id=kind_schema.id)
        refusals = await self._kind_refusals(request=request, kind_schema=kind_schema, previous_kinds=previous_kinds)
        if not refusals:
            return []
        return [
            self.violation_builder.build_refusals(
                branch_name=request.branch.name, field_name=field_name, refusals=refusals
            )
        ]

    async def _kind_refusals(
        self,
        request: SchemaConstraintValidatorRequest,
        kind_schema: MainSchemaTypes,
        previous_kinds: list[MainSchemaTypes],
    ) -> list[tuple[str, str]]:
        """Return the pools that allocate numbers for the kind under a name the change replaces."""
        # A load that changes both the name and the namespace raises both constraints, so the pool is reported once.
        renamed_kinds = {
            previous.kind
            for previous in previous_kinds
            if previous.kind != kind_schema.kind
            and (request.constraint_name == KIND_NAME_CONSTRAINT or previous.name == kind_schema.name)
        }
        if not renamed_kinds:
            return []
        pools = await self.pool_source.get_attached_to_kinds(kinds=renamed_kinds)
        return [
            (
                pool.id,
                f"pool {pool.name} allocates numbers for {pool.kind}.{pool.tracked_attribute}; {KIND_RENAME_REASON}",
            )
            for pool in pools
        ]

    def _previous_kinds(self, request: SchemaConstraintValidatorRequest, kind_id: str) -> list[MainSchemaTypes]:
        """Return the kind as each schema before the change defines it, found by the id it keeps when renamed.

        A schema load builds the candidate on the branch's own schema, while a proposed change, a merge or a rebase
        builds it on the destination's schema, so the kind is looked up on both.
        """
        names = [request.branch.name]
        if request.schema_branch.name != request.branch.name:
            names.append(request.schema_branch.name)
        previous_kinds: list[MainSchemaTypes] = []
        for name in names:
            try:
                previous_kinds.append(
                    self.schema_source.get_schema_branch(name=name).get_by_id(id=kind_id, duplicate=False)
                )
            except SchemaNotFoundError:
                continue
        return previous_kinds
