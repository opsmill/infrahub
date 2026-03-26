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
    """Identifies a computed attribute that needs recomputation.

    Points to a specific (kind, attribute) pair — e.g. InfraDevice.computed_name — that should
    be re-evaluated when a dependency changes. The ``filter_keys`` field carries relationship-based
    query filters (e.g. ``site__ids``) used to locate affected nodes when the trigger comes from
    a peer node rather than the owner itself.
    """

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
    """Dependency record for a single trigger node kind in the Jinja2 computed attribute registry.
    Each instance describes what should happen when a node of a particular kind is mutated.

    Example: InfraDevice has ``computed_name = "{{ name__value }}-{{ site__name__value }}"``.
    This produces two entries in the map:

    - **"InfraDevice"** (the owner): ``local_fields = {"name": [target], "site": [target]}``
      A change to the device's own ``name`` or ``site`` relationship triggers recomputation.

    - **"InfraSite"** (the peer): ``local_fields = {"name": [target]}``,
      ``relationships = {"site": [target]}``
      A change to the site's ``name`` triggers recomputation of devices linked via ``site``.
      The ``relationships`` dict provides ``filter_keys`` (e.g. ``site__ids``) so the system
      can locate which devices are affected.
    """

    local_fields: dict[str, list[ComputedAttributeTarget]] = Field(
        default_factory=dict,
        description="These are fields local to the modified node, which can include the names of attributes and relationships",
    )
    relationships: dict[str, list[ComputedAttributeTarget]] = Field(
        default_factory=dict,
        description="These relationships refer to the name of the relationship as seen from the source node.",
    )

    def get_targets(self, updates: list[str] | None = None) -> list[ComputedAttributeTarget]:
        """Resolve which ComputedAttributeTargets are affected by changes to this node.

        Args:
            updates: Field names (attributes or relationships) that changed. When None, all
                     registered local_fields are included.

        Returns:
            Deduplicated list of ComputedAttributeTarget, each enriched with any applicable
            relationship-based filter_keys.
        """
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
        """Register a Jinja2 computed attribute and its dependency graph.

        Args:
            node: The schema owning the computed attribute (e.g. InfraDevice).
            attribute: The computed attribute definition (e.g. ``computed_name``).
            schema_path: Parsed Jinja2 template token identifying the dependency — either a
                         local attribute or a relationship + peer attribute.

        Returns:
            None
        """
        # Determine the trigger key: for local attributes it's the node itself,
        # for relationship attributes it's the peer kind.
        key = node.kind if not schema_path.is_type_relationship else schema_path.active_relationship_schema.peer

        trigger_node = self._computed_jinja2_attribute_map.setdefault(key, RegisteredNodeComputedAttribute())
        source_attribute = ComputedAttributeTarget(kind=node.kind, attribute=attribute)
        attr_name = schema_path.active_attribute_schema.name

        # Both cases: register the attribute as a local_field on the trigger node,
        # so a change to this field triggers recomputation.
        trigger_node.local_fields.setdefault(attr_name, []).append(deepcopy(source_attribute))

        if schema_path.is_type_relationship:
            rel_name = schema_path.active_relationship_schema.name

            # Record the relationship on the *peer* entry
            trigger_node.relationships.setdefault(rel_name, []).append(deepcopy(source_attribute))

            # Register on the *owner* entry so that a relationship re-assignment also triggers recomputation.
            owner_entry = self._computed_jinja2_attribute_map.setdefault(
                source_attribute.kind, RegisteredNodeComputedAttribute()
            )
            owner_entry.local_fields.setdefault(rel_name, []).append(deepcopy(source_attribute))

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
        """Return computed Jinja2 attribute targets that need re-evaluation when a node of the given kind is modified.

        Args:
            kind: The schema kind of the node that was modified (e.g. "InfraInterface").
            updates: Optional list of field names (attributes or relationships) that changed on the node.
                     When provided, only targets whose Jinja2 templates reference these fields are returned.
                     When None, all registered targets for this kind are returned.

        Returns:
            List of ComputedAttributeTarget entries, each identifying a (kind, attribute) pair whose
            computed value depends on the modified node and may need recomputation. The target kind
            can differ from the input kind when the dependency crosses a relationship.
        """
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
        """Build a reverse index from computed attribute targets to the node mutations that trigger them.

        Example: if InfraDevice.computed_name depends on its own ``name`` and on InfraSite's ``name``
        (via a ``site`` relationship), the result includes::

            ComputedAttributeTarget(kind="InfraDevice", attribute=computed_name) -> [
                ComputedAttributeTriggerNode(
                    kind="InfraDevice",
                    attributes=["name", "site"],  # "site" is here because reassigning the relationship is a local change
                    targets_self=True,
                ),
                ComputedAttributeTriggerNode(
                    kind="InfraSite",
                    attributes=["name"],       # the peer attribute referenced in the template
                    relationships=["site"],    # the relationship used to locate affected InfraDevices
                    targets_self=False,
                ),
            ]
        """
        # Intermediate map: target -> {trigger_kind -> trigger_node}
        working_map: dict[ComputedAttributeTarget, dict[str, ComputedAttributeTriggerNode]] = {}

        def _ensure_trigger(target: ComputedAttributeTarget, kind: str) -> ComputedAttributeTriggerNode:
            """Get or create the trigger node for a (target, kind) pair."""
            target_map = working_map.setdefault(target, {})
            trigger = target_map.setdefault(kind, ComputedAttributeTriggerNode(kind=kind))
            if target.kind == kind:
                trigger.targets_self = True
            return trigger

        for node_kind, registered in self._computed_jinja2_attribute_map.items():
            # Local fields: attributes and relationship names on the trigger node itself
            for local_field, targets in registered.local_fields.items():
                for target in targets:
                    _ensure_trigger(target, node_kind).attributes.append(local_field)
            # Relationships: the trigger node is a peer reached via this relationship
            for relationship, targets in registered.relationships.items():
                for target in targets:
                    _ensure_trigger(target, node_kind).relationships.append(relationship)

        return {target: list(nodes.values()) for target, nodes in working_map.items()}
