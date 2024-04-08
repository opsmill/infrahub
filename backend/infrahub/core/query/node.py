from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, Generator, List, Optional, Tuple, Union

from infrahub import config
from infrahub.core.constants import RelationshipDirection, RelationshipHierarchyDirection
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
    from infrahub.database import InfrahubDatabase

# pylint: disable=consider-using-f-string,redefined-builtin


@dataclass
class NodeToProcess:
    schema: Optional[NodeSchema]

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
    ):
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
        for attr_name in self.node._attributes:
            attr: BaseAttribute = getattr(self.node, attr_name)
            attributes.append(attr.get_create_data())

        relationships: List[RelationshipCreateData] = []
        for rel_name in self.node._relationships:
            rel_manager: RelationshipManager = getattr(self.node, rel_name)
            for rel in rel_manager._relationships:
                relationships.append(await rel.get_create_data(db=db))

        self.params["attrs"] = [attr.dict() for attr in attributes]
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
        """ % {"labels": ":".join(self.node.get_labels()), "rel_prop": rel_prop_str}

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

    def __init__(self, ids: List[str], account=None, *args, **kwargs):
        self.account = account
        self.ids = ids
        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
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
                profile_uuids=result.get("profile_uuids"),
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


class NodeGetListQuery(Query):
    name = "node_get_list"

    def __init__(
        self, schema: NodeSchema, filters: Optional[dict] = None, partial_match: bool = False, *args, **kwargs
    ):
        self.schema = schema
        self.filters = filters
        self.partial_match = partial_match

        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        filter_has_single_id = False
        self.order_by = []

        final_return_labels = ["n.uuid", "rb.branch", "ID(rb) as rb_id"]

        # Add the Branch filters
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        query = (
            """
        MATCH p = (n:Node)
        WHERE $node_kind IN LABELS(n)
        CALL {
            WITH n
            MATCH (root:Root)<-[r:IS_PART_OF]-(n)
            WHERE %s
            RETURN n as n1, r as r1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as n, r1 as rb
        """
            % branch_filter
        )
        self.add_to_query(query)
        self.params["node_kind"] = self.schema.kind

        where_clause = ['rb.status = "active"']

        # Check 'id' or 'ids' is part of the filter
        # if 'id' is present, we can skip ordering, filtering etc ..
        # if 'ids' is present, we keep the filtering and the ordering
        if self.filters and "id" in self.filters:
            filter_has_single_id = True
            where_clause.append("n.uuid = $uuid")
            self.params["uuid"] = self.filters["id"]
        elif self.filters and "ids" in self.filters:
            where_clause.append("n.uuid IN $node_ids")
            self.params["node_ids"] = self.filters["ids"]

        self.add_to_query("WHERE " + " AND ".join(where_clause))
        self.return_labels = ["n", "rb"]

        if filter_has_single_id:
            self.return_labels = final_return_labels
            return

        if self.filters:
            filter_query, filter_params = await self.build_filters(
                db=db, filters=self.filters, branch_filter=branch_filter
            )

            self.add_to_query(filter_query)
            self.params.update(filter_params)

        self.return_labels = final_return_labels
        await self._set_order_by(db=db, branch_filter=branch_filter)

    async def _set_order_by(self, db: InfrahubDatabase, branch_filter: str) -> None:
        if not self.schema.order_by:
            self.order_by.append("n.uuid")
            return

        order_cnt = 1

        for order_by_path in self.schema.order_by:
            order_by_field_name, order_by_attr_property_name = order_by_path.split("__", maxsplit=1)

            field = self.schema.get_field(order_by_field_name)

            subquery, subquery_params, subquery_result_name = await build_subquery_order(
                db=db,
                field=field,
                name=order_by_field_name,
                order_by=order_by_attr_property_name,
                branch_filter=branch_filter,
                branch=self.branch,
                subquery_idx=order_cnt,
            )
            self.order_by.append(subquery_result_name)
            self.params.update(subquery_params)

            self.add_subquery(subquery=subquery)

            order_cnt += 1

    async def build_filters(
        self, db: InfrahubDatabase, filters: Dict[str, Any], branch_filter: str
    ) -> Tuple[List[str], Dict[str, Any]]:
        filter_query: List[str] = []
        filter_params: Dict[str, Any] = {}
        filter_cnt = 0

        INTERNAL_FILTERS: List[str] = ["any", "attribute", "relationship"]

        for field_name in self.schema.valid_input_names + INTERNAL_FILTERS:
            attr_filters = extract_field_filters(field_name=field_name, filters=filters)
            if not attr_filters:
                continue

            filter_cnt += 1

            field = self.schema.get_field(field_name, raise_on_error=False)

            for field_attr_name, field_attr_value in attr_filters.items():
                subquery, subquery_params, subquery_result_name = await build_subquery_filter(
                    db=db,
                    field=field,
                    name=field_name,
                    filter_name=field_attr_name,
                    filter_value=field_attr_value,
                    branch_filter=branch_filter,
                    branch=self.branch,
                    subquery_idx=filter_cnt,
                    partial_match=self.partial_match,
                )
                filter_params.update(subquery_params)

                with_str = ", ".join(
                    [f"{subquery_result_name} as {label}" if label == "n" else label for label in self.return_labels]
                )

                filter_query.append("CALL {")
                filter_query.append(subquery)
                filter_query.append("}")
                filter_query.append(f"WITH {with_str}")

        return filter_query, filter_params

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
        *args,
        **kwargs,
    ):
        self.filters = filters or {}
        self.direction = direction
        self.node_id = node_id
        self.node_schema = node_schema

        super().__init__(*args, **kwargs)

        self.hierarchy_schema = node_schema.get_hierarchy_schema(self.branch)

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):  # pylint: disable=too-many-statements
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
