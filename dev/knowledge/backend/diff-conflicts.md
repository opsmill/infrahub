# Diff Conflict Resolvability

> Part of: `dev/knowledge/backend/` | Related: [merge-recompute.md](merge-recompute.md), [branch-status.md](branch-status.md)

`EnrichedDiffConflict.resolvable` means one thing: a merge can apply a selection. It is `False` only
on a node-level conflict where one side deleted the node (set in
`backend/infrahub/core/diff/conflicts_enricher.py`); attribute, relationship-property and
cardinality-one peer conflicts keep the default `True`, because a merge can apply either side. The
`ResolveDiffConflict` mutation refuses `resolvable=False`; other conflicts are resolved through the
mutation.

A rebase answers a narrower question. It keeps the branch's edge for every conflicting field, so the
only conflict it lets through is an attribute-level one whose default-branch side is not a removal,
resolved in favor of the branch. Such a conflict resolved the other way must be resolved in favor of
the branch first; every other conflict — an attribute the default branch removed, node-level,
relationship, cardinality-one peer — blocks the rebase until the data is updated so both branches
agree. A removed attribute leaves the branch's value edge hanging from nothing, which is why a
resolution in favor of the branch cannot save it. The gate is the explicit check in
`rebase_branch` (`backend/infrahub/core/branch/tasks.py`) — do not reuse `resolvable` as
"rebasable".
