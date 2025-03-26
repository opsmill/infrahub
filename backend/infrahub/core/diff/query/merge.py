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

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "node_diff_dicts": self.node_diff_dicts,
            "at": self.at.to_string(),
            "branch_level": self.target_branch.hierarchy_level,
            "target_branch": self.target_branch.name,
            "source_branch": self.source_branch_name,
        }
        # ruff: noqa: E501
        query = """
UNWIND $node_diff_dicts AS node_diff_map
CALL {
    WITH node_diff_map
    MATCH (n:Node {uuid: node_diff_map.uuid})
    RETURN n
}
WITH n, node_diff_map
CALL {
    WITH n, node_diff_map
    WITH n, node_diff_map, CASE
        WHEN node_diff_map.action = "ADDED" THEN "active"
        WHEN node_diff_map.action = "REMOVED" THEN "deleted"
        ELSE NULL
    END AS node_rel_status
    CALL {
        // ------------------------------
        // only make IS_PART_OF updates if node is ADDED or REMOVED
        // ------------------------------
        WITH n, node_diff_map, node_rel_status
        WITH n, node_diff_map, node_rel_status
        WHERE node_rel_status IS NOT NULL
        MATCH (root:Root)
        // ------------------------------
        // set IS_PART_OF.to, optionally, target branch
        // ------------------------------
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
        // ------------------------------
        // shortcut to delete all attributes and relationships for this node if the node is deleted
        // ------------------------------
        CALL {
            WITH n, node_rel_status
            WITH n, node_rel_status
            WHERE node_rel_status = "deleted"
            CALL {
                WITH n
                OPTIONAL MATCH (n)-[rel1:IS_RELATED]-(:Relationship)-[rel2]-(p)
                WHERE (p.uuid IS NULL OR n.uuid <> p.uuid)
                AND rel1.branch = $target_branch
                AND rel2.branch = $target_branch
                AND rel1.status = "active"
                AND rel2.status = "active"
                RETURN rel1, rel2
                UNION
                WITH n
                OPTIONAL MATCH (n)-[rel1:HAS_ATTRIBUTE]->(:Attribute)-[rel2]->()
                WHERE type(rel2) <> "HAS_ATTRIBUTE"
                AND rel1.branch = $target_branch
                AND rel2.branch = $target_branch
                AND rel1.status = "active"
                AND rel2.status = "active"
                RETURN rel1, rel2
            }
            WITH n, rel1, rel2
            WHERE rel1.to IS NULL
            AND rel2.to IS NULL
            AND rel1.from <= $at
            AND rel2.from <= $at
            SET rel1.to = $at
            SET rel2.to = $at
            // ------------------------------
            // and delete HAS_OWNER and HAS_SOURCE edges to this node if the node is deleted
            // ------------------------------
            WITH n
            CALL {
                WITH n
                CALL {
                    WITH n
                    MATCH (n)<-[rel:HAS_OWNER]-()
                    WHERE rel.branch = $target_branch
                    AND rel.status = "active"
                    AND rel.from <= $at
                    AND rel.to IS NULL
                    RETURN rel
                    UNION
                    MATCH (n)<-[rel:HAS_SOURCE]-()
                    WHERE rel.branch = $target_branch
                    AND rel.status = "active"
                    AND rel.from <= $at
                    AND rel.to IS NULL
                    RETURN rel
                }
                SET rel.to = $at
            }
        }
    }
    WITH n, node_diff_map
    CALL {
        WITH n, node_diff_map
        WITH n, CASE
            WHEN node_diff_map.attributes IS NULL OR node_diff_map.attributes = [] THEN [NULL]
            ELSE node_diff_map.attributes
        END AS attribute_maps
        UNWIND attribute_maps AS attribute_diff_map
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
                OPTIONAL MATCH (n)-[has_attr:HAS_ATTRIBUTE]->(a:Attribute {name: attr_name})
                WHERE has_attr.branch IN [$source_branch, $target_branch]
                RETURN a
                ORDER BY has_attr.from DESC
                LIMIT 1
            }
            WITH n, attr_rel_status, a
            // ------------------------------
            // set HAS_ATTRIBUTE.to on target branch if necessary
            // ------------------------------
            CALL {
                WITH n, attr_rel_status, a
                OPTIONAL MATCH (n)
                    -[target_r_attr:HAS_ATTRIBUTE {branch: $target_branch, status: "active"}]
                    ->(a)
                WHERE attr_rel_status = "deleted"
                AND target_r_attr.from <= $at AND target_r_attr.to IS NULL
                SET target_r_attr.to = $at
            }
            WITH n, attr_rel_status, a
            // ------------------------------
            // conditionally create new HAS_ATTRIBUTE relationship on target_branch, if necessary
            // ------------------------------
            CALL {
                WITH n, attr_rel_status, a
                WITH n, attr_rel_status, a
                WHERE a IS NOT NULL
                OPTIONAL MATCH (n)-[r_attr:HAS_ATTRIBUTE {branch: $target_branch}]->(a)
                WHERE r_attr.status = attr_rel_status
                AND r_attr.from <= $at
                AND (r_attr.to >= $at OR r_attr.to IS NULL)
                WITH n, r_attr, attr_rel_status, a
                WHERE r_attr IS NULL
                CREATE (n)-[:HAS_ATTRIBUTE { branch: $target_branch, branch_level: $branch_level, from: $at, status: attr_rel_status }]->(a)
            }
            RETURN 1 AS done
        }
        RETURN 1 AS done
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
            // determine the directions of each IS_RELATED
            // ------------------------------
            CALL {
                WITH n, rel_name, rel_peer_id, related_rel_status
                MATCH (n)
                    -[source_r_rel_1:IS_RELATED]
                    -(r:Relationship {name: rel_name})
                    -[source_r_rel_2:IS_RELATED]
                    -(:Node {uuid: rel_peer_id})
                WHERE source_r_rel_1.branch IN [$source_branch, $target_branch]
                AND source_r_rel_2.branch IN [$source_branch, $target_branch]
                AND source_r_rel_1.from <= $at AND source_r_rel_1.to IS NULL
                AND source_r_rel_2.from <= $at AND source_r_rel_2.to IS NULL
                WITH n, rel_name, rel_peer_id, related_rel_status, r, source_r_rel_1, source_r_rel_2
                ORDER BY source_r_rel_1.branch_level DESC, source_r_rel_2.branch_level DESC, source_r_rel_1.from DESC, source_r_rel_2.from DESC
                LIMIT 1
                RETURN r, CASE
                    WHEN startNode(source_r_rel_1).uuid = n.uuid THEN "r"
                    ELSE "l"
                END AS r1_dir,
                CASE
                    WHEN startNode(source_r_rel_2).uuid = r.uuid THEN "r"
                    ELSE "l"
                END AS r2_dir,
                source_r_rel_1.hierarchy AS r1_hierarchy,
                source_r_rel_2.hierarchy AS r2_hierarchy
            }
            WITH n, r, r1_dir, r2_dir, r1_hierarchy, r2_hierarchy, rel_name, rel_peer_id, related_rel_status
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
            WITH n, r, r1_dir, r2_dir, r1_hierarchy, r2_hierarchy, rel_name, rel_peer_id, related_rel_status
            // ------------------------------
            // conditionally create new IS_RELATED relationships on target_branch, if necessary
            // ------------------------------
            CALL {
                WITH n, r, r1_dir, r2_dir, r1_hierarchy, r2_hierarchy, rel_name, rel_peer_id, related_rel_status
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
                WITH n, r, r1_dir, r2_dir, r1_hierarchy, r2_hierarchy, p, related_rel_status, r_rel_1, r_rel_2
                WHERE r_rel_1 IS NULL
                AND r_rel_2 IS NULL
                // ------------------------------
                // create IS_RELATED relationships with directions maintained from source
                // ------------------------------
                CALL {
                    WITH n, r, r1_dir, r1_hierarchy, related_rel_status
                    WITH n, r, r1_dir, r1_hierarchy, related_rel_status
                    WHERE r1_dir = "r"
                    CREATE (n)
                        -[:IS_RELATED {branch: $target_branch, branch_level: $branch_level, from: $at, status: related_rel_status, hierarchy: r1_hierarchy}]
                        ->(r)
                }
                CALL {
                    WITH n, r, r1_dir, r1_hierarchy, related_rel_status
                    WITH n, r, r1_dir, r1_hierarchy, related_rel_status
                    WHERE r1_dir = "l"
                    CREATE (n)
                        <-[:IS_RELATED {branch: $target_branch, branch_level: $branch_level, from: $at, status: related_rel_status, hierarchy: r1_hierarchy}]
                        -(r)
                }
                CALL {
                    WITH r, p, r2_dir, r2_hierarchy, related_rel_status
                    WITH r, p, r2_dir, r2_hierarchy, related_rel_status
                    WHERE r2_dir = "r"
                    CREATE (r)
                        -[:IS_RELATED {branch: $target_branch, branch_level: $branch_level, from: $at, status: related_rel_status, hierarchy: r2_hierarchy}]
                        ->(p)
                }
                CALL {
                    WITH r, p, r2_dir, r2_hierarchy, related_rel_status
                    WITH r, p, r2_dir, r2_hierarchy, related_rel_status
                    WHERE r2_dir = "l"
                    CREATE (r)
                        <-[:IS_RELATED {branch: $target_branch, branch_level: $branch_level, from: $at, status: related_rel_status, hierarchy: r2_hierarchy}]
                        -(p)
                }
            }
        }
    }
}
RETURN 1 AS done
        """
        self.add_to_query(query=query)


