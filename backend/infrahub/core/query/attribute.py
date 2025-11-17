from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import AttributeDBNodeType
from infrahub.core.constants.relationship_label import RELATIONSHIP_TO_NODE_LABEL, RELATIONSHIP_TO_VALUE_LABEL
from infrahub.core.constants.schema import FlagProperty, NodeProperty
from infrahub.core.graph.schema import (
    GraphAttributeIPHostNode,
    GraphAttributeIPNetworkNode,
    GraphAttributeValueIndexedNode,
    GraphAttributeValueNode,
)
from infrahub.core.query import Query, QueryNode, QueryRel, QueryType
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import build_regex_attrs
from infrahub.types import is_large_attribute_type

if TYPE_CHECKING:
    from infrahub.core.attribute import BaseAttribute
    from infrahub.core.branch import Branch
    from infrahub.core.query import QueryElement
    from infrahub.database import InfrahubDatabase


class AttributeQuery(Query):
    def __init__(
        self,
        attr: BaseAttribute,
        user_id: str,
        attr_id: str | None = None,
        at: Timestamp | str | None = None,
        branch: Branch | None = None,
        **kwargs: Any,
    ):
        self.attr = attr
        self.attr_id = attr_id or attr.db_id
        self.user_id = user_id

        if at:
            self.at = Timestamp(at)
        else:
            self.at = self.attr.at

        self.branch = branch or self.attr.get_branch_based_on_support_type()

        super().__init__(**kwargs)


class AttributeUpdateValueQuery(AttributeQuery):
    name = "attribute_update_value"
    type: QueryType = QueryType.WRITE
    insert_return: bool = False
    raise_error_if_empty: bool = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        at = self.at or self.attr.at

        self.params["attr_uuid"] = self.attr.id
        self.params["user_id"] = self.user_id
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["at"] = at.to_string()
        content = self.attr.to_db()
        self.params.update(self.attr.to_db())

        prop_list = [f"{key}: ${key}" for key in content.keys()]

        labels = [GraphAttributeValueNode.get_default_label()]
        node_type = self.attr.get_db_node_type()
        if AttributeDBNodeType.INDEXED in node_type:
            labels.append(GraphAttributeValueIndexedNode.get_default_label())
        if AttributeDBNodeType.IPHOST in node_type:
            labels.append(GraphAttributeIPHostNode.get_default_label())
        if AttributeDBNodeType.IPNETWORK in node_type:
            labels.append(GraphAttributeIPNetworkNode.get_default_label())

        query = """
MATCH (a:Attribute { uuid: $attr_uuid })
MERGE (av:%(labels)s { %(props)s } )
WITH av, a
LIMIT 1
OPTIONAL MATCH (a)-[existing_active_r:%(rel_label)s { branch: $branch, status: "active" }]->()
WHERE existing_active_r.to IS NULL
LIMIT 1
CREATE (a)-[r:%(rel_label)s { branch: $branch, branch_level: $branch_level, status: "active", from: $at, from_user_id: $user_id }]->(av)
WITH a, existing_active_r
CALL (a) {
    WITH a
    WHERE $branch_level = 1
    LIMIT 1
    SET a.updated_at = $at, a.updated_by = $user_id
}
WITH existing_active_r
WHERE existing_active_r IS NOT NULL
SET existing_active_r.to = $at, existing_active_r.to_user_id = $user_id
        """ % {"rel_label": self.attr._rel_to_value_label, "labels": ":".join(labels), "props": ", ".join(prop_list)}

        self.add_to_query(query)


