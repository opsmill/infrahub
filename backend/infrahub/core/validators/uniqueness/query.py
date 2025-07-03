from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants.relationship_label import RELATIONSHIP_TO_VALUE_LABEL
from infrahub.core.graph.schema import GraphAttributeValueIndexedNode, GraphAttributeValueNode
from infrahub.core.query import Query, QueryType
from infrahub.types import is_large_attribute_type

from .model import QueryAttributePathValued, QueryRelationshipPathValued

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

    from .model import NodeUniquenessQueryRequest, NodeUniquenessQueryRequestValued


class NodeUniqueAttributeConstraintQuery(Query):
    name = "node_constraints_uniqueness"
    insert_return = False
    type = QueryType.READ
    attribute_property_map = {"value": RELATIONSHIP_TO_VALUE_LABEL}

    def __init__(
        self,
        query_request: NodeUniquenessQueryRequest,
        min_count_required: int = 1,
        **kwargs: Any,
    ) -> None:
        self.query_request = query_request
        self.min_count_required = min_count_required
        super().__init__(**kwargs)

    def get_context(self) -> dict[str, str]:
        return {"kind": self.query_request.kind}

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002,PLR0915
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string(), is_isolated=False)
        self.params.update(branch_params)
        from_times = db.render_list_comprehension(items="relationships(potential_path)", item_name="from")
        branch_name_and_level = db.render_list_comprehension_with_list(
            items="relationships(active_path)", item_names=["branch", "branch_level"]
        )

        attrs_include_large_type = False
        attribute_names = set()
        attr_paths, attr_paths_with_value, attr_values = [], [], []
        for attr_path in self.query_request.unique_attribute_paths:
            try:
                property_rel_name = self.attribute_property_map[attr_path.property_name or "value"]
            except KeyError as exc:
                raise ValueError(
                    f"{attr_path.property_name} is not a valid property for a uniqueness constraint"
                ) from exc
            if is_large_attribute_type(attr_path.attribute_kind):
                attrs_include_large_type = True
            attribute_names.add(attr_path.attribute_name)
            if attr_path.value:
                attr_paths_with_value.append((attr_path.attribute_name, property_rel_name, attr_path.value))
                attr_values.append(attr_path.value)
            else:
                attr_paths.append((attr_path.attribute_name, property_rel_name))
        attr_value_label = (
            GraphAttributeValueNode.get_default_label()
            if attrs_include_large_type
            else GraphAttributeValueIndexedNode.get_default_label()
        )

        relationship_names = set()
        relationship_attr_paths = []
        relationship_only_attr_paths = []
        relationship_only_attr_values = []
        relationship_attr_values = []
        relationship_attr_paths_with_value = []
        for rel_path in self.query_request.relationship_attribute_paths:
            relationship_names.add(rel_path.identifier)
            if rel_path.attribute_name and rel_path.value:
                relationship_attr_paths_with_value.append(
                    (rel_path.identifier, rel_path.attribute_name, rel_path.value)
                )
                relationship_attr_values.append(rel_path.value)
            elif rel_path.attribute_name:
                relationship_attr_paths.append((rel_path.identifier, rel_path.attribute_name))
            else:
                relationship_only_attr_paths.append(rel_path.identifier)
                if rel_path.value:
                    relationship_only_attr_values.append(rel_path.value)

        if (
            not attr_paths
            and not attr_paths_with_value
            and not relationship_attr_paths
            and not relationship_attr_paths_with_value
            and not relationship_only_attr_paths
        ):
            raise ValueError(
                "The NodeUniquenessQueryRequest provided for node_constraints_uniqueness doesn't have enough information to continue"
            )

        self.params.update(
            {
                "node_kind": self.query_request.kind,
                "attr_paths": attr_paths,
                "attr_paths_with_value": attr_paths_with_value,
                "attr_values": attr_values,
                "attribute_names": list(attribute_names),
                "relationship_names": list(relationship_names),
                "relationship_attr_paths": relationship_attr_paths,
                "relationship_attr_paths_with_value": relationship_attr_paths_with_value,
                "relationship_only_attr_paths": relationship_only_attr_paths,
                "relationship_only_attr_values": relationship_only_attr_values,
                "relationship_attr_values": relationship_attr_values,
                "min_count_required": self.min_count_required,
            }
        )

        attr_paths_subquery = """
        MATCH attr_path = (start_node:%(node_kind)s)-[:HAS_ATTRIBUTE]->(attr:Attribute)-[r:HAS_VALUE]->(attr_value:AttributeValue)
        WHERE attr.name in $attribute_names
            AND [attr.name, type(r)] in $attr_paths
        RETURN start_node, attr_path as potential_path, NULL as rel_identifier, attr.name as potential_attr, attr_value.value as potential_attr_value
        """ % {"node_kind": self.query_request.kind}

        attr_paths_with_value_subquery = """
        MATCH attr_path = (start_node:%(node_kind)s)-[:HAS_ATTRIBUTE]->(attr:Attribute)-[r:HAS_VALUE]->(attr_value:%(attr_value_label)s)
        WHERE attr.name in $attribute_names AND attr_value.value in $attr_values
            AND [attr.name, type(r), attr_value.value] in $attr_paths_with_value
        RETURN start_node, attr_path as potential_path, NULL as rel_identifier, attr.name as potential_attr, attr_value.value as potential_attr_value
        """ % {"node_kind": self.query_request.kind, "attr_value_label": attr_value_label}

        relationship_attr_paths_subquery = """
        MATCH rel_path = (start_node:%(node_kind)s)-[:IS_RELATED]-(relationship_node:Relationship)-[:IS_RELATED]-(related_n:Node)-[:HAS_ATTRIBUTE]->(rel_attr:Attribute)-[:HAS_VALUE]->(rel_attr_value:AttributeValue)
        WHERE relationship_node.name in $relationship_names
            AND [relationship_node.name, rel_attr.name] in $relationship_attr_paths
        RETURN start_node, rel_path as potential_path, relationship_node.name as rel_identifier, rel_attr.name as potential_attr, rel_attr_value.value as potential_attr_value
        """ % {"node_kind": self.query_request.kind}

        relationship_attr_paths_with_value_subquery = """
        MATCH rel_path = (start_node:%(node_kind)s)-[:IS_RELATED]-(relationship_node:Relationship)-[:IS_RELATED]-(related_n:Node)-[:HAS_ATTRIBUTE]->(rel_attr:Attribute)-[:HAS_VALUE]->(rel_attr_value:AttributeValue)
        WHERE relationship_node.name in $relationship_names AND rel_attr_value.value in $relationship_attr_values
            AND [relationship_node.name, rel_attr.name, rel_attr_value.value] in $relationship_attr_paths_with_value
        RETURN start_node, rel_path as potential_path, relationship_node.name as rel_identifier, rel_attr.name as potential_attr, rel_attr_value.value as potential_attr_value
        """ % {"node_kind": self.query_request.kind}

        relationship_only_attr_paths_subquery = """
        MATCH rel_path = (start_node:%(node_kind)s)-[:IS_RELATED]-(relationship_node:Relationship)-[:IS_RELATED]-(related_n:Node)
        WHERE %(rel_node_filter)s relationship_node.name in $relationship_only_attr_paths
        RETURN start_node, rel_path as potential_path, relationship_node.name as rel_identifier, "id" as potential_attr, related_n.uuid as potential_attr_value
        """ % {
            "node_kind": self.query_request.kind,
            "rel_node_filter": "related_n.uuid IN $relationship_only_attr_values AND "
            if relationship_only_attr_values
            else "",
        }

        select_subqueries = []
        if attr_paths:
            select_subqueries.append(attr_paths_subquery)
        if attr_paths_with_value:
            select_subqueries.append(attr_paths_with_value_subquery)
        if relationship_attr_paths:
            select_subqueries.append(relationship_attr_paths_subquery)
        if relationship_attr_paths_with_value:
            select_subqueries.append(relationship_attr_paths_with_value_subquery)
        if relationship_only_attr_paths:
            select_subqueries.append(relationship_only_attr_paths_subquery)

        select_subqueries_str = "UNION".join(select_subqueries)

        # ruff: noqa: E501
        query = """
        // get attributes for node and its relationships
        CALL () {
            %(select_subqueries_str)s
        }
        CALL (potential_path) {
            WITH potential_path
            // only the branches and times we care about
            WHERE all(
                r IN relationships(potential_path) WHERE (
                    %(branch_filter)s
                )
            )
            // only get the latest path on the farthest branch from main
            RETURN
                potential_path as matched_path,
                reduce(br_lvl = 0, r in relationships(potential_path) | br_lvl + r.branch_level) AS branch_level_sum,
                %(from_times)s AS from_times,
                // used as tiebreaker for updated relationships that were deleted and added at the same microsecond
                reduce(active_count = 0, r in relationships(potential_path) | active_count + (CASE r.status WHEN "active" THEN 1 ELSE 0 END)) AS active_relationship_count
        }
        WITH
            collect([matched_path, branch_level_sum, from_times, active_relationship_count, potential_attr_value]) as enriched_paths,
            start_node,
            rel_identifier,
            potential_attr
        CALL (enriched_paths) {
            UNWIND enriched_paths as path_to_check
            RETURN path_to_check[0] as current_path, path_to_check[4] as latest_value
            ORDER BY
                path_to_check[1] DESC,
                path_to_check[2][-1] DESC,
                path_to_check[2][-2] DESC,
                path_to_check[3] DESC
            LIMIT 1
        }
        CALL (current_path) {
            // only active paths
            WITH current_path
            WHERE all(r IN relationships(current_path) WHERE r.status = "active")
            RETURN current_path as active_path
        }
        CALL (active_path) {
            // get deepest branch name
            UNWIND %(branch_name_and_level)s as branch_name_and_level
            RETURN branch_name_and_level[0] as branch_name
            ORDER BY branch_name_and_level[1] DESC
            LIMIT 1
        }
        // only duplicate values
        WITH
            collect([start_node.uuid, branch_name]) as nodes_and_branches,
            count(*) as node_count,
            potential_attr as attr_name,
            latest_value as attr_value,
            rel_identifier as relationship_identifier
        WHERE node_count > $min_count_required
        UNWIND nodes_and_branches as node_and_branch
        RETURN
            node_and_branch[0] as node_id,
            node_and_branch[1] as deepest_branch_name,
            node_count,
            attr_name,
            attr_value,
            relationship_identifier
        ORDER BY
            node_id,
            deepest_branch_name,
            node_count,
            attr_name,
            attr_value,
            relationship_identifier
        """ % {
            "select_subqueries_str": select_subqueries_str,
            "branch_filter": branch_filter,
            "from_times": from_times,
            "branch_name_and_level": branch_name_and_level,
        }

        self.add_to_query(query)
        self.return_labels = [
            "node_id",
            "deepest_branch_name",
            "node_count",
            "attr_name",
            "attr_value",
            "relationship_identifier",
        ]


