# 11. Inline evaluation of local Jinja2 computed attributes during update mutations

**Status:** Accepted
**Date:** 2026-07-31
**Author:** @opsmill-team

**Source:** `specs/archive/ifc-2273-local-computation-jinja2/research.md` (R1, R3, R5) and the scope
decisions recorded in that spec's `spec.md` Clarifications.

## Context

Jinja2 computed attributes were recomputed exclusively through Prefect background tasks triggered by
change events, except at node creation, which was already handled inline by `_process_macros()`. A
single bulk update of thousands of nodes spawned one background task per node, each re-querying the
database, even when the triggering change and the computed attribute lived on the same node. The
response to the originating mutation did not reflect the recomputed value, and a node could emit two
events: one for the original change and one for the later computed update.

The change had to integrate with the current automation structure, since the placeholder-automation
refactor (INFP-441) was scheduled separately and not available.

## Decision

Split recomputation by the locality of the triggering change.

A local change (the changed attribute or relationship is on the node that owns the computed
attribute) is evaluated inline during `Node._update()`, after attribute and relationship saves and
before HFID and display-label recomputation, and persisted in the same transaction and
`NodeChangelog`. The inline path reuses the template variable-resolution pattern from
`_process_macros()`, and loads the peer attributes that relationship-referencing templates need
through the existing `_collect_extra_filters()` mechanism, so no query is issued beyond the
`resolve_relationships()` the update already runs.

A remote change (a peer node attribute referenced by a computed attribute on another node) keeps the
existing Prefect background-task path unchanged.

The duplicate background path for local changes is suppressed by neutralizing self-targeting
triggers (`targets_self`) into placeholder field matchers that never match a real update event,
rather than deleting them, so the trigger definitions remain available for schema-change detection.
This mirrors the existing HFID and display-label handling.

The optimization is scoped to the update path. Node creation, template instantiation, and Python
transform computed attributes are unchanged. Both optional and mandatory Jinja2 computed attributes
recompute inline on local updates. On inline evaluation failure the error is logged and the value is
left unchanged; the mutation still succeeds, matching the background-task error semantics.

How the four evaluation paths, the `targets_self` neutralization, and the extra-filter peer loading
work is documented in [Computed Attributes](../knowledge/backend/computed-attributes.md).

## Consequences

### Positive

- Mutation responses immediately reflect recomputed local values, with no page refresh.
- Bulk updates of local computed attributes spawn zero background tasks for those recomputes.
- Each local mutation emits a single consolidated event, because inline computed updates are
  recorded in the same `NodeChangelog`.

### Negative

- Two evaluation paths now exist for the same attribute kind and must stay consistent: an inline
  result must match what the background path would produce for the same inputs.
- Inline evaluation errors are swallowed (logged, value left unchanged), a deliberate exception to
  the general "do not catch broadly" convention, justified by parity with the async path.

### Neutral

- The update path does more work per mutation. The cost is bounded by reusing already-loaded node
  state and peer data, and is a net reduction against the background-task fan-out it replaces.

## Alternatives Considered

### Hook at `Node.save()` or at the GraphQL `mutate_update()` level

Rejected as too high in the stack. `save()` also covers creation, which already recomputes inline,
and the GraphQL layer misses SDK and other non-GraphQL update paths.

### Delete self-targeting triggers entirely rather than converting them to placeholders

Rejected because it removes schema-change detection for those attributes. Placeholders keep the
definitions available while preventing them from matching real update events.

### Let both the inline and background paths run for local changes

Rejected due to double computation and the race between the two writes.

### Add a `locally_recomputed` flag to event payloads so the trigger can skip

Rejected as more coupling than the placeholder approach for the same effect.

### Re-fetch peer data with an extra query on relationship changes

Rejected as it defeats the performance goal. `_collect_extra_filters()` loads the peers during the
`resolve_relationships()` the update already performs.
