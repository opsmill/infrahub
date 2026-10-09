from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from infrahub.core.constants import InfrahubKind, PathType, RelationshipCardinality
from infrahub.core.path import DataPath, GroupedDataPaths
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema
from infrahub.core.validators.enum import ConstraintIdentifier
from infrahub.exceptions import ValidationError
from infrahub.log import get_logger
from infrahub.pools.scope import NON_SCALAR_ATTRIBUTE_KINDS, AllocationScopeResolver, ScopeElement

from ..interface import ConstraintCheckerInterface

log = get_logger()

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.pools.scoped_number_pool_reader import KindNumberPools, ScopedNumberPool

    from ..model import SchemaConstraintValidatorRequest


class ScopedNumberPoolSource(Protocol):
    async def get_for_kinds(self, kinds: Iterable[str]) -> KindNumberPools: ...


class SchemaBranchSource(Protocol):
    def get_schema_branch(self, name: str) -> SchemaBranch: ...


class PoolDependency(StrEnum):
    """What ties a pool to the changed field."""

    SCOPE_ELEMENT = "scope_element"
    TRACKED_ATTRIBUTE = "tracked_attribute"


@dataclass(frozen=True)
class ScopeBreakage:
    """A schema change that stops the pools depending on the changed field from dividing their space."""

    dependency: PoolDependency
    reason: str