class UniquenessValidationQuery(Query):
    name = "uniqueness_constraint_validation"
    type = QueryType.READ

    def __init__(
        self,
        query_request: NodeUniquenessQueryRequestValued,
        node_ids_to_exclude: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        self.query_request = query_request
        self.node_ids_to_exclude = node_ids_to_exclude
        super().__init__(**kwargs)

    def _is_attribute_large_type(self, db: InfrahubDatabase, node_kind: str, attribute_name: str) -> bool:
        """Determine if an attribute is a large type that should use AttributeValue instead of AttributeValueIndexed."""
        node_schema = db.schema.get(node_kind, branch=self.branch, duplicate=False)
        attr_schema = node_schema.get_attribute(attribute_name)
        return is_large_attribute_type(attr_schema.kind)

    def _build_attr_subquery(
        self,
        node_kind: str,
        attr_path: QueryAttributePathValued,
        index: int,
        branch_filter: str,
        is_first_query: bool,
        is_large_type: bool,
    ) -> tuple[str, dict[str, str | int | float | bool]]:
        attr_name_var = f"attr_name_{index}"
        attr_value_var = f"attr_value_{index}"
        if is_first_query:
            first_query_filter = "WHERE $node_ids_to_exclude IS NULL OR NOT node.uuid IN $node_ids_to_exclude"
        else:
            first_query_filter = ""

        # Determine the appropriate label based on attribute type
        attr_value_label = (
            GraphAttributeValueNode.get_default_label()
            if is_large_type
            else GraphAttributeValueIndexedNode.get_default_label()
        )

        attribute_query = """
MATCH (node:%(node_kind)s)-[:HAS_ATTRIBUTE]->(attr:Attribute {name: $%(attr_name_var)s})-[:HAS_VALUE]->(:%(attr_value_label)s {value: $%(attr_value_var)s})
%(first_query_filter)s
WITH DISTINCT node
CALL (node) {
    MATCH (node)-[r:HAS_ATTRIBUTE]->(attr:Attribute {name: $%(attr_name_var)s})
    WHERE %(branch_filter)s
    WITH attr, r.status = "active" AS is_active
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    WITH attr, is_active
    LIMIT 1
    WITH attr, is_active
    WHERE is_active = TRUE
    MATCH (attr)-[r:HAS_VALUE]->(:AttributeValue {value: $%(attr_value_var)s})
    WHERE %(branch_filter)s
    WITH r
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
    WITH r
    WHERE r.status = "active"
    RETURN 1 AS is_match_%(index)s
}
        """ % {
            "first_query_filter": first_query_filter,
            "node_kind": node_kind,
            "attr_name_var": attr_name_var,
            "attr_value_var": attr_value_var,
            "branch_filter": branch_filter,
            "index": index,
            "attr_value_label": attr_value_label,
        }
        params: dict[str, str | int | float | bool] = {
            attr_name_var: attr_path.attribute_name,
            attr_value_var: attr_path.value,
        }
        return attribute_query, params

    def _build_rel_subquery(
        self,
        node_kind: str,
        rel_path: QueryRelationshipPathValued,
        index: int,
        branch_filter: str,
        is_first_query: bool,
        is_large_type: bool = False,
    ) -> tuple[str, dict[str, str | int | float | bool]]:
        params: dict[str, str | int | float | bool] = {}
        rel_attr_query = ""
        rel_attr_match = ""
        if rel_path.attribute_name and rel_path.attribute_value:
            attr_name_var = f"attr_name_{index}"
            attr_value_var = f"attr_value_{index}"

            # Determine the appropriate label based on relationship attribute type
            rel_attr_value_label = (
                GraphAttributeValueNode.get_default_label()
                if is_large_type
                else GraphAttributeValueIndexedNode.get_default_label()
            )

            rel_attr_query = """
    MATCH (peer)-[r:HAS_ATTRIBUTE]->(attr:Attribute {name: $%(attr_name_var)s})
    WHERE %(branch_filter)s
    WITH attr, r.status = "active" AS is_active
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    WITH attr, is_active
    LIMIT 1
    WITH attr, is_active
    WHERE is_active = TRUE
    MATCH (attr)-[r:HAS_VALUE]->(:%(rel_attr_value_label)s {value: $%(attr_value_var)s})
    WHERE %(branch_filter)s
    WITH r
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
    WITH r
    WHERE r.status = "active"
            """ % {
                "attr_name_var": attr_name_var,
                "attr_value_var": attr_value_var,
                "branch_filter": branch_filter,
                "rel_attr_value_label": rel_attr_value_label,
            }
            rel_attr_match = (
                "-[r:HAS_ATTRIBUTE]->(attr:Attribute {name: $%(attr_name_var)s})-[:HAS_VALUE]->(:%(rel_attr_value_label)s {value: $%(attr_value_var)s})"
                % {
                    "attr_name_var": attr_name_var,
                    "attr_value_var": attr_value_var,
                    "rel_attr_value_label": rel_attr_value_label,
                }
            )
            params[attr_name_var] = rel_path.attribute_name
            params[attr_value_var] = rel_path.attribute_value
        query_arrows = rel_path.relationship_schema.get_query_arrows()
        rel_name_var = f"rel_name_{index}"
        # long path MATCH is required to hit an index on the peer or AttributeValue of the peer
        first_match = (
            "MATCH (node:%(node_kind)s)%(lstart)s[:IS_RELATED]%(lend)s(:Relationship {name: $%(rel_name_var)s})%(rstart)s[:IS_RELATED]%(rend)s"
            % {
                "node_kind": node_kind,
                "lstart": query_arrows.left.start,
                "lend": query_arrows.left.end,
                "rstart": query_arrows.right.start,
                "rend": query_arrows.right.end,
                "rel_name_var": rel_name_var,
            }
        )
        peer_where = f"WHERE {branch_filter}"
        if rel_path.peer_id:
            peer_id_var = f"peer_id_{index}"
            peer_where += f" AND peer.uuid = ${peer_id_var}"
            params[peer_id_var] = rel_path.peer_id
            first_match += "(:Node {uuid: $%(peer_id_var)s})" % {"peer_id_var": peer_id_var}
        else:
            peer_where += " AND peer.uuid <> node.uuid"
            first_match += "(:Node)"
        if rel_attr_match:
            first_match += rel_attr_match
        if is_first_query:
            first_query_filter = "WHERE $node_ids_to_exclude IS NULL OR NOT node.uuid IN $node_ids_to_exclude"
        else:
            first_query_filter = ""
        relationship_query = f"""
{first_match}
{first_query_filter}
WITH DISTINCT node
        """
        relationship_query += """
CALL (node) {
    MATCH (node)%(lstart)s[r:IS_RELATED]%(lend)s(rel:Relationship {name: $%(rel_name_var)s})
    WHERE %(branch_filter)s
    WITH rel, r.status = "active" AS is_active
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    WITH rel, is_active
    LIMIT 1
    WITH rel, is_active
    WHERE is_active = TRUE
    MATCH (rel)%(rstart)s[r:IS_RELATED]%(rend)s(peer:Node)
    %(peer_where)s
    WITH peer, r.status = "active" AS is_active
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    WITH peer, is_active
    LIMIT 1
    WITH peer, is_active
    WHERE is_active = TRUE
%(rel_attr_query)s
    RETURN 1 AS is_match_%(index)s
    LIMIT 1
}
        """ % {
            "rel_name_var": rel_name_var,
            "lstart": query_arrows.left.start,
            "lend": query_arrows.left.end,
            "rstart": query_arrows.right.start,
            "rend": query_arrows.right.end,
            "peer_where": peer_where,
            "rel_attr_query": rel_attr_query,
            "branch_filter": branch_filter,
            "index": index,
        }
        params[rel_name_var] = rel_path.relationship_schema.get_identifier()
        return relationship_query, params

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["node_ids_to_exclude"] = self.node_ids_to_exclude
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string(), is_isolated=False)
        self.params.update(branch_params)

        subqueries = []
        for index, schema_path in enumerate(self.query_request.unique_valued_paths):
            is_first_query = index == 0
            if isinstance(schema_path, QueryAttributePathValued):
                is_large_type = self._is_attribute_large_type(
                    db=db, node_kind=self.query_request.kind, attribute_name=schema_path.attribute_name
                )
                subquery, params = self._build_attr_subquery(
                    node_kind=self.query_request.kind,
                    attr_path=schema_path,
                    index=index,
                    branch_filter=branch_filter,
                    is_first_query=is_first_query,
                    is_large_type=is_large_type,
                )
            else:
                subquery, params = self._build_rel_subquery(
                    node_kind=self.query_request.kind,
                    rel_path=schema_path,
                    index=index,
                    branch_filter=branch_filter,
                    is_first_query=is_first_query,
                )
            subqueries.append(subquery)
            self.params.update(params)

        full_query = "\n".join(subqueries)
        self.add_to_query(full_query)
        self.return_labels = ["node.uuid AS node_uuid", "node.kind AS node_kind"]

    def get_violation_nodes(self) -> list[tuple[str, str]]:
        violation_tuples = []
        for result in self.results:
            violation_tuples.append(
                (result.get_as_type("node_uuid", return_type=str), result.get_as_type("node_kind", return_type=str))
            )
        return violation_tuples
