from __future__ import annotations

from uuid import UUID, uuid4

from infrahub.core.changelog.models import RelationshipCardinalityOneChangelog
from infrahub.core.changelog.relationship_mapper import ChangelogRelationshipMapper
from infrahub.core.constants import RelationshipCardinality, RelationshipDirection, RelationshipKind
from infrahub.core.query.relationship import RelationshipPeerData
from infrahub.core.schema import RelationshipSchema


def _parent_schema() -> RelationshipSchema:
    return RelationshipSchema(
        name="parent",
        peer="TestPerson",
        identifier="testchild__parent",
        cardinality=RelationshipCardinality.ONE,
        direction=RelationshipDirection.OUTBOUND,
        kind=RelationshipKind.PARENT,
    )


def _peer_data(peer_id: UUID, peer_kind: str) -> RelationshipPeerData:
    return RelationshipPeerData(
        branch="main",
        source_id=uuid4(),
        source_db_id="source-db-id",
        source_kind="TestChild",
        peer_id=peer_id,
        peer_db_id="peer-db-id",
        peer_kind=peer_kind,
        properties={},
        rel_node_id=uuid4(),
    )


def test_remove_peer_keeps_the_removed_parent_on_the_one_cardinality_changelog() -> None:
    mapper = ChangelogRelationshipMapper(schema=_parent_schema())
    peer_id = uuid4()

    mapper.remove_peer(peer_data=_peer_data(peer_id=peer_id, peer_kind="TestPerson"))

    changelog = mapper.changelog
    assert isinstance(changelog, RelationshipCardinalityOneChangelog)
    assert changelog.peer_id_previous == str(peer_id)
    assert changelog.parent is not None
    assert changelog.parent.node_id == str(peer_id)
    assert changelog.parent.node_kind == "TestPerson"
