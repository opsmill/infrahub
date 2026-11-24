# 24. The merge and the rebase refresh the profiles they replay

**Status:** Accepted
**Date:** 2026-10-28
**Author:** @opsmill-team

## Context

[ADR 0016](0016-node-mutation-origin-label-suppression.md) gave each node mutation event an origin,
and [ADR 0017](0017-coalesced-merge-rebase-recompute.md) made one coalesced pass the dispatcher of
the derived values of a merge or a rebase. The profile refresh automation stayed outside both: it
matched a profile update whatever its origin.

A merge replays each changed profile as a `merge` event. The automation then refreshed every node
and template linked to the profile on the destination. For the nodes that the branch had already
refreshed, the merge carries the profile values over, so that refresh wrote nothing but still read
each node, its profiles and the profile data. A rebase did the same on the branch with `rebase`
events. A rebase replays every change of the branch, and the changes of the default branch only for
the kinds whose schema the branch changed.

A refresh is still needed for:

- nodes created on the destination, or linked to the profile there, after the last rebase;
- nodes whose other profiles changed on the destination;
- branch refreshes still pending or failed when the merge ran;
- attribute conflicts resolved in favour of the destination;
- on a rebase, the same cases with the default branch as the other side, for the changes that the
  rebase replays.

## Decision

The profile refresh automation matches only `live` events, as the per-node triggers of the
coalesced families do. After the coalesced pass, the merge post-process and the rebase flow submit
one `profile-refresh-process` run for each replayed profile whose refresh fields changed, on the
target branch. The run reads the ids of the linked nodes and templates page by page, as for a live
change, and leaves out a node only when, for each attribute the profile changed, the node holds the
current value of the profile and the profile is the source of that value.

The check reads the stored state after the merge or the rebase, not the diff. A destination change
that moves the winning profile of a node moves the source of its value, even when the value stays
the same, so the check refreshes that node. A branch refresh that did not run leaves the old value,
and a node created or linked on the destination has the value of that side or none, so the check
refreshes them too.

A change that the check cannot judge from the changed attributes refreshes every linked node: a
change to the priority, which can move the winning profile of any attribute, and a change to a
relationship. A rebase replays a profile from both branches only when both changed it and the branch
changed the schema of its kind. The check then uses the union of the attributes the two sides
changed. The rebase keeps its refresh of the nodes whose profiles the branch changed.

## Consequences

### Positive

- A merge of a branch that refreshed every linked node submits no refresh for them. The cost moves
  from a refresh flow per chunk of nodes to one read of the changed attributes, with their source,
  for each page of linked nodes, in the `profile-refresh-process` run.
- The merge and the rebase flows only submit one run per replayed profile. The reads run outside
  the merge lock, and a failed run shows as a failed flow run.

### Negative

- Each page of linked nodes costs one more read in the run, also when no node of the page holds the
  value.

### Neutral

- A node unlinked from the profile on the destination is not in the linked set, so it is not
  refreshed. The automation did not refresh it either.

## Alternatives Considered

### Skip the nodes whose replayed changelog holds the new value and that have no diff conflict

Rejected. A conflict is detected for each property of an attribute, so a destination change to the
source alone, with the same value, makes no conflict. Masked values, such as passwords, also compare
equal in a changelog. Both cases would leave a wrong value.

### Keep the automation for `merge` and `rebase` events, with the check

Rejected. ADR 0016 makes the post-process the single dispatcher of a merge or a rebase replay. The
post-process holds every replayed changelog, so it decides once which attributes the check can use,
including for a profile replayed from both branches.
