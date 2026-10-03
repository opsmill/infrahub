# Diff Conflict Resolvability

> Part of: `dev/knowledge/backend/` | Related: [merge-recompute.md](merge-recompute.md), [branch-status.md](branch-status.md)

`EnrichedDiffConflict.resolvable` means one thing: a merge can apply a selection. It is `False` only
on a node-level conflict where one side deleted the node (set in
`backend/infrahub/core/diff/conflicts_enricher.py`); attribute, relationship-property and
cardinality-one peer conflicts keep the default `True`, because a merge can apply either side. The
`ResolveDiffConflict` mutation refuses `resolvable=False`; other conflicts are resolved through the
mutation.

A rebase answers a narrower question. It keeps the branch's edge for every conflicting field, so it
honors only a resolution in favor of the branch, and only at the attribute level: a cardinality-one
peer conflict leaves both peers visible after the rebase, and a node removed on the default branch
cannot carry the branch's values. The gate is the explicit check in `rebase_branch`
(`backend/infrahub/core/branch/tasks.py`) — do not reuse `resolvable` as "rebasable".
