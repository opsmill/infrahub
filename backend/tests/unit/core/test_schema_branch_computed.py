from infrahub.core.schema import AttributeSchema
from infrahub.core.schema.schema_branch_computed import (
    ComputedAttributes,
    ComputedAttributeTarget,
    RegisteredNodeComputedAttribute,
)


def _attr(name: str) -> AttributeSchema:
    return AttributeSchema(name=name, kind="Text")


def _target(kind: str, attr_name: str, filter_keys: list[str] | None = None) -> ComputedAttributeTarget:
    return ComputedAttributeTarget(kind=kind, attribute=_attr(attr_name), filter_keys=filter_keys or [])


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