class AttributeUpdateFlagQuery(AttributeQuery):
    name = "attribute_update_flag"
    type: QueryType = QueryType.WRITE
    insert_return: bool = False
    raise_error_if_empty: bool = False

    def __init__(
        self,
        flag_name: str,
        **kwargs: Any,
    ) -> None:
        SUPPORTED_FLAGS = ["is_visible", "is_protected"]

        if flag_name not in SUPPORTED_FLAGS:
            raise ValueError(f"Only {SUPPORTED_FLAGS} are supported for now.")

        self.flag_name = flag_name

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        at = self.at or self.attr.at

        self.params["attr_uuid"] = self.attr.id
        self.params["user_id"] = self.user_id
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["at"] = at.to_string()
        self.params["flag_value"] = getattr(self.attr, self.flag_name)
        self.params["flag_type"] = self.attr.get_kind()

        query = """
MATCH (a:Attribute { uuid: $attr_uuid })
MERGE (flag:Boolean { value: $flag_value })
WITH flag, a
LIMIT 1
OPTIONAL MATCH (a)-[existing_active_r:%(flag_type)s { branch: $branch, status: "active" }]->()
WHERE existing_active_r.to IS NULL
CREATE (a)-[r:%(flag_type)s { branch: $branch, branch_level: $branch_level, status: "active", from: $at, from_user_id: $user_id }]->(flag)
WITH a, existing_active_r
CALL (a) {
    WITH a
    WHERE $branch_level = 1
    LIMIT 1
    SET a.updated_at = $at, a.updated_by = $user_id
}
WITH existing_active_r
WHERE existing_active_r IS NOT NULL
SET existing_active_r.to = $at, existing_active_r.to_user_id = $user_id
        """ % {"flag_type": self.flag_name.upper()}
        self.add_to_query(query)


class AttributeUpdateNodePropertyQuery(AttributeQuery):
    name = "attribute_update_node_property"
    type: QueryType = QueryType.WRITE
    insert_return: bool = False
    raise_error_if_empty: bool = False

    def __init__(
        self,
        prop_name: str,
        prop_id: str | None = None,
        **kwargs: Any,
    ):
        self.prop_name = prop_name
        self.prop_id = prop_id

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        at = self.at or self.attr.at

        branch_filter, branch_params = self.branch.get_query_filter_path(at=at)
        self.params.update(branch_params)
        self.params["attr_uuid"] = self.attr.id
        self.params["user_id"] = self.user_id
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["at"] = at.to_string()
        self.params["prop_name"] = self.prop_name
        self.params["prop_id"] = self.prop_id

        rel_label = f"HAS_{self.prop_name.upper()}"

        if self.branch.is_default or self.branch.is_global:
            node_query = """
        MATCH (np:Node { uuid: $prop_id })-[r:IS_PART_OF]->(:Root)
        WHERE r.branch IN $branch0
        AND r.status = "active"
        AND r.from <= $at AND (r.to IS NULL OR r.to > $at)
        WITH np
        LIMIT 1
            """
        else:
            node_query = """
        MATCH (np:Node { uuid: $prop_id })-[r:IS_PART_OF]->(:Root)
        WHERE %(branch_filter)s
        ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
        LIMIT 1
        WITH np
        WHERE r.status = "active"
            """ % {"branch_filter": branch_filter}
        self.add_to_query(node_query)

        attr_query = """
MATCH (a:Attribute { uuid: $attr_uuid })
OPTIONAL MATCH (a)-[existing_active_r:%(rel_label)s { branch: $branch, status: "active" }]->()
WHERE existing_active_r.to IS NULL
CREATE (a)-[r:%(rel_label)s { branch: $branch, branch_level: $branch_level, status: "active", from: $at, from_user_id: $user_id }]->(np)
WITH a, existing_active_r
CALL (a) {
    WITH a
    WHERE $branch_level = 1
    LIMIT 1
    SET a.updated_at = $at, a.updated_by = $user_id
}
WITH existing_active_r
WHERE existing_active_r IS NOT NULL
SET existing_active_r.to = $at, existing_active_r.to_user_id = $user_id
        """ % {"rel_label": rel_label}
        self.add_to_query(attr_query)


