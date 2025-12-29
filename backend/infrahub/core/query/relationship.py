from __future__ import annotations

import inspect
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generator

from infrahub_sdk.uuidt import UUIDT

from infrahub.core.changelog.models import (
    ChangelogRelationshipMapper,
    RelationshipCardinalityManyChangelog,
    RelationshipCardinalityOneChangelog,
)
from infrahub.core.constants import InfrahubKind, MetadataOptions, RelationshipDirection, RelationshipStatus
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.query import Query, QueryType
from infrahub.core.query.subquery import build_subquery_filter, build_subquery_order
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import extract_field_filters
from infrahub.log import get_logger

if TYPE_CHECKING:
    from uuid import UUID

    from neo4j.graph import Relationship as Neo4jRelationship

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.relationship import Relationship
    from infrahub.core.schema import NodeSchema, RelationshipSchema
    from infrahub.database import InfrahubDatabase

# pylint: disable=redefined-builtin,too-many-lines

log = get_logger()


@dataclass
class RelData:
    """Represent a relationship object in the database."""

    db_id: str
    branch: str
    type: str
    status: str

    @classmethod
    def from_db(cls, obj: Neo4jRelationship) -> RelData:
        return cls(db_id=obj.element_id, branch=obj.get("branch"), type=obj.type, status=obj.get("status"))


@dataclass
class FlagPropertyData:
    name: str
    prop_db_id: str
    rel: RelData
    value: bool


@dataclass
class NodePropertyData:
    name: str
    prop_db_id: str
    rel: RelData
    value: UUID


@dataclass
class RelationshipPeerData:
    branch: str

    source_id: UUID
    """UUID of the Source Node."""

    source_db_id: str
    """Internal DB ID of the Source Node."""

    source_kind: str
    """Kind of the Source Node."""

    peer_id: UUID
    """UUID of the Peer Node."""

    peer_db_id: str
    """Internal DB ID of the Peer Node."""

    peer_kind: str
    """Kind of the Peer Node."""

    properties: dict[str, FlagPropertyData | NodePropertyData]
    """UUID of the Relationship Node."""

    rel_node_id: UUID
    """UUID of the Relationship Node."""

    rel_node_db_id: str | None = None
    """Internal DB ID of the Relationship Node."""

    rels: list[RelData] | None = None
    """Both relationships pointing at this Relationship Node."""

    created_at: Timestamp | None = None
    created_by: str | None = None
    updated_at: Timestamp | None = None
    updated_by: str | None = None

    is_from_profile: bool = False
    profile_id: UUID | None = None

    def rel_ids_per_branch(self) -> dict[str, list[str | int]]:
        response = defaultdict(list)
        for rel in self.rels:
            response[rel.branch].append(rel.db_id)

        for prop in self.properties.values():
            response[prop.rel.branch].append(prop.rel.db_id)

        return response


@dataclass
class RelationshipPeersData:
    id: UUID
    identifier: str
    source_id: UUID
    source_kind: str
    destination_id: UUID
    destination_kind: str

    def reversed(self) -> RelationshipPeersData:
        return RelationshipPeersData(
            id=self.id,
            identifier=self.identifier,
            source_id=self.destination_id,
            source_kind=self.destination_kind,
            destination_id=self.source_id,
            destination_kind=self.source_kind,
        )


@dataclass
class FullRelationshipIdentifier:
    identifier: str
    source_kind: str
    destination_kind: str


class RelationshipQuery(Query):
    def __init__(
        self,
        rel: type[Relationship] | Relationship | None = None,
        rel_id: str | None = None,
        source: Node | None = None,
        source_id: UUID | None = None,
        destination: Node | None = None,
        destination_id: UUID | None = None,
        schema: RelationshipSchema | None = None,
        branch: Branch | None = None,
        at: Timestamp | str | None = None,
        **kwargs,
    ):
        if not source and not source_id:
            raise ValueError("Either source or source_id must be provided.")
        if not rel and not rel_id:
            raise ValueError("rel or rel_id must be provided.")
        if not inspect.isclass(rel) and not hasattr(rel, "schema") and not rel_id:
            raise ValueError(
                "Rel must be a Relationship class or an instance of Relationship or a relationship ID must be provided."
            )
        if not schema and inspect.isclass(rel) and not hasattr(rel, "schema"):
            raise ValueError("Either an instance of Relationship or a valid schema must be provided.")

        self.source_id = source_id or source.id
        self.source = source

        # Destination is optional because not all RelationshipQuery needs it
        # If a query must have a destination defined, the validation must be done in the query specific init
        self.destination = destination
        self.destination_id = destination_id
        if not self.destination_id and destination:
            self.destination_id = destination.id

        self.rel = rel
        self.rel_id = rel_id
        self.schema = schema or self.rel.schema

        if not branch and inspect.isclass(rel) and not hasattr(rel, "branch"):
            raise ValueError("Either an instance of Relationship or a valid branch must be provided.")

        self.branch = branch or self.rel.branch

        if at:
            self.at = Timestamp(at)
        elif inspect.isclass(rel) and hasattr(rel, "at"):
            self.at = self.rel.at
        else:
            self.at = Timestamp()

        super().__init__(**kwargs)

    def get_relationship_properties_dict(self, status: RelationshipStatus, user_id: str) -> dict[str, str | None]:
        rel_prop_dict = {
            "branch": self.branch.name,
            "branch_level": self.branch.hierarchy_level,
            "status": status.value,
            "from": self.at.to_string(),
            "from_user_id": user_id,
        }
        if self.schema.hierarchical:
            rel_prop_dict["hierarchy"] = self.schema.hierarchical
        return rel_prop_dict

    def add_source_match_to_query(self, source_branch: Branch) -> None:
        self.params["source_id"] = self.source_id or self.source.get_id()
        if source_branch.is_global or source_branch.is_default:
            source_query_match = """
            MATCH (s:Node { uuid: $source_id })-[source_e:IS_PART_OF {branch_level: 1, status: "active"}]->(:Root)
            WHERE source_e.from <= $at AND (source_e.to IS NULL OR source_e.to > $at)
            OPTIONAL MATCH (s)-[delete_edge:IS_PART_OF {status: "deleted", branch_level: 1}]->(:Root)
            WHERE delete_edge.from <= $at
            WITH *, s WHERE delete_edge IS NULL
            """
        else:
            source_filter, source_filter_params = source_branch.get_query_filter_path(
                at=self.at, variable_name="r", params_prefix="src_"
            )
            source_query_match = """
            MATCH (s:Node { uuid: $source_id })
            CALL (s) {
                MATCH (s)-[r:IS_PART_OF]->(:Root)
                WHERE %(source_filter)s
                RETURN r.status = "active" AS s_is_active
                ORDER BY r.from DESC
                LIMIT 1
            }
            WITH *, s WHERE s_is_active = TRUE
                """ % {"source_filter": source_filter}
            self.params.update(source_filter_params)
        self.add_to_query(source_query_match)

    def add_dest_match_to_query(self, destination_branch: Branch, destination_id: str) -> None:
        self.params["destination_id"] = destination_id
        if destination_branch.is_global or destination_branch.is_default:
            destination_query_match = """
            MATCH (d:Node { uuid: $destination_id })-[dest_e:IS_PART_OF {branch_level: 1, status: "active"}]->(:Root)
            WHERE dest_e.from <= $at AND (dest_e.to IS NULL OR dest_e.to > $at)
            OPTIONAL MATCH (d)-[delete_edge:IS_PART_OF {status: "deleted", branch_level: 1}]->(:Root)
            WHERE delete_edge.from <= $at
            WITH *, d WHERE delete_edge IS NULL
            """
        else:
            destination_filter, destination_filter_params = destination_branch.get_query_filter_path(
                at=self.at, variable_name="r", params_prefix="dst_"
            )
            destination_query_match = """
            MATCH (d:Node { uuid: $destination_id })
            CALL (d) {
                MATCH (d)-[r:IS_PART_OF]->(:Root)
                WHERE %(destination_filter)s
                RETURN r.status = "active" AS d_is_active
                ORDER BY r.from DESC
                LIMIT 1
            }
            WITH *, d WHERE d_is_active = TRUE
            """ % {"destination_filter": destination_filter}
            self.params.update(destination_filter_params)
        self.add_to_query(destination_query_match)


