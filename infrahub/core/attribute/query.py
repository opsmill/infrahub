import uuid

from infrahub.core.query import Query, QueryType

# flake8: noqa: F723


class AttributeQuery(Query):
    def __init__(self, attr=None, attr_id=None, *args, **kwargs):

        if not attr and not attr_id:
            raise ValueError("Either attr or attr_id must be defined, none provided")

        self.attr = attr
        self.attr_id = attr_id or attr.db_id

        super().__init__(*args, **kwargs)


class AttributeCreateQuery(AttributeQuery):

    raise_error_if_empty: bool = True

    def query_init(self):

        self.query_add_match()

        # if self.attr.node.use_permission:
        #     self.query_add_match_permission()

        # if self.attr.source:
        #     self.query_add_match_source()

        self.query_add_create()

        # if self.attr.node.use_permission:
        #     self.query_add_create_permission()

        # if self.attr.source:
        #     self.query_add_create_source()

        at = self.at or self.attr.at
        self.params["at"] = at.to_string()

        self.params["uuid"] = str(uuid.uuid4())
        self.params["name"] = self.attr.name
        self.params["branch"] = self.attr.branch.name

    def get_new_ids(self):

        result = self.get_result()
        attr = result.get("a")

        return attr.get("uuid"), attr.id

    # def query_add_match_source(self):

    #     self.add_to_query("MATCH (src) WHERE ID(src) = $source_id")

    #     self.params["source_id"] = self.attr.source.id

    # def query_add_create_source(self):

    #     query = """
    #     CREATE (a)-[r4:HAS_SOURCE { branch: $branch, from: $at, to: null }]->(src)
    #     """

    #     self.add_to_query(query)

    # def query_add_match_permission(self):

    #     from infrahub.core import registry

    #     group_name = f"{self.attr.node.get_type().lower()}.{self.attr.name}.all"
    #     attr_group = registry.attr_group[group_name]

    #     self.add_to_query("MATCH (ag) WHERE ID(ag) = $attr_group_id")

    #     self.params["attr_group_id"] = attr_group.id

    # def query_add_create_permission(self):

    #     query = """
    #     CREATE (a)-[r3:IS_MEMBER_OF { branch: $branch, from: $at, to: null }]->(ag)
    #     """

    #     self.add_to_query(query)


class AttributeGetValueQuery(AttributeQuery):

    name = "attribute_get_value"
    type: QueryType = QueryType.READ

    def query_init(self):

        self.params["attr_id"] = self.attr_id

        at = self.at or self.attr.at
        self.params["at"] = at.to_string()

        branch = self.branch or self.attr.branch

        rels_filter, rel_params = branch.get_query_filter_relationships(rel_labels=["r"], at=at.to_string())
        self.params.update(rel_params)

        query = """
        MATCH (a) WHERE ID(a) = $attr_id
        MATCH (a)-[r:HAS_VALUE]-(av)
        WHERE %s
        """ % (
            "\n AND ".join(rels_filter),
        )

        self.add_to_query(query)

        self.return_labels = ["a", "av", "r"]

    def get_value(self):
        result = self.get_result()
        if not result:
            return None

        return result.get("av").get("value")

    def get_relationship(self):
        result = self.get_result()
        if not result:
            return None

        return result.get("r")


# ------------------------------------------------------
# Remote Attribute Queries
# ------------------------------------------------------


# class RemoteAttributeCreateQuery(AttributeCreateQuery):
#     name = "remote_attribute_create"
#     type: QueryType = QueryType.WRITE

#     def query_add_match(self):

#         query = """
#         MATCH (n) WHERE ID(n) = $node_id
#         MATCH (rn) WHERE ID(rn) = $remote_node_id
#         """
#         self.add_to_query(query)

#         self.params["node_id"] = self.attr.node._internal_id
#         self.params["remote_node_id"] = self.attr.remote_node._internal_id

#     def query_add_create(self):

#         query = """
#         CREATE (a:Attribute:Attribute%s { uuid: $uuid, branch: $branch, name: $name, type: $remote_node_type })
#         CREATE (n)-[r1:%s { branch: $branch, from: $at, to: null }]->(a)
#         CREATE (a)-[r2:%s { branch: $branch, from: $at, to: null }]->(rn)
#         """ % (
#             self.attr._attr_type,
#             self.attr._rel_to_node_label,
#             self.attr._rel_to_value_label,
#         )

#         self.add_to_query(query)

#         self.params["remote_node_type"] = self.attr.remote_node.get_type()

#         self.return_labels = ["a", "r1", "r2"]


# class RemoteAttributeCreateNewValueQuery(AttributeQuery):

#     name = "remote_attribute_create_new_values"
#     type: QueryType = QueryType.WRITE  noqa: F723

#     raise_error_if_empty: bool = True

#     def query_init(self):

#         self.params["attr_id"] = self.attr.id
#         self.params["branch"] = self.attr.branch.name
#         self.params["at"] = self.at or pendulum.now(tz="UTC").to_iso8601_string()
#         self.params["remote_node_id"] = self.attr.remote_node.id

