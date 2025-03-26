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
from infrahub.core.constants import RelationshipDirection, RelationshipStatus
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

    peer_id: UUID
    """UUID of the Peer Node."""

    peer_kind: str
    """Kind of the Peer Node."""

    properties: dict[str, FlagPropertyData | NodePropertyData]
    """UUID of the Relationship Node."""

    rel_node_id: UUID | None = None
    """UUID of the Relationship Node."""

    peer_db_id: str | None = None
    """Internal DB ID of the Peer Node."""

    rel_node_db_id: str | None = None
    """Internal DB ID of the Relationship Node."""

    rels: list[RelData] | None = None
    """Both relationships pointing at this Relationship Node."""

    updated_at: str | None = None

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
        rel_type: str | None = None,
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
        if not rel and not rel_type:
            raise ValueError("Either rel or rel_type must be provided.")
        if not inspect.isclass(rel) and not hasattr(rel, "schema"):
            raise ValueError("Rel must be a Relationship class or an instance of Relationship.")
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
        self.rel_type = rel_type or self.rel.rel_type
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

    def get_relationship_properties_dict(self, status: RelationshipStatus) -> dict[str, str | None]:
        rel_prop_dict = {
            "branch": self.branch.name,
            "branch_level": self.branch.hierarchy_level,
            "status": status.value,
            "from": self.at.to_string(),
        }
        if self.schema.hierarchical:
            rel_prop_dict["hierarchy"] = self.schema.hierarchical
        return rel_prop_dict


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
        self.params["source_id"] = self.source_id
        self.params["destination_id"] = self.destination_id
        self.params["name"] = self.schema.identifier
        self.params["branch_support"] = self.schema.branch.value

        self.params["uuid"] = str(UUIDT())

        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["at"] = self.at.to_string()

        self.params["is_protected"] = self.rel.is_protected
        self.params["is_visible"] = self.rel.is_visible

        query_match = """
        MATCH (s:Node { uuid: $source_id })
        MATCH (d:Node { uuid: $destination_id })
        """
        self.add_to_query(query_match)

        self.query_add_all_node_property_match()

        self.params["rel_prop"] = self.get_relationship_properties_dict(status=RelationshipStatus.ACTIVE)
        arrows = self.schema.get_query_arrows()
        r1 = f"{arrows.left.start}[r1:{self.rel_type} $rel_prop ]{arrows.left.end}"
        r2 = f"{arrows.right.start}[r2:{self.rel_type} $rel_prop ]{arrows.right.end}"

        query_create = """
        CREATE (rl:Relationship { uuid: $uuid, name: $name, branch_support: $branch_support })
        CREATE (s)%s(rl)
        CREATE (rl)%s(d)
        MERGE (ip:Boolean { value: $is_protected })
        MERGE (iv:Boolean { value: $is_visible })
        CREATE (rl)-[r3:IS_PROTECTED $rel_prop ]->(ip)
        CREATE (rl)-[r4:IS_VISIBLE $rel_prop ]->(iv)
        """ % (
            r1,
            r2,
        )

        self.add_to_query(query_create)
        self.return_labels = ["s", "d", "rl", "r1", "r2", "r3", "r4"]
        self.query_add_all_node_property_create()

    def query_add_all_node_property_match(self) -> None:
        for prop_name in self.rel._node_properties:
            if hasattr(self.rel, f"{prop_name}_id") and getattr(self.rel, f"{prop_name}_id"):
                self.query_add_node_property_match(name=prop_name)

    def query_add_node_property_match(self, name: str) -> None:
        self.add_to_query("MATCH (%s { uuid: $prop_%s_id })" % (name, name))
        self.params[f"prop_{name}_id"] = getattr(self.rel, f"{name}_id")
        self.return_labels.append(name)

    def query_add_all_node_property_create(self) -> None:
        for prop_name in self.rel._node_properties:
            if hasattr(self.rel, f"{prop_name}_id") and getattr(self.rel, f"{prop_name}_id"):
                self.query_add_node_property_create(name=prop_name)

    def query_add_node_property_create(self, name: str) -> None:
        query = """
        CREATE (rl)-[:HAS_%s { branch: $branch, branch_level: $branch_level, status: "active", from: $at }]->(%s)
        """ % (
            name.upper(),
            name,
        )
        self.add_to_query(query)


