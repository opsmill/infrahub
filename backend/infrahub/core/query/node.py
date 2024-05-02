from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from enum import Enum
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, Generator, List, Optional, Tuple, Union

from infrahub import config
from infrahub.core.constants import AttributeDBNodeType, RelationshipDirection, RelationshipHierarchyDirection
from infrahub.core.query import Query, QueryResult, QueryType
from infrahub.core.query.subquery import build_subquery_filter, build_subquery_order
from infrahub.core.query.utils import find_node_schema
from infrahub.core.utils import extract_field_filters
from infrahub.exceptions import QueryError

if TYPE_CHECKING:
    from neo4j.graph import Node as Neo4jNode

    from infrahub.core.attribute import AttributeCreateData, BaseAttribute
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.relationship import RelationshipCreateData, RelationshipManager
    from infrahub.core.schema import GenericSchema, NodeSchema
    from infrahub.core.schema.attribute_schema import AttributeSchema
    from infrahub.core.schema.profile_schema import ProfileSchema
    from infrahub.core.schema.relationship_schema import RelationshipSchema
    from infrahub.database import InfrahubDatabase

# pylint: disable=consider-using-f-string,redefined-builtin,too-many-lines


@dataclass
class NodeToProcess:
    schema: Optional[Union[NodeSchema, ProfileSchema]]

    node_id: str
    node_uuid: str
    profile_uuids: list[str]

    updated_at: str

    branch: str

    labels: List[str]


@dataclass
class AttributeNodePropertyFromDB:
    uuid: str
    labels: List[str]


@dataclass
class AttributeFromDB:
    name: str

    attr_labels: List[str]
    attr_id: str
    attr_uuid: str

    attr_value_id: str
    attr_value_uuid: Optional[str]

    value: Any
    content: Any

    updated_at: str

    branch: str

    is_default: bool
    is_from_profile: bool = dataclass_field(default=False)

    node_properties: Dict[str, AttributeNodePropertyFromDB] = dataclass_field(default_factory=dict)
    flag_properties: Dict[str, bool] = dataclass_field(default_factory=dict)


@dataclass
class NodeAttributesFromDB:
    node: Neo4jNode
    attrs: Dict[str, AttributeFromDB] = dataclass_field(default_factory=dict)


