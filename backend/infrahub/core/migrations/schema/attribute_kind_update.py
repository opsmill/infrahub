from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Sequence

from infrahub.core.constants import BranchSupportType
from infrahub.core.graph.schema import GraphAttributeRelationships
from infrahub.core.query import Query, QueryType

from ..shared import AttributeSchemaMigration

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from infrahub.database import InfrahubDatabase


class AttributeKindUpdateMigrationQuery01(Query):
    name = "migration_attribute_kind_update_01"
    type: QueryType = QueryType.WRITE

    def __init__(
        self,
        *args: Any,
        migration: AttributeKindUpdateMigration,
        **kwargs: Any,
    ):
        self.migration = migration

        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: Dict[str, Any]) -> None:
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        self.params["node_kind"] = self.migration.new_node_schema.kind
        self.params["attr_name"] = self.migration.new_attribute_schema.name
        self.params["previous_attr_type"] = self.migration.previous_attribute_schema.kind
        self.params["new_attr_type"] = self.migration.new_attribute_schema.kind
        self.params["current_time"] = self.at.to_string()
        self.params["branch_name"] = self.branch.name

        if self.branch.is_default:
            self.params["branch_support"] = self.migration.new_attribute_schema._branch.value
        else:
            self.params["branch_support"] = BranchSupportType.LOCAL.value

        self.params["rel_props"] = {
            "branch": self.branch.name,
            "branch_level": self.branch.hierarchy_level,
            "status": "active",
            "from": self.at.to_string(),
        }

        def render_sub_query_per_rel_type(rel_type: str, rel_def: FieldInfo) -> str:
            subquery = [
                "WITH peer_node, rb, active_attr, new_attr",
                "WITH peer_node, rb, active_attr, new_attr",
                f'WHERE type(rb) = "{rel_type}"',
            ]
            if rel_def.default.direction.value == "outbound":
                subquery.append(f"CREATE (new_attr)-[:{rel_type} $rel_props ]->(peer_node)")
            elif rel_def.default.direction.value == "inbound":
                subquery.append(f"CREATE (new_attr)<-[:{rel_type} $rel_props ]-(peer_node)")
            else:
                subquery.append(f"CREATE (new_attr)-[:{rel_type} $rel_props ]-(peer_node)")

            subquery.append("RETURN peer_node as p2")
            return "\n".join(subquery)

        sub_queries = [
            render_sub_query_per_rel_type(rel_type, rel_def)
            for rel_type, rel_def in GraphAttributeRelationships.model_fields.items()
        ]
        sub_query_all = "\nUNION\n".join(sub_queries)

        add_uuid = db.render_uuid_generation(node_label="new_attr", node_attr="uuid")
        query = """
        // Find all the active nodes
        MATCH (node:Node)
        WHERE $node_kind IN LABELS(node) AND NOT exists((node)-[:HAS_ATTRIBUTE]-(:Attribute { name: $attr_name, type: $new_attr_type }))
        CALL {
            WITH node
            MATCH (root:Root)<-[r:IS_PART_OF]-(node)
            WHERE %(branch_filter)s
            RETURN node as n1, r as r1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as active_node, r1 as rb
        WHERE rb.status = "active"
        // Find all the attribute that need to be updated
        CALL {
            WITH active_node
            MATCH (active_node)-[r:HAS_ATTRIBUTE]-(attr:Attribute { name: $attr_name, type: $previous_attr_type })
            WHERE %(branch_filter)s
            RETURN active_node as n1, r as r1, attr as attr1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as active_node, r1 as rb, attr1 as active_attr
        WHERE rb.status = "active"
        CREATE (new_attr:Attribute:AttributeLocal { name: $attr_name, type: $new_attr_type, branch_support: $branch_support })
        %(add_uuid)s
        WITH active_attr, new_attr
        MATCH (active_attr)-[]-(peer)
        CALL {
            WITH active_attr, peer
            MATCH (active_attr)-[r]-(peer)
            WHERE %(branch_filter)s
            RETURN active_attr as a1, r as r1, peer as p1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH a1 as active_attr, r1 as rb, p1 as peer_node, new_attr
        WHERE rb.status = "active"
        CALL {
            %(sub_query_all)s
        }
        WITH p2 as peer_node, rb
        FOREACH (i in CASE WHEN rb.branch = $branch_name THEN [1] ELSE [] END |
            SET rb.to = $current_time
        )
        """ % {"branch_filter": branch_filter, "add_uuid": add_uuid, "sub_query_all": sub_query_all}
        self.add_to_query(query)
        self.return_labels = ["peer_node"]


class AttributeKindUpdateMigration(AttributeSchemaMigration):
    name: str = "attribute.kind.update"
    queries: Sequence[type[Query]] = [AttributeKindUpdateMigrationQuery01]
