from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from infrahub.core.schema import AttributeSchema  # noqa: TC001

if TYPE_CHECKING:
    from infrahub.core.schema import GenericSchema, NodeSchema, SchemaAttributePath


@dataclass
class PythonDefinition:
    kind: str
    attribute: AttributeSchema

    @property
    def key_name(self) -> str:
        return f"{self.kind}_{self.attribute.name}"


class ComputedAttributeTarget(BaseModel):
    kind: str
    attribute: AttributeSchema
    filter_keys: list[str] = Field(default_factory=list)

    @property
    def key_name(self) -> str:
        return f"{self.kind}_{self.attribute.name}"

    @property
    def node_filters(self) -> list[str]:
        if self.filter_keys:
            return self.filter_keys

        return ["ids"]

    def __hash__(self) -> int:
        return hash((self.kind, self.attribute, tuple(self.filter_keys)))


class ComputedAttributeTriggerNode(BaseModel):
    kind: str
    attributes: list[str] = Field(default_factory=list)
    relationships: list[str] = Field(default_factory=list)
    targets_self: bool = Field(default=False)

    @property
    def fields(self) -> list[str]:
        return self.attributes + self.relationships


class RegisteredNodeComputedAttribute(BaseModel):
    local_fields: dict[str, list[ComputedAttributeTarget]] = Field(
        default_factory=dict,
        description="These are fields local to the modified node, which can include the names of attributes and relationships",
    )
    relationships: dict[str, list[ComputedAttributeTarget]] = Field(
        default_factory=dict,
        description="These relationships refer to the name of the relationship as seen from the source node.",
    )

    def get_targets(self, updates: list[str] | None = None) -> list[ComputedAttributeTarget]:
        targets: dict[str, ComputedAttributeTarget] = {}
        for attribute, entries in self.local_fields.items():
            if updates and attribute not in updates:
                continue

            for entry in entries:
                if entry.key_name not in targets:
                    targets[entry.key_name] = entry

        for relationship_name, entries in self.relationships.items():
            for entry in entries:
                filter_key = f"{relationship_name}__ids"
                if entry.key_name in targets and filter_key not in targets[entry.key_name].filter_keys:
                    targets[entry.key_name].filter_keys.append(filter_key)

        return list(targets.values())


