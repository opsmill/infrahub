from __future__ import annotations

from infrahub.core.constants import DiffAction, RelationshipCardinality
from infrahub.core.diff.model.path import (
    BranchTrackingId,
    EnrichedDiffAttribute,
    EnrichedDiffNode,
    EnrichedDiffRelationship,
    EnrichedDiffRoot,
    EnrichedDiffSingleRelationship,
    NodeIdentifier,
)
from infrahub.core.diff.summary_serializer import DiffSummarySerializer
from infrahub.core.timestamp import Timestamp

SOURCE_BRANCH = "feature"
TARGET_BRANCH = "main"


def _node(
    *,
    uuid: str,
    kind: str,
    action: DiffAction,
    attributes: set[EnrichedDiffAttribute] | None = None,
    relationships: set[EnrichedDiffRelationship] | None = None,
) -> EnrichedDiffNode:
    return EnrichedDiffNode(
        identifier=NodeIdentifier(uuid=uuid, kind=kind, db_id=f"db-{uuid}"),
        label="node-label",
        action=action,
        attributes=attributes or set(),
        relationships=relationships or set(),
    )


def _attribute(
    *, name: str, action: DiffAction, added: int = 0, updated: int = 0, removed: int = 0
) -> EnrichedDiffAttribute:
    return EnrichedDiffAttribute(
        name=name, changed_at=Timestamp(), action=action, num_added=added, num_updated=updated, num_removed=removed
    )


def _relationship(
    *,
    name: str,
    action: DiffAction,
    cardinality: RelationshipCardinality,
    peers: set[EnrichedDiffSingleRelationship] | None = None,
    added: int = 0,
) -> EnrichedDiffRelationship:
    return EnrichedDiffRelationship(
        name=name,
        identifier=f"rel-{name}",
        label=name,
        cardinality=cardinality,
        action=action,
        relationships=peers or set(),
        num_added=added,
    )


def _peer(
    *, peer_id: str, action: DiffAction, added: int = 0, updated: int = 0, removed: int = 0
) -> EnrichedDiffSingleRelationship:
    return EnrichedDiffSingleRelationship(
        changed_at=Timestamp(),
        action=action,
        peer_id=peer_id,
        num_added=added,
        num_updated=updated,
        num_removed=removed,
    )


def _root(nodes: set[EnrichedDiffNode]) -> EnrichedDiffRoot:
    return EnrichedDiffRoot(
        base_branch_name=TARGET_BRANCH,
        diff_branch_name=SOURCE_BRANCH,
        from_time=Timestamp(),
        to_time=Timestamp(),
        uuid="diff-root-uuid",
        tracking_id=BranchTrackingId(name=SOURCE_BRANCH),
        nodes=nodes,
    )


def _serialize(root: EnrichedDiffRoot) -> list:
    return DiffSummarySerializer().serialize(root=root, target_branch_name=TARGET_BRANCH)


def test_unchanged_nodes_are_excluded() -> None:
    root = _root(
        {
            _node(uuid="n1", kind="TestDevice", action=DiffAction.UPDATED),
            _node(uuid="n2", kind="TestDevice", action=DiffAction.UNCHANGED),
        }
    )
    assert {entry["id"] for entry in _serialize(root)} == {"n1"}


def test_actions_are_uppercase_enum_names() -> None:
    root = _root(
        {
            _node(uuid="added", kind="TestDevice", action=DiffAction.ADDED),
            _node(uuid="updated", kind="TestDevice", action=DiffAction.UPDATED),
            _node(uuid="removed", kind="TestDevice", action=DiffAction.REMOVED),
        }
    )
    actions = {entry["id"]: entry["action"] for entry in _serialize(root)}
    assert actions == {"added": "ADDED", "updated": "UPDATED", "removed": "REMOVED"}


def test_nodes_are_tagged_with_target_branch_not_source() -> None:
    root = _root({_node(uuid="n1", kind="TestDevice", action=DiffAction.UPDATED)})
    assert [entry["branch"] for entry in _serialize(root)] == [TARGET_BRANCH]
    assert root.diff_branch_name != TARGET_BRANCH


