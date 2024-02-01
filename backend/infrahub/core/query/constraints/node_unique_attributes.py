from __future__ import annotations

from typing import TYPE_CHECKING, Any, Union

from infrahub.core.query import Query

if TYPE_CHECKING:
    from infrahub.core.schema import GenericSchema, NodeSchema
    from infrahub.database import InfrahubDatabase


class NodeUniqueAttributeConstraintQuery(Query):
    name = "node_constraints_uniqueness"

    def __init__(self, schema: Union[NodeSchema, GenericSchema], *args: Any, **kwargs: Any):
        self.schema = schema
        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: Any) -> None:
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string(), is_isolated=False)
        self.params.update(branch_params)
        from_times = db.render_list_comprehension(items="relationships(potential_path)", item_name="from")

        attr_names = {attr_schema.name for attr_schema in self.schema.unique_attributes}
        relationship_attr_paths = []

        if self.schema.uniqueness_constraints:
            for uniqueness_constraint in self.schema.uniqueness_constraints:
                for path in uniqueness_constraint:
                    if "__" in path:
                        relationship_name, attribute_name = path.split("__")
                    else:
                        relationship_name, attribute_name = None, path
                    if not relationship_name:
                        attr_names.add(attribute_name)
                        continue
                    relationship = self.schema.get_relationship(relationship_name)
                    relationship_attr_paths.append((relationship.identifier, attribute_name))

        self.params.update(
            {
                "node_kind": self.schema.kind,
                "attr_names": list(attr_names),
                "relationship_attr_paths": relationship_attr_paths,
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
            WHERE all(r IN relationships(current_path) WHERE r.status = "active")
            RETURN current_path as active_path
        }
        // only duplicate values
        WITH
            start_node.kind as kind,
            collect(start_node.uuid) as node_ids,
            count(*) as node_count,
            potential_attr.name as attr_name,
            latest_value as attr_value,
            rel_identifier as relationship_identifier
        WHERE node_count > 1
        """ % {"branch_filter": branch_filter, "from_times": from_times}

        self.add_to_query(query)
        self.return_labels = ["kind", "node_ids", "node_count", "attr_name", "attr_value", "relationship_identifier"]
