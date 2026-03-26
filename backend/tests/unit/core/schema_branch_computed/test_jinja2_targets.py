from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.schema.schema_branch_computed import ComputedAttributes
from infrahub.core.schema.schema_branch_computed.jinja2 import RegisteredNodeComputedAttribute

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
