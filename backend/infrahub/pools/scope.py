from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.constants import RelationshipCardinality
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.exceptions import ValidationError

if TYPE_CHECKING:
    from infrahub.core.schema import AttributeSchema, MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch

SCOPE_FIELD = "allocation_scope"
SCOPE_SEPARATOR = "__"
NON_SCALAR_ATTRIBUTE_KINDS = frozenset({"List", "JSON", "Any"})


@dataclass(frozen=True)
class ScopeElement:
    """An attribute or a relationship of the pool's kind, referenced by its schema id and shown by its name."""

    id: str
    name: str

    def to_stored(self) -> dict[str, str]:
        return {"id": self.id, "name": self.name}


@dataclass(frozen=True)
class AllocationScope:
    """The ordered elements that divide a pool's space; no element means the pool allocates from one space."""

    elements: tuple[ScopeElement, ...] = ()

    @classmethod
    def from_stored(cls, value: object, pool: str) -> AllocationScope:
        """Read the scope stored on `pool`, absent or empty meaning unscoped.

        Raises:
            ValidationError: the value is not a list, or an entry is not an object holding a text `id` and a
                text `name`.

        """
        if value is None:
            entries: list[Any] = []
        elif isinstance(value, list):
            entries = value
        else:
            raise ValidationError(
                f"allocation_scope of pool {pool}: the stored value {json.dumps(value, default=repr)} is not a list "
                "of elements; recreate the pool to set its scope"
            )
        elements: list[ScopeElement] = []
        for entry in entries:
            if not (
                isinstance(entry, dict) and isinstance(entry.get("id"), str) and isinstance(entry.get("name"), str)
            ):
                raise ValidationError(
                    f"allocation_scope of pool {pool}: the stored entry {json.dumps(entry, default=repr)} is not an element "
                    'with an "id" and a "name"; recreate the pool to set its scope'
                )
            elements.append(ScopeElement(id=entry["id"], name=entry["name"]))
        return cls(elements=tuple(elements))

    def to_stored(self) -> list[dict[str, str]]:
        return [element.to_stored() for element in self.elements]

    @property
    def is_empty(self) -> bool:
        return not self.elements

    @property
    def element_names(self) -> tuple[str, ...]:
        return tuple(element.name for element in self.elements)


