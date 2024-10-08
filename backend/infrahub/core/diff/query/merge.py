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
        WITH node_diff_map, node_rel_status
        WHERE node_rel_status IS NOT NULL
        MATCH (root:Root)
        MATCH (n:Node {uuid: node_diff_map.uuid})
        // ------------------------------
        // set IS_PART_OF.to on source branch and, optionally, target branch
        // ------------------------------
        WITH root, n, node_rel_status
        CALL {
            WITH root, n, node_rel_status
            OPTIONAL MATCH (root)<-[source_r_root:IS_PART_OF {branch: $source_branch, status: node_rel_status}]-(n)
            WHERE source_r_root.from <= $at AND source_r_root.to IS NULL
            SET source_r_root.to = $at
        }
        WITH root, n, node_rel_status
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
        WITH root, n, node_rel_status
        CALL {
            WITH root, n, node_rel_status
            OPTIONAL MATCH (root)<-[r_root:IS_PART_OF {branch: $target_branch}]-(n)
            WHERE r_root.status = node_rel_status
            AND r_root.from <= $at
            AND (r_root.to >= $at OR r_root.to IS NULL)
            WITH root, r_root, n, node_rel_status
            WHERE r_root IS NULL
            CREATE (root)
                <-[:IS_PART_OF { branch: $target_branch, branch_level: $branch_level, from: $at, status: node_rel_status }]
                -(n)
        }
        RETURN n
    }
    WITH n, node_diff_map
    CALL {
        WITH n, node_diff_map
        UNWIND node_diff_map.attributes AS attribute_diff_map
        // ------------------------------
        // handle updates for attributes under this node
        // ------------------------------
        CALL {
            WITH n, attribute_diff_map
            WITH n, attribute_diff_map.name AS attr_name, CASE
                WHEN attribute_diff_map.action = "ADDED" THEN "active"
                WHEN attribute_diff_map.action = "REMOVED" THEN "deleted"
                ELSE NULL
            END AS attr_rel_status
            CALL {
                WITH n, attr_name
                MATCH (n)-[:HAS_ATTRIBUTE]->(a:Attribute {name: attr_name})
                RETURN a
                LIMIT 1
            }
            WITH n, attr_rel_status, a
            // ------------------------------
            // set HAS_ATTRIBUTE.to on source branch if necessary
            // ------------------------------
            CALL {
                WITH n, attr_rel_status, a
                OPTIONAL MATCH (n)
                    -[source_r_attr:HAS_ATTRIBUTE {branch: $source_branch, status: attr_rel_status}]
                    ->(a)
                WHERE source_r_attr.from <= $at AND source_r_attr.to IS NULL
                SET source_r_attr.to = $at
            }
            WITH n, attr_rel_status, a
            // ------------------------------
            // conditionally create new HAS_ATTRIBUTE relationship on target_branch, if necessary
            // ------------------------------
            CALL {
                WITH n, attr_rel_status, a
                OPTIONAL MATCH (n)-[r_attr:HAS_ATTRIBUTE {branch: $target_branch}]->(a)
                WHERE r_attr.status = attr_rel_status
                AND r_attr.from <= $at
                AND (r_attr.to >= $at OR r_attr.to IS NULL)
                WITH n, r_attr, attr_rel_status, a
                WHERE r_attr IS NULL
                CREATE (n)-[:HAS_ATTRIBUTE { branch: $target_branch, branch_level: $branch_level, from: $at, status: attr_rel_status }]->(a)
            }
            RETURN a
        }
        RETURN a
    }
    WITH n, node_diff_map
    CALL {
        WITH n,node_diff_map
        UNWIND node_diff_map.relationships AS relationship_diff_map
        // ------------------------------
        // handle updates for relationships under this node
        // ------------------------------
        CALL {
            WITH n, relationship_diff_map
            WITH n, relationship_diff_map.peer_id AS rel_peer_id, relationship_diff_map.name AS rel_name, CASE
                WHEN relationship_diff_map.action = "ADDED" THEN "active"
                WHEN relationship_diff_map.action = "REMOVED" THEN "deleted"
                ELSE NULL
            END AS related_rel_status
            // ------------------------------
            // set IS_RELATED.to on source branch and, optionally, target_branch
            // ------------------------------
            CALL {
                WITH n, rel_name, rel_peer_id, related_rel_status
                MATCH (n)
                    -[source_r_rel_1:IS_RELATED {branch: $source_branch, status: related_rel_status}]
                    -(r:Relationship {name: rel_name})
                    -[source_r_rel_2:IS_RELATED {branch: $source_branch, status: related_rel_status}]
                    -(:Node {uuid: rel_peer_id})
                WHERE source_r_rel_1.from <= $at AND source_r_rel_1.to IS NULL
                AND source_r_rel_2.from <= $at AND source_r_rel_2.to IS NULL
                SET source_r_rel_1.to = $at
                SET source_r_rel_2.to = $at
                RETURN r
            }
            WITH n, r, rel_name, rel_peer_id, related_rel_status
            CALL {
                WITH n, rel_name, rel_peer_id, related_rel_status
                OPTIONAL MATCH (n)
                    -[target_r_rel_1:IS_RELATED {branch: $target_branch, status: "active"}]
                    -(:Relationship {name: rel_name})
                    -[target_r_rel_2:IS_RELATED {branch: $target_branch, status: "active"}]
                    -(:Node {uuid: rel_peer_id})
                WHERE related_rel_status = "deleted"
                AND target_r_rel_1.from <= $at AND target_r_rel_1.to IS NULL
                AND target_r_rel_2.from <= $at AND target_r_rel_2.to IS NULL
                SET target_r_rel_1.to = $at
                SET target_r_rel_2.to = $at
            }
            WITH n, r, rel_name, rel_peer_id, related_rel_status
            // ------------------------------
            // conditionally create new IS_RELATED relationships on target_branch, if necessary
            // ------------------------------
            CALL {
                WITH n, r, rel_name, rel_peer_id, related_rel_status
                MATCH (p:Node {uuid: rel_peer_id})
                OPTIONAL MATCH (n)
                    -[r_rel_1:IS_RELATED {branch: $target_branch, status: related_rel_status}]
                    -(:Relationship {name: rel_name})
                    -[r_rel_2:IS_RELATED {branch: $target_branch, status: related_rel_status}]
                    -(p)
                WHERE r_rel_1.from <= $at
                AND (r_rel_1.to >= $at OR r_rel_1.to IS NULL)
                AND r_rel_2.from <= $at
                AND (r_rel_2.to >= $at OR r_rel_2.to IS NULL)
                WITH n, r, p, related_rel_status, r_rel_1, r_rel_2
                WHERE r_rel_1 IS NULL
                AND r_rel_2 IS NULL
                CREATE (n)
                    -[:IS_RELATED {branch: $target_branch, branch_level: $branch_level, from: $at, status: related_rel_status}]
                    ->(r)
                    <-[:IS_RELATED {branch: $target_branch, branch_level: $branch_level, from: $at, status: related_rel_status}]
                    -(p)
            }
        }
    }
}
RETURN NULL AS done
        """
        self.add_to_query(query=query)

    # // ------------------------------
    # // handle updates for properties under this attribute
    # // ------------------------------
    # CALL {
    #     WITH a, property_diff_map
    #     WITH a,
    #         property_diff_map.property_type AS prop_type,
    #         CASE
    #             WHEN property_diff_map.is_peer_id = TRUE THEN property_diff_map.value
    #             ELSE NULL
    #         END as prop_peer_id,
    #         CASE
    #             WHEN property_diff_map.is_peer_id = FALSE THEN property_diff_map.value
    #             ELSE NULL
    #         END as prop_value,
    #         CASE
    #             WHEN property_diff_map.action = "ADDED" THEN "active"
    #             WHEN property_diff_map.action = "REMOVED" THEN "deleted"
    #             ELSE NULL
    #         END as prop_rel_status
    #     // ------------------------------
    #     // identify the property node for which we need to update edges
    #     // ------------------------------
    #     OPTIONAL MATCH (peer:Node {uuid: prop_peer_id})
    #     OPTIONAL MATCH (attr_val:AttributeValue {value: prop_value})
    #     WITH a, prop_type, prop_rel_status, COALESCE(peer, attr_val) AS prop_node
    #     // ------------------------------
    #     // set property edge.to on source branch and, optionally, target branch
    #     // ------------------------------
    #     CALL {
    #         WITH a, prop_rel_status, prop_type, prop_node
    #         OPTIONAL MATCH (a)
    #             -[source_r_prop {branch: $source_branch, status: prop_rel_status}]
    #             ->(prop_node)
    #         WHERE type(source_r_prop) = prop_type
    #         AND source_r_prop.from <= $at AND source_r_prop.to IS NULL
    #         SET source_r_prop.to = $at
    #     }
    #     WITH a, prop_rel_status, prop_type, prop_node
    #     CALL {
    #         WITH a, prop_rel_status, prop_type, prop_node
    #         OPTIONAL MATCH (a)
    #             -[target_r_prop {branch: $target_branch, status: "active"}]
    #             ->(prop_node)
    #         WHERE type(target_r_prop) = prop_type
    #         AND prop_rel_status = "deleted"
    #         AND target_r_prop.from <= $at AND target_r_prop.to IS NULL
    #         SET target_r_prop.to = $at
    #     }
    #     // ------------------------------
    #     // conditionally create new edge to prop_node on target_branch, if necessary
    #     // ------------------------------
    #     CALL {
    #         WITH a, prop_rel_status, prop_type, prop_node
    #         OPTIONAL MATCH (a)-[r_prop:prop_type {branch: $target_branch}]->(prop_node)
    #         WHERE r_prop.status = prop_rel_status
    #         AND r_prop.from <= $at
    #         AND (r_prop.to >= $at OR r_prop.to IS NULL)
    #         WITH a, prop_rel_status, prop_type, prop_node, r_prop
    #         WHERE r_prop IS NULL
    #         CREATE (a)-[:prop_type { branch: $target_branch, branch_level: $branch_level, from: $at, status: prop_rel_status }]->(prop_node)
    #     }
    # }
