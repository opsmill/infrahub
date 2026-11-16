from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import GLOBAL_BRANCH_NAME, NULL_VALUE, BranchSupportType, RelationshipStatus
from infrahub.core.graph.schema import GraphAttributeValueIndexedNode, GraphAttributeValueNode
from infrahub.core.query import Query, QueryType
from infrahub.types import is_large_attribute_type

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class AttributeAddQuery(Query):
    """Create missing attribute rows on the nodes of the given kinds.

    ``uuids`` optionally restricts the write to specific nodes.

    Created edges live on the query's branch, except when ``branch_support`` is
    agnostic: those rows belong to the global branch, visible from every branch.
    """

    name = "attribute_add"
    type = QueryType.WRITE

    def __init__(
        self,
        node_kinds: list[str],
        attribute_name: str,
        attribute_kind: str,
        branch_support: str,
        default_value: Any | None = None,
        uuids: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        self.node_kinds = node_kinds
        self.attribute_name = attribute_name
        self.attribute_kind = attribute_kind
        self.branch_support = branch_support
        self.default_value = default_value
        self.uuids = uuids
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        write_time = self.at.to_string()

        self.params["node_kinds"] = self.node_kinds
        self.params["node_uuids"] = self.uuids
        self.params["attr_name"] = self.attribute_name
        self.params["branch_support"] = self.branch_support
        self.params["current_time"] = write_time

        if self.default_value is not None:
            self.params["attr_value"] = self.default_value
        else:
            self.params["attr_value"] = NULL_VALUE

        self.params["user_id"] = self.user_id

        self.params["is_branch_agnostic"] = self.branch_support == BranchSupportType.AGNOSTIC.value
        self.params["is_branch_local"] = self.branch_support == BranchSupportType.LOCAL.value
        self.params["agnostic_support"] = BranchSupportType.AGNOSTIC.value
        self.params["global_branch_name"] = GLOBAL_BRANCH_NAME
        self.params["branch_name"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["edge_status"] = RelationshipStatus.ACTIVE.value

        self.params["is_protected_default"] = False

        # Set metadata for vertex properties on default/global branch
        self.params["set_metadata"] = self.branch.is_default or self.branch.is_global

        attr_value_label = GraphAttributeValueNode.get_default_label()
        if not is_large_attribute_type(self.attribute_kind):
            # should be indexed
            attr_value_label += f":{GraphAttributeValueIndexedNode.get_default_label()}"
            match_query = """
            MERGE (av:%(attr_value_label)s { value: $attr_value, is_default: true })
            LIMIT 1
            """ % {"attr_value_label": attr_value_label}
        else:
            # cannot be indexed
            match_query = """
            OPTIONAL MATCH (existing_av:%(attr_value_label)s { value: $attr_value, is_default: true })
            WHERE NOT existing_av:AttributeValueIndexed
            CALL (existing_av) {
                WITH existing_av
                WHERE existing_av IS NULL
                CREATE (:%(attr_value_label)s { value: $attr_value, is_default: true })
            }
            MATCH (av:%(attr_value_label)s { value: $attr_value, is_default: true })
            WHERE NOT av:AttributeValueIndexed
            LIMIT 1
            """ % {"attr_value_label": attr_value_label}

        node_kinds_str = "|".join(self.node_kinds)
        query = """
        %(match_query)s
        MERGE (is_protected_value:Boolean { value: $is_protected_default })
        WITH av, is_protected_value
        MATCH (n:%(node_kinds_str)s)
        WHERE $node_uuids IS NULL OR n.uuid IN $node_uuids
        CALL (n) {
            MATCH (:Root)<-[r:IS_PART_OF]-(n)
            WHERE %(branch_filter)s
            WITH n, r AS is_part_of_e
            OPTIONAL MATCH (n)-[r:HAS_ATTRIBUTE]-(:Attribute { name: $attr_name })
            WHERE %(branch_filter)s
            WITH is_part_of_e, r AS has_attr_e
            RETURN is_part_of_e, has_attr_e
            ORDER BY has_attr_e.branch_level DESC, has_attr_e.from DESC, has_attr_e.status ASC,
                is_part_of_e.branch_level DESC, is_part_of_e.from DESC, is_part_of_e.status ASC
            LIMIT 1
        }
        WITH n, is_part_of_e, has_attr_e, av, is_protected_value
        WHERE is_part_of_e.status = "active" AND (has_attr_e IS NULL OR has_attr_e.status = "deleted")
        // -----------------
        // Use the branch support of the new Attribute and its Node to determine which branch the edges are added to
        // If Attribute is (branch-agnostic) OR (branch-local AND Node is branch-agnostic) then use global branch
        // -----------------
        WITH n, has_attr_e, av, is_protected_value,
            $is_branch_agnostic
            OR ($is_branch_local AND n.branch_support = $agnostic_support) AS on_global_branch
        WITH n, has_attr_e, av, is_protected_value,
            {
                branch: CASE WHEN on_global_branch THEN $global_branch_name ELSE $branch_name END,
                branch_level: CASE WHEN on_global_branch THEN 1 ELSE $branch_level END,
                status: $edge_status,
                from: $current_time,
                from_user_id: $user_id
            } AS edge_props
        CREATE (a:Attribute { name: $attr_name, branch_support: $branch_support })
        CREATE (n)-[new_has_attr:HAS_ATTRIBUTE]->(a)
        SET new_has_attr = edge_props
        CREATE (a)-[new_has_value:HAS_VALUE]->(av)
        SET new_has_value = edge_props
        CREATE (a)-[new_is_protected:IS_PROTECTED]->(is_protected_value)
        SET new_is_protected = edge_props
        %(uuid_generation)s
        // -----------------
        // Set metadata on Attribute and Node vertices if on default/global branch
        // -----------------
        WITH a, n, has_attr_e
        CALL (a, n) {
            WITH a, n
            WHERE $set_metadata
            // -----------------
            // The Attribute vertex is created here, so it has no prior metadata to snapshot for rollback
            // -----------------
            SET a.created_at = $current_time, a.created_by = $user_id, a.updated_at = $current_time, a.updated_by = $user_id
            SET n.previous_updated_at = CASE
                    WHEN n.updated_at IS NULL OR n.updated_at <> $current_time THEN n.updated_at
                    ELSE n.previous_updated_at
                END,
                n.previous_updated_by = CASE
                    WHEN n.updated_at IS NULL OR n.updated_at <> $current_time THEN n.updated_by
                    ELSE n.previous_updated_by
                END
            SET n.updated_at = $current_time, n.updated_by = $user_id
        }
        """ % {
            "match_query": match_query,
            "branch_filter": branch_filter,
            "node_kinds_str": node_kinds_str,
            "uuid_generation": db.render_uuid_generation(node_label="a", node_attr="uuid"),
        }

        self.add_to_query(query)
        self.return_labels = ["n.uuid", "a.uuid"]
