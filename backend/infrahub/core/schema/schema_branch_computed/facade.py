"""Facade composing Python transform and Jinja2 computed attribute registries.

The ``ComputedAttributes`` class delegates to two focused sub-registries:

- :class:`~.python_transform.PythonTransformRegistry` — Python transform-based computed attributes
- :class:`~.jinja2.Jinja2ComputedRegistry` — Jinja2 template-based computed attributes
  with dependency graph tracking
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.schema import AttributeSchema  # noqa: TC001
from infrahub.core.schema.schema_branch_computed.jinja2 import (
    ComputedAttributeTarget,
    ComputedAttributeTriggerNode,
    Jinja2ComputedRegistry,
    RegisteredNodeComputedAttribute,
    ResolvedComputedTarget,
)
from infrahub.core.schema.schema_branch_computed.python_transform import PythonDefinition, PythonTransformRegistry

if TYPE_CHECKING:
    from infrahub.core.schema import NodeSchema, SchemaAttributePath


class ComputedAttributes:
    def __init__(
        self,
        transform_attribute_map: dict[str, list[AttributeSchema]] | None = None,
        jinja2_attribute_map: dict | None = None,
    ) -> None:
        self._python = PythonTransformRegistry(transform_attribute_map=transform_attribute_map)
        self._jinja2 = Jinja2ComputedRegistry(jinja2_attribute_map=jinja2_attribute_map)

    def duplicate(self) -> ComputedAttributes:
        return self.__class__(
            transform_attribute_map=self._python.duplicate()._map,
            jinja2_attribute_map=self._jinja2.duplicate()._map,
        )

    # --- Python transform delegates ---

    def add_python_attribute(self, node: NodeSchema, attribute: AttributeSchema) -> None:
        self._python.add_attribute(node, attribute)

    def get_kinds_python_attributes(self) -> list[str]:
        """Return kinds that have Python attributes defined."""
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

    def get_impacted_jinja2_targets(self, kind: str, updates: list[str] | None = None) -> list[ResolvedComputedTarget]:
        return self._jinja2.get_impacted_targets(kind, updates)

    def get_local_jinja2_targets(self, kind: str, updates: list[str] | None = None) -> list[ComputedAttributeTarget]:
        return self._jinja2.get_local_targets(kind, updates)

    def get_registered_jinja2_node(self, kind: str) -> RegisteredNodeComputedAttribute | None:
        """Return the registered Jinja2 node entry for a given kind, or None."""
        return self._jinja2.get_registered_node(kind)

    def get_jinja2_target_map(self) -> dict[ComputedAttributeTarget, list[str]]:
        return self._jinja2.get_target_map()

    def get_jinja2_trigger_nodes(self) -> dict[ComputedAttributeTarget, list[ComputedAttributeTriggerNode]]:
        return self._jinja2.get_trigger_nodes()