class RelationshipCreateQuery(RelationshipQuery):
    name = "relationship_create"

    type: QueryType = QueryType.WRITE

    def __init__(
        self,
        destination: Node = None,
        destination_id: UUID | None = None,
        **kwargs,
    ):
        if not destination and not destination_id:
            raise ValueError("Either destination or destination_id must be provided.")

        super().__init__(destination=destination, destination_id=destination_id, **kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:  # noqa: ARG002
        self.params["name"] = self.schema.identifier
        self.params["branch_support"] = self.schema.branch.value

        self.params["uuid"] = str(UUIDT())

        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["at"] = self.at.to_string()

        self.params["is_protected"] = self.rel.is_protected
        self.params["user_id"] = self.user_id

        self.add_source_match_to_query(source_branch=self.source.get_branch_based_on_support_type())
        self.add_dest_match_to_query(
            destination_branch=self.destination.get_branch_based_on_support_type(),
            destination_id=self.destination_id or self.destination.get_id(),
        )
        self.query_add_all_node_property_match()

        self.params["rel_prop"] = self.get_relationship_properties_dict(
            status=RelationshipStatus.ACTIVE, user_id=self.user_id
        )
        arrows = self.schema.get_query_arrows()
        r1 = f"{arrows.left.start}[r1:IS_RELATED $rel_prop ]{arrows.left.end}"
        r2 = f"{arrows.right.start}[r2:IS_RELATED $rel_prop ]{arrows.right.end}"

        relationship_create_query = (
            "CREATE (rl:Relationship { uuid: $uuid, name: $name, branch_support: $branch_support"
        )
        if self.branch.is_default or self.branch.is_global:
            relationship_create_query += (
                ", created_at: $at, created_by: $user_id, updated_at: $at, updated_by: $user_id"
            )
        relationship_create_query += " })"
        self.add_to_query(relationship_create_query)

        query_create = """
        CREATE (s)%s(rl)
        CREATE (rl)%s(d)
        MERGE (ip:Boolean { value: $is_protected })
        CREATE (rl)-[r3:IS_PROTECTED $rel_prop ]->(ip)
        """ % (
            r1,
            r2,
        )
        if self.branch.is_default or self.branch.is_global:
            query_create += """
        SET s.updated_at = $at, s.updated_by = $user_id
        SET d.updated_at = $at, d.updated_by = $user_id
            """

        self.add_to_query(query_create)
        self.return_labels = ["s", "d", "rl", "r1", "r2", "r3"]
        self.query_add_all_node_property_create()

    def query_add_all_node_property_match(self) -> None:
        if not self.rel._node_properties:
            return

        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at)
        self.params.update(branch_params)

        for prop_name in self.rel._node_properties:
            if hasattr(self.rel, f"{prop_name}_id") and getattr(self.rel, f"{prop_name}_id"):
                self.query_add_node_property_match(name=prop_name, branch_filter=branch_filter)

    def query_add_node_property_match(self, name: str, branch_filter: str) -> None:
        if self.branch.is_default or self.branch.is_global:
            match_property_peer_query = """
MATCH (%(var_name)s:Node { uuid: $prop_%(var_name)s_id })
WHERE NOT exists((%(var_name)s)-[:IS_PART_OF {branch: $branch, status: "deleted"}]->(:Root))
            """ % {"var_name": name}
        else:
            match_property_peer_query = """
CALL () {
    MATCH (%(var_name)s:Node { uuid: $prop_%(var_name)s_id })-[r:IS_PART_OF]->(:Root)
    WHERE %(branch_filter)s
    RETURN %(var_name)s, r.status = "active" AS %(var_name)s_is_active
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
WITH *
WHERE %(var_name)s_is_active = TRUE
            """ % {"var_name": name, "branch_filter": branch_filter}
        self.add_to_query(match_property_peer_query)
        self.params[f"prop_{name}_id"] = getattr(self.rel, f"{name}_id")
        self.return_labels.append(name)

    def query_add_all_node_property_create(self) -> None:
        for prop_name in self.rel._node_properties:
            if hasattr(self.rel, f"{prop_name}_id") and getattr(self.rel, f"{prop_name}_id"):
                self.query_add_node_property_create(name=prop_name)

    def query_add_node_property_create(self, name: str) -> None:
        query = """
CREATE (rl)-[:HAS_%s { branch: $branch, branch_level: $branch_level, status: "active", from: $at, from_user_id: $user_id }]->(%s)
        """ % (
            name.upper(),
            name,
        )
        self.add_to_query(query)


