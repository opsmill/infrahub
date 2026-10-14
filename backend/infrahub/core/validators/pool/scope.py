from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from infrahub.core.constants import RelationshipCardinality
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.validators.enum import ConstraintIdentifier
from infrahub.core.validators.schema_branch.number_pool_scope_validator import (
    DeclaredScopeComparator,
    DeclaredScopeValidator,
    scope_refusal_reason,
)
from infrahub.exceptions import SchemaNotFoundError, ValidationError
from infrahub.pools.scope import NON_SCALAR_ATTRIBUTE_KINDS, SCOPE_FIELD, AllocationScopeResolver, ScopeElement

from ..interface import ConstraintCheckerInterface
from .scope_dependency import ChangedField, PoolDependency, ScopeBreakage

if TYPE_CHECKING:
    from collections.abc import Iterable

    from infrahub.core.path import GroupedDataPaths
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.pools.scoped_number_pool_reader import ScopedNumberPool

    from ..model import SchemaConstraintValidatorRequest
    from .scope_dependency import DependentPoolFinder, ScopeViolationBuilder


class SchemaBranchSource(Protocol):
    def get_schema_branch(self, name: str) -> SchemaBranch: ...


class ScopedNumberPoolSource(Protocol):
    async def get_for_kinds(self, kinds: Iterable[str]) -> list[ScopedNumberPool]: ...

    async def get_by_ids(self, ids: Iterable[str]) -> list[ScopedNumberPool]: ...

    async def get_schema_pool_ids(self, attributes: Iterable[tuple[str, str]]) -> dict[tuple[str, str], str]: ...


@dataclass(frozen=True)
class DeclaringAttribute:
    """A NumberPool attribute on the kind that declares its allocation scope, with the pool the schema created.

    The pool id is unknown until it is written into the attribute's parameters.
    """

    kind: str
    attribute_name: str
    pool_id: str | None
    entries: list[str] | None


RENAME_CONSTRAINTS = frozenset({"attribute.name.update", "relationship.name.update"})
REMOVE_CONSTRAINTS = frozenset({"node.attribute.remove", "node.relationship.remove"})
ALLOCATION_SCOPE_CONSTRAINT = ConstraintIdentifier.ATTRIBUTE_PARAMETERS_ALLOCATION_SCOPE_UPDATE.value
UNIQUENESS_CONSTRAINTS = ConstraintIdentifier.NODE_UNIQUENESS_CONSTRAINTS_UPDATE.value
UNIQUE_CONSTRAINT = "attribute.unique.update"

# What a change reports when it gives a scope element, or the tracked attribute, the property its constraint names.
PROPERTY_BREAKAGES = {
    "attribute.optional.update": ScopeBreakage(
        dependency=PoolDependency.SCOPE_ELEMENT, reason="a scope element must stay required"
    ),
    "relationship.optional.update": ScopeBreakage(
        dependency=PoolDependency.SCOPE_ELEMENT, reason="a scope element must stay required"
    ),
    "relationship.cardinality.update": ScopeBreakage(
        dependency=PoolDependency.SCOPE_ELEMENT, reason="a scope element must stay a relationship of cardinality one"
    ),
    UNIQUE_CONSTRAINT: ScopeBreakage(
        dependency=PoolDependency.TRACKED_ATTRIBUTE, reason="a globally unique number cannot be allocated per division"
    ),
    "attribute.kind.update": ScopeBreakage(
        dependency=PoolDependency.SCOPE_ELEMENT, reason="a scope element must hold a single scalar value"
    ),
}
REMOVAL_BREAKAGE = ScopeBreakage(
    dependency=PoolDependency.SCOPE_ELEMENT, reason="a scope element cannot be removed while the pool exists"
)


