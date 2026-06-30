"""Origin labelling and recompute-trigger suppression for replayed merge/rebase changes.

Node events carry an origin label so the coalesced merge and rebase recompute can own the
computed-attribute, display-label, and human-friendly-id families while their per-node
automations skip the replayed change. A live mutation keeps the default origin and keeps firing.
"""

from __future__ import annotations

import uuid

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.computed_attribute.models import ComputedAttrJinja2TriggerDefinition
from infrahub.context import InfrahubContext
from infrahub.core.branch import Branch
from infrahub.core.changelog.models import NodeChangelog
from infrahub.core.constants import ComputedAttributeKind
from infrahub.core.schema import AttributeSchema
from infrahub.core.schema.computed_attribute import ComputedAttribute
from infrahub.core.schema.schema_branch_computed import ComputedAttributeTarget, ComputedAttributeTriggerNode
from infrahub.display_labels.models import DisplayLabelTriggerDefinition
from infrahub.events.constants import NODE_ORIGIN_LABEL, NodeMutationOrigin
from infrahub.events.models import EventMeta
from infrahub.events.node_action import NodeUpdatedEvent
from infrahub.hfid.models import HFIDTriggerDefinition


def _node_event(origin: NodeMutationOrigin | None) -> NodeUpdatedEvent:
    branch = Branch(name="test-node-origin", uuid=uuid.uuid4())
    meta = EventMeta(
        branch=branch,
        context=InfrahubContext.init(
            branch=branch,
            account=AccountSession(auth_type=AuthType.NONE, authenticated=False, account_id=""),
        ).to_event_context(),
    )
    meta.origin = origin
    return NodeUpdatedEvent(
        kind="TestingNode",
        node_id="node-1",
        changelog=NodeChangelog(node_id="node-1", node_kind="TestingNode", display_label="node-1"),
        fields=["name"],
        meta=meta,
    )


def test_live_node_event_carries_the_default_origin() -> None:
    assert _node_event(origin=None).get_resource()[NODE_ORIGIN_LABEL] == NodeMutationOrigin.LIVE


def test_merge_node_event_carries_the_merge_origin() -> None:
    assert _node_event(origin=NodeMutationOrigin.MERGE).get_resource()[NODE_ORIGIN_LABEL] == NodeMutationOrigin.MERGE


def test_rebase_node_event_carries_the_rebase_origin() -> None:
    assert _node_event(origin=NodeMutationOrigin.REBASE).get_resource()[NODE_ORIGIN_LABEL] == NodeMutationOrigin.REBASE


def test_origin_label_is_a_plain_string_on_the_wire() -> None:
    """Prefect matches on the serialized resource, so the label must be a plain str, not the enum."""
    resource_value = _node_event(origin=NodeMutationOrigin.MERGE).get_resource()[NODE_ORIGIN_LABEL]
    assert type(resource_value) is str
    match_value = DisplayLabelTriggerDefinition.new(
        branch="main", node_kind="TestingPeer", target_kind="TestingNode", template_hash="hash", fields=["name"]
    ).trigger.match[NODE_ORIGIN_LABEL]
    assert type(match_value) is str


def test_display_label_trigger_matches_only_live_origin() -> None:
    definition = DisplayLabelTriggerDefinition.new(
        branch="main",
        node_kind="TestingPeer",
        target_kind="TestingNode",
        template_hash="hash",
        fields=["name"],
    )
    assert definition.trigger.match[NODE_ORIGIN_LABEL] == NodeMutationOrigin.LIVE


def test_hfid_trigger_matches_only_live_origin() -> None:
    definition = HFIDTriggerDefinition.new(
        branch="main",
        node_kind="TestingPeer",
        target_kind="TestingNode",
        hfid_hash="hash",
        fields=["name"],
    )
    assert definition.trigger.match[NODE_ORIGIN_LABEL] == NodeMutationOrigin.LIVE


def test_computed_jinja2_trigger_matches_only_live_origin() -> None:
    attribute = AttributeSchema(
        name="summary",
        kind="Text",
        optional=True,
        read_only=True,
        computed_attribute=ComputedAttribute(kind=ComputedAttributeKind.JINJA2, jinja2_template="{{ name__value }}"),
    )
    target = ComputedAttributeTarget(kind="TestingNode", attribute=attribute)
    trigger_node = ComputedAttributeTriggerNode(kind="TestingPeer", attributes=["name"])

    definition = ComputedAttrJinja2TriggerDefinition.from_computed_attribute(
        branch="main",
        computed_attribute=target,
        trigger_node=trigger_node,
    )
    assert definition.trigger.match[NODE_ORIGIN_LABEL] == NodeMutationOrigin.LIVE
