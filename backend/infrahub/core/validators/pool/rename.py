from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from infrahub.core.schema import GenericSchema
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
ATTRIBUTE_NAME_CONSTRAINT = "attribute.name.update"

KIND_RENAME_REASON = "a kind cannot be renamed while a number pool allocates numbers for it"
ATTRIBUTE_RENAME_REASON = "an attribute cannot be renamed while a number pool allocates numbers for it"


class NumberPoolRenameChecker(ConstraintCheckerInterface):
    """Refuses a schema change that renames a kind, or an attribute, that a number pool allocates numbers for.

    A number pool names its kind and its attribute, and serves every branch, so a rename would leave the pool naming
    a kind or an attribute that the schema no longer has.
    """

    # Only a schema change can rename a kind or an attribute, so a data change never needs this checker.
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
        return request.constraint_name in {KIND_NAME_CONSTRAINT, KIND_NAMESPACE_CONSTRAINT, ATTRIBUTE_NAME_CONSTRAINT}

    async def check(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]:
        """Return one violation per number pool that allocates numbers for the kind or the attribute the change renames.

        A kind or an attribute keeps its id when it is renamed, so one without an id is new and renames nothing.

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
        if request.constraint_name == ATTRIBUTE_NAME_CONSTRAINT:
            refusals = await self._attribute_refusals(
                candidate_schema=request.schema_branch,
                kind_schema=kind_schema,
                previous_kinds=previous_kinds,
                field_name=field_name,
            )
        else:
            refusals = await self._kind_refusals(
                request=request, kind_schema=kind_schema, previous_kinds=previous_kinds
            )
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

    async def _attribute_refusals(
        self,
        candidate_schema: SchemaBranch,
        kind_schema: MainSchemaTypes,
        previous_kinds: list[MainSchemaTypes],
        field_name: str,
    ) -> list[tuple[str, str]]:
        """Return the pools that allocate numbers for the attribute under a name the change replaces.

        A pool on a node can allocate numbers for an attribute the node inherits, so the kinds that implement a generic
        are read with it.
        """
        attribute = kind_schema.get_attribute_or_none(name=field_name)
        if attribute is None or not attribute.id:
            return []
        renamed_attributes: set[tuple[str, str]] = set()
        for previous_kind in previous_kinds:
            previous_attribute = next(
                (candidate for candidate in previous_kind.attributes if candidate.id == attribute.id), None
            )
            if previous_attribute is None or previous_attribute.name == attribute.name:
                continue
            # A kind renamed by the same load is refused under its own constraint, so its pools are reported once.
            kinds = {previous_kind.kind} if previous_kind.kind == kind_schema.kind else set()
            if isinstance(previous_kind, GenericSchema):
                kinds.update(kind for kind in previous_kind.used_by if candidate_schema.has(name=kind))
            renamed_attributes.update((kind, previous_attribute.name) for kind in kinds)
        if not renamed_attributes:
            return []
        pools = await self.pool_source.get_attached_to_kinds(kinds={kind for kind, _ in renamed_attributes})
        return [
            (
                pool.id,
                f"pool {pool.name} allocates numbers for {pool.kind}.{pool.tracked_attribute}; {ATTRIBUTE_RENAME_REASON}",
            )
            for pool in pools
            if (pool.kind, pool.tracked_attribute) in renamed_attributes
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