class RelationshipUpdatePropertyQuery(RelationshipQuery):
    name = "relationship_property_update"
    type = QueryType.WRITE
    insert_return = False
    raise_error_if_empty = False

    def __init__(
        self,
        flag_properties_to_update: dict[str, bool],
        node_properties_to_update: dict[str, str],
        **kwargs,
    ):
        if not flag_properties_to_update and not node_properties_to_update:
            raise ValueError("Either flag_properties_to_update or node_properties_to_update must be set")
        self.flag_properties_to_update = flag_properties_to_update
        self.node_properties_to_update = node_properties_to_update
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:  # noqa: ARG002
        self.params["rel_node_id"] = self.rel_id or (self.rel.id if self.rel else None)
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["user_id"] = self.user_id
        self.params["at"] = self.at.to_string()

        rel_query = """
        MATCH (rl:Relationship { uuid: $rel_node_id })
        """
        if self.branch.is_default or self.branch.is_global:
            rel_query += """
            SET rl.updated_at = $at, rl.updated_by = $user_id
            WITH rl
            """
        self.add_to_query(rel_query)

        self.params["property_types_to_update"] = sorted(
            [flag.upper() for flag in self.flag_properties_to_update.keys()]
        )
        self.params["property_types_to_update"] += sorted(
            [f"HAS_{prop.upper()}" for prop in self.node_properties_to_update.keys()]
        )
        set_to_time_on_current_property_query = """
OPTIONAL MATCH (rl)-[r]->()
WHERE type(r) IN $property_types_to_update
AND r.branch = $branch
AND r.status = "active"
AND r.to IS NULL
SET r.to = $at, r.to_user_id = $user_id
WITH rl
        """
        self.add_to_query(set_to_time_on_current_property_query)

        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at)
        self.params.update(branch_params)

        self.query_add_all_node_property_merge(branch_filter=branch_filter)
        self.query_add_all_flag_property_merge()

        self.query_add_all_node_property_create(branch_filter=branch_filter)
        self.query_add_all_flag_property_create()

        # Update peer node metadata at the end (only on default/global branch)
        if self.branch.is_default or self.branch.is_global:
            peer_metadata_query = """
WITH rl
CALL (rl) {
    MATCH (peer:Node)-[r_rel:IS_RELATED]-(rl)
    WHERE r_rel.branch_level = 1
    WITH DISTINCT peer, rl
    CALL (peer, rl) {
        MATCH (peer)-[r_rel:IS_RELATED]-(rl)
        WHERE r_rel.branch_level = 1
        ORDER BY r_rel.from DESC, r_rel.status ASC
        LIMIT 1
        WITH peer, r_rel
        WHERE r_rel.status = "active" AND r_rel.to IS NULL
        MATCH (peer)-[r_part:IS_PART_OF]->(:Root)
        WHERE r_part.branch_level = 1
        ORDER BY r_part.from DESC, r_part.status ASC
        LIMIT 1
        WITH peer, r_part
        WHERE r_part.status = "active" AND r_part.to IS NULL
        SET peer.updated_at = $at, peer.updated_by = $user_id
    }
}
            """
            self.add_to_query(peer_metadata_query)

    def query_add_all_flag_property_merge(self) -> None:
        for prop_name, prop_value in self.flag_properties_to_update.items():
            self.query_add_flag_property_merge(name=prop_name, value=prop_value)

    def query_add_flag_property_merge(self, name: str, value: bool) -> None:
        self.add_to_query("MERGE (prop_%s:Boolean { value: $prop_%s })" % (name, name))
        self.params[f"prop_{name}"] = value

    def query_add_all_node_property_merge(self, branch_filter: str) -> None:
        for prop_name, prop_value in self.node_properties_to_update.items():
            self.params[f"prop_{prop_name}"] = prop_value
            if self.branch.is_default or self.branch.is_global:
                node_query = """
            OPTIONAL MATCH (prop_%(prop_name)s:Node {uuid: $prop_%(prop_name)s })-[r_%(prop_name)s:IS_PART_OF]->(:Root)
            WHERE r_%(prop_name)s.branch IN $branch0
            AND r_%(prop_name)s.status = "active"
            AND r_%(prop_name)s.from <= $at AND (r_%(prop_name)s.to IS NULL OR r_%(prop_name)s.to > $at)
            WITH *
            WHERE $prop_%(prop_name)s IS NULL OR prop_%(prop_name)s IS NOT NULL
            LIMIT 1
                """ % {"prop_name": prop_name}
            else:
                node_query = """
            OPTIONAL MATCH (prop_%(prop_name)s:Node {uuid: $prop_%(prop_name)s })-[r_%(prop_name)s:IS_PART_OF]->(:Root)
            WHERE all(r in [r_%(prop_name)s] WHERE %(branch_filter)s)
            ORDER BY r_%(prop_name)s.branch_level DESC, r_%(prop_name)s.from DESC, r_%(prop_name)s.status ASC
            LIMIT 1
            WITH *
            WHERE $prop_%(prop_name)s IS NULL OR r_%(prop_name)s.status = "active"
                """ % {"branch_filter": branch_filter, "prop_name": prop_name}
            self.add_to_query(node_query)

    def query_add_all_flag_property_create(self) -> None:
        for prop_name in self.flag_properties_to_update:
            self.query_add_flag_property_create(name=prop_name)

    def query_add_flag_property_create(self, name: str) -> None:
        query = """
        CREATE (rl)-[:%s { branch: $branch, branch_level: $branch_level, status: "active", from: $at, from_user_id: $user_id }]->(prop_%s)
        """ % (
            name.upper(),
            name,
        )
        self.add_to_query(query)

    def query_add_all_node_property_create(self, branch_filter: str) -> None:
        for prop_name in self.node_properties_to_update:
            self.query_add_node_property_create(name=prop_name, branch_filter=branch_filter)

    def query_add_node_property_create(self, name: str, branch_filter: str) -> None:
        query = """
WITH *
CALL (rl, prop_%(var_name)s) {
    WITH rl, prop_%(var_name)s
    WHERE $prop_%(var_name)s IS NOT NULL
    CREATE (rl)
        -[:%(edge_type)s { branch: $branch, branch_level: $branch_level, status: "active", from: $at, from_user_id: $user_id }]
        ->(prop_%(var_name)s)
}
CALL (rl) {
    WITH rl
    WHERE $prop_%(var_name)s IS NULL
    AND $branch_level > 1
    MATCH (rl)-[r:%(edge_type)s]->(current_prop)
    WHERE %(branch_filter)s
    AND r.branch_level = 1
    AND r.status = "active"
    CREATE (rl)
        -[:%(edge_type)s { branch: $branch, branch_level: $branch_level, status: "deleted", from: $at, from_user_id: $user_id }]
        ->(current_prop)
}
        """ % {"edge_type": "HAS_" + name.upper(), "var_name": name, "branch_filter": branch_filter}
        self.add_to_query(query)


