from __future__ import annotations

import contextlib
from collections import defaultdict
from copy import copy
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from enum import Enum
from typing import TYPE_CHECKING, Any, AsyncIterator, Generator

from infrahub import config
from infrahub.core import registry
from infrahub.core.constants import (
    GLOBAL_BRANCH_NAME,
    PROFILE_NODE_RELATIONSHIP_IDENTIFIER,
    PROFILE_TEMPLATE_RELATIONSHIP_IDENTIFIER,
    AttributeDBNodeType,
    MetadataOptions,
    RelationshipDirection,
    RelationshipHierarchyDirection,
)
from infrahub.core.query import Query, QueryResult, QueryType
from infrahub.core.query.subquery import build_subquery_filter, build_subquery_order
from infrahub.core.query.utils import find_node_schema
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import build_regex_attrs, extract_field_filters
from infrahub.exceptions import QueryError
from infrahub.graphql.models import OrderModel

if TYPE_CHECKING:
    from neo4j.graph import Node as Neo4jNode

    from infrahub.core.attribute import AttributeCreateData, BaseAttribute
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.relationship import RelationshipCreateData, RelationshipManager
    from infrahub.core.schema import GenericSchema, NodeSchema
    from infrahub.core.schema.profile_schema import ProfileSchema
    from infrahub.core.schema.relationship_schema import RelationshipSchema
    from infrahub.core.schema.template_schema import TemplateSchema
    from infrahub.database import InfrahubDatabase


@dataclass
class NodeToProcess:
    schema: NodeSchema | ProfileSchema | TemplateSchema | None

    labels: list[str]
    node_id: str
    node_uuid: str
    branch: str

    created_at: Timestamp | None = None
    created_by: str | None = None
    updated_at: Timestamp | None = None
    updated_by: str | None = None


@dataclass
class AttributeNodePropertyFromDB:
    uuid: str
    labels: list[str]


@dataclass
class AttributeFromDB:
    name: str

    attr_labels: list[str]
    attr_id: str
    attr_uuid: str

    attr_value_id: str
    attr_value_uuid: str | None

    value: Any
    content: Any

    branch: str

    is_default: bool
    is_from_profile: bool = dataclass_field(default=False)

    updated_at: Timestamp | None = None
    updated_by: str | None = None
    created_at: Timestamp | None = None
    created_by: str | None = None

    node_properties: dict[str, AttributeNodePropertyFromDB] = dataclass_field(default_factory=dict)
    flag_properties: dict[str, bool] = dataclass_field(default_factory=dict)


@dataclass
class NodeAttributesFromDB:
    node: Neo4jNode
    attrs: dict[str, AttributeFromDB] = dataclass_field(default_factory=dict)


@dataclass
class PeerInfo:
    uuid: str
    kind: str
    db_id: str


class NodeQuery(Query):
    def __init__(
        self,
        user_id: str,
        node: Node | None = None,
        node_id: str | None = None,
        node_db_id: int | None = None,
        id: str | None = None,
        branch: Branch | None = None,
        **kwargs,
    ) -> None:
        self.user_id = user_id
        self.node = node
        self.node_id = node_id or id
        self.node_db_id = node_db_id

        if not self.node_id and self.node:
            self.node_id = self.node.id

        if not self.node_db_id and self.node:
            self.node_db_id = self.node.db_id

        self.branch = branch or self.node.get_branch_based_on_support_type()

        super().__init__(**kwargs)


