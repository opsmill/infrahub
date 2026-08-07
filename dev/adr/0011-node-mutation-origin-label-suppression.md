# 11. Suppress coalesced-family triggers with a node-mutation origin label

**Status:** Accepted
**Date:** 2026-07-31
**Author:** @opsmill-team

**Source:** `specs/archive/ifc-2761-coalesce-merge-recompute/research.md` (R3)

## Context

After a graph merge or rebase, the follow-up path replays each changed node as a
`NodeMutatedEvent`. Prefect matches every event against every recompute automation, so the
three derived-value families that read across relationships (Jinja2 computed attributes,
display labels, human-friendly ids) each start one per-node flow. That per-node fan-out is
exactly what the coalesced recompute pass exists to remove.

The events cannot simply be dropped on the merge/rebase path. The same per-node
`NodeCreated/Updated/Deleted` events are consumed by user-defined action and node-trigger
rules and by webhook delivery, none of which discriminate on where the change came from, and
all of which must keep firing on merge today. Same-node values are already free: self-targeting
triggers are built with a placeholder field that no real node event carries, so they never
match, and the same-node value is written inline during the save and carried over by the merge.
The asynchronous cost that matters is the cross-node triggers matching the replayed events.

## Decision

Keep emitting one `NodeMutatedEvent` per changed node, but stamp each with an `origin` label
(`live` | `merge` | `rebase` | `recompute`, default `live`) surfaced as a Prefect match label
(`infrahub.node.origin`). The three coalesced families' cross-node trigger builders add a match
so their per-node flows fire only on `live` events; the coalesced pass becomes their single
dispatcher for merge and rebase. The bulk writer stamps `recompute` on its own writes so a
chained recompute does not re-enter the per-node path either.

Families that are not coalesced in this pass keep receiving every event whatever the origin:
Python-transform computed attributes, profile refresh, user action rules, and webhooks.

## Consequences

### Positive

- Action rules and webhooks keep working across merge and rebase; nothing is silently broken by
  dropping events.
- The three families are dispatched exactly once, by the coalesced pass, with no
  double-processing.
- The label is an explicit, matchable signal. It is cleaner than deriving origin from event
  lineage (`meta.parent` / `meta.ancestors`), which Prefect cannot match on.

### Negative

- Suppression only removes the trigger. The coalesced pass MUST itself recompute the cross-node
  readers those suppressed events used to drive; missing that is the main correctness gap.
- Every future family that should be coalesced has to remember to add the `live`-only match, or
  it will double-process on merge and rebase.

### Neutral

- The origin is stamped at three sites: the merge post-process, the rebase flow, and the bulk
  writer (for `recompute`).

## Alternatives Considered

### Drop per-node event emission on the merge/rebase path

Rejected. User action rules and webhooks consume the same events with no origin discrimination
and rely on them firing on merge, so dropping emission silently breaks them.

### Derive the origin from event lineage instead of a label

Rejected. The merge/rebase relationship is present in `meta.parent` / `meta.ancestors`, but that
lineage is not exposed as a Prefect match label, so a trigger cannot filter on it. A dedicated
`EventMeta` field surfaced as a label is matchable.
