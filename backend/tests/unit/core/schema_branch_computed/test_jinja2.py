from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.schema.basenode_schema import SchemaAttributePath
from infrahub.core.schema.schema_branch_computed import ComputedAttributes
from infrahub.core.schema.schema_branch_computed.jinja2 import RegisteredNodeComputedAttribute

if TYPE_CHECKING:
    from collections.abc import Callable

    from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema
    from infrahub.core.schema.schema_branch_computed import ComputedAttributeTarget

LOCAL_KIND = "TestDevice"
REMOTE_KIND = "TestSite"


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
                    relationships={"site": [t]},
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
                    relationships={"site": [t]},
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
        assert registry["InfraDevice"].relationships == {}

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
        assert list(peer_entry.relationships.keys()) == ["site"]
        assert peer_entry.local_fields["name"][0].kind == "InfraDevice"
        assert peer_entry.relationships["site"][0].kind == "InfraDevice"

        # Owner entry (InfraDevice): local_fields has the relationship name (for re-assignment triggers)
        assert "InfraDevice" in registry
        owner_entry = registry["InfraDevice"]
        assert list(owner_entry.local_fields.keys()) == ["site"]
        assert owner_entry.relationships == {}
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
        assert list(peer.relationships.keys()) == ["site"]


class TestComputedAttributesGetLocalJinja2Targets:
    def test_returns_only_self_targeting(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """When a node has both local and remote targets, only local ones are returned."""
        local_target = make_target(kind=LOCAL_KIND, attr_name="computed_name")
        remote_target = make_target(kind=REMOTE_KIND, attr_name="computed_name")

        ca = ComputedAttributes(
            jinja2_attribute_map={
                LOCAL_KIND: RegisteredNodeComputedAttribute(
                    local_fields={
                        "instance": [local_target],
                        "site": [remote_target],
                    },
                ),
            },
        )

        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND)
        assert len(results) == 1
        assert results[0].kind == LOCAL_KIND

    def test_filters_with_updates(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """When updates are specified, only matching fields are returned."""
        instance_attribute_name = "computed_name"
        local_target_name = make_target(kind=LOCAL_KIND, attr_name=instance_attribute_name)
        local_target_desc = make_target(kind=LOCAL_KIND, attr_name="computed_desc")

        ca = ComputedAttributes(
            jinja2_attribute_map={
                LOCAL_KIND: RegisteredNodeComputedAttribute(
                    local_fields={
                        "instance": [local_target_name],
                        "description": [local_target_desc],
                    },
                ),
            },
        )

        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND, updates=["instance"])
        assert len(results) == 1
        assert results[0].attribute.name == instance_attribute_name

    def test_returns_empty_for_unknown_kind(self) -> None:
        ca = ComputedAttributes()
        assert ca.get_local_jinja2_targets(kind="UnknownKind") == []

    def test_returns_empty_when_no_self_targets(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """When all targets are remote (different kind), returns empty."""
        remote_target = make_target(kind=REMOTE_KIND, attr_name="computed_name")

        ca = ComputedAttributes(
            jinja2_attribute_map={
                LOCAL_KIND: RegisteredNodeComputedAttribute(
                    local_fields={"name": [remote_target]},
                ),
            },
        )

        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND)
        assert results == []