class NumberPoolScopeChecker(ConstraintCheckerInterface):
    """Refuses a schema change that stops a field from giving the one value per node that a pool's scope needs."""

    # Only a schema change can break a scope, so a data change never needs this checker.
    triggered_by_data_change = False

    def __init__(self, pool_source: ScopedNumberPoolSource, schema_source: SchemaBranchSource) -> None:
        self.pool_source = pool_source
        self.schema_source = schema_source
        self._rules: dict[str, Callable[[SchemaConstraintValidatorRequest, str], ScopeBreakage | None]] = {
            "attribute.optional.update": self._made_optional,
            "relationship.optional.update": self._made_optional,
            "relationship.cardinality.update": self._made_many,
            "attribute.unique.update": self._made_unique,
            "attribute.kind.update": self._made_non_scalar,
            "node.attribute.remove": self._removed,
            "node.relationship.remove": self._removed,
            "attribute.name.update": self._accepted,
            "relationship.name.update": self._accepted,
            ConstraintIdentifier.ATTRIBUTE_PARAMETERS_ALLOCATION_SCOPE_UPDATE.value: self._accepted,
        }

    @property
    def name(self) -> str:
        return "number_pool.scope"

    def supports(self, request: SchemaConstraintValidatorRequest) -> bool:
        return request.constraint_name in self._rules

    async def check(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]:
        field_name = request.schema_path.field_name
        if not field_name:
            raise ValueError("field_name is not defined")

        breakage = self._rules[request.constraint_name](request, field_name)
        if breakage is None:
            return []

        previous_schemas = self._previous_schemas(request=request)
        kind = request.schema_path.schema_kind
        kind_schemas = [
            schema_branch.get(name=kind, duplicate=False)
            for schema_branch in previous_schemas
            if schema_branch.has(name=kind)
        ]
        if not kind_schemas:
            return []

        pools = await self.pool_source.get_for_kinds(
            kinds={kind for kind_schema in kind_schemas for kind in self._kinds_sharing_fields(kind_schema=kind_schema)}
        )
        elements = self._scope_elements(request=request, schema_branches=previous_schemas, field_name=field_name)
        element_ids = {element.id for element in elements}
        if breakage.dependency == PoolDependency.SCOPE_ELEMENT:
            dependent_pools = [
                pool for pool in pools.scoped if element_ids & {stored.id for stored in pool.scope.elements}
            ]
            unchecked_pools = [
                pool
                for pool in pools.unreadable
                if self._may_reference(stored_scope=pool.stored_scope, elements=elements, field_name=field_name)
            ]
        else:
            # A pool stores its tracked attribute by name, which is the pre-change name when the same load renames it.
            tracked_names = {field_name} | {element.name for element in elements}
            dependent_pools = [pool for pool in pools.scoped if pool.tracked_attribute in tracked_names]
            unchecked_pools = [pool for pool in pools.unreadable if pool.tracked_attribute in tracked_names]

        unchecked_ids = {unchecked_pool.id for unchecked_pool in unchecked_pools}
        for unreadable_pool in pools.unreadable:
            if unreadable_pool.id not in unchecked_ids:
                log.warning(
                    f"Not checking {kind}.{field_name} against NumberPool={unreadable_pool.id}: {unreadable_pool.reason}"
                )

        grouped_data_paths = GroupedDataPaths()
        for pool in dependent_pools:
            grouped_data_paths.add_data_path(
                DataPath(
                    branch=request.branch.name,
                    path_type=PathType.NODE,
                    node_id=pool.id,
                    kind=InfrahubKind.NUMBERPOOL,
                    field_name=field_name,
                    value=self._describe(pool=pool, kind=kind, field_name=field_name, breakage=breakage),
                )
            )
        for unchecked_pool in unchecked_pools:
            grouped_data_paths.add_data_path(
                DataPath(
                    branch=request.branch.name,
                    path_type=PathType.NODE,
                    node_id=unchecked_pool.id,
                    kind=InfrahubKind.NUMBERPOOL,
                    field_name=field_name,
                    value=f"{unchecked_pool.reason}; the change to {kind}.{field_name} cannot be checked against this pool",
                )
            )
        return [grouped_data_paths]

    @staticmethod
    def _may_reference(stored_scope: object, elements: Iterable[ScopeElement], field_name: str) -> bool:
        # A scope that cannot be read can only be searched as text, so naming the field's id or a name it carries
        # before or after the change counts as a use.
        serialized = json.dumps(stored_scope, default=repr)
        texts = {field_name}.union(*({element.name, element.id} for element in elements))
        return any(json.dumps(text) in serialized for text in texts)

    def _candidate_field(
        self, request: SchemaConstraintValidatorRequest, field_name: str
    ) -> AttributeSchema | RelationshipSchema | None:
        kind = request.schema_path.schema_kind
        if not request.schema_branch.has(name=kind):
            return None
        return request.schema_branch.get(name=kind, duplicate=False).get_field(name=field_name, raise_on_error=False)

    def _previous_fields(
        self, request: SchemaConstraintValidatorRequest, field: AttributeSchema | RelationshipSchema
    ) -> list[AttributeSchema | RelationshipSchema]:
        # A field renamed by the same load keeps its id, while a field without an id is found by its name.
        kind = request.schema_path.schema_kind
        previous_fields: list[AttributeSchema | RelationshipSchema] = []
        for schema_branch in self._previous_schemas(request=request):
            if not schema_branch.has(name=kind):
                continue
            kind_schema = schema_branch.get(name=kind, duplicate=False)
            fields: list[AttributeSchema | RelationshipSchema] = [*kind_schema.attributes, *kind_schema.relationships]
            previous_fields.extend(
                previous
                for previous in fields
                if (previous.id == field.id if field.id else previous.name == field.name)
            )
        return previous_fields

    # A proposed change or a merge also raises the constraints below for the data changed on a field, so a property
    # the schema leaves unchanged cannot break a scope and needs no pool read.

    def _made_optional(self, request: SchemaConstraintValidatorRequest, field_name: str) -> ScopeBreakage | None:
        field = self._candidate_field(request=request, field_name=field_name)
        if field is None or not field.optional:
            return None
        if all(previous.optional for previous in self._previous_fields(request=request, field=field)):
            return None
        return ScopeBreakage(dependency=PoolDependency.SCOPE_ELEMENT, reason="a scope element must stay required")

    def _made_many(self, request: SchemaConstraintValidatorRequest, field_name: str) -> ScopeBreakage | None:
        field = self._candidate_field(request=request, field_name=field_name)
        if not isinstance(field, RelationshipSchema) or field.cardinality == RelationshipCardinality.ONE:
            return None
        if all(
            isinstance(previous, RelationshipSchema) and previous.cardinality != RelationshipCardinality.ONE
            for previous in self._previous_fields(request=request, field=field)
        ):
            return None
        return ScopeBreakage(
            dependency=PoolDependency.SCOPE_ELEMENT,
            reason="a scope element must stay a relationship of cardinality one",
        )

    def _made_unique(self, request: SchemaConstraintValidatorRequest, field_name: str) -> ScopeBreakage | None:
        field = self._candidate_field(request=request, field_name=field_name)
        if not isinstance(field, AttributeSchema) or not field.unique:
            return None
        if all(
            isinstance(previous, AttributeSchema) and previous.unique
            for previous in self._previous_fields(request=request, field=field)
        ):
            return None
        return ScopeBreakage(
            dependency=PoolDependency.TRACKED_ATTRIBUTE,
            reason="a globally unique number cannot be allocated per division",
        )

    def _made_non_scalar(self, request: SchemaConstraintValidatorRequest, field_name: str) -> ScopeBreakage | None:
        field = self._candidate_field(request=request, field_name=field_name)
        if not isinstance(field, AttributeSchema) or field.kind not in NON_SCALAR_ATTRIBUTE_KINDS:
            return None
        if all(
            isinstance(previous, AttributeSchema) and previous.kind in NON_SCALAR_ATTRIBUTE_KINDS
            for previous in self._previous_fields(request=request, field=field)
        ):
            return None
        return ScopeBreakage(
            dependency=PoolDependency.SCOPE_ELEMENT, reason="a scope element must hold a single scalar value"
        )

    def _removed(self, request: SchemaConstraintValidatorRequest, field_name: str) -> ScopeBreakage | None:  # noqa: ARG002
        return ScopeBreakage(
            dependency=PoolDependency.SCOPE_ELEMENT, reason="a scope element cannot be removed while the pool exists"
        )

    def _accepted(self, request: SchemaConstraintValidatorRequest, field_name: str) -> ScopeBreakage | None:  # noqa: ARG002
        return None

    def _kinds_sharing_fields(self, kind_schema: MainSchemaTypes) -> set[str]:
        # A pool on a generic reaches the fields of its implementing kinds, and an inherited field is changed on the
        # generic only, so the pools on both sides of the inheritance can depend on the changed field.
        kinds = {kind_schema.kind}
        if isinstance(kind_schema, NodeSchema):
            kinds.update(kind_schema.inherit_from)
        elif isinstance(kind_schema, GenericSchema):
            kinds.update(kind_schema.used_by)
        return kinds

    def _previous_schemas(self, request: SchemaConstraintValidatorRequest) -> list[SchemaBranch]:
        # A schema load builds the candidate on the branch's own schema, while a proposed change, a merge or a rebase
        # builds it on the destination's schema, so a field the change removes or renames is found on one of them.
        names = [request.branch.name]
        if request.schema_branch.name != request.branch.name:
            names.append(request.schema_branch.name)
        return [self.schema_source.get_schema_branch(name=name) for name in names]

    def _scope_elements(
        self, request: SchemaConstraintValidatorRequest, schema_branches: list[SchemaBranch], field_name: str
    ) -> list[ScopeElement]:
        # The changed field carries its name from the candidate schema, so a field renamed by the same load is found
        # by the id it keeps.
        field = self._candidate_field(request=request, field_name=field_name)
        entry: str | dict[str, str] = {"id": field.id} if field is not None and field.id else field_name
        elements: dict[str, ScopeElement] = {}
        for schema_branch in schema_branches:
            try:
                scope = AllocationScopeResolver(schema_branch=schema_branch).resolve(
                    kind=request.schema_path.schema_kind, entries=[entry]
                )
            except ValidationError:
                # A field the resolver cannot identify cannot be stored in any scope.
                continue
            elements.setdefault(scope.elements[0].id, scope.elements[0])
        return list(elements.values())

    def _describe(self, pool: ScopedNumberPool, kind: str, field_name: str, breakage: ScopeBreakage) -> str:
        if breakage.dependency == PoolDependency.TRACKED_ATTRIBUTE:
            return f"pool {pool.name} allocates {kind}.{field_name} per division; {breakage.reason}"
        return f"pool {pool.name} divides its numbers by {kind}.{field_name}; {breakage.reason}"