class DiffMergePropertiesQuery(Query):
    name = "diff_merge_properties"
    type = QueryType.WRITE
    insert_return = False

    def __init__(
        self,
        property_diff_dicts: dict[str, Any],
        at: Timestamp,
        target_branch: Branch,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.property_diff_dicts = property_diff_dicts
        self.at = at
        self.target_branch = target_branch
        self.source_branch_name = self.branch.name

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "property_diff_dicts": self.property_diff_dicts,
            "at": self.at.to_string(),
            "branch_level": self.target_branch.hierarchy_level,
            "target_branch": self.target_branch.name,
            "source_branch": self.source_branch_name,
        }
        query = """
UNWIND $property_diff_dicts AS attr_rel_prop_diff
CALL {
    // ------------------------------
    // find the Attribute node
    // ------------------------------
    WITH attr_rel_prop_diff
    CALL {
        WITH attr_rel_prop_diff
        OPTIONAL MATCH (n:Node {uuid: attr_rel_prop_diff.node_uuid})
            -[has_attr:HAS_ATTRIBUTE]
            ->(attr:Attribute {name: attr_rel_prop_diff.attribute_name})
        WHERE attr_rel_prop_diff.attribute_name IS NOT NULL
        AND has_attr.branch IN [$source_branch, $target_branch]
        RETURN attr
        ORDER BY has_attr.from DESC
        LIMIT 1
    }
    CALL {
        WITH attr_rel_prop_diff
        OPTIONAL MATCH (n:Node {uuid: attr_rel_prop_diff.node_uuid})
            -[r1:IS_RELATED]
            -(rel:Relationship {name: attr_rel_prop_diff.relationship_id})
            -[r2:IS_RELATED]
            -(:Node {uuid: attr_rel_prop_diff.peer_uuid})
        WHERE attr_rel_prop_diff.relationship_id IS NOT NULL
        AND r1.branch IN [$source_branch, $target_branch]
        AND r2.branch IN [$source_branch, $target_branch]
        RETURN rel
        ORDER BY r1.branch_level DESC, r2.branch_level DESC, r1.from DESC, r2.from DESC
        LIMIT 1
    }
    WITH attr_rel_prop_diff, COALESCE(attr, rel) AS attr_rel
    UNWIND attr_rel_prop_diff.properties AS property_diff
    // ------------------------------
    // handle updates for properties under this attribute/relationship
    // ------------------------------
    CALL {
        WITH attr_rel, property_diff
        // ------------------------------
        // identify the correct property node to link
        // ------------------------------
        CALL {
            WITH attr_rel, property_diff
            OPTIONAL MATCH (peer:Node {uuid: property_diff.value})
            WHERE property_diff.property_type IN ["HAS_SOURCE", "HAS_OWNER"]
            // ------------------------------
            // the serialized diff might not include the values for IS_VISIBLE and IS_PROTECTED in
            // some cases, so we need to figure them out here
            // ------------------------------
            CALL {
                WITH attr_rel, property_diff
                OPTIONAL MATCH (attr_rel)-[r_vis_pro]->(bool:Boolean)
                WHERE property_diff.property_type IN ["IS_VISIBLE", "IS_PROTECTED"]
                AND r_vis_pro.branch IN [$source_branch, $target_branch]
                AND type(r_vis_pro) = property_diff.property_type
                AND (property_diff.value IS NULL OR bool.value = property_diff.value)
                RETURN bool
                ORDER BY r_vis_pro.from DESC
                LIMIT 1
            }
            CALL {
                // ------------------------------
                // get the latest linked AttributeValue on the source b/c there could be multiple
                // with different is_default values
                // ------------------------------
                WITH attr_rel, property_diff
                OPTIONAL MATCH (attr_rel)-[r_attr_val:HAS_VALUE]->(av:AttributeValue)
                WHERE property_diff.property_type = "HAS_VALUE"
                AND (
                    av.value = property_diff.value
                    OR toLower(toString(av.value)) = toLower(toString(property_diff.value))
                )
                AND r_attr_val.branch IN [$source_branch, $target_branch]
                RETURN av
                ORDER BY r_attr_val.from DESC
                LIMIT 1
            }
            RETURN COALESCE (peer, bool, av) AS prop_node
        }
        WITH attr_rel, property_diff.property_type AS prop_type, prop_node, CASE
            WHEN property_diff.action = "ADDED" THEN "active"
            WHEN property_diff.action = "REMOVED" THEN "deleted"
            ELSE NULL
        END as prop_rel_status
        // ------------------------------
        // set property edge.to, optionally, on target branch
        // ------------------------------
        CALL {
            WITH attr_rel, prop_rel_status, prop_type
            OPTIONAL MATCH (attr_rel)
                -[target_r_prop {branch: $target_branch}]
                ->()
            WHERE type(target_r_prop) = prop_type
            AND target_r_prop.from < $at AND target_r_prop.to IS NULL
            SET target_r_prop.to = $at
        }
        // ------------------------------
        // check for existing edge on target_branch
        // ------------------------------
        CALL {
            WITH attr_rel, prop_rel_status, prop_type, prop_node
            OPTIONAL MATCH (attr_rel)-[r_prop {branch: $target_branch}]->(prop_node)
            WHERE type(r_prop) = prop_type
            AND r_prop.status = prop_rel_status
            AND r_prop.from <= $at
            AND (r_prop.to > $at OR r_prop.to IS NULL)
            RETURN r_prop
        }
        WITH attr_rel, prop_rel_status, prop_type, prop_node, r_prop
        WHERE r_prop IS NULL
        // ------------------------------
        // create new edge to prop_node on target_branch, if necessary
        // one subquery per possible edge type b/c edge type cannot be a variable
        // ------------------------------
        CALL {
            WITH attr_rel, prop_rel_status, prop_type, prop_node
            WITH attr_rel, prop_rel_status, prop_type, prop_node
            WHERE prop_type = "HAS_VALUE"
            CREATE (attr_rel)-[:HAS_VALUE { branch: $target_branch, branch_level: $branch_level, from: $at, status: prop_rel_status }]->(prop_node)
        }
        CALL {
            WITH attr_rel, prop_rel_status, prop_type, prop_node
            WITH attr_rel, prop_rel_status, prop_type, prop_node
            WHERE prop_type = "HAS_SOURCE"
            CREATE (attr_rel)-[:HAS_SOURCE { branch: $target_branch, branch_level: $branch_level, from: $at, status: prop_rel_status }]->(prop_node)
        }
        CALL {
            WITH attr_rel, prop_rel_status, prop_type, prop_node
            WITH attr_rel, prop_rel_status, prop_type, prop_node
            WHERE prop_type = "HAS_OWNER"
            CREATE (attr_rel)-[:HAS_OWNER { branch: $target_branch, branch_level: $branch_level, from: $at, status: prop_rel_status }]->(prop_node)
        }
        CALL {
            WITH attr_rel, prop_rel_status, prop_type, prop_node
            WITH attr_rel, prop_rel_status, prop_type, prop_node
            WHERE prop_type = "IS_VISIBLE"
            CREATE (attr_rel)-[:IS_VISIBLE { branch: $target_branch, branch_level: $branch_level, from: $at, status: prop_rel_status }]->(prop_node)
        }
        CALL {
            WITH attr_rel, prop_rel_status, prop_type, prop_node
            WITH attr_rel, prop_rel_status, prop_type, prop_node
            WHERE prop_type = "IS_PROTECTED"
            CREATE (attr_rel)-[:IS_PROTECTED { branch: $target_branch, branch_level: $branch_level, from: $at, status: prop_rel_status }]->(prop_node)
        }
    }
}
        """
        self.add_to_query(query=query)


class DiffMergeRollbackQuery(Query):
    name = "diff_merge_rollback"
    type = QueryType.WRITE
    insert_return = False

    def __init__(
        self,
        at: Timestamp,
        target_branch: Branch,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.at = at
        self.target_branch = target_branch
        self.source_branch_name = self.branch.name

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "at": self.at.to_string(),
            "target_branch": self.target_branch.name,
            "source_branch": self.source_branch_name,
        }
        query = """
        // ---------------------------
        // reset to times on target branch
        // ---------------------------
        CALL {
            OPTIONAL MATCH ()-[r_to {to: $at, branch: $target_branch}]-()
            SET r_to.to = NULL
        }
        // ---------------------------
        // reset from times on target branch
        // ---------------------------
        CALL {
            OPTIONAL MATCH ()-[r_from {from: $at, branch: $target_branch}]-()
            DELETE r_from
        }
        """
        self.add_to_query(query=query)