class RelationshipUpdatePropertyQuery(RelationshipQuery):
    name = "relationship_property_update"
    type = QueryType.WRITE

    def __init__(
        self,
        properties_to_update: list[str],
        data: RelationshipPeerData,
        **kwargs,
    ):
        self.properties_to_update = properties_to_update
        self.data = data

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:  # noqa: ARG002
        self.params["rel_node_id"] = self.data.rel_node_id
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["at"] = self.at.to_string()

        query = """
        MATCH (rl:Relationship { uuid: $rel_node_id })
        """
        self.add_to_query(query)

        self.query_add_all_flag_property_merge()
        self.query_add_all_node_property_merge()

        self.query_add_all_flag_property_create()
        self.query_add_all_node_property_create()

    def query_add_all_flag_property_merge(self) -> None:
        for prop_name in self.rel._flag_properties:
            if prop_name in self.properties_to_update:
                self.query_add_flag_property_merge(name=prop_name)

    def query_add_flag_property_merge(self, name: str) -> None:
        self.add_to_query("MERGE (prop_%s:Boolean { value: $prop_%s })" % (name, name))
        self.params[f"prop_{name}"] = getattr(self.rel, name)
        self.return_labels.append(f"prop_{name}")

    def query_add_all_node_property_merge(self) -> None:
        for prop_name in self.rel._node_properties:
            if prop_name in self.properties_to_update:
                self.query_add_node_property_merge(name=prop_name)

    def query_add_node_property_merge(self, name: str) -> None:
        self.add_to_query("MERGE (prop_%s:Node { uuid: $prop_%s })" % (name, name))
        self.params[f"prop_{name}"] = getattr(self.rel, f"{name}_id")
        self.return_labels.append(f"prop_{name}")

    def query_add_all_flag_property_create(self) -> None:
        for prop_name in self.rel._flag_properties:
            if prop_name in self.properties_to_update:
                self.query_add_flag_property_create(name=prop_name)

    def query_add_flag_property_create(self, name: str) -> None:
        query = """
        CREATE (rl)-[:%s { branch: $branch, branch_level: $branch_level, status: "active", from: $at }]->(prop_%s)
        """ % (
            name.upper(),
            name,
        )
        self.add_to_query(query)

    def query_add_all_node_property_create(self) -> None:
        for prop_name in self.rel._node_properties:
            if prop_name in self.properties_to_update:
                self.query_add_node_property_create(name=prop_name)

    def query_add_node_property_create(self, name: str) -> None:
        query = """
        CREATE (rl)-[:%s { branch: $branch, branch_level: $branch_level, status: "active", from: $at }]->(prop_%s)
        """ % (
            "HAS_" + name.upper(),
            name,
        )
        self.add_to_query(query)