class AttributeClearNodePropertyQuery(AttributeQuery):
    name = "attribute_clear_node_property"
    type: QueryType = QueryType.WRITE
    insert_return: bool = False

    def __init__(
        self,
        prop_name: str,
        **kwargs: Any,
    ):
        self.prop_name = prop_name

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        at = self.at or self.attr.at

        branch_filter, branch_params = self.branch.get_query_filter_path(at=at)
        self.params.update(branch_params)
        self.params["attr_uuid"] = self.attr.id
        self.params["user_id"] = self.user_id
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["at"] = at.to_string()

        rel_label = f"HAS_{self.prop_name.upper()}"
        query = """
MATCH (a:Attribute { uuid: $attr_uuid })-[r:%(rel_label)s]->(np:Node)
WITH DISTINCT a, np
CALL (a, np) {
    MATCH (a)-[r:%(rel_label)s]->(np)
    WHERE %(branch_filter)s
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
    RETURN r AS property_edge
}
WITH a, np, property_edge
WHERE property_edge.status = "active"
CALL (property_edge) {
    WITH property_edge
    WHERE property_edge.branch = $branch
    SET property_edge.to = $at, property_edge.to_user_id = $user_id
}
CALL (a, np, property_edge) {
    WITH property_edge
    WHERE property_edge.branch_level < $branch_level
    CREATE (a)-[r:%(rel_label)s { branch: $branch, branch_level: $branch_level, status: "deleted", from: $at, from_user_id: $user_id }]->(np)
}
CALL (a) {
    WITH a
    WHERE $branch_level = 1
    LIMIT 1
    SET a.updated_at = $at, a.updated_by = $user_id
}
        """ % {"branch_filter": branch_filter, "rel_label": rel_label}
        self.add_to_query(query)


class AttributeDeleteQuery(AttributeQuery):
    name = "attribute_delete"
    type: QueryType = QueryType.WRITE
    insert_return: bool = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["attr_uuid"] = self.attr.id
        self.params["user_id"] = self.user_id
        self.params["branch"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["branched_from"] = self.branch.get_branched_from()
        self.params["at"] = self.at.to_string()

        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at)
        self.params.update(branch_params)

        query = """
MATCH (a:Attribute { uuid: $attr_uuid })
CALL (a) {
    WITH a
    WHERE $branch_level = 1
    LIMIT 1
    SET a.updated_at = $at, a.updated_by = $user_id
}

UNWIND [
    ["HAS_ATTRIBUTE", "in"],
    ["HAS_VALUE", "out"],
    ["IS_VISIBLE", "out"],
    ["IS_PROTECTED", "out"],
    ["HAS_SOURCE", "out"],
    ["HAS_OWNER", "out"]
] AS edge_details
WITH a, edge_details[0] AS property_type, edge_details[1] AS direction
CALL (a, property_type, direction) {
    MATCH (a)-[r]-(attr_peer)
    WHERE type(r) = property_type
    AND (
        (direction = "in" AND startNode(r) = attr_peer)
        OR (direction = "out" AND startNode(r) = a)
    )
    AND %(branch_filter)s
    RETURN r AS property_edge, attr_peer
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
CALL (property_edge) {
    WITH property_edge
    WHERE property_edge.status = "active"
    AND property_edge.branch = $branch
    AND property_edge.to IS NULL
    SET property_edge.to = $at, property_edge.to_user_id = $user_id
}
WITH a, property_edge, property_type, attr_peer, direction
CALL (a, property_type, attr_peer, direction) {
    WITH direction
    WHERE direction = "out"
    CREATE (a)
        -[r:$(property_type) { branch: $branch, branch_level: $branch_level, status: "deleted", from: $at, from_user_id: $user_id }]
        ->(attr_peer)
}
CALL (a, property_type, attr_peer, direction) {
    WITH direction
    WHERE direction = "in"
    CREATE (a)
        <-[r:$(property_type) { branch: $branch, branch_level: $branch_level, status: "deleted", from: $at, from_user_id: $user_id }]
        -(attr_peer)
}
WITH CASE
    WHEN property_type = "HAS_VALUE" THEN attr_peer.value
    ELSE NULL
END AS property_value
WITH property_value
RETURN property_value
ORDER BY property_value ASC
LIMIT 1
        """ % {"branch_filter": branch_filter}
        self.add_to_query(query)
        self.return_labels = ["property_value"]

    def get_previous_property_value(self) -> Any:
        result = self.get_result()
        if result:
            return result.get(label="property_value")
        return None


