"""Facade composing Python transform and Jinja2 computed attribute registries.

The ``ComputedAttributes`` class delegates to two focused sub-registries:

- :class:`~.schema_branch_computed_python.PythonTransformRegistry` — Python transform-based computed attributes
- :class:`~.schema_branch_computed_jinja2.Jinja2ComputedRegistry` — Jinja2 template-based computed attributes
  with dependency graph tracking
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.schema import AttributeSchema  # noqa: TC001
from infrahub.core.schema.schema_branch_computed_jinja2 import (
    ComputedAttributeTarget,
    ComputedAttributeTriggerNode,
    Jinja2ComputedRegistry,
)
from infrahub.core.schema.schema_branch_computed_python import PythonDefinition, PythonTransformRegistry

if TYPE_CHECKING:
    from infrahub.core.schema import GenericSchema, NodeSchema, SchemaAttributePath

# Re-export for backwards compatibility
__all__ = [
    "ComputedAttributeTarget",
    "ComputedAttributeTriggerNode",
    "PythonDefinition",
]


class ComputedAttributes:
    def __init__(
        self,
        transform_attribute_map: dict[str, list[AttributeSchema]] | None = None,
        jinja2_attribute_map: dict | None = None,
    ) -> None:
        self._python = PythonTransformRegistry(transform_attribute_map=transform_attribute_map)
        self._jinja2 = Jinja2ComputedRegistry(jinja2_attribute_map=jinja2_attribute_map)
        self._defined_from_generic: dict[str, str] = {}

    def duplicate(self) -> ComputedAttributes:
        return self.__class__(
            transform_attribute_map=self._python.duplicate()._map,
            jinja2_attribute_map=self._jinja2.duplicate()._map,
        )

    # --- Python transform delegates ---

    def add_python_attribute(self, node: NodeSchema, attribute: AttributeSchema) -> None:
        self._python.add_attribute(node, attribute)

    def get_kinds_python_attributes(self) -> list[str]:
        """Return kinds that have Python attributes defined"""
        return self._python.get_kinds()

    def get_python_attributes_per_node(self) -> dict[str, list[AttributeSchema]]:
        return self._python.get_attributes_per_node()

    @property
    def python_attributes_by_transform(self) -> dict[str, list[PythonDefinition]]:
        return self._python.attributes_by_transform

    # --- Jinja2 delegates ---

    def register_computed_jinja2(
        self, node: NodeSchema, attribute: AttributeSchema, schema_path: SchemaAttributePath
    ) -> None:
        self._jinja2.register(node, attribute, schema_path)

    def validate_generic_inheritance(
        self, node: NodeSchema, attribute: AttributeSchema, generic: GenericSchema
    ) -> None:
        """Ensure a computed attribute is not inherited from multiple generics.

        This validation applies to all computed attribute kinds.
        """
        attribute_key = f"{node.kind}__{attribute.name}"
        if duplicate := self._defined_from_generic.get(attribute_key):
            raise ValueError(
                f"{node.kind}: {attribute.name!r} is declared as a computed attribute from multiple generics {sorted([duplicate, generic.kind])}"
            )
        self._defined_from_generic[attribute_key] = generic.kind

    def get_impacted_jinja2_targets(self, kind: str, updates: list[str] | None = None) -> list[ComputedAttributeTarget]:
        return self._jinja2.get_impacted_targets(kind, updates)

    def get_jinja2_target_map(self) -> dict[ComputedAttributeTarget, list[str]]:
        return self._jinja2.get_target_map()

    def get_jinja2_trigger_nodes(self) -> dict[ComputedAttributeTarget, list[ComputedAttributeTriggerNode]]:
        return self._jinja2.get_trigger_nodes()
