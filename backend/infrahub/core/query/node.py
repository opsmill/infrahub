from __future__ import annotations

from collections import defaultdict
from copy import copy
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from enum import Enum
from typing import TYPE_CHECKING, Any, AsyncIterator, Generator

from infrahub import config
from infrahub.core import registry
from infrahub.core.constants import (
    AttributeDBNodeType,
    RelationshipDirection,
    RelationshipHierarchyDirection,
)
from infrahub.core.query import Query, QueryResult, QueryType
from infrahub.core.query.subquery import build_subquery_filter, build_subquery_order
from infrahub.core.query.utils import find_node_schema
from infrahub.core.schema.attribute_schema import AttributeSchema
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

    node_id: str
    node_uuid: str
    profile_uuids: list[str]

    updated_at: str

    branch: str

    labels: list[str]


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

    updated_at: str

    branch: str

    is_default: bool
    is_from_profile: bool = dataclass_field(default=False)

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
        node: Node | None = None,
        node_id: str | None = None,
        node_db_id: int | None = None,
        id: str | None = None,
        branch: Branch | None = None,
        **kwargs,
    ) -> None:
        # TODO Validate that Node is a valid node
        # Eventually extract the branch from Node as well
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

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:  # noqa: ARG002
        at = self.at or self.node._at
        self.params["uuid"] = self.node.id
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["kind"] = self.node.get_kind()
        self.params["branch_support"] = self.node._schema.branch

        attributes: list[AttributeCreateData] = []
        attributes_iphost: list[AttributeCreateData] = []
        attributes_ipnetwork: list[AttributeCreateData] = []

        for attr_name in self.node._attributes:
            attr: BaseAttribute = getattr(self.node, attr_name)
            attr_data = attr.get_create_data()

            if attr_data.node_type == AttributeDBNodeType.IPHOST:
                attributes_iphost.append(attr_data)
            elif attr_data.node_type == AttributeDBNodeType.IPNETWORK:
                attributes_ipnetwork.append(attr_data)
            else:
                attributes.append(attr_data)

        relationships: list[RelationshipCreateData] = []
        for rel_name in self.node._relationships:
            rel_manager: RelationshipManager = getattr(self.node, rel_name)
            for rel in rel_manager._relationships:
                relationships.append(await rel.get_create_data(db=db))

        self.params["attrs"] = [attr.model_dump() for attr in attributes]
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
        self.params["node_branch_prop"] = {
            "branch": self.branch.name,
            "branch_level": self.branch.hierarchy_level,
            "status": "active",
            "from": at.to_string(),
        }

        rel_prop_str = "{ branch: rel.branch, branch_level: rel.branch_level, status: rel.status, hierarchy: rel.hierarchical, from: $at }"

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
            # "num_addresses": "attr.content.num_addresses",
        }
        ipnetwork_prop_list = [f"{key}: {value}" for key, value in ipnetwork_prop.items()]

        attrs_query = """
        WITH distinct n
        UNWIND $attrs AS attr
        CALL (n, attr) {
            CREATE (a:Attribute { uuid: attr.uuid, name: attr.name, branch_support: attr.branch_support })
            CREATE (n)-[:HAS_ATTRIBUTE { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at }]->(a)
            MERGE (av:AttributeValue { value: attr.content.value, is_default: attr.content.is_default })
            WITH av, a
            LIMIT 1
            CREATE (a)-[:HAS_VALUE { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at }]->(av)
            MERGE (ip:Boolean { value: attr.is_protected })
            MERGE (iv:Boolean { value: attr.is_visible })
            CREATE (a)-[:IS_PROTECTED { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at }]->(ip)
            CREATE (a)-[:IS_VISIBLE { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at }]->(iv)
            FOREACH ( prop IN attr.source_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (a)-[:HAS_SOURCE { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at }]->(peer)
            )
            FOREACH ( prop IN attr.owner_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (a)-[:HAS_OWNER { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at }]->(peer)
            )
        }"""

        attrs_iphost_query = """
        WITH distinct n
        UNWIND $attrs_iphost AS attr_iphost
        CALL (n, attr_iphost) {
            WITH n, attr_iphost AS attr
            CREATE (a:Attribute { uuid: attr.uuid, name: attr.name, branch_support: attr.branch_support })
            CREATE (n)-[:HAS_ATTRIBUTE { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at }]->(a)
            MERGE (av:AttributeValue:AttributeIPHost { %(iphost_prop)s })
            WITH attr, av, a
            LIMIT 1
            CREATE (a)-[:HAS_VALUE { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at }]->(av)
            MERGE (ip:Boolean { value: attr.is_protected })
            MERGE (iv:Boolean { value: attr.is_visible })
            CREATE (a)-[:IS_PROTECTED { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at }]->(ip)
            CREATE (a)-[:IS_VISIBLE { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at }]->(iv)
            FOREACH ( prop IN attr.source_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (a)-[:HAS_SOURCE { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at }]->(peer)
            )
            FOREACH ( prop IN attr.owner_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (a)-[:HAS_OWNER { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at }]->(peer)
            )
        }
        """ % {"iphost_prop": ", ".join(iphost_prop_list)}

        attrs_ipnetwork_query = """
        WITH distinct n
        UNWIND $attrs_ipnetwork AS attr_ipnetwork
        CALL (n, attr_ipnetwork) {
            WITH n, attr_ipnetwork AS attr
            CREATE (a:Attribute { uuid: attr.uuid, name: attr.name, branch_support: attr.branch_support })
            CREATE (n)-[:HAS_ATTRIBUTE { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at }]->(a)
            MERGE (av:AttributeValue:AttributeIPNetwork { %(ipnetwork_prop)s })
            WITH attr, av, a
            LIMIT 1
            CREATE (a)-[:HAS_VALUE { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at }]->(av)
            MERGE (ip:Boolean { value: attr.is_protected })
            MERGE (iv:Boolean { value: attr.is_visible })
            CREATE (a)-[:IS_PROTECTED { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at }]->(ip)
            CREATE (a)-[:IS_VISIBLE { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at }]->(iv)
            FOREACH ( prop IN attr.source_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (a)-[:HAS_SOURCE { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at }]->(peer)
            )
            FOREACH ( prop IN attr.owner_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (a)-[:HAS_OWNER { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at }]->(peer)
            )
        }
        """ % {"ipnetwork_prop": ", ".join(ipnetwork_prop_list)}

        rels_bidir_query = """
        WITH distinct n
        UNWIND $rels_bidir AS rel
        CALL (n, rel) {
            MERGE (d:Node { uuid: rel.destination_id })
            CREATE (rl:Relationship { uuid: rel.uuid, name: rel.name, branch_support: rel.branch_support })
            CREATE (n)-[:IS_RELATED %(rel_prop)s ]->(rl)
            CREATE (d)-[:IS_RELATED %(rel_prop)s ]->(rl)
            MERGE (ip:Boolean { value: rel.is_protected })
            MERGE (iv:Boolean { value: rel.is_visible })
            CREATE (rl)-[:IS_PROTECTED { branch: rel.branch, branch_level: rel.branch_level, status: rel.status, from: $at }]->(ip)
            CREATE (rl)-[:IS_VISIBLE { branch: rel.branch, branch_level: rel.branch_level, status: rel.status, from: $at }]->(iv)
            FOREACH ( prop IN rel.source_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (rl)-[:HAS_SOURCE { branch: rel.branch, branch_level: rel.branch_level, status: rel.status, from: $at }]->(peer)
            )
            FOREACH ( prop IN rel.owner_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (rl)-[:HAS_OWNER { branch: rel.branch, branch_level: rel.branch_level, status: rel.status, from: $at }]->(peer)
            )
        }
        """ % {"rel_prop": rel_prop_str}

        rels_out_query = """
        WITH distinct n
        UNWIND $rels_out AS rel_out
        CALL (n, rel_out) {
            WITH n, rel_out as rel
            MERGE (d:Node { uuid: rel.destination_id })
            CREATE (rl:Relationship { uuid: rel.uuid, name: rel.name, branch_support: rel.branch_support })
            CREATE (n)-[:IS_RELATED %(rel_prop)s ]->(rl)
            CREATE (d)<-[:IS_RELATED %(rel_prop)s ]-(rl)
            MERGE (ip:Boolean { value: rel.is_protected })
            MERGE (iv:Boolean { value: rel.is_visible })
            CREATE (rl)-[:IS_PROTECTED { branch: rel.branch, branch_level: rel.branch_level, status: rel.status, from: $at }]->(ip)
            CREATE (rl)-[:IS_VISIBLE { branch: rel.branch, branch_level: rel.branch_level, status: rel.status, from: $at }]->(iv)
            FOREACH ( prop IN rel.source_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (rl)-[:HAS_SOURCE { branch: rel.branch, branch_level: rel.branch_level, status: rel.status, from: $at }]->(peer)
            )
            FOREACH ( prop IN rel.owner_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (rl)-[:HAS_OWNER { branch: rel.branch, branch_level: rel.branch_level, status: rel.status, from: $at }]->(peer)
            )
        }
        """ % {"rel_prop": rel_prop_str}

        rels_in_query = """
        WITH distinct n
        UNWIND $rels_in AS rel_in
        CALL (n, rel_in) {
            WITH n, rel_in AS rel
            MERGE (d:Node { uuid: rel.destination_id })
            CREATE (rl:Relationship { uuid: rel.uuid, name: rel.name, branch_support: rel.branch_support })
            CREATE (n)<-[:IS_RELATED %(rel_prop)s ]-(rl)
            CREATE (d)-[:IS_RELATED %(rel_prop)s ]->(rl)
            MERGE (ip:Boolean { value: rel.is_protected })
            MERGE (iv:Boolean { value: rel.is_visible })
            CREATE (rl)-[:IS_PROTECTED { branch: rel.branch, branch_level: rel.branch_level, status: rel.status, from: $at }]->(ip)
            CREATE (rl)-[:IS_VISIBLE { branch: rel.branch, branch_level: rel.branch_level, status: rel.status, from: $at }]->(iv)
            FOREACH ( prop IN rel.source_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (rl)-[:HAS_SOURCE { branch: rel.branch, branch_level: rel.branch_level, status: rel.status, from: $at }]->(peer)
            )
            FOREACH ( prop IN rel.owner_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (rl)-[:HAS_OWNER { branch: rel.branch, branch_level: rel.branch_level, status: rel.status, from: $at }]->(peer)
            )
        }
        """ % {"rel_prop": rel_prop_str}

        query = f"""
        MATCH (root:Root)
        CREATE (n:Node:%(labels)s $node_prop )
        CREATE (n)-[r:IS_PART_OF $node_branch_prop ]->(root)
        {attrs_query if self.params["attrs"] else ""}
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

    raise_error_if_empty: bool = True

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:  # noqa: ARG002
        self.params["uuid"] = self.node_id
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level

        if self.branch.is_global or self.branch.is_default:
            node_query_match = """
            MATCH (n:Node { uuid: $uuid })
            OPTIONAL MATCH (n)-[delete_edge:IS_PART_OF {status: "deleted", branch: $branch}]->(:Root)
            WHERE delete_edge.from <= $at
            WITH n WHERE delete_edge IS NULL
            """
        else:
            node_filter, node_filter_params = self.branch.get_query_filter_path(at=self.at, variable_name="r")
            node_query_match = """
                MATCH (n:Node { uuid: $uuid })
                CALL (n) {
                    MATCH (n)-[r:IS_PART_OF]->(:Root)
                    WHERE %(node_filter)s
                    RETURN r.status = "active" AS is_active
                    ORDER BY r.from DESC
                    LIMIT 1
                }
                WITH n WHERE is_active = TRUE
                """ % {"node_filter": node_filter}
            self.params.update(node_filter_params)
        self.add_to_query(node_query_match)

        query = """
        MATCH (root:Root)
        CREATE (n)-[r:IS_PART_OF { branch: $branch, branch_level: $branch_level, status: "deleted", from: $at }]->(root)
        """

        self.params["at"] = self.at.to_string()

        self.add_to_query(query)
        self.return_labels = ["n"]


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
        "IS_VISIBLE": ("rel_isv", "isv"),
    }

    def __init__(
        self,
        ids: list[str],
        fields: dict | None = None,
        include_source: bool = False,
        include_owner: bool = False,
        account=None,
        **kwargs,
    ):
        self.account = account
        self.ids = ids
        self.fields = fields
        self.include_source = include_source
        self.include_owner = include_owner

        super().__init__(order_by=["n.uuid", "a.name"], **kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:  # noqa: ARG002
        self.params["ids"] = self.ids

        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at, branch_agnostic=self.branch_agnostic
        )
        self.params.update(branch_params)

        query = """
        MATCH (n:Node) WHERE n.uuid IN $ids
        MATCH (n)-[:HAS_ATTRIBUTE]-(a:Attribute)
        """
        if self.fields:
            query += "\n WHERE a.name IN $field_names"
            self.params["field_names"] = list(self.fields.keys())

        self.add_to_query(query)

        query = """
        CALL (n, a) {
            MATCH (n)-[r:HAS_ATTRIBUTE]-(a:Attribute)
            WHERE %(branch_filter)s
            RETURN n as n1, r as r1, a as a1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as n, r1, a1 as a
        WHERE r1.status = "active"
        WITH n, r1, a
        MATCH (a)-[r:HAS_VALUE]-(av:AttributeValue)
        WHERE %(branch_filter)s
        CALL (a, av) {
            MATCH (a)-[r:HAS_VALUE]-(av:AttributeValue)
            WHERE %(branch_filter)s
            RETURN a as a1, r as r2, av as av1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n, r1, a1 as a, r2, av1 as av
        WHERE r2.status = "active"
        WITH n, a, av, r1, r2
        """ % {"branch_filter": branch_filter}
        self.add_to_query(query)

        self.return_labels = ["n", "a", "av", "r1", "r2"]

        # Add Is_Protected and Is_visible
        rel_isv_branch_filter, _ = self.branch.get_query_filter_path(
            at=self.at, branch_agnostic=self.branch_agnostic, variable_name="rel_isv"
        )
        rel_isp_branch_filter, _ = self.branch.get_query_filter_path(
            at=self.at, branch_agnostic=self.branch_agnostic, variable_name="rel_isp"
        )
        query = """
        MATCH (a)-[rel_isv:IS_VISIBLE]-(isv:Boolean)
        MATCH (a)-[rel_isp:IS_PROTECTED]-(isp:Boolean)
        WHERE (%(rel_isv_branch_filter)s) AND (%(rel_isp_branch_filter)s)
        """ % {"rel_isv_branch_filter": rel_isv_branch_filter, "rel_isp_branch_filter": rel_isp_branch_filter}
        self.add_to_query(query)

        self.return_labels.extend(["isv", "isp", "rel_isv", "rel_isp"])

        if self.include_source:
            query = """
            OPTIONAL MATCH (a)-[rel_source:HAS_SOURCE]-(source)
            WHERE all(r IN [rel_source] WHERE ( %(branch_filter)s ))
            """ % {"branch_filter": branch_filter}
            self.add_to_query(query)
            self.return_labels.extend(["source", "rel_source"])

        if self.include_owner:
            query = """
            OPTIONAL MATCH (a)-[rel_owner:HAS_OWNER]-(owner)
            WHERE all(r IN [rel_owner] WHERE ( %(branch_filter)s ))
            """ % {"branch_filter": branch_filter}
            self.add_to_query(query)
            self.return_labels.extend(["owner", "rel_owner"])

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

        data = AttributeFromDB(
            name=attr.get("name"),
            attr_labels=list(attr.labels),
            attr_id=attr.element_id,
            attr_uuid=attr.get("uuid"),
            attr_value_id=attr_value.element_id,
            attr_value_uuid=attr_value.get("uuid"),
            updated_at=result.get_rel("r2").get("from"),
            value=attr_value.get("value"),
            is_default=attr_value.get("is_default"),
            content=attr_value._properties,
            branch=self.branch.name,
            flag_properties={
                "is_protected": result.get("isp").get("value"),
                "is_visible": result.get("isv").get("value"),
            },
        )

        if self.include_source and result.get("source"):
            data.node_properties["source"] = AttributeNodePropertyFromDB(
                uuid=result.get_node("source").get("uuid"), labels=list(result.get_node("source").labels)
            )

        if self.include_owner and result.get("owner"):
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

    def add_peer(self, node_id: str, rel_name: str, peer_id: str, direction: RelationshipDirection) -> None:
        self._rel_names_by_node_id[node_id].add(rel_name)
        if direction not in self._rel_directions_map[node_id, rel_name]:
            self._rel_directions_map[node_id, rel_name][direction] = set()
        self._rel_directions_map[node_id, rel_name][direction].add(peer_id)

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


class NodeListGetRelationshipsQuery(Query):
    name: str = "node_list_get_relationship"
    type: QueryType = QueryType.READ
    insert_return: bool = False

    def __init__(
        self,
        ids: list[str],
        outbound_identifiers: list[str] | None = None,
        inbound_identifiers: list[str] | None = None,
        bidirectional_identifiers: list[str] | None = None,
        **kwargs,
    ):
        self.ids = ids
        self.outbound_identifiers = outbound_identifiers
        self.inbound_identifiers = inbound_identifiers
        self.bidirectional_identifiers = bidirectional_identifiers
        super().__init__(**kwargs)

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
                RETURN 1 AS is_active
            }
            RETURN n.uuid AS n_uuid, rel.name AS rel_name, peer.uuid AS peer_uuid, "inbound" as direction
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
                RETURN 1 AS is_active
            }
            RETURN n.uuid AS n_uuid, rel.name AS rel_name, peer.uuid AS peer_uuid, "outbound" as direction
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
                RETURN 1 AS is_active
            }
            RETURN n.uuid AS n_uuid, rel.name AS rel_name, peer.uuid AS peer_uuid, "bidirectional" as direction
        }
        RETURN DISTINCT n_uuid, rel_name, peer_uuid, direction
        """ % {"filters": rels_filter}
        self.add_to_query(query)
        self.return_labels = ["n_uuid", "rel_name", "peer_uuid", "direction"]

    def get_peers_group_by_node(self) -> GroupedPeerNodes:
        gpn = GroupedPeerNodes()
        for result in self.get_results():
            node_id = result.get("n_uuid")
            rel_name = result.get("rel_name")
            peer_id = result.get("peer_uuid")
            direction = str(result.get("direction"))
            direction_enum = {
                "inbound": RelationshipDirection.INBOUND,
                "outbound": RelationshipDirection.OUTBOUND,
                "bidirectional": RelationshipDirection.BIDIR,
            }.get(direction)
            gpn.add_peer(node_id=node_id, rel_name=rel_name, peer_id=peer_id, direction=direction_enum)

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

    def __init__(self, ids: list[str], account=None, **kwargs: Any) -> None:
        self.account = account
        self.ids = ids
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at, branch_agnostic=self.branch_agnostic
        )
        self.params.update(branch_params)

        query = """
        MATCH p = (root:Root)<-[:IS_PART_OF]-(n:Node)
        WHERE n.uuid IN $ids
        CALL (root, n) {
            MATCH (root:Root)<-[r:IS_PART_OF]-(n:Node)
            WHERE %(branch_filter)s
            RETURN n as n1, r as r1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as n, r1 as rb
        WHERE rb.status = "active"
        OPTIONAL MATCH profile_path = (n)-[:IS_RELATED]->(profile_r:Relationship)<-[:IS_RELATED]-(profile:Node)-[:IS_PART_OF]->(:Root)
        WHERE profile_r.name = "node__profile"
        AND profile.namespace = "Profile"
        AND all(r in relationships(profile_path) WHERE %(branch_filter)s and r.status = "active")
        """ % {"branch_filter": branch_filter}

        self.add_to_query(query)
        self.params["ids"] = self.ids

        self.return_labels = ["collect(profile.uuid) as profile_uuids", "n", "rb"]

    async def get_nodes(self, db: InfrahubDatabase, duplicate: bool = False) -> AsyncIterator[NodeToProcess]:
        """Return all the node objects as NodeToProcess."""

        for result in self.get_results_group_by(("n", "uuid")):
            schema = find_node_schema(db=db, node=result.get_node("n"), branch=self.branch, duplicate=duplicate)
            node_branch = self.branch
            if self.branch_agnostic:
                node_branch = result.get_rel("rb").get("branch")
            yield NodeToProcess(
                schema=schema,
                node_id=result.get_node("n").element_id,
                node_uuid=result.get_node("n").get("uuid"),
                profile_uuids=[str(puuid) for puuid in result.get("profile_uuids")],
                updated_at=result.get_rel("rb").get("from"),
                branch=node_branch,
                labels=list(result.get_node("n").labels),
            )

    def get_profile_ids_by_node_id(self) -> dict[str, list[str]]:
        profile_id_map: dict[str, list[str]] = {}
        for result in self.results:
            node_id = result.get_node("n").get("uuid")
            profile_ids = result.get("profile_uuids")
            if not node_id or not profile_ids:
                continue
            if node_id not in profile_id_map:
                profile_id_map[node_id] = []
            profile_id_map[node_id].extend(profile_ids)
        return profile_id_map


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
    def supports_profile(self) -> bool:
        return bool(self.field and self.field.is_attribute and self.field_attr_name in ("value", "values", "isnull"))

    @property
    def is_filter(self) -> bool:
        return FieldAttributeRequirementType.FILTER in self.types

    @property
    def is_order(self) -> bool:
        return FieldAttributeRequirementType.ORDER in self.types

    @property
    def is_default_query_variable(self) -> str:
        return f"attr{self.index}_is_default"

    @property
    def node_value_query_variable(self) -> str:
        return f"attr{self.index}_node_value"

    @property
    def profile_value_query_variable(self) -> str:
        return f"attr{self.index}_profile_value"

    @property
    def profile_final_value_query_variable(self) -> str:
        return f"attr{self.index}_final_profile_value"

    @property
    def final_value_query_variable(self) -> str:
        return f"attr{self.index}_final_value"

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
        try:
            self._variables_to_track.remove(variable)
        except ValueError:
            ...

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
        use_profiles = any(far for far in field_attribute_requirements if far.supports_profile)
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
                if far.supports_profile:
                    self.order_by.append(far.final_value_query_variable)
                    continue
                self.order_by.append(far.node_value_query_variable)

        # Always order by uuid to guarantee pagination, see https://github.com/opsmill/infrahub/pull/4704.
        self.order_by.append("n.uuid")

        if use_profiles:
            await self._add_profiles_per_node_query(db=db, branch_filter=branch_filter)
            await self._add_profile_attributes(
                db=db, field_attribute_requirements=field_attribute_requirements, branch_filter=branch_filter
            )
            await self._add_profile_rollups(field_attribute_requirements=field_attribute_requirements)

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
            if far.supports_profile:
                extra_tail_properties[far.is_default_query_variable] = "is_default"
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
                support_profiles=far.supports_profile,
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
            extra_tail_properties = {}
            if far.supports_profile:
                extra_tail_properties[far.is_default_query_variable] = "is_default"

            subquery, subquery_params, _ = await build_subquery_order(
                db=db,
                field=far.field,
                name=far.field_name,
                order_by=far.field_attr_name,
                branch_filter=branch_filter,
                branch=self.branch,
                subquery_idx=far.index,
                result_prefix=far.node_value_query_variable,
                support_profiles=far.supports_profile,
                extra_tail_properties=extra_tail_properties,
            )
            for query_var in extra_tail_properties:
                self._track_variable(query_var)
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

    async def _add_profiles_per_node_query(self, db: InfrahubDatabase, branch_filter: str) -> None:
        with_str = ", ".join(self._get_tracked_variables())
        froms_str = db.render_list_comprehension(items="relationships(profile_path)", item_name="from")
        profiles_per_node_query = (
            """
            CALL (n) {
                OPTIONAL MATCH profile_path = (n)-[:IS_RELATED]->(profile_r:Relationship)<-[:IS_RELATED]-(maybe_profile_n:Node)-[:IS_PART_OF]->(:Root)
                WHERE profile_r.name = "node__profile"
                AND all(r in relationships(profile_path) WHERE %(branch_filter)s)
                WITH
                    maybe_profile_n,
                    profile_path,
                    reduce(br_lvl = 0, r in relationships(profile_path) | br_lvl + r.branch_level) AS branch_level,
                    %(froms_str)s AS froms,
                    all(r in relationships(profile_path) WHERE r.status = "active") AS is_active
                RETURN maybe_profile_n, is_active, branch_level, froms
            }
            WITH %(with_str)s, maybe_profile_n, branch_level, froms, is_active
            ORDER BY n.uuid, maybe_profile_n.uuid, branch_level DESC, froms[-1] DESC, froms[-2] DESC, froms[-3] DESC
            WITH %(with_str)s, maybe_profile_n, collect(is_active) as ordered_is_actives
            WITH %(with_str)s, CASE
                WHEN ordered_is_actives[0] = True THEN maybe_profile_n ELSE NULL
            END AS profile_n
            CALL (profile_n) {
                OPTIONAL MATCH profile_priority_path = (profile_n)-[pr1:HAS_ATTRIBUTE]->(a:Attribute)-[pr2:HAS_VALUE]->(av:AttributeValue)
                WHERE a.name = "profile_priority"
                AND all(r in relationships(profile_priority_path) WHERE %(branch_filter)s and r.status = "active")
                RETURN av.value as profile_priority
                ORDER BY pr1.branch_level + pr2.branch_level DESC, pr2.from DESC, pr1.from DESC
                LIMIT 1
            }
            WITH %(with_str)s, profile_n, profile_priority
            """
        ) % {"branch_filter": branch_filter, "with_str": with_str, "froms_str": froms_str}
        self.add_to_query(profiles_per_node_query)
        self._track_variable("profile_n")
        self._track_variable("profile_priority")

    async def _add_profile_attributes(
        self, db: InfrahubDatabase, field_attribute_requirements: list[FieldAttributeRequirement], branch_filter: str
    ) -> None:
        attributes_queries: list[str] = []
        attributes_params: dict[str, Any] = {}
        profile_attributes = [far for far in field_attribute_requirements if far.supports_profile]

        for profile_attr in profile_attributes:
            if not profile_attr.field:
                continue
            subquery, subquery_params, _ = await build_subquery_order(
                db=db,
                field=profile_attr.field,
                node_alias="profile_n",
                name=profile_attr.field_name,
                order_by=profile_attr.field_attr_name,
                branch_filter=branch_filter,
                branch=self.branch,
                subquery_idx=profile_attr.index,
                result_prefix=profile_attr.profile_value_query_variable,
                support_profiles=False,
            )
            attributes_params.update(subquery_params)
            self._track_variable(profile_attr.profile_value_query_variable)
            with_str = ", ".join(self._get_tracked_variables())

            attributes_queries.append("CALL (profile_n) {")
            attributes_queries.append(subquery)
            attributes_queries.append("}")
            attributes_queries.append(f"WITH {with_str}")

        self.add_to_query(attributes_queries)
        self.params.update(attributes_params)

    async def _add_profile_rollups(self, field_attribute_requirements: list[FieldAttributeRequirement]) -> None:
        profile_attributes = [far for far in field_attribute_requirements if far.supports_profile]
        profile_value_collects = []
        for profile_attr in profile_attributes:
            self._untrack_variable(profile_attr.profile_value_query_variable)
            profile_value_collects.append(
                f"""head(
                    reduce(
                        non_null_values = [], v in collect({profile_attr.profile_value_query_variable}) |
                        CASE WHEN v IS NOT NULL AND v <> "NULL" THEN non_null_values + [v] ELSE non_null_values END
                    )
                ) as {profile_attr.profile_final_value_query_variable}"""
            )
        self._untrack_variable("profile_n")
        self._untrack_variable("profile_priority")
        profile_rollup_with_str = ", ".join(self._get_tracked_variables() + profile_value_collects)
        profile_rollup_query = f"""
        ORDER BY n.uuid, profile_priority ASC, profile_n.uuid ASC
        WITH {profile_rollup_with_str}
        """
        self.add_to_query(profile_rollup_query)
        for profile_attr in profile_attributes:
            self._track_variable(profile_attr.profile_final_value_query_variable)

        final_value_with = []
        for profile_attr in profile_attributes:
            final_value_with.append(f"""
            CASE
                WHEN {profile_attr.is_default_query_variable} AND {profile_attr.profile_final_value_query_variable} IS NOT NULL
                THEN {profile_attr.profile_final_value_query_variable}
                ELSE {profile_attr.node_value_query_variable}
            END AS {profile_attr.final_value_query_variable}
            """)
            self._untrack_variable(profile_attr.is_default_query_variable)
            self._untrack_variable(profile_attr.profile_final_value_query_variable)
            self._untrack_variable(profile_attr.node_value_query_variable)
        final_value_with_str = ", ".join(self._get_tracked_variables() + final_value_with)
        self.add_to_query(f"WITH {final_value_with_str}")

    def _add_final_filter(self, field_attribute_requirements: list[FieldAttributeRequirement]) -> None:
        where_parts = []
        where_str = ""
        for far in field_attribute_requirements:
            if not far.is_filter or not far.supports_profile:
                continue
            var_name = f"final_attr_value{far.index}"
            self.params[var_name] = far.field_attr_comparison_value
            if self.partial_match:
                if isinstance(far.field_attr_comparison_value, list):
                    # If the any filter is an array/list
                    var_array = f"{var_name}_array"
                    where_parts.append(
                        f"any({var_array} IN ${var_name} WHERE toLower(toString({far.final_value_query_variable})) CONTAINS toLower({var_array}))"
                    )
                else:
                    where_parts.append(
                        f"toLower(toString({far.final_value_query_variable})) CONTAINS toLower(toString(${var_name}))"
                    )
                continue
            if far.field and isinstance(far.field, AttributeSchema) and far.field.kind == "List":
                if isinstance(far.field_attr_comparison_value, list):
                    self.params[var_name] = build_regex_attrs(values=far.field_attr_comparison_value)
                else:
                    self.params[var_name] = build_regex_attrs(values=[far.field_attr_comparison_value])

                where_parts.append(f"toString({far.final_value_query_variable}) =~ ${var_name}")
                continue

            where_parts.append(f"{far.final_value_query_variable} {far.comparison_operator} ${var_name}")
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
