from typing import Any

from infrahub.core.constants import RelationshipCardinality, RelationshipKind
from infrahub.core.schema import AttributeSchema, RelationshipSchema
from infrahub.core.schema.basenode_schema import SchemaAttributePath
from infrahub.core.schema.schema_branch_computed import (
    ComputedAttributes,
    ComputedAttributeTarget,
    RegisteredNodeComputedAttribute,
)


def _attr(name: str) -> AttributeSchema:
    return AttributeSchema(name=name, kind="Text")


def _rel(name: str, peer: str) -> RelationshipSchema:
    return RelationshipSchema(
        name=name, peer=peer, cardinality=RelationshipCardinality.ONE, kind=RelationshipKind.ATTRIBUTE
    )


def _target(kind: str, attr_name: str, filter_keys: list[str] | None = None) -> ComputedAttributeTarget:
    return ComputedAttributeTarget(kind=kind, attribute=_attr(attr_name), filter_keys=filter_keys or [])


def _fake_node(kind: str) -> Any:
    """Create a minimal object with a .kind attribute, sufficient for register_computed_jinja2."""

    class _Node:
        pass

    node = _Node()
    node.kind = kind  # type: ignore[attr-defined]
    return node


class TestGetJinja2TriggerNodes:
    def test_empty_map(self) -> None:
        computed = ComputedAttributes()
        assert computed.get_jinja2_trigger_nodes() == {}

    def test_single_local_field(self) -> None:
        """A single node kind with one local field dependency."""
        node_kind = "InfraDevice"
        target = _target(node_kind, "computed_name")
        computed = ComputedAttributes(
            jinja2_attribute_map={
                node_kind: RegisteredNodeComputedAttribute(
                    local_fields={"name": [target]},
                ),
            },
        )

        result = computed.get_jinja2_trigger_nodes()

        assert len(result) == 1
        trigger_nodes = result[target]
        assert len(trigger_nodes) == 1
        assert trigger_nodes[0].kind == node_kind
        assert trigger_nodes[0].attributes == ["name"]
        assert trigger_nodes[0].relationships == []
        assert trigger_nodes[0].targets_self is True

    def test_peer_relationship(self) -> None:
        """A peer kind triggers recomputation via a relationship."""
        local_kind = "InfraDevice"
        target = _target("%s" % local_kind, "computed_name")
        remote_kind = "InfraSite"
        computed = ComputedAttributes(
            jinja2_attribute_map={
                ("%s" % remote_kind): RegisteredNodeComputedAttribute(
                    local_fields={"name": [target]},
                    relationships={"site": [target]},
                ),
            },
        )

        result = computed.get_jinja2_trigger_nodes()

        assert len(result) == 1
        trigger_nodes = result[target]
        assert len(trigger_nodes) == 1
        node = trigger_nodes[0]
        assert node.kind == remote_kind
        assert node.attributes == ["name"]
        assert node.relationships == ["site"]
        assert node.targets_self is False

    def test_multiple_trigger_kinds_for_same_target(self) -> None:
        """Two different node kinds both trigger the same computed attribute."""
        local_kind = "InfraDevice"
        target = _target("%s" % local_kind, "computed_name")
        remote_kind = "InfraSite"
        computed = ComputedAttributes(
            jinja2_attribute_map={
                local_kind: RegisteredNodeComputedAttribute(
                    local_fields={"name": [target]},
                ),
                ("%s" % remote_kind): RegisteredNodeComputedAttribute(
                    local_fields={"name": [target]},
                    relationships={"site": [target]},
                ),
            },
        )

        result = computed.get_jinja2_trigger_nodes()

        assert len(result) == 1
        trigger_nodes = result[target]
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

    def test_multiple_targets(self) -> None:
        """One trigger node kind feeds into multiple computed attributes."""
        target_a = _target("InfraDevice", "computed_name")
        target_b = _target("InfraDevice", "computed_label")
        computed = ComputedAttributes(
            jinja2_attribute_map={
                "InfraDevice": RegisteredNodeComputedAttribute(
                    local_fields={"name": [target_a, target_b]},
                ),
            },
        )

        result = computed.get_jinja2_trigger_nodes()

        assert len(result) == 2
        for target in (target_a, target_b):
            trigger_nodes = result[target]
            assert len(trigger_nodes) == 1
            assert trigger_nodes[0].kind == "InfraDevice"
            assert trigger_nodes[0].attributes == ["name"]
            assert trigger_nodes[0].targets_self is True

    def test_multiple_local_fields_same_trigger(self) -> None:
        """Multiple local fields on the same trigger kind accumulate in attributes."""
        target = _target("InfraDevice", "computed_name")
        computed = ComputedAttributes(
            jinja2_attribute_map={
                "InfraDevice": RegisteredNodeComputedAttribute(
                    local_fields={"name": [target], "description": [target]},
                ),
            },
        )

        result = computed.get_jinja2_trigger_nodes()

        trigger_nodes = result[target]
        assert len(trigger_nodes) == 1
        assert set(trigger_nodes[0].attributes) == {"name", "description"}
        assert trigger_nodes[0].targets_self is True


