"""The one predicate that decides whether a branch-agnostic field is still retained by any branch.

A branch-agnostic field keeps its value on edges carrying the global branch name, which every branch
reads. Those edges may only be closed once **NO** branch can still reach a live owner over a live field
edge. Cypher for this is consolidated here to ensure consistency.

Retention is decided per branch **and** per linked vertex: under that branch's view, the vertex's
existence edge and its edge to the field must both resolve to `active`. Surviving edges are summed
per branch, and only then is the maximum taken across branches. Retention is a disjunction of what
each branch holds live on its own, never a pool the branches contribute to jointly.

A `:Relationship` needs two qualifying field edges rather than one, because a relationship missing a
peer is not a relationship. A `:Relationship` must also have two distinct active peers to be
considered active.

The winner lookups are OPTIONAL CALL subqueries and the peers are counted conditionally rather than
filtered so that a field with no live edge on a branch reaches the end of the predicate carrying a
count of zero -- a plain CALL or MATCH would drop its row instead.

Assumption: every branch forks from the default branch. A branch-of-branch feature would not extend
this logic.
"""

# Expects `agnostic_candidates` in scope: a list of the candidate `:Attribute` / `:Relationship`
# vertices, plus the `$global_branch_name` and `$at` parameters. Emits one row per candidate that no
# branch retains, with `field` as the only variable in scope.
UNRETAINED_AGNOSTIC_FIELD_PREDICATE = """
// ----------------------
// The branches are read once for the whole run and carried as a list.
// ----------------------
MATCH (branch:Branch)
WHERE branch.name <> $global_branch_name
WITH
    agnostic_candidates,
    collect({
        name: branch.name,
        origin_name: CASE WHEN branch.is_default THEN NULL ELSE branch.origin_branch END,
        origin_at: CASE
            WHEN branch.is_default THEN NULL
            WHEN branch.branched_from < $at THEN branch.branched_from
            ELSE $at
        END
    }) AS branch_windows

UNWIND agnostic_candidates AS field
WITH DISTINCT field, branch_windows
// ----------------------
// Quick filter to remove all fields with no active edges on the global branch, covers most fields
// ----------------------
WHERE EXISTS {
    MATCH (field)-[global_edge]-()
    WHERE global_edge.branch = $global_branch_name
      AND global_edge.status = "active"
      AND global_edge.to IS NULL
}
WITH field, branch_windows, CASE WHEN field:Relationship THEN 2 ELSE 1 END AS required_live_peers

// ----------------------
// Get all the possible peer :Nodes for each field. Usually 1 for :Attribute and 2 for :Relationship
// ----------------------
OPTIONAL MATCH (node:Node)-[:HAS_ATTRIBUTE|IS_RELATED]-(field)
WITH DISTINCT field, branch_windows, required_live_peers, node

UNWIND branch_windows AS branch_window
WITH
    field,
    required_live_peers,
    node,
    branch_window.name AS branch_name,
    branch_window.origin_name AS origin_name,
    branch_window.origin_at AS origin_at

// ----------------------
// Resolve the status of this peer's latest edge to the field on this branch.
// ----------------------
OPTIONAL CALL (field, node, branch_name, origin_name, origin_at) {
    MATCH (node)-[field_edge:HAS_ATTRIBUTE|IS_RELATED]-(field)
    WHERE (field_edge.branch IN [$global_branch_name, branch_name]
           AND field_edge.from <= $at
           AND (field_edge.to IS NULL OR field_edge.to > $at))
       OR (field_edge.branch = origin_name
           AND field_edge.from <= origin_at
           AND (field_edge.to IS NULL OR field_edge.to > origin_at))
    RETURN field_edge.status AS latest_field_edge_status
    ORDER BY field_edge.branch_level DESC, field_edge.from DESC, field_edge.status ASC
    LIMIT 1
}

// ----------------------
// Resolve whether this peer exists on this branch.
// The global branch stays in the existence match so that an owner which is itself branch-agnostic
// reads as live on every branch and is therefore retained.
// ----------------------
OPTIONAL CALL (node, branch_name, origin_name, origin_at) {
    MATCH (node)-[existence:IS_PART_OF]->(:Root)
    WHERE (existence.branch IN [$global_branch_name, branch_name]
           AND existence.from <= $at
           AND (existence.to IS NULL OR existence.to > $at))
       OR (existence.branch = origin_name
           AND existence.from <= origin_at
           AND (existence.to IS NULL OR existence.to > origin_at))
    RETURN existence.status AS latest_existence
    ORDER BY existence.branch_level DESC, existence.from DESC, existence.status ASC
    LIMIT 1
}

// ----------------------
// Peers are counted by uuid. Kind/inheritance migration leaves multiple Node vertices with
// the same uuid for a single entity.
// ----------------------
WITH
    field,
    required_live_peers,
    branch_name,
    count(DISTINCT CASE
        WHEN latest_field_edge_status = "active" AND latest_existence = "active" THEN node.uuid
    END) AS live_peer_count

WITH field, required_live_peers, max(live_peer_count) AS most_live_peers
WHERE most_live_peers < required_live_peers
WITH field
"""
