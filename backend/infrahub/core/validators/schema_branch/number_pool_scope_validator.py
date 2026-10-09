from __future__ import annotations

from typing import TYPE_CHECKING, override

from infrahub.pools.scope import SCOPE_FIELD, AllocationScopeResolver, AllocationScopeValidator

if TYPE_CHECKING:
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


class DeclaredScopeValidator:
    """Checks the allocation scope a NumberPool attribute declares on a candidate schema."""

    def __init__(self, candidate: SchemaBranch) -> None:
        self.candidate = candidate

    def validate(self, kind: str, tracked_attribute: str, entries: list[str] | None) -> None:
        """Refuse a declaration whose elements cannot divide the pool over the kind's tracked attribute.

        Raises:
            ValidationError: When an element cannot divide the pool, naming it with the reason alone.

        """
        AllocationScopeValidator(schema_branch=self.candidate).validate(
            kind=kind,
            tracked_attribute=tracked_attribute,
            scope=_DeclaredScopeResolver(schema_branch=self.candidate).resolve(kind=kind, entries=entries),
        )


def scope_refusal_reason(error: ValidationError) -> str:
    """Return the reason of a scope refusal without the field it is attached to."""
    if isinstance(error.input_value, dict) and isinstance(reason := error.input_value.get(SCOPE_FIELD), str):
        return reason
    return error.message
