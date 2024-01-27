from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query

if TYPE_CHECKING:
    from infrahub.core.schema import NodeSchema
    from infrahub.database import InfrahubDatabase


class NodeConstraintsUniquenessQuery(Query):
    name = "node_constraints_uniqueness"

    def __init__(self, schema: NodeSchema, *args: Any, **kwargs: Any):
        self.schema = schema
        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: Any) -> None:
        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at.to_string(), use_cross_branch_time=True
        )
        self.params.update(branch_params)
        self.params.update(
            {
                "node_kind": self.schema.kind,
                "attr_names": [attr_schema.name for attr_schema in self.schema.unique_attributes],
            }
        )
        from_times = db.render_list_comprehension(items="relationships(sub_path)", item_name="from")

        query = """
        // group by node and attribute
        MATCH (sub_n:Node)-[:HAS_ATTRIBUTE]-(sub_attr:Attribute)
        WHERE $node_kind IN LABELS(sub_n)
        CALL {
        WITH sub_n, sub_attr
        // get all paths to an attribute value for this node and this attribute
        MATCH sub_path = (sub_n:Node)-[:HAS_ATTRIBUTE]-(sub_attr:Attribute)-[:HAS_VALUE]-(sub_attr_value:AttributeValue)
        WHERE
            // only include the attributes we care about
            sub_attr.name IN $attr_names
            // only the branches and times we care about
            AND all(
            r IN relationships(sub_path) WHERE (
                %(branch_filter)s
            )
        )
        // only get the latest path on the farthest branch from main
        WITH
            sub_attr,
            sub_attr_value,
            sub_path,
            reduce(br_lvl = 0, r in relationships(sub_path) | br_lvl + r.branch_level) AS branch_level
            , %(from_times)s AS from_times
        RETURN sub_n AS n, sub_attr AS attr, sub_attr_value AS attr_value, all(r IN relationships(sub_path) WHERE r.status = "active") as is_active
        ORDER BY
            branch_level DESC
            , from_times[1] DESC
            , from_times[2] DESC
        LIMIT 1
        }
        // filter by the active path to exclude deleted nodes
        CALL {
          WITH n, attr, attr_value, is_active
          WHERE is_active = TRUE
          RETURN n as final_n, attr as final_attr, attr_value as final_attr_value
        }
        // only duplicate values
        WITH
            final_n.kind as kind,
            collect(final_n.uuid) as node_ids,
            count(*) as node_count,
            final_attr.name as attr_name,
            final_attr_value.value as attr_value
        WHERE node_count > 1
        """ % {"branch_filter": branch_filter, "from_times": from_times}

        self.add_to_query(query)
        self.return_labels = ["kind", "node_ids", "node_count", "attr_name", "attr_value"]