class RelationshipDeleteQuery(RelationshipQuery):
    name = "relationship_delete"
    type = QueryType.WRITE
    insert_return = False
    raise_error_if_empty = False

    def __init__(self, source_branch: Branch, destination_branch: Branch, **kwargs):
        self.source_branch = source_branch
        self.destination_branch = destination_branch
        super().__init__(**kwargs)

        if inspect.isclass(self.rel) and not self.rel_id:
            raise TypeError(
                "An instance of Relationship or a relationship ID must be provided to RelationshipDeleteQuery"
            )

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:  # noqa: ARG002
        rel_filter, rel_params = self.branch.get_query_filter_path(at=self.at, variable_name="edge")
        self.params["rel_id"] = self.rel_id or self.rel.id
        self.params["branch"] = self.branch.name
        self.params["rel_prop"] = self.get_relationship_properties_dict(
            status=RelationshipStatus.DELETED, user_id=self.user_id
        )
        self.params["user_id"] = self.user_id
        self.params["at"] = self.at.to_string()
        self.params.update(rel_params)

        arrows = self.schema.get_query_arrows()
        r1 = f"{arrows.left.start}[r1:IS_RELATED $rel_prop ]{arrows.left.end}"
        r2 = f"{arrows.right.start}[r2:IS_RELATED $rel_prop ]{arrows.right.end}"

        self.add_source_match_to_query(source_branch=self.source_branch)
        self.add_dest_match_to_query(
            destination_branch=self.destination_branch,
            destination_id=self.destination_id or self.destination.get_id(),
        )

        # if the IS_RELATED edges are already deleted on this branch, then we assume the delete already succeeded
        rel_match_query = """
        MATCH (s)%(arrows_l1)s[r1:IS_RELATED]%(arrows_l2)s(rl:Relationship { uuid: $rel_id })%(arrows_r1)s[r2:IS_RELATED]%(arrows_r2)s(d)
        WHERE all(edge in [r1, r2] WHERE %(rel_filter)s)
        ORDER BY r1.branch_level DESC, r1.from DESC, r1.status ASC, r2.branch_level DESC, r2.from DESC, r2.status ASC
        LIMIT 1
        WITH s, rl, d, r1 AS source_edge, r2 AS destination_edge
        WHERE source_edge.status = "active" OR destination_edge.status = "active"
        """ % {
            "rel_filter": rel_filter,
            "arrows_l1": arrows.left.start,
            "arrows_l2": arrows.left.end,
            "arrows_r1": arrows.right.start,
            "arrows_r2": arrows.right.end,
        }
        if self.branch.is_default or self.branch.is_global:
            rel_match_query += """
        SET rl.updated_at = $at, rl.updated_by = $user_id
        SET s.updated_at = $at, s.updated_by = $user_id
        SET d.updated_at = $at, d.updated_by = $user_id
            """
        self.add_to_query(rel_match_query)

        query = """
        WITH s, rl, d, source_edge, destination_edge
        // --------------
        // create the deleted edges if the existing edges are on global or default branch
        // --------------
        CALL (s, source_edge, rl) {
            WITH source_edge
            WHERE source_edge.branch <> $branch
            CREATE (s)%(r1)s(rl)
        }
        CALL (rl, destination_edge, d) {
            WITH destination_edge
            WHERE destination_edge.branch <> $branch
            CREATE (rl)%(r2)s(d)
        }
        // --------------
        // set the to time on the existing edges if they are on the current branch
        // --------------
        CALL (s, source_edge, rl) {
            WITH source_edge
            WHERE source_edge.branch = $branch
            AND source_edge.to IS NULL
            SET source_edge.to = $at, source_edge.to_user_id = $user_id
        }
        CALL (rl, destination_edge, d) {
            WITH destination_edge
            WHERE destination_edge.branch = $branch
            AND destination_edge.to IS NULL
            SET destination_edge.to = $at, destination_edge.to_user_id = $user_id
        }
        WITH rl

        OPTIONAL MATCH (rl)-[edge:IS_PROTECTED|HAS_OWNER|HAS_SOURCE]->(peer)
        WHERE %(rel_filter)s
        ORDER BY type(edge), edge.branch_level DESC, edge.from DESC, edge.status ASC
        WITH rl, type(edge) AS edge_type, head(collect(edge)) AS edge, head(collect(peer)) AS peer

        CALL (rl, edge, edge_type, peer) {
            WITH edge
            WHERE edge.branch <> $branch
            AND edge.status = "active"
            CREATE (rl)-[deleted_edge:$(edge_type) $rel_prop]->(peer)
        }
        CALL (edge) {
            WITH edge
            WHERE edge.branch = $branch
            AND edge.status = "active"
            AND edge.to IS NULL
            SET edge.to = $at, edge.to_user_id = $user_id
        }
        """ % {
            "r1": r1,
            "r2": r2,
            "rel_filter": rel_filter,
        }

        self.params["at"] = self.at.to_string()
        self.return_labels = ["rl"]

        self.add_to_query(query)


