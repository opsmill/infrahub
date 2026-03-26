"""Registry for Python transform-based computed attributes."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core.schema import AttributeSchema  # noqa: TC001

if TYPE_CHECKING:
    from infrahub.core.schema import NodeSchema


@dataclass
class PythonDefinition:
    kind: str
    attribute: AttributeSchema

    @property
    def key_name(self) -> str:
        return f"{self.kind}_{self.attribute.name}"


class PythonTransformRegistry:
    """Tracks which node kinds have Python transform-based computed attributes."""

    def __init__(self, transform_attribute_map: dict[str, list[AttributeSchema]] | None = None) -> None:
        self._map: dict[str, list[AttributeSchema]] = transform_attribute_map or {}

    def duplicate(self) -> PythonTransformRegistry:
        return self.__class__(transform_attribute_map=deepcopy(self._map))

    def add_attribute(self, node: NodeSchema, attribute: AttributeSchema) -> None:
        if node.kind not in self._map:
            self._map[node.kind] = []
        self._map[node.kind].append(attribute)

    def get_kinds(self) -> list[str]:
        """Return kinds that have Python attributes defined."""
        return list(self._map.keys())

    def get_attributes_per_node(self) -> dict[str, list[AttributeSchema]]:
        return self._map

    @property
    def attributes_by_transform(self) -> dict[str, list[PythonDefinition]]:
        computed_attributes: dict[str, list[PythonDefinition]] = {}
        for kind, attributes in self._map.items():
            for attribute in attributes:
                if attribute.computed_attribute and attribute.computed_attribute.transform:
                    if attribute.computed_attribute.transform not in computed_attributes:
                        computed_attributes[attribute.computed_attribute.transform] = []

                    computed_attributes[attribute.computed_attribute.transform].append(
                        PythonDefinition(kind=kind, attribute=attribute)
                    )

        return computed_attributes