class TestComputedAttributesGetLocalJinja2TargetsCascade:
    """Tests for chained dependency resolution in get_local_jinja2_targets."""

    def _make_chain_registry(self, make_target: Callable[..., ComputedAttributeTarget]) -> ComputedAttributes:
        """name -> label -> fqdn chain on a single kind."""
        label_target = make_target(kind=LOCAL_KIND, attr_name="label")
        fqdn_target = make_target(kind=LOCAL_KIND, attr_name="fqdn")
        return ComputedAttributes(
            jinja2_attribute_map={
                LOCAL_KIND: RegisteredNodeComputedAttribute(
                    local_fields={
                        "name": [label_target],
                        "label": [fqdn_target],
                    },
                ),
            },
        )

    def test_returns_full_chain(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        ca = self._make_chain_registry(make_target)
        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND, updates=["name"])
        assert [r.attribute.name for r in results] == ["label", "fqdn"]

    def test_respects_dependency_order(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """label must come before fqdn since fqdn depends on label."""
        ca = self._make_chain_registry(make_target)
        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND, updates=["name"])
        names = [r.attribute.name for r in results]
        assert names.index("label") < names.index("fqdn")

    def test_single_target_no_chain(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """When there's no chain, only the direct target is returned."""
        target = make_target(kind=LOCAL_KIND, attr_name="label")
        ca = ComputedAttributes(
            jinja2_attribute_map={
                LOCAL_KIND: RegisteredNodeComputedAttribute(
                    local_fields={"name": [target]},
                ),
            },
        )
        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND, updates=["name"])
        assert [r.attribute.name for r in results] == ["label"]

    def test_cascade_cycle_terminates(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """alpha -> beta -> alpha cycle does not loop forever."""
        target_alpha = make_target(kind=LOCAL_KIND, attr_name="alpha")
        target_beta = make_target(kind=LOCAL_KIND, attr_name="beta")
        ca = ComputedAttributes(
            jinja2_attribute_map={
                LOCAL_KIND: RegisteredNodeComputedAttribute(
                    local_fields={
                        "beta": [target_alpha],
                        "alpha": [target_beta],
                    },
                ),
            },
        )
        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND, updates=["alpha"])
        assert {r.attribute.name for r in results} == {"alpha", "beta"}

    def test_cascade_diamond(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """Diamond: name -> label, name -> desc, label -> summary, desc -> summary."""
        label_target = make_target(kind=LOCAL_KIND, attr_name="label")
        desc_target = make_target(kind=LOCAL_KIND, attr_name="desc")
        summary_target = make_target(kind=LOCAL_KIND, attr_name="summary")
        ca = ComputedAttributes(
            jinja2_attribute_map={
                LOCAL_KIND: RegisteredNodeComputedAttribute(
                    local_fields={
                        "name": [label_target, desc_target],
                        "label": [summary_target],
                        "desc": [summary_target],
                    },
                ),
            },
        )
        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND, updates=["name"])
        names = [r.attribute.name for r in results]
        # summary appears exactly once despite two paths
        assert names.count("summary") == 1
        # summary comes after both label and desc
        assert names.index("summary") > names.index("label")
        assert names.index("summary") > names.index("desc")

    def test_cascade_mixed_direct_and_transitive(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """When name triggers both label and fqdn, but fqdn also depends on label,
        label must be recomputed before fqdn regardless of list order in local_fields."""
        label_target = make_target(kind=LOCAL_KIND, attr_name="label")
        fqdn_target = make_target(kind=LOCAL_KIND, attr_name="fqdn")
        # fqdn listed BEFORE label in the "name" entry to exercise wrong-order scenario
        ca = ComputedAttributes(
            jinja2_attribute_map={
                LOCAL_KIND: RegisteredNodeComputedAttribute(
                    local_fields={
                        "name": [fqdn_target, label_target],
                        "label": [fqdn_target],
                    },
                ),
            },
        )
        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND, updates=["name"])
        names = [r.attribute.name for r in results]
        assert names.index("label") < names.index("fqdn")

    def test_cascade_skips_remote_targets(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """Remote targets (different kind) are excluded even with cascade."""
        local_target = make_target(kind=LOCAL_KIND, attr_name="label")
        remote_target = make_target(kind=REMOTE_KIND, attr_name="remote_label")
        ca = ComputedAttributes(
            jinja2_attribute_map={
                LOCAL_KIND: RegisteredNodeComputedAttribute(
                    local_fields={
                        "name": [local_target, remote_target],
                        "label": [make_target(kind=LOCAL_KIND, attr_name="fqdn")],
                    },
                ),
            },
        )
        results = ca.get_local_jinja2_targets(kind=LOCAL_KIND, updates=["name"])
        result_kinds = {r.kind for r in results}
        assert REMOTE_KIND not in result_kinds


class TestComputedAttributesGetRegisteredJinja2Node:
    def test_returns_node(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        expected = RegisteredNodeComputedAttribute(
            relationship_peer_attributes={"site": {"name"}, "role": {"label"}},
        )
        ca = ComputedAttributes(
            jinja2_attribute_map={LOCAL_KIND: expected},
        )
        result = ca.get_registered_jinja2_node(LOCAL_KIND)
        assert result is expected
        assert result.relationship_fields == {"site": {"name"}, "role": {"label"}}

    def test_returns_none_for_unknown_kind(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        ca = ComputedAttributes()
        assert ca.get_registered_jinja2_node("UnknownKind") is None
