from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import GLOBAL_BRANCH_NAME, NULL_VALUE, BranchSupportType, RelationshipStatus
from infrahub.core.graph.schema import (
    GraphAttributeValueIndexedNode,
    GraphAttributeValueNode,
    get_attribute_value_key,
)
from infrahub.core.migrations.query.selection import MigrationSelectionQuery
from infrahub.core.query import QueryType
from infrahub.core.query.vertex_metadata import stamp_vertex_metadata
from infrahub.types import is_large_attribute_type

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.database import InfrahubDatabase


class AttributeAddQuery(MigrationSelectionQuery):
    """Create missing attribute rows on the nodes of the given kinds.

    ``node_ids`` optionally restricts the write to specific nodes.

    Created edges live on the query's branch, except when ``branch_support`` is
    agnostic: those rows belong to the global branch, visible from every branch.
    """

    name = "attribute_add"
    type = QueryType.WRITE
    selected_node = "n"

    def __init__(
        self,
        node_kinds: list[str],
        attribute_name: str,
        attribute_kind: str,
        branch_support: str,
        default_value: Any | None = None,
        **kwargs: Any,
    ) -> None:
        self.node_kinds = node_kinds
        self.attribute_name = attribute_name
        self.attribute_kind = attribute_kind
        self.branch_support = branch_support
        self.default_value = default_value
        super().__init__(**kwargs)

    def render_selection(self, carry: Sequence[str] = ()) -> str:
        """Return the selection, passing the variables named in `carry` through its ``WITH`` clause."""
        branch_filter, _ = self.branch.get_query_filter_path(at=self.at.to_string())
        return """
        %(node_match)s
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
        WITH n, is_part_of_e, has_attr_e%(carry)s
        WHERE is_part_of_e.status = "active" AND (has_attr_e IS NULL OR has_attr_e.status = "deleted")
        """ % {
            "node_match": self.render_node_match("n", self.node_kinds),
            "branch_filter": branch_filter,
            "carry": "".join(f", {variable}" for variable in carry),
        }

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        _, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        write_time = self.at.to_string()

        self.params["node_kinds"] = self.node_kinds
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
            self.params["attr_value_key"] = get_attribute_value_key(self.params["attr_value"])
            match_query = """
            MERGE (av:%(attr_value_label)s { value_key: $attr_value_key, value: $attr_value, is_default: true })
            LIMIT 1
            """ % {"attr_value_label": attr_value_label}

        stamp_node, stamp_params = stamp_vertex_metadata(
            "n", at=self.at, operation_ats=self.operation_ats, at_param="current_time"
        )
        self.params.update(stamp_params)
        query = """
        %(match_query)s
        MERGE (is_protected_value:Boolean { value: $is_protected_default })
        WITH av, is_protected_value
        %(selection)s
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
            %(stamp_node)s
        }
        """ % {
            "match_query": match_query,
            "selection": self.render_selection(carry=("av", "is_protected_value")),
            "uuid_generation": db.render_uuid_generation(node_label="a", node_attr="uuid"),
            "stamp_node": stamp_node,
        }

        self.add_to_query(query)
        self.return_labels = ["n.uuid", "a.uuid"]