class NumberPoolScopeChecker(ConstraintCheckerInterface):
    """Refuses a schema change that stops a field from giving the one value per node that a pool's scope needs."""

    # Only a schema change can break a scope, so a data change never needs this checker.
    triggered_by_data_change = False

    def __init__(
        self,
        pool_source: ScopedNumberPoolSource,
        schema_source: SchemaBranchSource,
        pool_finder: DependentPoolFinder,
        violation_builder: ScopeViolationBuilder,
        declared_scope_validator: DeclaredScopeValidator,
        declared_scope_comparator: DeclaredScopeComparator,
        default_branch_name: str,
    ) -> None:
        self.pool_source = pool_source
        self.declared_scope_validator = declared_scope_validator
        self.declared_scope_comparator = declared_scope_comparator
        self.schema_source = schema_source
        self.default_branch_name = default_branch_name
        self.pool_finder = pool_finder
        self.violation_builder = violation_builder

    @property
    def name(self) -> str:
        return "number_pool.scope"

    def supports(self, request: SchemaConstraintValidatorRequest) -> bool:
        """Accept the constraints whose change can break a scope.

        They include the node uniqueness constraint, which another checker is registered for.
        """
        return (
            request.constraint_name in PROPERTY_BREAKAGES
            or request.constraint_name in RENAME_CONSTRAINTS
            or request.constraint_name in REMOVE_CONSTRAINTS
            or request.constraint_name in {ALLOCATION_SCOPE_CONSTRAINT, UNIQUENESS_CONSTRAINTS}
        )

    async def check(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]:
        """Return one violation per number pool that the schema change stops from dividing its space.

        A change breaks a pool when the changed field is one of the pool's scope elements and stops holding one
        required scalar value per node, or when the field is the pool's tracked attribute and becomes unique. A change
        that leaves the field's property as it was is accepted without reading any pool.

        Raises:
            ValueError: When the request names no field.

        """
        field_name = request.schema_path.field_name
        if not field_name:
            raise ValueError("field_name is not defined")

        constraint_name = request.constraint_name
        if constraint_name in RENAME_CONSTRAINTS:
            return await self._check_declarations(
                request=request,
                field_name=field_name,
                declarations=self._declarations_reaching_renamed_field(request=request),
            )
        if constraint_name == ALLOCATION_SCOPE_CONSTRAINT:
            return await self._check_declarations(
                request=request,
                field_name=field_name,
                declarations=self._changed_declaration(request=request, field_name=field_name),
            )
        if constraint_name == UNIQUENESS_CONSTRAINTS:
            return await self._check_attributes_made_unique(request=request)
        if constraint_name in REMOVE_CONSTRAINTS:
            return await self._check_breakage(request=request, field_name=field_name, breakage=REMOVAL_BREAKAGE)
        if not self._gained_property(request=request, field_name=field_name, constraint_name=constraint_name):
            return []
        return await self._check_breakage(
            request=request, field_name=field_name, breakage=PROPERTY_BREAKAGES[constraint_name]
        )

    async def _check_attributes_made_unique(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]:
        """Return the violations of each attribute of the node that the uniqueness constraint change makes unique.

        A uniqueness constraint naming one attribute makes it unique on the node. The schema diff records that change
        under this constraint alone only for an inherited attribute, so only the inherited attributes go through the
        tracked-attribute rule here, and every other attribute is checked once under its own unique change.
        """
        kind = request.schema_path.schema_kind
        if not request.schema_branch.has(name=kind):
            return []
        results: list[GroupedDataPaths] = []
        for attribute in request.schema_branch.get(name=kind, duplicate=False).attributes:
            if not attribute.inherited:
                continue
            if self._gained_property(request=request, field_name=attribute.name, constraint_name=UNIQUE_CONSTRAINT):
                results.extend(
                    await self._check_breakage(
                        request=request, field_name=attribute.name, breakage=PROPERTY_BREAKAGES[UNIQUE_CONSTRAINT]
                    )
                )
        return results

    async def _check_breakage(
        self, request: SchemaConstraintValidatorRequest, field_name: str, breakage: ScopeBreakage
    ) -> list[GroupedDataPaths]:
        """Return one violation per pool that depends on the changed field, for a change known to break a scope.

        The pools of the kind and of the kinds sharing its fields through inheritance are read, under the names they
        had before the change, and each one is matched against the scope elements the field was before the change.
        No violation is returned when no schema before the change defines the kind.
        """
        previous_kinds = self._previous_kinds(request=request, previous_schemas=self._previous_schemas(request=request))
        if not previous_kinds:
            return []

        pools = await self.pool_source.get_for_kinds(
            kinds={
                kind
                for _, kind_schema in previous_kinds
                for kind in self._kinds_sharing_fields(kind_schema=kind_schema)
            }
        )
        field = ChangedField(
            kind=request.schema_path.schema_kind,
            name=field_name,
            elements=tuple(self._scope_elements(request=request, previous_kinds=previous_kinds, field_name=field_name)),
        )
        return [
            self.violation_builder.build(
                branch_name=request.branch.name,
                field=field,
                breakage=breakage,
                pools=self.pool_finder.find(pools=pools, field=field, dependency=breakage.dependency),
            )
        ]

    def _candidate_field(
        self, request: SchemaConstraintValidatorRequest, field_name: str
    ) -> AttributeSchema | RelationshipSchema | None:
        """Return the field the request names, as the candidate schema defines it, or None when it does not."""
        kind = request.schema_path.schema_kind
        if not request.schema_branch.has(name=kind):
            return None
        return request.schema_branch.get(name=kind, duplicate=False).get_field(name=field_name, raise_on_error=False)

    def _previous_fields(
        self,
        request: SchemaConstraintValidatorRequest,
        field: AttributeSchema | RelationshipSchema,
        previous_schemas: list[SchemaBranch],
    ) -> list[AttributeSchema | RelationshipSchema]:
        """Return the field as each schema before the change defines it.

        A field renamed by the same load keeps its id and is matched by it, while a field without an id, not saved
        yet, is matched by its name.
        """
        previous_fields: list[AttributeSchema | RelationshipSchema] = []
        for _, kind_schema in self._previous_kinds(request=request, previous_schemas=previous_schemas):
            fields: list[AttributeSchema | RelationshipSchema] = [*kind_schema.attributes, *kind_schema.relationships]
            previous_fields.extend(previous for previous in fields if self._same_field(previous=previous, field=field))
        return previous_fields

    @staticmethod
    def _same_field(
        previous: AttributeSchema | RelationshipSchema, field: AttributeSchema | RelationshipSchema
    ) -> bool:
        """Tell whether a field before the change is the field, by id, or by name for a field not saved yet."""
        # A field renamed by the same load keeps its id.
        return previous.id == field.id if field.id else previous.name == field.name

    def _gained_property(
        self, request: SchemaConstraintValidatorRequest, field_name: str, constraint_name: str
    ) -> bool:
        """Tell whether the change gives the field the property the constraint names, which it did not have before.

        A proposed change or a merge raises the constraint for every field whose data changed, so the field is compared
        with the same field before the change, and a property it already had is not a gain.
        """
        field = self._candidate_field(request=request, field_name=field_name)
        if field is None or not self._has_property(constraint_name=constraint_name, field=field):
            return False
        previous_fields = self._previous_fields(
            request=request, field=field, previous_schemas=self._previous_schemas(request=request)
        )
        return not all(
            self._has_property(constraint_name=constraint_name, field=previous) for previous in previous_fields
        )

    @staticmethod
    def _has_property(constraint_name: str, field: AttributeSchema | RelationshipSchema) -> bool:
        """Tell whether the field has the property that the constraint names and that breaks a scope."""
        match constraint_name:
            case "attribute.optional.update" | "relationship.optional.update":
                return field.optional
            case "relationship.cardinality.update":
                return isinstance(field, RelationshipSchema) and field.cardinality != RelationshipCardinality.ONE
            case "attribute.unique.update":
                return isinstance(field, AttributeSchema) and field.unique
            case "attribute.kind.update":
                return isinstance(field, AttributeSchema) and field.kind in NON_SCALAR_ATTRIBUTE_KINDS
        return False

    async def _check_declarations(
        self, request: SchemaConstraintValidatorRequest, field_name: str, declarations: list[DeclaringAttribute]
    ) -> list[GroupedDataPaths]:
        """Return one violation per schema-created pool whose declaration the change no longer matches.

        Raises:
            ValidationError: When a pool stores an allocation scope that is not a list of elements.

        """
        declarations_by_pool = await self._with_pool_ids(declarations=declarations)
        if not declarations_by_pool:
            return []
        pools = {
            pool.id: pool
            for pool in await self.pool_source.get_by_ids(ids={pool_id for pool_id, _ in declarations_by_pool})
        }
        previous_schemas = self._previous_schemas(request=request)

        refusals: list[tuple[str, str]] = []
        for pool_id, declaration in declarations_by_pool:
            pool = pools.get(pool_id)
            if pool is None:
                # The load accepted the names it could not resolve as a possible rename, which only a stored scope
                # can confirm, so a declaration without its pool is checked as a new one.
                reason = self._new_declaration_refusal(request=request, declaration=declaration)
            else:
                reason = self.declared_scope_comparator.refusal(
                    schema_branch=request.schema_branch,
                    previous_schemas=previous_schemas,
                    kind=declaration.kind,
                    entries=declaration.entries,
                    stored=pool.scope,
                )
            if reason is not None:
                refusals.append((pool_id, f"{declaration.kind}.{declaration.attribute_name}: {reason}"))
        return [
            self.violation_builder.build_refusals(
                branch_name=request.branch.name, field_name=field_name, refusals=refusals
            )
        ]

    def _new_declaration_refusal(
        self, request: SchemaConstraintValidatorRequest, declaration: DeclaringAttribute
    ) -> str | None:
        """Return why the declaration cannot scope a new pool, or None when it can."""
        try:
            self.declared_scope_validator.validate(
                candidate=request.schema_branch,
                default_branch_schema=self._default_branch_schema(candidate=request.schema_branch),
                kind=declaration.kind,
                tracked_attribute=declaration.attribute_name,
                entries=declaration.entries,
                pool_exists=False,
            )
        except ValidationError as exc:
            return f"{SCOPE_FIELD}: {scope_refusal_reason(error=exc)}"
        return None

    def _default_branch_schema(self, candidate: SchemaBranch) -> SchemaBranch:
        """Return the schema of the default branch, which is the candidate itself when the candidate is that branch."""
        if candidate.name == self.default_branch_name:
            return candidate
        return self.schema_source.get_schema_branch(name=self.default_branch_name)

    def _changed_declaration(
        self, request: SchemaConstraintValidatorRequest, field_name: str
    ) -> list[DeclaringAttribute]:
        """Return the declaration of the attribute whose allocation_scope the change updates."""
        kind = request.schema_path.schema_kind
        if not request.schema_branch.has(name=kind):
            return []
        kind_schema = request.schema_branch.get(name=kind, duplicate=False)
        attribute = kind_schema.get_attribute_or_none(name=field_name)
        # An inherited declaration is compared on the generic that declares it, so the pool is reported once.
        if attribute is None or attribute.inherited:
            return []
        declaration = self._declaring(kind=kind, attribute=attribute)
        return [declaration] if declaration is not None else []

    def _declarations_reaching_renamed_field(
        self, request: SchemaConstraintValidatorRequest
    ) -> list[DeclaringAttribute]:
        """Return the declarations of the kinds sharing the renamed field's fields that the same load leaves as is."""
        kind = request.schema_path.schema_kind
        if not request.schema_branch.has(name=kind):
            return []
        candidates: list[tuple[str, AttributeSchema, DeclaringAttribute]] = []
        for sharing_kind in sorted(
            self._kinds_sharing_fields(kind_schema=request.schema_branch.get(name=kind, duplicate=False))
        ):
            if not request.schema_branch.has(name=sharing_kind):
                continue
            kind_schema = request.schema_branch.get(name=sharing_kind, duplicate=False)
            # An inherited declaration is compared on the generic that declares it, so the pool is reported once, and
            # a rename cannot reach a declaration that names no element.
            for attribute in kind_schema.attributes:
                declaration = None if attribute.inherited else self._declaring(kind=sharing_kind, attribute=attribute)
                if declaration is not None and declaration.entries:
                    candidates.append((sharing_kind, attribute, declaration))
        if not candidates:
            return []

        # A declaration changed by the same load is compared under its own constraint, so the pool is reported once.
        previous_schemas = self._previous_schemas(request=request)
        return [
            declaration
            for sharing_kind, attribute, declaration in candidates
            if not any(
                self._declaration_changed(previous_schema=previous_schema, kind=sharing_kind, attribute=attribute)
                for previous_schema in previous_schemas
            )
        ]

    async def _with_pool_ids(self, declarations: list[DeclaringAttribute]) -> list[tuple[str, DeclaringAttribute]]:
        """Return the declarations that have a schema-created pool, each after the id of that pool."""
        # A pool the schema created holds the declaration's scope before its id is written into the attribute.
        missing = {
            (declaration.kind, declaration.attribute_name) for declaration in declarations if not declaration.pool_id
        }
        found = await self.pool_source.get_schema_pool_ids(attributes=missing) if missing else {}
        declarations_by_pool: list[tuple[str, DeclaringAttribute]] = []
        for declaration in declarations:
            pool_id = declaration.pool_id or found.get((declaration.kind, declaration.attribute_name))
            if pool_id is not None:
                declarations_by_pool.append((pool_id, declaration))
        return declarations_by_pool

    @staticmethod
    def _declaring(kind: str, attribute: AttributeSchema) -> DeclaringAttribute | None:
        """Return the attribute's declaration when it is a NumberPool attribute, and None otherwise."""
        parameters = attribute.parameters
        if not isinstance(parameters, NumberPoolParameters):
            return None
        return DeclaringAttribute(
            kind=kind,
            attribute_name=attribute.name,
            pool_id=parameters.number_pool_id,
            entries=parameters.allocation_scope,
        )

    @staticmethod
    def _declaration_changed(previous_schema: SchemaBranch, kind: str, attribute: AttributeSchema) -> bool:
        """Tell whether the attribute's declaration differs from the one on the schema before the change."""
        if not isinstance(attribute.parameters, NumberPoolParameters) or not previous_schema.has(name=kind):
            return False
        previous_kind = previous_schema.get(name=kind, duplicate=False)
        previous = next(
            (
                candidate
                for candidate in previous_kind.attributes
                if NumberPoolScopeChecker._same_field(previous=candidate, field=attribute)
            ),
            None,
        )
        if previous is None or not isinstance(previous.parameters, NumberPoolParameters):
            return False
        previous_entries = previous.parameters.allocation_scope
        entries = attribute.parameters.allocation_scope
        if previous_entries is None or entries is None:
            return previous_entries != entries
        # A reorder keeps the same divisions, so it does not change the declaration.
        return Counter(previous_entries) != Counter(entries)

    @staticmethod
    def _previous_kinds(
        request: SchemaConstraintValidatorRequest, previous_schemas: list[SchemaBranch]
    ) -> list[tuple[SchemaBranch, MainSchemaTypes]]:
        """Return each schema before the change that defines the changed kind, paired with that kind's definition.

        A kind renamed by the same load keeps its id and is matched by it, while a kind without an id, not saved yet,
        is matched by its name.
        """
        kind = request.schema_path.schema_kind
        kind_id = (
            request.schema_branch.get(name=kind, duplicate=False).id if request.schema_branch.has(name=kind) else None
        )
        previous_kinds: list[tuple[SchemaBranch, MainSchemaTypes]] = []
        for schema_branch in previous_schemas:
            if kind_id is not None:
                try:
                    previous_kinds.append((schema_branch, schema_branch.get_by_id(id=kind_id, duplicate=False)))
                except SchemaNotFoundError:
                    continue
            elif schema_branch.has(name=kind):
                previous_kinds.append((schema_branch, schema_branch.get(name=kind, duplicate=False)))
        return previous_kinds

    def _kinds_sharing_fields(self, kind_schema: MainSchemaTypes) -> set[str]:
        """Return the kind and the kinds it shares fields with through inheritance.

        A pool on a generic reaches the fields of the kinds that implement it, and an inherited field is changed on
        the generic only, so a pool on either side of the inheritance can depend on the changed field.
        """
        kinds = {kind_schema.kind}
        if isinstance(kind_schema, NodeSchema):
            kinds.update(kind_schema.inherit_from)
        elif isinstance(kind_schema, GenericSchema):
            kinds.update(kind_schema.used_by)
        return kinds

    def _previous_schemas(self, request: SchemaConstraintValidatorRequest) -> list[SchemaBranch]:
        """Return the schemas before the change.

        A schema load builds the candidate on the branch's own schema, while a proposed change, a merge or a rebase
        builds it on the destination's schema, so the changed field is looked up on both: a field the change
        removes or renames is found on one of the two.
        """
        names = [request.branch.name]
        if request.schema_branch.name != request.branch.name:
            names.append(request.schema_branch.name)
        return [self.schema_source.get_schema_branch(name=name) for name in names]

    def _scope_elements(
        self,
        request: SchemaConstraintValidatorRequest,
        previous_kinds: list[tuple[SchemaBranch, MainSchemaTypes]],
        field_name: str,
    ) -> list[ScopeElement]:
        """Return the scope elements that the changed field was on the schemas before the change.

        The request names the field as the candidate schema does, so a field renamed by the same load is looked up by
        the id it keeps. Each element appears once, and a field that no schema can resolve gives no element.
        """
        field = self._candidate_field(request=request, field_name=field_name)
        entry: str | dict[str, str] = {"id": field.id} if field is not None and field.id else field_name
        elements: dict[str, ScopeElement] = {}
        for schema_branch, kind_schema in previous_kinds:
            try:
                scope = AllocationScopeResolver(schema_branch=schema_branch).resolve(
                    kind=kind_schema.kind, entries=[entry]
                )
            except ValidationError:
                # A field the resolver cannot identify cannot be stored in any scope.
                continue
            elements.setdefault(scope.elements[0].id, scope.elements[0])
        return list(elements.values())
