from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

from infrahub.core.query import Query, QueryType
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.core.attribute import BaseAttribute
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

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

        self.branch = branch or self.attr.get_branch_based_on_support_type()

        super().__init__(*args, **kwargs)


class AttributeGetValueQuery(AttributeQuery):
    name = "attribute_get_value"
    type: QueryType = QueryType.READ

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
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
        """ % ("\n AND ".join(rels_filter),)

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

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
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

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        at = self.at or self.attr.at

        self.params["attr_uuid"] = self.attr.id
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["at"] = at.to_string()
        self.params["flag_value"] = getattr(self.attr, self.flag_name)
        self.params["flag_type"] = self.attr.get_kind()

        query = """
        MATCH (a { uuid: $attr_uuid })
        MERGE (flag:Boolean { value: $flag_value })
        CREATE (a)-[r:%s { branch: $branch, branch_level: $branch_level, status: "active", from: $at, to: null }]->(flag)
        """ % self.flag_name.upper()

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

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
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

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        self.params["attr_uuid"] = self.attr.id
        self.params["node_uuid"] = self.attr.node.id

        at = self.at or self.attr.at
        self.params["at"] = at.to_string()

        rels_filter, rels_params = self.branch.get_query_filter_path(at=at.to_string())
        self.params.update(rels_params)

        query = (
            """
        MATCH (a:Attribute { uuid: $attr_uuid })
        MATCH p = ((a)-[r2:HAS_VALUE|IS_VISIBLE|IS_PROTECTED|HAS_SOURCE|HAS_OWNER]->(ap))
        WHERE all(r IN relationships(p) WHERE ( %s))
        """
            % rels_filter
        )

        self.add_to_query(query)

        self.return_labels = ["a", "ap", "r2"]