class NodeCreateAllQuery(NodeQuery):
    name = "node_create_all"
    type = QueryType.WRITE

    raise_error_if_empty: bool = True

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:  # noqa: ARG002, PLR0915
        at = self.at or self.node._at
        self.params["user_id"] = self.user_id
        self.params["uuid"] = self.node.id
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["kind"] = self.node.get_kind()
        self.params["branch_support"] = self.node._schema.branch

        attributes: list[AttributeCreateData] = []
        attributes_iphost: list[AttributeCreateData] = []
        attributes_ipnetwork: list[AttributeCreateData] = []
        attributes_indexed: list[AttributeCreateData] = []

        if self.node.has_display_label():
            attributes_indexed.append(
                self.node._display_label.get_node_attribute(node=self.node, at=at).get_create_data(
                    node_schema=self.node.get_schema()
                )
            )
        if self.node.has_human_friendly_id():
            attributes_indexed.append(
                self.node._human_friendly_id.get_node_attribute(node=self.node, at=at).get_create_data(
                    node_schema=self.node.get_schema()
                )
            )

        for attr_name in self.node._attributes:
            attr: BaseAttribute = getattr(self.node, attr_name)
            attr_data = attr.get_create_data(node_schema=self.node.get_schema())
            node_type = attr.get_db_node_type()

            if AttributeDBNodeType.IPHOST in node_type:
                attributes_iphost.append(attr_data)
            elif AttributeDBNodeType.IPNETWORK in node_type:
                attributes_ipnetwork.append(attr_data)
            elif AttributeDBNodeType.INDEXED in node_type:
                attributes_indexed.append(attr_data)
            else:
                attributes.append(attr_data)

        deepest_branch_name = self.branch.name
        deepest_branch_level = self.branch.hierarchy_level
        relationships: list[RelationshipCreateData] = []
        for rel_name in self.node._relationships:
            rel_manager: RelationshipManager = getattr(self.node, rel_name)
            if rel_manager.schema.cardinality == "many":
                # Fetch all relationship peers through a single database call for performances.
                peers = await rel_manager.get_peers(db=db, branch_agnostic=self.branch_agnostic)

            for rel in rel_manager._relationships:
                if rel_manager.schema.cardinality == "many":
                    try:
                        rel.set_peer(value=peers[rel.get_peer_id()])
                    except KeyError:
                        pass
                    except ValueError:
                        # Relationship has not been initialized yet, it means the peer does not exist in db yet
                        # typically because it will be allocated from a resource pool. In that case, the peer
                        # will be fetched using `rel.resolve` later.
                        pass

                rel_create_data = await rel.get_create_data(db=db, at=at)
                if rel_create_data.peer_branch_level > deepest_branch_level or (
                    deepest_branch_name == GLOBAL_BRANCH_NAME and rel_create_data.peer_branch == registry.default_branch
                ):
                    deepest_branch_name = rel_create_data.peer_branch
                    deepest_branch_level = rel_create_data.peer_branch_level
                relationships.append(rel_create_data)

        self.params["attrs"] = [attr.model_dump() for attr in attributes]
        self.params["attrs_indexed"] = [attr.model_dump() for attr in attributes_indexed]
        self.params["attrs_iphost"] = [attr.model_dump() for attr in attributes_iphost]
        self.params["attrs_ipnetwork"] = [attr.model_dump() for attr in attributes_ipnetwork]
        self.params["rels_bidir"] = [
            rel.model_dump() for rel in relationships if rel.direction == RelationshipDirection.BIDIR.value
        ]
        self.params["rels_out"] = [
            rel.model_dump() for rel in relationships if rel.direction == RelationshipDirection.OUTBOUND.value
        ]
        self.params["rels_in"] = [
            rel.model_dump() for rel in relationships if rel.direction == RelationshipDirection.INBOUND.value
        ]

        self.params["node_prop"] = {
            "uuid": self.node.id,
            "kind": self.node.get_kind(),
            "namespace": self.node._schema.namespace,
            "branch_support": self.node._schema.branch,
        }
        if self.branch.is_default or self.branch.is_global:
            self.params["node_prop"].update(
                {
                    "created_at": at.to_string(),
                    "created_by": self.user_id,
                    "updated_at": at.to_string(),
                    "updated_by": self.user_id,
                }
            )
        self.params["node_branch_prop"] = {
            "branch": self.branch.name,
            "branch_level": self.branch.hierarchy_level,
            "status": "active",
            "from": at.to_string(),
            "from_user_id": self.user_id,
        }

        # set all the property strings that we reuse
        # include the create/updated_at/by metadata if on default or global branch
        attr_edge_prop_str = "{ branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at, from_user_id: $user_id }"
        attr_vertex_prop_str = "{ uuid: attr.uuid, name: attr.name, branch_support: attr.branch_support"
        if self.branch.is_default or self.branch.is_global:
            attr_vertex_prop_str += ", created_at: $at, created_by: $user_id, updated_at: $at, updated_by: $user_id"
        attr_vertex_prop_str += " }"

        rel_edge_prop_str = "{ branch: rel.branch, branch_level: rel.branch_level, status: rel.status, from: $at, from_user_id: $user_id }"
        rel_edge_prop_str_hierarchy = (
            "{ branch: rel.branch, branch_level: rel.branch_level, "
            "status: rel.status, hierarchy: rel.hierarchical, from: $at, from_user_id: $user_id }"
        )
        rel_vertex_prop_str = "{ uuid: rel.uuid, name: rel.name, branch_support: rel.branch_support"
        if self.branch.is_default or self.branch.is_global:
            rel_vertex_prop_str += ", created_at: $at, created_by: $user_id, updated_at: $at, updated_by: $user_id"
        rel_vertex_prop_str += " }"

        iphost_prop = {
            "value": "attr.content.value",
            "is_default": "attr.content.is_default",
            "binary_address": "attr.content.binary_address",
            "version": "attr.content.version",
            "prefixlen": "attr.content.prefixlen",
        }
        iphost_prop_list = [f"{key}: {value}" for key, value in iphost_prop.items()]

        ipnetwork_prop = {
            "value": "attr.content.value",
            "is_default": "attr.content.is_default",
            "binary_address": "attr.content.binary_address",
            "version": "attr.content.version",
            "prefixlen": "attr.content.prefixlen",
        }
        ipnetwork_prop_list = [f"{key}: {value}" for key, value in ipnetwork_prop.items()]

        attrs_nonindexed_query = """
        WITH DISTINCT n
        UNWIND $attrs AS attr
        // Try to find a matching vertex
        CALL (attr) {
            OPTIONAL MATCH (existing_av:AttributeValue {value: attr.content.value, is_default: attr.content.is_default})
            WHERE NOT existing_av:AttributeValueIndexed
            RETURN existing_av
            LIMIT 1
        }
        CALL (attr, existing_av) {
            // If none found, create a new one
            WITH existing_av
            WHERE existing_av IS NULL
            CREATE (:AttributeValue {value: attr.content.value, is_default: attr.content.is_default})
        }
        CALL (attr) {
            MATCH (av:AttributeValue {value: attr.content.value, is_default: attr.content.is_default})
            WHERE NOT av:AttributeValueIndexed
            RETURN av
            LIMIT 1
        }
        CALL (n, attr, av) {
            CREATE (a:Attribute %(attr_vertex)s)
            CREATE (n)-[:HAS_ATTRIBUTE %(attr_edge)s]->(a)
            CREATE (a)-[:HAS_VALUE %(attr_edge)s]->(av)
            MERGE (ip:Boolean { value: attr.is_protected })
            WITH a, ip
            LIMIT 1
            CREATE (a)-[:IS_PROTECTED %(attr_edge)s]->(ip)
            FOREACH ( prop IN attr.source_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (a)-[:HAS_SOURCE %(attr_edge)s]->(peer)
            )
            FOREACH ( prop IN attr.owner_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (a)-[:HAS_OWNER %(attr_edge)s]->(peer)
            )
        }""" % {"attr_edge": attr_edge_prop_str, "attr_vertex": attr_vertex_prop_str}

        attrs_indexed_query = """
        WITH distinct n
        UNWIND $attrs_indexed AS attr
        CALL (n, attr) {
            CREATE (a:Attribute %(attr_vertex)s)
            CREATE (n)-[:HAS_ATTRIBUTE %(attr_edge)s]->(a)
            MERGE (av:AttributeValue:AttributeValueIndexed { value: attr.content.value, is_default: attr.content.is_default })
            WITH av, a
            LIMIT 1
            CREATE (a)-[:HAS_VALUE %(attr_edge)s]->(av)
            MERGE (ip:Boolean { value: attr.is_protected })
            CREATE (a)-[:IS_PROTECTED %(attr_edge)s]->(ip)
            FOREACH ( prop IN attr.source_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (a)-[:HAS_SOURCE %(attr_edge)s]->(peer)
            )
            FOREACH ( prop IN attr.owner_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (a)-[:HAS_OWNER %(attr_edge)s]->(peer)
            )
        }""" % {"attr_edge": attr_edge_prop_str, "attr_vertex": attr_vertex_prop_str}

        attrs_iphost_query = """
        WITH distinct n
        UNWIND $attrs_iphost AS attr
        CALL (n, attr) {
            CREATE (a:Attribute %(attr_vertex)s)
            CREATE (n)-[:HAS_ATTRIBUTE %(attr_edge)s]->(a)
            MERGE (av:AttributeValue:AttributeValueIndexed:AttributeIPHost { %(iphost_prop)s })
            WITH attr, av, a
            LIMIT 1
            CREATE (a)-[:HAS_VALUE %(attr_edge)s]->(av)
            MERGE (ip:Boolean { value: attr.is_protected })
            WITH a, ip
            LIMIT 1
            CREATE (a)-[:IS_PROTECTED %(attr_edge)s]->(ip)
            FOREACH ( prop IN attr.source_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (a)-[:HAS_SOURCE %(attr_edge)s]->(peer)
            )
            FOREACH ( prop IN attr.owner_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (a)-[:HAS_OWNER %(attr_edge)s]->(peer)
            )
        }
        """ % {
            "iphost_prop": ", ".join(iphost_prop_list),
            "attr_edge": attr_edge_prop_str,
            "attr_vertex": attr_vertex_prop_str,
        }

        attrs_ipnetwork_query = """
        WITH distinct n
        UNWIND $attrs_ipnetwork AS attr
        CALL (n, attr) {
            CREATE (a:Attribute %(attr_vertex)s)
            CREATE (n)-[:HAS_ATTRIBUTE %(attr_edge)s]->(a)
            MERGE (av:AttributeValue:AttributeValueIndexed:AttributeIPNetwork { %(ipnetwork_prop)s })
            WITH attr, av, a
            LIMIT 1
            CREATE (a)-[:HAS_VALUE %(attr_edge)s]->(av)
            MERGE (ip:Boolean { value: attr.is_protected })
            WITH a, ip
            LIMIT 1
            CREATE (a)-[:IS_PROTECTED %(attr_edge)s]->(ip)
            FOREACH ( prop IN attr.source_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (a)-[:HAS_SOURCE %(attr_edge)s]->(peer)
            )
            FOREACH ( prop IN attr.owner_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (a)-[:HAS_OWNER %(attr_edge)s]->(peer)
            )
        }
        """ % {
            "ipnetwork_prop": ", ".join(ipnetwork_prop_list),
            "attr_edge": attr_edge_prop_str,
            "attr_vertex": attr_vertex_prop_str,
        }

        deepest_branch = await registry.get_branch(db=db, branch=deepest_branch_name)
        branch_filter, branch_params = deepest_branch.get_query_filter_path(at=self.at)
        self.params.update(branch_params)
        self.params["global_branch_name"] = GLOBAL_BRANCH_NAME
        self.params["default_branch_name"] = registry.default_branch

        dest_node_subquery = """
        CALL (rel) {
            MATCH (dest_node:Node { uuid: rel.destination_id })-[r:IS_PART_OF]->(root:Root)
            WHERE (
                // if the relationship is on a branch, use the regular filter
                (rel.peer_branch_level = 2 AND %(branch_filter)s)
                // simplified filter for the global branch
                OR (
                    rel.peer_branch_level = 1
                    AND rel.peer_branch = $global_branch_name
                    AND r.branch = $global_branch_name
                    AND r.from <= $at AND (r.to IS NULL or r.to > $at)
                )
                // simplified filter for the default branch
                OR (
                    rel.peer_branch_level = 1 AND
                    rel.peer_branch = $default_branch_name AND
                    r.branch IN [$default_branch_name, $global_branch_name]
                    AND r.from <= $at AND (r.to IS NULL or r.to > $at)
                )
            )
            // r.status is a tie-breaker when there are nodes with the same UUID added/deleted at the same time
            ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
            WITH dest_node, r
            LIMIT 1
            WITH dest_node, r
            WHERE r.status = "active"
            RETURN dest_node
        }
        """ % {"branch_filter": branch_filter}

        rels_bidir_query = """
        WITH distinct n
        UNWIND $rels_bidir AS rel
        %(dest_node_subquery)s
        CALL (n, rel, dest_node) {
            CREATE (rl:Relationship %(rel_vertex)s)
            CREATE (n)-[:IS_RELATED %(rel_edge_hierarchy)s ]->(rl)
            CREATE (dest_node)-[:IS_RELATED %(rel_edge_hierarchy)s ]->(rl)
            MERGE (ip:Boolean { value: rel.is_protected })
            WITH rl, ip
            LIMIT 1
            CREATE (rl)-[:IS_PROTECTED %(rel_edge)s]->(ip)
            FOREACH ( prop IN rel.source_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (rl)-[:HAS_SOURCE %(rel_edge)s]->(peer)
            )
            FOREACH ( prop IN rel.owner_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (rl)-[:HAS_OWNER %(rel_edge)s]->(peer)
            )
        }
        """ % {
            "rel_edge": rel_edge_prop_str,
            "rel_edge_hierarchy": rel_edge_prop_str_hierarchy,
            "rel_vertex": rel_vertex_prop_str,
            "dest_node_subquery": dest_node_subquery,
        }

        rels_out_query = """
        WITH distinct n
        UNWIND $rels_out AS rel
        %(dest_node_subquery)s
        CALL (n, rel, dest_node) {
            CREATE (rl:Relationship %(rel_vertex)s)
            CREATE (n)-[:IS_RELATED %(rel_edge_hierarchy)s ]->(rl)
            CREATE (dest_node)<-[:IS_RELATED %(rel_edge_hierarchy)s ]-(rl)
            MERGE (ip:Boolean { value: rel.is_protected })
            WITH rl, ip
            LIMIT 1
            CREATE (rl)-[:IS_PROTECTED %(rel_edge)s]->(ip)
            FOREACH ( prop IN rel.source_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (rl)-[:HAS_SOURCE %(rel_edge)s]->(peer)
            )
            FOREACH ( prop IN rel.owner_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (rl)-[:HAS_OWNER %(rel_edge)s]->(peer)
            )
        }
        """ % {
            "rel_edge": rel_edge_prop_str,
            "rel_edge_hierarchy": rel_edge_prop_str_hierarchy,
            "rel_vertex": rel_vertex_prop_str,
            "dest_node_subquery": dest_node_subquery,
        }

        rels_in_query = """
        WITH distinct n
        UNWIND $rels_in AS rel
        %(dest_node_subquery)s
        CALL (n, rel, dest_node) {
            CREATE (rl:Relationship %(rel_vertex)s)
            CREATE (n)<-[:IS_RELATED %(rel_edge_hierarchy)s ]-(rl)
            CREATE (dest_node)-[:IS_RELATED %(rel_edge_hierarchy)s ]->(rl)
            MERGE (ip:Boolean { value: rel.is_protected })
            WITH rl, ip
            LIMIT 1
            CREATE (rl)-[:IS_PROTECTED %(rel_edge)s]->(ip)
            FOREACH ( prop IN rel.source_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (rl)-[:HAS_SOURCE %(rel_edge)s]->(peer)
            )
            FOREACH ( prop IN rel.owner_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (rl)-[:HAS_OWNER %(rel_edge)s]->(peer)
            )
        }
        """ % {
            "rel_edge": rel_edge_prop_str,
            "rel_edge_hierarchy": rel_edge_prop_str_hierarchy,
            "rel_vertex": rel_vertex_prop_str,
            "dest_node_subquery": dest_node_subquery,
        }

        query = f"""
        MATCH (root:Root)
        CREATE (n:Node:%(labels)s $node_prop )
        CREATE (n)-[r:IS_PART_OF $node_branch_prop ]->(root)
        {attrs_nonindexed_query if self.params["attrs"] else ""}
        {attrs_indexed_query if self.params["attrs_indexed"] else ""}
        {attrs_iphost_query if self.params["attrs_iphost"] else ""}
        {attrs_ipnetwork_query if self.params["attrs_ipnetwork"] else ""}
        {rels_bidir_query if self.params["rels_bidir"] else ""}
        {rels_out_query if self.params["rels_out"] else ""}
        {rels_in_query if self.params["rels_in"] else ""}
        WITH distinct n
        MATCH (n)-[:HAS_ATTRIBUTE|IS_RELATED]-(rn)-[:HAS_VALUE|IS_RELATED]-(rv)
        """ % {
            "labels": ":".join(self.node.get_labels()),
        }

        self.params["at"] = at.to_string()

        self.add_to_query(query)
        self.return_labels = ["n", "rn", "rv"]

    def get_self_ids(self) -> tuple[str, str]:
        result = self.get_result()
        node = result.get("n")

        if node is None:
            raise QueryError(query=self.get_query(), params=self.params)

        return node["uuid"], node.element_id

    def get_ids(self) -> dict[str, tuple[str, str]]:
        data = {}
        for result in self.get_results():
            node = result.get("rn")
            if "Relationship" in node.labels:
                peer = result.get("rv")
                name = f"{node.get('name')}::{peer.get('uuid')}"
            elif "Attribute" in node.labels:
                name = node.get("name")
            data[name] = (node["uuid"], node.element_id)

        return data


