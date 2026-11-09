from __future__ import annotations

from uuid import uuid4

from infrahub.core.branch import Branch
from infrahub.core.changelog.models import (
    AttributeChangelog,
    ChangelogRelatedNode,
    NodeChangelog,
    RelationshipCardinalityManyChangelog,
    RelationshipPeerChangelog,
)
from infrahub.core.constants import DiffAction
from infrahub.events.limits import get_prefect_max_related_resources, get_related_resource_budget
from infrahub.events.node_action import NodeCreatedEvent
from tests.helpers.events import dummy_event_meta

# Mirrors a real-world trunk interface carrying (almost) every VLAN of a 4k VLAN range.
LARGE_PEER_COUNT = 4000
SMALL_PEER_COUNT = 3


def _make_event(peer_count: int) -> NodeCreatedEvent:
    changelog = NodeChangelog(
        node_id=str(uuid4()),
        node_kind="NetworkPhysicalInterface",
        display_label="Ethernet52",
    )
    changelog.attributes["description"] = AttributeChangelog(
        name="description", value="trunk interface", value_previous=None, kind="Text"
    )
    changelog.add_parent(ChangelogRelatedNode(node_id=str(uuid4()), node_kind="NetworkDevice"))
    changelog.relationships["tagged_vlans"] = RelationshipCardinalityManyChangelog(
        name="tagged_vlans",
        peers=[
            RelationshipPeerChangelog(
                peer_id=str(uuid4()),
                peer_kind="NetworkVlan",
                peer_status=DiffAction.ADDED,
            )
            for _ in range(peer_count)
        ],
    )

    return NodeCreatedEvent(
        kind=changelog.node_kind,
        node_id=changelog.node_id,
        changelog=changelog,
        fields=changelog.updated_fields,
        meta=dummy_event_meta(branch=Branch(name="main", uuid=uuid4())),
    )


def test_related_resources_stay_within_prefect_maximum_for_large_relationships() -> None:
    """The related resources of a node mutation event must fit within the Prefect maximum.

    The Prefect API rejects any event whose list of related resources exceeds the
    configured maximum, so an event emitted for a node with a large cardinality-many
    relationship must keep its related resources bounded or it is never recorded.
    """
    event = _make_event(peer_count=LARGE_PEER_COUNT)

    related = event.get_related()

    assert len(related) <= get_prefect_max_related_resources()


def test_truncation_drops_peer_entries_not_node_scoped_entries() -> None:
    """Per-peer entries are the unbounded part, so only they are truncated.

    The entries describing the node itself (attribute updates, its parent, the
    node's own related-node entry) must survive, and the remaining space is
    filled with relationship updates, which automation triggers match on.
    """
    event = _make_event(peer_count=LARGE_PEER_COUNT)

    related = event.get_related()

    attribute_entries = [item for item in related if item["prefect.resource.role"] == "infrahub.node.attribute_update"]
    assert [item["infrahub.attribute.name"] for item in attribute_entries] == ["description"]

    parent_entries = [item for item in related if item["prefect.resource.role"] == "infrahub.node.parent"]
    assert [item["infrahub.parent.id"] for item in parent_entries] == [event.changelog.parent.node_id]  # type: ignore[union-attr]

    # Far more peers than remaining slots: the per-peer related-node entries are
    # all dropped (only the node's own remains) and every remaining slot goes to
    # a relationship update, up to the budget.
    related_node_ids = [
        item["prefect.resource.id"] for item in related if item["prefect.resource.role"] == "infrahub.related.node"
    ]
    assert related_node_ids == [event.node_id]

    relationship_entries = [
        item for item in related if item["prefect.resource.role"] == "infrahub.node.relationship_update"
    ]
    assert relationship_entries
    assert len(related) == get_related_resource_budget()


def test_small_changelog_keeps_every_peer_entry() -> None:
    """Nodes with ordinarily-sized relationships keep both entries of every peer."""
    event = _make_event(peer_count=SMALL_PEER_COUNT)

    related = event.get_related()

    peer_ids = [peer.peer_id for peer in event.changelog.relationships["tagged_vlans"].peers]  # type: ignore[union-attr]

    relationship_peer_ids = [
        item["infrahub.relationship.peer_id"]
        for item in related
        if item["prefect.resource.role"] == "infrahub.node.relationship_update"
    ]
    assert relationship_peer_ids == peer_ids

    related_node_ids = [
        item["prefect.resource.id"] for item in related if item["prefect.resource.role"] == "infrahub.related.node"
    ]
    assert set(peer_ids) <= set(related_node_ids)
