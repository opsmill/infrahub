"""Close the edges of branch-agnostic fields schema removal made unreachable from any branch.

The candidates are handed in as a list of vertices.
"""

from infrahub.core.query.agnostic_retention import UNRETAINED_AGNOSTIC_FIELD_PREDICATE

# Expects a list variable `agnostic_candidates` in scope holding the `:Attribute` / `:Relationship`
# vertices, plus the `$global_branch_name` and `$at` parameters. It writes, but returns no rows,
# so the composing query's own RETURN is left untouched.
CLOSE_UNRETAINED_AGNOSTIC_FIELDS = """
CALL (agnostic_candidates) {
    %(unretained_predicate)s

    MATCH (field)-[unread_edge]-()
    WHERE unread_edge.branch = $global_branch_name
    AND unread_edge.status = "active"
    AND unread_edge.from <= $at
    AND unread_edge.to IS NULL
    SET unread_edge.to = $at
}
""" % {"unretained_predicate": UNRETAINED_AGNOSTIC_FIELD_PREDICATE}