class NodeDeleteQuery(NodeQuery):
    name = "node_delete"
    type: QueryType = QueryType.WRITE
    insert_return = False
    raise_error_if_empty = False

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:  # noqa: ARG002
        self.params["user_id"] = self.user_id
        self.params["uuid"] = self.node_id
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["at"] = self.at.to_string()

        if self.branch.is_global or self.branch.is_default:
            # update the updated_at/by metadata on the Node if we're on the global or default branch
            node_query_match = """
MATCH (n:Node { uuid: $uuid })-[r:IS_PART_OF { branch_level: 1, status: "active" }]->(:Root)
WHERE r.to IS NULL
OPTIONAL MATCH (n)-[delete_edge:IS_PART_OF {status: "deleted", branch: $branch}]->(:Root)
WHERE delete_edge.from <= $at
WITH n, r
WHERE delete_edge IS NULL
SET n.updated_at = $at, n.updated_by = $user_id
WITH n, r
            """
        else:
            node_filter, node_filter_params = self.branch.get_query_filter_path(at=self.at, variable_name="r")
            node_query_match = """
MATCH (n:Node { uuid: $uuid })
CALL (n) {
    MATCH (n)-[r:IS_PART_OF]->(:Root)
    WHERE %(node_filter)s
    RETURN r
    ORDER BY r.from DESC
    LIMIT 1
}
WITH n, r
WHERE r.status = "active"
                """ % {"node_filter": node_filter}
            self.params.update(node_filter_params)
        self.add_to_query(node_query_match)

        # set the to time/user_id if the active IS_PART_OF edge is on this branch
        query = """
MATCH (root:Root)
LIMIT 1
CREATE (n)-[delete_edge:IS_PART_OF { branch: $branch, branch_level: $branch_level, status: "deleted", from: $at, from_user_id: $user_id }]->(root)
WITH r
WHERE r.branch = $branch
SET r.to = $at
SET r.to_user_id = $user_id
        """
        self.add_to_query(query)


class NodeUpdateMetadataQuery(NodeQuery):
    name = "node_update_metadata"
    type: QueryType = QueryType.WRITE
    insert_return = False
    raise_error_if_empty = False

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:  # noqa: ARG002
        if not self.branch.is_default and not self.branch.is_global:
            raise ValueError("NodeUpdateMetadataQuery can only be used on the default or global branch")
        self.params["uuid"] = self.node_id
        self.params["branch"] = self.branch.name
        self.params["at"] = self.at.to_string()
        self.params["user_id"] = self.user_id

        query = """
MATCH (n:Node { uuid: $uuid })-[r:IS_PART_OF { branch_level: 1, status: "active" }]->(:Root)
WHERE r.to IS NULL
OPTIONAL MATCH (n)-[delete_edge:IS_PART_OF {status: "deleted", branch: $branch}]->(:Root)
WHERE delete_edge.from <= $at
WITH n, r
WHERE delete_edge IS NULL
SET n.updated_at = $at, n.updated_by = $user_id
        """
        self.add_to_query(query)


class NodeCheckIDQuery(Query):
    name = "node_check_id"

    type: QueryType = QueryType.READ

    def __init__(
        self,
        node_id: str,
        **kwargs,
    ):
        self.node_id = node_id
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:  # noqa: ARG002
        self.params["uuid"] = self.node_id

        query = """
        MATCH (root:Root)-[]-(n:Node { uuid: $uuid })
        """

        self.add_to_query(query)
        self.return_labels = ["n"]


