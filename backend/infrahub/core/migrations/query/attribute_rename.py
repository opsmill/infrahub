from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from infrahub.core.constants import BranchSupportType, RelationshipStatus
from infrahub.core.query import Query

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class AttributeInfo(BaseModel):
    name: str
    node_kind: str
    branch_support: str = BranchSupportType.AWARE.value


class AttributeRenameQuery(Query):
    name = "attribute_rename"
    insert_return: bool = False

    def __init__(
        self,
        previous_attr: AttributeInfo,
        new_attr: AttributeInfo,
        **kwargs: Any,
    ) -> None:
        self.previous_attr = previous_attr
        self.new_attr = new_attr
        super().__init__(**kwargs)

    def render_match(self) -> str:
        """Select the nodes to rename the attribute on. Subclasses narrow this to add their own guards."""
        return """
        // --------------
        // Find all possible nodes
        // --------------
        MATCH (node:%(node_kind)s|Profile%(node_kind)s|Template%(node_kind)s)
        WHERE exists((node)-[:HAS_ATTRIBUTE]-(:Attribute { name: $prev_attr.name }))
        """ % {"node_kind": self.previous_attr.node_kind}

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        self.params["new_attr"] = self.new_attr.model_dump()
        self.params["prev_attr"] = self.previous_attr.model_dump()

        self.params["current_time"] = self.at.to_string()
        self.params["branch_name"] = self.branch.name

        self.params["user_id"] = self.user_id

        self.params["rel_props_create"] = {
            "branch": self.branch.name,
            "branch_level": self.branch.hierarchy_level,
            "status": RelationshipStatus.ACTIVE.value,
            "from": self.at.to_string(),
            "from_user_id": self.user_id,
        }

        self.params["rel_props_delete"] = {
            "branch": self.branch.name,
            "branch_level": self.branch.hierarchy_level,
            "status": RelationshipStatus.DELETED.value,
            "from": self.at.to_string(),
            "from_user_id": self.user_id,
        }

        # Set metadata for vertex properties on default/global branch
        self.params["set_metadata"] = self.branch.is_default or self.branch.is_global

        self.add_to_query(self.render_match())

        add_uuid = db.render_uuid_generation(node_label="new_attr", node_attr="uuid")
        query = """
        // --------------
        // Filter to just the active nodes
        // --------------
        CALL (node) {
            MATCH (root:Root)<-[r:IS_PART_OF]-(node)
            WHERE %(branch_filter)s
            RETURN r
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH node as active_node
        WHERE r.status = "active"
        // --------------
        // Find all the attributes that need to be updated
        // --------------
        CALL (active_node) {
            MATCH (active_node)-[r:HAS_ATTRIBUTE]-(active_attr:Attribute { name: $prev_attr.name })
            WHERE %(branch_filter)s
            RETURN r, active_attr
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH active_node, active_attr
        WHERE r.status = "active"
        // --------------
        // Create the new attribute vertexes
        // --------------
        CREATE (new_attr:Attribute { name: $new_attr.name, branch_support: $new_attr.branch_support })
        %(add_uuid)s
        WITH active_node, active_attr, new_attr
        MATCH (active_attr)-[]-(peer_node)
        WITH DISTINCT active_node, active_attr, new_attr, peer_node
        CALL (active_attr, peer_node) {
            MATCH (active_attr)-[r]-(peer_node)
            WHERE %(branch_filter)s
            RETURN r
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH active_node, active_attr, r as r, peer_node, new_attr
        WHERE r.status = "active"
        // --------------
        // Copy every edge of the old attribute onto the new one, preserving its direction
        // --------------
        CALL (peer_node, r, new_attr) {
            WITH peer_node, r, new_attr
            WHERE startNode(r) = peer_node
            CREATE (new_attr)<-[:$(type(r)) $rel_props_create ]-(peer_node)
        }
        CALL (peer_node, r, new_attr) {
            WITH peer_node, r, new_attr
            WHERE endNode(r) = peer_node
            CREATE (new_attr)-[:$(type(r)) $rel_props_create ]->(peer_node)
        }
        """ % {"branch_filter": branch_filter, "add_uuid": add_uuid}
        self.add_to_query(query)

        if not (self.branch.is_default or self.branch.is_global):
            query = """
            // --------------
            // An edge owned by another branch cannot be modified from here, so the old attribute is
            // ended by shadowing it with a deleted edge; the ones this branch owns are closed below
            // --------------
            CALL (peer_node, r, active_attr) {
                WITH peer_node, r, active_attr
                WHERE r.branch <> $branch_name AND startNode(r) = peer_node
                CREATE (active_attr)<-[:$(type(r)) $rel_props_delete ]-(peer_node)
            }
            CALL (peer_node, r, active_attr) {
                WITH peer_node, r, active_attr
                WHERE r.branch <> $branch_name AND endNode(r) = peer_node
                CREATE (active_attr)-[:$(type(r)) $rel_props_delete ]->(peer_node)
            }
            CALL (r) {
                WITH r
                WHERE r.branch = $branch_name
                SET r.to = $current_time, r.to_user_id = $user_id
            }
            RETURN DISTINCT new_attr
            """
            self.add_to_query(query)
        else:
            query = """
            CALL (r) {
                WITH r
                WHERE r.branch = $branch_name
                SET r.to = $current_time, r.to_user_id = $user_id
            }
            WITH new_attr, active_node
            // --------------
            // Set metadata on new Attribute and Node vertices if on default/global branch
            // --------------
            CALL (new_attr, active_node) {
                WITH new_attr, active_node
                WHERE $set_metadata
                // The renamed Attribute vertex is created here, so it has no prior metadata to snapshot
                SET new_attr.created_at = $current_time, new_attr.created_by = $user_id
                SET new_attr.updated_at = $current_time, new_attr.updated_by = $user_id
                SET active_node.previous_updated_at = CASE
                        WHEN active_node.updated_at IS NULL OR active_node.updated_at <> $current_time THEN active_node.updated_at
                        ELSE active_node.previous_updated_at
                    END,
                    active_node.previous_updated_by = CASE
                        WHEN active_node.updated_at IS NULL OR active_node.updated_at <> $current_time THEN active_node.updated_by
                        ELSE active_node.previous_updated_by
                    END
                SET active_node.updated_at = $current_time, active_node.updated_by = $user_id
            }
            RETURN DISTINCT new_attr
            """
            self.add_to_query(query)
