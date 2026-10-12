from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, override

from infrahub.exceptions import ValidationError
from infrahub.pools.scope import (
    SCOPE_FIELD,
    SCOPE_SEPARATOR,
    AllocationScope,
    AllocationScopeResolver,
    AllocationScopeValidator,
    ScopeElement,
    UnknownScopeElementError,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from infrahub.core.schema import AttributeSchema, MainSchemaTypes, RelationshipSchema
    from infrahub.core.schema.schema_branch import SchemaBranch

UNSAVED_ELEMENT_ID_PREFIX = "unsaved:"


class _DeclaredScopeResolver(AllocationScopeResolver):
    """Resolves a declared scope on a candidate schema, where a field added by the same load holds no id yet.

    The placeholder id only serves to tell elements apart while validating; a stored scope always holds the id the
    saved schema assigns.
    """

    @override
    def _element_id(self, node_schema: MainSchemaTypes, field: AttributeSchema | RelationshipSchema) -> str | None:
        return super()._element_id(node_schema=node_schema, field=field) or (
            f"{UNSAVED_ELEMENT_ID_PREFIX}{node_schema.kind}.{field.name}"
        )


class SchemaBranchSource(Protocol):
    def get_schema_branch(self, name: str) -> SchemaBranch: ...


@dataclass(frozen=True)
class DefaultBranchSchema:
    """Where a worker reads the schema of the default branch, and the name of that branch."""

    source: SchemaBranchSource
    name: str

    def for_candidate(self, candidate: SchemaBranch) -> SchemaBranch:
        """Return the schema of the default branch, which is the candidate itself when the candidate is that branch."""
        if candidate.name == self.name:
            return candidate
        return self.source.get_schema_branch(name=self.name)


class DeclaredScopeValidator:
    """Checks the allocation scope a NumberPool attribute declares on a candidate schema."""

    def __init__(self, candidate: SchemaBranch, default_branch_schema: Callable[[], SchemaBranch]) -> None:
        self.candidate = candidate
        self.default_branch_schema = default_branch_schema

    def validate(self, kind: str, tracked_attribute: str, entries: list[str] | None, pool_exists: bool) -> None:
        """Refuse a declaration whose elements cannot divide the pool over the kind's tracked attribute.

        A new declaration resolves against the schema of the default branch, and its elements must also divide the
        pool on the candidate. Once the pool exists, the declaration is checked on the candidate only and a name that
        resolves to nothing is accepted here, since only the stored scope can tell a renamed element from a changed
        declaration.

        Raises:
            ValidationError: When an element cannot divide the pool, naming it with the reason alone, when the
                schema of the default branch does not define the kind of a new declaration, or when a name of a new
                declaration on a branch holds another field there than on the default branch.

        """
        if pool_exists:
            scope = self._resolve_known_entries(kind=kind, entries=entries)
        else:
            default_branch_schema = self.default_branch_schema()
            default_scope = _DeclaredScopeResolver(schema_branch=default_branch_schema).resolve(
                kind=kind, entries=entries
            )
            AllocationScopeValidator(schema_branch=default_branch_schema).validate(
                kind=kind, tracked_attribute=tracked_attribute, scope=default_scope
            )
            if default_branch_schema is self.candidate:
                return
            scope = _DeclaredScopeResolver(schema_branch=self.candidate).resolve(kind=kind, entries=entries)
            # The pool stores the default branch's ids, so a name must reach the same field on the branch.
            for default_element, element in zip(default_scope.elements, scope.elements, strict=True):
                if default_element.id != element.id:
                    raise ValidationError(
                        {
                            SCOPE_FIELD: f'"{element.name}" is a different field on branch {self.candidate.name} than'
                            f" on the default branch {default_branch_schema.name}; declare the scope once the field is"
                            " the same on both branches"
                        }
                    )

        AllocationScopeValidator(schema_branch=self.candidate).validate(
            kind=kind, tracked_attribute=tracked_attribute, scope=scope
        )

    def _resolve_known_entries(self, kind: str, entries: list[str] | None) -> AllocationScope:
        resolver = _DeclaredScopeResolver(schema_branch=self.candidate)
        elements: list[ScopeElement] = []
        for entry in entries or []:
            try:
                elements.extend(resolver.resolve(kind=kind, entries=[entry]).elements)
            except UnknownScopeElementError:
                if SCOPE_SEPARATOR in entry:
                    raise
                continue
        return AllocationScope(elements=tuple(elements))


def scope_refusal_reason(error: ValidationError) -> str:
    """Return the reason of a scope refusal without the field it is attached to."""
    if isinstance(error.input_value, dict) and isinstance(reason := error.input_value.get(SCOPE_FIELD), str):
        return reason
    return error.message
