from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

from infrahub.core.query import Query, QueryType
from infrahub.core.schema import NodeSchema
from infrahub.exceptions import QueryError


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

    changed_at: str

    branch: str

    # permission: PermissionLevel

    # source: Optional[str]

    # time_from: Optional[str]
    # time_to: Optional[str]

    # source_uuid: Optional[str]
    # source_labels: Optional[List[str]]
    is_inherited: bool = False


class NodeQuery(Query):
    def __init__(self, node=None, id=None, *args, **kwargs):
        # TODO Validate that Node is a valid node
        # Eventually extract the branch from Node as well
        self.node = node
        self.id = id

        super().__init__(*args, **kwargs)


class NodeCreateQuery(NodeQuery):
    name = "node_create"

    type: QueryType = QueryType.WRITE

    raise_error_if_empty: bool = True

    def query_init(self):

        self.params["uuid"] = str(uuid.uuid4())
        self.params["branch"] = self.node._branch.name

        query = (
            """
        MATCH (b:Branch { name: $branch })
        CREATE (n:Node:%s { uuid: $uuid })
        CREATE (n)-[r:IS_PART_OF { status: "active", from: $at}]->(b)
        """
            % self.node.get_kind()
        )

        at = self.at or self.node._at
        self.params["at"] = at.to_string()

        self.add_to_query(query)
        self.return_labels = ["n"]

    def get_new_ids(self):

        result = self.get_result()
        node = result.get("n")

        if node is None:
            raise QueryError(self.get_query(), self.params)

        return node["uuid"], int(node.id)


class NodeDeleteQuery(NodeQuery):
    name = "node_delete"

    type: QueryType = QueryType.WRITE

    raise_error_if_empty: bool = True

    def query_init(self):

        self.params["uuid"] = self.node.id
        self.params["branch"] = self.node._branch.name

        query = (
            """
        MATCH (b:Branch { name: $branch })
        MATCH (n:Node:%s { uuid: $uuid })
        CREATE (n)-[r:IS_PART_OF { status: "deleted", from: $at}]->(b)
        """
            % self.node.get_kind()
        )

        self.params["at"] = self.at.to_string()

        self.add_to_query(query)
        self.return_labels = ["n"]