class RelationshipGetPeerQuery(Query):
    name = "relationship_get_peer"
    type = QueryType.READ

    def __init__(
        self,
        filters: dict | None = None,
        source: Node | None = None,
        source_ids: list[str] | None = None,
        source_kind: str | None = None,
        rel: type[Relationship] | Relationship | None = None,
        rel_type: str | None = None,
        schema: RelationshipSchema | None = None,
        branch: Branch | None = None,
        at: Timestamp | str | None = None,
        include_metadata: MetadataOptions = MetadataOptions.NONE,
        **kwargs,
    ):
        if not source and not source_ids:
            raise ValueError("Either source or source_ids must be provided.")
        if not rel and not rel_type:
            raise ValueError("Either rel or rel_type must be provided.")
        if rel and not inspect.isclass(rel) and not hasattr(rel, "schema"):
            raise ValueError("Rel must be a Relationship class or an instance of Relationship.")
        if not schema and inspect.isclass(rel) and not hasattr(rel, "schema"):
            raise ValueError("Either an instance of Relationship or a valid schema must be provided.")

        self.filters = filters or {}
        self.source_ids = source_ids or [source.id]
        self.source = source

        self.source_kind = source_kind or "Node"
        if source and not source_kind:
            self.source_kind = source.get_kind()

        self.rel = rel
        self.rel_type = rel_type or self.rel.rel_type
        self.schema = schema or self.rel.schema
        self.include_metadata = include_metadata

        if not branch and inspect.isclass(rel) and not hasattr(rel, "branch"):
            raise ValueError("Either an instance of Relationship or a valid branch must be provided.")

        self.branch = branch or self.rel.branch

        if not at and inspect.isclass(rel) and hasattr(rel, "at"):
            self.at = self.rel.at
        else:
            self.at = Timestamp(at)

        super().__init__(**kwargs)

    def _add_is_protected_query(self, branch_filter: str) -> None:
        if not (self.include_metadata & MetadataOptions.IS_PROTECTED):
            return
        query = """
CALL (rl) {
    MATCH (rl)-[r:IS_PROTECTED]-(is_protected)
    WHERE %(branch_filter)s
    RETURN r AS rel_is_protected, is_protected
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
        """ % {"branch_filter": branch_filter}
        self.add_to_query(query)
        self.update_return_labels(["rel_is_protected", "is_protected"])

    def _add_node_property_query(self, node_prop: str, branch_filter: str) -> None:
        query = """
CALL (rl) {
    OPTIONAL MATCH (rl)-[r:HAS_%(node_prop_type)s]-(%(node_prop)s)
    WHERE %(branch_filter)s
    WITH r, %(node_prop)s
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
    RETURN CASE
        WHEN r.status = "active" THEN %(node_prop)s
        ELSE NULL
    END AS %(node_prop)s,
    CASE
        WHEN r.status = "active" THEN r
        ELSE NULL
    END AS rel_%(node_prop)s
}
        """ % {
            "node_prop": node_prop,
            "node_prop_type": node_prop.upper(),
            "branch_filter": branch_filter,
        }
        self.add_to_query(query)
        self.update_return_labels([f"rel_{node_prop}", node_prop])

    def _add_has_owner_query(self, branch_filter: str) -> None:
        if not (self.include_metadata & MetadataOptions.OWNER):
            return
        self._add_node_property_query(node_prop="owner", branch_filter=branch_filter)

    def _add_has_source_query(self, branch_filter: str) -> None:
        if not (self.include_metadata & MetadataOptions.SOURCE):
            return
        self._add_node_property_query(node_prop="source", branch_filter=branch_filter)

    def _add_created_metadata_to_query(self) -> None:
        if not (self.include_metadata & (MetadataOptions.CREATED_AT | MetadataOptions.CREATED_BY)):
            return
        if self.branch.is_default or self.branch.is_global:
            last_created_query = """
WITH *, rl.created_at AS created_at, rl.created_by AS created_by
            """
        else:
            last_created_query = """
CALL (rels) {
    UNWIND rels AS rel
    RETURN rel.from AS created_at, rel.from_user_id AS created_by
    ORDER BY created_at ASC
    LIMIT 1
}
            """
        self.add_to_query(last_created_query)
        self.update_return_labels(["created_at", "created_by"])

    def _add_updated_metadata_to_query(self, branch_filter_str: str) -> None:
        if not (self.include_metadata & (MetadataOptions.UPDATED_AT | MetadataOptions.UPDATED_BY)):
            return
        self.update_return_labels(["updated_at", "updated_by"])
        if self.branch.is_default or self.branch.is_global:
            last_updated_query = """
WITH *, rl.updated_at AS updated_at, rl.updated_by AS updated_by
            """
            self.add_to_query(last_updated_query)
            return

        # query for non-default, non-global branches
        if self.branch_agnostic:
            time_details = """
WITH [r.from, r.from_user_id] AS from_details, [r.to, r.to_user_id] AS to_details
            """
        else:
            time_details = """
WITH CASE
    WHEN $is_branch_agnostic THEN [r.from, r.from_user_id]
    WHEN r.branch IN $branch0 AND r.from < $time0 THEN [r.from, r.from_user_id]
    WHEN r.branch IN $branch1 AND r.from < $time1 THEN [r.from, r.from_user_id]
    ELSE [NULL, NULL]
END AS from_details,
CASE
    WHEN $is_branch_agnostic THEN [r.to, r.to_user_id]
    WHEN r.branch IN $branch0 AND r.to < $time0 THEN [r.to, r.to_user_id]
    WHEN r.branch IN $branch1 AND r.to < $time1 THEN [r.to, r.to_user_id]
    ELSE [NULL, NULL]
END AS to_details
            """
        last_updated_query = """
CALL (rl) {
MATCH (rl)-[r]-(property)
WHERE %(branch_filter)s
%(time_details)s
WITH collect(from_details) AS from_details_list, collect(to_details) AS to_details_list
WITH from_details_list + to_details_list AS details_list
UNWIND details_list AS one_details
WITH one_details[0] AS updated_at, one_details[1] AS updated_by
WHERE updated_at IS NOT NULL
WITH updated_at, updated_by
ORDER BY updated_at DESC
LIMIT 1
RETURN updated_at, updated_by
}
        """ % {"branch_filter": branch_filter_str, "time_details": time_details}
        self.add_to_query(last_updated_query)

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at, branch_agnostic=self.branch_agnostic
        )
        self.params.update(branch_params)
        self.order_by = []

        peer_schema = self.schema.get_peer_schema(db=db, branch=self.branch)

        self.params["is_branch_agnostic"] = self.branch_agnostic
        self.params["source_ids"] = self.source_ids
        self.params["rel_identifier"] = self.schema.identifier
        self.params["peer_kind"] = self.schema.peer
        self.params["source_kind"] = self.source_kind

        arrows = self.schema.get_query_arrows()

        path_str = f"{arrows.left.start}[r1:IS_RELATED]{arrows.left.end}(rl){arrows.right.start}[r2:IS_RELATED]{arrows.right.end}"

        branch_level_str = "reduce(br_lvl = 0, r in relationships(path) | br_lvl + r.branch_level)"
        query = """
        MATCH (source_node:Node)%(arrow_left_start)s[:IS_RELATED]%(arrow_left_end)s(rl:Relationship { name: $rel_identifier })
        WHERE source_node.uuid IN $source_ids
        WITH DISTINCT source_node, rl
        CALL (rl, source_node) {
            MATCH path = (source_node)%(path)s(peer:Node)
            WHERE
                $source_kind IN LABELS(source_node) AND
                peer.uuid <> source_node.uuid AND
                $peer_kind IN LABELS(peer) AND
                all(r IN [r1, r2] WHERE (%(branch_filter)s))
            WITH source_node, peer, rl, r1, r2, %(branch_level)s AS branch_level
            RETURN peer as peer, r1.status = "active" AND r2.status = "active" AS is_active, [r1, r2] AS rels
            // status is required as a tiebreaker for migrated-kind nodes
            ORDER BY branch_level DESC, r2.from DESC, r2.status ASC, r1.from DESC, r1.status ASC
            LIMIT 1
        }
        WITH peer, rl, is_active, rels, source_node
        """ % {
            "path": path_str,
            "branch_filter": branch_filter,
            "branch_level": branch_level_str,
            "arrow_left_start": arrows.left.start,
            "arrow_left_end": arrows.left.end,
        }

        self.add_to_query(query)
        where_clause = ["is_active = TRUE"]
        clean_filters = extract_field_filters(field_name=self.schema.name, filters=self.filters)

        if (clean_filters and "id" in clean_filters) or "ids" in clean_filters:
            where_clause.append("peer.uuid IN $peer_ids")
            self.params["peer_ids"] = clean_filters.get("ids", [])
            if clean_filters.get("id", None):
                self.params["peer_ids"].append(clean_filters.get("id"))

        self.add_to_query("WHERE " + " AND ".join(where_clause))

        self.return_labels = ["rl", "peer", "rels", "source_node"]

        # ----------------------------------------------------------------------------
        # FILTER Results
        # ----------------------------------------------------------------------------
        filter_cnt = 0
        for peer_filter_name, peer_filter_value in clean_filters.items():
            if "__" not in peer_filter_name:
                continue

            filter_cnt += 1

            filter_field_name, filter_next_name = peer_filter_name.split("__", maxsplit=1)

            if filter_field_name not in peer_schema.valid_input_names:
                continue

            field = peer_schema.get_field(filter_field_name)

            subquery, subquery_params, subquery_result_name = await build_subquery_filter(
                db=db,
                node_alias="peer",
                field=field,
                name=filter_field_name,
                filter_name=filter_next_name,
                filter_value=peer_filter_value,
                branch_filter=branch_filter,
                branch=self.branch,
                subquery_idx=filter_cnt,
            )
            self.params.update(subquery_params)

            with_str = ", ".join(
                [f"{subquery_result_name} as {label}" if label == "peer" else label for label in self.return_labels]
            )
            self.add_subquery(subquery=subquery, node_alias="peer", with_clause=with_str)
        # ----------------------------------------------------------------------------
        # add metadata
        # ----------------------------------------------------------------------------
        self._add_is_protected_query(branch_filter)
        self._add_has_owner_query(branch_filter)
        self._add_has_source_query(branch_filter)
        self._add_created_metadata_to_query()
        self._add_updated_metadata_to_query(branch_filter_str=branch_filter)

        self.add_to_query("WITH " + ",".join(self.return_labels))

        # ----------------------------------------------------------------------------
        # ORDER Results
        # ----------------------------------------------------------------------------
        if hasattr(peer_schema, "order_by") and peer_schema.order_by:
            order_cnt = 1

            for order_by_value in peer_schema.order_by:
                order_by_field_name, order_by_next_name = order_by_value.split("__", maxsplit=1)

                field = peer_schema.get_field(order_by_field_name)

                subquery, subquery_params, subquery_result_name = await build_subquery_order(
                    db=db,
                    field=field,
                    node_alias="peer",
                    name=order_by_field_name,
                    order_by=order_by_next_name,
                    branch_filter=branch_filter,
                    branch=self.branch,
                    subquery_idx=order_cnt,
                )
                self.order_by.append(subquery_result_name)
                self.params.update(subquery_params)

                self.add_subquery(subquery=subquery, node_alias="peer")

                order_cnt += 1

        else:
            self.order_by.append("peer.uuid")

    def get_peer_ids(self) -> list[str]:
        """Return a list of UUID of nodes associated with this relationship."""

        return [peer.peer_id for peer in self.get_peers()]

    def get_peers(self) -> Generator[RelationshipPeerData, None, None]:
        for result in self.get_results_group_by(("peer", "uuid"), ("source_node", "uuid")):
            rels = result.get("rels")
            source_node = result.get_node("source_node")
            peer_node = result.get_node("peer")

            if self.include_metadata & MetadataOptions.CREATED_AT:
                created_at_str = result.get("created_at")
                created_at = Timestamp(created_at_str) if created_at_str else None
            else:
                created_at = None
            if self.include_metadata & MetadataOptions.UPDATED_AT:
                updated_at_str = result.get("updated_at")
                updated_at = Timestamp(updated_at_str) if updated_at_str else None
            else:
                updated_at = None
            data = RelationshipPeerData(
                source_id=source_node.get("uuid"),
                source_db_id=source_node.element_id,
                source_kind=source_node.get("kind"),
                peer_id=peer_node.get("uuid"),
                peer_db_id=peer_node.element_id,
                peer_kind=peer_node.get("kind"),
                rel_node_db_id=result.get("rl").element_id,
                rel_node_id=result.get("rl").get("uuid"),
                rels=[RelData.from_db(rel) for rel in rels],
                branch=self.branch.name,
                created_at=created_at,
                created_by=result.get("created_by") if self.include_metadata & MetadataOptions.CREATED_BY else None,
                updated_at=updated_at,
                updated_by=result.get("updated_by") if self.include_metadata & MetadataOptions.UPDATED_BY else None,
                properties={},
            )

            prop, metadata_option = ("is_protected", MetadataOptions.IS_PROTECTED)
            if self.include_metadata & metadata_option:
                prop_node = result.get(prop)
                if prop_node:
                    data.properties[prop] = FlagPropertyData(
                        name=prop,
                        prop_db_id=prop_node.element_id,
                        rel=RelData.from_db(result.get(f"rel_{prop}")),
                        value=prop_node.get("value"),
                    )

            for prop, metadata_option in [("owner", MetadataOptions.OWNER), ("source", MetadataOptions.SOURCE)]:
                if not self.include_metadata & metadata_option:
                    continue
                prop_node = result.get(prop)
                if not prop_node:
                    continue
                data.properties[prop] = NodePropertyData(
                    name=prop,
                    prop_db_id=prop_node.element_id,
                    rel=RelData.from_db(result.get(f"rel_{prop}")),
                    value=prop_node.get("uuid"),
                )

                if prop == "source" and InfrahubKind.PROFILE in prop_node.labels:
                    data.is_from_profile = True
                    data.profile_id = prop_node._properties["uuid"]

            yield data


