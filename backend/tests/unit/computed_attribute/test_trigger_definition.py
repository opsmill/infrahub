"""Tests for gather_trigger_computed_attribute_jinja2.

Verifies the placeholder substitution logic: self-targeting triggers get
_trigger_placeholder fields, remote triggers keep their real field names.
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from infrahub.computed_attribute.gather import gather_trigger_computed_attribute_jinja2
from infrahub.core.constants import ComputedAttributeKind
from infrahub.core.schema import AttributeSchema
from infrahub.core.schema.computed_attribute import ComputedAttribute
from infrahub.core.schema.schema_branch_computed import (
    ComputedAttributeTarget,
    ComputedAttributeTriggerNode,
)
from infrahub.trigger.constants import TRIGGER_PLACEHOLDER_FIELD


def _make_target(kind: str, attr_name: str, template: str, optional: bool = False) -> ComputedAttributeTarget:
    return ComputedAttributeTarget(
        kind=kind,
        attribute=AttributeSchema(
            name=attr_name,
            kind="Text",
            optional=optional,
            computed_attribute=ComputedAttribute(kind=ComputedAttributeKind.JINJA2, jinja2_template=template),
        ),
    )


@pytest.fixture(autouse=True)
def _patch_prefect_logger() -> Any:
    with patch(
        "infrahub.computed_attribute.gather.get_run_logger",
        return_value=logging.getLogger("test_trigger_definition"),
    ):
        yield


def _build_registry_mock(
    trigger_mapping: dict[ComputedAttributeTarget, list[ComputedAttributeTriggerNode]],
) -> MagicMock:
    """Build a mock registry that returns the given trigger mapping for the main branch."""
    mock_reg = MagicMock()
    mock_reg.default_branch = "main"
    mock_reg.get_altered_schema_branches.return_value = []

    schema_branch = MagicMock()
    schema_branch.computed_attributes.get_jinja2_trigger_nodes.return_value = trigger_mapping
    mock_reg.schema.get_schema_branch.return_value = schema_branch

    return mock_reg


class TestGatherSelfTargetingPlaceholder:
    """Self-targeting triggers should have their fields replaced with _trigger_placeholder."""

    @pytest.mark.anyio
    async def test_self_targeting_trigger_gets_placeholder(self) -> None:
        target = _make_target("InfraDevice", "computed_name", "{{ name__value }}-{{ instance__value }}")
        self_trigger = ComputedAttributeTriggerNode(
            kind="InfraDevice", attributes=["name", "instance"], relationships=[], targets_self=True
        )

        mock_reg = _build_registry_mock({target: [self_trigger]})

        with (
            patch("infrahub.computed_attribute.gather.registry", mock_reg),
            patch("infrahub.computed_attribute.models.registry", mock_reg),
        ):
            triggers = await gather_trigger_computed_attribute_jinja2.fn()

        assert len(triggers) == 1
        assert triggers[0].trigger.match_related["infrahub.field.name"] == [TRIGGER_PLACEHOLDER_FIELD]
        assert triggers[0].targets_self is True

    @pytest.mark.anyio
    async def test_remote_trigger_keeps_real_fields(self) -> None:
        target = _make_target("InfraDevice", "computed_name", "{{ site__name__value }}")
        remote_trigger = ComputedAttributeTriggerNode(
            kind="InfraSite", attributes=["name"], relationships=["site"], targets_self=False
        )

        mock_reg = _build_registry_mock({target: [remote_trigger]})

        with (
            patch("infrahub.computed_attribute.gather.registry", mock_reg),
            patch("infrahub.computed_attribute.models.registry", mock_reg),
        ):
            triggers = await gather_trigger_computed_attribute_jinja2.fn()

        assert len(triggers) == 1
        assert triggers[0].trigger.match_related["infrahub.field.name"] == ["name", "site"]
        assert triggers[0].targets_self is False

    @pytest.mark.anyio
    async def test_mixed_self_and_remote_triggers(self) -> None:
        target = _make_target("InfraDevice", "computed_name", "{{ name__value }}-{{ site__name__value }}")
        self_trigger = ComputedAttributeTriggerNode(
            kind="InfraDevice", attributes=["name", "instance"], relationships=[], targets_self=True
        )
        remote_trigger = ComputedAttributeTriggerNode(
            kind="InfraSite", attributes=["name"], relationships=["site"], targets_self=False
        )

        mock_reg = _build_registry_mock({target: [self_trigger, remote_trigger]})

        with (
            patch("infrahub.computed_attribute.gather.registry", mock_reg),
            patch("infrahub.computed_attribute.models.registry", mock_reg),
        ):
            triggers = await gather_trigger_computed_attribute_jinja2.fn()

        assert len(triggers) == 2

        by_kind = {t.trigger_kind: t for t in triggers}
        assert by_kind["InfraDevice"].trigger.match_related["infrahub.field.name"] == [TRIGGER_PLACEHOLDER_FIELD]
        assert by_kind["InfraDevice"].targets_self is True
        assert by_kind["InfraSite"].trigger.match_related["infrahub.field.name"] == ["name", "site"]
        assert by_kind["InfraSite"].targets_self is False