@dataclass(frozen=True)
class Division:
    """The values an object has for the scope elements, in scope order; one division is one space of the pool.

    A scope element is a relationship or a scalar attribute, so each value is a peer id or a scalar as stored.
    """

    values: tuple[str | int | float | bool, ...]

    @property
    def key(self) -> str:
        """Return a hash of the values that stays the same across processes, used to name the division's lock."""
        encoded = json.dumps(list(self.values), separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(encoded.encode("ascii")).hexdigest()


def _get_kind_schema(schema_branch: SchemaBranch, kind: str) -> MainSchemaTypes:
    if not schema_branch.has(name=kind):
        raise ValidationError({SCOPE_FIELD: f"{kind} is not defined on branch {schema_branch.name}"})
    return schema_branch.get(name=kind, duplicate=False)


def _is_input_entry(entry: object) -> bool:
    return isinstance(entry, str) or (isinstance(entry, dict) and isinstance(entry.get("id"), str))


class AllocationScopeResolver:
    """Turns the entries sent for an allocation scope into the scope elements of a kind on a schema branch."""

    def __init__(self, schema_branch: SchemaBranch) -> None:
        self.schema_branch = schema_branch

    def resolve(self, kind: str, entries: object) -> AllocationScope:
        """Return the scope the entries name on the kind, in entry order, reading None as an empty scope.

        An entry is an element name, an element id, or an object whose `id` names the element. Whether each element
        can divide a pool is not checked here.

        Raises:
            ValidationError: When the entries are not a list, when an entry is a path, names no attribute or
                relationship of the kind or names a field whose schema is not saved, or when the schema branch does
                not define the kind.

        """
        raw_entries = self._parse(entries=entries)
        if not raw_entries:
            return AllocationScope()

        node_schema = _get_kind_schema(schema_branch=self.schema_branch, kind=kind)
        return AllocationScope(
            elements=tuple(self._resolve_entry(node_schema=node_schema, entry=entry) for entry in raw_entries)
        )

    def refresh_names(self, scope: AllocationScope, kind: str) -> AllocationScope:
        """Return the scope with each element named as the kind names it now, keeping an element no field holds.

        Raises:
            ValidationError: When the schema branch does not define the kind.

        """
        node_schema = _get_kind_schema(schema_branch=self.schema_branch, kind=kind)
        names_by_id: dict[str, str] = {}
        for field in self._fields(node_schema=node_schema):
            names_by_id.update(dict.fromkeys(self._candidate_ids(node_schema=node_schema, field=field), field.name))
        return AllocationScope(
            elements=tuple(
                ScopeElement(id=element.id, name=names_by_id.get(element.id, element.name))
                for element in scope.elements
            )
        )

    def _parse(self, entries: object) -> list[str | dict[str, Any]]:
        if entries is None:
            return []
        if not isinstance(entries, list) or not all(_is_input_entry(entry) for entry in entries):
            raise ValidationError({SCOPE_FIELD: "the allocation scope must be a list of entries"})
        return list(entries)

    def _resolve_entry(self, node_schema: MainSchemaTypes, entry: str | dict[str, Any]) -> ScopeElement:
        label = entry if isinstance(entry, str) else entry["id"]
        if isinstance(entry, str) and SCOPE_SEPARATOR in entry:
            raise ValidationError(
                {
                    SCOPE_FIELD: f'"{entry}" is a path; a scope element must be an attribute or a relationship'
                    f" of {node_schema.kind} itself"
                }
            )

        field = self._find_field(node_schema=node_schema, entry=entry)
        if field is None:
            raise ValidationError({SCOPE_FIELD: self._not_found_message(node_schema=node_schema, label=label)})

        element_id = self._element_id(node_schema=node_schema, field=field)
        if element_id is None:
            raise ValidationError(
                {
                    SCOPE_FIELD: f'"{field.name}" has no id; the schema of {node_schema.kind} is not saved'
                    f" on branch {self.schema_branch.name}"
                }
            )
        return ScopeElement(id=element_id, name=field.name)

    def _find_field(
        self, node_schema: MainSchemaTypes, entry: str | dict[str, Any]
    ) -> AttributeSchema | RelationshipSchema | None:
        if isinstance(entry, str) and (
            field := node_schema.get_attribute_or_none(name=entry) or node_schema.get_relationship_or_none(name=entry)
        ):
            return field
        entry_id = entry if isinstance(entry, str) else entry["id"]
        for candidate in self._fields(node_schema=node_schema):
            if entry_id in self._candidate_ids(node_schema=node_schema, field=candidate):
                return candidate
        return None

    def _not_found_message(self, node_schema: MainSchemaTypes, label: str) -> str:
        if isinstance(node_schema, GenericSchema) and any(
            self._declares(kind=kind, name=label) for kind in node_schema.used_by
        ):
            return f'"{label}" is not declared on the generic {node_schema.kind}'
        return (
            f'"{label}" is not an attribute or a relationship of {node_schema.kind} on branch {self.schema_branch.name}'
        )

    def _declares(self, kind: str, name: str) -> bool:
        if not self.schema_branch.has(name=kind):
            return False
        schema = self.schema_branch.get(name=kind, duplicate=False)
        return name in schema.attribute_names or name in schema.relationship_names

    def _fields(self, node_schema: MainSchemaTypes) -> list[AttributeSchema | RelationshipSchema]:
        return [*node_schema.attributes, *node_schema.relationships]

    def _element_id(self, node_schema: MainSchemaTypes, field: AttributeSchema | RelationshipSchema) -> str | None:
        # A field inherited unchanged has no vertex of its own, so the generic's vertex identifies it on every kind.
        if field.inherited and (generic_id := self._generic_field_id(node_schema=node_schema, name=field.name)):
            return generic_id
        return field.id

    def _candidate_ids(self, node_schema: MainSchemaTypes, field: AttributeSchema | RelationshipSchema) -> set[str]:
        candidates = {field.id, self._element_id(node_schema=node_schema, field=field)}
        return {candidate for candidate in candidates if candidate}

    def _generic_field_id(self, node_schema: MainSchemaTypes, name: str) -> str | None:
        if not isinstance(node_schema, NodeSchema):
            return None
        for generic_kind in node_schema.inherit_from:
            generic = self.schema_branch.get_generic(name=generic_kind, duplicate=False)
            field = generic.get_attribute_or_none(name=name) or generic.get_relationship_or_none(name=name)
            if field is not None:
                return field.id
        return None


class AllocationScopeValidator:
    """Checks that the elements of an allocation scope can divide the space of a pool over a kind's attribute."""

    def __init__(self, schema_branch: SchemaBranch) -> None:
        self.schema_branch = schema_branch

    def validate(self, kind: str, tracked_attribute: str, scope: AllocationScope) -> None:
        """Refuse a scope whose elements cannot divide the space of a pool over the kind's tracked attribute.

        Raises:
            ValidationError: When the tracked attribute is unique, when an element appears more than once or cannot
                divide the pool, naming it, or when the schema branch does not define the kind or an element.

        """
        if scope.is_empty:
            return

        node_schema = _get_kind_schema(schema_branch=self.schema_branch, kind=kind)
        tracked = node_schema.get_attribute_or_none(name=tracked_attribute)
        if tracked is not None and tracked.unique:
            raise ValidationError(
                {
                    SCOPE_FIELD: f"{node_schema.kind}.{tracked_attribute} is unique;"
                    " a globally unique number cannot be allocated per division"
                }
            )

        seen_ids: set[str] = set()
        for element in scope.elements:
            if element.id in seen_ids:
                raise ValidationError({SCOPE_FIELD: f'"{element.name}" appears more than once'})
            seen_ids.add(element.id)
            field = node_schema.get_attribute_or_none(name=element.name) or node_schema.get_relationship_or_none(
                name=element.name
            )
            if field is None:
                raise ValidationError(
                    {
                        SCOPE_FIELD: f'"{element.name}" is not an attribute or a relationship of {node_schema.kind}'
                        f" on branch {self.schema_branch.name}"
                    }
                )
            self.check_element(node_schema=node_schema, tracked_attribute=tracked_attribute, field=field)

    def check_element(
        self, node_schema: MainSchemaTypes, tracked_attribute: str, field: AttributeSchema | RelationshipSchema
    ) -> None:
        """Refuse a field that cannot divide the space of a pool over the kind's tracked attribute.

        Raises:
            ValidationError: When the field is the tracked attribute, is an attribute that holds more than one scalar
                value, is a relationship of cardinality many, or is optional, naming it.

        """
        if field.name == tracked_attribute:
            raise ValidationError(
                {SCOPE_FIELD: f'"{field.name}" is the attribute the pool allocates; it cannot divide the pool'}
            )
        if isinstance(field, RelationshipSchema):
            if field.cardinality != RelationshipCardinality.ONE:
                raise ValidationError(
                    {
                        SCOPE_FIELD: f'"{field.name}" has cardinality many;'
                        " a scope element must be a relationship of cardinality one"
                    }
                )
        elif field.kind in NON_SCALAR_ATTRIBUTE_KINDS:
            raise ValidationError(
                {
                    SCOPE_FIELD: f'"{field.name}" is of kind {field.kind};'
                    " a scope element must hold a single scalar value"
                }
            )
        if field.optional:
            raise ValidationError(
                {SCOPE_FIELD: f'"{field.name}" is optional; a scope element must be required on {node_schema.kind}'}
            )
