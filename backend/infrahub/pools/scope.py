from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core.constants import RelationshipCardinality
from infrahub.core.constants.schema import SchemaElementPathType
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.exceptions import ValidationError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.schema import AttributeSchema, GenericSchema, MainSchemaTypes
    from infrahub.core.schema.basenode_schema import SchemaAttributePath
    from infrahub.core.schema.schema_branch import SchemaBranch

SCOPE_FIELD = "allocation_scope"
SCOPE_SEPARATOR = "__"
NON_SCALAR_ATTRIBUTE_KINDS = frozenset({"List", "JSON", "Any"})
# Optional relationships are let through and refused here, because path validation exempts ip_namespace on IP kinds.
ALLOWED_SCOPE_PATHS = SchemaElementPathType.ATTR | SchemaElementPathType.REL_ONE_NO_ATTR


@dataclass(frozen=True)
class ScopeEntry:
    """One field of the pool's kind that divides the pool's space."""

    path: str
    """The bare field name, without a property suffix."""

    relationship_identifier: str | None = None
    """The identifier of the relationship vertices, set only when the entry names a relationship."""

    @property
    def is_relationship(self) -> bool:
        return self.relationship_identifier is not None


@dataclass(frozen=True)
class DivisionKey:
    """The division a node belongs to: its value for each scope entry in force."""

    entries: tuple[ScopeEntry, ...]
    """The entries in force on the reading branch, in scope order."""

    values: tuple[str | int | bool | None, ...]
    """One value per entry; None means the node the value is allocated to holds nothing for that entry."""

    def __post_init__(self) -> None:
        if len(self.entries) != len(self.values):
            raise ValueError(
                f"A division needs one value per scope entry, got {len(self.values)} for {len(self.entries)}"
            )


class DivisionResolver:
    """Resolves which scope entries of a pool apply on a branch."""

    @staticmethod
    def entries_in_force(scope: Sequence[str], schema_branch: SchemaBranch, kind: str) -> tuple[ScopeEntry, ...]:
        """Return the scope entries the branch's schema defines on the kind, in scope order.

        An entry is dropped rather than refused because the scope is shared by every branch while the kind's fields
        differ between branches; with no entry left the pool is unscoped on the branch.
        """
        if not schema_branch.has(name=kind):
            return ()
        schema = schema_branch.get(name=kind, duplicate=False)

        entries: list[ScopeEntry] = []
        for path in scope:
            if schema.get_attribute_or_none(name=path) is not None:
                entries.append(ScopeEntry(path=path))
            elif (relationship := schema.get_relationship_or_none(name=path)) is not None:
                entries.append(ScopeEntry(path=path, relationship_identifier=relationship.get_identifier()))
        return tuple(entries)


