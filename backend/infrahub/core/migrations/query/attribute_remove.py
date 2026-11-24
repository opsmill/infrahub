from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import GLOBAL_BRANCH_NAME, RelationshipStatus
from infrahub.core.graph.schema import GraphAttributeRelationships
from infrahub.core.migrations.query.selection import MigrationSelectionQuery
from infrahub.core.query.agnostic_field_closure import CLOSE_UNRETAINED_AGNOSTIC_FIELDS
from infrahub.core.query.vertex_metadata import stamp_vertex_metadata
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.node_schema import NodeSchema

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class AttributeRemoveQuery(MigrationSelectionQuery):
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
        self.selection_kinds: list[str] = []
        super().__init__(**kwargs)

    def render_selection(self) -> str:
        branch_filter, _ = self.branch.get_query_filter_path(at=self.at.to_string())
        return """
        // ------------
        // Find all the active nodes
        // ------------
        %(node_match)s
        CALL (node) {
            MATCH (root:Root)<-[r:IS_PART_OF]-(node)
            WHERE %(branch_filter)s
            RETURN node as n1, r as r1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as active_node, r1 as rb
        WHERE rb.status = "active"
        // ------------
        // Find all the attributes that need to be updated
        // ------------
        CALL (active_node) {
            MATCH (active_node)-[r:HAS_ATTRIBUTE]-(attr:Attribute { name: $attr_name })
            WHERE %(branch_filter)s
            RETURN active_node as n1, r as r1, attr as attr1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as active_node, r1 as rb, attr1 as active_attr
        WHERE rb.status = "active"
        """ % {
            "node_match": self.render_node_match(
                "node",
                self.selection_kinds,
                conditions=[
                    "size($kinds_to_ignore) = 0 OR NOT any(l IN labels(node) WHERE l IN $kinds_to_ignore)",
                    "exists((node)-[:HAS_ATTRIBUTE]-(:Attribute { name: $attr_name }))",
                ],
            ),
            "branch_filter": branch_filter,
        }

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        kinds_to_ignore: list[str] = []
        profile_kinds_to_update = []
        template_kinds_to_update = []

        for node_kind in self.node_kinds:
            new_schema = db.schema.get(name=node_kind, branch=self.branch, duplicate=False)

            if isinstance(new_schema, NodeSchema):
                profile_kinds_to_update.append(f"Profile{node_kind}")
                template_kinds_to_update.append(f"Template{node_kind}")

            if isinstance(new_schema, GenericSchema):
                for inheriting_schema_kind in new_schema.used_by:
                    node_schema = db.schema.get_node_schema(
                        name=inheriting_schema_kind, branch=self.branch, duplicate=False
                    )
                    attr_schema = node_schema.get_attribute_or_none(name=self.attribute_name)
                    if attr_schema and not attr_schema.inherited:
                        kinds_to_ignore.extend((inheriting_schema_kind, f"Template{inheriting_schema_kind}"))
                    else:
                        profile_kinds_to_update.append(f"Profile{inheriting_schema_kind}")
                        template_kinds_to_update.append(f"Template{inheriting_schema_kind}")

        self.params["kinds_to_ignore"] = kinds_to_ignore
        self.params["attr_name"] = self.attribute_name
        self.params["at"] = self.at.to_string()
        self.params["branch_name"] = self.branch.name
        self.params["global_branch_name"] = GLOBAL_BRANCH_NAME

        self.params["user_id"] = self.user_id

        self.params["rel_props"] = {
            "branch": self.branch.name,
            "branch_level": self.branch.hierarchy_level,
            "status": RelationshipStatus.DELETED.value,
            "from": self.at.to_string(),
            "from_user_id": self.user_id,
        }

        # Set metadata for vertex properties on default/global branch
        self.params["set_metadata"] = self.branch.is_default or self.branch.is_global

        self.params["attribute_edge_types"] = list(GraphAttributeRelationships.model_fields)

        self.selection_kinds = self.node_kinds + profile_kinds_to_update + template_kinds_to_update
        self.add_to_query(self.render_selection())
        stamp_attr, stamp_params = stamp_vertex_metadata("active_attr", at=self.at, operation_ats=self.operation_ats)
        self.params.update(stamp_params)
        stamp_node, stamp_params = stamp_vertex_metadata("active_node", at=self.at, operation_ats=self.operation_ats)
        self.params.update(stamp_params)
        query = """
        WITH active_node, active_attr
        MATCH (active_attr)-[]-(peer)
        WITH DISTINCT active_node, active_attr, peer
        CALL (active_attr, peer) {
            MATCH (active_attr)-[r]-(peer)
            WHERE %(branch_filter)s
            RETURN active_attr as a1, r as r1, peer as p1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH active_node, a1 as active_attr, r1 as rb, p1 as peer_node
        WHERE rb.status = "active" AND type(rb) IN $attribute_edge_types
        WITH active_node, active_attr, rb, peer_node, rb.branch = $branch_name AND rb.from = $at AS created_by_this_load
        // An edge an earlier migration of this load created gets no deleted edge, because a deleted edge
        // from the same time as the closed edge would be a second path between the same vertices.
        CALL (peer_node, rb, active_attr, created_by_this_load) {
            WITH peer_node, rb, active_attr, created_by_this_load
            WHERE NOT created_by_this_load AND startNode(rb) = peer_node
            CREATE (active_attr)<-[:$(type(rb)) $rel_props ]-(peer_node)
        }
        CALL (peer_node, rb, active_attr, created_by_this_load) {
            WITH peer_node, rb, active_attr, created_by_this_load
            WHERE NOT created_by_this_load AND endNode(rb) = peer_node
            CREATE (active_attr)-[:$(type(rb)) $rel_props ]->(peer_node)
        }
        FOREACH (i in CASE WHEN rb.branch = $branch_name THEN [1] ELSE [] END |
            SET rb.to = $at, rb.to_user_id = $user_id
        )
        // ------------
        // Set metadata on Attribute and Node vertices if on default/global branch
        // ------------
        WITH active_attr, active_node
        CALL (active_attr, active_node) {
            WITH active_attr, active_node
            WHERE $set_metadata
            %(stamp_attr)s
            %(stamp_node)s
        }
        // ------------
        // Clean up branch-agnostic edges when they become unreachable
        // ------------
        WITH collect(DISTINCT active_attr) AS agnostic_candidates
        %(close_unretained_agnostic_fields)s
        UNWIND agnostic_candidates AS active_attr
        RETURN DISTINCT active_attr
        """ % {
            "branch_filter": branch_filter,
            "close_unretained_agnostic_fields": CLOSE_UNRETAINED_AGNOSTIC_FIELDS,
            "stamp_attr": stamp_attr,
            "stamp_node": stamp_node,
        }
        self.add_to_query(query)
