from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class RelationshipDirection(Enum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"
    BIDIRECTIONAL = "bidirectional"


@dataclass
class AttributeMetadata:
    uuid: str
    name: str
    is_deleted: bool
    created_at: Timestamp | None = None
    created_by: str | None = None
    updated_at: Timestamp | None = None
    updated_by: str | None = None

    def __hash__(self) -> int:
        return hash(
            (
                self.uuid,
                self.name,
                self.is_deleted,
                self.created_at,
                self.created_by,
                self.updated_at,
                self.updated_by,
            )
        )


@dataclass
class RelationshipMetadata:
    uuid: str
    identifier: str  # Relationship.name in DB (e.g., "testcar__testperson")
    peer_uuid: str
    direction: RelationshipDirection
    is_deleted: bool
    created_at: Timestamp | None = None
    created_by: str | None = None
    updated_at: Timestamp | None = None
    updated_by: str | None = None

    def __hash__(self) -> int:
        return hash(
            (
                self.uuid,
                self.identifier,
                self.peer_uuid,
                self.direction,
                self.is_deleted,
                self.created_at,
                self.created_by,
                self.updated_at,
                self.updated_by,
            )
        )


@dataclass
class NodeMetadata:
    uuid: str
    kind: str
    is_deleted: bool
    created_at: Timestamp | None = None
    created_by: str | None = None
    updated_at: Timestamp | None = None
    updated_by: str | None = None
    attributes: list[AttributeMetadata] = field(default_factory=list)
    relationships: list[RelationshipMetadata] = field(default_factory=list)

    def __hash__(self) -> int:
        return hash(
            (
                self.uuid,
                self.kind,
                self.is_deleted,
                self.created_at,
                self.created_by,
                self.updated_at,
                self.updated_by,
                tuple(self.attributes),
                tuple(self.relationships),
            )
        )


class NodeMetadataDefaultBranchQuery(Query):
    """Query to retrieve metadata for nodes and their attributes/relationships.

    This query only works on the default branch and reads metadata directly from
    vertex properties. It supports retrieving deleted nodes, attributes, and
    relationships.
    """

    name = "node_metadata"
    type = QueryType.READ
    insert_return = False

    def __init__(self, node_uuids: list[str], **kwargs: Any) -> None:
        self.node_uuids = node_uuids
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        if not self.branch.is_default:
            raise ValueError("NodeMetadataQuery only runs on the default branch")

        self.params["node_uuids"] = self.node_uuids
        self.params["branch"] = self.branch.name

        # Query nodes with their metadata and deletion status
        # Then query attributes and relationships
        query = """
// ------------------
// Part 1: Get node metadata with deletion status
// ------------------
MATCH (n:Node)
WHERE n.uuid IN $node_uuids
CALL (n) {
    MATCH (n)-[r_ipo:IS_PART_OF]->(root:Root)
    WHERE r_ipo.branch = $branch
    RETURN r_ipo
    ORDER BY r_ipo.from DESC
    LIMIT 1
}
WITH n,
    CASE
        WHEN r_ipo.status = "deleted" THEN true
        WHEN r_ipo.to IS NOT NULL THEN true
        ELSE false
    END AS node_is_deleted

// ------------------
// Part 2: Get attribute details
// ------------------
OPTIONAL MATCH (n)-[:HAS_ATTRIBUTE {branch: $branch}]->(attr:Attribute)
WITH DISTINCT n, node_is_deleted, attr
CALL (n, attr) {
    OPTIONAL MATCH (n)-[r_attr:HAS_ATTRIBUTE]->(attr)
    WHERE r_attr.branch = $branch
    WITH r_attr, attr
    ORDER BY r_attr.from DESC
    LIMIT 1
    RETURN {
        uuid: attr.uuid,
        name: attr.name,
        is_deleted: CASE
            WHEN r_attr.status = "deleted" THEN true
            WHEN r_attr.to IS NOT NULL THEN true
            ELSE false
        END,
        created_at: attr.created_at,
        created_by: attr.created_by,
        updated_at: attr.updated_at,
        updated_by: attr.updated_by
    } AS attribute_details
}
WITH n, node_is_deleted, COALESCE(collect(attribute_details), []) AS attributes

// ------------------
// Part 3: Get relationship details
// ------------------
OPTIONAL MATCH (n)-[:IS_RELATED {branch: $branch}]-(rel:Relationship)-[:IS_RELATED {branch: $branch}]-(peer:Node)
WHERE n <> peer
WITH DISTINCT n, node_is_deleted, attributes, rel, peer
CALL (n, rel, peer) {
    OPTIONAL MATCH (n)-[r1:IS_RELATED]-(rel:Relationship)-[r2:IS_RELATED]-(peer:Node)
    WHERE r1.branch = $branch AND r2.branch = $branch
    WITH r1, r2
    ORDER BY r1.from DESC, r2.from DESC
    LIMIT 1
    RETURN {
        uuid: rel.uuid,
        identifier: rel.name,
        peer_uuid: peer.uuid,
        direction: CASE
            WHEN startNode(r1) = n AND startNode(r2) = rel THEN "outbound"
            WHEN startNode(r1) = rel AND startNode(r2) = peer THEN "inbound"
            ELSE "bidirectional"
        END,
        is_deleted: CASE
            WHEN (r1.status = "deleted" OR r1.to IS NOT NULL) AND (r2.status = "deleted" OR r2.to IS NOT NULL) THEN true
            ELSE false
        END,
        created_at: rel.created_at,
        created_by: rel.created_by,
        updated_at: rel.updated_at,
        updated_by: rel.updated_by
    } AS relationship_details
}
WITH n, node_is_deleted, attributes, COALESCE(collect(relationship_details), []) AS relationships

RETURN n.uuid AS node_uuid, n.kind AS node_kind, node_is_deleted,
       n.created_at AS node_created_at, n.created_by AS node_created_by,
       n.updated_at AS node_updated_at, n.updated_by AS node_updated_by,
       attributes, relationships
        """
        self.return_labels = [
            "node_uuid",
            "node_kind",
            "node_is_deleted",
            "node_created_at",
            "node_created_by",
            "node_updated_at",
            "node_updated_by",
            "attributes",
            "relationships",
        ]
        self.add_to_query(query)

    def get_metadatas(self) -> list[NodeMetadata]:
        """Process query results into NodeMetadata dataclasses."""
        from infrahub.core.timestamp import Timestamp

        nodes: list[NodeMetadata] = []

        for result in self.get_results():
            node_uuid = result.get_as_type("node_uuid", return_type=str)
            node_kind = result.get_as_type("node_kind", return_type=str)
            node_is_deleted = result.get_as_type("node_is_deleted", bool)

            node_created_at_str = result.get_as_str("node_created_at")
            node_created_at = Timestamp(node_created_at_str) if node_created_at_str else None
            node_created_by = result.get_as_str("node_created_by")
            node_updated_at_str = result.get_as_str("node_updated_at")
            node_updated_at = Timestamp(node_updated_at_str) if node_updated_at_str else None
            node_updated_by = result.get_as_str("node_updated_by")

            # Parse attributes
            attributes_data: list[dict[str, Any]] = result.get_as_type("attributes", list)
            attributes: list[AttributeMetadata] = []
            for attr_data in attributes_data:
                attr_created_at_str = attr_data.get("created_at")
                attr_created_at = Timestamp(attr_created_at_str) if attr_created_at_str else None
                attr_updated_at_str = attr_data.get("updated_at")
                attr_updated_at = Timestamp(attr_updated_at_str) if attr_updated_at_str else None

                attributes.append(
                    AttributeMetadata(
                        uuid=attr_data["uuid"],
                        name=attr_data["name"],
                        is_deleted=attr_data["is_deleted"],
                        created_at=attr_created_at,
                        created_by=attr_data.get("created_by"),
                        updated_at=attr_updated_at,
                        updated_by=attr_data.get("updated_by"),
                    )
                )

            # Parse relationships
            relationships_data: list[dict[str, Any]] = result.get_as_type("relationships", list)
            relationships: list[RelationshipMetadata] = []
            for rel_data in relationships_data:
                rel_created_at_str = rel_data.get("created_at")
                rel_created_at = Timestamp(rel_created_at_str) if rel_created_at_str else None
                rel_updated_at_str = rel_data.get("updated_at")
                rel_updated_at = Timestamp(rel_updated_at_str) if rel_updated_at_str else None

                direction_str = rel_data["direction"]
                direction = RelationshipDirection(direction_str)

                relationships.append(
                    RelationshipMetadata(
                        uuid=rel_data["uuid"],
                        identifier=rel_data["identifier"],
                        peer_uuid=rel_data["peer_uuid"],
                        direction=direction,
                        is_deleted=rel_data["is_deleted"],
                        created_at=rel_created_at,
                        created_by=rel_data.get("created_by"),
                        updated_at=rel_updated_at,
                        updated_by=rel_data.get("updated_by"),
                    )
                )

            nodes.append(
                NodeMetadata(
                    uuid=node_uuid,
                    kind=node_kind,
                    is_deleted=node_is_deleted,
                    created_at=node_created_at,
                    created_by=node_created_by,
                    updated_at=node_updated_at,
                    updated_by=node_updated_by,
                    attributes=attributes,
                    relationships=relationships,
                )
            )

        return nodes