class RelationshipGetByIdentifierQuery(Query):
    name = "relationship_get_identifier"
    type = QueryType.READ

    def __init__(
        self,
        identifiers: list[str] | None = None,
        full_identifiers: list[FullRelationshipIdentifier] | None = None,
        excluded_namespaces: list[str] | None = None,
        **kwargs,
    ) -> None:
        if (not identifiers and not full_identifiers) or (identifiers and full_identifiers):
            raise ValueError("one and only one of identifiers or full_identifiers is required")

        if full_identifiers:
            self.identifiers = list({i.identifier for i in full_identifiers})
            self.full_identifiers = full_identifiers
        else:
            self.identifiers = identifiers
            self.full_identifiers = []
        self.excluded_namespaces = excluded_namespaces or []

        # Always exclude relationships with internal nodes
        if "Internal" not in self.excluded_namespaces:
            self.excluded_namespaces.append("Internal")

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:  # noqa: ARG002
        self.params["identifiers"] = self.identifiers
        self.params["full_identifiers"] = [
            [full_id.source_kind, full_id.identifier, full_id.destination_kind] for full_id in self.full_identifiers
        ]
        self.params["excluded_namespaces"] = self.excluded_namespaces
        self.params["branch"] = self.branch.name
        self.params["at"] = self.at.to_string()

        rels_filter, rels_params = self.branch.get_query_filter_relationships(
            rel_labels=["r1", "r2"], at=self.at, include_outside_parentheses=True
        )
        self.params.update(rels_params)

        query = """
        MATCH (rl:Relationship)
        WHERE rl.name IN $identifiers
        CALL (rl) {
            MATCH (src:Node)-[r1:IS_RELATED]-(rl:Relationship)-[r2:IS_RELATED]-(dst:Node)
            WHERE (size($full_identifiers) = 0 OR [src.kind, rl.name, dst.kind] in $full_identifiers)
            AND NOT src.namespace IN $excluded_namespaces
            AND NOT dst.namespace IN $excluded_namespaces
            AND %s
            RETURN src, dst, r1, r2, rl as rl1
            ORDER BY r1.branch_level DESC, r2.branch_level DESC, r1.from DESC, r2.from DESC
            LIMIT 1
        }
        WITH src, dst, r1, r2, rl1 as rl
        WHERE r1.status = "active" AND r2.status = "active"
        """ % ("\n AND ".join(rels_filter),)

        self.add_to_query(query)
        self.return_labels = ["src", "dst", "rl"]

    def get_peers(self) -> Generator[RelationshipPeersData, None, None]:
        for result in self.get_results():
            data = RelationshipPeersData(
                id=result.get("rl").get("uuid"),
                identifier=result.get("rl").get("name"),
                source_id=result.get("src").get("uuid"),
                source_kind=result.get("src").get("kind"),
                destination_id=result.get("dst").get("uuid"),
                destination_kind=result.get("dst").get("kind"),
            )
            yield data