class RelationshipDataDeleteQuery(RelationshipQuery):
    name = "relationship_data_delete"
    type = QueryType.WRITE

    def __init__(
        self,
        data: RelationshipPeerData,
        **kwargs,
    ):
        self.data = data
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:  # noqa: ARG002
        self.params["source_id"] = self.source_id
        self.params["destination_id"] = self.data.peer_id
        self.params["rel_node_id"] = self.data.rel_node_id
        self.params["name"] = self.schema.identifier
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["at"] = self.at.to_string()

        # -----------------------------------------------------------------------
        # Match all nodes, including properties
        # -----------------------------------------------------------------------
        query = """
        MATCH (s:Node { uuid: $source_id })
        MATCH (d:Node { uuid: $destination_id })
        MATCH (rl:Relationship { uuid: $rel_node_id })
        """
        self.add_to_query(query)
        self.return_labels = ["s", "d", "rl"]

        for prop_name, prop in self.data.properties.items():
            self.add_to_query(
                "MATCH (prop_%(prop_name)s) WHERE %(id_func)s(prop_%(prop_name)s) = $prop_%(prop_name)s_id"
                % {"prop_name": prop_name, "id_func": db.get_id_function_name()}
            )
            self.params[f"prop_{prop_name}_id"] = db.to_database_id(prop.prop_db_id)
            self.return_labels.append(f"prop_{prop_name}")

        self.params["rel_prop"] = self.get_relationship_properties_dict(status=RelationshipStatus.DELETED)

        arrows = self.schema.get_query_arrows()
        r1 = f"{arrows.left.start}[r1:{self.rel_type} $rel_prop ]{arrows.left.end}"
        r2 = f"{arrows.right.start}[r2:{self.rel_type} $rel_prop ]{arrows.right.end}"

        # -----------------------------------------------------------------------
        # Create all the DELETE relationships, including properties
        # -----------------------------------------------------------------------
        query = """
        CREATE (s)%s(rl)
        CREATE (rl)%s(d)
        """ % (
            r1,
            r2,
        )
        self.add_to_query(query)
        self.return_labels.extend(["r1", "r2"])

        for prop_name, prop in self.data.properties.items():
            self.add_to_query(
                "CREATE (prop_%s)<-[rel_prop_%s:%s $rel_prop ]-(rl)" % (prop_name, prop_name, prop.rel.type),
            )
            self.return_labels.append(f"rel_prop_{prop_name}")


