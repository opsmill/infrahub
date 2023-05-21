from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Generator, List, Optional, Tuple, Union

from infrahub.core import registry
from infrahub.core.query import Query, QueryResult, QueryType
from infrahub.core.query.utils import build_subquery_filter, build_subquery_order
from infrahub.core.utils import extract_field_filters
from infrahub.exceptions import QueryError

if TYPE_CHECKING:
    from neo4j import AsyncSession

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.schema import NodeSchema

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


def find_node_schema(node, branch: Union[Branch, str]) -> NodeSchema:
    for label in node.labels:
        if registry.has_schema(name=label, branch=branch):
            return registry.get_schema(name=label, branch=branch)

    return None


class NodeQuery(Query):
    def __init__(
        self,
        node: Node = None,
        node_id: Optional[str] = None,
        node_db_id: Optional[int] = None,
        id=None,
        branch: Branch = None,
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

        self.branch = branch or self.node._branch

        super().__init__(*args, **kwargs)


class NodeCreateQuery(NodeQuery):
    name = "node_create"

    type: QueryType = QueryType.WRITE

    raise_error_if_empty: bool = True

    async def query_init(self, session: AsyncSession, *args, **kwargs):
        self.params["uuid"] = str(uuid.uuid4())
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["kind"] = self.node.get_kind()

        query = (
            """
        MATCH (root:Root)
        CREATE (n:Node:%s { uuid: $uuid, kind: $kind })
        CREATE (n)-[r:IS_PART_OF { branch: $branch, branch_level: $branch_level, status: "active", from: $at }]->(root)
        """
            % self.node.get_kind()
        )

        at = self.at or self.node._at
        self.params["at"] = at.to_string()

        self.add_to_query(query)
        self.return_labels = ["n"]

    def get_new_ids(self) -> Tuple[str, str]:
        result = self.get_result()
        node = result.get("n")

        if node is None:
            raise QueryError(self.get_query(), self.params)

        return node["uuid"], node.element_id


class NodeDeleteQuery(NodeQuery):
    name = "node_delete"

    type: QueryType = QueryType.WRITE

    raise_error_if_empty: bool = True

    async def query_init(self, session: AsyncSession, *args, **kwargs):
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


class NodeListGetLocalAttributeValueQuery(Query):
    name: str = "node_list_get_local_attribute_value"

    def __init__(self, ids: List[str], *args, **kwargs):
        self.ids = ids
        super().__init__(*args, **kwargs)

    async def query_init(self, session: AsyncSession, *args, **kwargs):
        self.params["attrs_ids"] = self.ids

        rel_filter, rel_params = self.branch.get_query_filter_relationships(
            rel_labels=["r1"], at=self.at.to_string(), include_outside_parentheses=False
        )

        self.params.update(rel_params)

        query = (
            """
        MATCH (a:Attribute) WHERE a.uuid IN $attrs_ids
        MATCH (a)-[r1:HAS_VALUE]-(av:AttributeValue)
        WHERE %s
        """
            % rel_filter[0]
        )

        self.add_to_query(query)
        self.return_labels = ["a", "av", "r1"]

    def get_results_by_id(self):
        return {item.get("a").get("uuid"): item for item in self.get_results_group_by(("a", "uuid"), ("a", "name"))}


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

        super().__init__(order_by=["a.name"], *args, **kwargs)

    async def query_init(self, session: AsyncSession, *args, **kwargs):
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
        # TODO NEED TO REVISIT HOW TO INTEGRATE THE PERMISSION SYSTEM

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

    async def query_init(self, session: AsyncSession, *args, **kwargs):
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

    async def query_init(self, session: AsyncSession, *args, **kwargs):
        branches = list(self.branch.get_branches_and_times_to_query().keys())
        self.params["branches"] = branches

        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        query = (
            """
        MATCH p = (root:Root)<-[rb:IS_PART_OF]-(n)
        WHERE all(r IN relationships(p) WHERE ((n.uuid IN $ids) AND %s))
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

    async def query_init(self, session: AsyncSession, *args, **kwargs):
        filter_has_id = False
        self.order_by = []

        self.add_to_query("MATCH p = (root:Root)<-[rb:IS_PART_OF]-(n:Node)")

        # Filter by Node Kind
        where_clause = ["$node_kind IN LABELS(n)"]
        self.params["node_kind"] = self.schema.kind

        # Check 'id' is part of the filter
        # if 'id' is present, we can skip ordering, filtering etc ..
        if self.filters and "id" in self.filters:
            filter_has_id = True
            where_clause.append("n.uuid = $uuid")
            self.params["uuid"] = self.filters["id"]

        # Add the Branch filters
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)
        where_clause.append('all(r IN relationships(p) WHERE r.status = "active" AND (%s))' % branch_filter)

        self.add_to_query("WHERE " + " AND ".join(where_clause))
        self.return_labels = ["n", "rb"]

        if filter_has_id:
            return

        if self.filters:
            # if Filters are provided
            #  Go over all the fields, remove the first part of the query to identify the field
            #  { "name__name": value }

            filter_cnt = 0
            for field_name in self.schema.valid_input_names:
                attr_filters = extract_field_filters(field_name=field_name, filters=self.filters)
                if not attr_filters:
                    continue

                filter_cnt += 1

                field = self.schema.get_field(field_name)

                for field_attr_name, field_attr_value in attr_filters.items():
                    subquery, subquery_params, subquery_result_name = await build_subquery_filter(
                        session=session,
                        field=field,
                        name=field_name,
                        filter_name=field_attr_name,
                        filter_value=field_attr_value,
                        branch_filter=branch_filter,
                        branch=self.branch,
                        subquery_idx=filter_cnt,
                    )
                    self.params.update(subquery_params)

                    with_str = ", ".join(
                        [
                            f"{subquery_result_name} as {label}" if label == "n" else label
                            for label in self.return_labels
                        ]
                    )

                    self.add_to_query("CALL {")
                    self.add_to_query(subquery)
                    self.add_to_query("}")
                    self.add_to_query(f"WITH {with_str}")

        if self.schema.order_by:
            order_cnt = 1

            for order_by_value in self.schema.order_by:
                order_by_field_name, order_by_next_name = order_by_value.split("__", maxsplit=1)

                field = self.schema.get_field(order_by_field_name)

                subquery, subquery_params, subquery_result_name = await build_subquery_order(
                    session=session,
                    field=field,
                    name=order_by_field_name,
                    order_by=order_by_next_name,
                    branch_filter=branch_filter,
                    branch=self.branch,
                    subquery_idx=order_cnt,
                )
                self.order_by.append(subquery_result_name)
                self.params.update(subquery_params)

                with_str = ", ".join(
                    [f"{subquery_result_name} as {label}" if label == "n" else label for label in self.return_labels]
                )

                self.add_to_query("CALL {")
                self.add_to_query(subquery)
                self.add_to_query("}")

                order_cnt += 1

        else:
            self.order_by.append("n.uuid")

    def get_node_ids(self) -> List[str]:
        return [str(result.get("n").get("uuid")) for result in self.get_results()]
