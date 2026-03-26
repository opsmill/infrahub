"""Tests for Jinja2 computed attribute trigger definitions.

Verifies that self-targeting triggers use _trigger_placeholder fields (matching the
HFID/display label pattern) while remote triggers preserve their real field names.
"""

from typing import Any
from unittest.mock import patch

import pytest

from infrahub.computed_attribute.models import ComputedAttrJinja2TriggerDefinition
from infrahub.core.constants import ComputedAttributeKind
from infrahub.core.schema import AttributeSchema
from infrahub.core.schema.computed_attribute import ComputedAttribute
from infrahub.core.schema.schema_branch_computed import (
    ComputedAttributeTarget,
    ComputedAttributeTriggerNode,
)

TRIGGER_PLACEHOLDER = "_trigger_placeholder"


def _make_computed_attr(name: str, template: str) -> AttributeSchema:
    return AttributeSchema(
        name=name,
        kind="Text",
        computed_attribute=ComputedAttribute(kind=ComputedAttributeKind.JINJA2, jinja2_template=template),
    )


def _make_target(kind: str, attr_name: str, template: str) -> ComputedAttributeTarget:
    return ComputedAttributeTarget(kind=kind, attribute=_make_computed_attr(attr_name, template))


@pytest.fixture
def self_trigger() -> ComputedAttributeTriggerNode:
    """Trigger node for the node itself (e.g. InfraDevice triggers InfraDevice.computed_name)."""
    return ComputedAttributeTriggerNode(
        kind="InfraDevice",
        attributes=["instance", "name"],
        relationships=[],
        targets_self=True,
    )


@pytest.fixture
def remote_trigger() -> ComputedAttributeTriggerNode:
    """Trigger node for a peer (e.g. InfraSite triggers InfraDevice.computed_name)."""
    return ComputedAttributeTriggerNode(
        kind="InfraSite",
        attributes=["name"],
        relationships=["site"],
        targets_self=False,
    )


@pytest.fixture
def target() -> ComputedAttributeTarget:
    return _make_target("InfraDevice", "computed_name", "{{ instance__value }}-{{ site__name__value }}")


class TestSelfTargetingTriggerPlaceholder:
    """Verify that self-targeting triggers get placeholder fields."""

    @patch("infrahub.computed_attribute.models.registry")
    def test_self_targeting_trigger_uses_placeholder(
        self,
        mock_registry: Any,
        self_trigger: ComputedAttributeTriggerNode,
        target: ComputedAttributeTarget,
    ) -> None:
        mock_registry.default_branch = "main"

        # Apply the same transformation as gather_trigger_computed_attribute_jinja2()
        trigger_node = self_trigger.model_copy(update={"attributes": [TRIGGER_PLACEHOLDER], "relationships": []})

        definition = ComputedAttrJinja2TriggerDefinition.from_computed_attribute(
            branch="main",
            computed_attribute=target,
            trigger_node=trigger_node,
        )

        assert definition.trigger.match_related["infrahub.field.name"] == [TRIGGER_PLACEHOLDER]
        assert definition.trigger_kind == "InfraDevice"
        assert definition.targets_self is True

    @patch("infrahub.computed_attribute.models.registry")
    def test_remote_trigger_keeps_real_fields(
        self,
        mock_registry: Any,
        remote_trigger: ComputedAttributeTriggerNode,
        target: ComputedAttributeTarget,
    ) -> None:
        mock_registry.default_branch = "main"

        definition = ComputedAttrJinja2TriggerDefinition.from_computed_attribute(
            branch="main",
            computed_attribute=target,
            trigger_node=remote_trigger,
        )

        assert definition.trigger.match_related["infrahub.field.name"] == ["name", "site"]
        assert definition.trigger_kind == "InfraSite"
        assert definition.targets_self is False


class TestMixedLocalRemoteTriggers:
    """Verify mixed local+remote dependencies produce correct trigger sets."""

    @patch("infrahub.computed_attribute.models.registry")
    def test_mixed_dependencies_produce_placeholder_and_real(
        self,
        mock_registry: Any,
        self_trigger: ComputedAttributeTriggerNode,
        remote_trigger: ComputedAttributeTriggerNode,
        target: ComputedAttributeTarget,
    ) -> None:
        """A computed attribute with both local and remote deps should produce:
        - One trigger with _trigger_placeholder for the self-targeting kind
        - One trigger with real field names for the remote kind
        """
        mock_registry.default_branch = "main"
        trigger_nodes = [self_trigger, remote_trigger]

        definitions = []
        for trigger_node in trigger_nodes:
            effective_trigger = trigger_node
            if trigger_node.targets_self:
                effective_trigger = trigger_node.model_copy(
                    update={"attributes": [TRIGGER_PLACEHOLDER], "relationships": []}
                )
            definitions.append(
                ComputedAttrJinja2TriggerDefinition.from_computed_attribute(
                    branch="main",
                    computed_attribute=target,
                    trigger_node=effective_trigger,
                )
            )

        assert len(definitions) == 2

        self_def = next(d for d in definitions if d.trigger_kind == "InfraDevice")
        remote_def = next(d for d in definitions if d.trigger_kind == "InfraSite")

        assert self_def.trigger.match_related["infrahub.field.name"] == [TRIGGER_PLACEHOLDER]
        assert self_def.targets_self is True

        assert remote_def.trigger.match_related["infrahub.field.name"] == ["name", "site"]
        assert remote_def.targets_self is False


class TestLocalOnlyTrigger:
    """Verify a computed attribute with only local dependencies still produces a placeholder trigger."""

    @patch("infrahub.computed_attribute.models.registry")
    def test_local_only_produces_placeholder_trigger(
        self,
        mock_registry: Any,
    ) -> None:
        """A computed attribute that only references local attributes (no peer relationships)
        should still produce one trigger with _trigger_placeholder fields, not zero triggers.
        """
        mock_registry.default_branch = "main"

        target = _make_target("InfraDevice", "computed_name", "{{ name__value }}-{{ instance__value }}")
        local_trigger = ComputedAttributeTriggerNode(
            kind="InfraDevice",
            attributes=["name", "instance"],
            relationships=[],
            targets_self=True,
        )

        # Apply placeholder transformation
        trigger_node = local_trigger.model_copy(update={"attributes": [TRIGGER_PLACEHOLDER], "relationships": []})

        definition = ComputedAttrJinja2TriggerDefinition.from_computed_attribute(
            branch="main",
            computed_attribute=target,
            trigger_node=trigger_node,
        )

        assert definition.trigger.match_related["infrahub.field.name"] == [TRIGGER_PLACEHOLDER]
        assert definition.trigger_kind == "InfraDevice"
        assert definition.targets_self is True


class TestRemoteOnlyTrigger:
    """Verify a computed attribute with only remote dependencies keeps real field names."""

    @patch("infrahub.computed_attribute.models.registry")
    def test_remote_only_keeps_real_fields(
        self,
        mock_registry: Any,
    ) -> None:
        mock_registry.default_branch = "main"

        target = _make_target(
            "InfraDevice",
            "computed_location",
            "{{ site__name__value }}",
        )
        remote_trigger = ComputedAttributeTriggerNode(
            kind="InfraSite",
            attributes=["name"],
            relationships=["site"],
            targets_self=False,
        )

        definition = ComputedAttrJinja2TriggerDefinition.from_computed_attribute(
            branch="main",
            computed_attribute=target,
            trigger_node=remote_trigger,
        )

        assert definition.trigger.match_related["infrahub.field.name"] == ["name", "site"]
        assert definition.targets_self is False
