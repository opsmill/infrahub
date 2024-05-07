from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants.relationship_label import RELATIONSHIP_TO_VALUE_LABEL
from infrahub.core.query import Query

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

    from .model import NodeUniquenessQueryRequest


class NodeUniqueAttributeConstraintQuery(Query):
    name = "node_constraints_uniqueness"
    insert_return = False
    attribute_property_map = {"value": RELATIONSHIP_TO_VALUE_LABEL}

    def __init__(
        self,
        query_request: NodeUniquenessQueryRequest,
        min_count_required: int = 1,
        *args: Any,
        **kwargs: Any,
    ):
        self.query_request = query_request
        self.min_count_required = min_count_required
        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: Any) -> None:
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string(), is_isolated=False)
        self.params.update(branch_params)
        from_times = db.render_list_comprehension(items="relationships(potential_path)", item_name="from")
        branch_name_and_level = db.render_list_comprehension_with_list(
            items="relationships(active_path)", item_names=["branch", "branch_level"]
        )

        attr_paths_param, attr_paths_with_value_param = [], []
        for attr_path in self.query_request.unique_attribute_paths:
            try:
                property_rel_name = self.attribute_property_map[attr_path.property_name or "value"]
            except KeyError as exc:
                raise ValueError(
                    f"{attr_path.property_name} is not a valid property for a uniqueness constraint"
                ) from exc
            if attr_path.value:
                attr_paths_with_value_param.append((attr_path.attribute_name, property_rel_name, attr_path.value))
            else:
                attr_paths_param.append((attr_path.attribute_name, property_rel_name))

        relationship_names = set()
        relationship_attr_paths = []
        relationship_only_attr_paths = []
        relationship_attr_paths_with_value = []
        for rel_path in self.query_request.relationship_attribute_paths:
            relationship_names.add(rel_path.identifier)
            if rel_path.attribute_name and rel_path.value:
                relationship_attr_paths_with_value.append(
                    (rel_path.identifier, rel_path.attribute_name, rel_path.value)
                )
                relationship_names.add(rel_path.identifier)
            elif rel_path.attribute_name:
                relationship_attr_paths.append((rel_path.identifier, rel_path.attribute_name))
            else:
                relationship_only_attr_paths.append(rel_path.identifier)

        self.params.update(
            {
                "node_kind": self.query_request.kind,
                "attr_paths": attr_paths_param,
                "attr_paths_with_value": attr_paths_with_value_param,
                "relationship_names": list(relationship_names),
                "relationship_attr_paths": relationship_attr_paths,
                "relationship_attr_paths_with_value": relationship_attr_paths_with_value,
                "relationship_only_attr_paths": relationship_only_attr_paths,
                "min_count_required": self.min_count_required,
            }
        )

        # ruff: noqa: E501
        query = """
        // group by node
        MATCH (start_node:Node)
        WHERE $node_kind IN LABELS(start_node)
        // get attributes for node and its relationships
        CALL {
            WITH start_node
            MATCH attr_path = (start_node:Node)-[:HAS_ATTRIBUTE]->(attr:Attribute)-[r:HAS_VALUE]->(attr_value:AttributeValue)
            WHERE [attr.name, type(r)] in $attr_paths OR [attr.name, type(r), attr_value.value] in $attr_paths_with_value
            RETURN attr_path as potential_path, NULL as rel_identifier, attr.name as potential_attr, attr_value.value as potential_attr_value
            UNION
            WITH start_node
            MATCH rel_path = (start_node:Node)-[:IS_RELATED]-(relationship_node:Relationship)-[:IS_RELATED]-(related_n:Node)-[:HAS_ATTRIBUTE]->(rel_attr:Attribute)-[:HAS_VALUE]->(rel_attr_value:AttributeValue)
            WHERE relationship_node.name in $relationship_names
               AND ([relationship_node.name, rel_attr.name] in $relationship_attr_paths
               OR [relationship_node.name, rel_attr.name, rel_attr_value.value] in $relationship_attr_paths_with_value)
            RETURN rel_path as potential_path, relationship_node.name as rel_identifier, rel_attr.name as potential_attr, rel_attr_value.value as potential_attr_value
            UNION
            WITH start_node
            MATCH rel_path = (start_node:Node)-[:IS_RELATED]-(relationship_node:Relationship)-[:IS_RELATED]-(related_n:Node)
            WHERE relationship_node.name in $relationship_only_attr_paths
            RETURN rel_path as potential_path, relationship_node.name as rel_identifier, "id" as potential_attr, related_n.uuid as potential_attr_value
        }
        CALL {
            WITH potential_path
            WITH potential_path  // workaround for neo4j not allowing WHERE in a WITH of a subquery
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
        CALL {
            WITH enriched_paths
            UNWIND enriched_paths as path_to_check
            RETURN path_to_check[0] as current_path, path_to_check[4] as latest_value
            ORDER BY
                path_to_check[1] DESC,
                path_to_check[2][-1] DESC,
                path_to_check[2][-2] DESC,
                path_to_check[3] DESC
            LIMIT 1
        }
        CALL {
            // only active paths
            WITH current_path
            WITH current_path  // workaround for neo4j not allowing WHERE in a WITH of a subquery
            WHERE all(r IN relationships(current_path) WHERE r.status = "active")
            RETURN current_path as active_path
        }
        CALL {
            // get deepest branch name
            WITH active_path
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
        """ % {"branch_filter": branch_filter, "from_times": from_times, "branch_name_and_level": branch_name_and_level}

        self.add_to_query(query)
        self.return_labels = [
            "node_id",
            "deepest_branch_name",
            "node_count",
            "attr_name",
            "attr_value",
            "relationship_identifier",
        ]
