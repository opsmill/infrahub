from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from infrahub.core.schema.basenode_schema import SCHEMA_PATH_PROPERTIES

if TYPE_CHECKING:
    from infrahub.core.schema import AttributeSchema, MainSchemaTypes, RelationshipSchema


@dataclass
class FieldNameChanges:
    """The attribute and relationship names that the operations removed or renamed on one kind, by name before the change.

    The path properties of the kind, such as its human-friendly ID, start with these names. A path property that no
    operation set still uses the names before the operations, and a path property that an operation set already
    uses the names after them, so only the first kind is rewritten.
    """

    removed: set[str] = field(default_factory=set)
    renamed: dict[str, str] = field(default_factory=dict)
    rename_positions: dict[str, int] = field(default_factory=dict)
    """The position of the operation that renamed each element, by the ID of the element."""

    original_names: dict[str, str] = field(default_factory=dict)
    """The name of each renamed element before the operations, by the ID of the element."""

    set_path_properties: set[str] = field(default_factory=set)

    def rename(self, element: AttributeSchema | RelationshipSchema, old_name: str, position: int) -> None:
        if element.id is None:
            original_name = self._original_name(name=old_name)
        else:
            original_name = self.original_names.setdefault(element.id, old_name)
            self.rename_positions[element.id] = position
        self.renamed[original_name] = element.name

    def was_renamed(self, element: AttributeSchema | RelationshipSchema) -> bool:
        return element.id is not None and element.id in self.rename_positions

    def remove(self, name: str) -> None:
        original_name = self._original_name(name=name)
        self.renamed.pop(original_name, None)
        self.removed.add(original_name)

    def set_property(self, property_name: str) -> None:
        if property_name in SCHEMA_PATH_PROPERTIES:
            self.set_path_properties.add(property_name)

    def rewrite_paths(self, node: MainSchemaTypes) -> None:
        """Rewrite the path properties of the kind to the names after the operations, except the ones an operation set."""
        node.apply_schema_path_updates(
            deleted_field_names=self.removed,
            renamed_field_name_map=self.renamed,
            kept_properties=self.set_path_properties,
        )

    def _original_name(self, name: str) -> str:
        for original_name, new_name in self.renamed.items():
            if new_name == name:
                return original_name
        return name
