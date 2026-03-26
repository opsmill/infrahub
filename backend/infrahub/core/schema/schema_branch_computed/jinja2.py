"""Registry for Jinja2-based computed attributes and their dependency graphs."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from infrahub.core.schema import AttributeSchema  # noqa: TC001

if TYPE_CHECKING:
    from infrahub.core.schema import NodeSchema, SchemaAttributePath


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
    relationship_peer_attributes: dict[str, set[str]] = Field(
        default_factory=dict,
        description="Maps relationship names to the set of peer attribute names needed for Jinja2 template rendering.",
    )

    @property
    def relationship_fields(self) -> dict[str, set[str]]:
        """Return mapping of relationship names to peer attribute names needed for computed attribute templates."""
        return {rel: set(attrs) for rel, attrs in self.relationship_peer_attributes.items()}

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

    def get_local_targets_in_dependency_order(self, kind: str, updates: list[str]) -> list[ComputedAttributeTarget]:
        """Walk local_fields wave by wave, returning self-targeting targets in dependency order.

        Starting from the given field names, each wave collects targets triggered by
        the previous wave's computed attribute names. Within each wave, targets that
        are dependencies of other wave members are emitted first by deferring
        dependents to the next iteration.
        """
        processed: set[str] = set()
        result: list[ComputedAttributeTarget] = []
        pending_fields = set(updates)

        while pending_fields:
            wave = self._collect_wave(pending_fields, kind, processed)
            if not wave:
                break

            ready, deferred = self._partition_wave(wave, kind)
            result.extend(ready)
            pending_fields = {t.attribute.name for t in ready}
            processed.difference_update(target.key_name for target in deferred)

        return result

    def _collect_wave(
        self, pending_fields: set[str], kind: str, processed: set[str]
    ) -> dict[str, ComputedAttributeTarget]:
        """Gather unprocessed local targets triggered by the given fields.

        Marks collected targets as processed (side effect on ``processed``).
        """
        wave: dict[str, ComputedAttributeTarget] = {}
        for field_name in pending_fields:
            for entry in self.local_fields.get(field_name, []):
                if entry.kind == kind and entry.key_name not in processed:
                    processed.add(entry.key_name)
                    wave[entry.key_name] = entry
        return wave

    def _partition_wave(
        self, wave: dict[str, ComputedAttributeTarget], kind: str
    ) -> tuple[list[ComputedAttributeTarget], list[ComputedAttributeTarget]]:
        """Split a wave into (ready, deferred) based on intra-wave dependencies.

        Ready targets have no unresolved prerequisites within the wave.
        Deferred targets depend on a ready target and must wait for the next iteration.
        When no intra-wave dependencies exist, all targets are ready.
        """
        wave_attr_names = {t.attribute.name for t in wave.values()}

        # Attributes whose output triggers another wave member (prerequisites).
        prerequisite_attrs = {
            attr_name
            for attr_name in wave_attr_names
            for entry in self.local_fields.get(attr_name, [])
            if entry.kind == kind and entry.attribute.name in wave_attr_names
        }

        if not prerequisite_attrs:
            return list(wave.values()), []

        # Attributes that depend on a prerequisite — only these need deferring.
        dependent_attrs = {
            entry.attribute.name
            for attr_name in prerequisite_attrs
            for entry in self.local_fields.get(attr_name, [])
            if entry.kind == kind and entry.attribute.name in wave_attr_names
        }

        ready = [t for t in wave.values() if t.attribute.name not in dependent_attrs]
        deferred = [t for t in wave.values() if t.attribute.name in dependent_attrs]
        return ready, deferred


class Jinja2ComputedRegistry:
    """Tracks Jinja2 computed attribute dependency graphs.

    Maintains a map keyed by the kind of node whose mutation should trigger recomputation.
    Each entry describes which local fields and relationships act as triggers, and which
    computed attributes are affected.
    """

    def __init__(
        self,
        jinja2_attribute_map: dict[str, RegisteredNodeComputedAttribute] | None = None,
    ) -> None:
        self._map: dict[str, RegisteredNodeComputedAttribute] = jinja2_attribute_map or {}

    def duplicate(self) -> Jinja2ComputedRegistry:
        return self.__class__(jinja2_attribute_map=deepcopy(self._map))

    def register(self, node: NodeSchema, attribute: AttributeSchema, schema_path: SchemaAttributePath) -> None:
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

        trigger_node = self._map.setdefault(key, RegisteredNodeComputedAttribute())
        source_attribute = ComputedAttributeTarget(kind=node.kind, attribute=attribute)
        attr_name = schema_path.active_attribute_schema.name

        # Both cases: register the attribute as a local_field on the trigger node,
        # so a change to this field triggers recomputation.
        trigger_node.local_fields.setdefault(attr_name, []).append(deepcopy(source_attribute))

        if schema_path.is_type_relationship:
            rel_name = schema_path.active_relationship_schema.name

            # Record the relationship on the *peer* entry
            trigger_node.relationships.setdefault(rel_name, []).append(deepcopy(source_attribute))

            # Register on the *owner* entry so that a relationship re-assignment
            owner_entry = self._map.setdefault(source_attribute.kind, RegisteredNodeComputedAttribute())
            owner_entry.local_fields.setdefault(rel_name, []).append(deepcopy(source_attribute))

            # Record which peer attributes are needed per relationship
            peer_attr = schema_path.active_attribute_schema.name
            owner_entry.relationship_peer_attributes.setdefault(rel_name, set()).add(peer_attr)

    def get_impacted_targets(self, kind: str, updates: list[str] | None = None) -> list[ComputedAttributeTarget]:
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
        if mapping := self._map.get(kind):
            return mapping.get_targets(updates=updates)

        return []

    def get_local_targets(self, kind: str, updates: list[str] | None = None) -> list[ComputedAttributeTarget]:
        """Return only self-targeting Jinja2 computed attribute targets for a given kind.

        Transitively includes targets that depend on the initially matched targets
        (e.g. if label depends on name and fqdn depends on label, updating name
        returns both label and fqdn targets in dependency order).
        """
        registered = self._map.get(kind)
        if not registered or not updates:
            return [t for t in self.get_impacted_targets(kind=kind, updates=updates) if t.kind == kind]

        return registered.get_local_targets_in_dependency_order(kind=kind, updates=updates)

    def get_registered_node(self, kind: str) -> RegisteredNodeComputedAttribute | None:
        """Return the registered node entry for a given kind, or None."""
        return self._map.get(kind)

    def get_target_map(self) -> dict[ComputedAttributeTarget, list[str]]:
        mapping: dict[ComputedAttributeTarget, set[str]] = {}

        for node, registered_computed_attribute in self._map.items():
            for local_fields in registered_computed_attribute.local_fields.values():
                for local_field in local_fields:
                    if local_field not in mapping:
                        mapping[local_field] = set()
                    mapping[local_field].add(node)

        return {key: list(value) for key, value in mapping.items()}

    def get_trigger_nodes(self) -> dict[ComputedAttributeTarget, list[ComputedAttributeTriggerNode]]:
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

        for node_kind, registered in self._map.items():
            # Local fields: attributes and relationship names on the trigger node itself
            for local_field, targets in registered.local_fields.items():
                for target in targets:
                    _ensure_trigger(target, node_kind).attributes.append(local_field)
            # Relationships: the trigger node is a peer reached via this relationship
            for relationship, targets in registered.relationships.items():
                for target in targets:
                    _ensure_trigger(target, node_kind).relationships.append(relationship)

        return {target: list(nodes.values()) for target, nodes in working_map.items()}