class NodeQuery(Query):
    def __init__(
        self,
        node: Optional[Node] = None,
        node_id: Optional[str] = None,
        node_db_id: Optional[int] = None,
        id: Optional[str] = None,
        branch: Optional[Branch] = None,
        *args,
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

        super().__init__(*args, **kwargs)


class NodeCreateAllQuery(NodeQuery):
    name = "node_create_all"

    type: QueryType = QueryType.WRITE

    raise_error_if_empty: bool = True

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        at = self.at or self.node._at
        self.params["uuid"] = self.node.id
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["kind"] = self.node.get_kind()
        self.params["branch_support"] = self.node._schema.branch

        attributes: List[AttributeCreateData] = []
        attributes_iphost: List[AttributeCreateData] = []
        attributes_ipnetwork: List[AttributeCreateData] = []

        for attr_name in self.node._attributes:
            attr: BaseAttribute = getattr(self.node, attr_name)
            attr_data = attr.get_create_data()

            if attr_data.node_type == AttributeDBNodeType.IPHOST:
                attributes_iphost.append(attr_data)
            elif attr_data.node_type == AttributeDBNodeType.IPNETWORK:
                attributes_ipnetwork.append(attr_data)
            else:
                attributes.append(attr_data)

        relationships: List[RelationshipCreateData] = []
        for rel_name in self.node._relationships:
            rel_manager: RelationshipManager = getattr(self.node, rel_name)
            for rel in rel_manager._relationships:
                relationships.append(await rel.get_create_data(db=db))

        self.params["attrs"] = [attr.dict() for attr in attributes]
        self.params["attrs_iphost"] = [attr.dict() for attr in attributes_iphost]
        self.params["attrs_ipnetwork"] = [attr.dict() for attr in attributes_ipnetwork]
        self.params["rels_bidir"] = [
            rel.dict() for rel in relationships if rel.direction == RelationshipDirection.BIDIR.value
        ]
        self.params["rels_out"] = [
            rel.dict() for rel in relationships if rel.direction == RelationshipDirection.OUTBOUND.value
        ]
        self.params["rels_in"] = [
            rel.dict() for rel in relationships if rel.direction == RelationshipDirection.INBOUND.value
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

        rel_prop_str = "{ branch: rel.branch, branch_level: rel.branch_level, status: rel.status, hierarchy: rel.hierarchical, from: $at, to: null }"

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

        query = """
        MATCH (root:Root)
        CREATE (n:Node:%(labels)s $node_prop )
        CREATE (n)-[r:IS_PART_OF $node_branch_prop ]->(root)
        WITH distinct n
        FOREACH ( attr IN $attrs |
            CREATE (a:Attribute { uuid: attr.uuid, name: attr.name, branch_support: attr.branch_support })
            CREATE (n)-[:HAS_ATTRIBUTE { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at, to: null }]->(a)
            MERGE (av:AttributeValue { value: attr.content.value, is_default: attr.content.is_default })
            CREATE (a)-[:HAS_VALUE { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at, to: null }]->(av)
            MERGE (ip:Boolean { value: attr.is_protected })
            MERGE (iv:Boolean { value: attr.is_visible })
            CREATE (a)-[:IS_PROTECTED { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at, to: null }]->(ip)
            CREATE (a)-[:IS_VISIBLE { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at, to: null }]->(iv)
            FOREACH ( prop IN attr.source_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (a)-[:HAS_SOURCE { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at, to: null }]->(peer)
            )
            FOREACH ( prop IN attr.owner_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (a)-[:HAS_OWNER { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at, to: null }]->(peer)
            )
        )
        FOREACH ( attr IN $attrs_iphost |
            CREATE (a:Attribute { uuid: attr.uuid, name: attr.name, branch_support: attr.branch_support })
            CREATE (n)-[:HAS_ATTRIBUTE { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at, to: null }]->(a)
            MERGE (av:AttributeValue:AttributeIPHost { %(iphost_prop)s })
            CREATE (a)-[:HAS_VALUE { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at, to: null }]->(av)
            MERGE (ip:Boolean { value: attr.is_protected })
            MERGE (iv:Boolean { value: attr.is_visible })
            CREATE (a)-[:IS_PROTECTED { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at, to: null }]->(ip)
            CREATE (a)-[:IS_VISIBLE { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at, to: null }]->(iv)
            FOREACH ( prop IN attr.source_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (a)-[:HAS_SOURCE { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at, to: null }]->(peer)
            )
            FOREACH ( prop IN attr.owner_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (a)-[:HAS_OWNER { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at, to: null }]->(peer)
            )
        )
        FOREACH ( attr IN $attrs_ipnetwork |
            CREATE (a:Attribute { uuid: attr.uuid, name: attr.name, branch_support: attr.branch_support })
            CREATE (n)-[:HAS_ATTRIBUTE { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at, to: null }]->(a)
            MERGE (av:AttributeValue:AttributeIPNetwork { %(ipnetwork_prop)s })
            CREATE (a)-[:HAS_VALUE { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at, to: null }]->(av)
            MERGE (ip:Boolean { value: attr.is_protected })
            MERGE (iv:Boolean { value: attr.is_visible })
            CREATE (a)-[:IS_PROTECTED { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at, to: null }]->(ip)
            CREATE (a)-[:IS_VISIBLE { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at, to: null }]->(iv)
            FOREACH ( prop IN attr.source_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (a)-[:HAS_SOURCE { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at, to: null }]->(peer)
            )
            FOREACH ( prop IN attr.owner_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (a)-[:HAS_OWNER { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at, to: null }]->(peer)
            )
        )
        FOREACH ( rel IN $rels_bidir |
            MERGE (d:Node { uuid: rel.destination_id })
            CREATE (rl:Relationship { uuid: rel.uuid, name: rel.name, branch_support: rel.branch_support })
            CREATE (n)-[:IS_RELATED %(rel_prop)s ]->(rl)
            CREATE (d)-[:IS_RELATED %(rel_prop)s ]->(rl)
            MERGE (ip:Boolean { value: rel.is_protected })
            MERGE (iv:Boolean { value: rel.is_visible })
            CREATE (rl)-[:IS_PROTECTED { branch: rel.branch, branch_level: rel.branch_level, status: rel.status, from: $at, to: null }]->(ip)
            CREATE (rl)-[:IS_VISIBLE { branch: rel.branch, branch_level: rel.branch_level, status: rel.status, from: $at, to: null }]->(iv)
            FOREACH ( prop IN rel.source_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (rl)-[:HAS_SOURCE { branch: rel.branch, branch_level: rel.branch_level, status: rel.status, from: $at, to: null }]->(peer)
            )
            FOREACH ( prop IN rel.owner_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (rl)-[:HAS_OWNER { branch: rel.branch, branch_level: rel.branch_level, status: rel.status, from: $at, to: null }]->(peer)
            )
        )
        FOREACH ( rel IN $rels_out |
            MERGE (d:Node { uuid: rel.destination_id })
            CREATE (rl:Relationship { uuid: rel.uuid, name: rel.name, branch_support: rel.branch_support })
            CREATE (n)-[:IS_RELATED %(rel_prop)s ]->(rl)
            CREATE (d)<-[:IS_RELATED %(rel_prop)s ]-(rl)
            MERGE (ip:Boolean { value: rel.is_protected })
            MERGE (iv:Boolean { value: rel.is_visible })
            CREATE (rl)-[:IS_PROTECTED { branch: rel.branch, branch_level: rel.branch_level, status: rel.status, from: $at, to: null }]->(ip)
            CREATE (rl)-[:IS_VISIBLE { branch: rel.branch, branch_level: rel.branch_level, status: rel.status, from: $at, to: null }]->(iv)
            FOREACH ( prop IN rel.source_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (rl)-[:HAS_SOURCE { branch: rel.branch, branch_level: rel.branch_level, status: rel.status, from: $at, to: null }]->(peer)
            )
            FOREACH ( prop IN rel.owner_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (rl)-[:HAS_OWNER { branch: rel.branch, branch_level: rel.branch_level, status: rel.status, from: $at, to: null }]->(peer)
            )
        )
        FOREACH ( rel IN $rels_in |
            MERGE (d:Node { uuid: rel.destination_id })
            CREATE (rl:Relationship { uuid: rel.uuid, name: rel.name, branch_support: rel.branch_support })
            CREATE (n)<-[:IS_RELATED %(rel_prop)s ]-(rl)
            CREATE (d)-[:IS_RELATED %(rel_prop)s ]->(rl)
            MERGE (ip:Boolean { value: rel.is_protected })
            MERGE (iv:Boolean { value: rel.is_visible })
            CREATE (rl)-[:IS_PROTECTED { branch: rel.branch, branch_level: rel.branch_level, status: rel.status, from: $at, to: null }]->(ip)
            CREATE (rl)-[:IS_VISIBLE { branch: rel.branch, branch_level: rel.branch_level, status: rel.status, from: $at, to: null }]->(iv)
            FOREACH ( prop IN rel.source_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (rl)-[:HAS_SOURCE { branch: rel.branch, branch_level: rel.branch_level, status: rel.status, from: $at, to: null }]->(peer)
            )
            FOREACH ( prop IN rel.owner_prop |
                MERGE (peer:Node { uuid: prop.peer_id })
                CREATE (rl)-[:HAS_OWNER { branch: rel.branch, branch_level: rel.branch_level, status: rel.status, from: $at, to: null }]->(peer)
            )
        )
        WITH distinct n
        MATCH (n)-[:HAS_ATTRIBUTE|IS_RELATED]-(rn)-[:HAS_VALUE|IS_RELATED]-(rv)
        """ % {
            "labels": ":".join(self.node.get_labels()),
            "rel_prop": rel_prop_str,
            "iphost_prop": ", ".join(iphost_prop_list),
            "ipnetwork_prop": ", ".join(ipnetwork_prop_list),
        }

        self.params["at"] = at.to_string()

        self.add_to_query(query)
        self.return_labels = ["n", "rn", "rv"]

    def get_self_ids(self) -> Tuple[str, str]:
        result = self.get_result()
        node = result.get("n")

        if node is None:
            raise QueryError(self.get_query(), self.params)

        return node["uuid"], node.element_id

    def get_ids(self) -> Dict[str, Tuple[str, str]]:
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

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        self.params["uuid"] = self.node_id
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level

        query = """
        MATCH (root:Root)
        MATCH (n:Node { uuid: $uuid })
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
        *args,
        **kwargs,
    ):
        self.node_id = node_id
        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        self.params["uuid"] = self.node_id

        query = """
        MATCH (root:Root)-[]-(n:Node { uuid: $uuid })
        """

        self.add_to_query(query)
        self.return_labels = ["n"]


class NodeListGetAttributeQuery(Query):
    name: str = "node_list_get_attribute"

    property_type_mapping = {
        "HAS_VALUE": ("r2", "av"),
        "HAS_OWNER": ("rel_owner", "owner"),
        "HAS_SOURCE": ("rel_source", "source"),
        "IS_PROTECTED": ("rel_isp", "isp"),
        "IS_VISIBLE": ("rel_isv", "isv"),
    }

    def __init__(
        self,
        ids: List[str],
        fields: Optional[dict] = None,
        include_source: bool = False,
        include_owner: bool = False,
        account=None,
        *args,
        **kwargs,
    ):
        self.account = account
        self.ids = ids
        self.fields = fields
        self.include_source = include_source
        self.include_owner = include_owner

        super().__init__(order_by=["n.uuid", "a.name"], *args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        self.params["ids"] = self.ids

        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
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
        CALL {
            WITH n, a
            MATCH (n)-[r:HAS_ATTRIBUTE]-(a:Attribute)
            WHERE %(branch_filter)s
            RETURN n as n1, r as r1, a as a1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as n, r1, a1 as a
        WHERE r1.status = "active"
        WITH n, r1, a
        MATCH (a)-[:HAS_VALUE]-(av:AttributeValue)
        CALL {
            WITH a, av
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
        query = """
        MATCH (a)-[rel_isv:IS_VISIBLE]-(isv:Boolean)
        MATCH (a)-[rel_isp:IS_PROTECTED]-(isp:Boolean)
        WHERE all(r IN [rel_isv, rel_isp] WHERE ( %(branch_filter)s ))
        """ % {"branch_filter": branch_filter}
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

    def get_attributes_group_by_node(self) -> Dict[str, NodeAttributesFromDB]:
        attrs_by_node: Dict[str, NodeAttributesFromDB] = {}

        for result in self.get_results_group_by(("n", "uuid"), ("a", "name")):
            node_id: str = result.get_node("n").get("uuid")
            attr_name: str = result.get_node("a").get("name")

            attr = self._extract_attribute_data(result=result)

            if node_id not in attrs_by_node:
                attrs_by_node[node_id] = NodeAttributesFromDB(node=result.get_node("n"))

            attrs_by_node[node_id].attrs[attr_name] = attr

        return attrs_by_node

    def get_result_by_id_and_name(self, node_id: str, attr_name: str) -> Tuple[AttributeFromDB, QueryResult]:
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


class NodeListGetRelationshipsQuery(Query):
    name: str = "node_list_get_relationship"

    def __init__(
        self,
        ids: List[str],
        *args,
        **kwargs,
    ):
        self.ids = ids

        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        self.params["ids"] = self.ids

        rels_filter, rels_params = self.branch.get_query_filter_path(at=self.at)
        self.params.update(rels_params)

        query = (
            """
        MATCH (n) WHERE n.uuid IN $ids
        MATCH p = ((n)-[r1:IS_RELATED]-(rel:Relationship)-[r2:IS_RELATED]-(peer))
        WHERE all(r IN relationships(p) WHERE (%s))
        """
            % rels_filter
        )

        self.add_to_query(query)

        self.return_labels = ["n", "rel", "peer", "r1", "r2"]

    def get_peers_group_by_node(self) -> Dict[str, Dict[str, List[str]]]:
        peers_by_node = defaultdict(lambda: defaultdict(list))

        for result in self.get_results_group_by(("n", "uuid"), ("rel", "name"), ("peer", "uuid")):
            node_id = result.get("n").get("uuid")
            rel_name = result.get("rel").get("name")
            peer_id = result.get("peer").get("uuid")

            peers_by_node[node_id][rel_name].append(peer_id)

        return peers_by_node


class NodeListGetInfoQuery(Query):
    name: str = "node_list_get_info"

    def __init__(self, ids: List[str], account=None, *args: Any, **kwargs: Any) -> None:
        self.account = account
        self.ids = ids
        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: Any) -> None:
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        query = """
        MATCH p = (root:Root)<-[:IS_PART_OF]-(n:Node)
        WHERE n.uuid IN $ids
        CALL {
            WITH root, n
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

    async def get_nodes(self, duplicate: bool = True) -> AsyncIterator[NodeToProcess]:
        """Return all the node objects as NodeToProcess."""

        for result in self.get_results_group_by(("n", "uuid")):
            schema = find_node_schema(node=result.get_node("n"), branch=self.branch, duplicate=duplicate)
            yield NodeToProcess(
                schema=schema,
                node_id=result.get_node("n").element_id,
                node_uuid=result.get_node("n").get("uuid"),
                profile_uuids=[str(puuid) for puuid in result.get("profile_uuids")],
                updated_at=result.get_rel("rb").get("from"),
                branch=self.branch.name,
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
    field: Optional[Union[AttributeSchema, RelationshipSchema]]
    field_attr_name: str
    field_attr_value: Any
    index: int
    types: list[FieldAttributeRequirementType] = dataclass_field(default_factory=list)

    @property
    def supports_profile(self) -> bool:
        return bool(self.field and self.field.is_attribute and self.field_attr_name in ("value", "values"))

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


class NodeGetListQuery(Query):
    name = "node_get_list"

    def __init__(
        self, schema: NodeSchema, filters: Optional[dict] = None, partial_match: bool = False, *args: Any, **kwargs: Any
    ) -> None:
        self.schema = schema
        self.filters = filters
        self.partial_match = partial_match
        self._variables_to_track = ["n", "rb"]

        super().__init__(*args, **kwargs)

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

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: Any) -> None:
        self.order_by = []
        self.params["node_kind"] = self.schema.kind

        self.return_labels = ["n.uuid", "rb.branch", "ID(rb) as rb_id"]
        where_clause_elements = []

        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        query = """
        MATCH p = (n:Node)
        WHERE $node_kind IN LABELS(n)
        CALL {
            WITH n
            MATCH (root:Root)<-[r:IS_PART_OF]-(n)
            WHERE %(branch_filter)s
            RETURN r
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n, r as rb
        WHERE rb.status = "active"
        """ % {"branch_filter": branch_filter}
        self.add_to_query(query)
        use_simple = False
        if self.filters and "id" in self.filters:
            use_simple = True
            where_clause_elements.append("n.uuid = $uuid")
            self.params["uuid"] = self.filters["id"]
        if not self.filters and not self.schema.order_by:
            use_simple = True
            self.order_by = ["n.uuid"]
        if use_simple:
            if where_clause_elements:
                self.add_to_query(" AND " + " AND ".join(where_clause_elements))
            return

        if self.filters and "ids" in self.filters:
            self.add_to_query("AND n.uuid IN $node_ids")
            self.params["node_ids"] = self.filters["ids"]

        field_attribute_requirements = self._get_field_requirements()
        use_profiles = any(far for far in field_attribute_requirements if far.supports_profile)
        await self._add_node_filter_attributes(
            db=db, field_attribute_requirements=field_attribute_requirements, branch_filter=branch_filter
        )
        await self._add_node_order_attributes(
            db=db, field_attribute_requirements=field_attribute_requirements, branch_filter=branch_filter
        )

        if use_profiles:
            await self._add_profiles_per_node_query(db=db, branch_filter=branch_filter)
            await self._add_profile_attributes(
                db=db, field_attribute_requirements=field_attribute_requirements, branch_filter=branch_filter
            )
            await self._add_profile_rollups(field_attribute_requirements=field_attribute_requirements)

        self._add_final_filter(field_attribute_requirements=field_attribute_requirements)
        self.order_by = []
        for far in field_attribute_requirements:
            if not far.is_order:
                continue
            if far.supports_profile:
                self.order_by.append(far.final_value_query_variable)
                continue
            self.order_by.append(far.node_value_query_variable)

    async def _add_node_filter_attributes(
        self,
        db: InfrahubDatabase,
        field_attribute_requirements: list[FieldAttributeRequirement],
        branch_filter: str,
    ) -> None:
        field_attribute_requirements = [far for far in field_attribute_requirements if far.is_filter]
        if not field_attribute_requirements:
            return

        filter_query: List[str] = []
        filter_params: Dict[str, Any] = {}

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
            filter_query.append("CALL {")
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

        sort_query: List[str] = []
        sort_params: Dict[str, Any] = {}

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
            sort_query.append("CALL {")
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
            CALL {
                WITH n
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
            CALL {
                WITH profile_n
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
        attributes_queries: List[str] = []
        attributes_params: Dict[str, Any] = {}
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

            attributes_queries.append("CALL {")
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
            self.params[var_name] = far.field_attr_value
            if self.partial_match:
                where_parts.append(
                    f"toLower(toString({far.final_value_query_variable})) CONTAINS toLower(toString(${var_name}))"
                )
                continue
            if far.field_attr_name == "values":
                operator = "IN"
            else:
                operator = "="

            where_parts.append(f"{far.final_value_query_variable} {operator} ${var_name}")
        if where_parts:
            where_str = "WHERE " + " AND ".join(where_parts)
        self.add_to_query(where_str)

    def _get_field_requirements(self) -> list[FieldAttributeRequirement]:
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
                    field_requirements_map[(field_name, field_attr_name)] = FieldAttributeRequirement(
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
        if not self.schema.order_by:
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
            field_requirements_map[(order_by_field_name, order_by_attr_property_name)] = field_req
            index += 1

        return list(field_requirements_map.values())

    def get_node_ids(self) -> List[str]:
        return [str(result.get("n.uuid")) for result in self.get_results()]


class NodeGetHierarchyQuery(Query):
    name = "node_get_hierarchy"

    type: QueryType = QueryType.READ

    def __init__(
        self,
        node_id: str,
        direction: RelationshipHierarchyDirection,
        node_schema: Union[NodeSchema, GenericSchema],
        filters: Optional[dict] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.filters = filters or {}
        self.direction = direction
        self.node_id = node_id
        self.node_schema = node_schema

        super().__init__(*args, **kwargs)

        self.hierarchy_schema = node_schema.get_hierarchy_schema(self.branch)

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: Any) -> None:  # pylint: disable=too-many-statements
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)
        self.order_by = []
        self.params["uuid"] = self.node_id

        filter_str = "[:IS_RELATED*2..%s { hierarchy: $hierarchy }]" % (
            config.SETTINGS.database.max_depth_search_hierarchy * 2,
        )
        self.params["hierarchy"] = self.hierarchy_schema.kind

        if self.direction == RelationshipHierarchyDirection.ANCESTORS:
            filter_str = f"-{filter_str}->"
        else:
            filter_str = f"<-{filter_str}-"

        froms_var = db.render_list_comprehension(items="relationships(path)", item_name="from")
        with_clause = (
            "peer, path,"
            " reduce(br_lvl = 0, r in relationships(path) | br_lvl + r.branch_level) AS branch_level,"
            f" {froms_var} AS froms"
        )

        query = """
        MATCH path = (n:Node { uuid: $uuid } )%(filter)s(peer:Node)
        WHERE $hierarchy IN LABELS(peer) and all(r IN relationships(path) WHERE (%(branch_filter)s))
        WITH n, last(nodes(path)) as peer
        CALL {
            WITH n, peer
            MATCH path = (n)%(filter)s(peer)
            WHERE all(r IN relationships(path) WHERE (%(branch_filter)s))
            WITH %(with_clause)s
            RETURN peer as peer1, path as path1
            ORDER BY branch_level DESC, froms[-1] DESC, froms[-2] DESC
            LIMIT 1
        }
        WITH peer1 as peer, path1 as path
        """ % {"filter": filter_str, "branch_filter": branch_filter, "with_clause": with_clause}

        self.add_to_query(query)
        where_clause = ['all(r IN relationships(path) WHERE (r.status = "active"))']

        clean_filters = extract_field_filters(field_name=self.direction.value, filters=self.filters)

        if clean_filters and "id" in clean_filters or "ids" in clean_filters:
            where_clause.append("peer.uuid IN $peer_ids")
            self.params["peer_ids"] = clean_filters.get("ids", [])
            if clean_filters.get("id", None):
                self.params["peer_ids"].append(clean_filters.get("id"))

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

            if filter_field_name not in self.hierarchy_schema.valid_input_names:
                continue

            field = self.hierarchy_schema.get_field(filter_field_name)

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
        # ORDER Results
        # ----------------------------------------------------------------------------
        if hasattr(self.hierarchy_schema, "order_by") and self.hierarchy_schema.order_by:
            order_cnt = 1

            for order_by_value in self.hierarchy_schema.order_by:
                order_by_field_name, order_by_next_name = order_by_value.split("__", maxsplit=1)

                field = self.hierarchy_schema.get_field(order_by_field_name)

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

    def get_peer_ids(self) -> Generator[str, None, None]:
        for result in self.get_results_group_by(("peer", "uuid")):
            data = result.get("peer").get("uuid")
            yield data