class NodeListGetAttributeQuery(Query):
    name = "node_list_get_attribute"
    type = QueryType.READ

    property_type_mapping = {
        "HAS_VALUE": ("r2", "av"),
        "HAS_OWNER": ("rel_owner", "owner"),
        "HAS_SOURCE": ("rel_source", "source"),
        "IS_PROTECTED": ("rel_isp", "isp"),
    }

    def __init__(
        self,
        ids: list[str],
        fields: dict | None = None,
        include_metadata: MetadataOptions = MetadataOptions.NONE,
        **kwargs,
    ):
        self.ids = ids
        self.fields = fields
        self.include_metadata = include_metadata
        super().__init__(order_by=["n.uuid", "a.name"], **kwargs)

    @property
    def _include_source(self) -> bool:
        return bool(self.include_metadata & MetadataOptions.SOURCE)

    @property
    def _include_owner(self) -> bool:
        return bool(self.include_metadata & MetadataOptions.OWNER)

    @property
    def _include_updated_metadata(self) -> bool:
        return bool(self.include_metadata & (MetadataOptions.UPDATED_AT | MetadataOptions.UPDATED_BY))

    @property
    def _include_created_metadata(self) -> bool:
        return bool(self.include_metadata & (MetadataOptions.CREATED_AT | MetadataOptions.CREATED_BY))

    def _add_source_to_query(self, branch_filter_str: str) -> None:
        if not self._include_source:
            return
        source_query = """
CALL (a) {
    OPTIONAL MATCH (a)-[rel_source:HAS_SOURCE]-(source)
    WHERE all(r IN [rel_source] WHERE ( %(branch_filter)s ))
    RETURN source, rel_source
    ORDER BY rel_source.branch_level DESC, rel_source.from DESC, rel_source.status ASC
    LIMIT 1
}
WITH *,
    CASE WHEN rel_source.status = "active" THEN source ELSE NULL END AS source,
    CASE WHEN rel_source.status = "active" THEN rel_source ELSE NULL END AS rel_source
        """ % {"branch_filter": branch_filter_str}
        self.add_to_query(source_query)
        self.return_labels.extend(["source", "rel_source"])

    def _add_owner_to_query(self, branch_filter_str: str) -> None:
        if not self._include_owner:
            return
        owner_query = """
CALL (a) {
    OPTIONAL MATCH (a)-[rel_owner:HAS_OWNER]-(owner)
    WHERE all(r IN [rel_owner] WHERE ( %(branch_filter)s ))
    RETURN owner, rel_owner
    ORDER BY rel_owner.branch_level DESC, rel_owner.from DESC, rel_owner.status ASC
    LIMIT 1
}
WITH *,
    CASE WHEN rel_owner.status = "active" THEN owner ELSE NULL END AS owner,
    CASE WHEN rel_owner.status = "active" THEN rel_owner ELSE NULL END AS rel_owner
        """ % {"branch_filter": branch_filter_str}
        self.add_to_query(owner_query)
        self.return_labels.extend(["owner", "rel_owner"])

    def _add_created_metadata_to_query(self) -> None:
        if not self._include_created_metadata:
            return
        if self.branch.is_default or self.branch.is_global:
            last_created_query = """
WITH *, a.created_at AS created_at, a.created_by AS created_by
            """
        else:
            last_created_query = """
WITH *, r1.from AS created_at, r1.from_user_id AS created_by
            """
        self.add_to_query(last_created_query)
        self.return_labels.extend(["created_at", "created_by"])

    def _add_updated_metadata_to_query(self, branch_filter_str: str) -> None:
        if not self._include_updated_metadata:
            return
        if self.branch.is_default or self.branch.is_global:
            last_updated_query = """
WITH *, a.updated_at AS updated_at, a.updated_by AS updated_by
            """
        else:
            last_updated_query = """
CALL (a) {
    MATCH (a)-[r]-(property)
    WHERE %(branch_filter)s
    WITH CASE
        WHEN r.branch IN $branch0 AND r.from < $time0 THEN [r.from, r.from_user_id]
        WHEN r.branch IN $branch1 AND r.from < $time1 THEN [r.from, r.from_user_id]
        ELSE [NULL, NULL]
    END AS from_details,
    CASE
        WHEN r.branch IN $branch0 AND r.to < $time0 THEN [r.to, r.to_user_id]
        WHEN r.branch IN $branch1 AND r.to < $time1 THEN [r.to, r.to_user_id]
        ELSE [NULL, NULL]
    END AS to_details
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
            """ % {"branch_filter": branch_filter_str}
        self.add_to_query(last_updated_query)
        self.return_labels.extend(["updated_at", "updated_by"])

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:  # noqa: ARG002
        self.params["ids"] = self.ids
        self.params["profile_node_relationship_name"] = PROFILE_NODE_RELATIONSHIP_IDENTIFIER
        self.params["profile_template_relationship_name"] = PROFILE_TEMPLATE_RELATIONSHIP_IDENTIFIER
        self.params["field_names"] = list(self.fields.keys()) if self.fields else []

        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at, branch_agnostic=self.branch_agnostic
        )
        self.params.update(branch_params)

        query = """
        MATCH (n:Node) WHERE n.uuid IN $ids
        WITH n, (
            exists((n)-[:IS_RELATED]-(:Relationship {name: $profile_node_relationship_name})) OR
            exists((n)-[:IS_RELATED]-(:Relationship {name: $profile_template_relationship_name}))
        ) AS might_use_profile
        MATCH (n)-[:HAS_ATTRIBUTE]-(a:Attribute)
        WHERE (a.name IN $field_names OR size($field_names) = 0)
        WITH DISTINCT n, a, might_use_profile
        """
        self.add_to_query(query)

        query = """
CALL (n, a) {
    MATCH (n)-[r:HAS_ATTRIBUTE]-(a:Attribute)
    WHERE %(branch_filter)s
    RETURN r AS r1
    ORDER BY r.branch_level DESC, r.from DESC
    LIMIT 1
}
WITH n, r1, a, might_use_profile
WHERE r1.status = "active"
WITH n, r1, a, might_use_profile
CALL (a, might_use_profile) {
    OPTIONAL MATCH (a)-[r:HAS_SOURCE]->(:CoreProfile)
    WHERE might_use_profile = TRUE AND %(branch_filter)s
    RETURN r.status = "active" AS has_active_profile
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
WITH *, has_active_profile = TRUE AS is_from_profile
CALL (a) {
    MATCH (a)-[r:HAS_VALUE]-(av:AttributeValue)
    WHERE %(branch_filter)s
    RETURN r as r2, av
    ORDER BY r.branch_level DESC, r.from DESC
    LIMIT 1
}
WITH n, r1, a, r2, av, is_from_profile
WHERE r2.status = "active"
        """ % {"branch_filter": branch_filter}
        self.add_to_query(query)

        self.return_labels = ["n", "a", "av", "r1", "r2", "is_from_profile"]

        # Add Is_Protected
        query = """
CALL (a) {
    MATCH (a)-[r:IS_PROTECTED]-(isp:Boolean)
    WHERE (%(branch_filter)s)
    RETURN r AS rel_isp, isp
    ORDER BY rel_isp.branch_level DESC, rel_isp.from DESC, rel_isp.status ASC
    LIMIT 1
}
        """ % {"branch_filter": branch_filter}
        self.add_to_query(query)

        self.return_labels.extend(["isp", "rel_isp"])

        self._add_source_to_query(branch_filter_str=branch_filter)
        self._add_owner_to_query(branch_filter_str=branch_filter)
        self._add_created_metadata_to_query()
        self._add_updated_metadata_to_query(branch_filter_str=branch_filter)

    def get_attributes_group_by_node(self) -> dict[str, NodeAttributesFromDB]:
        attrs_by_node: dict[str, NodeAttributesFromDB] = {}

        for result in self.get_results_group_by(("n", "uuid"), ("a", "name")):
            node_id: str = result.get_node("n").get("uuid")
            attr_name: str = result.get_node("a").get("name")

            attr = self._extract_attribute_data(result=result)

            if node_id not in attrs_by_node:
                attrs_by_node[node_id] = NodeAttributesFromDB(node=result.get_node("n"))

            attrs_by_node[node_id].attrs[attr_name] = attr

        return attrs_by_node

    def get_result_by_id_and_name(self, node_id: str, attr_name: str) -> tuple[AttributeFromDB, QueryResult]:
        for result in self.get_results_group_by(("n", "uuid"), ("a", "name")):
            if result.get_node("n").get("uuid") == node_id and result.get_node("a").get("name") == attr_name:
                return self._extract_attribute_data(result=result), result

        raise IndexError(f"Unable to find the result with ID: {node_id} and NAME: {attr_name}")

    def _extract_attribute_data(self, result: QueryResult) -> AttributeFromDB:
        attr = result.get_node("a")
        attr_value = result.get_node("av")
        is_from_profile = result.get_as_type(label="is_from_profile", return_type=bool)

        data = AttributeFromDB(
            name=attr.get("name"),
            attr_labels=list(attr.labels),
            attr_id=attr.element_id,
            attr_uuid=attr.get("uuid"),
            attr_value_id=attr_value.element_id,
            attr_value_uuid=attr_value.get("uuid"),
            value=attr_value.get("value"),
            is_default=attr_value.get("is_default"),
            is_from_profile=is_from_profile,
            content=attr_value._properties,
            branch=self.branch.name,
            flag_properties={
                "is_protected": result.get("isp").get("value"),
            },
        )

        if self.include_metadata & MetadataOptions.CREATED_AT:
            created_at_str = result.get_as_str("created_at")
            data.created_at = Timestamp(created_at_str) if created_at_str else None
        if self.include_metadata & MetadataOptions.CREATED_BY:
            data.created_by = result.get_as_str("created_by")
        if self.include_metadata & MetadataOptions.UPDATED_AT:
            updated_at_str = result.get_as_str("updated_at")
            data.updated_at = Timestamp(updated_at_str) if updated_at_str else None
        if self.include_metadata & MetadataOptions.UPDATED_BY:
            data.updated_by = result.get_as_str("updated_by")

        if self._include_source and result.get("source"):
            data.node_properties["source"] = AttributeNodePropertyFromDB(
                uuid=result.get_node("source").get("uuid"), labels=list(result.get_node("source").labels)
            )

        if self._include_owner and result.get("owner"):
            data.node_properties["owner"] = AttributeNodePropertyFromDB(
                uuid=result.get_node("owner").get("uuid"), labels=list(result.get_node("owner").labels)
            )

        return data