class RelationshipDeleteQuery(RelationshipQuery):
    name = "relationship_delete"
    type = QueryType.WRITE

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if inspect.isclass(self.rel):
            raise TypeError("An instance of Relationship must be provided to RelationshipDeleteQuery")

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:  # noqa: ARG002
        rel_filter, rel_params = self.branch.get_query_filter_path(at=self.at, variable_name="edge")
        self.params["source_id"] = self.source_id
        self.params["destination_id"] = self.destination_id
        self.params["rel_id"] = self.rel.id
        self.params["branch"] = self.branch.name
        self.params["rel_prop"] = self.get_relationship_properties_dict(status=RelationshipStatus.DELETED)
        self.params["at"] = self.at.to_string()
        self.params.update(rel_params)

        arrows = self.schema.get_query_arrows()
        r1 = f"{arrows.left.start}[r1:{self.rel_type} $rel_prop ]{arrows.left.end}"
        r2 = f"{arrows.right.start}[r2:{self.rel_type} $rel_prop ]{arrows.right.end}"

        query = """
        MATCH (s:Node { uuid: $source_id })-[:IS_RELATED]-(rl:Relationship {uuid: $rel_id})-[:IS_RELATED]-(d:Node { uuid: $destination_id })
        WITH s, rl, d
        LIMIT 1
        CREATE (s)%(r1)s(rl)
        CREATE (rl)%(r2)s(d)
        WITH rl
        CALL {
            WITH rl
            MATCH (rl)-[edge:IS_VISIBLE]->(visible)
            WHERE %(rel_filter)s AND edge.status = "active"
            WITH rl, edge, visible
            ORDER BY edge.branch_level DESC
            LIMIT 1
            CREATE (rl)-[deleted_edge:IS_VISIBLE $rel_prop]->(visible)
            WITH edge
            WHERE edge.branch = $branch
            SET edge.to = $at
        }
        CALL {
            WITH rl
            MATCH (rl)-[edge:IS_PROTECTED]->(protected)
            WHERE %(rel_filter)s AND edge.status = "active"
            WITH rl, edge, protected
            ORDER BY edge.branch_level DESC
            LIMIT 1
            CREATE (rl)-[deleted_edge:IS_PROTECTED $rel_prop]->(protected)
            WITH edge
            WHERE edge.branch = $branch
            SET edge.to = $at
        }
        CALL {
            WITH rl
            MATCH (rl)-[edge:HAS_OWNER]->(owner_node)
            WHERE %(rel_filter)s AND edge.status = "active"
            WITH rl, edge, owner_node
            ORDER BY edge.branch_level DESC
            LIMIT 1
            CREATE (rl)-[deleted_edge:HAS_OWNER $rel_prop]->(owner_node)
            WITH edge
            WHERE edge.branch = $branch
            SET edge.to = $at
        }
        CALL {
            WITH rl
            MATCH (rl)-[edge:HAS_SOURCE]->(source_node)
            WHERE %(rel_filter)s AND edge.status = "active"
            WITH rl, edge, source_node
            ORDER BY edge.branch_level DESC
            LIMIT 1
            CREATE (rl)-[deleted_edge:HAS_SOURCE $rel_prop]->(source_node)
            WITH edge
            WHERE edge.branch = $branch
            SET edge.to = $at
        }
        """ % {"r1": r1, "r2": r2, "rel_filter": rel_filter}

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

        if not branch and inspect.isclass(rel) and not hasattr(rel, "branch"):
            raise ValueError("Either an instance of Relationship or a valid branch must be provided.")

        self.branch = branch or self.rel.branch

        if not at and inspect.isclass(rel) and hasattr(rel, "at"):
            self.at = self.rel.at
        else:
            self.at = Timestamp(at)

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at, branch_agnostic=self.branch_agnostic
        )
        self.params.update(branch_params)
        self.order_by = []

        peer_schema = self.schema.get_peer_schema(db=db, branch=self.branch)

        self.params["source_ids"] = self.source_ids
        self.params["rel_identifier"] = self.schema.identifier
        self.params["peer_kind"] = self.schema.peer
        self.params["source_kind"] = self.source_kind

        arrows = self.schema.get_query_arrows()

        path_str = (
            f"{arrows.left.start}[:IS_RELATED]{arrows.left.end}(rl){arrows.right.start}[:IS_RELATED]{arrows.right.end}"
        )

        branch_level_str = "reduce(br_lvl = 0, r in relationships(path) | br_lvl + r.branch_level)"
        froms_str = db.render_list_comprehension(items="relationships(path)", item_name="from")
        query = """
        MATCH (source_node:Node)%(arrow_left_start)s[:IS_RELATED]%(arrow_left_end)s(rl:Relationship { name: $rel_identifier })
        WHERE source_node.uuid IN $source_ids
        WITH DISTINCT source_node, rl
        CALL {
            WITH rl, source_node
            MATCH path = (source_node)%(path)s(peer:Node)
            WHERE
                $source_kind IN LABELS(source_node) AND
                peer.uuid <> source_node.uuid AND
                $peer_kind IN LABELS(peer) AND
                all(r IN relationships(path) WHERE (%(branch_filter)s))
            WITH source_node, peer, rl, relationships(path) as rels, %(branch_level)s AS branch_level, %(froms)s AS froms
            RETURN peer as peer, rels, rl as rl1
            ORDER BY branch_level DESC, froms[-1] DESC, froms[-2] DESC
            LIMIT 1
        }
        WITH peer, rl1 as rl, rels, source_node
        """ % {
            "path": path_str,
            "branch_filter": branch_filter,
            "branch_level": branch_level_str,
            "froms": froms_str,
            "arrow_left_start": arrows.left.start,
            "arrow_left_end": arrows.left.end,
        }

        self.add_to_query(query)
        where_clause = ['all(r IN rels WHERE r.status = "active")']
        clean_filters = extract_field_filters(field_name=self.schema.name, filters=self.filters)

        if clean_filters and "id" in clean_filters or "ids" in clean_filters:
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
            self.add_subquery(subquery=subquery, with_clause=with_str)

        # ----------------------------------------------------------------------------
        # QUERY Properties
        # ----------------------------------------------------------------------------
        query = """
        CALL {
            WITH rl
            MATCH (rl)-[r:IS_VISIBLE]-(is_visible)
            WHERE %(branch_filter)s
            RETURN r AS rel_is_visible, is_visible
            ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
            LIMIT 1
        }
        CALL {
            WITH rl
            MATCH (rl)-[r:IS_PROTECTED]-(is_protected)
            WHERE %(branch_filter)s
            RETURN r AS rel_is_protected, is_protected
            ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
            LIMIT 1
        }
        """ % {"branch_filter": branch_filter}

        self.add_to_query(query)

        self.update_return_labels(["rel_is_visible", "rel_is_protected", "is_visible", "is_protected"])

        # Add Node Properties
        # We must query them one by one otherwise the second one won't return
        for node_prop in ["source", "owner"]:
            query = """
        CALL {
            WITH rl
            OPTIONAL MATCH (rl)-[r:HAS_%(node_prop_type)s]-(%(node_prop)s)
            WHERE %(branch_filter)s
            RETURN r AS rel_%(node_prop)s, %(node_prop)s
            ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
            LIMIT 1
        }
            """ % {
                "node_prop": node_prop,
                "node_prop_type": node_prop.upper(),
                "branch_filter": branch_filter,
            }
            self.add_to_query(query)
            self.update_return_labels([f"rel_{node_prop}", node_prop])

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

                self.add_subquery(subquery=subquery)

                order_cnt += 1

        else:
            self.order_by.append("peer.uuid")

    def get_peer_ids(self) -> list[str]:
        """Return a list of UUID of nodes associated with this relationship."""

        return [peer.peer_id for peer in self.get_peers()]

    def get_peers(self) -> Generator[RelationshipPeerData, None, None]:
        for result in self.get_results_group_by(("peer", "uuid"), ("source_node", "uuid")):
            rels = result.get("rels")
            data = RelationshipPeerData(
                source_id=result.get_node("source_node").get("uuid"),
                peer_id=result.get_node("peer").get("uuid"),
                peer_kind=result.get_node("peer").get("kind"),
                rel_node_db_id=result.get("rl").element_id,
                rel_node_id=result.get("rl").get("uuid"),
                updated_at=rels[0]["from"],
                rels=[RelData.from_db(rel) for rel in rels],
                branch=self.branch.name,
                properties={},
            )

            if hasattr(self.rel, "_flag_properties"):
                for prop in self.rel._flag_properties:
                    if prop_node := result.get(prop):
                        data.properties[prop] = FlagPropertyData(
                            name=prop,
                            prop_db_id=prop_node.element_id,
                            rel=RelData.from_db(result.get(f"rel_{prop}")),
                            value=prop_node.get("value"),
                        )

            if hasattr(self.rel, "_node_properties"):
                for prop in self.rel._node_properties:
                    if prop_node := result.get(prop):
                        data.properties[prop] = NodePropertyData(
                            name=prop,
                            prop_db_id=prop_node.element_id,
                            rel=RelData.from_db(result.get(f"rel_{prop}")),
                            value=prop_node.get("uuid"),
                        )

            yield data


