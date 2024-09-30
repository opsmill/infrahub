from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class DiffMergeQuery(Query):
    name = "diff_merge"
    type = QueryType.WRITE
    insert_return = False

    def __init__(
        self,
        node_diff_dicts: dict[str, Any],
        at: Timestamp,
        target_branch: Branch,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.node_diff_dicts = node_diff_dicts
        self.at = at
        self.target_branch = target_branch
        self.source_branch_name = self.branch.name

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        self.params = {
            "node_diff_dicts": self.node_diff_dicts,
            "at": self.at.to_string(),
            "branch_level": self.target_branch.hierarchy_level,
            "target_branch": self.target_branch.name,
            "source_branch": self.source_branch_name,
        }
        query = """
UNWIND $node_diff_dicts AS node_diff_map
CALL {
    WITH node_diff_map
    WITH node_diff_map, CASE
        WHEN node_diff_map.action = "ADDED" THEN "active"
        WHEN node_diff_map.action = "REMOVED" THEN "deleted"
        ELSE NULL
    END AS node_rel_status
    CALL {
        // ------------------------------
        // only make IS_PART_OF updates if node is ADDED or REMOVED
        // ------------------------------
        WITH node_diff_map, node_rel_status
        WHERE node_rel_status IS NOT NULL
        MATCH (root:Root)
        MATCH (n:Node {uuid: node_diff_map.uuid})
        // ------------------------------
        // check if IS_PART_OF relationship with node_rel_status already exists on the target branch
        // ------------------------------
        CALL {
            WITH root, n, node_rel_status
            OPTIONAL MATCH (root)<-[r_root:IS_PART_OF {branch: $target_branch}]-(n)
            WHERE r_root.status = node_rel_status
            AND r_root.from <= $at
            AND (r_root.to >= $at OR r_root.to IS NULL)
            RETURN r_root
        }
        // ------------------------------
        // set IS_PART_OF.to on source branch and, optionally, target branch
        // ------------------------------
        WITH root, r_root, n, node_rel_status
        CALL {
            WITH root, n, node_rel_status
            OPTIONAL MATCH (root)<-[source_r_root:IS_PART_OF {branch: $source_branch, status: node_rel_status}]-(n)
            WHERE source_r_root.from <= $at AND source_r_root.to IS NULL
            SET source_r_root.to = $at
        }
        WITH root, r_root, n, node_rel_status
        CALL {
            WITH root, n, node_rel_status
            OPTIONAL MATCH (root)<-[target_r_root:IS_PART_OF {branch: $target_branch, status: "active"}]-(n)
            WHERE node_rel_status = "deleted"
            AND target_r_root.from <= $at AND target_r_root.to IS NULL
            SET target_r_root.to = $at
        }
        // ------------------------------
        // create new IS_PART_OF relationship on target_branch
        // ------------------------------
        WITH root, r_root, n, node_rel_status
        WHERE r_root IS NULL
        CREATE (root)<-[:IS_PART_OF { branch: $target_branch, branch_level: $branch_level, from: $at, status: node_rel_status }]-(n)
    }
}
        """
        self.add_to_query(query=query)