class GroupedPeerNodes:
    def __init__(self):
        # {node_id: [rel_name, ...]}
        self._rel_names_by_node_id: dict[str, set[str]] = defaultdict(set)
        # {(node_id, rel_name): {RelationshipDirection: {peer_id, ...}}}
        self._rel_directions_map: dict[tuple[str, str], dict[RelationshipDirection, set[str]]] = defaultdict(dict)
        # {(node_id, rel_name, direction, peer_Id): {MetadataOptions: value}}
        self._metadata_map: dict[
            tuple[str, str, RelationshipDirection, str], dict[MetadataOptions, Timestamp | str | None]
        ] = {}

    def add_peer(
        self,
        node_id: str,
        rel_name: str,
        peer_id: str,
        direction: RelationshipDirection,
        created_at: Timestamp | None = None,
        created_by: str | None = None,
        updated_at: Timestamp | None = None,
        updated_by: str | None = None,
    ) -> None:
        self._rel_names_by_node_id[node_id].add(rel_name)
        if direction not in self._rel_directions_map[node_id, rel_name]:
            self._rel_directions_map[node_id, rel_name][direction] = set()
        self._rel_directions_map[node_id, rel_name][direction].add(peer_id)
        key = (node_id, rel_name, direction, peer_id)
        if created_at is not None or created_by is not None or updated_at is not None or updated_by is not None:
            self._metadata_map[key] = {}
        if created_at is not None:
            self._metadata_map[key][MetadataOptions.CREATED_AT] = created_at
        if created_by is not None:
            self._metadata_map[key][MetadataOptions.CREATED_BY] = created_by
        if updated_at is not None:
            self._metadata_map[key][MetadataOptions.UPDATED_AT] = updated_at
        if updated_by is not None:
            self._metadata_map[key][MetadataOptions.UPDATED_BY] = updated_by

    def get_peer_ids(self, node_id: str, rel_name: str, direction: RelationshipDirection) -> set[str]:
        if (node_id, rel_name) not in self._rel_directions_map:
            return set()
        return self._rel_directions_map[node_id, rel_name].get(direction, set())

    def get_all_peers(self) -> set[str]:
        all_peers_set = set()
        for peer_direction_map in self._rel_directions_map.values():
            for peer_ids in peer_direction_map.values():
                all_peers_set.update(peer_ids)
        return all_peers_set

    def has_node(self, node_id: str) -> bool:
        return node_id in self._rel_names_by_node_id

    def get_metadata_map(
        self, node_id: str, rel_name: str, direction: RelationshipDirection, peer_id: str
    ) -> dict[MetadataOptions, Timestamp | str | None]:
        return self._metadata_map.get((node_id, rel_name, direction, peer_id), {})


class NodeListGetRelationshipsQuery(Query):
    name: str = "node_list_get_relationship"
    type: QueryType = QueryType.READ

    def __init__(
        self,
        ids: list[str],
        outbound_identifiers: list[str] | None = None,
        inbound_identifiers: list[str] | None = None,
        bidirectional_identifiers: list[str] | None = None,
        include_metadata: MetadataOptions = MetadataOptions.NONE,
        **kwargs,
    ):
        self.ids = ids
        self.outbound_identifiers = outbound_identifiers
        self.inbound_identifiers = inbound_identifiers
        self.bidirectional_identifiers = bidirectional_identifiers
        self.include_metadata = include_metadata
        super().__init__(**kwargs)

    def _add_created_metadata_to_query(self) -> None:
        if not (self.include_metadata & (MetadataOptions.CREATED_AT | MetadataOptions.CREATED_BY)):
            return
        if self.branch.is_default or self.branch.is_global:
            last_created_query = """
WITH *, rel.created_at AS created_at, rel.created_by AS created_by
            """
        else:
            last_created_query = """
WITH *, CASE
    WHEN r1.from < r2.from THEN [r1.from, r1.from_user_id]
    ELSE [r2.from, r2.from_user_id]
END AS created_details
WITH *, created_details[0] AS created_at, created_details[1] AS created_by
            """
        self.add_to_query(last_created_query)
        self.return_labels.extend(["created_at", "created_by"])

    def _add_updated_metadata_to_query(self, branch_filter_str: str) -> None:
        if not (self.include_metadata & (MetadataOptions.UPDATED_AT | MetadataOptions.UPDATED_BY)):
            return
        if self.branch.is_default or self.branch.is_global:
            last_updated_query = """
WITH *, rel.updated_at AS updated_at, rel.updated_by AS updated_by
            """
        else:
            last_updated_query = """
CALL (rel) {
    MATCH (rel)-[r]-(property)
    WHERE %(branch_filter)s
    WITH CASE
        WHEN r.branch IN $branch0 AND r.from < $time0 THEN [r.from, r.from_user_id]
        WHEN r.branch IN $branch1 AND r.from < $time1 THEN [r.from, r.from_user_id]
        ELSE [NULL, NULL]
    END AS from_details,
    CASE
        WHEN r.branch IN $branch0 AND r.to < $time0 THEN [r.to, r.to_user_id]
        WHEN r.branch IN $branch1 AND r.to < $time1 THEN [r.to, r.to_user_id]
        ELSE [NULL, NULL]
    END AS to_details
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
            """ % {"branch_filter": branch_filter_str}
        self.add_to_query(last_updated_query)
        self.return_labels.extend(["updated_at", "updated_by"])

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:  # noqa: ARG002
        self.params["ids"] = self.ids
        self.params["outbound_identifiers"] = self.outbound_identifiers
        self.params["inbound_identifiers"] = self.inbound_identifiers
        self.params["bidirectional_identifiers"] = self.bidirectional_identifiers

        rels_filter, rels_params = self.branch.get_query_filter_path(at=self.at, branch_agnostic=self.branch_agnostic)
        self.params.update(rels_params)

        query = """
        MATCH (n:Node) WHERE n.uuid IN $ids
        CALL (n) {
            MATCH (n)<-[:IS_RELATED]-(rel:Relationship)<-[:IS_RELATED]-(peer)
            WHERE ($inbound_identifiers IS NULL OR rel.name in $inbound_identifiers)
            AND n.uuid <> peer.uuid
            WITH DISTINCT n, rel, peer
            CALL (n, rel, peer) {
                MATCH (n)<-[r:IS_RELATED]-(rel)
                WHERE (%(filters)s)
                WITH n, rel, peer, r
                ORDER BY r.from DESC
                LIMIT 1
                WITH n, rel, peer, r AS r1
                WHERE r1.status = "active"
                MATCH (rel)<-[r:IS_RELATED]-(peer)
                WHERE (%(filters)s)
                WITH r1, r
                ORDER BY r.from DESC
                LIMIT 1
                WITH r1, r AS r2
                WHERE r2.status = "active"
                RETURN r1, r2
            }
            RETURN n.uuid AS n_uuid, rel, peer.uuid AS peer_uuid, "inbound" as direction, r1, r2
            UNION
            WITH n
            MATCH (n)-[:IS_RELATED]->(rel:Relationship)-[:IS_RELATED]->(peer)
            WHERE ($outbound_identifiers IS NULL OR rel.name in $outbound_identifiers)
            AND n.uuid <> peer.uuid
            WITH DISTINCT n, rel, peer
            CALL (n, rel, peer) {
                MATCH (n)-[r:IS_RELATED]->(rel)
                WHERE (%(filters)s)
                WITH n, rel, peer, r
                ORDER BY r.from DESC
                LIMIT 1
                WITH n, rel, peer, r AS r1
                WHERE r1.status = "active"
                MATCH (rel)-[r:IS_RELATED]->(peer)
                WHERE (%(filters)s)
                WITH r1, r
                ORDER BY r.from DESC
                LIMIT 1
                WITH r1, r AS r2
                WHERE r2.status = "active"
                RETURN r1, r2
            }
            RETURN n.uuid AS n_uuid, rel, peer.uuid AS peer_uuid, "outbound" as direction, r1, r2
            UNION
            WITH n
            MATCH (n)-[:IS_RELATED]->(rel:Relationship)<-[:IS_RELATED]-(peer)
            WHERE ($bidirectional_identifiers IS NULL OR rel.name in $bidirectional_identifiers)
            AND n.uuid <> peer.uuid
            WITH DISTINCT n, rel, peer
            CALL (n, rel, peer) {
                MATCH (n)-[r:IS_RELATED]->(rel)
                WHERE (%(filters)s)
                WITH n, rel, peer, r
                ORDER BY r.from DESC
                LIMIT 1
                WITH n, rel, peer, r AS r1
                WHERE r1.status = "active"
                MATCH (rel)<-[r:IS_RELATED]-(peer)
                WHERE (%(filters)s)
                WITH r1, r
                ORDER BY r.from DESC
                LIMIT 1
                WITH r1, r AS r2
                WHERE r2.status = "active"
                RETURN r1, r2
            }
            RETURN n.uuid AS n_uuid, rel, peer.uuid AS peer_uuid, "bidirectional" as direction, r1, r2
        }
        """ % {"filters": rels_filter}
        self.add_to_query(query)

        self.order_by = ["n_uuid", "rel_name", "peer_uuid", "direction"]
        self.return_labels = ["n_uuid", "peer_uuid", "direction"]

        self._add_created_metadata_to_query()
        self._add_updated_metadata_to_query(branch_filter_str=rels_filter)
        return_labels_str = ", ".join(sorted(self.return_labels))
        self.add_to_query(f"WITH DISTINCT {return_labels_str}, rel.name AS rel_name")
        self.return_labels.append("rel_name")

    def get_peers_group_by_node(self) -> GroupedPeerNodes:
        gpn = GroupedPeerNodes()
        for result in self.get_results():
            node_id = result.get("n_uuid")
            rel_name = result.get("rel_name")
            peer_id = result.get("peer_uuid")
            direction = str(result.get("direction"))

            created_at = None
            if self.include_metadata & MetadataOptions.CREATED_AT:
                created_at_str = result.get("created_at")
                created_at = Timestamp(created_at_str) if created_at_str else None

            created_by_str = None
            if self.include_metadata & MetadataOptions.CREATED_BY:
                created_by_str = result.get("created_by")

            updated_at = None
            if self.include_metadata & MetadataOptions.UPDATED_AT:
                updated_at_str = result.get("updated_at")
                updated_at = Timestamp(updated_at_str) if updated_at_str else None

            updated_by_str = None
            if self.include_metadata & MetadataOptions.UPDATED_BY:
                updated_by_str = result.get("updated_by")

            direction_enum = {
                "inbound": RelationshipDirection.INBOUND,
                "outbound": RelationshipDirection.OUTBOUND,
                "bidirectional": RelationshipDirection.BIDIR,
            }.get(direction)
            gpn.add_peer(
                node_id=node_id,
                rel_name=rel_name,
                peer_id=peer_id,
                direction=direction_enum,
                created_at=created_at,
                created_by=created_by_str,
                updated_at=updated_at,
                updated_by=updated_by_str,
            )

        return gpn


