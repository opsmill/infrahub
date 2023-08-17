from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional, Tuple, Union

from infrahub.core import registry
from infrahub.core.query import Query, QueryType
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from neo4j import AsyncSession

    from infrahub.core.attribute import BaseAttribute
    from infrahub.core.branch import Branch

# flake8: noqa: F723


class AttributeQuery(Query):
    def __init__(
        self,
        attr: BaseAttribute = None,
        attr_id: Optional[str] = None,
        at: Optional[Union[Timestamp, str]] = None,
        branch: Optional[Branch] = None,
        *args,
        **kwargs,
    ):
        if not attr and not attr_id:
            raise ValueError("Either attr or attr_id must be defined, none provided")

        self.attr = attr
        self.attr_id = attr_id or attr.db_id

        if at:
            self.at = Timestamp(at)
        else:
            self.at = self.attr.at

        if self.attr and self.attr.schema.branch is False:
            self.branch = registry.get_global_branch()
        else:
            self.branch = branch or self.attr.branch

        super().__init__(*args, **kwargs)


class AttributeCreateQuery(AttributeQuery):
    raise_error_if_empty: bool = True

    name = "attribute_create"
    type: QueryType = QueryType.WRITE

    async def query_init(self, session: AsyncSession, *args, **kwargs):
        self.query_add_match()

        if self.attr.source_id:
            self.query_add_match_source()

        if self.attr.owner_id:
            self.query_add_match_owner()

        self.query_add_create()

        if self.attr.source_id:
            self.query_add_create_source()

        if self.attr.owner_id:
            self.query_add_create_owner()

        self.params["at"] = self.at.to_string()
        self.params["uuid"] = str(uuid.uuid4())
        self.params["name"] = self.attr.name
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level

    def query_add_match(self):
        query = """
        MATCH (n { uuid: $node_id})
        """

        self.params["node_id"] = self.attr.node.id

        self.add_to_query(query)

    def query_add_create(self):
        query = """
        CREATE (a:Attribute:AttributeLocal { uuid: $uuid, name: $name, type: $attribute_type })
        CREATE (n)-[r1:%s { branch: $branch, branch_level: $branch_level, status: "active", from: $at, to: null }]->(a)
        MERGE (av:AttributeValue { type: $attribute_type, value: $value })
        CREATE (a)-[r2:%s { branch: $branch, branch_level: $branch_level, status: "active", from: $at, to: null }]->(av)
        MERGE (ip:Boolean { value: $is_protected })
        MERGE (iv:Boolean { value: $is_visible })
        CREATE (a)-[:IS_PROTECTED { branch: $branch, branch_level: $branch_level, status: "active", from: $at, to: null }]->(ip)
        CREATE (a)-[:IS_VISIBLE { branch: $branch, branch_level: $branch_level, status: "active", from: $at, to: null }]->(iv)
        """ % (
            self.attr._rel_to_node_label,
            self.attr._rel_to_value_label,
        )
        self.add_to_query(query)

        self.params["value"] = self.attr.to_db()
        self.params["is_protected"] = self.attr.is_protected
        self.params["is_visible"] = self.attr.is_visible
        self.params["attribute_type"] = self.attr.get_kind()

        self.return_labels = ["a", "av", "r1", "r2"]

    def get_new_ids(self) -> Tuple[str, int]:
        result = self.get_result()
        attr = result.get("a")

        return attr.get("uuid"), attr.element_id

    def query_add_match_source(self):
        self.add_to_query("MATCH (src { uuid: $source_id })")

        self.params["source_id"] = self.attr.source_id

    def query_add_create_source(self):
        query = """
        CREATE (a)-[:HAS_SOURCE { branch: $branch, branch_level: $branch_level, status: "active", from: $at, to: null }]->(src)
        """

        self.add_to_query(query)

    def query_add_match_owner(self):
        self.add_to_query("MATCH (owner { uuid: $owner_id })")

        self.params["owner_id"] = self.attr.owner_id

    def query_add_create_owner(self):
        query = """
        CREATE (a)-[:HAS_OWNER { branch: $branch, branch_level: $branch_level, status: "active", from: $at, to: null }]->(owner)
        """

        self.add_to_query(query)

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

    async def query_init(self, session: AsyncSession, *args, **kwargs):
        self.params["attr_uuid"] = self.attr.id
        at = self.at or self.attr.at
        self.params["at"] = at.to_string()

        branch = self.branch or self.attr.branch

        rels_filter, rel_params = branch.get_query_filter_relationships(rel_labels=["r"], at=at.to_string())
        self.params.update(rel_params)

        query = """
        MATCH (a { uuid: $attr_uuid })
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


class AttributeUpdateValueQuery(AttributeQuery):
    name = "attribute_update_value"
    type: QueryType = QueryType.WRITE

    raise_error_if_empty: bool = True

    async def query_init(self, session: AsyncSession, *args, **kwargs):
        at = self.at or self.attr.at

        self.params["attr_uuid"] = self.attr.id
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["at"] = at.to_string()
        self.params["value"] = self.attr.to_db()
        self.params["attribute_type"] = self.attr.get_kind()

        query = (
            """
        MATCH (a { uuid: $attr_uuid })
        MERGE (av:AttributeValue { type: $attribute_type, value: $value })
        CREATE (a)-[r:%s { branch: $branch, branch_level: $branch_level, status: "active", from: $at, to: null }]->(av)
        """
            % self.attr._rel_to_value_label
        )

        self.add_to_query(query)
        self.return_labels = ["a", "av", "r"]


class AttributeUpdateFlagQuery(AttributeQuery):
    name = "attribute_update_flag"
    type: QueryType = QueryType.WRITE

    raise_error_if_empty: bool = True

    def __init__(
        self,
        flag_name: str,
        *args,
        **kwargs,
    ):
        SUPPORTED_FLAGS = ["is_visible", "is_protected"]

        if flag_name not in SUPPORTED_FLAGS:
            raise ValueError(f"Only {SUPPORTED_FLAGS} are supported for now.")

        self.flag_name = flag_name

        super().__init__(*args, **kwargs)

    async def query_init(self, session: AsyncSession, *args, **kwargs):
        at = self.at or self.attr.at

        self.params["attr_uuid"] = self.attr.id
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["at"] = at.to_string()
        self.params["flag_value"] = getattr(self.attr, self.flag_name)
        self.params["flag_type"] = self.attr.get_kind()

        query = (
            """
        MATCH (a { uuid: $attr_uuid })
        MERGE (flag:Boolean { value: $flag_value })
        CREATE (a)-[r:%s { branch: $branch, branch_level: $branch_level, status: "active", from: $at, to: null }]->(flag)
        """
            % self.flag_name.upper()
        )

        self.add_to_query(query)
        self.return_labels = ["a", "flag", "r"]


class AttributeUpdateNodePropertyQuery(AttributeQuery):
    name = "attribute_update_node_property"
    type: QueryType = QueryType.WRITE

    raise_error_if_empty: bool = True

    def __init__(
        self,
        prop_name: str,
        prop_id: str,
        *args,
        **kwargs,
    ):
        self.prop_name = prop_name
        self.prop_id = prop_id

        super().__init__(*args, **kwargs)

    async def query_init(self, session: AsyncSession, *args, **kwargs):
        at = self.at or self.attr.at

        self.params["attr_uuid"] = self.attr.id
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["at"] = at.to_string()
        self.params["prop_name"] = self.prop_name
        self.params["prop_id"] = self.prop_id

        rel_name = f"HAS_{self.prop_name.upper()}"

        query = (
            """
        MATCH (a { uuid: $attr_uuid })
        MATCH (np { uuid: $prop_id })
        CREATE (a)-[r:%s { branch: $branch, branch_level: $branch_level, status: "active", from: $at, to: null }]->(np)
        """
            % rel_name
        )

        self.add_to_query(query)
        self.return_labels = ["a", "np", "r"]


class AttributeGetQuery(AttributeQuery):
    name = "attribute_get"
    type: QueryType = QueryType.READ

    async def query_init(self, session: AsyncSession, *args, **kwargs):
        self.params["attr_uuid"] = self.attr.id
        self.params["node_uuid"] = self.attr.node.id

        at = self.at or self.attr.at
        self.params["at"] = at.to_string()

        rels_filter, rel_params = self.branch.get_query_filter_relationships(rel_labels=["r1", "r2"], at=at.to_string())
        self.params.update(rel_params)

        query = """
        MATCH (n { uuid: $node_uuid })
        MATCH (a { uuid: $attr_uuid })
        MATCH (n)-[r1]-(a)-[r2:HAS_VALUE|IS_VISIBLE|IS_PROTECTED|HAS_SOURCE|HAS_OWNER]-(ap)
        WHERE %s
        """ % (
            "\n AND ".join(rels_filter),
        )

        self.add_to_query(query)

        self.return_labels = ["n", "a", "ap", "r1", "r2"]