async def default_attribute_query_filter(
    name: str,
    filter_name: str,
    branch: Branch | None = None,  # noqa: ARG001
    filter_value: str | int | bool | list | None = None,
    attribute_kind: str | None = None,
    include_match: bool = True,
    param_prefix: str | None = None,
    db: InfrahubDatabase | None = None,  # noqa: ARG001
    partial_match: bool = False,
) -> tuple[list[QueryElement], dict[str, Any], list[str]]:
    """Generate Query String Snippet to filter the right node."""
    attribute_value_label = GraphAttributeValueNode.get_default_label()
    if attribute_kind and not is_large_attribute_type(attribute_kind):
        attribute_value_label = GraphAttributeValueIndexedNode.get_default_label()

    query_filter: list[QueryElement] = []
    query_params: dict[str, Any] = {}
    query_where: list[str] = []

    if filter_value and not isinstance(filter_value, str | bool | int | list):
        raise TypeError(f"filter {filter_name}: {filter_value} ({type(filter_value)}) is not supported.")

    if isinstance(filter_value, list) and not all(isinstance(value, str | bool | int) for value in filter_value):
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

    if filter_name in ("value", "binary_address", "prefixlen", "isnull"):
        query_filter.append(QueryRel(labels=[RELATIONSHIP_TO_VALUE_LABEL]))

        if filter_value is None:
            query_filter.append(QueryNode(name="av", labels=[attribute_value_label]))
        else:
            if partial_match:
                query_filter.append(QueryNode(name="av", labels=[attribute_value_label]))
                query_where.append(
                    f"toLower(toString(av.{filter_name})) CONTAINS toLower(toString(${param_prefix}_{filter_name}))"
                )
            elif attribute_kind and attribute_kind == "List" and not isinstance(filter_value, list):
                query_filter.append(QueryNode(name="av", labels=[attribute_value_label]))
                filter_value = build_regex_attrs(values=[filter_value])
                query_where.append(f"toString(av.{filter_name}) =~ ${param_prefix}_{filter_name}")
            elif filter_name == "isnull":
                query_filter.append(QueryNode(name="av", labels=[attribute_value_label]))
            else:
                query_filter.append(
                    QueryNode(
                        name="av",
                        labels=[attribute_value_label],
                        params={filter_name: f"${param_prefix}_{filter_name}"},
                    )
                )
            query_params[f"{param_prefix}_{filter_name}"] = filter_value

    elif filter_name == "values" and isinstance(filter_value, list):
        query_filter.extend(
            (QueryRel(labels=[RELATIONSHIP_TO_VALUE_LABEL]), QueryNode(name="av", labels=[attribute_value_label]))
        )
        if attribute_kind and attribute_kind == "List":
            query_params[f"{param_prefix}_{filter_name}"] = build_regex_attrs(values=filter_value)
            query_where.append(f"toString(av.value) =~ ${param_prefix}_{filter_name}")
        else:
            query_where.append(f"av.value IN ${param_prefix}_value")
        query_params[f"{param_prefix}_value"] = filter_value

    elif filter_name == "version":
        query_filter.append(QueryRel(labels=[RELATIONSHIP_TO_VALUE_LABEL]))

        if filter_value is None:
            query_filter.append(QueryNode(name="av", labels=[GraphAttributeValueNode.get_default_label()]))
        else:
            query_filter.append(
                QueryNode(
                    name="av",
                    labels=[GraphAttributeValueNode.get_default_label()],
                    params={filter_name: f"${param_prefix}_{filter_name}"},
                )
            )
            query_params[f"{param_prefix}_{filter_name}"] = filter_value

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
                QueryNode(name="ap", labels=["Node"], params={"uuid": f"${param_prefix}_{clean_filter_name}"}),
            ]
        )
        query_params[f"{param_prefix}_{clean_filter_name}"] = filter_value

    return query_filter, query_params, query_where
