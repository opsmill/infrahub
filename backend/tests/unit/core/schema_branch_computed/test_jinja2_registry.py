from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.schema.basenode_schema import SchemaAttributePath
from infrahub.core.schema.schema_branch_computed import ComputedAttributes
from infrahub.core.schema.schema_branch_computed.jinja2 import RegisteredNodeComputedAttribute, RelationshipDependency

if TYPE_CHECKING:
    from collections.abc import Callable

    from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema
    from infrahub.core.schema.schema_branch_computed import ComputedAttributeTarget


class TestGetJinja2TriggerNodes:
    def test_empty_map(self) -> None:
        computed = ComputedAttributes()
        assert computed.get_jinja2_trigger_nodes() == {}

    def test_single_local_field(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """A single node kind with one local field dependency."""
        node_kind = "InfraDevice"
        t = make_target(node_kind, "computed_name")
        computed = ComputedAttributes(
            jinja2_attribute_map={
                node_kind: RegisteredNodeComputedAttribute(
                    local_fields={"name": [t]},
                ),
            },
        )

        result = computed.get_jinja2_trigger_nodes()

        assert len(result) == 1
        trigger_nodes = result[t]
        assert len(trigger_nodes) == 1
        assert trigger_nodes[0].kind == node_kind
        assert trigger_nodes[0].attributes == ["name"]
        assert trigger_nodes[0].relationships == []
        assert trigger_nodes[0].targets_self is True

    def test_peer_relationship(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """A peer kind triggers recomputation via a relationship."""
        local_kind = "InfraDevice"
        t = make_target(local_kind, "computed_name")
        remote_kind = "InfraSite"
        computed = ComputedAttributes(
            jinja2_attribute_map={
                remote_kind: RegisteredNodeComputedAttribute(
                    local_fields={"name": [t]},
                    relationship_dependencies={"site": RelationshipDependency(targets=[t])},
                ),
            },
        )

        result = computed.get_jinja2_trigger_nodes()

        assert len(result) == 1
        trigger_nodes = result[t]
        assert len(trigger_nodes) == 1
        node = trigger_nodes[0]
        assert node.kind == remote_kind
        assert node.attributes == ["name"]
        assert node.relationships == ["site"]
        assert node.targets_self is False

    def test_multiple_trigger_kinds_for_same_target(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """Two different node kinds both trigger the same computed attribute."""
        local_kind = "InfraDevice"
        t = make_target(local_kind, "computed_name")
        remote_kind = "InfraSite"
        computed = ComputedAttributes(
            jinja2_attribute_map={
                local_kind: RegisteredNodeComputedAttribute(
                    local_fields={"name": [t]},
                ),
                remote_kind: RegisteredNodeComputedAttribute(
                    local_fields={"name": [t]},
                    relationship_dependencies={"site": RelationshipDependency(targets=[t])},
                ),
            },
        )

        result = computed.get_jinja2_trigger_nodes()

        assert len(result) == 1
        trigger_nodes = result[t]
        assert len(trigger_nodes) == 2
        kinds = {n.kind for n in trigger_nodes}
        assert kinds == {local_kind, remote_kind}

        device_node = next(n for n in trigger_nodes if n.kind == local_kind)
        assert device_node.targets_self is True
        assert device_node.attributes == ["name"]
        assert device_node.relationships == []

        site_node = next(n for n in trigger_nodes if n.kind == remote_kind)
        assert site_node.targets_self is False
        assert site_node.attributes == ["name"]
        assert site_node.relationships == ["site"]

    def test_multiple_targets(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """One trigger node kind feeds into multiple computed attributes."""
        target_a = make_target("InfraDevice", "computed_name")
        target_b = make_target("InfraDevice", "computed_label")
        computed = ComputedAttributes(
            jinja2_attribute_map={
                "InfraDevice": RegisteredNodeComputedAttribute(
                    local_fields={"name": [target_a, target_b]},
                ),
            },
        )

        result = computed.get_jinja2_trigger_nodes()

        assert len(result) == 2
        for t in (target_a, target_b):
            trigger_nodes = result[t]
            assert len(trigger_nodes) == 1
            assert trigger_nodes[0].kind == "InfraDevice"
            assert trigger_nodes[0].attributes == ["name"]
            assert trigger_nodes[0].targets_self is True

    def test_multiple_local_fields_same_trigger(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """Multiple local fields on the same trigger kind accumulate in attributes."""
        t = make_target("InfraDevice", "computed_name")
        computed = ComputedAttributes(
            jinja2_attribute_map={
                "InfraDevice": RegisteredNodeComputedAttribute(
                    local_fields={"name": [t], "description": [t]},
                ),
            },
        )

        result = computed.get_jinja2_trigger_nodes()

        trigger_nodes = result[t]
        assert len(trigger_nodes) == 1
        assert set(trigger_nodes[0].attributes) == {"name", "description"}
        assert trigger_nodes[0].targets_self is True


class TestRegisterComputedJinja2:
    def test_local_attribute(
        self,
        make_attr: Callable[..., AttributeSchema],
        make_node: Callable[..., NodeSchema],
    ) -> None:
        """Registering a local attribute (e.g. {{ name__value }}) creates one entry under the owner kind."""
        computed = ComputedAttributes()
        node = make_node("Device")
        computed_attr = make_attr("computed_name")
        path = SchemaAttributePath(attribute_schema=make_attr("name"))

        computed.register_computed_jinja2(node=node, attribute=computed_attr, schema_path=path)

        registry = computed._jinja2._map
        assert set(registry.keys()) == {"InfraDevice"}
        assert list(registry["InfraDevice"].local_fields.keys()) == ["name"]
        assert registry["InfraDevice"].relationship_dependencies == {}

        target = registry["InfraDevice"].local_fields["name"][0]
        assert target.kind == "InfraDevice"
        assert target.attribute.name == "computed_name"

    def test_relationship_attribute(
        self,
        make_attr: Callable[..., AttributeSchema],
        make_rel: Callable[..., RelationshipSchema],
        make_node: Callable[..., NodeSchema],
    ) -> None:
        """Registering a relationship path (e.g. {{ site__name__value }}) creates entries on both peer and owner."""
        computed = ComputedAttributes()
        node = make_node("Device")
        computed_attr = make_attr("computed_name")
        relationship = make_rel("site", peer="InfraSite")
        path = SchemaAttributePath(
            relationship_schema=relationship,
            related_schema=make_node("Site"),
            attribute_schema=make_attr("name"),
        )

        computed.register_computed_jinja2(node=node, attribute=computed_attr, schema_path=path)

        registry = computed._jinja2._map

        # Peer entry (InfraSite): local_fields has the peer attribute, relationships has the relationship name
        assert "InfraSite" in registry
        peer_entry = registry["InfraSite"]
        assert list(peer_entry.local_fields.keys()) == ["name"]
        assert list(peer_entry.relationship_dependencies.keys()) == ["site"]
        assert peer_entry.local_fields["name"][0].kind == "InfraDevice"
        assert peer_entry.relationship_dependencies["site"].targets[0].kind == "InfraDevice"

        # Owner entry (InfraDevice): local_fields has the relationship name (for re-assignment triggers)
        assert "InfraDevice" in registry
        owner_entry = registry["InfraDevice"]
        assert list(owner_entry.local_fields.keys()) == ["site"]
        assert owner_entry.relationship_dependencies["site"].targets == []
        assert owner_entry.relationship_dependencies["site"].peer_attributes == {"name"}
        assert owner_entry.local_fields["site"][0].kind == "InfraDevice"

    def test_multiple_registrations_accumulate(
        self,
        make_attr: Callable[..., AttributeSchema],
        make_rel: Callable[..., RelationshipSchema],
        make_node: Callable[..., NodeSchema],
    ) -> None:
        """Calling register twice for the same node builds up the dependency map."""
        computed = ComputedAttributes()
        node = make_node("Device")
        computed_attr = make_attr("computed_label")

        # First: local attribute "name"
        computed.register_computed_jinja2(
            node=node,
            attribute=computed_attr,
            schema_path=SchemaAttributePath(attribute_schema=make_attr("name")),
        )
        # Second: relationship attribute "site__name"
        computed.register_computed_jinja2(
            node=node,
            attribute=computed_attr,
            schema_path=SchemaAttributePath(
                relationship_schema=make_rel("site", peer="InfraSite"),
                related_schema=make_node("Site"),
                attribute_schema=make_attr("name"),
            ),
        )

        registry = computed._jinja2._map

        # Owner entry should have both "name" (local attr) and "site" (relationship re-assignment)
        owner = registry["InfraDevice"]
        assert set(owner.local_fields.keys()) == {"name", "site"}

        # Peer entry should have the peer attribute and the relationship
        peer = registry["InfraSite"]
        assert list(peer.local_fields.keys()) == ["name"]
        assert list(peer.relationship_dependencies.keys()) == ["site"]
