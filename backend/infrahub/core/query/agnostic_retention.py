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

Assumption: every branch forks from the default branch. A branch-of-branch feature would not extend
this logic.
"""

# Expects `field` in scope, one row per candidate vertex, plus the `$global_branch_name` and `$at`
# parameters. Emits the candidates no branch retains, with `field` as the only variable in scope.
UNRETAINED_AGNOSTIC_FIELD_PREDICATE = """
WITH collect(field) AS candidates

// ----------------------
// The branches are read once for the whole run and carried as a list.
// ----------------------
MATCH (branch:Branch)
WHERE branch.name <> $global_branch_name
WITH
    candidates,
    collect({
        name: branch.name,
        origin_name: CASE WHEN branch.is_default THEN NULL ELSE branch.origin_branch END,
        origin_at: CASE
            WHEN branch.is_default THEN NULL
            WHEN branch.branched_from < $at THEN branch.branched_from
            ELSE $at
        END
    }) AS branch_windows

UNWIND candidates AS field
WITH field, branch_windows, CASE WHEN field:Relationship THEN 2 ELSE 1 END AS required_live_peers

CALL (field, branch_windows) {
    UNWIND branch_windows AS branch_window
    WITH
        field,
        branch_window.name AS branch_name,
        branch_window.origin_name AS origin_name,
        branch_window.origin_at AS origin_at

    // ----------------------
    // Count this `field`'s  active links to :Node vertices on this branch
    // ----------------------
    MATCH (node:Node)-[field_edge:HAS_ATTRIBUTE|IS_RELATED]-(field)
    WHERE (field_edge.branch IN [$global_branch_name, branch_name]
           AND field_edge.from <= $at
           AND (field_edge.to IS NULL OR field_edge.to > $at))
       OR (field_edge.branch = origin_name
           AND field_edge.from <= origin_at
           AND (field_edge.to IS NULL OR field_edge.to > origin_at))
    WITH
        branch_name,
        origin_name,
        origin_at,
        node,
        field_edge.branch_level AS field_edge_level,
        field_edge.from AS field_edge_from,
        field_edge.status AS field_edge_status
    ORDER BY field_edge_level DESC, field_edge_from DESC, field_edge_status ASC
    WITH
        branch_name,
        origin_name,
        origin_at,
        node,
        collect(field_edge_status)[0] AS winning_field_edge_status
    WHERE winning_field_edge_status = "active"

    // ----------------------
    // Check that each linked :Node vertex is active on this branch.
    // The global branch stays in the existence match so that an owner which is itself branch-agnostic
    // reads as live on every branch and is therefore retained.
    // ----------------------
    MATCH (node)-[existence:IS_PART_OF]->(:Root)
    WHERE (existence.branch IN [$global_branch_name, branch_name]
           AND existence.from <= $at
           AND (existence.to IS NULL OR existence.to > $at))
       OR (existence.branch = origin_name
           AND existence.from <= origin_at
           AND (existence.to IS NULL OR existence.to > origin_at))
    WITH
        branch_name,
        node,
        existence.branch_level AS existence_level,
        existence.from AS existence_from,
        existence.status AS existence_status
    ORDER BY existence_level DESC, existence_from DESC, existence_status ASC
    WITH branch_name, node, collect(existence_status)[0] AS winning_existence
    WHERE winning_existence = "active"

    // ----------------------
    // Peers are counted by uuid. Kind/inheritance migration leaves multiple Node vertices with
    // the same uuid for a single entity
    // ----------------------
    WITH branch_name, count(DISTINCT node.uuid) AS live_peer_count
    RETURN max(live_peer_count) AS most_live_peers
}

WITH field, required_live_peers, coalesce(most_live_peers, 0) AS live_peers
WHERE live_peers < required_live_peers
"""
