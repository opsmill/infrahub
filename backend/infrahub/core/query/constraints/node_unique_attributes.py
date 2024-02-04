from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

    from .request import NodeUniquenessQueryRequest


class NodeUniqueAttributeConstraintQuery(Query):
    name = "node_constraints_uniqueness"

    def __init__(
        self,
        query_request: NodeUniquenessQueryRequest,
        *args: Any,
        **kwargs: Any,
    ):
        self.query_request = query_request
        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: Any) -> None:
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string(), is_isolated=False)
        self.params.update(branch_params)
        from_times = db.render_list_comprehension(items="relationships(potential_path)", item_name="from")

        self.params.update(
            {
                "node_kind": self.query_request.kind,
                "attr_names": self.query_request.unique_attribute_names,
                "relationship_attr_paths": [
                    (rel_path.identifier, rel_path.attribute_name)
                    for rel_path in self.query_request.relationship_attribute_paths
                ],
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
            MATCH attr_path = (start_node:Node)-[:HAS_ATTRIBUTE]-(attr:Attribute)-[:HAS_VALUE]-(attr_value:AttributeValue)
            WHERE attr.name in $attr_names
            RETURN attr_path as potential_path, start_node as potential_node, NULL as rel_identifier, attr as potential_attr, attr_value as potential_attr_value
            UNION
            WITH start_node
            MATCH rel_path = (start_node:Node)-[:IS_RELATED]-(relationship_node:Relationship)-[:IS_RELATED]-(related_n:Node)-[:HAS_ATTRIBUTE]-(rel_attr:Attribute)-[:HAS_VALUE]-(rel_attr_value:AttributeValue)
            WHERE [relationship_node.name, rel_attr.name] in $relationship_attr_paths
            RETURN rel_path as potential_path, start_node as potential_node, relationship_node.name as rel_identifier, rel_attr as potential_attr, rel_attr_value as potential_attr_value
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
                %(from_times)s AS from_times
        }
        WITH
            collect([matched_path, branch_level_sum, from_times, potential_attr_value.value]) as enriched_paths,
            start_node,
            rel_identifier,
            potential_attr
        CALL {
            WITH enriched_paths
            UNWIND enriched_paths as path_to_check
            RETURN path_to_check[0] as current_path, path_to_check[3] as latest_value
            ORDER BY
                path_to_check[1] DESC,
                path_to_check[2][-1] DESC,
                path_to_check[2][-2] DESC
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
            UNWIND extract(r in relationships(active_path) | [r.branch, r.branch_level]) as branch_name_and_level
            RETURN branch_name_and_level[0] as branch_name
            ORDER BY branch_name_and_level[1] DESC
            LIMIT 1
        }
        // only duplicate values
        WITH
            collect(start_node.uuid) as node_ids,
            count(*) as node_count,
            potential_attr.name as attr_name,
            latest_value as attr_value,
            rel_identifier as relationship_identifier,
            branch_name as deepest_branch_name
        WHERE node_count > 1
        UNWIND node_ids as node_id
        """ % {"branch_filter": branch_filter, "from_times": from_times}

        self.add_to_query(query)
        self.return_labels = [
            "node_id",
            "node_count",
            "attr_name",
            "attr_value",
            "relationship_identifier",
            "deepest_branch_name",
        ]
