from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.constants import RelationshipStatus
from infrahub.core.graph.schema import GraphAttributeRelationships
from infrahub.core.schema.generic_schema import GenericSchema

from ..query import AttributeMigrationQuery
from ..shared import AttributeSchemaMigration

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from infrahub.database import InfrahubDatabase


class NodeAttributeRemoveMigrationQuery01(AttributeMigrationQuery):
    name = "migration_node_attribute_remove_01"
    insert_return: bool = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        attr_name = self.migration.schema_path.field_name
        kinds_to_ignore = []
        if isinstance(self.migration.new_node_schema, GenericSchema) and attr_name is not None:
            for inheriting_schema_kind in self.migration.new_node_schema.used_by:
                node_schema = db.schema.get_node_schema(
                    name=inheriting_schema_kind, branch=self.branch, duplicate=False
                )
                attr_schema = node_schema.get_attribute_or_none(name=attr_name)
                if attr_schema and not attr_schema.inherited:
                    kinds_to_ignore.append(inheriting_schema_kind)

        self.params["node_kind"] = self.migration.new_schema.kind
        self.params["kinds_to_ignore"] = kinds_to_ignore
        self.params["attr_name"] = attr_name
        self.params["current_time"] = self.at.to_string()
        self.params["branch_name"] = self.branch.name
        self.params["branch_support"] = self.migration.previous_attribute_schema.get_branch().value

        self.params["rel_props"] = {
            "branch": self.branch.name,
            "branch_level": self.branch.hierarchy_level,
            "status": RelationshipStatus.DELETED.value,
            "from": self.at.to_string(),
        }

        def render_sub_query_per_rel_type(rel_type: str, rel_def: FieldInfo) -> str:
            subquery = [
                "WITH peer_node, rb, active_attr",
                "WITH peer_node, rb, active_attr",
                f'WHERE type(rb) = "{rel_type}"',
            ]
            if rel_def.default.direction.value == "outbound":
                subquery.append(f"CREATE (active_attr)-[:{rel_type} $rel_props ]->(peer_node)")
            elif rel_def.default.direction.value == "inbound":
                subquery.append(f"CREATE (active_attr)<-[:{rel_type} $rel_props ]-(peer_node)")
            else:
                subquery.append(f"CREATE (active_attr)-[:{rel_type} $rel_props ]-(peer_node)")

            subquery.append("RETURN peer_node as p2")
            return "\n".join(subquery)

        sub_queries = [
            render_sub_query_per_rel_type(rel_type, rel_def)
            for rel_type, rel_def in GraphAttributeRelationships.model_fields.items()
        ]
        sub_query_all = "\nUNION\n".join(sub_queries)

        query = """
        // Find all the active nodes
        MATCH (node:%(node_kind)s)
        WHERE (size($kinds_to_ignore) = 0 OR NOT any(l IN labels(node) WHERE l IN $kinds_to_ignore))
        AND exists((node)-[:HAS_ATTRIBUTE]-(:Attribute { name: $attr_name }))
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
            MATCH (active_node)-[r:HAS_ATTRIBUTE]-(attr:Attribute { name: $attr_name })
            WHERE %(branch_filter)s
            RETURN active_node as n1, r as r1, attr as attr1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as active_node, r1 as rb, attr1 as active_attr
        WHERE rb.status = "active"
        WITH active_attr
        MATCH (active_attr)-[]-(peer)
        CALL {
            WITH active_attr, peer
            MATCH (active_attr)-[r]-(peer)
            WHERE %(branch_filter)s
            RETURN active_attr as a1, r as r1, peer as p1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH a1 as active_attr, r1 as rb, p1 as peer_node
        WHERE rb.status = "active"
        CALL {
            %(sub_query_all)s
        }
        WITH p2 as peer_node, rb, active_attr
        FOREACH (i in CASE WHEN rb.branch = $branch_name THEN [1] ELSE [] END |
            SET rb.to = $current_time
        )
        RETURN DISTINCT active_attr
        """ % {
            "branch_filter": branch_filter,
            "sub_query_all": sub_query_all,
            "node_kind": self.migration.new_schema.kind,
        }
        self.add_to_query(query)


class NodeAttributeRemoveMigration(AttributeSchemaMigration):
    name: str = "node.attribute.remove"
    queries: Sequence[type[AttributeMigrationQuery]] = [NodeAttributeRemoveMigrationQuery01]  # type: ignore[assignment]