class ScopeValidator:
    """Checks that every entry of an allocation scope can divide a number pool's space on a schema."""

    def __init__(self, schema_branch: SchemaBranch) -> None:
        self.schema_branch = schema_branch

    @staticmethod
    def parse(value: object) -> list[str]:
        """Return the entries of a scope as sent, reading None as an empty scope.

        Raises:
            ValidationError: When the value is not a list of strings.

        """
        if value is None:
            return []
        if not isinstance(value, list) or not all(isinstance(entry, str) for entry in value):
            raise ValidationError({SCOPE_FIELD: "the scope must be a list of field names"})
        return list(value)

    @staticmethod
    def field_name(entry: str) -> str:
        """Return the field an entry names, without any property suffix."""
        return entry.split(SCOPE_SEPARATOR, maxsplit=1)[0]

    def validate(self, kind: str, attribute_name: str, scope: Sequence[str]) -> tuple[str, ...]:
        """Return the scope's entries as bare field names, in scope order.

        Raises:
            ValidationError: When an entry cannot divide the pool, naming the entry; when the pool's attribute is
                unique, naming the attribute; or when the attribute is inherited from a generic that does not declare
                the entry as a required cardinality-one field, naming the generic.
            SchemaNotFoundError: When the schema does not define the kind.

        """
        if not scope:
            return ()

        schema = self.schema_branch.get(name=kind, duplicate=False)
        attribute = schema.get_attribute_or_none(name=attribute_name)
        if attribute is not None and attribute.unique:
            raise ValidationError(
                {SCOPE_FIELD: f"cannot scope a pool whose attribute {attribute_name!r} of {kind} is unique"}
            )
        generic = self._generic_declaring(schema=schema, attribute=attribute)

        normalised: list[str] = []
        for entry in scope:
            field_name = self._validate_entry(schema=schema, attribute_name=attribute_name, entry=entry)
            if field_name in normalised:
                raise ValidationError({SCOPE_FIELD: f"scope entry {entry!r} is a duplicate"})
            if generic is not None:
                self._validate_entry_on_generic(generic=generic, entry=entry, field_name=field_name)
            normalised.append(field_name)
        return tuple(normalised)

    def _validate_entry(self, schema: MainSchemaTypes, attribute_name: str, entry: str) -> str:
        segments = entry.split(SCOPE_SEPARATOR)
        # Path parsing reads an undeclared `parent` as the hierarchy parent, so the field must be declared on the kind.
        if segments[0] not in schema.attribute_names and segments[0] not in schema.relationship_names:
            raise ValidationError({SCOPE_FIELD: f"scope entry {entry!r} is not defined on {schema.kind}"})

        try:
            path = self.schema_branch.validate_schema_path(
                node_schema=schema, path=entry, allowed_path_types=ALLOWED_SCOPE_PATHS
            )
        except ValueError as exc:
            raise ValidationError({SCOPE_FIELD: f"scope entry {entry!r} is refused, {exc}"}) from exc

        if path.is_type_relationship:
            self._validate_relationship_path(path=path, entry=entry, kind=schema.kind)
            return path.active_relationship_schema.name
        self._validate_attribute_path(
            path=path, entry=entry, attribute_name=attribute_name, kind=schema.kind, segment_count=len(segments)
        )
        return path.active_attribute_schema.name

    @staticmethod
    def _validate_relationship_path(path: SchemaAttributePath, entry: str, kind: str) -> None:
        # Path validation accepts a related node's attribute when no property follows it.
        if path.attribute_schema is not None:
            raise ValidationError(
                {SCOPE_FIELD: f"scope entry {entry!r} cannot use attributes of related node, only the relationship"}
            )
        if path.active_relationship_schema.optional:
            raise ValidationError({SCOPE_FIELD: f"scope entry {entry!r} must be required on {kind}"})

    @staticmethod
    def _validate_attribute_path(
        path: SchemaAttributePath, entry: str, attribute_name: str, kind: str, segment_count: int
    ) -> None:
        attribute = path.active_attribute_schema
        # Path parsing ignores the segments that follow a property.
        if path.attribute_property_name not in {None, "value"} or segment_count > 2:
            raise ValidationError(
                {SCOPE_FIELD: f"scope entry {entry!r} must name the attribute or its value, nothing else"}
            )
        if attribute.name == attribute_name:
            raise ValidationError(
                {SCOPE_FIELD: f"scope entry {entry!r} cannot scope a pool by the attribute it allocates"}
            )
        if attribute.optional:
            raise ValidationError({SCOPE_FIELD: f"scope entry {entry!r} must be required on {kind}"})
        if attribute.kind in NON_SCALAR_ATTRIBUTE_KINDS:
            raise ValidationError(
                {SCOPE_FIELD: f"scope entry {entry!r} must be a single scalar value, not of kind {attribute.kind}"}
            )

    def _generic_declaring(self, schema: MainSchemaTypes, attribute: AttributeSchema | None) -> GenericSchema | None:
        if attribute is None or not attribute.inherited or not isinstance(schema, NodeSchema):
            return None
        for generic_kind in schema.inherit_from:
            generic = self.schema_branch.get_generic(name=generic_kind, duplicate=False)
            if generic.get_attribute_or_none(name=attribute.name) is not None:
                return generic
        return None

    @staticmethod
    def _validate_entry_on_generic(generic: GenericSchema, entry: str, field_name: str) -> None:
        attribute = generic.get_attribute_or_none(name=field_name)
        relationship = generic.get_relationship_or_none(name=field_name)
        if attribute is not None:
            is_required_single_field = not attribute.optional
        elif relationship is not None:
            is_required_single_field = (
                not relationship.optional and relationship.cardinality == RelationshipCardinality.ONE
            )
        else:
            is_required_single_field = False

        # The division of a node is read from the generic's fields, so every implementing kind must hold the entry.
        if not is_required_single_field:
            raise ValidationError(
                {
                    SCOPE_FIELD: f"scope entry {entry!r} must be a required cardinality-one field of {generic.kind},"
                    " the generic the pool's attribute is inherited from"
                }
            )