class NodeGetKindQuery(Query):
    name = "node_get_kind_query"
    type = QueryType.READ

    def __init__(self, ids: list[str], **kwargs: Any) -> None:
        self.ids = ids
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["ids"] = self.ids
        query = """
MATCH (n:Node)-[r:IS_PART_OF {status: "active"}]->(:Root)
WHERE toString(n.uuid) IN $ids
        """
        # only add the branch filter logic if a branch is included in the query parameters
        if branch := getattr(self, "branch", None):
            branch = await registry.get_branch(db=db, branch=branch)
            branch_filter, branch_params = branch.get_query_filter_path(at=self.at)
            self.params.update(branch_params)
            query += f"AND {branch_filter}"
        query += """
WITH n.uuid AS node_id, n.kind AS node_kind
ORDER BY r.from DESC
WITH node_id, head(collect(node_kind)) AS node_kind
        """
        self.add_to_query(query)
        self.return_labels = ["node_id", "node_kind"]

    async def get_node_kind_map(self) -> dict[str, str]:
        node_kind_map: dict[str, str] = {}
        for result in self.get_results():
            node_kind_map[str(result.get("node_id"))] = str(result.get("node_kind"))
        return node_kind_map


class NodeListGetInfoQuery(Query):
    name = "node_list_get_info"
    type = QueryType.READ

    def __init__(self, ids: list[str], include_metadata: MetadataOptions = MetadataOptions.NONE, **kwargs: Any) -> None:
        self.ids = ids
        self.include_metadata = include_metadata
        super().__init__(**kwargs)

    def _needs_user_timestamp_metadata(self) -> bool:
        return bool(self.include_metadata & MetadataOptions.USER_TIMESTAMPS)

    def _add_updated_metadata_to_query(self, branch_filter_str: str) -> None:
        if self.branch.is_default or self.branch.is_global:
            last_update_query = """
WITH *, n.updated_at AS updated_at, n.updated_by AS updated_by
            """
        else:
            if self.branch_agnostic:
                time_details = """
    WITH [r.from, r.from_user_id] AS from_details, [r.to, r.to_user_id] AS to_details
                """
            else:
                time_details = """
    WITH CASE
        WHEN r.branch IN $branch0 AND r.from < $time0 THEN [r.from, r.from_user_id]
        WHEN r.branch IN $branch1 AND r.from < $time1 THEN [r.from, r.from_user_id]
        ELSE [NULL, NULL]
    END AS from_details,
    CASE
        WHEN r.branch IN $branch0 AND r.to < $time0 THEN [r.to, r.to_user_id]
        WHEN r.branch IN $branch1 AND r.to < $time1 THEN [r.to, r.to_user_id]
        ELSE [NULL, NULL]
    END AS to_details
                """
            last_update_query = """
MATCH (n)-[r:HAS_ATTRIBUTE|IS_RELATED]-(field:Attribute|Relationship)
WHERE %(branch_filter)s
WITH DISTINCT n, r_is_part_of, field
CALL (n, field) {
    MATCH (n)-[r:HAS_ATTRIBUTE|IS_RELATED]-(field)
    WHERE %(branch_filter)s
    RETURN r.status = "active" AS is_active
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
WITH n, r_is_part_of, field
WHERE is_active = TRUE
CALL (field) {
    MATCH (field)-[r]-(property)
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
WITH n, r_is_part_of, updated_at, updated_by
// updated_by ordering preferences non "__system__" users
ORDER BY elementId(n), updated_at DESC, updated_by DESC
WITH n, r_is_part_of, head(collect(updated_at)) AS updated_at, head(collect(updated_by)) AS updated_by
            """ % {"branch_filter": branch_filter_str, "time_details": time_details}
        self.add_to_query(last_update_query)
        self.return_labels.extend(["updated_at", "updated_by"])

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at, branch_agnostic=self.branch_agnostic
        )
        self.params.update(branch_params)
        self.params["ids"] = self.ids
        self.order_by = ["n.uuid"]

        query = """
        MATCH p = (root:Root)<-[:IS_PART_OF]-(n:Node)
        WHERE n.uuid IN $ids
        CALL (root, n) {
            MATCH (root:Root)<-[r:IS_PART_OF]-(n:Node)
            WHERE %(branch_filter)s
            RETURN r AS r_is_part_of
            ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
            LIMIT 1
        }
        WITH n, r_is_part_of
        WHERE r_is_part_of.status = "active"
        """ % {"branch_filter": branch_filter}
        self.add_to_query(query)
        self.return_labels = [
            "labels(n) AS node_labels",
            "r_is_part_of.branch AS branch",
            "elementId(n) AS node_database_id",
            "n.uuid AS node_uuid",
        ]

        if self._needs_user_timestamp_metadata():
            self.return_labels.append("r_is_part_of.from AS created_at")
            self.return_labels.append("r_is_part_of.from_user_id AS created_by")
            self._add_updated_metadata_to_query(branch_filter_str=branch_filter)

    async def get_nodes(self, db: InfrahubDatabase, duplicate: bool = False) -> AsyncIterator[NodeToProcess]:
        """Return all the node objects as NodeToProcess."""

        for result in self.get_results():
            raw_labels: list[str] = result.get_as_type(label="node_labels", return_type=list)
            labels = [str(lbl) for lbl in raw_labels]
            schema = find_node_schema(db=db, branch=self.branch, labels=labels, duplicate=duplicate)
            node_branch = self.branch
            if self.branch_agnostic:
                node_branch = result.get_as_type(label="branch", return_type=str)

            created_at = None
            created_by = None
            if self.include_metadata & (MetadataOptions.CREATED_AT | MetadataOptions.UPDATED_AT):
                raw_created_at = result.get_as_str(label="created_at")
                created_at = Timestamp(raw_created_at) if raw_created_at else None
            if self.include_metadata & (MetadataOptions.CREATED_BY | MetadataOptions.UPDATED_BY):
                created_by = result.get_as_str(label="created_by")
            updated_at = None
            updated_by = None
            if self.include_metadata & MetadataOptions.UPDATED_AT:
                raw_updated_at = result.get_as_str(label="updated_at")
                updated_at = Timestamp(raw_updated_at) if raw_updated_at else None
            if self.include_metadata & MetadataOptions.UPDATED_BY:
                updated_by = result.get_as_str(label="updated_by")

            yield NodeToProcess(
                schema=schema,
                node_id=result.get_as_type(label="node_database_id", return_type=str),
                node_uuid=result.get_as_type(label="node_uuid", return_type=str),
                branch=node_branch,
                labels=labels,
                created_at=created_at,
                created_by=created_by,
                updated_at=updated_at or created_at,
                updated_by=updated_by or created_by,
            )


