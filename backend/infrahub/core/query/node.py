from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Generator, List, Optional, Tuple

from infrahub import config
from infrahub.core.constants import RelationshipDirection
from infrahub.core.query import Query, QueryResult, QueryType
from infrahub.core.query.subquery import build_subquery_filter, build_subquery_order
from infrahub.core.query.utils import find_node_schema
from infrahub.core.utils import extract_field_filters
from infrahub.exceptions import QueryError

if TYPE_CHECKING:
    from infrahub.core.attribute import AttributeCreateData, BaseAttribute
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.relationship import RelationshipCreateData, RelationshipManager
    from infrahub.core.schema import GenericSchema, NodeSchema
    from infrahub.database import InfrahubDatabase

# pylint: disable=consider-using-f-string,redefined-builtin


@dataclass
class NodeToProcess:
    schema: NodeSchema

    node_id: int
    node_uuid: str

    updated_at: str

    branch: str


@dataclass
class AttrToProcess:
    name: str
    type: str

    attr_labels: List[str]
    attr_id: int
    attr_uuid: str

    attr_value_id: int
    attr_value_uuid: Optional[str]
    value: Any

    updated_at: str

    branch: str

    # permission: PermissionLevel

    # time_from: Optional[str]
    # time_to: Optional[str]

    source_uuid: Optional[str]
    source_labels: Optional[List[str]]

    owner_uuid: Optional[str]
    owner_labels: Optional[List[str]]

    is_inherited: Optional[bool]
    is_protected: Optional[bool]
    is_visible: Optional[bool]


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
        CREATE (n:Node:%s $node_prop )
        CREATE (n)-[r:IS_PART_OF $node_branch_prop ]->(root)
        WITH distinct n
        FOREACH ( attr IN $attrs |
            CREATE (a:Attribute:AttributeLocal { uuid: attr.uuid, name: attr.name, type: attr.type, branch_support: attr.branch_support })
            CREATE (n)-[:HAS_ATTRIBUTE { branch: attr.branch, branch_level: attr.branch_level, status: attr.status, from: $at, to: null }]->(a)
            MERGE (av:AttributeValue { type: attr.type, value: attr.value })
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
            CREATE (n)-[:IS_RELATED %s ]->(rl)
            CREATE (d)-[:IS_RELATED %s ]->(rl)
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
            CREATE (n)-[:IS_RELATED %s ]->(rl)
            CREATE (d)<-[:IS_RELATED %s ]-(rl)
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
            CREATE (n)<-[:IS_RELATED %s ]-(rl)
            CREATE (d)-[:IS_RELATED %s ]->(rl)
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
        """ % (
            ":".join(self.node.get_labels()),
            rel_prop_str,
            rel_prop_str,
            rel_prop_str,
            rel_prop_str,
            rel_prop_str,
            rel_prop_str,
        )

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
        MATCH (n { uuid: $uuid })
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

        rels_filter, rels_params = self.branch.get_query_filter_path(at=self.at)
        self.params.update(rels_params)

        query = """
        MATCH (n) WHERE n.uuid IN $ids
        MATCH p = ((n)-[r1:HAS_ATTRIBUTE]-(a:Attribute)-[r2:HAS_VALUE]-(av))
        """

        if self.fields:
            query += "\n WHERE all(r IN relationships(p) WHERE ((a.name IN $field_names) AND %s))" % rels_filter
            self.params["field_names"] = list(self.fields.keys())
        else:
            query += "\n WHERE all(r IN relationships(p) WHERE ( %s))" % rels_filter

        self.add_to_query(query)

        self.return_labels = ["n", "a", "av", "r1", "r2"]

        # Add Is_Protected and Is_visible
        query = (
            """
        MATCH (a)-[rel_isv:IS_VISIBLE]-(isv:Boolean)
        MATCH (a)-[rel_isp:IS_PROTECTED]-(isp:Boolean)
        WHERE all(r IN [rel_isv, rel_isp] WHERE ( %s))
        """
            % rels_filter
        )
        self.add_to_query(query)

        self.return_labels.extend(["isv", "isp", "rel_isv", "rel_isp"])

        if self.include_source:
            query = (
                """
            OPTIONAL MATCH (a)-[rel_source:HAS_SOURCE]-(source)
            WHERE all(r IN [rel_source] WHERE ( %s))
            """
                % rels_filter
            )
            self.add_to_query(query)
            self.return_labels.extend(["source", "rel_source"])

        if self.include_owner:
            query = (
                """
            OPTIONAL MATCH (a)-[rel_owner:HAS_OWNER]-(owner)
            WHERE all(r IN [rel_owner] WHERE ( %s))
            """
                % rels_filter
            )
            self.add_to_query(query)
            self.return_labels.extend(["owner", "rel_owner"])

    # def query_add_permission(self):

    #     rels_filter_perms, rels_params = self.branch.get_query_filter_relationships(
    #         rel_labels=["r4", "r5", "r6", "r7"], at=self.at, include_outside_parentheses=True
    #     )
    #     self.params.update(rels_params)

    #     query = """
    #     WITH %s
    #     MATCH (account) WHERE ID(account) = $account_id
    #     MATCH (a)-[r4:IS_MEMBER_OF]-(ag:AttrGroup)-[r5:CAN_READ|CAN_WRITE]-(perm:Permission)-[r6:HAS_PERM]-(g:Group)-[r7:IS_MEMBER_OF]-(account)
    #     WHERE %s
    #     """ % (
    #         ",".join(self.return_labels),
    #         "\n AND ".join(rels_filter_perms),
    #     )

    #     self.add_to_query(query)

    #     self.params["account_id"] = self.account.id

    #     self.return_labels.extend(["r5"])

    def get_attributes_group_by_node(self) -> Dict[str, Dict[str, AttrToProcess]]:
        attrs_by_node = defaultdict(lambda: {"node": None, "attrs": None})

        for result in self.get_results_group_by(("n", "uuid"), ("a", "name")):
            node_id = result.get("n").get("uuid")
            attr_name = result.get("a").get("name")
            attr = AttrToProcess(
                name=attr_name,
                type=result.get("a").get("type"),
                attr_labels=result.get("a").labels,
                attr_id=result.get("a").element_id,
                attr_uuid=result.get("a").get("uuid"),
                attr_value_id=result.get("av").element_id,
                attr_value_uuid=result.get("av").get("uuid"),
                updated_at=result.get("r2").get("from"),
                value=result.get("av").get("value"),
                # permission=result.permission_score,
                branch=self.branch.name,
                is_inherited=None,
                is_protected=result.get("isp").get("value"),
                is_visible=result.get("isv").get("value"),
                source_uuid=None,
                source_labels=None,
                owner_uuid=None,
                owner_labels=None,
            )

            if self.include_source and result.get("source"):
                attr.source_uuid = result.get("source").get("uuid")
                attr.source_labels = result.get("source").labels

            if self.include_owner and result.get("owner"):
                attr.owner_uuid = result.get("owner").get("uuid")
                attr.owner_labels = result.get("owner").labels

            if node_id not in attrs_by_node:
                attrs_by_node[node_id]["node"] = result.get("n")
                attrs_by_node[node_id]["attrs"] = {}

            attrs_by_node[node_id]["attrs"][attr_name] = attr

        return attrs_by_node

    def get_result_by_id_and_name(self, node_id: str, attr_name: str) -> QueryResult:
        for result in self.get_results_group_by(("n", "uuid"), ("a", "name")):
            if result.get("n").get("uuid") == node_id and result.get("a").get("name") == attr_name:
                return result

        return None


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

        query = (
            """
        MATCH p = (root:Root)<-[rb:IS_PART_OF]-(n)
        WHERE (n.uuid IN $ids) AND all(r IN relationships(p) WHERE (%s))
        """
            % branch_filter
        )

        self.add_to_query(query)

        self.params["ids"] = self.ids

        self.return_labels = ["n", "rb"]

    async def get_nodes(self) -> Generator[NodeToProcess, None, None]:
        """Return all the node objects as NodeToProcess."""

        for result in self.get_results_group_by(("n", "uuid")):
            schema = find_node_schema(node=result.get("n"), branch=self.branch)
            yield NodeToProcess(
                schema=schema,
                node_id=result.get("n").element_id,
                node_uuid=result.get("n").get("uuid"),
                updated_at=result.get("rb").get("from"),
                branch=self.branch,
            )


class NodeGetListQuery(Query):
    name = "node_get_list"

    def __init__(self, schema: NodeSchema, filters: Optional[dict] = None, *args, **kwargs):
        self.schema = schema
        self.filters = filters

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

        if self.schema.order_by:
            order_cnt = 1

            for order_by_value in self.schema.order_by:
                order_by_field_name, order_by_next_name = order_by_value.split("__", maxsplit=1)

                field = self.schema.get_field(order_by_field_name)

                subquery, subquery_params, subquery_result_name = await build_subquery_order(
                    db=db,
                    field=field,
                    name=order_by_field_name,
                    order_by=order_by_next_name,
                    branch_filter=branch_filter,
                    branch=self.branch,
                    subquery_idx=order_cnt,
                )
                self.order_by.append(subquery_result_name)
                self.params.update(subquery_params)

                self.add_to_query("CALL {")
                self.add_to_query(subquery)
                self.add_to_query("}")

                order_cnt += 1

        else:
            self.order_by.append("n.uuid")

        self.return_labels = final_return_labels

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
    # insert_return: bool = False

    def __init__(
        self,
        node_id: str,
        direction: str,
        node_schema: NodeSchema,
        hierarchy_schema: GenericSchema,
        filters: Optional[dict] = None,
        *args,
        **kwargs,
    ):
        self.filters = filters or {}
        self.direction = direction
        self.node_id = node_id
        self.node_schema = node_schema
        self.hierarchy_schema = hierarchy_schema

        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):  # pylint: disable=too-many-statements
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)
        self.order_by = []
        self.params["uuid"] = self.node_id

        filter_str = "[:IS_RELATED*2..%s { hierarchy: $hierarchy }]" % (
            config.SETTINGS.schema_.max_depth_search_hierarchy * 2,
        )
        self.params["hierarchy"] = self.hierarchy_schema.kind

        if self.direction == "ancestors":
            filter_str = f"-{filter_str}->"
        else:
            filter_str = f"<-{filter_str}-"

        with_clause = (
            "peer, path, extract(r in relationships(path) | r.branch_level) as branch_levels,"
            " extract(r in relationships(path) | r.from) as froms"
        )

        query = """
        MATCH path = (n:Node { uuid: $uuid } )%s(peer:Node)
        WHERE $hierarchy IN LABELS(peer) and all(r IN relationships(path) WHERE (%s))
        CALL {
            WITH n, last(nodes(path)) as peer
            MATCH path = (n)%s(peer)
            WHERE all(r IN relationships(path) WHERE (%s))
            WITH %s
            RETURN peer as peer1, path as path1
            ORDER BY reduce(acc = [], i in RANGE(1,size(branch_levels)) | acc + branch_levels[i] + froms[i]) DESC
            LIMIT 1
        }
        WITH peer1 as peer, path1 as path
        """ % (filter_str, branch_filter, filter_str, branch_filter, with_clause)

        self.add_to_query(query)
        where_clause = ['all(r IN relationships(path) WHERE (r.status = "active"))']

        # clean_filters = extract_field_filters(field_name=self.schema.name, filters=self.filters)

        if self.filters and "id" in self.filters or "ids" in self.filters:
            where_clause.append("peer.uuid IN $peer_ids")
            self.params["peer_ids"] = self.filters.get("ids", [])
            if self.filters.get("id", None):
                self.params["peer_ids"].append(self.filters.get("id"))

        self.add_to_query("WHERE " + " AND ".join(where_clause))

        self.return_labels = ["peer"]

        # ----------------------------------------------------------------------------
        # FILTER Results
        # ----------------------------------------------------------------------------
        # filter_cnt = 0
        # for peer_filter_name, peer_filter_value in clean_filters.items():
        #     if "__" not in peer_filter_name:
        #         continue

        #     filter_cnt += 1

        #     filter_field_name, filter_next_name = peer_filter_name.split("__", maxsplit=1)

        #     if filter_field_name not in peer_schema.valid_input_names:
        #         continue

        #     field = peer_schema.get_field(filter_field_name)

        #     subquery, subquery_params, subquery_result_name = await build_subquery_filter(
        #         db=db,
        #         node_alias="peer",
        #         field=field,
        #         name=filter_field_name,
        #         filter_name=filter_next_name,
        #         filter_value=peer_filter_value,
        #         branch_filter=branch_filter,
        #         branch=self.branch,
        #         subquery_idx=filter_cnt,
        #     )
        #     self.params.update(subquery_params)

        #     with_str = ", ".join(
        #         [f"{subquery_result_name} as {label}" if label == "peer" else label for label in self.return_labels]
        #     )

        #     self.add_to_query("CALL {")
        #     self.add_to_query(subquery)
        #     self.add_to_query("}")
        #     self.add_to_query(f"WITH {with_str}")

        # ----------------------------------------------------------------------------
        # ORDER Results
        # ----------------------------------------------------------------------------
        # if hasattr(peer_schema, "order_by") and peer_schema.order_by:
        #     order_cnt = 1

        #     for order_by_value in peer_schema.order_by:
        #         order_by_field_name, order_by_next_name = order_by_value.split("__", maxsplit=1)

        #         field = peer_schema.get_field(order_by_field_name)

        #         subquery, subquery_params, subquery_result_name = await build_subquery_order(
        #             db=db,
        #             field=field,
        #             node_alias="peer",
        #             name=order_by_field_name,
        #             order_by=order_by_next_name,
        #             branch_filter=branch_filter,
        #             branch=self.branch,
        #             subquery_idx=order_cnt,
        #         )
        #         self.order_by.append(subquery_result_name)
        #         self.params.update(subquery_params)

        #         with_str = ", ".join(
        #             [f"{subquery_result_name} as {label}" if label == "n" else label for label in self.return_labels]
        #         )

        #         self.add_to_query("CALL {")
        #         self.add_to_query(subquery)
        #         self.add_to_query("}")

        #         order_cnt += 1

        # else:
        self.order_by.append("peer.uuid")

    def get_peer_ids(self) -> Generator[str, None, None]:
        for result in self.get_results_group_by(("peer", "uuid")):
            data = result.get("peer").get("uuid")
            yield data
