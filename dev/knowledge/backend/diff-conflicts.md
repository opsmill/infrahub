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
resolution in favor of the branch cannot save it. A conflict on any owner list or source list is
attribute-level in the diff, but it also blocks the rebase. These lists are the owners of a node
(`node_metadata__owners`), of an attribute (the `HAS_OWNER` property of the attribute) and of a
relationship field, the owners that a profile or an object template gives, and the sources of a
node (`node_metadata__sources`). Each list is a set of edges, so the branch would read the owners or
the sources that the default branch added next to its own. The gate is the explicit
check in `rebase_branch` (`backend/infrahub/core/branch/tasks.py`) — do not reuse `resolvable` as
"rebasable".

A merge can apply either side of a conflict on the owners of a node or of an attribute. In favor of
the default branch, it skips the owner edges of the holder. In favor of the branch, it merges each
owner edge and then gives the holder the list of owners of the branch (`OwnerDiffResolution` in
`backend/infrahub/core/diff/merger/exclusion_plan.py`), because the owners that only the default
branch added would stay otherwise. The default branch can delete the node after the last diff
update, so the merge skips the list of a node that is not active, and logs a warning.

The diff reads the owners of an attribute as one list, like the owners of a node:
`DiffQueryParser` skips the `HAS_OWNER` paths of attributes, and `OwnershipDiffer` adds one
`HAS_OWNER` property with the whole list to the attribute. The `HAS_OWNER` property of a
relationship link keeps one owner ID. `DiffCalculator` reads the owner changes of the branch before
the queries of the default branch, and adds each changed node to their scope. So a node that the
default branch deletes gives a node conflict, also when the branch changed only its owners or
sources.

A holder can lose the `HAS_OWNER_SOURCE` mark of a copy from an object template and keep its
owners. The diff shows this holder as an update with the same list at both ends, because the merge
closes the mark on the default branch. Such an update gives no conflict with a change of the list
on the other branch (`ConflictsEnricher._have_same_value`).

The owners of a relationship field, and the owners that a profile or an object template gives to
its nodes or to one field, show as an attribute with a reserved name: `<relationship>__owners`,
`node_metadata__target_owners` and `<field>__target_owners`. The schema of the diff branch gives
the field name from the key of the `OwnerSet`, so a set whose field the schema lacks is not in the
diff. The merge reads the edges and not the diff, so it still merges that set.
`MergeExclusionPlanBuilder` needs the schema of the source branch to find the set of a resolved
conflict from its reserved name. When that schema lacks the field, the merge skips the resolution
and writes a log line.

The sources of a node show as the attribute `node_metadata__sources`, with one `HAS_SOURCE` property
that holds the whole list of sources. The rules of an owner list apply to it: the conflict rule, the
two resolutions of the merge, and the block of the rebase. `is_list_property` in
`backend/infrahub/core/ownership/fields.py` tells this property apart from the `HAS_SOURCE`
property of an attribute, which keeps one source ID.