class RelationshipGetQuery(RelationshipQuery):
    name = "relationship_get"

    type: QueryType = QueryType.READ

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:  # noqa: ARG002
        self.params["source_id"] = self.source_id
        self.params["destination_id"] = self.destination_id
        self.params["name"] = self.schema.identifier
        self.params["branch"] = self.branch.name

        rels_filter, rels_params = self.branch.get_query_filter_relationships(
            rel_labels=["r1", "r2"], at=self.at.to_string(), include_outside_parentheses=True
        )

        self.params.update(rels_params)

        arrows = self.schema.get_query_arrows()
        r1 = f"{arrows.left.start}[r1:{self.rel.rel_type}]{arrows.left.end}"
        r2 = f"{arrows.right.start}[r2:{self.rel.rel_type}]{arrows.right.end}"

        query = """
        MATCH (s:Node { uuid: $source_id })
        MATCH (d:Node { uuid: $destination_id })
        MATCH (s)%s(rl:Relationship { name: $name })%s(d)
        WHERE %s
        """ % (
            r1,
            r2,
            "\n AND ".join(rels_filter),
        )

        self.params["at"] = self.at.to_string()

        self.add_to_query(query)
        self.return_labels = ["s", "d", "rl", "r1", "r2"]


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
            rel_labels=["r1", "r2"], at=self.at.to_string(), include_outside_parentheses=True
        )
        self.params.update(rels_params)

        query = """
        MATCH (rl:Relationship)
        WHERE rl.name IN $identifiers
        CALL {
            WITH rl
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
        CALL {
            WITH rl
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

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:  # noqa: ARG002
        self.params["source_id"] = kwargs["node_id"]
        self.params["branch"] = self.branch.name

        self.params["rel_prop"] = {
            "branch": self.branch.name,
            "branch_level": self.branch.hierarchy_level,
            "status": RelationshipStatus.DELETED.value,
            "from": self.at.to_string(),
        }

        self.params["at"] = self.at.to_string()

        active_rel_filter, rel_params = self.branch.get_query_filter_path(
            at=self.at, variable_name="active_edge", branch_agnostic=self.branch_agnostic
        )
        self.params.update(rel_params)

        query = """
        MATCH (s:Node { uuid: $source_id })-[active_edge:IS_RELATED]-(rl:Relationship)
        WHERE %(active_rel_filter)s AND active_edge.status = "active"
        WITH DISTINCT rl
        """ % {"active_rel_filter": active_rel_filter}

        edge_types = [
            DatabaseEdgeType.IS_VISIBLE.value,
            DatabaseEdgeType.IS_PROTECTED.value,
            DatabaseEdgeType.HAS_OWNER.value,
            DatabaseEdgeType.HAS_SOURCE.value,
        ]

        for arrow_left, arrow_right in (("<-", "-"), ("-", "->")):
            for edge_type in edge_types:
                sub_query = """
                    CALL {
                        WITH rl
                        MATCH (rl)%(arrow_left)s[active_edge:%(edge_type)s]%(arrow_right)s(n)
                        WHERE %(active_rel_filter)s AND active_edge.status ="active"
                        CREATE (rl)%(arrow_left)s[deleted_edge:%(edge_type)s $rel_prop]%(arrow_right)s(n)
                        SET deleted_edge.hierarchy = active_edge.hierarchy
                        WITH active_edge, n
                        WHERE active_edge.branch = $branch AND active_edge.to IS NULL
                        SET active_edge.to = $at
                    }
                """ % {
                    "arrow_left": arrow_left,
                    "arrow_right": arrow_right,
                    "active_rel_filter": active_rel_filter,
                    "edge_type": edge_type,
                }

                query += sub_query

        # We only want to return uuid/kind of `Node` connected through `IS_RELATED` edges.
        query += """
        CALL {
            WITH rl
            MATCH (rl)-[active_edge:IS_RELATED]->(n)
            WHERE %(active_rel_filter)s AND active_edge.status ="active"
            CREATE (rl)-[deleted_edge:IS_RELATED $rel_prop]->(n)
            SET deleted_edge.hierarchy = active_edge.hierarchy
            WITH rl, active_edge, n
            WHERE active_edge.branch = $branch AND active_edge.to IS NULL
            SET active_edge.to = $at
            RETURN
                n.uuid as uuid,
                n.kind as kind,
                rl.name as rel_identifier,
                "outbound" as rel_direction

            UNION

            WITH rl
            MATCH (rl)<-[active_edge:IS_RELATED]-(n)
            WHERE %(active_rel_filter)s AND active_edge.status ="active"
            CREATE (rl)<-[deleted_edge:IS_RELATED $rel_prop]-(n)
            SET deleted_edge.hierarchy = active_edge.hierarchy
            WITH rl, active_edge, n
            WHERE active_edge.branch = $branch AND active_edge.to IS NULL
            SET active_edge.to = $at
            RETURN
                n.uuid as uuid,
                n.kind as kind,
                rl.name as rel_identifier,
                "inbound" as rel_direction
        }
        RETURN DISTINCT uuid, kind, rel_identifier, rel_direction
        """ % {
            "active_rel_filter": active_rel_filter,
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