class RelationshipCountPerNodeQuery(Query):
    name = "relationship_count_per_node"
    type: QueryType = QueryType.READ

    def __init__(
        self,
        node_ids: list[str],
        identifier: str,
        direction: RelationshipDirection,
        **kwargs,
    ):
        self.node_ids = node_ids
        self.identifier = identifier
        self.direction = direction

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        self.params["peer_ids"] = self.node_ids
        self.params["rel_identifier"] = self.identifier

        path = "-[r:IS_RELATED]-"
        if self.direction == RelationshipDirection.OUTBOUND:
            path = "-[r:IS_RELATED]->"
        elif self.direction == RelationshipDirection.INBOUND:
            path = "<-[r:IS_RELATED]-"

        query = """
        MATCH (peer_node:Node)%(path)s(rl:Relationship { name: $rel_identifier })
        WHERE peer_node.uuid IN $peer_ids AND %(branch_filter)s
        CALL (rl) {
            MATCH path = (peer_node:Node)%(path)s(rl)
            WHERE peer_node.uuid IN $peer_ids AND %(branch_filter)s
            RETURN peer_node as peer, r as r1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH peer as peer_node, r1 as r
        WHERE r.status = "active"
        """ % {"branch_filter": branch_filter, "path": path}

        self.add_to_query(query)
        self.order_by = ["peer_node.uuid"]
        self.return_labels = ["peer_node.uuid", "COUNT(peer_node.uuid) as nbr_peers"]

    async def get_count_per_peer(self) -> dict[str, int]:
        data: dict[str, int] = {}
        for result in self.results:
            data[result.get("peer_node.uuid")] = result.get("nbr_peers")

        for node_id in self.node_ids:
            if node_id not in data:
                data[node_id] = 0

        return data