class FieldAttributeRequirementType(Enum):
    FILTER = "filter"
    ORDER = "order"


@dataclass
class FieldAttributeRequirement:
    field_name: str
    field: AttributeSchema | RelationshipSchema | None
    field_attr_name: str
    field_attr_value: Any
    index: int
    types: list[FieldAttributeRequirementType] = dataclass_field(default_factory=list)

    @property
    def is_attribute_value(self) -> bool:
        return bool(self.field and self.field.is_attribute and self.field_attr_name in ("value", "values", "isnull"))

    @property
    def is_filter(self) -> bool:
        return FieldAttributeRequirementType.FILTER in self.types

    @property
    def is_order(self) -> bool:
        return FieldAttributeRequirementType.ORDER in self.types

    @property
    def node_value_query_variable(self) -> str:
        return f"attr{self.index}_node_value"

    @property
    def comparison_operator(self) -> str:
        if self.field_attr_name == "isnull":
            return "=" if self.field_attr_value is True else "<>"
        if self.field_attr_name == "values":
            return "IN"
        return "="

    @property
    def field_attr_comparison_value(self) -> Any:
        if self.field_attr_name == "isnull":
            return "NULL"
        return self.field_attr_value


class NodeGetListQuery(Query):
    name = "node_get_list"
    type = QueryType.READ

    def __init__(
        self,
        schema: NodeSchema,
        filters: dict | None = None,
        partial_match: bool = False,
        order: OrderModel | None = None,
        **kwargs: Any,
    ) -> None:
        self.schema = schema
        self.filters = filters
        self.partial_match = partial_match
        self._variables_to_track = ["n", "rb"]
        self._validate_filters()

        # Force disabling order when `limit` is 1 as it simplifies the query a lot.
        if "limit" in kwargs and kwargs["limit"] == 1:
            if order is None:
                order = OrderModel(disable=True)
            else:
                order = copy(order)
                order.disable = True

        self.order = order

        super().__init__(**kwargs)

    @property
    def has_filters(self) -> bool:
        if not self.filters or self.has_filter_by_id:
            return False
        return True

    @property
    def has_filter_by_id(self) -> bool:
        if self.filters and "id" in self.filters:
            return True
        return False

    def _validate_filters(self) -> None:
        if not self.filters:
            return
        filter_errors = []
        for filter_str in self.filters:
            split_filter = filter_str.split("__")
            if len(split_filter) > 2 and split_filter[-1] == "isnull":
                filter_errors.append(
                    f"{filter_str} is not allowed: 'isnull' is not supported for attributes of relationships"
                )
        if filter_errors:
            raise RuntimeError(*filter_errors)

    def _track_variable(self, variable: str) -> None:
        if variable not in self._variables_to_track:
            self._variables_to_track.append(variable)

    def _untrack_variable(self, variable: str) -> None:
        with contextlib.suppress(ValueError):
            self._variables_to_track.remove(variable)

    def _get_tracked_variables(self) -> list[str]:
        return self._variables_to_track

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.order_by = []

        self.return_labels = ["n.uuid", "rb.branch", f"{db.get_id_function_name()}(rb) as rb_id"]

        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at, branch_agnostic=self.branch_agnostic
        )
        self.params.update(branch_params)

        # The initial subquery is used to filter out deleted nodes because we can have multiple valid results per branch
        #   and we need to filter out the one that have been deleted in the branch.
        # If we are on the default branch, the subquery is not required because only one valid result is expected at a given time
        if not self.branch.is_default:
            topquery = """
            MATCH (n:%(node_kind)s)
            CALL (n) {
                MATCH (root:Root)<-[r:IS_PART_OF]-(n)
                WHERE %(branch_filter)s
                RETURN r
                ORDER BY r.branch_level DESC, r.from DESC
                LIMIT 1
            }
            WITH n, r as rb
            WHERE rb.status = "active"
            """ % {"branch_filter": branch_filter, "node_kind": self.schema.kind}
            self.add_to_query(topquery)
        else:
            topquery = """
            MATCH (root:Root)<-[r:IS_PART_OF]-(n:%(node_kind)s)
            WHERE %(branch_filter)s
            WITH n, r as rb
            WHERE rb.status = "active"
            """ % {"branch_filter": branch_filter, "node_kind": self.schema.kind}
            self.add_to_query(topquery)

        if self.has_filter_by_id and self.filters:
            self.params["uuid"] = self.filters["id"]
            self.add_to_query(" AND n.uuid = $uuid")
            return

        disable_order = not self.schema.order_by or (self.order is not None and self.order.disable)
        if not self.has_filters and disable_order:
            # Always order by uuid to guarantee pagination, see https://github.com/opsmill/infrahub/pull/4704.
            self.order_by = ["n.uuid"]
            return

        if self.filters and "ids" in self.filters:
            self.add_to_query("AND n.uuid IN $node_ids")
            self.params["node_ids"] = self.filters["ids"]

        field_attribute_requirements = self._get_field_requirements(disable_order=disable_order)
        await self._add_node_filter_attributes(
            db=db, field_attribute_requirements=field_attribute_requirements, branch_filter=branch_filter
        )

        if not disable_order:
            await self._add_node_order_attributes(
                db=db, field_attribute_requirements=field_attribute_requirements, branch_filter=branch_filter
            )
            for far in field_attribute_requirements:
                if not far.is_order:
                    continue
                self.order_by.append(far.node_value_query_variable)

        # Always order by uuid to guarantee pagination, see https://github.com/opsmill/infrahub/pull/4704.
        self.order_by.append("n.uuid")

        self._add_final_filter(field_attribute_requirements=field_attribute_requirements)

    async def _add_node_filter_attributes(
        self,
        db: InfrahubDatabase,
        field_attribute_requirements: list[FieldAttributeRequirement],
        branch_filter: str,
    ) -> None:
        field_attribute_requirements = [far for far in field_attribute_requirements if far.is_filter]
        if not field_attribute_requirements:
            return

        filter_query: list[str] = []
        filter_params: dict[str, Any] = {}

        for far in field_attribute_requirements:
            extra_tail_properties = {far.node_value_query_variable: "value"}
            subquery, subquery_params, subquery_result_name = await build_subquery_filter(
                db=db,
                field=far.field,
                name=far.field_name,
                filter_name=far.field_attr_name,
                filter_value=far.field_attr_value,
                branch_filter=branch_filter,
                branch=self.branch,
                subquery_idx=far.index,
                partial_match=self.partial_match,
                extra_tail_properties=extra_tail_properties,
            )
            for query_var in extra_tail_properties:
                self._track_variable(query_var)
            with_str = ", ".join(
                [
                    f"{subquery_result_name} as {label}" if label == "n" else label
                    for label in self._get_tracked_variables()
                ]
            )

            filter_params.update(subquery_params)
            filter_query.append("CALL (n) {")
            filter_query.append(subquery)
            filter_query.append("}")
            filter_query.append(f"WITH {with_str}")

        if filter_query:
            self.add_to_query(filter_query)
        self.params.update(filter_params)

    async def _add_node_order_attributes(
        self,
        db: InfrahubDatabase,
        field_attribute_requirements: list[FieldAttributeRequirement],
        branch_filter: str,
    ) -> None:
        field_attribute_requirements = [
            far for far in field_attribute_requirements if far.is_order and not far.is_filter
        ]
        if not field_attribute_requirements:
            return

        sort_query: list[str] = []
        sort_params: dict[str, Any] = {}

        for far in field_attribute_requirements:
            if far.field is None:
                continue

            subquery, subquery_params, _ = await build_subquery_order(
                db=db,
                field=far.field,
                name=far.field_name,
                order_by=far.field_attr_name,
                branch_filter=branch_filter,
                branch=self.branch,
                subquery_idx=far.index,
                result_prefix=far.node_value_query_variable,
            )
            self._track_variable(far.node_value_query_variable)
            with_str = ", ".join(self._get_tracked_variables())

            sort_params.update(subquery_params)
            sort_query.append("CALL (n) {")
            sort_query.append(subquery)
            sort_query.append("}")
            sort_query.append(f"WITH {with_str}")

        if sort_query:
            self.add_to_query(sort_query)
        self.params.update(sort_params)

    def _add_final_filter(self, field_attribute_requirements: list[FieldAttributeRequirement]) -> None:
        where_parts = []
        where_str = ""
        for far in field_attribute_requirements:
            if not far.is_filter or not far.is_attribute_value:
                continue
            var_name = f"final_attr_value{far.index}"
            self.params[var_name] = far.field_attr_comparison_value
            if self.partial_match:
                if isinstance(far.field_attr_comparison_value, list):
                    # If the any filter is an array/list
                    var_array = f"{var_name}_array"
                    where_parts.append(
                        f"any({var_array} IN ${var_name} WHERE toLower(toString({far.node_value_query_variable})) CONTAINS toLower({var_array}))"
                    )
                else:
                    where_parts.append(
                        f"toLower(toString({far.node_value_query_variable})) CONTAINS toLower(toString(${var_name}))"
                    )
                continue
            if far.field and isinstance(far.field, AttributeSchema) and far.field.kind == "List":
                if isinstance(far.field_attr_comparison_value, list):
                    self.params[var_name] = build_regex_attrs(values=far.field_attr_comparison_value)
                else:
                    self.params[var_name] = build_regex_attrs(values=[far.field_attr_comparison_value])

                where_parts.append(f"toString({far.node_value_query_variable}) =~ ${var_name}")
                continue

            where_parts.append(f"{far.node_value_query_variable} {far.comparison_operator} ${var_name}")
        if where_parts:
            where_str = "WHERE " + " AND ".join(where_parts)
        self.add_to_query(where_str)

    def _get_field_requirements(self, disable_order: bool) -> list[FieldAttributeRequirement]:
        internal_filters = ["any", "attribute", "relationship"]
        field_requirements_map: dict[tuple[str, str], FieldAttributeRequirement] = {}
        index = 1
        if self.filters:
            for field_name in self.schema.valid_input_names + internal_filters:
                attr_filters = extract_field_filters(field_name=field_name, filters=self.filters)
                if not attr_filters:
                    continue
                field = self.schema.get_field(field_name, raise_on_error=False)
                for field_attr_name, field_attr_value in attr_filters.items():
                    field_requirements_map[field_name, field_attr_name] = FieldAttributeRequirement(
                        field_name=field_name,
                        field=field,
                        field_attr_name=field_attr_name,
                        field_attr_value=field_attr_value.value
                        if isinstance(field_attr_value, Enum)
                        else field_attr_value,
                        index=index,
                        types=[FieldAttributeRequirementType.FILTER],
                    )
                    index += 1

        if disable_order:
            return list(field_requirements_map.values())

        for order_by_path in self.schema.order_by:
            order_by_field_name, order_by_attr_property_name = order_by_path.split("__", maxsplit=1)

            field = self.schema.get_field(order_by_field_name)
            field_req = field_requirements_map.get(
                (order_by_field_name, order_by_attr_property_name),
                FieldAttributeRequirement(
                    field_name=order_by_field_name,
                    field=field,
                    field_attr_name=order_by_attr_property_name,
                    field_attr_value=None,
                    index=index,
                    types=[],
                ),
            )
            field_req.types.append(FieldAttributeRequirementType.ORDER)
            field_requirements_map[order_by_field_name, order_by_attr_property_name] = field_req
            index += 1

        return list(field_requirements_map.values())

    def get_node_ids(self) -> list[str]:
        return [str(result.get("n.uuid")) for result in self.get_results()]


