from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Sequence

from infrahub.core.constants import BranchSupportType
from infrahub.core.graph.schema import GraphAttributeRelationships

from ..shared import AttributeMigrationQuery, AttributeSchemaMigration

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from infrahub.database import InfrahubDatabase


class AttributeNameUpdateMigrationQuery01(AttributeMigrationQuery):
    name = "migration_attribute_name_update_01"
    insert_return: bool = False

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: Dict[str, Any]) -> None:
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        self.params["node_kind"] = self.migration.new_node_schema.kind
        self.params["new_attr_name"] = self.migration.new_attribute_schema.name

        attr_id = self.migration.new_attribute_schema.id
        if not attr_id:
            raise ValueError("The Id is not defined on new_attribute_schema")
        prev_attr = self.migration.previous_node_schema.get_attribute_by_id(id=attr_id)
        self.params["prev_attr_name"] = prev_attr.name
        self.params["current_time"] = self.at.to_string()
        self.params["branch_name"] = self.branch.name

        if self.branch.is_default:
            self.params["branch_support"] = self.migration.new_attribute_schema.get_branch().value
        else:
            self.params["branch_support"] = BranchSupportType.LOCAL.value

        self.params["rel_props"] = {
            "branch": self.branch.name,
            "branch_level": self.branch.hierarchy_level,
            "status": "active",
            "from": self.at.to_string(),
        }

        self.params["is_protected_default"] = False
        self.params["is_visible_default"] = True

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
        WHERE $node_kind IN LABELS(node) AND exists((node)-[:HAS_ATTRIBUTE]-(:Attribute { name: $prev_attr_name }))
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
        // Find all the attributes that need to be updated
        CALL {
            WITH active_node
            MATCH (active_node)-[r:HAS_ATTRIBUTE]-(attr:Attribute { name: $prev_attr_name })
            WHERE %(branch_filter)s
            RETURN active_node as n1, r as r1, attr as attr1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as active_node, r1 as rb, attr1 as active_attr
        WHERE rb.status = "active"
        CREATE (new_attr:Attribute { name: $new_attr_name, branch_support: $branch_support })
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
        WITH p2 as peer_node, rb, new_attr
        FOREACH (i in CASE WHEN rb.branch = $branch_name THEN [1] ELSE [] END |
            SET rb.to = $current_time
        )
        RETURN DISTINCT new_attr
        """ % {"branch_filter": branch_filter, "add_uuid": add_uuid, "sub_query_all": sub_query_all}
        self.add_to_query(query)


class AttributeNameUpdateMigration(AttributeSchemaMigration):
    name: str = "attribute.name.update"
    queries: Sequence[type[AttributeMigrationQuery]] = [AttributeNameUpdateMigrationQuery01]  # type: ignore[assignment]
