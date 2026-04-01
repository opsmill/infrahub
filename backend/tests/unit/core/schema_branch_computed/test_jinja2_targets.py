from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.schema.schema_branch_computed import ComputedAttributes
from infrahub.core.schema.schema_branch_computed.jinja2 import (
    RegisteredNodeComputedAttribute,
    RelationshipDependency,
    ResolvedComputedTarget,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from infrahub.core.schema.schema_branch_computed import ComputedAttributeTarget

LOCAL_KIND = "TestDevice"
REMOTE_KIND = "TestSite"


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


class TestGetTargetsNodeFilters:
    """Verify that node_filters on ResolvedComputedTarget are set correctly."""

    def test_self_target_gets_ids_filter(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """A target triggered only by local fields should get the default ["ids"] filter."""
        target = make_target(kind=LOCAL_KIND, attr_name="computed_name")
        registered = RegisteredNodeComputedAttribute(
            local_fields={"name": [target]},
        )

        results = registered.get_targets(updates=["name"])
        assert len(results) == 1
        assert results[0].node_filters == ["ids"]

    def test_peer_target_gets_only_relationship_filter(
        self, make_target: Callable[..., ComputedAttributeTarget]
    ) -> None:
        """A peer-triggered target should only have relationship filters, not the spurious "ids" filter."""
        target = make_target(kind=LOCAL_KIND, attr_name="computed_name")
        registered = RegisteredNodeComputedAttribute(
            local_fields={"name": [target]},
            relationship_dependencies={
                "site": RelationshipDependency(targets=[target]),
            },
        )

        results = registered.get_targets(updates=["name"])
        assert len(results) == 1
        assert results[0].node_filters == ["site__ids"]

    def test_multiple_relationship_filters(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """A target reachable via multiple relationships gets all relationship filters but no "ids"."""
        target = make_target(kind=LOCAL_KIND, attr_name="computed_name")
        registered = RegisteredNodeComputedAttribute(
            local_fields={"name": [target]},
            relationship_dependencies={
                "site": RelationshipDependency(targets=[target]),
                "region": RelationshipDependency(targets=[target]),
            },
        )

        results = registered.get_targets(updates=["name"])
        assert len(results) == 1
        assert sorted(results[0].node_filters) == ["region__ids", "site__ids"]

    def test_default_node_filters_is_empty(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        """ResolvedComputedTarget should default to an empty node_filters list."""
        resolved = ResolvedComputedTarget(target=make_target(kind=LOCAL_KIND, attr_name="some_attr"))
        assert resolved.node_filters == []


class TestComputedAttributesGetRegisteredJinja2Node:
    def test_returns_node(self, make_target: Callable[..., ComputedAttributeTarget]) -> None:
        expected = RegisteredNodeComputedAttribute(
            relationship_dependencies={
                "site": RelationshipDependency(peer_attributes={"name"}),
                "role": RelationshipDependency(peer_attributes={"label"}),
            },
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