class NodeGetHierarchyQuery(Query):
    name = "node_get_hierarchy"
    type = QueryType.READ

    def __init__(
        self,
        node_id: str,
        direction: RelationshipHierarchyDirection,
        node_schema: NodeSchema | GenericSchema,
        filters: dict | None = None,
        hierarchical_ordering: bool = False,
        **kwargs: Any,
    ) -> None:
        self.filters = filters or {}
        self.direction = direction
        self.node_id = node_id
        self.node_schema = node_schema
        self.hierarchical_ordering = hierarchical_ordering

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002,PLR0915
        hierarchy_schema = self.node_schema.get_hierarchy_schema(db=db, branch=self.branch)
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)
        self.order_by = []
        self.params["uuid"] = self.node_id

        filter_str = "[:IS_RELATED*2..%s { hierarchy: $hierarchy }]" % (
            config.SETTINGS.database.max_depth_search_hierarchy * 2,
        )
        self.params["hierarchy"] = hierarchy_schema.kind

        if self.direction == RelationshipHierarchyDirection.ANCESTORS:
            filter_str = f"-{filter_str}->"
        else:
            filter_str = f"<-{filter_str}-"

        froms_var = db.render_list_comprehension(items="relationships(path)", item_name="from")
        with_clause = (
            "peer, path,"
            " reduce(br_lvl = 0, r in relationships(path) | CASE WHEN r.branch_level > br_lvl THEN r.branch_level ELSE br_lvl END) AS branch_level,"
            f" {froms_var} AS froms"
        )

        query = """
        MATCH path = (n:Node { uuid: $uuid } )%(filter)s(peer:Node)
        WHERE $hierarchy IN LABELS(peer) and all(r IN relationships(path) WHERE (%(branch_filter)s))
        WITH n, collect(last(nodes(path))) AS peers_with_duplicates
        CALL (peers_with_duplicates) {
            UNWIND peers_with_duplicates AS pwd
            RETURN DISTINCT pwd AS peer
        }

        """ % {"filter": filter_str, "branch_filter": branch_filter}

        if not self.branch.is_default:
            query += """
        CALL (n, peer) {
            MATCH path = (n)%(filter)s(peer)
            WHERE all(r IN relationships(path) WHERE (%(branch_filter)s))
            WITH %(with_clause)s
            RETURN peer as peer1, all(r IN relationships(path) WHERE (r.status = "active")) AS is_active
            ORDER BY branch_level DESC, froms[-1] DESC, froms[-2] DESC, is_active DESC
            LIMIT 1
        }
        WITH peer1 as peer, is_active
            """ % {"filter": filter_str, "branch_filter": branch_filter, "with_clause": with_clause}
        else:
            query += """
        WITH peer
            """

        self.add_to_query(query)
        where_clause = ["is_active = TRUE"] if not self.branch.is_default else []

        clean_filters = extract_field_filters(field_name=self.direction.value, filters=self.filters)

        if (clean_filters and "id" in clean_filters) or "ids" in clean_filters:
            where_clause.append("peer.uuid IN $peer_ids")
            self.params["peer_ids"] = clean_filters.get("ids", [])
            if clean_filters.get("id", None):
                self.params["peer_ids"].append(clean_filters.get("id"))

        if where_clause:
            self.add_to_query("WHERE " + " AND ".join(where_clause))

        self.return_labels = ["peer"]

        # ----------------------------------------------------------------------------
        # FILTER Results
        # ----------------------------------------------------------------------------
        filter_cnt = 0
        for peer_filter_name, peer_filter_value in clean_filters.items():
            if "__" not in peer_filter_name:
                continue

            filter_cnt += 1

            filter_field_name, filter_next_name = peer_filter_name.split("__", maxsplit=1)

            if filter_field_name not in hierarchy_schema.valid_input_names:
                continue

            field = hierarchy_schema.get_field(filter_field_name)

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
        # ORDER Results
        # ----------------------------------------------------------------------------
        if self.hierarchical_ordering:
            return
        if hasattr(hierarchy_schema, "order_by") and hierarchy_schema.order_by:
            order_cnt = 1

            for order_by_value in hierarchy_schema.order_by:
                order_by_field_name, order_by_next_name = order_by_value.split("__", maxsplit=1)

                field = hierarchy_schema.get_field(order_by_field_name)

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

    def get_peer_ids(self) -> Generator[str, None, None]:
        for result in self.get_results_group_by(("peer", "uuid")):
            data = result.get("peer").get("uuid")
            yield data

    def get_relatives(self) -> Generator[PeerInfo, None, None]:
        for result in self.get_results_group_by(("peer", "uuid")):
            peer_node = result.get("peer")
            yield PeerInfo(
                uuid=peer_node.get("uuid"),
                kind=peer_node.get("kind"),
                db_id=peer_node.element_id,
            )
