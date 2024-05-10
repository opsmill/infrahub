// all updated edges
MATCH (p:Node|Attribute|Relationship)-[diff_rel]->(q)
WHERE diff_rel.branch IN ['main', "atl1-delete-upstream"]
AND diff_rel.from >= "2024-05-09T15:39:11.099780Z"
AND diff_rel.from <= "2024-05-09T15:39:40.099780Z"
AND (
    diff_rel.to IS NULL
    OR (diff_rel.to >= "2024-05-09T15:39:11.099780Z" AND diff_rel.to <= "2024-05-09T15:39:40.099780Z")
)
AND p.branch_support IN ["aware"]
// deepest diff edges properties, flags, and value
CALL {
    WITH p, q, diff_rel
    OPTIONAL MATCH path = (
        (:Root)<-[r_root:IS_PART_OF]-(:Node)-[r_node:HAS_ATTRIBUTE|IS_RELATED]-(p:Attribute|Relationship)-[diff_rel:IS_VISIBLE|IS_PROTECTED|HAS_SOURCE|HAS_OWNER|HAS_VALUE]->(q:Boolean|Node|AttributeValue)
    )
    WHERE ALL(
        r in [r_root, r_node]
        WHERE r.from <= "2024-05-09T15:39:40.099780Z" AND (r.to IS NULL or r.to >= "2024-05-09T15:39:40.099780Z")
        AND r.branch IN ['main', 'atl1-upstream-delete']
    )
    RETURN path AS diff_rel_path
    ORDER BY
        r_node.branch = diff_rel.branch DESC,
        r_root.branch = diff_rel.branch DESC,
        r_node.from DESC,
        r_root.from DESC
    LIMIT 1
}
// middle-level edges, has_attribute, is_related
WITH p, q, diff_rel, CASE WHEN diff_rel_path IS NOT NULL THEN [diff_rel_path] ELSE [] END AS full_diff_paths
CALL {
    WITH p, q, diff_rel
    OPTIONAL MATCH path = (
        (:Root)<-[r_root:IS_PART_OF]-(p:Node)-[diff_rel:HAS_ATTRIBUTE|IS_RELATED]-(q:Attribute|Relationship)-[r_prop:IS_VISIBLE|IS_PROTECTED|HAS_SOURCE|HAS_OWNER|HAS_VALUE|IS_RELATED]-(prop:Boolean|Node|AttributeValue)
    )
    WHERE ALL(
        r in [r_root, r_prop]
        WHERE r.from <= "2024-05-09T15:39:40.099780Z" AND (r.to IS NULL or r.to >= "2024-05-09T15:39:40.099780Z")
        AND r.branch IN ['main', 'atl1-upstream-delete']
    )
    AND p <> prop
    WITH path, q, prop, r_prop, r_root
    ORDER BY
        q,
        prop,
        r_prop.branch = diff_rel.branch DESC,
        r_root.branch = diff_rel.branch DESC,
        r_prop.from DESC,
        r_root.from DESC
    WITH q, prop, head(collect(path)) AS latest_path
    RETURN latest_path
}
WITH p, q, diff_rel, full_diff_paths, collect(latest_path) AS latest_paths
WITH p, q, diff_rel, full_diff_paths + latest_paths AS full_diff_paths
// whole node-paths - IS_PART_OF
CALL {
    WITH p, q, diff_rel
    OPTIONAL MATCH path = (
        (q:Root)<-[diff_rel:IS_PART_OF]-(p:Node)-[r_node:HAS_ATTRIBUTE|IS_RELATED]-(node:Attribute|Relationship)-[r_prop:IS_VISIBLE|IS_PROTECTED|HAS_SOURCE|HAS_OWNER|HAS_VALUE|IS_RELATED]-(prop:Boolean|Node|AttributeValue)
    )
    WHERE ALL(
        r in [r_node, r_prop]
        WHERE r.from <= "2024-05-09T15:39:40.099780Z" AND (r.to IS NULL or r.to >= "2024-05-09T15:39:40.099780Z")
        AND r.branch IN ['main', 'atl1-upstream-delete']
    )
    AND p <> prop
    WITH path, node, prop, r_prop, r_node
    ORDER BY
        node,
        prop,
        r_prop.branch = diff_rel.branch DESC,
        r_node.branch = diff_rel.branch DESC,
        r_prop.from DESC,
        r_node.from DESC
    WITH node, prop, head(collect(path)) AS latest_path
    RETURN latest_path
}
WITH p, q, diff_rel, full_diff_paths, collect(latest_path) AS latest_paths
WITH p, q, diff_rel, full_diff_paths + latest_paths AS full_diff_paths
RETURN full_diff_paths
