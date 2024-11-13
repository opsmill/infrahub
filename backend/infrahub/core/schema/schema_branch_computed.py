from dataclasses import dataclass

from infrahub.core.schema import (
    AttributeSchema,
    NodeSchema,
)


@dataclass
class PythonDefinition:
    kind: str
    attribute: AttributeSchema

    @property
    def key_name(self) -> str:
        return f"{self.kind}_{self.attribute.name}"


class ComputedAttributes:
    def __init__(self) -> None:
        self._computed_python_transform_attribute_map: dict[str, list[AttributeSchema]] = {}

    def add_python_attribute(self, node: NodeSchema, attribute: AttributeSchema) -> None:
        if node.kind not in self._computed_python_transform_attribute_map:
            self._computed_python_transform_attribute_map[node.kind] = []
        self._computed_python_transform_attribute_map[node.kind].append(attribute)

    def get_kinds_python_attributes(self) -> list[str]:
        """Return kinds that have Python attributes defined"""
        return list(self._computed_python_transform_attribute_map.keys())

    @property
    def python_attributes_by_transform(self) -> dict[str, list[PythonDefinition]]:
        computed_attributes: dict[str, list[PythonDefinition]] = {}
        for kind, attributes in self._computed_python_transform_attribute_map.items():
            for attribute in attributes:
                if attribute.computed_attribute and attribute.computed_attribute.transform:
                    if attribute.computed_attribute.transform not in computed_attributes:
                        computed_attributes[attribute.computed_attribute.transform] = []

                    computed_attributes[attribute.computed_attribute.transform].append(
                        PythonDefinition(kind=kind, attribute=attribute)
                    )

        return computed_attributes