class NodeListGetLocalAttributeValueQuery(Query):

    name: str = "node_list_get_local_attribute_value"

    def __init__(self, ids, *args, **kwargs):
        self.ids = ids
        super().__init__(*args, **kwargs)

    def query_init(self):

        self.params["attrs_ids"] = self.ids

        rel_filter, rel_params = self.branch.get_query_filter_relationships(
            rel_labels=["r1"], at=self.at.to_string(), include_outside_parentheses=False
        )

        self.params.update(rel_params)

        query = (
            """
        MATCH (a:Attribute) WHERE ID(a) IN $attrs_ids
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
    order_by: List[str] = ["a.name"]

    def __init__(self, ids, fields=None, account=None, *args, **kwargs):
        self.account = account
        self.ids = ids
        self.fields = fields
        super().__init__(*args, **kwargs)

    def query_init(self):

        rels_filter, rels_params = self.branch.get_query_filter_path(at=self.at)
        self.params.update(rels_params)

        query = """
        MATCH (n) WHERE ID(n) IN $ids OR n.uuid IN $ids
        MATCH p = ((n)-[r1:HAS_ATTRIBUTE]-(a:Attribute)-[r2:HAS_VALUE]-(av))
        """

        if self.fields:
            query += "\n WHERE all(r IN relationships(p) WHERE ((a.name IN $field_names) AND %s))" % rels_filter
            self.params["field_names"] = list(self.fields.keys())
        else:
            query += "\n WHERE all(r IN relationships(p) WHERE ( %s))" % rels_filter

        self.add_to_query(query)

        self.params["ids"] = self.ids

        self.return_labels = ["n", "a", "av", "r1", "r2"]

        # self.query_add_source()

        # if self.account and self.node.use_permission:
        #     self.query_add_permission()

    # def query_add_source(self):

    #     rels_filter_perms, rels_params = self.branch.get_query_filter_relationships(
    #         rel_labels=["r3"], at=self.at, include_outside_parentheses=True
    #     )
    #     self.params.update(rels_params)

    #     query = """
    #     WITH %s
    #     OPTIONAL MATCH (a)-[r3:HAS_SOURCE]-(src)
    #     WHERE %s
    #     """ % (
    #         ",".join(self.return_labels),
    #         "\n AND ".join(rels_filter_perms),
    #     )

    #     self.add_to_query(query)

    #     self.return_labels.extend(["src", "r3"])

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

        attrs_by_node = defaultdict(lambda: dict(node=None, attrs=None))

        for result in self.get_results_group_by(("n", "uuid"), ("a", "name")):
            node_id = result.get("n").get("uuid")
            attr_name = result.get("a").get("name")
            attr = AttrToProcess(
                name=attr_name,
                type=result.get("a").get("type"),
                attr_labels=result.get("a").labels,
                attr_id=result.get("a").id,
                attr_uuid=result.get("a").get("uuid"),
                attr_value_id=result.get("av").id,
                attr_value_uuid=result.get("av").get("uuid"),
                changed_at=result.get("r2").get("from"),
                value=result.get("av").get("value"),
                # permission=result.permission_score,
                branch=self.branch.name,
                is_inherited=False,
            )
            # source = result.get("src")
            # if source:
            #     attr.source_uuid = source.get("uuid")
            #     attr.source_labels = source.labels

            if node_id not in attrs_by_node:
                attrs_by_node[node_id]["node"] = result.get("n")
                attrs_by_node[node_id]["attrs"] = {}

            attrs_by_node[node_id]["attrs"][attr_name] = attr

        return attrs_by_node


class NodeGetListQuery(Query):

    name = "node_get_list"

    order_by: List[str] = ["id(n)"]

    def __init__(self, schema: NodeSchema, filters=None, *args, **kwargs):

        self.schema = schema
        self.filters = filters

        super().__init__(*args, **kwargs)

    def query_init(self):

        branches = list(self.branch.get_branches_and_times_to_query().keys())

        branch_filter, branch_params = self.branch.get_query_filter_branch_to_node(
            at=self.at.to_string(), rel_label="rb", branch_label="br", include_outside_parentheses=False
        )

        self.params["branches"] = branches
        self.params.update(branch_params)

        node_filter = ""
        if self.filters and "id" in self.filters:
            node_filter = "{ uuid: $uuid }"
            self.params["uuid"] = self.filters["id"]

        query = """
        MATCH (br:Branch) WHERE br.name IN $branches
        WITH (br)
        MATCH (br)<-[rb:IS_PART_OF]-(n:%s %s)
        WHERE %s
        """ % (
            self.schema.kind,
            node_filter,
            branch_filter,
        )

        self.add_to_query(query)

        self.return_labels = ["n", "br", "rb"]

        if not self.filters:
            return

        # if Filters are provided
        #  Go over all the fields, remove the first part of the query to identify the field
        #  { "name__name": value }
        for field_name in self.schema.valid_input_names:

            attr_filters = {
                key.replace(f"{field_name}__", ""): value
                for key, value in self.filters.items()
                if key.startswith(f"{field_name}__")
            }
            if not attr_filters:
                continue

            field = self.schema.get_field(field_name)

            field_filters, field_params, nbr_rels = field.get_query_filter(
                name=field_name, filters=attr_filters, branch=self.branch
            )
            self.params.update(field_params)

            self.add_to_query(
                "WITH " + ",".join(self.return_labels)
            )  # [label for label in self.return_labels if not label.startswith("r")]))

            for field_filter in field_filters:
                self.add_to_query(field_filter)

            rels_filter, rels_params = self.branch.get_query_filter_relationships(
                rel_labels=[f"r{y+1}" for y in range(nbr_rels)],
                at=self.at.to_string(),
                include_outside_parentheses=True,
            )
            self.params.update(rels_params)
            self.add_to_query("WHERE " + "\n AND ".join(rels_filter))

    def get_node_ids(self):
        return [str(result.get("n").get("uuid")) for result in self.get_results()]
