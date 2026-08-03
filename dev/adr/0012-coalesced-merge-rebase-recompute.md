# 12. Coalesced deduplicated recompute pass on merge and rebase

**Status:** Accepted
**Date:** 2026-07-31
**Author:** @opsmill-team

**Source:** `specs/archive/ifc-2761-coalesce-merge-recompute/research.md` (R1, R2, R4, R5); `specs/archive/ifc-2761-merge-recompute-profile/findings.md`

## Context

Merge and rebase do not recompute derived values themselves. After the graph merge they walk
the diff changelog, emit one node event per changed node, and Prefect starts one flow per event
per family, each running its own reader query and one update per reader. There is no batching and
no dedup across nodes.

Profiling the path established where the cost lives. The synchronous merge call is fixed
overhead: its duration does not grow with the size of the change. The trailing asynchronous
recompute fan-out is the opposite: it grows linearly with the change (the profiled cross-node
case ran about two recompute jobs per changed node) and comes to dominate, so at scale it dwarfs
the merge call itself and stretches the degraded-instance window from seconds into minutes.
Same-node values recompute inline during the save and cost nothing asynchronously; the growing
cost is the cross-node readers, plus every derived value carried by a created node. So the lever
is the number of recompute jobs the merge's node events dispatch, not the merge transaction.

## Decision

Intercept at the point where the full set of changed `(kind, field)` pairs and created/deleted
nodes is already known (the merge post-process, the rebase flow) and submit one coalesced
recompute instead of the per-node events. Build a deduplicated target set grouped by change
signature, then resolve the affected reader ids with one query over the union of readers per
family, never one flow plus one reader query per changed node. Submit one batched flow per
affected derived value, reusing the existing per-family process flows and chunking.

A shared coordinator serves both operations; only the branch differs, merge recomputing on the
destination branch and rebase on the user branch. The pass covers Jinja2 computed attributes,
display labels, and human-friendly ids. It reuses the computed-attribute deriver and adds
display-label and HFID derivers built from the dependency metadata already recorded on those
definitions. It recomputes all affected readers on the correct branch, which never
under-recomputes, and defers any source-branch redundancy skip.

## Consequences

### Positive

- Work scales with the number of affected derived values, not changed-node count times
  automations. The degraded-instance window stops growing linearly with the change size.
- The stored values are identical to the per-node path; only the dispatch changes.
- One shared coordinator handles merge and rebase; the branch argument is the only difference.

### Negative

- The coalesced pass must itself drive the cross-node readers the suppressed per-node events used
  to handle. A missed family or cross-node case silently under-recomputes.
- Display-label and HFID derivers had to be built, since no shared deriver existed for those
  families; they follow the computed-attribute pattern.
- Recomputing all readers on the correct branch can redo readers already correct on the source
  branch. This over-recompute is accepted (see below).

### Neutral

- Python-transform computed attributes and profile refresh stay on their own automations, outside
  this pass.
- Readers of a recompute write are handled by a schema-derived, depth-bounded chain submitter.

## Alternatives Considered

### Keep the per-node fan-out

Rejected. It is the measured bottleneck: recompute jobs grow linearly with the change and reach
minutes of degraded service at scale.

### One flow plus one reader query per changed node

Rejected. That is the N+1 fan-out being removed. Reader resolution must batch into one union
query per family so cost tracks affected values, not changed nodes.

### Skip readers already recomputed on the source branch

Deferred. A reader is provably redundant only under a strict conjunction (reader and its
relationship present on the source branch, the best-effort source fan-out actually completed
before merge, the merged value not base-resolved by conflict handling, no schema or template
change to its derivation). Proving it needs a source-versus-destination query plus a
conflict-resolution check whose cost rivals the recompute avoided, while adding correctness risk.
Revisit only if reader overlap is later measured as a hotspot.
