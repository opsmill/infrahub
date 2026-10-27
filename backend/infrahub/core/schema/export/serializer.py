from __future__ import annotations

from operator import itemgetter
from typing import TYPE_CHECKING, Any

from infrahub_sdk.schema.generated.write import GenericSchemaWrite, NodeSchemaWrite

from infrahub.core.constants import (
    OBJECT_TEMPLATE_RELATIONSHIP_NAME,
    PROFILES_RELATIONSHIP_NAME,
    RESTRICTED_NAMESPACES,
    RelationshipKind,
)
from infrahub.core.schema import GenericSchema, NodeSchema

from .document import ElementData, ExportDocument

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.attribute_schema import AttributeSchema
    from infrahub.core.schema.relationship_schema import RelationshipSchema
    from infrahub.core.schema.schema_branch import SchemaBranch

GENERATED_RELATIONSHIPS: frozenset[tuple[str, RelationshipKind, str | None]] = frozenset(
    {
        ("member_of_groups", RelationshipKind.GROUP, "group_member"),
        ("subscriber_of_groups", RelationshipKind.GROUP, "group_subscriber"),
        ("parent", RelationshipKind.HIERARCHY, "parent__child"),
        ("children", RelationshipKind.HIERARCHY, "parent__child"),
    }
)
"""Relationships that processing adds to a node, identified by name, kind and identifier together."""

VIRTUAL_RELATIONSHIPS: frozenset[tuple[str, RelationshipKind]] = frozenset(
    {
        (PROFILES_RELATIONSHIP_NAME, RelationshipKind.PROFILE),
        (OBJECT_TEMPLATE_RELATIONSHIP_NAME, RelationshipKind.TEMPLATE),
    }
)

DEPRECATED_COPIED_PROPERTIES: frozenset[str] = frozenset({"default_filter", "display_labels"})
"""Deprecated node properties that warn on every load; one equal to the value its generic gives it is left out."""

_ELEMENT_EXCLUDE: dict[str, Any] = {"id": True, "state": True}
# The top-level validation settings are deprecated aliases that processing keeps in sync with `parameters`.
_ATTRIBUTE_EXCLUDE: dict[str, Any] = {
    **_ELEMENT_EXCLUDE,
    "regex": True,
    "min_length": True,
    "max_length": True,
    # Identifies the pool of one instance, so it means nothing on another one.
    "parameters": {"number_pool_id": True},
}
_EXCLUDE: dict[str, Any] = {
    **_ELEMENT_EXCLUDE,
    "attributes": {"__all__": _ATTRIBUTE_EXCLUDE},
    "relationships": {"__all__": _ELEMENT_EXCLUDE},
}


class SchemaExportSerializer:
    """Write the user-defined nodes and generics of a schema branch with every value they hold."""

    def __init__(self, shipped_kinds: frozenset[str]) -> None:
        self.shipped_kinds = shipped_kinds
        """Kinds that every instance has before a schema is loaded, such as the core models."""

    def serialize(self, schema_branch: SchemaBranch, namespaces: list[str]) -> ExportDocument:
        """Return the user-defined nodes and generics of the given namespaces, sorted."""
        document = ExportDocument()
        for schema in schema_branch.get_schemas_for_namespaces(namespaces=namespaces):
            if not self._is_user_defined(schema=schema) or schema.namespace not in namespaces:
                continue
            if isinstance(schema, NodeSchema):
                node = self._serialize_element(schema=schema)
                for name in self._copied_deprecated_properties(schema_branch=schema_branch, schema=schema):
                    node.pop(name, None)
                document.nodes.append(node)
            elif isinstance(schema, GenericSchema):
                document.generics.append(self._serialize_element(schema=schema))

        document.generics.sort(key=itemgetter("namespace", "name"))
        document.nodes.sort(key=itemgetter("namespace", "name"))
        return document

    def user_namespaces(self, schema_branch: SchemaBranch) -> list[str]:
        return sorted(
            {
                schema.namespace
                for schema in schema_branch.get_all(duplicate=False).values()
                if self._is_user_defined(schema=schema)
            }
        )

    def _copied_deprecated_properties(self, schema_branch: SchemaBranch, schema: NodeSchema) -> list[str]:
        copied: list[str] = []
        node_values = schema.model_dump(include=set(DEPRECATED_COPIED_PROPERTIES))
        for name, value in node_values.items():
            for generic_kind in schema.inherit_from:
                generic_value = schema_branch.get(name=generic_kind, duplicate=False).model_dump(include={name})[name]
                if generic_value:
                    if generic_value == value:
                        copied.append(name)
                    break
        return copied

    def _is_user_defined(self, schema: MainSchemaTypes) -> bool:
        return (
            isinstance(schema, NodeSchema | GenericSchema)
            and schema.namespace not in RESTRICTED_NAMESPACES
            and schema.kind not in self.shipped_kinds
        )

    def _serialize_element(self, schema: NodeSchema | GenericSchema) -> ElementData:
        data = schema.model_dump(mode="json")
        if data["include_in_menu"] is None:
            # An instance stores an unset value as `true`, so a schema read from the database never has `None`.
            data["include_in_menu"] = True
        data["attributes"] = [
            attribute.model_dump(mode="json")
            for attribute in sorted(schema.attributes, key=_field_sort_key)
            if not attribute.inherited
        ]
        data["relationships"] = [
            relationship.model_dump(mode="json")
            for relationship in sorted(schema.relationships, key=_field_sort_key)
            if not relationship.inherited and not _is_generated(relationship=relationship)
        ]
        write_model = NodeSchemaWrite if isinstance(schema, NodeSchema) else GenericSchemaWrite
        element = write_model.model_validate(data).model_dump(mode="json", exclude_none=True, exclude=_EXCLUDE)
        for attribute in element["attributes"]:
            if attribute.get("parameters") == {}:
                del attribute["parameters"]
        return element


def _is_generated(relationship: RelationshipSchema) -> bool:
    if (relationship.name, relationship.kind) in VIRTUAL_RELATIONSHIPS:
        return True
    return (relationship.name, relationship.kind, relationship.identifier) in GENERATED_RELATIONSHIPS


def _field_sort_key(item: AttributeSchema | RelationshipSchema) -> tuple[int, str]:
    return (item.order_weight or 0, item.name)
