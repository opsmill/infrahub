from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from infrahub.core.constants.relationship_label import RELATIONSHIP_TO_NODE_LABEL, RELATIONSHIP_TO_VALUE_LABEL
from infrahub.core.constants.schema import FlagProperty, NodeProperty
from infrahub.core.query import Query, QueryNode, QueryRel, QueryType
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.core.attribute import BaseAttribute
    from infrahub.core.branch import Branch
    from infrahub.core.query import QueryElement
    from infrahub.database import InfrahubDatabase


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
        content = self.attr.to_db()
        self.params["value"] = content["value"]
        self.params["is_default"] = content["is_default"]

        query = (
            """
        MATCH (a:Attribute { uuid: $attr_uuid })
        CREATE (av:AttributeValue { value: $value, is_default: $is_default })
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
        CREATE (flag:Boolean { value: $flag_value })
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


async def default_attribute_query_filter(  # pylint: disable=unused-argument,disable=too-many-branches
    name: str,
    filter_name: str,
    branch: Optional[Branch] = None,
    filter_value: Optional[Union[str, int, bool, list]] = None,
    include_match: bool = True,
    param_prefix: Optional[str] = None,
    db: Optional[InfrahubDatabase] = None,
    partial_match: bool = False,
) -> Tuple[List[QueryElement], Dict[str, Any], List[str]]:
    """Generate Query String Snippet to filter the right node."""

    query_filter: List[QueryElement] = []
    query_params: Dict[str, Any] = {}
    query_where: List[str] = []

    if filter_value and not isinstance(filter_value, (str, bool, int, list)):
        raise TypeError(f"filter {filter_name}: {filter_value} ({type(filter_value)}) is not supported.")

    if isinstance(filter_value, list) and not all(isinstance(value, (str, bool, int)) for value in filter_value):
        raise TypeError(f"filter {filter_name}: {filter_value} (list) contains unsupported item")

    param_prefix = param_prefix or f"attr_{name}"

    if include_match:
        query_filter.append(QueryNode(name="n"))

    query_filter.append(QueryRel(labels=[RELATIONSHIP_TO_NODE_LABEL]))

    if name in ["any", "attribute"]:
        query_filter.append(QueryNode(name="i", labels=["Attribute"]))
    else:
        query_filter.append(QueryNode(name="i", labels=["Attribute"], params={"name": f"${param_prefix}_name"}))
        query_params[f"{param_prefix}_name"] = name

    if filter_name == "value":
        query_filter.append(QueryRel(labels=[RELATIONSHIP_TO_VALUE_LABEL]))

        if filter_value is None:
            query_filter.append(QueryNode(name="av", labels=["AttributeValue"]))
        else:
            if partial_match:
                query_filter.append(QueryNode(name="av", labels=["AttributeValue"]))
                query_where.append(f"toLower(toString(av.value)) CONTAINS toLower(toString(${param_prefix}_value))")
            else:
                query_filter.append(
                    QueryNode(name="av", labels=["AttributeValue"], params={"value": f"${param_prefix}_value"})
                )
            query_params[f"{param_prefix}_value"] = filter_value

    elif filter_name == "values" and isinstance(filter_value, list):
        query_filter.extend(
            (QueryRel(labels=[RELATIONSHIP_TO_VALUE_LABEL]), QueryNode(name="av", labels=["AttributeValue"]))
        )
        query_where.append(f"av.value IN ${param_prefix}_value")
        query_params[f"{param_prefix}_value"] = filter_value

    elif filter_name in [v.value for v in FlagProperty] and filter_value is not None:
        query_filter.append(QueryRel(labels=[filter_name.upper()]))
        query_filter.append(
            QueryNode(name="ap", labels=["Boolean"], params={"value": f"${param_prefix}_{filter_name}"})
        )
        query_params[f"{param_prefix}_{filter_name}"] = filter_value

    elif "__" in filter_name and filter_value is not None:
        filter_name_split = filter_name.split(sep="__", maxsplit=1)
        property_name: str = filter_name_split[0]
        property_attr: str = filter_name_split[1]

        if property_name not in [v.value for v in NodeProperty]:
            raise ValueError(f"filter {filter_name}: {filter_value}, {property_name} is not a valid property")

        if property_attr not in ["id"]:
            raise ValueError(f"filter {filter_name}: {filter_value}, {property_attr} is supported")

        clean_filter_name = f"{property_name}_{property_attr}"

        query_filter.extend(
            [
                QueryRel(labels=[f"HAS_{property_name.upper()}"]),
                QueryNode(name="ap", labels=["CoreNode"], params={"uuid": f"${param_prefix}_{clean_filter_name}"}),
            ]
        )
        query_params[f"{param_prefix}_{clean_filter_name}"] = filter_value

    return query_filter, query_params, query_where