#         query = (
#             """
#         MATCH (a) WHERE ID(a) = $attr_id
#         MATCH (rn) WHERE ID(rn) = $remote_node_id
#         CREATE (a)-[r:%s { branch: $branch, from: $at, to: null }]->(rn)
#         """
#             % self.attr._rel_to_value_label
#         )

#         self.add_to_query(query)
#         self.return_labels = ["a", "rn", "r"]


# ------------------------------------------------------
# Local Attribute Queries
# ------------------------------------------------------


class LocalAttributeCreateQuery(AttributeCreateQuery):

    name = "local_attribute_create"
    type: QueryType = QueryType.WRITE

    def query_add_match(self):
        query = """
        MATCH (n) WHERE ID(n) = $node_id
        """

        self.params["node_id"] = self.attr.node.db_id

        self.add_to_query(query)

    def query_add_create(self):

        query = """
        CREATE (a:Attribute:AttributeLocal { uuid: $uuid, name: $name, type: $attribute_type })
        CREATE (n)-[r1:%s { branch: $branch, status: "active", from: $at, to: null }]->(a)
        MERGE (av:AttributeValue { type: $attribute_type, value: $value })
        CREATE (a)-[r2:%s { branch: $branch, status: "active", from: $at, to: null }]->(av)
        """ % (
            self.attr._rel_to_node_label,
            self.attr._rel_to_value_label,
        )
        self.add_to_query(query)

        self.params["value"] = self.attr.value if self.attr.value is not None else "NULL"
        self.params["attribute_type"] = self.attr.get_kind()

        self.return_labels = ["a", "av", "r1", "r2"]


# class LocalAttributeGetAllValuesQuery(AttributeQuery):

#     name = "local_attribute_get_all_values"
#     type: QueryType = QueryType.READ

#     def query_init(self):

#         self.params["attr_id"] = self.attr.id

#         query = """
#         MATCH (a) WHERE ID(a) = $attr_id
#         MATCH (a)-[r:HAS_VALUE]-(av)
#         """

#         self.add_to_query(query)

#         self.return_labels = ["a", "av", "r"]


class LocalAttributeCreateNewValueQuery(AttributeQuery):

    name = "local_attribute_create_new_values"
    type: QueryType = QueryType.WRITE

    raise_error_if_empty: bool = True

    def query_init(self):

        at = self.at or self.attr.at

        self.params["attr_id"] = self.attr_id
        self.params["branch"] = self.attr.branch.name
        self.params["at"] = at.to_string()
        self.params["value"] = self.attr.value if self.attr.value is not None else "NULL"
        self.params["attribute_type"] = self.attr.get_kind()

        query = (
            """
        MATCH (a) WHERE ID(a) = $attr_id
        MERGE (av:AttributeValue { type: $attribute_type, value: $value })
        CREATE (a)-[r:%s { branch: $branch, status: "active", from: $at, to: null }]->(av)
        """
            % self.attr._rel_to_value_label
        )

        self.add_to_query(query)
        self.return_labels = ["a", "av", "r"]


class AttributeDeleteQuery(AttributeQuery):

    name = "attribute_delete"
    type: QueryType = QueryType.WRITE

    raise_error_if_empty: bool = True

    def query_init(self):

        self.params["attr_id"] = self.attr_id
        self.params["node_id"] = self.attr.node.db_id
        self.params["branch"] = self.attr.branch.name
        self.params["at"] = self.at.to_string()
        self.params["value"] = self.attr.value if self.attr.value is not None else "NULL"
        self.params["attribute_type"] = self.attr.get_kind()

        query = (
            """
        MATCH (a) WHERE ID(a) = $attr_id
        MATCH (n) WHERE ID(n) = $node_id
        MERGE (av:AttributeValue { type: $attribute_type, value: $value })
        CREATE (n)-[r1:HAS_ATTRIBUTE { branch: $branch, status: "deleted", from: $at, to: null }]->(a)
        CREATE (a)-[r2:%s { branch: $branch, status: "deleted", from: $at, to: null }]->(av)
        """
            % self.attr._rel_to_value_label
        )

        self.add_to_query(query)
        self.return_labels = ["n", "a", "av", "r1", "r2"]


class AttributeGetQuery(AttributeQuery):

    name = "attribute_get"
    type: QueryType = QueryType.READ

    def query_init(self):

        self.params["attr_id"] = self.attr_id
        self.params["node_id"] = self.attr.node.db_id

        at = self.at or self.attr.at
        self.params["at"] = at.to_string()

        branch = self.branch or self.attr.branch

        rels_filter, rel_params = branch.get_query_filter_relationships(rel_labels=["r1", "r2"], at=at.to_string())
        self.params.update(rel_params)

        query = """
        MATCH (n) WHERE ID(n) = $node_id
        MATCH (a) WHERE ID(a) = $attr_id
        MATCH (n)-[r1]-(a)-[r2:HAS_VALUE]-(av)
        WHERE %s
        """ % (
            "\n AND ".join(rels_filter),
        )

        self.add_to_query(query)

        self.return_labels = ["n", "a", "av", "r1", "r2"]
