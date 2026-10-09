from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, override

from infrahub.core.registry import registry
from infrahub.exceptions import InitializationError
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
    from infrahub.exceptions import ValidationError

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
    def has_schema_branch(self, name: str) -> bool: ...

    def get_schema_branch(self, name: str) -> SchemaBranch: ...


def registered_schema_branch(schema_source: SchemaBranchSource, name: str, unloaded_message: str) -> SchemaBranch:
    """Return the schema registered for the branch, without registering an empty one for a branch not loaded.

    Raises:
        InitializationError: When the schema of the branch is not loaded, with the message given.

    """
    if not schema_source.has_schema_branch(name=name):
        raise InitializationError(unloaded_message)
    return schema_source.get_schema_branch(name=name)


def registered_default_branch_schema(
    candidate: SchemaBranch, schema_source: SchemaBranchSource | None = None
) -> SchemaBranch:
    """Return the schema of the default branch, which is the candidate itself when the candidate is that branch.

    Raises:
        InitializationError: When the schema of the default branch is not loaded.

    """
    if candidate.name == registry.default_branch:
        return candidate
    return registered_schema_branch(
        schema_source=schema_source or registry.schema,
        name=registry.default_branch,
        unloaded_message=f"The schema of the default branch {registry.default_branch} is not loaded; an allocation"
        f" scope declared on branch {candidate.name} cannot be resolved",
    )


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
            ValidationError: When an element cannot divide the pool, naming it with the reason alone, or when the
                schema of the default branch does not define the kind of a new declaration.
            InitializationError: When a new declaration needs the schema of the default branch and it is not loaded.

        """
        if pool_exists:
            scope = self._resolve_known_entries(kind=kind, entries=entries)
        else:
            default_branch_schema = self.default_branch_schema()
            AllocationScopeValidator(schema_branch=default_branch_schema).validate(
                kind=kind,
                tracked_attribute=tracked_attribute,
                scope=_DeclaredScopeResolver(schema_branch=default_branch_schema).resolve(kind=kind, entries=entries),
            )
            if default_branch_schema is self.candidate:
                return
            scope = _DeclaredScopeResolver(schema_branch=self.candidate).resolve(kind=kind, entries=entries)

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
