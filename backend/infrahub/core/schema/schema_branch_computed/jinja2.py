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
    be re-evaluated when a dependency changes.
    """

    kind: str
    attribute: AttributeSchema

    @property
    def key_name(self) -> str:
        return f"{self.kind}_{self.attribute.name}"

    def __hash__(self) -> int:
        return hash((self.kind, self.attribute))


class ResolvedComputedTarget(BaseModel):
    """A ComputedAttributeTarget paired with the query filters needed to locate affected nodes.

    The ``node_filters`` carry relationship-based query filters (e.g. ``site__ids``) built at
    resolution time by :meth:`RegisteredNodeComputedAttribute.get_targets`. When the trigger comes
    from the owner itself, the default ``["ids"]`` filter is used.
    """

    target: ComputedAttributeTarget
    node_filters: list[str] = Field(default_factory=list)


class ComputedAttributeTriggerNode(BaseModel):
    kind: str
    attributes: list[str] = Field(default_factory=list)
    relationships: list[str] = Field(default_factory=list)
    targets_self: bool = Field(default=False)

    @property
    def fields(self) -> list[str]:
        return self.attributes + self.relationships


class RelationshipDependency(BaseModel):
    """Groups the two facets of a relationship-based computed attribute dependency:
    the targets to recompute and the peer attributes needed for template rendering.
    """

    targets: list[ComputedAttributeTarget] = Field(default_factory=list)
    peer_attributes: set[str] = Field(default_factory=set)


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
      The ``relationships`` dict provides query filters (e.g. ``site__ids``) so the system
      can locate which devices are affected.
    """

    local_fields: dict[str, list[ComputedAttributeTarget]] = Field(
        default_factory=dict,
        description="These are fields local to the modified node, which can include the names of attributes and relationships",
    )
    relationship_dependencies: dict[str, RelationshipDependency] = Field(
        default_factory=dict,
        description="Maps relationship names to their dependency info: targets to recompute and peer attributes needed for rendering.",
    )

    @property
    def relationship_fields(self) -> dict[str, set[str]]:
        """Return mapping of relationship names to peer attribute names needed for computed attribute templates."""
        return {rel: dep.peer_attributes for rel, dep in self.relationship_dependencies.items()}

    def get_targets(
        self, updates: list[str] | None = None, trigger_kind: str | None = None
    ) -> list[ResolvedComputedTarget]:
        """Resolve which ComputedAttributeTargets are affected by changes to this node.

        Args:
            updates: Field names (attributes or relationships) that changed. When None, all
                     registered local_fields are included.
            trigger_kind: The schema kind of the node that was modified. Used to detect
                          self-referential relationships where a target needs both direct
                          (``ids``) and relationship-based (``rel__ids``) filters.

        Returns:
            Deduplicated list of ResolvedComputedTarget, each pairing a target with the
            query filters needed to locate affected nodes.

        """
        resolved: dict[str, ResolvedComputedTarget] = {}
        for attribute, entries in self.local_fields.items():
            if updates and attribute not in updates:
                continue

            for entry in entries:
                if entry.key_name not in resolved:
                    resolved[entry.key_name] = ResolvedComputedTarget(target=entry)

        for relationship_name, dep in self.relationship_dependencies.items():
            for entry in dep.targets:
                filter_key = f"{relationship_name}__ids"
                if entry.key_name in resolved and filter_key not in resolved[entry.key_name].node_filters:
                    resolved[entry.key_name].node_filters.append(filter_key)

        for target in resolved.values():
            # Self-referential targets need direct ID lookup in addition to any
            # relationship filters, because the changed node itself must also recompute.
            if trigger_kind and target.target.kind == trigger_kind and "ids" not in target.node_filters:
                target.node_filters.append("ids")
            # Targets with no filters need the default "ids" filter
            if not target.node_filters:
                target.node_filters.append("ids")

        return list(resolved.values())

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
            if not ready and deferred:
                # All targets in this wave form a cycle — no clear ordering is
                # possible, so emit them all to avoid silently dropping them.
                ready = deferred
                deferred = []
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
            peer_dep = trigger_node.relationship_dependencies.setdefault(rel_name, RelationshipDependency())
            peer_dep.targets.append(deepcopy(source_attribute))

            # Register on the *owner* entry so that a relationship re-assignment
            owner_entry = self._map.setdefault(source_attribute.kind, RegisteredNodeComputedAttribute())
            owner_entry.local_fields.setdefault(rel_name, []).append(deepcopy(source_attribute))

            # Record which peer attributes are needed per relationship
            owner_dep = owner_entry.relationship_dependencies.setdefault(rel_name, RelationshipDependency())
            owner_dep.peer_attributes.add(schema_path.active_attribute_schema.name)

    def get_impacted_targets(self, kind: str, updates: list[str] | None = None) -> list[ResolvedComputedTarget]:
        """Return computed Jinja2 attribute targets that need re-evaluation when a node of the given kind is modified.

        Args:
            kind: The schema kind of the node that was modified (e.g. "InfraInterface").
            updates: Optional list of field names (attributes or relationships) that changed on the node.
                     When provided, only targets whose Jinja2 templates reference these fields are returned.
                     When None, all registered targets for this kind are returned.

        Returns:
            List of ResolvedComputedTarget entries, each pairing a (kind, attribute) identity with the
            query filters needed to locate affected nodes. The target kind can differ from the input
            kind when the dependency crosses a relationship.

        """
        if mapping := self._map.get(kind):
            return mapping.get_targets(updates=updates, trigger_kind=kind)

        return []

    def get_local_targets(self, kind: str, updates: list[str] | None = None) -> list[ComputedAttributeTarget]:
        """Return only self-targeting Jinja2 computed attribute targets for a given kind.

        Transitively includes targets that depend on the initially matched targets
        (e.g. if label depends on name and fqdn depends on label, updating name
        returns both label and fqdn targets in dependency order).
        """
        registered = self._map.get(kind)
        if not registered:
            return []

        effective_updates = updates or list(registered.local_fields.keys())
        return registered.get_local_targets_in_dependency_order(kind=kind, updates=effective_updates)

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
                    trigger = _ensure_trigger(target, node_kind)
                    if local_field not in trigger.attributes:
                        trigger.attributes.append(local_field)
            # Relationships: the trigger node is a peer reached via this relationship
            for relationship, dep in registered.relationship_dependencies.items():
                for target in dep.targets:
                    trigger = _ensure_trigger(target, node_kind)
                    if relationship not in trigger.relationships:
                        trigger.relationships.append(relationship)

        return {target: list(nodes.values()) for target, nodes in working_map.items()}
