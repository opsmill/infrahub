from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from infrahub.core.constants import RelationshipCardinality
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema
from infrahub.core.validators.enum import ConstraintIdentifier
from infrahub.exceptions import ValidationError
from infrahub.pools.scope import NON_SCALAR_ATTRIBUTE_KINDS, AllocationScopeResolver, ScopeElement

from ..interface import ConstraintCheckerInterface
from .scope_dependency import ChangedField, PoolDependency, ScopeBreakage

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from infrahub.core.path import GroupedDataPaths
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.pools.scoped_number_pool_reader import ScopedNumberPool

    from ..model import SchemaConstraintValidatorRequest
    from .scope_dependency import DependentPoolFinder, ScopeViolationBuilder


class ScopedNumberPoolSource(Protocol):
    async def get_for_kinds(self, kinds: Iterable[str]) -> list[ScopedNumberPool]: ...


class SchemaBranchSource(Protocol):
    def get_schema_branch(self, name: str) -> SchemaBranch: ...


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
    ) -> None:
        self.pool_source = pool_source
        self.schema_source = schema_source
        self.pool_finder = pool_finder
        self.violation_builder = violation_builder
        made_optional = self._gained_property_rule(
            predicate=lambda field: field.optional,
            breakage=ScopeBreakage(
                dependency=PoolDependency.SCOPE_ELEMENT, reason="a scope element must stay required"
            ),
        )
        made_unique = self._gained_property_rule(
            predicate=lambda field: isinstance(field, AttributeSchema) and field.unique,
            breakage=ScopeBreakage(
                dependency=PoolDependency.TRACKED_ATTRIBUTE,
                reason="a globally unique number cannot be allocated per division",
            ),
        )
        self._made_unique = made_unique
        self._rules: dict[str, Callable[[SchemaConstraintValidatorRequest, str], ScopeBreakage | None]] = {
            "attribute.optional.update": made_optional,
            "relationship.optional.update": made_optional,
            "relationship.cardinality.update": self._gained_property_rule(
                predicate=lambda field: (
                    isinstance(field, RelationshipSchema) and field.cardinality != RelationshipCardinality.ONE
                ),
                breakage=ScopeBreakage(
                    dependency=PoolDependency.SCOPE_ELEMENT,
                    reason="a scope element must stay a relationship of cardinality one",
                ),
            ),
            "attribute.unique.update": made_unique,
            "attribute.kind.update": self._gained_property_rule(
                predicate=lambda field: isinstance(field, AttributeSchema) and field.kind in NON_SCALAR_ATTRIBUTE_KINDS,
                breakage=ScopeBreakage(
                    dependency=PoolDependency.SCOPE_ELEMENT, reason="a scope element must hold a single scalar value"
                ),
            ),
            "node.attribute.remove": self._removed,
            "node.relationship.remove": self._removed,
        }

    @property
    def name(self) -> str:
        return "number_pool.scope"

    def supports(self, request: SchemaConstraintValidatorRequest) -> bool:
        """Accept the constraints whose change can break a scope.

        They include the node uniqueness constraint, which another checker is registered for.
        """
        return (
            request.constraint_name in self._rules
            or request.constraint_name == ConstraintIdentifier.NODE_UNIQUENESS_CONSTRAINTS_UPDATE.value
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

        if request.constraint_name == ConstraintIdentifier.NODE_UNIQUENESS_CONSTRAINTS_UPDATE.value:
            return await self._check_attributes_made_unique(request=request)

        breakage = self._rules[request.constraint_name](request, field_name)
        if breakage is None:
            return []
        return await self._check_breakage(request=request, field_name=field_name, breakage=breakage)

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
            breakage = self._made_unique(request, attribute.name)
            if breakage is not None:
                results.extend(
                    await self._check_breakage(request=request, field_name=attribute.name, breakage=breakage)
                )
        return results

    async def _check_breakage(
        self, request: SchemaConstraintValidatorRequest, field_name: str, breakage: ScopeBreakage
    ) -> list[GroupedDataPaths]:
        """Return one violation per pool that depends on the changed field, for a change known to break a scope.

        The pools of the kind and of the kinds sharing its fields through inheritance are read, and each one is
        matched against the scope elements the field was before the change. No violation is returned when no
        schema before the change defines the kind.
        """
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
        field = ChangedField(
            kind=kind,
            name=field_name,
            elements=tuple(
                self._scope_elements(request=request, schema_branches=previous_schemas, field_name=field_name)
            ),
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
        kind = request.schema_path.schema_kind
        previous_fields: list[AttributeSchema | RelationshipSchema] = []
        for schema_branch in previous_schemas:
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

    def _gained_property_rule(
        self, predicate: Callable[[AttributeSchema | RelationshipSchema], bool], breakage: ScopeBreakage
    ) -> Callable[[SchemaConstraintValidatorRequest, str], ScopeBreakage | None]:
        """Build the rule of a constraint that can break a scope by giving a field a property.

        A proposed change or a merge raises the constraint for every field whose data changed, so the rule compares
        the field with the same field before the change and reports nothing when it already had the property.

        Args:
            predicate: Whether a field has the property that breaks a scope, such as being optional.
            breakage: What the rule reports when the change gives the field that property.

        Returns:
            A rule that returns the breakage when the field has the property and did not have it before the change,
            and None otherwise.

        """

        def rule(request: SchemaConstraintValidatorRequest, field_name: str) -> ScopeBreakage | None:
            field = self._candidate_field(request=request, field_name=field_name)
            if field is None or not predicate(field):
                return None
            previous_fields = self._previous_fields(
                request=request, field=field, previous_schemas=self._previous_schemas(request=request)
            )
            if all(predicate(previous) for previous in previous_fields):
                return None
            return breakage

        return rule

    def _removed(self, request: SchemaConstraintValidatorRequest, field_name: str) -> ScopeBreakage | None:  # noqa: ARG002
        """Report that removing the field breaks the pools whose scope holds it."""
        return ScopeBreakage(
            dependency=PoolDependency.SCOPE_ELEMENT, reason="a scope element cannot be removed while the pool exists"
        )

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
        self, request: SchemaConstraintValidatorRequest, schema_branches: list[SchemaBranch], field_name: str
    ) -> list[ScopeElement]:
        """Return the scope elements that the changed field was on the schemas before the change.

        The request names the field as the candidate schema does, so a field renamed by the same load is looked up by
        the id it keeps. Each element appears once, and a field that no schema can resolve gives no element.
        """
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
