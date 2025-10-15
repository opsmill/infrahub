from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import RelationshipStatus
from infrahub.core.graph.schema import GraphAttributeRelationships
from infrahub.core.query import Query
from infrahub.core.schema.generic_schema import GenericSchema

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from infrahub.database import InfrahubDatabase


class AttributeRemoveQuery(Query):
    name = "attribute_remove"
    insert_return: bool = False

    def __init__(
        self,
        attribute_name: str,
        node_kinds: list[str],
        **kwargs: Any,
    ) -> None:
        self.attribute_name = attribute_name
        self.node_kinds = node_kinds
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        kinds_to_ignore = []
        profile_kinds_to_update = []

        for node_kind in self.node_kinds:
            new_schema = db.schema.get(name=node_kind, branch=self.branch, duplicate=False)

        if isinstance(new_schema, GenericSchema):
            for inheriting_schema_kind in new_schema.used_by:
                node_schema = db.schema.get_node_schema(
                    name=inheriting_schema_kind, branch=self.branch, duplicate=False
                )
                attr_schema = node_schema.get_attribute_or_none(name=self.attribute_name)
                if attr_schema and not attr_schema.inherited:
                    kinds_to_ignore.append(inheriting_schema_kind)
                else:
                    profile_kinds_to_update.append(f"Profile{inheriting_schema_kind}")

        self.params["kinds_to_ignore"] = kinds_to_ignore
        self.params["attr_name"] = self.attribute_name
        self.params["current_time"] = self.at.to_string()
        self.params["branch_name"] = self.branch.name

        self.params["rel_props"] = {
            "branch": self.branch.name,
            "branch_level": self.branch.hierarchy_level,
            "status": RelationshipStatus.DELETED.value,
            "from": self.at.to_string(),
        }

        def render_sub_query_per_rel_type(rel_type: str, rel_def: FieldInfo) -> str:
            subquery = [
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

        node_kinds_str = "|".join(self.node_kinds + profile_kinds_to_update)
        query = """
        // Find all the active nodes
        MATCH (node:%(node_kinds)s)
        WHERE (size($kinds_to_ignore) = 0 OR NOT any(l IN labels(node) WHERE l IN $kinds_to_ignore))
        AND exists((node)-[:HAS_ATTRIBUTE]-(:Attribute { name: $attr_name }))
        CALL (node) {
            MATCH (root:Root)<-[r:IS_PART_OF]-(node)
            WHERE %(branch_filter)s
            RETURN node as n1, r as r1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as active_node, r1 as rb
        WHERE rb.status = "active"
        // Find all the attributes that need to be updated
        CALL (active_node) {
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
        WITH DISTINCT active_attr, peer
        CALL (active_attr, peer) {
            MATCH (active_attr)-[r]-(peer)
            WHERE %(branch_filter)s
            RETURN active_attr as a1, r as r1, peer as p1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH a1 as active_attr, r1 as rb, p1 as peer_node
        WHERE rb.status = "active"
        CALL (peer_node, rb, active_attr) {
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
            "node_kinds": node_kinds_str,
        }
        self.add_to_query(query)