def test_attribute_element_is_serialized() -> None:
    node = _node(
        uuid="n1",
        kind="CoreArtifactDefinition",
        action=DiffAction.UPDATED,
        attributes={_attribute(name="fingerprint", action=DiffAction.UPDATED, updated=1)},
    )
    (element,) = _serialize(_root({node}))[0]["elements"]
    assert element["name"] == "fingerprint"
    assert element["element_type"] == "ATTRIBUTE"
    assert element["action"] == "UPDATED"
    assert element["summary"] == {"added": 0, "updated": 1, "removed": 0}
    assert "peers" not in element


def test_cardinality_one_relationship_has_no_peers() -> None:
    node = _node(
        uuid="n1",
        kind="TestDevice",
        action=DiffAction.UPDATED,
        relationships={
            _relationship(name="primary_site", action=DiffAction.UPDATED, cardinality=RelationshipCardinality.ONE)
        },
    )
    (element,) = _serialize(_root({node}))[0]["elements"]
    assert element["element_type"] == "RELATIONSHIP_ONE"
    assert "peers" not in element


def test_cardinality_many_relationship_serializes_peers() -> None:
    node = _node(
        uuid="group1",
        kind="CoreStandardGroup",
        action=DiffAction.UPDATED,
        relationships={
            _relationship(
                name="members",
                action=DiffAction.UPDATED,
                cardinality=RelationshipCardinality.MANY,
                added=1,
                peers={_peer(peer_id="member-1", action=DiffAction.ADDED, added=1)},
            )
        },
    )
    (element,) = _serialize(_root({node}))[0]["elements"]
    assert element["name"] == "members"
    assert element["element_type"] == "RELATIONSHIP_MANY"
    assert element["peers"] == [{"action": "ADDED", "summary": {"added": 1, "updated": 0, "removed": 0}}]


def test_unchanged_relationship_without_peers_is_dropped() -> None:
    node = _node(
        uuid="n1",
        kind="TestDevice",
        action=DiffAction.UPDATED,
        attributes={_attribute(name="name", action=DiffAction.UPDATED, updated=1)},
        relationships={
            _relationship(name="tags", action=DiffAction.UNCHANGED, cardinality=RelationshipCardinality.MANY)
        },
    )
    element_names = {element["name"] for element in _serialize(_root({node}))[0]["elements"]}
    assert element_names == {"name"}


def test_changed_element_kept_and_unchanged_element_dropped() -> None:
    node = _node(
        uuid="n1",
        kind="TestDevice",
        action=DiffAction.UPDATED,
        attributes={
            _attribute(name="name", action=DiffAction.UPDATED, updated=1),
            _attribute(name="color", action=DiffAction.UNCHANGED),
        },
    )
    result = _serialize(_root({node}))
    assert [element["name"] for element in result[0]["elements"]] == ["name"]


def test_changed_node_retained_when_all_elements_unchanged() -> None:
    # A conflict resolved to the base branch marks the node changed while leaving every element
    # unchanged, so a node with no triggering element must still be emitted.
    node = _node(
        uuid="n1",
        kind="TestDevice",
        action=DiffAction.UPDATED,
        attributes={_attribute(name="name", action=DiffAction.UNCHANGED)},
    )
    result = _serialize(_root({node}))
    assert [entry["id"] for entry in result] == ["n1"]
    assert result[0]["elements"] == []


def test_dump_then_load_round_trips_the_summary() -> None:
    serializer = DiffSummarySerializer()
    root = _root(
        {
            _node(
                uuid="n1",
                kind="CoreStandardGroup",
                action=DiffAction.UPDATED,
                relationships={
                    _relationship(
                        name="members",
                        action=DiffAction.UPDATED,
                        cardinality=RelationshipCardinality.MANY,
                        added=1,
                        peers={_peer(peer_id="member-1", action=DiffAction.ADDED, added=1)},
                    )
                },
            )
        }
    )
    summary = serializer.serialize(root=root, target_branch_name=TARGET_BRANCH)
    assert serializer.load(serializer.dump(summary)) == summary
