from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from infrahub.core.constants import InfrahubKind, PathType, RelationshipCardinality
from infrahub.core.path import DataPath, GroupedDataPaths
from infrahub.core.registry import registry
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.validators.enum import ConstraintIdentifier
from infrahub.core.validators.schema_branch.number_pool_scope_validator import (
    DeclaredScopeComparator,
    DeclaredScopeValidator,
    scope_refusal_reason,
)
from infrahub.exceptions import ValidationError
from infrahub.log import get_logger
from infrahub.pools.scope import NON_SCALAR_ATTRIBUTE_KINDS, SCOPE_FIELD, AllocationScopeResolver, ScopeElement

from ..interface import ConstraintCheckerInterface

log = get_logger()

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.pools.scoped_number_pool_reader import NumberPoolScopes, ScopedNumberPool

    from ..model import SchemaConstraintValidatorRequest


class ScopedNumberPoolSource(Protocol):
    async def get_for_kinds(self, kinds: Iterable[str]) -> NumberPoolScopes: ...

    async def get_by_ids(self, ids: Iterable[str]) -> NumberPoolScopes: ...


class SchemaBranchSource(Protocol):
    def get_schema_branch(self, name: str) -> SchemaBranch: ...


class PoolDependency(StrEnum):
    """What ties a pool to the changed field."""

    SCOPE_ELEMENT = "scope_element"
    TRACKED_ATTRIBUTE = "tracked_attribute"