class TestRegisterComputedJinja2:
    def test_local_attribute(self) -> None:
        """Registering a local attribute (e.g. {{ name__value }}) creates one entry under the owner kind."""
        computed = ComputedAttributes()
        node = _fake_node(kind="InfraDevice")
        attr = _attr("computed_name")
        path = SchemaAttributePath(attribute_schema=_attr("name"))

        computed.register_computed_jinja2(node=node, attribute=attr, schema_path=path)

        registry = computed._computed_jinja2_attribute_map
        assert set(registry.keys()) == {"InfraDevice"}
        assert list(registry["InfraDevice"].local_fields.keys()) == ["name"]
        assert registry["InfraDevice"].relationships == {}

        target = registry["InfraDevice"].local_fields["name"][0]
        assert target.kind == "InfraDevice"
        assert target.attribute.name == "computed_name"

    def test_relationship_attribute(self) -> None:
        """Registering a relationship path (e.g. {{ site__name__value }}) creates entries on both peer and owner."""
        computed = ComputedAttributes()
        node = _fake_node(kind="InfraDevice")
        attr = _attr("computed_name")
        rel = _rel("site", peer="InfraSite")
        path = SchemaAttributePath(
            relationship_schema=rel,
            related_schema=_fake_node(kind="InfraSite"),
            attribute_schema=_attr("name"),
        )

        computed.register_computed_jinja2(node=node, attribute=attr, schema_path=path)

        registry = computed._computed_jinja2_attribute_map

        # Peer entry (InfraSite): local_fields has the peer attribute, relationships has the relationship name
        assert "InfraSite" in registry
        peer_entry = registry["InfraSite"]
        assert list(peer_entry.local_fields.keys()) == ["name"]
        assert list(peer_entry.relationships.keys()) == ["site"]
        assert peer_entry.local_fields["name"][0].kind == "InfraDevice"
        assert peer_entry.relationships["site"][0].kind == "InfraDevice"

        # Owner entry (InfraDevice): local_fields has the relationship name (for re-assignment triggers)
        assert "InfraDevice" in registry
        owner_entry = registry["InfraDevice"]
        assert list(owner_entry.local_fields.keys()) == ["site"]
        assert owner_entry.relationships == {}
        assert owner_entry.local_fields["site"][0].kind == "InfraDevice"

    def test_multiple_registrations_accumulate(self) -> None:
        """Calling register twice for the same node builds up the dependency map."""
        computed = ComputedAttributes()
        node = _fake_node(kind="InfraDevice")
        attr = _attr("computed_label")

        # First: local attribute "name"
        computed.register_computed_jinja2(
            node=node,
            attribute=attr,
            schema_path=SchemaAttributePath(attribute_schema=_attr("name")),
        )
        # Second: relationship attribute "site__name"
        computed.register_computed_jinja2(
            node=node,
            attribute=attr,
            schema_path=SchemaAttributePath(
                relationship_schema=_rel("site", peer="InfraSite"),
                related_schema=_fake_node(kind="InfraSite"),
                attribute_schema=_attr("name"),
            ),
        )

        registry = computed._computed_jinja2_attribute_map

        # Owner entry should have both "name" (local attr) and "site" (relationship re-assignment)
        owner = registry["InfraDevice"]
        assert set(owner.local_fields.keys()) == {"name", "site"}

        # Peer entry should have the peer attribute and the relationship
        peer = registry["InfraSite"]
        assert list(peer.local_fields.keys()) == ["name"]
        assert list(peer.relationships.keys()) == ["site"]