class ComputedAttributes:
    def __init__(
        self,
        transform_attribute_map: dict[str, list[AttributeSchema]] | None = None,
        jinja2_attribute_map: dict[str, RegisteredNodeComputedAttribute] | None = None,
    ) -> None:
        self._computed_python_transform_attribute_map: dict[str, list[AttributeSchema]] = transform_attribute_map or {}
        self._computed_jinja2_attribute_map: dict[str, RegisteredNodeComputedAttribute] = jinja2_attribute_map or {}
        self._defined_from_generic: dict[str, str] = {}

    def duplicate(self) -> ComputedAttributes:
        return self.__class__(
            transform_attribute_map=deepcopy(self._computed_python_transform_attribute_map),
            jinja2_attribute_map=deepcopy(self._computed_jinja2_attribute_map),
        )

    def add_python_attribute(self, node: NodeSchema, attribute: AttributeSchema) -> None:
        if node.kind not in self._computed_python_transform_attribute_map:
            self._computed_python_transform_attribute_map[node.kind] = []
        self._computed_python_transform_attribute_map[node.kind].append(attribute)

    def get_kinds_python_attributes(self) -> list[str]:
        """Return kinds that have Python attributes defined"""
        return list(self._computed_python_transform_attribute_map.keys())

    def get_python_attributes_per_node(self) -> dict[str, list[AttributeSchema]]:
        return self._computed_python_transform_attribute_map

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

    def register_computed_jinja2(
        self, node: NodeSchema, attribute: AttributeSchema, schema_path: SchemaAttributePath
    ) -> None:
        key = node.kind
        if schema_path.is_type_relationship:
            key = schema_path.active_relationship_schema.peer

        if key not in self._computed_jinja2_attribute_map:
            self._computed_jinja2_attribute_map[key] = RegisteredNodeComputedAttribute()

        source_attribute = ComputedAttributeTarget(kind=node.kind, attribute=attribute)
        trigger_node = self._computed_jinja2_attribute_map[key]
        if schema_path.is_type_attribute:
            if schema_path.active_attribute_schema.name not in trigger_node.local_fields:
                trigger_node.local_fields[schema_path.active_attribute_schema.name] = []

            trigger_node.local_fields[schema_path.active_attribute_schema.name].append(deepcopy(source_attribute))
        elif schema_path.is_type_relationship:
            if schema_path.active_attribute_schema.name not in trigger_node.local_fields:
                trigger_node.local_fields[schema_path.active_attribute_schema.name] = []

            trigger_node.local_fields[schema_path.active_attribute_schema.name].append(deepcopy(source_attribute))

            if schema_path.active_relationship_schema.name not in trigger_node.relationships:
                trigger_node.relationships[schema_path.active_relationship_schema.name] = []

            trigger_node.relationships[schema_path.active_relationship_schema.name].append(deepcopy(source_attribute))

            if source_attribute.kind not in self._computed_jinja2_attribute_map:
                self._computed_jinja2_attribute_map[source_attribute.kind] = RegisteredNodeComputedAttribute()

            if (
                schema_path.active_relationship_schema.name
                not in self._computed_jinja2_attribute_map[source_attribute.kind].local_fields
            ):
                self._computed_jinja2_attribute_map[source_attribute.kind].local_fields[
                    schema_path.active_relationship_schema.name
                ] = []
            self._computed_jinja2_attribute_map[source_attribute.kind].local_fields[
                schema_path.active_relationship_schema.name
            ].append(deepcopy(source_attribute))

    def validate_generic_inheritance(
        self, node: NodeSchema, attribute: AttributeSchema, generic: GenericSchema
    ) -> None:
        attribute_key = f"{node.kind}__{attribute.name}"
        if duplicate := self._defined_from_generic.get(attribute_key):
            raise ValueError(
                f"{node.kind}: {attribute.name!r} is declared as a computed attribute from multiple generics {sorted([duplicate, generic.kind])}"
            )
        self._defined_from_generic[attribute_key] = generic.kind

    def get_impacted_jinja2_targets(self, kind: str, updates: list[str] | None = None) -> list[ComputedAttributeTarget]:
        if mapping := self._computed_jinja2_attribute_map.get(kind):
            return mapping.get_targets(updates=updates)

        return []

    def get_jinja2_target_map(self) -> dict[ComputedAttributeTarget, list[str]]:
        mapping: dict[ComputedAttributeTarget, set[str]] = {}

        for node, registered_computed_attribute in self._computed_jinja2_attribute_map.items():
            for local_fields in registered_computed_attribute.local_fields.values():
                for local_field in local_fields:
                    if local_field not in mapping:
                        mapping[local_field] = set()
                    mapping[local_field].add(node)

        return {key: list(value) for key, value in mapping.items()}

    def get_jinja2_trigger_nodes(self) -> dict[ComputedAttributeTarget, list[ComputedAttributeTriggerNode]]:
        working_map: dict[ComputedAttributeTarget, dict[str, ComputedAttributeTriggerNode]] = {}
        for node_kind, registered_computed_attribute in self._computed_jinja2_attribute_map.items():
            for local_field, computed_attribute_targets in registered_computed_attribute.local_fields.items():
                for computed_attribute_target in computed_attribute_targets:
                    if computed_attribute_target not in working_map:
                        working_map[computed_attribute_target] = {}
                    if node_kind not in working_map[computed_attribute_target]:
                        working_map[computed_attribute_target][node_kind] = ComputedAttributeTriggerNode(kind=node_kind)
                    working_map[computed_attribute_target][node_kind].attributes.append(local_field)
                    if computed_attribute_target.kind == node_kind:
                        working_map[computed_attribute_target][node_kind].targets_self = True
            for relationship, computed_attribute_targets in registered_computed_attribute.relationships.items():
                for computed_attribute_target in computed_attribute_targets:
                    if computed_attribute_target not in working_map:
                        working_map[computed_attribute_target] = {}
                    if node_kind not in working_map[computed_attribute_target]:
                        working_map[computed_attribute_target][node_kind] = ComputedAttributeTriggerNode(kind=node_kind)
                    working_map[computed_attribute_target][node_kind].relationships.append(relationship)
                    if computed_attribute_target.kind == node_kind:
                        working_map[computed_attribute_target][node_kind].targets_self = True

        return {
            computed_attribute_target: list(nodes.values()) for computed_attribute_target, nodes in working_map.items()
        }