@dataclass(frozen=True)
class DeclaringAttribute:
    """A NumberPool attribute whose schema created a pool, on the kind that declares its allocation scope."""

    kind: str
    attribute_name: str
    pool_id: str
    entries: list[str] | None


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
        }
        self._declaration_rules: dict[
            str, Callable[[SchemaConstraintValidatorRequest, str], list[DeclaringAttribute]]
        ] = {
            "attribute.name.update": self._declarations_reaching_renamed_field,
            "relationship.name.update": self._declarations_reaching_renamed_field,
            ConstraintIdentifier.ATTRIBUTE_PARAMETERS_ALLOCATION_SCOPE_UPDATE.value: self._changed_declaration,
        }

    @property
    def name(self) -> str:
        return "number_pool.scope"

    def supports(self, request: SchemaConstraintValidatorRequest) -> bool:
        return request.constraint_name in self._rules or request.constraint_name in self._declaration_rules

    async def check(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]:
        field_name = request.schema_path.field_name
        if not field_name:
            raise ValueError("field_name is not defined")

        if declaration_rule := self._declaration_rules.get(request.constraint_name):
            return await self._check_declarations(
                request=request, field_name=field_name, declarations=declaration_rule(request, field_name)
            )

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
                pool for pool in pools.readable if element_ids & {stored.id for stored in pool.scope.elements}
            ]
            unchecked_pools = [
                pool
                for pool in pools.unreadable
                if self._may_reference(stored_scope=pool.stored_scope, elements=elements, field_name=field_name)
            ]
        else:
            # A pool stores its tracked attribute by name, which is the pre-change name when the same load renames it.
            tracked_names = {field_name} | {element.name for element in elements}
            dependent_pools = [pool for pool in pools.readable if pool.tracked_attribute in tracked_names]
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

    async def _check_declarations(
        self, request: SchemaConstraintValidatorRequest, field_name: str, declarations: list[DeclaringAttribute]
    ) -> list[GroupedDataPaths]:
        if not declarations:
            return []
        read_pools = await self.pool_source.get_by_ids(ids={declaration.pool_id for declaration in declarations})
        pools = {pool.id: pool for pool in read_pools.readable}
        unreadable_pools = {pool.id: pool for pool in read_pools.unreadable}
        comparator = DeclaredScopeComparator(schema_branch=request.schema_branch)
        validator = DeclaredScopeValidator(
            candidate=request.schema_branch, default_branch_schema=lambda: self._default_branch_schema(request=request)
        )

        grouped_data_paths = GroupedDataPaths()
        for declaration in declarations:
            pool = pools.get(declaration.pool_id)
            reason: str | None
            if unreadable_pool := unreadable_pools.get(declaration.pool_id):
                # A changed declaration cannot be compared with a stored scope that cannot be read.
                reason = (
                    f"{unreadable_pool.reason}; the change to {request.schema_path.schema_kind}.{field_name}"
                    " cannot be checked against this pool"
                )
            elif pool is None:
                # The load accepted the names it could not resolve as a possible rename, which only a stored scope
                # can confirm, so a declaration without its pool is checked as a new one.
                reason = self._new_declaration_refusal(validator=validator, declaration=declaration)
            else:
                reason = comparator.refusal(kind=declaration.kind, entries=declaration.entries, stored=pool.scope)
            if reason is None:
                continue
            grouped_data_paths.add_data_path(
                DataPath(
                    branch=request.branch.name,
                    path_type=PathType.NODE,
                    node_id=declaration.pool_id,
                    kind=InfrahubKind.NUMBERPOOL,
                    field_name=field_name,
                    value=f"{declaration.kind}.{declaration.attribute_name}: {reason}",
                )
            )
        return [grouped_data_paths]

    def _previous_schemas(self, request: SchemaConstraintValidatorRequest) -> list[SchemaBranch]:
        # A schema load builds the candidate on the branch's own schema, while a proposed change, a merge or a rebase
        # builds it on the destination's schema, so a field the change removes or renames is found on one of them.
        names = [request.branch.name]
        if request.schema_branch.name != request.branch.name:
            names.append(request.schema_branch.name)
        return [self.schema_source.get_schema_branch(name=name) for name in names]

    def _default_branch_schema(self, request: SchemaConstraintValidatorRequest) -> SchemaBranch:
        if request.branch.name == registry.default_branch:
            return request.schema_branch
        return self.schema_source.get_schema_branch(name=registry.default_branch)

    @staticmethod
    def _new_declaration_refusal(validator: DeclaredScopeValidator, declaration: DeclaringAttribute) -> str | None:
        try:
            validator.validate(
                kind=declaration.kind,
                tracked_attribute=declaration.attribute_name,
                entries=declaration.entries,
                pool_exists=False,
            )
        except ValidationError as exc:
            return f"{SCOPE_FIELD}: {scope_refusal_reason(error=exc)}"
        return None

    def _changed_declaration(
        self, request: SchemaConstraintValidatorRequest, field_name: str
    ) -> list[DeclaringAttribute]:
        kind = request.schema_path.schema_kind
        if not request.schema_branch.has(name=kind):
            return []
        kind_schema = request.schema_branch.get(name=kind, duplicate=False)
        attribute = kind_schema.get_attribute_or_none(name=field_name)
        # An inherited declaration is compared on the generic that declares it, so the pool is reported once.
        if attribute is None or attribute.inherited:
            return []
        return self._declaring(kind=kind, attribute=attribute)

    def _declarations_reaching_renamed_field(
        self,
        request: SchemaConstraintValidatorRequest,
        field_name: str,  # noqa: ARG002
    ) -> list[DeclaringAttribute]:
        kind = request.schema_path.schema_kind
        if not request.schema_branch.has(name=kind):
            return []
        previous_schemas = self._previous_schemas(request=request)
        declarations: list[DeclaringAttribute] = []
        for sharing_kind in sorted(
            self._kinds_sharing_fields(kind_schema=request.schema_branch.get(name=kind, duplicate=False))
        ):
            if not request.schema_branch.has(name=sharing_kind):
                continue
            kind_schema = request.schema_branch.get(name=sharing_kind, duplicate=False)
            for attribute in kind_schema.attributes:
                # An inherited declaration is compared on the generic that declares it, and a declaration changed by
                # the same load is compared under its own constraint, so the pool is reported once.
                if attribute.inherited or any(
                    self._declaration_changed(previous_schema=previous_schema, kind=sharing_kind, attribute=attribute)
                    for previous_schema in previous_schemas
                ):
                    continue
                declarations.extend(self._declaring(kind=sharing_kind, attribute=attribute))
        return declarations

    @staticmethod
    def _declaring(kind: str, attribute: AttributeSchema) -> list[DeclaringAttribute]:
        parameters = attribute.parameters
        if not isinstance(parameters, NumberPoolParameters) or parameters.number_pool_id is None:
            return []
        return [
            DeclaringAttribute(
                kind=kind,
                attribute_name=attribute.name,
                pool_id=parameters.number_pool_id,
                entries=parameters.allocation_scope,
            )
        ]

    @staticmethod
    def _declaration_changed(previous_schema: SchemaBranch, kind: str, attribute: AttributeSchema) -> bool:
        if not isinstance(attribute.parameters, NumberPoolParameters) or not previous_schema.has(name=kind):
            return False
        previous = previous_schema.get(name=kind, duplicate=False).get_attribute_or_none(name=attribute.name)
        if previous is None or not isinstance(previous.parameters, NumberPoolParameters):
            return False
        return previous.parameters.allocation_scope != attribute.parameters.allocation_scope

    def _kinds_sharing_fields(self, kind_schema: MainSchemaTypes) -> set[str]:
        # A pool on a generic reaches the fields of its implementing kinds, and an inherited field is changed on the
        # generic only, so the pools on both sides of the inheritance can depend on the changed field.
        kinds = {kind_schema.kind}
        if isinstance(kind_schema, NodeSchema):
            kinds.update(kind_schema.inherit_from)
        elif isinstance(kind_schema, GenericSchema):
            kinds.update(kind_schema.used_by)
        return kinds

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
