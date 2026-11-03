from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from infrahub.core.schema import GenericSchema, NodeSchema
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
INHERIT_FROM_CONSTRAINT = "node.inherit_from.update"

KIND_RENAME_REASON = "a kind cannot be renamed while a number pool allocates numbers for it"
ATTRIBUTE_RENAME_REASON = "an attribute cannot be renamed while a number pool allocates numbers for it"
INHERITANCE_REASON = "a kind cannot inherit from another generic while a number pool allocates numbers for it"


class NumberPoolRenameChecker(ConstraintCheckerInterface):
    """Refuses a schema change that renames a kind, or an attribute, that a number pool allocates numbers for.

    A number pool names its kind and its attribute, and serves every branch, so a rename would leave the pool naming
    a kind or an attribute that the schema no longer has. A kind that inherits from another generic is migrated like a
    renamed kind, so that change is refused too.
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
        return request.constraint_name in {
            KIND_NAME_CONSTRAINT,
            KIND_NAMESPACE_CONSTRAINT,
            ATTRIBUTE_NAME_CONSTRAINT,
            INHERIT_FROM_CONSTRAINT,
        }

    async def check(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]:
        """Return one violation per number pool that allocates numbers for the kind or the attribute the change renames.

        A kind or an attribute keeps its id when it is renamed, so one without an id is new and renames nothing.

        Raises:
            ValueError: When the request names no field, for a change other than the kind's inheritance.

        """
        field_name = request.schema_path.field_name
        # The schema diff raises the inheritance change twice, once without a field, so the pool is reported once.
        if request.constraint_name == INHERIT_FROM_CONSTRAINT and not field_name:
            return []
        if not field_name:
            raise ValueError("field_name is not defined")
        kind = request.schema_path.schema_kind
        if not request.schema_branch.has(name=kind):
            return []
        kind_schema = request.schema_branch.get(name=kind, duplicate=False)
        if not kind_schema.id:
            return []

        previous_kinds = self._previous_kinds(request=request, kind_id=kind_schema.id)
        if request.constraint_name == INHERIT_FROM_CONSTRAINT:
            refusals = await self._inheritance_refusals(
                candidate_schema=request.schema_branch, kind_schema=kind_schema, previous_kinds=previous_kinds
            )
        elif request.constraint_name == ATTRIBUTE_NAME_CONSTRAINT:
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
        previous_kinds: list[tuple[SchemaBranch, MainSchemaTypes]],
    ) -> list[tuple[str, str]]:
        """Return the pools that allocate numbers for the kind under a name the change replaces."""
        # A load that changes both the name and the namespace raises both constraints, so the pool is reported once.
        renamed_kinds = {
            previous.kind
            for _, previous in previous_kinds
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
        previous_kinds: list[tuple[SchemaBranch, MainSchemaTypes]],
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
        for _, previous_kind in previous_kinds:
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

    async def _inheritance_refusals(
        self,
        candidate_schema: SchemaBranch,
        kind_schema: MainSchemaTypes,
        previous_kinds: list[tuple[SchemaBranch, MainSchemaTypes]],
    ) -> list[tuple[str, str]]:
        """Return the pools that count the objects of a kind the change makes inherit from another generic.

        The objects of a kind also count in the pools of the generics it already inherits from, so those pools are read
        too. A generic is matched by its id, so a generic renamed by the same load is not another generic.
        """
        if not isinstance(kind_schema, NodeSchema):
            return []
        generic_ids = [candidate_schema.get(name=name, duplicate=False).id for name in kind_schema.inherit_from]
        affected_kinds: set[str] = set()
        for previous_schema, previous_kind in previous_kinds:
            # A kind renamed by the same load is refused under its own constraint, so its pools are reported once.
            if previous_kind.kind != kind_schema.kind or not isinstance(previous_kind, NodeSchema):
                continue
            previous_ids = {
                previous_schema.get(name=name, duplicate=False).id
                for name in previous_kind.inherit_from
                if previous_schema.has(name=name)
            }
            if any(generic_id is None or generic_id not in previous_ids for generic_id in generic_ids):
                affected_kinds.update([previous_kind.kind, *previous_kind.inherit_from])
        if not affected_kinds:
            return []
        pools = await self.pool_source.get_attached_to_kinds(kinds=affected_kinds)
        return [
            (
                pool.id,
                f"pool {pool.name} allocates numbers for {pool.kind}.{pool.tracked_attribute}; {INHERITANCE_REASON}",
            )
            for pool in pools
        ]

    def _previous_kinds(
        self, request: SchemaConstraintValidatorRequest, kind_id: str
    ) -> list[tuple[SchemaBranch, MainSchemaTypes]]:
        """Return each schema before the change that defines the kind, with the kind found by the id it keeps.

        A schema load builds the candidate on the branch's own schema, while a proposed change, a merge or a rebase
        builds it on the destination's schema, so the kind is looked up on both.
        """
        names = [request.branch.name]
        if request.schema_branch.name != request.branch.name:
            names.append(request.schema_branch.name)
        previous_kinds: list[tuple[SchemaBranch, MainSchemaTypes]] = []
        for name in names:
            previous_schema = self.schema_source.get_schema_branch(name=name)
            try:
                previous_kinds.append((previous_schema, previous_schema.get_by_id(id=kind_id, duplicate=False)))
            except SchemaNotFoundError:
                continue
        return previous_kinds