class RelationshipDeleteAllQuery(Query):
    """
    Delete all relationships linked to a given node on a given branch at a given time. For every IS_RELATED edge:
    - Set `to` time if an active edge exist on the same branch.
    - Create `deleted` edge.
    - Apply above to every edges linked to any connected Relationship node.
    This query returns node uuids/kinds and corresponding relationship identifiers of deleted nodes,
    that are later used to update node changelog.
    """

    name = "node_delete_all_relationships"
    type = QueryType.WRITE
    insert_return = False

    def __init__(self, node_id: str, **kwargs):
        self.node_id = node_id
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:
        self.params["source_id"] = kwargs["node_id"]
        self.params["branch"] = self.branch.name
        self.params["user_id"] = self.user_id
        self.params["rel_prop"] = {
            "branch": self.branch.name,
            "branch_level": self.branch.hierarchy_level,
            "status": RelationshipStatus.DELETED.value,
            "from": self.at.to_string(),
            "from_user_id": self.user_id,
        }

        self.params["at"] = self.at.to_string()

        active_rel_filter, rel_params = self.branch.get_query_filter_path(
            at=self.at, variable_name="active_edge", branch_agnostic=self.branch_agnostic
        )
        self.params.update(rel_params)

        rel_match_query = """
        MATCH (s:Node { uuid: $source_id })-[active_edge:IS_RELATED]-(rl:Relationship)
        WHERE %(active_rel_filter)s AND active_edge.status = "active"
        """ % {"active_rel_filter": active_rel_filter}
        if self.branch.is_default or self.branch.is_global:
            rel_match_query += """
            SET rl.updated_at = $at, rl.updated_by = $user_id
            """
        rel_match_query += """
        WITH DISTINCT rl
        """
        self.add_to_query(rel_match_query)

        edge_types = [
            DatabaseEdgeType.IS_PROTECTED.value,
            DatabaseEdgeType.HAS_OWNER.value,
            DatabaseEdgeType.HAS_SOURCE.value,
        ]

        for arrow_left, arrow_right in (("<-", "-"), ("-", "->")):
            for edge_type in edge_types:
                sub_query = """
                    CALL (rl) {
                        MATCH (rl)%(arrow_left)s[active_edge:%(edge_type)s]%(arrow_right)s(n)
                        WHERE %(active_rel_filter)s AND active_edge.status ="active"
                        CREATE (rl)%(arrow_left)s[deleted_edge:%(edge_type)s $rel_prop]%(arrow_right)s(n)
                        SET deleted_edge.hierarchy = active_edge.hierarchy
                        WITH active_edge, n
                        WHERE active_edge.branch = $branch AND active_edge.to IS NULL
                        SET active_edge.to = $at, active_edge.to_user_id = $user_id
                    }
                """ % {
                    "arrow_left": arrow_left,
                    "arrow_right": arrow_right,
                    "active_rel_filter": active_rel_filter,
                    "edge_type": edge_type,
                }

                self.add_to_query(sub_query)

        # We only want to return uuid/kind of `Node` connected through `IS_RELATED` edges.
        peer_node_metadata_update = ""
        if self.branch.is_default or self.branch.is_global:
            peer_node_metadata_update = "SET n.updated_at = $at, n.updated_by = $user_id"

        query = """
        CALL (rl) {
            MATCH (rl)-[active_edge:IS_RELATED]->(n)
            WHERE %(active_rel_filter)s
            WITH rl, active_edge, n
            ORDER BY %(id_func)s(rl), %(id_func)s(n), active_edge.from DESC
            WITH rl, n, head(collect(active_edge)) AS active_edge
            WHERE active_edge.status = "active"
            CREATE (rl)-[deleted_edge:IS_RELATED $rel_prop]->(n)
            SET deleted_edge.hierarchy = active_edge.hierarchy
            %(peer_node_metadata_update)s
            WITH rl, active_edge, n
            WHERE active_edge.branch = $branch AND active_edge.to IS NULL
            SET active_edge.to = $at, active_edge.to_user_id = $user_id
            RETURN
                n.uuid as uuid,
                n.kind as kind,
                rl.name as rel_identifier,
                "outbound" as rel_direction

            UNION
            WITH rl
            MATCH (rl)<-[active_edge:IS_RELATED]-(n)
            WHERE %(active_rel_filter)s
            WITH rl, active_edge, n
            ORDER BY %(id_func)s(rl), %(id_func)s(n), active_edge.from DESC
            WITH rl, n, head(collect(active_edge)) AS active_edge
            WHERE active_edge.status = "active"
            CREATE (rl)<-[deleted_edge:IS_RELATED $rel_prop]-(n)
            SET deleted_edge.hierarchy = active_edge.hierarchy
            %(peer_node_metadata_update)s
            WITH rl, active_edge, n
            WHERE active_edge.branch = $branch AND active_edge.to IS NULL
            SET active_edge.to = $at, active_edge.to_user_id = $user_id
            RETURN
                n.uuid as uuid,
                n.kind as kind,
                rl.name as rel_identifier,
                "inbound" as rel_direction
        }
        RETURN DISTINCT uuid, kind, rel_identifier, rel_direction
        """ % {
            "active_rel_filter": active_rel_filter,
            "id_func": db.get_id_function_name(),
            "peer_node_metadata_update": peer_node_metadata_update,
        }
        self.add_to_query(query)

    def get_deleted_relationships_changelog(
        self, node_schema: NodeSchema
    ) -> list[RelationshipCardinalityOneChangelog | RelationshipCardinalityManyChangelog]:
        rel_identifier_to_changelog_mapper = {}

        for result in self.get_results():
            peer_uuid = result.data["uuid"]
            if peer_uuid == self.node_id:
                continue

            rel_identifier = result.data["rel_identifier"]
            kind = result.data["kind"]
            deleted_rel_schemas = [
                rel_schema for rel_schema in node_schema.relationships if rel_schema.identifier == rel_identifier
            ]

            if len(deleted_rel_schemas) == 0:
                continue  # TODO Unidirectional relationship changelog should be handled, cf IFC-1319.

            if len(deleted_rel_schemas) > 2:
                log.error(f"Duplicated relationship schema with identifier {rel_identifier}")
                continue

            if len(deleted_rel_schemas) == 2:
                # Hierarchical schema nodes have 2 relationships with `parent_child` identifiers,
                # which are differentiated by their direction within the database.
                # assert rel_identifier != PARENT_CHILD_IDENTIFIER

                rel_direction = result.data["rel_direction"]
                deleted_rel_schema = (
                    deleted_rel_schemas[0]
                    if deleted_rel_schemas[0].direction.value == rel_direction
                    else deleted_rel_schemas[1]
                )
            else:
                deleted_rel_schema = deleted_rel_schemas[0]

            try:
                changelog_mapper = rel_identifier_to_changelog_mapper[rel_identifier]
            except KeyError:
                changelog_mapper = ChangelogRelationshipMapper(schema=deleted_rel_schema)
                rel_identifier_to_changelog_mapper[rel_identifier] = changelog_mapper

            changelog_mapper.delete_relationship(peer_id=peer_uuid, peer_kind=kind, rel_schema=deleted_rel_schema)

        return [changelog_mapper.changelog for changelog_mapper in rel_identifier_to_changelog_mapper.values()]


class GetAllPeersIds(Query):
    """
    Return all peers ids connected to input node. Some peers can be excluded using `exclude_identifiers`.
    """

    name = "get_peers_ids"
    type: QueryType = QueryType.READ
    insert_return = False

    def __init__(self, node_id: str, exclude_identifiers: list[str], **kwargs):
        self.node_id = node_id
        self.exclude_identifiers = exclude_identifiers
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:  # noqa: ARG002
        self.params["source_id"] = kwargs["node_id"]
        self.params["branch"] = self.branch.name
        self.params["exclude_identifiers"] = self.exclude_identifiers

        active_rel_filter, rel_params = self.branch.get_query_filter_path(
            at=self.at, variable_name="e1", branch_agnostic=self.branch_agnostic
        )
        self.params.update(rel_params)

        query = """
            MATCH (node:Node { uuid: $source_id })-[e1:IS_RELATED]-(rl:Relationship)-[e2:IS_RELATED]-(peer:Node)
            WHERE %(active_rel_filter)s AND peer.uuid <> node.uuid AND NOT (rl.name IN $exclude_identifiers)
            WITH DISTINCT(peer.uuid) as uuid
            RETURN uuid
        """ % {"active_rel_filter": active_rel_filter}

        self.add_to_query(query)

    def get_peers_uuids(self) -> list[str]:
        return [row.data["uuid"] for row in self.results]  # type: ignore
